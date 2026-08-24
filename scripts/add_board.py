"""Give real people accounts, without putting their names in the repository.

    modal run backend/app.py::board                 # against the live database
    python scripts/add_board.py --db dev.db         # against a local file

WHY THE NAMES ARE NOT IN THIS FILE
    This repository is public, and the demonstration is projected in a room.
    Everything in scripts/seed.py is invented for exactly that reason. Real
    board members are real people, so their names live in `board.json` in the
    project folder, which is listed in .gitignore and never committed.

    `board.example.json` shows the shape. Copy it, fill it in, and keep it.

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


class BoardError(Exception):
    pass


def load(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        raise BoardError(
            f"no {path.name} found.\n"
            f"Copy board.example.json to {path.name} and fill it in. It is "
            f"gitignored, so the names never reach the repository.")
    people = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(people, list):
        raise BoardError(f"{path.name} should hold a list of people.")

    for index, person in enumerate(people, start=1):
        for required in ("first", "last", "title", "roles"):
            if not person.get(required):
                raise BoardError(
                    f"entry {index} in {path.name} has no {required!r}.")
        if not isinstance(person["roles"], list):
            raise BoardError(f"entry {index}: 'roles' should be a list.")
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
        name, entry.get("level", "HS"), "chapter", entry.get("city", ""),
        0, 0, None, None, now, now))
    tx.run("schools.stats_init", (school_id, now))
    return school_id


def _find(tx, school_id: int, first: str, last: str) -> dict | None:
    for row in tx.all("admin.people_search", (school_id,)):
        if (row["first_name"].strip().lower() == first.strip().lower()
                and row["last_name"].strip().lower() == last.strip().lower()):
            return dict(row)
    return None


def _set_roles(tx, person_id: int, wanted: list[str], now: str) -> list[str]:
    """Bring a person's roles into line with the file. Returns what changed."""
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
    from backend.lib import auth, clock

    results = []

    for entry in people:
        first = entry["first"].strip()
        middle = (entry.get("middle") or "").strip() or None
        last = entry["last"].strip()
        title = entry["title"].strip()
        roles = list(entry["roles"])
        school_name = (entry.get("school") or "").strip() or BOARD_SCHOOL

        with db.tx() as tx:
            now = clock.now_iso()
            school_id = _school_id(tx, school_name, entry,
                                   create=create_schools)
            existing = _find(tx, school_id, first, last)

            # A sponsor is filed as a sponsor; everyone else is 'other' with
            # their actual title beside it, which is what the roster and the
            # printed sheet show.
            is_sponsor = "sponsor" in roles
            adult_type = "sponsor" if is_sponsor else "other"
            adult_type_other = None if is_sponsor else title

            if existing:
                person_id = existing["id"]
                action = "already there"
            else:
                person_id = tx.insert("people.create", (
                    school_id, "adult", adult_type, adult_type_other,
                    first, middle, last, None, None,
                    None, None, None, None,
                    entry.get("email"), None, None,
                    None, None,
                    # Both replaced by issue_code below, in this same transaction. VOL is
                    # a valid placeholder; the real prefix depends on the scopes
                    # the roles grant, which are not attached yet.
                    f"pending-{school_id}-{first}-{last}-{now}",
                    "VOL", 1, now, now, now, None))
                action = "created"

            changed = _set_roles(tx, person_id, roles, now)

            code = None
            if not existing or new_codes:
                scopes = {r["scope"]
                          for r in tx.all("auth.scopes_for_person", (person_id,))}
                prefix = auth.code_prefix_for("adult", adult_type, scopes)
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

        results.append({
            "name": f"{first} {last}", "title": title, "school": school_name,
            "action": action, "roles": roles, "role_changes": changed,
            "code": code, "person_id": person_id,
        })

    return {"people": results}


def report(result: dict) -> str:
    lines = []
    for row in result["people"]:
        lines.append(f"{row['name']} - {row['title']} - {row['school']}")
        lines.append(f"    {row['action']}"
                     + (f", roles {' '.join(row['role_changes'])}"
                        if row["role_changes"] else ""))
        if row["code"]:
            lines.append(f"    CODE  {row['code']}")
        else:
            lines.append("    code unchanged (use --new-codes to reissue)")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="a local .db file; omit to use Turso")
    parser.add_argument("--file", default=str(DEFAULT_FILE))
    parser.add_argument("--create-schools", action="store_true",
                        help="create any chapter named in the file that does "
                             "not exist yet")
    parser.add_argument("--new-codes", action="store_true",
                        help="reissue codes for people who already exist, "
                             "signing out every device using the old ones")
    args = parser.parse_args()

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
