"""Joining a chapter with its join code.

THE PROBLEM THIS SOLVES
    A sponsor does not know which of their Latin students are coming until the
    paper packets are in hand. When registration was on paper they printed
    packets that belonged to nobody in particular and interested students took
    one. Pasting a roster up front made them collect every name twice.

    So a chapter has a JOIN CODE. A student types it, gives their name, grade
    and Latin level, and is handed an ordinary access code -- the same kind a
    sponsor-pasted roster produces, hashed the same way, used to sign in the
    same way. The only difference is that the student is PENDING until their
    sponsor approves them.

PENDING IS NOT BLOCKED
    A pending student signs in and fills in their activity sheet straight away;
    nobody has to wait for an approval before starting. What pending changes is
    what they COUNT toward: not the invoice, not the public count, not the
    caterer's meal totals (see stats.sql). Approval moves them into all of it.
    Denial removes them -- roster.deny -- and leaves only an anonymous row.

THE JOIN CODE IS NOT A SECRET IN THE WAY AN ACCESS CODE IS
    It is printed on every packet and shown on the sponsor's screen, so it is
    stored as-is rather than hashed. The most it can do is create one more
    PENDING delegate in one chapter. What bounds that:

      * a sponsor can close joining, or replace the code, at any moment;
      * a chapter holds at most MAX_PENDING waiting students, so a leaked code
        cannot bury the approval list;
      * wrong codes are rate limited per network, counted apart from sign-in
        failures so a classroom fumbling one printed sheet cannot lock anybody
        out of signing in.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from . import auth, catalog, clock, codes, forms, roster, settings, stats
from .db import Tx

CODE_LENGTH = 8

# Students waiting for approval in one chapter. A sponsor with forty students
# and a packet for twenty is nowhere near this; a script holding a leaked code
# is stopped by it.
MAX_PENDING = 150

# Wrong join codes per network per window. Far more generous than the sign-in
# limit (10): thirty students typing from one school address is ordinary, and
# one of them being a typo is the common case rather than an attack.
JOIN_IP_LIMIT, JOIN_IP_WINDOW_MINUTES = 30, 15

NAME_MAX = 60
LATIN_LEVELS = ("MS-1", "MS-2", "MS-3", "HS-1", "HS-2", "HS-3", "HS-Adv")


# ---------------------------------------------------------------------------
# The code itself
# ---------------------------------------------------------------------------

def generate() -> str:
    """Eight characters from the access-code alphabet. Stored without a dash."""
    return "".join(secrets.choice(codes.ALPHABET) for _ in range(CODE_LENGTH))


def normalize(raw: str) -> str:
    """What a student typed -> what is stored. Raises ValueError if it cannot be.

    Forgiving in the same ways the access code is: case, dashes, spaces, and
    the letters that look like digits.
    """
    stripped = "".join(str(raw or "").split()).replace("-", "").replace("–", "").upper()
    stripped = "".join(codes.CONFUSABLES.get(ch, ch) for ch in stripped)
    if len(stripped) != CODE_LENGTH or any(ch not in codes.ALPHABET for ch in stripped):
        raise ValueError("a join code is eight letters and numbers")
    return stripped


def display(code: str | None) -> str | None:
    """ABCD-EFGH, for the screen and the page."""
    if not code:
        return None
    return f"{code[:4]}-{code[4:]}"


def _assign(tx: Tx, school_id: int) -> str:
    """Give a chapter a fresh code, retrying the one-in-a-trillion collision."""
    for _ in range(5):
        code = generate()
        try:
            tx.run("schools.set_join_code", (code, clock.now_iso(), school_id))
            return code
        except Exception as exc:  # pragma: no cover - a 39-bit collision
            if "UNIQUE" not in str(exc).upper():
                raise
    raise RuntimeError("could not mint a unique join code after five attempts")


def ensure_code(tx: Tx, school: dict) -> str:
    """The chapter's code, minting one if it has none. For writers only."""
    if school.get("join_code"):
        return school["join_code"]
    return _assign(tx, school["id"])


def regenerate(tx: Tx, school: dict, actor: auth.Principal) -> str:
    """Replace the code. The old one stops working at once; students who
    already joined with it are untouched."""
    code = _assign(tx, school["id"])
    tx.audit(
        "school.join_code",
        f"{actor.display_name} replaced the join code for {school['name']}.",
        actor_person_id=actor.person_id,
        impersonator_person_id=actor.impersonator_person_id,
        school_id=school["id"], entity_type="school", entity_id=school["id"],
        changed_fields=["join_code"],
    )
    return code


def set_open(tx: Tx, school: dict, actor: auth.Principal, is_open: bool) -> None:
    """Close or reopen joining. The code is kept; it simply stops admitting."""
    tx.run("schools.set_join_open",
           (1 if is_open else 0, clock.now_iso(), school["id"]))
    tx.audit(
        "school.join_open",
        f"{actor.display_name} {'reopened' if is_open else 'closed'} joining "
        f"for {school['name']}.",
        actor_person_id=actor.person_id,
        impersonator_person_id=actor.impersonator_person_id,
        school_id=school["id"], entity_type="school", entity_id=school["id"],
        changed_fields=["join_open"],
    )


# ---------------------------------------------------------------------------
# Joining
# ---------------------------------------------------------------------------

@dataclass
class Joined:
    token: str
    principal: auth.Principal
    code: str                 # the access code, readable ONCE
    school: dict


def _clean_name(value, label: str) -> str:
    name = " ".join(str(value or "").split())
    if not name:
        raise catalog.ValidationError([f"Enter your {label}."])
    if len(name) > NAME_MAX:
        raise catalog.ValidationError([f"That {label} is too long."])
    # Someone typing in lower case gets a capital letter; anyone who typed
    # capitals deliberately (McDonald, de la Cruz) is left exactly as they wrote.
    if name == name.lower():
        name = " ".join(word[:1].upper() + word[1:] for word in name.split(" "))
    return name


def _clean_basics(school: dict, payload: dict) -> tuple[str, str, int, str]:
    first = _clean_name(payload.get("first_name"), "first name")
    last = _clean_name(payload.get("last_name"), "last name")

    problems = []
    try:
        grade = int(payload.get("grade"))
    except (TypeError, ValueError):
        grade = None
        problems.append("Choose your grade.")
    level = payload.get("latin_level")
    if level not in LATIN_LEVELS:
        problems.append("Choose your Latin level.")
    if problems:
        raise catalog.ValidationError(problems)

    # Grade and level against the chapter's own level. The form is a courtesy
    # and this is the authority.
    forms._check_delegate_basics(school["level"], grade, level, None)
    return first, last, grade, level


def join(db, raw_code: str, payload: dict, *, ip: str | None = None,
         user_agent: str | None = None) -> Joined:
    """Create a PENDING delegate in the chapter this code belongs to, and sign
    them in.

    Takes the Database rather than a Tx for the same reason auth.redeem does: a
    wrong code must be recorded in its own committed transaction, or the rate
    limiter counts nothing and does nothing.
    """
    pepper = auth._pepper()
    ip_hash = auth.hash_ip(ip)

    with db.read() as tx:
        failures = tx.value(
            "auth.join_failures_by_ip",
            (ip_hash, clock.plus_minutes(-JOIN_IP_WINDOW_MINUTES)), default=0)
    if failures >= JOIN_IP_LIMIT:
        raise auth.RateLimited(
            "Too many wrong join codes from this network. Wait 15 minutes and "
            "try again, or ask your sponsor to check the code.")

    def miss(message: str) -> None:
        # Hashed like a sign-in attempt, with a leading 'j' (a hex digest never
        # has one) so the two limiters cannot see each other's failures.
        try:
            subject = normalize(raw_code)
        except ValueError:
            subject = "MALFORMED:" + "".join(str(raw_code).split()).upper()[:64]
        digest = "j" + hmac.new(pepper, subject.encode("utf-8", "replace"),
                                hashlib.sha256).hexdigest()
        with db.tx() as failure_tx:
            failure_tx.run("auth.attempt_record",
                           (digest, None, ip_hash, 0, clock.now_iso()))
            failure_tx.audit(
                "auth.join_failed",
                "Someone entered a join code that did not match any chapter.",
                ip_hash=ip_hash)
        raise catalog.ValidationError([message])

    try:
        code = normalize(raw_code)
    except ValueError:
        miss("Check that join code again. It is eight letters and numbers.")

    with db.read() as tx:
        found = tx.one("schools.by_join_code", (code,))
    if found is None:
        miss("That join code was not recognised. Check it with your sponsor.")

    with db.tx() as tx:
        # Re-read inside the writer. A sponsor closing joining or replacing the
        # code while this student was typing takes effect, not "mostly".
        school = tx.one("schools.get", (found["id"],))
        if (school is None or school["join_code"] != code
                or school["status"] != "active" or school["kind"] != "chapter"):
            raise catalog.ValidationError([
                "That join code is no longer valid. Ask your sponsor for the "
                "current one."])
        if not school["join_open"]:
            raise catalog.ValidationError([
                "Joining is closed for this chapter. Ask your sponsor to "
                "reopen it."])
        school = dict(school)

        first, last, grade, level = _clean_basics(school, payload)

        # THE SAME NAME TWICE IS ALMOST ALWAYS THE SAME PERSON joining again
        # after losing their access code -- and a second account for them is a
        # row the sponsor then has to find and deny. Stopped with the real
        # remedy instead. Two genuinely identical names are rare enough for the
        # sponsor to add one by hand.
        wanted = (first.casefold(), last.casefold())
        for row in tx.all("people.existing_names_for_dedupe", (school["id"],)):
            if ((row["first_name"] or "").casefold(),
                    (row["last_name"] or "").casefold()) == wanted:
                raise catalog.ValidationError([
                    "Someone with that name has already joined this chapter. "
                    "If that was you and you lost your access code, ask your "
                    "sponsor to issue you a new one."])

        waiting = tx.value("people.pending_count", (school["id"],), default=0)
        if waiting >= MAX_PENDING:
            raise catalog.ValidationError([
                "A lot of students are already waiting for approval in this "
                "chapter. Tell your sponsor, who can approve some and let you "
                "join afterwards."])

        now = clock.now_iso()
        created = roster._insert_person(tx, school, {
            "person_type": "delegate",
            "first_name": first, "last_name": last,
            "grade": grade, "latin_level": level,
            "raw": f"{first} {last}",
        }, now)
        tx.run("people.set_approval", ("pending", now, created["id"]))

        person = tx.one("auth.person_by_id", (created["id"],))
        token, session_id = auth.start_session(
            tx, created["id"], ip_hash=ip_hash, user_agent=user_agent)
        principal = auth._principal_from_person(tx, person, session_id=session_id)

        tx.audit(
            "person.join",
            f"{first} {last} joined {school['name']} with its join code "
            f"and is waiting for approval.",
            actor_person_id=created["id"],
            actor_role_snapshot=",".join(principal.roles),
            school_id=school["id"], entity_type="person",
            entity_id=created["id"], ip_hash=ip_hash,
        )
        stats.recompute(tx, school["id"], settings=settings.fee_settings(tx))

    return Joined(token=token, principal=principal, code=created["code"],
                  school=school)
