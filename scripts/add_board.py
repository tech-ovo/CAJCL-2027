"""Give real people accounts, without putting their names in the repository.

    modal run backend/app.py::board                 # against the live database
    python scripts/add_board.py --db dev.db         # against a local file

WHY THE NAMES ARE NOT IN THIS FILE
    This repository is public, and the demonstration is projected in a room.
    Everything in scripts/seed.py is invented for exactly that reason. Real
    board members are real people, so their names live in `board.json` in the
    project folder, which is listed in .gitignore and never committed.

    docs/DEPLOY.md step 4b shows the shape and the role names.

RUNNING IT TWICE IS SAFE
    A person is matched on first name, last name, and chapter. Someone already
    there keeps their account, their id, and their existing code; only their
    roles are brought into line with the file. Nobody gets a second account and
    nobody is silently signed out.

    `--new-codes` is the exception, and it says what it does: it issues fresh
    codes and revokes every session opened with the old ones.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# The backend is imported INSIDE the functions that need it, not here.
#
# `load()` and `report()` are pure text handling, and they are the only parts
# the Modal entrypoint runs on your own machine -- the database work happens in
# the container. Importing backend.lib at module level dragged in clock.py,
# which needs a time-zone database, so `modal run ... ::board` failed on Windows
# before it had read a single line of board.json.
#
# Keeping the import local means the entrypoint works on any machine, and the
# heavy import happens exactly where the heavy work does.

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_FILE = ROOT / "board.json"

# Where a board member who is not a chapter's sponsor is filed. It is an
# organization rather than a chapter, so these people never appear in the public
# school count, never land on the chair dashboard as a delegation, and never
# generate an invoice.
BOARD_SCHOOL = "CAJCL State Board"

# Authority beyond one chapter. `sponsor` is deliberately not here: every
# chapter has one, they arrive with the roster, and a file listing all fifty of
# them is not a board.
CONVENTION_ROLES = frozenset({
    "admin", "registration_chair", "academics_chair", "awards_chair",
})


class BoardError(Exception):
    pass


def load(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        raise BoardError(
            f"no {path.name} found.\n"
            f"Create {path.name} in the project folder — docs/DEPLOY.md "
            f"step 4b shows the shape. It is gitignored, so the names never "
            f"reach the repository.")
    people = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(people, list):
        raise BoardError(f"{path.name} should hold a list of people.")

    for index, person in enumerate(people, start=1):
        for required in ("first", "last", "title"):
            if not person.get(required):
                raise BoardError(
                    f"entry {index} in {path.name} has no {required!r}.")
        # `roles` must be PRESENT but may be empty. Somebody with a title and
        # no permissions is a real thing -- an awards chair, before the awards
        # pages exist -- and giving them a role that reaches nothing, so the
        # file does not look wrong, is how a permission ends up granted for no
        # reason and never taken away.
        if "roles" not in person or not isinstance(person["roles"], list):
            raise BoardError(
                f"entry {index}: 'roles' should be a list, and [] is allowed.")
    return people


def _school_id(tx, name: str, entry: dict, *, create: bool) -> int:
    from backend.lib import clock

    for row in tx.all("schools.all_including_organizations"):
        if row["name"].strip().lower() == name.strip().lower():
            return row["id"]

    if not create:
        known = ", ".join(sorted(
            r["name"] for r in tx.all("schools.all_including_organizations")))
        raise BoardError(
            f"no chapter called {name!r}.\n"
            f"Known: {known}\n"
            f"Pass --create-schools to add it, or fix the spelling. A typo "
            f"would otherwise create a second chapter that looks right in a "
            f"list and holds nobody.")

    now = clock.now_iso()
    school_id = tx.insert("schools.create", (
        name, entry.get("level", "HS"), "chapter",
        entry.get("city") or "Irvine",
        0, 0, None, None, now, now))
    tx.run("schools.stats_init", (school_id, now))
    return school_id


def _find(tx, school_id: int, first: str, last: str) -> dict | None:
    for row in tx.all("admin.people_search", (school_id,)):
        if (row["first_name"].strip().lower() == first.strip().lower()
                and row["last_name"].strip().lower() == last.strip().lower()):
            return dict(row)
    return None


# What somebody IS, as opposed to what they have been asked to do.
#
# `board.json` declares convention roles -- admin, registration_chair. It says
# nothing about being a delegate, because everybody in it is one by default and
# saying so in every entry would be noise.
#
# Reconciling roles to exactly the file therefore REVOKED these, and a
# registration chair lost the `delegate` role that lets them open their own
# activity sheet. They could run the convention and not fill in their own form:
# the button was there, and it led to "You do not have access".
IDENTITY_ROLES = {
    "delegate": "delegate",          # person_type
    "sponsor": "sponsor",            # adult_type
}


def _identity_role(person_type: str, adult_type: str | None) -> str | None:
    if person_type == "delegate":
        return "delegate"
    if adult_type == "sponsor":
        return "sponsor"
    return None


def _set_roles(tx, person_id: int, wanted: list[str], now: str,
               *, keep: str | None = None) -> list[str]:
    """Bring a person's roles into line with the file. Returns what changed.

    `keep` is the identity role, which is granted if missing and never revoked
    however the file is written.
    """
    wanted = list(wanted)
    if keep and keep not in wanted:
        wanted.append(keep)

    have = {row["key"] for row in tx.all("people.roles_of", (person_id,))}
    changes = []

    for key in wanted:
        if key in have:
            continue
        role = tx.one("roles.by_key", (key,))
        if role is None:
            raise BoardError(
                f"no role called {key!r}. Create it in Settings > Roles first.")
        tx.run("people.grant_role", (person_id, role["id"], None, now))
        changes.append(f"+{key}")

    for key in sorted(have - set(wanted)):
        role = tx.one("roles.by_key", (key,))
        tx.run("people.revoke_role", (person_id, role["id"]))
        changes.append(f"-{key}")

    return changes


def run(db, people: list[dict], *,
        new_codes: bool = False, create_schools: bool = False) -> dict:
    from backend.lib import auth, clock, settings as settings_lib, stats

    results = []

    for entry in people:
        first = entry["first"].strip()
        middle = (entry.get("middle") or "").strip() or None
        last = entry["last"].strip()
        title = entry["title"].strip()
        roles = list(entry["roles"])
        school_name = (entry.get("school") or "").strip() or BOARD_SCHOOL

        # MOST OF THE BOARD ARE STUDENTS.
        #
        # A convention president is a delegate at their own chapter who also
        # holds a convention role -- exactly like a chapter leader. One person,
        # one account, one code; the role is granted on top.
        #
        # Filing them as adults to make `adult_type_other` available for their
        # title gave them the Adult Registration Form instead of the Student
        # Activity Sheet, so a president could not complete the form every
        # other delegate completes and their roster row read "Not yet" forever.
        # `board_title` exists so the title has somewhere to live that is not
        # an adult-only column.
        #
        # Delegate is the DEFAULT, because it is the common case. An entry says
        # `"type": "adult"` only for a sponsor or a chaperone.
        person_type = (entry.get("type") or "delegate").strip().lower()
        if person_type not in ("delegate", "adult"):
            raise BoardError(
                f"{first} {last}: 'type' must be \"delegate\" or \"adult\", "
                f"not {person_type!r}.")

        with db.tx() as tx:
            now = clock.now_iso()
            school_id = _school_id(tx, school_name, entry,
                                   create=create_schools)
            existing = _find(tx, school_id, first, last)

            # A delegate has no adult_type at all -- the database refuses one.
            if person_type == "delegate":
                adult_type = None
                adult_type_other = None
            else:
                is_sponsor = "sponsor" in roles
                adult_type = "sponsor" if is_sponsor else "other"
                adult_type_other = None if is_sponsor else title

            if existing:
                person_id = existing["id"]
                action = "already there"

                # Bring the TITLE into line too, not only the roles.
                #
                # This file is declarative: what it says is what should be
                # true. Reconciling roles but leaving the title alone meant a
                # correction here was silently ignored for anybody who already
                # existed -- and the two people the seed creates arrive with no
                # title at all, so they kept showing as "Board member" no
                # matter what the file said.
                #
                # It does mean the file wins over a rename made in Settings.
                # That is the right way round for the people it names: the file
                # is the record, and the next run is where the two are
                # reconciled.
                if (existing.get("adult_type") != adult_type
                        or existing.get("adult_type_other") != adult_type_other
                        or existing.get("board_title") != title
                        or existing.get("person_type") != person_type):
                    tx.run("people.set_board_identity", (
                        first, middle, last, person_type, adult_type,
                        adult_type_other, title, now, person_id))
                    changed_title = True
                else:
                    changed_title = False
            else:
                changed_title = False
                # A delegate may not have an email address: the database
                # refuses one, and several delegates are eleven.
                email = entry.get("email") if person_type == "adult" else None
                person_id = tx.insert("people.create", (
                    school_id, person_type, adult_type, adult_type_other,
                    first, middle, last, None, None,
                    None, None, None, None,
                    email, None, None,
                    None, None,
                    # Both replaced by issue_code below, in this same transaction. VOL is
                    # a valid placeholder; the real prefix depends on the scopes
                    # the roles grant, which are not attached yet.
                    f"pending-{school_id}-{first}-{last}-{now}",
                    "VOL", 1, now, now, now, None, school_id))
                tx.run("people.set_board_title", (title, now, person_id))
                action = "created"

            changed = _set_roles(tx, person_id, roles, now,
                                 keep=_identity_role(person_type, adult_type))

            code = None
            if not existing or new_codes:
                prefix = auth.code_prefix_for(person_type, adult_type)
                if existing:
                    tx.run("auth.session_revoke_all_for_person", (now, person_id))
                code = auth.issue_code(tx, person_id, prefix)

            summary = (f"{'Added' if action == 'created' else 'Updated'} "
                       f"{first} {last} ({title}) at {school_name}"
                       + (f", roles {' '.join(changed)}" if changed else "")
                       + ".")
            tx.audit("person.create" if action == "created" else "person.update",
                     summary, school_id=school_id,
                     entity_type="person", entity_id=person_id)

            # INVARIANT 2: the counters move with the data, in the same
            # transaction. This was missing, and the effect was quiet and
            # expensive: adding ten people to a chapter left `school_stats`
            # holding the old numbers, so the invoice charged for adults it
            # then did not include in the amount owed. Nothing failed; the
            # arithmetic just stopped agreeing with itself.
            #
            # See backend/lib/db.py. Every path that writes to `people` owes
            # this call.
            stats.recompute(tx, school_id,
                            settings=settings_lib.fee_settings(tx))

        results.append({
            "name": f"{first} {last}", "title": title, "school": school_name,
            "action": action, "roles": roles, "role_changes": changed,
            "code": code, "person_id": person_id,
        })

    return {"people": results}


def retire_prefix(db, old_prefix: str = "ADM") -> dict:
    """Give everyone still holding an `old_prefix` code a correct one.

    A prefix is part of the string that gets hashed, so it cannot be rewritten
    in place: the stored HMAC was computed over `ADM...`, and changing the
    column alone would leave a person whose code no longer matches their row --
    which fails at sign-in with no explanation.

    So each of them gets a genuinely new code, their sessions are revoked, and
    the new code comes back ONCE. Whoever runs this has to hand out new sheets.
    There is no cheaper version of this, which is the argument for having
    retired the prefix before any codes went out rather than after.
    """
    from backend.lib import auth, clock

    issued = []
    with db.tx() as tx:
        people = [dict(r) for r in tx.all("people.with_prefix", (old_prefix,))]

    for person in people:
        with db.tx() as tx:
            now = clock.now_iso()
            prefix = auth.code_prefix_for(person["person_type"],
                                          person["adult_type"])
            tx.run("auth.session_revoke_all_for_person", (now, person["id"]))
            code = auth.issue_code(tx, person["id"], prefix)
            name = f"{person['first_name']} {person['last_name']}"
            tx.audit(
                "person.code_regenerate",
                f"{name}'s access code was reissued as {prefix} when the "
                f"{old_prefix} prefix was retired. The previous code and every "
                f"device signed in with it stopped working.",
                school_id=person["school_id"],
                entity_type="person", entity_id=person["id"],
                changed_fields=["code_hmac", "code_prefix"])

        issued.append({
            "name": name, "title": person["adult_type"] or person["person_type"],
            "school": person["school_name"], "action": "reissued",
            "roles": [], "role_changes": [], "code": code,
            "person_id": person["id"],
        })

    return {"people": issued}


def export(db) -> list[dict]:
    """Rebuild `board.json` from the database.

    The file is gitignored, so it lives in exactly one place: whichever laptop
    made it. The NAMES are not lost with it -- they are in the database -- but
    the file is, and the file is the only way in to provisioning. This turns a
    lost laptop from a problem into an inconvenience.

    Codes are not exported and cannot be: only their HMAC is stored. Anyone who
    needs one gets a new one.
    """
    with db.read() as tx:
        people = [dict(r) for r in tx.all("admin.board_members")]

    out = []
    for person in people:
        roles = [k for k in (person["role_keys"] or "").split(",") if k]
        # `delegate` and `chapter_leader` are NOT written back: they follow
        # from what somebody is, and a file listing them would make them look
        # like something a person chose.
        #
        # `sponsor` IS written back, and the distinction matters. In this file
        # it is a declaration -- "make this person their chapter's sponsor" --
        # and `adult_type` is derived from it. Dropping it produced a file that
        # re-imported the sponsors as ordinary adults.
        roles = [r for r in roles if r not in ("delegate", "chapter_leader")]

        # A chapter's sponsor is not, by itself, somebody this file provisions.
        # Every chapter has one and they arrive with the roster; board.json is
        # for people who hold authority BEYOND their own chapter -- which is
        # what makes a sponsor who also sits on the board belong in it.
        if not (set(roles) & CONVENTION_ROLES):
            continue

        entry = {
            "first": person["first_name"],
            "last": person["last_name"],
            "title": (person.get("board_title")
                      or person["adult_type_other"]
                      or ("Sponsor" if person["adult_type"] == "sponsor"
                          else "Board member")),
            "roles": roles,
        }
        # Written only when it is not the default, so a file exported and read
        # back is the shape somebody would have typed.
        if person.get("adult_type") is not None:
            entry["type"] = "adult"
        if person["middle_name"]:
            entry["middle"] = person["middle_name"]
        if person["school_name"] != BOARD_SCHOOL:
            entry["school"] = person["school_name"]
        out.append(entry)
    return out


def report(result: dict) -> str:
    """One line per person, code first. The same shape as demo-codes.txt.

    EVERYBODY IS LISTED, including the people whose code did not change. A
    report that showed only new codes looked like the run had missed somebody
    — the usual case is adding one person to a board of twelve, which printed
    one line and said nothing about the other eleven.
    """
    lines = []
    for row in sorted(result["people"], key=lambda r: r["name"]):
        code = row["code"] or "(unchanged)"
        lines.append(f"{code:16} — {row['title']}: {row['name']}")
    return "\n".join(lines)


def summarise(result: dict) -> str:
    """What actually happened, printed under the list."""
    people = result["people"]
    issued = sum(1 for r in people if r["code"])
    made = sum(1 for r in people if r["action"] == "created")
    changed = sum(1 for r in people if r["role_changes"])

    parts = [f"{len(people)} listed"]
    if made:
        parts.append(f"{made} added")
    if changed:
        parts.append(f"{changed} with roles changed")
    parts.append(f"{issued} new code(s)" if issued else "no new codes")
    if 0 < issued < len(people):
        parts.append("the rest keep the codes they already have")
    return ", ".join(parts) + "."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="a local .db file; omit to use Turso")
    parser.add_argument("--file", default=str(DEFAULT_FILE))
    parser.add_argument("--export", action="store_true",
                        help="write board.json FROM the database instead of "
                             "reading it, for when the file has been lost")
    parser.add_argument("--create-schools", action="store_true",
                        help="create any chapter named in the file that does "
                             "not exist yet")
    parser.add_argument("--new-codes", action="store_true",
                        help="reissue codes for people who already exist, "
                             "signing out every device using the old ones")
    args = parser.parse_args()

    if args.export:
        from backend.lib.db import connect

        db = connect(args.db) if args.db else connect()
        try:
            people = export(db)
        finally:
            db.close()

        target = pathlib.Path(args.file)
        if target.exists():
            print(f"{target.name} already exists. Move it aside first -- this "
                  f"would overwrite it.", file=sys.stderr)
            return 1
        target.write_text(json.dumps(people, indent=2, ensure_ascii=False) + '\n',
                          encoding="utf-8")
        print(f"wrote {len(people)} person/people to {target.name}")
        for entry in people:
            print(f"  {entry['first']} {entry['last']} - {entry['title']} "
                  f"- {', '.join(entry['roles'])}")
        return 0

    try:
        people = load(pathlib.Path(args.file))
    except BoardError as error:
        print(error, file=sys.stderr)
        return 1

    from backend.lib.db import connect

    db = connect(args.db) if args.db else connect()
    try:
        print(report(run(db, people, new_codes=args.new_codes,
                         create_schools=args.create_schools)))
    except BoardError as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
