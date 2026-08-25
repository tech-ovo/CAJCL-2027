"""Authentication, authorization, sessions, and impersonation.

AUTHENTICATION is proving who you are: one code, redeemed for a session token.
AUTHORIZATION is what you may then do, and IT IS WHERE THE REAL WORK IS.

    This repository is public, so every endpoint is documented to anyone
    curious. The realistic threat is not a database dump -- it is a sponsor at
    one school reading another school's roster because an endpoint checked
    identity but not scope. Every endpoint declares its required scope and its
    school-scoping rule, and the test suite hits every endpoint with a
    wrong-role and a wrong-school credential.

SCOPES REACH A PERSON ONLY THROUGH ROLES
    person_roles -> roles -> role_scopes. There is no other path, there is no
    person_scopes table, and a scope is never attached to a person directly,
    anywhere, for any reason.

    Four scopes are ADMINISTRATIVE and global: `registration`, `academics`,
    `awards`, and `*` which subsumes everything. Three are IDENTITY scopes
    carried by ordinary accounts and ALWAYS school-limited: `sponsor`,
    `delegate`, and `chapter`.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass, field, replace

from . import clock, codes
from .db import Tx

SESSION_DAYS = 180
IMPERSONATION_MINUTES = 30

# 10 failures per IP per 15 minutes, 5 per code per hour.
IP_LIMIT, IP_WINDOW_MINUTES = 10, 15
CODE_LIMIT, CODE_WINDOW_MINUTES = 5, 60

ADMIN_SCOPES = frozenset({"*", "registration", "academics", "awards"})
IDENTITY_SCOPES = frozenset({"sponsor", "delegate", "chapter"})


class AuthError(Exception):
    """Wrong or missing credential. Always surfaces as 401."""


class ForbiddenError(Exception):
    """Valid credential, insufficient authority. Always surfaces as 403."""


class RateLimited(Exception):
    """Too many failed attempts. Surfaces as 429."""


class ReadOnlySession(ForbiddenError):
    """An impersonation session tried to write without the write toggle."""


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

def _pepper() -> bytes:
    """The code pepper, from Modal Secrets.

    Never in the database and never in the repository -- that is the whole
    point of peppering rather than plain hashing. The development fallback is
    deliberately obvious in the value itself, so a misconfigured production
    container is discoverable rather than silently insecure.
    """
    raw = os.environ.get("CODE_PEPPER")
    if not raw:
        if os.environ.get("CAJCL_ENV") == "production":
            raise RuntimeError(
                "CODE_PEPPER is not set. Every access code in the database was "
                "hashed with it; without it nobody can log in. See docs/RUNBOOK.md."
            )
        raw = "development-pepper-not-for-production"
    return raw.encode("utf-8")


def hash_ip(ip: str | None) -> str:
    """IPs are hashed, never stored raw. Most subjects here are minors."""
    return hashlib.sha256(f"ip:{ip or ''}".encode("utf-8")).hexdigest()


def hash_token(token: str) -> str:
    """Session tokens are 32 random bytes; SHA-256 with no pepper is plenty.

    There is nothing to brute-force at 256 bits of entropy, and unlike the code
    lookup this is not guarding a 45-bit secret.
    """
    return hashlib.sha256(token.encode("ascii")).hexdigest()


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

@dataclass
class Principal:
    """Who is making this request, and what they may do."""

    person_id: int
    school_id: int
    person_type: str
    first_name: str
    last_name: str
    school_name: str
    school_level: str
    school_kind: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    roles: tuple[str, ...] = ()
    session_id: int | None = None
    impersonator_person_id: int | None = None
    impersonator_name: str | None = None
    impersonation_can_write: bool = False
    # Set when `last_seen_at` has gone stale. The caller writes it, in its own
    # transaction, AFTER authentication -- so the authenticated path itself
    # never takes the single write lock. See authenticate().
    needs_touch: bool = False
    row: dict = field(default_factory=dict)

    @property
    def is_impersonating(self) -> bool:
        return self.impersonator_person_id is not None

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def has_scope(self, scope: str) -> bool:
        """`*` subsumes every other scope. Nothing else implies anything."""
        return "*" in self.scopes or scope in self.scopes

    def has_any(self, *scopes: str) -> bool:
        return any(self.has_scope(s) for s in scopes)

    @property
    def is_admin(self) -> bool:
        return "*" in self.scopes

    def to_public_dict(self) -> dict:
        """What /auth/me returns. Never contains a code or a token."""
        return {
            "person_id": self.person_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "person_type": self.person_type,
            "school": {
                "id": self.school_id,
                "name": self.school_name,
                "level": self.school_level,
                "kind": self.school_kind,
            },
            "scopes": sorted(self.scopes),
            "roles": list(self.roles),
            "impersonation": {
                "active": self.is_impersonating,
                "by": self.impersonator_name,
                "can_write": self.impersonation_can_write,
            } if self.is_impersonating else None,
        }


# ---------------------------------------------------------------------------
# Authorization guards
# ---------------------------------------------------------------------------

def require_scope(principal: Principal, *scopes: str) -> None:
    """Assert the caller holds at least one of these scopes."""
    if not principal.has_any(*scopes):
        raise ForbiddenError(
            f"this action needs the {' or '.join(scopes)} scope"
        )


def require_school(principal: Principal, school_id: int) -> None:
    """Assert the caller may act on this school.

    THE SCHOOL-SCOPING RULE. Administrative scopes are global, so a registration
    chair may act on any school. Identity scopes are always school-limited, so a
    sponsor may act on their own school and nothing else.

    This is the check that stops one sponsor reading another school's roster,
    which is the realistic attack on this system. It is a function rather than
    an inline comparison so that every endpoint calls the same one and the tests
    have a single thing to verify.
    """
    if principal.scopes & ADMIN_SCOPES:
        return
    if principal.school_id != school_id:
        raise ForbiddenError("that belongs to a different school")


def require_writable(principal: Principal) -> None:
    """Impersonation sessions are read-only unless explicitly toggled."""
    if principal.is_impersonating and not principal.impersonation_can_write:
        raise ReadOnlySession(
            "this is a read-only impersonation session. Turn on editing in the "
            "banner if you really need to make a change as this person."
        )


def require_person_in_scope(tx: Tx, principal: Principal, person_id: int) -> dict:
    """Load a person, asserting the caller may act on them. Returns the row.

    Two checks, not one: the person must exist, AND they must belong to a school
    the caller may act on. Endpoints that take a person_id from the URL all go
    through this, so none of them can forget the second half.
    """
    row = tx.one("people.school_of", (person_id,))
    if row is None:
        raise ForbiddenError("no such person")
    require_school(principal, row["school_id"])
    return row


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def _check_rate_limits(tx: Tx, attempted_hmac: str, ip_hash: str) -> None:
    ip_failures = tx.value(
        "auth.attempts_by_ip",
        (ip_hash, clock.plus_minutes(-IP_WINDOW_MINUTES)),
        default=0,
    )
    if ip_failures >= IP_LIMIT:
        raise RateLimited(
            "Too many sign-in attempts from this network. Wait 15 minutes and "
            "try again, or ask your sponsor for help."
        )

    code_failures = tx.value(
        "auth.attempts_by_code",
        (attempted_hmac, clock.plus_minutes(-CODE_WINDOW_MINUTES)),
        default=0,
    )
    if code_failures >= CODE_LIMIT:
        raise RateLimited(
            "That code has been entered incorrectly too many times. Wait an "
            "hour, or ask your sponsor to give you a new code."
        )


# ---------------------------------------------------------------------------
# Redeeming a code
# ---------------------------------------------------------------------------

def redeem(
    db,
    raw_code: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    via_magic_link: bool = False,
) -> tuple[str, Principal]:
    """Exchange a code for a session token. Returns (raw_token, principal).

    Takes the Database rather than a Tx, because a FAILED attempt has to be
    recorded in its own committed transaction.

    That is not a stylistic choice. A failure raises, the raising rolls the
    transaction back, and a rolled-back `login_attempts` row means the rate
    limiter counts zero failures forever -- the limiter silently does nothing
    while looking entirely correct. Recording the failure separately, before
    raising, is the only shape that works.

    The raw token is returned to the caller ONCE and never stored server-side --
    only its SHA-256 hash is. The raw code is never stored on the device at all.
    """
    pepper = _pepper()
    ip_hash = hash_ip(ip)
    attempted = codes.attempted_hmac(raw_code, pepper)

    with db.read() as tx:
        _check_rate_limits(tx, attempted, ip_hash)

    def fail(message: str) -> None:
        """Commit the failure, then raise. Order matters -- see above."""
        with db.tx() as failure_tx:
            failure_tx.run("auth.attempt_record",
                           (attempted, None, ip_hash, 0, clock.now_iso()))
            failure_tx.audit(
                "auth.login_failed",
                "Someone entered a code that did not match any account.",
                ip_hash=ip_hash,
            )
        raise AuthError(message)

    # The browser validates the check symbol before sending, so a well-formed
    # code reaching here and failing is a real miss, not a typo.
    if not codes.is_well_formed(raw_code):
        fail("Check that code again - it does not look quite right.")

    normalized = codes.normalize(raw_code)

    with db.read() as tx:
        person = tx.one("auth.person_by_code_hmac",
                        (codes.code_hmac(normalized, pepper),))

    if person is None:
        fail("That code was not recognised. Check it with your sponsor.")
    if person["status"] == "cancelled":
        fail("That registration was cancelled. Ask your sponsor.")
    if person["school_status"] == "withdrawn":
        fail("That chapter is no longer registered. Ask your sponsor.")

    token = secrets.token_urlsafe(32)
    with db.tx() as tx:
        session_id = tx.insert("auth.session_create", (
            person["id"], hash_token(token), None, 0,
            clock.now_iso(), clock.now_iso(), clock.plus_days(SESSION_DAYS),
            (user_agent or "")[:200], ip_hash,
        ))
        tx.run("auth.attempt_record",
               (attempted, person["code_prefix"], ip_hash, 1, clock.now_iso()))

        principal = _principal_from_person(tx, person, session_id=session_id)
        tx.audit(
            "auth.magic_link" if via_magic_link else "auth.login",
            f"{principal.display_name} signed in"
            + (" by scanning their printed code." if via_magic_link else "."),
            actor_person_id=person["id"],
            actor_role_snapshot=",".join(principal.roles),
            school_id=person["school_id"],
            entity_type="session", entity_id=session_id,
            ip_hash=ip_hash,
        )
    return token, principal


def _principal_from_person(tx: Tx, person: dict, *, session_id: int | None = None,
                           impersonator: dict | None = None,
                           can_write: bool = False) -> Principal:
    scopes = frozenset(r["scope"] for r in tx.all("auth.scopes_for_person", (person["id"],)))
    roles = tuple(r["key"] for r in tx.all("auth.roles_for_person", (person["id"],)))
    return Principal(
        person_id=person["id"],
        school_id=person["school_id"],
        person_type=person["person_type"],
        first_name=person["first_name"],
        last_name=person["last_name"],
        school_name=person["school_name"],
        school_level=person["school_level"],
        school_kind=person["school_kind"],
        scopes=scopes,
        roles=roles,
        session_id=session_id,
        impersonator_person_id=impersonator["id"] if impersonator else None,
        impersonator_name=(
            f"{impersonator['first_name']} {impersonator['last_name']}"
            if impersonator else None
        ),
        impersonation_can_write=can_write,
        row=dict(person),
    )


# ---------------------------------------------------------------------------
# Using a session
# ---------------------------------------------------------------------------

def authenticate(tx: Tx, token: str | None, *, touch: bool = True) -> Principal:
    """Resolve a session token to a Principal. Raises AuthError if it will not.

    READ ONLY. If the session's `last_seen_at` has gone stale, the returned
    Principal carries `needs_touch`, and the caller writes it separately -- see
    `_authenticate` in api.py. Authentication must not take the write lock,
    because it happens on every single request.
    """
    if not token:
        raise AuthError("Sign in to see this page.")

    session = tx.one("auth.session_by_token", (hash_token(token),))
    if session is None:
        raise AuthError("Sign in again - that session is no longer valid.")

    if session["revoked_at"]:
        # The common cause is a sponsor regenerating this person's code, so the
        # message says so rather than leaving them guessing.
        raise AuthError(
            "You were signed out. If your sponsor gave you a new code, use that one."
        )
    if clock.is_past(session["expires_at"]):
        raise AuthError("That session has expired. Sign in again.")

    # WHETHER the session needs touching is decided HERE, in Python, from a row
    # already read. The caller does the write, in its own transaction, only if
    # the answer is yes.
    #
    # This used to run the UPDATE unconditionally, inside a WRITE transaction
    # opened for every authenticated request. Narrowing the statement with a
    # `last_seen_at <` clause stopped it changing a row -- but an UPDATE that
    # matches nothing still takes the write lock, and libSQL has one writer. So
    # every request queued behind every other request for a column nobody reads
    # in real time, and two clicks in quick succession returned SQLITE_BUSY to
    # somebody standing at a check-in desk.
    #
    # Now the common path is a pure read and takes no lock at all.
    stale = (touch and (
        not session["last_seen_at"]
        or session["last_seen_at"] < clock.plus_minutes(-SESSION_TOUCH_MINUTES)))

    impersonator = None
    if session["impersonator_person_id"]:
        impersonator = {
            "id": session["impersonator_person_id"],
            "first_name": session["impersonator_first_name"],
            "last_name": session["impersonator_last_name"],
        }

    principal = _principal_from_person(
        tx,
        {
            "id": session["person_id"],
            "school_id": session["school_id"],
            "person_type": session["person_type"],
            "adult_type": session["adult_type"],
            "first_name": session["first_name"],
            "last_name": session["last_name"],
            "middle_name": session["middle_name"],
            "suffix": session["suffix"],
            "status": session["status"],
            "school_name": session["school_name"],
            "school_level": session["school_level"],
            "school_kind": session["school_kind"],
            "billing_exempt": session["billing_exempt"],
            "forms_unlocked": session["forms_unlocked"],
            "latin_level": session["latin_level"],
            "grade": session["grade"],
            "latin_knowledge": session["latin_knowledge"],
            "meal": session["meal"],
            "email": session["email"],
            "cell_phone": session["cell_phone"],
        },
        session_id=session["session_id"],
        impersonator=impersonator,
        can_write=bool(session["impersonation_can_write"]),
    )
    return replace(principal, needs_touch=stale)


def touch_session(tx: Tx, session_id: int) -> None:
    """Record that this session was used. Its own transaction, on purpose.

    Called AFTER authentication and only when the timestamp has actually gone
    stale, so the request that just authenticated did not have to hold the
    single write lock to get there.
    """
    tx.run("auth.session_touch",
           (clock.now_iso(), session_id,
            clock.plus_minutes(-SESSION_TOUCH_MINUTES)))
    tx.mark_silent("session.touch")


def logout(tx: Tx, principal: Principal) -> None:
    """Revoke the current session SERVER-SIDE, not just in localStorage.

    Assume shared devices: a school Chromebook will hold sessions for a dozen
    delegates over a weekend, and clearing localStorage on one of them does
    nothing about the token someone already copied.
    """
    tx.run("auth.session_revoke", (clock.now_iso(), principal.session_id))
    tx.audit(
        "auth.logout", f"{principal.display_name} signed out.",
        actor_person_id=principal.person_id,
        impersonator_person_id=principal.impersonator_person_id,
        school_id=principal.school_id,
        entity_type="session", entity_id=principal.session_id,
    )


def revoke_session(tx: Tx, principal: Principal, session_id: int) -> None:
    """Revoke one of your OWN sessions from the account page."""
    owner = tx.one("auth.session_owned_by", (session_id,))
    if owner is None or owner["person_id"] != principal.person_id:
        raise ForbiddenError("that is not your session")
    tx.run("auth.session_revoke", (clock.now_iso(), session_id))
    tx.audit(
        "session.revoke",
        f"{principal.display_name} signed out one of their other devices.",
        actor_person_id=principal.person_id,
        school_id=principal.school_id,
        entity_type="session", entity_id=session_id,
    )


# ---------------------------------------------------------------------------
# Impersonation
# ---------------------------------------------------------------------------

def start_impersonation(
    tx: Tx, admin: Principal, target_person_id: int, admin_code: str,
    *, ip: str | None = None, user_agent: str | None = None,
) -> tuple[str, Principal]:
    """Open a read-only view of exactly what another person sees.

    This exists because it is the only practical way to debug a confused
    sponsor. It requires `*`, a STEP-UP re-entry of the admin's own code, and
    produces a distinct session that expires in 30 minutes, is read-only unless
    explicitly toggled, shows a permanent banner naming both identities, and
    never reveals the target's code.
    """
    require_scope(admin, "*")
    if admin.is_impersonating:
        raise ForbiddenError("you are already impersonating someone")

    # Step-up. Proves the person at the keyboard is the admin, not someone who
    # walked up to an unlocked laptop -- which is the exact scenario that makes
    # an impersonation feature dangerous.
    pepper = _pepper()
    if not codes.is_well_formed(admin_code):
        raise AuthError("Re-enter your own code to confirm.")
    check = tx.one("auth.person_by_code_hmac",
                   (codes.code_hmac(codes.normalize(admin_code), pepper),))
    if check is None or check["id"] != admin.person_id:
        raise AuthError("That is not your code.")

    target = tx.one("people.get", (target_person_id,))
    if target is None:
        raise ForbiddenError("no such person")

    token = secrets.token_urlsafe(32)
    session_id = tx.insert("auth.session_create", (
        target["id"], hash_token(token), admin.person_id, 0,
        clock.now_iso(), clock.now_iso(),
        clock.plus_minutes(IMPERSONATION_MINUTES),
        (user_agent or "")[:200], hash_ip(ip),
    ))

    principal = _principal_from_person(
        tx, target, session_id=session_id,
        impersonator={"id": admin.person_id,
                      "first_name": admin.first_name,
                      "last_name": admin.last_name},
        can_write=False,
    )
    tx.audit(
        "impersonation.start",
        f"{admin.display_name} started viewing the site as "
        f"{principal.display_name} ({principal.school_name}).",
        actor_person_id=target["id"],
        impersonator_person_id=admin.person_id,
        school_id=target["school_id"],
        entity_type="person", entity_id=target["id"],
    )
    return token, principal


def end_impersonation(tx: Tx, principal: Principal) -> None:
    if not principal.is_impersonating:
        raise ForbiddenError("this is not an impersonation session")
    tx.run("auth.session_revoke", (clock.now_iso(), principal.session_id))
    tx.audit(
        "impersonation.end",
        f"{principal.impersonator_name} stopped viewing the site as "
        f"{principal.display_name}.",
        actor_person_id=principal.person_id,
        impersonator_person_id=principal.impersonator_person_id,
        school_id=principal.school_id,
        entity_type="person", entity_id=principal.person_id,
    )


# ---------------------------------------------------------------------------
# Issuing codes
# ---------------------------------------------------------------------------

def issue_code(tx: Tx, person_id: int, prefix: str) -> str:
    """Mint a new code for a person. Returns the display form ONCE.

    The caller must revoke that person's sessions in the same transaction when
    this is a regeneration -- otherwise the old QR keeps working, which defeats
    the entire point of regenerating.
    """
    pepper = _pepper()
    for _ in range(5):
        display, normalized = codes.generate(prefix)
        digest = codes.code_hmac(normalized, pepper)
        try:
            tx.run("people.set_code",
                   (digest, prefix, 1, clock.now_iso(), clock.now_iso(), person_id))
            return display
        except Exception as exc:  # pragma: no cover - a 45-bit collision
            if "UNIQUE" not in str(exc).upper():
                raise
    raise RuntimeError("could not mint a unique code after five attempts")


# How stale a session's last_seen_at may get before a request bothers to update
# it. Anything above zero turns "a write on every request" into "a write every
# few minutes per device", which is the difference between contending for the
# single write lock constantly and almost never.
SESSION_TOUCH_MINUTES = 5


def code_prefix_for(person_type: str, adult_type: str | None) -> str:
    """Which prefix a person's code carries.

    The prefix is display and disambiguation only -- it is NOT a namespace, and
    codes are globally unique across prefixes. It exists so that a sponsor
    holding a stack of printed sheets can tell at a glance which is which.

    IT DESCRIBES WHAT SOMEONE IS, NOT WHAT THEY CAN DO.
        There used to be an `ADM` prefix, returned whenever a person held scope
        `*`. It was wrong twice over.

        It conflated two unrelated things. Two sponsors doing exactly the same
        job for their two chapters got different prefixes because one of them
        also sat on the board, which made a stack of printed sheets harder to
        sort rather than easier.

        And it implied a second account. Powers are granted by ROLE, on the one
        account a person already has -- the same way a delegate becomes a
        chapter leader without being issued a second code. A prefix that
        changes when a role is granted contradicts that, and the contradiction
        is not cosmetic: the prefix is part of the string that gets hashed, so
        "promote this person" would have silently invalidated their code.

    `ADM` is gone from codes.VALID_PREFIXES entirely, so an old one no longer
    signs anybody in. `modal run backend/app.py::retire_adm_codes` reissues for
    everyone who held one.
    """
    if person_type == "delegate":
        return "DEL"
    if adult_type == "sponsor":
        return "SPO"
    return "VOL"
