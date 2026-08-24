"""The sponsor's roster: preview, idempotent commit, and per-person edits.

THE ONE THING THAT MUST NOT HAPPEN
    A sponsor creating their roster twice. It is the single most damaging
    accident available to them, and it must be impossible -- not unlikely.

    Preview issues a signed idempotency key. Commit stores that key in
    roster_imports, where a UNIQUE constraint makes a second commit return the
    first one's result instead of importing again. A double-click, a flaky
    connection, and an impatient refresh all land on the same guarantee, and it
    is a database constraint rather than an application check because an
    application check loses to two concurrent requests.

PREVIEW WRITES NOTHING
    Not a roster_imports row, not an audit entry, nothing. The key is a signed
    token rather than a database row, so a sponsor who tweaks their paste five
    times leaves nothing behind and we store no copies of abandoned text.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets

from . import auth, clock, settings, stats
from .db import Tx
from .names import ParsedRow, parse_roster

# How long a preview stays committable. Long enough for a sponsor to read
# thirty rows carefully and fix a few; short enough that a key found in a
# browser history months later is inert.
PREVIEW_TTL_MINUTES = 120

# A paste larger than this is refused with a clear message rather than landing
# 5,000 rows in one transaction. Thirty is a normal chapter; the largest
# plausible chapter is well under a hundred.
MAX_PASTE_LINES = 500


class RosterError(Exception):
    """Something the sponsor can fix, phrased so they can fix it."""


def _signing_key() -> bytes:
    """Derived from the code pepper rather than being its own secret.

    One fewer thing in Modal Secrets, one fewer thing to rotate, and one fewer
    way for a future commissioner to deploy with half the secrets configured.
    Rotating the pepper invalidates outstanding preview keys, which is harmless:
    the sponsor previews again.
    """
    return hmac.new(auth._pepper(), b"roster-idempotency-v1", hashlib.sha256).digest()


def roster_fingerprint(existing: list[dict]) -> str:
    """What the chapter's roster looked like at a given moment.

    Ids and nothing else: a rename does not invalidate a preview, and does not
    need to. What matters is whether the SET of people changed while somebody
    was reviewing a paste, because that is the case where two sponsors each
    add the same twenty students and the chapter ends up with forty.
    """
    ids = sorted(int(person["id"]) for person in existing)
    joined = ",".join(str(i) for i in ids)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def issue_key(school_id: int, raw_text: str, roster_sha: str) -> str:
    """A signed idempotency key. No database row, no cleanup, no stored text."""
    payload = {
        "school_id": school_id,
        "text_sha": hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:32],
        # The roster this preview was reviewed against. See verify_key.
        # None is how a key made before this existed looks, and is accepted.
        "roster_sha": roster_sha,
        "issued_at": clock.now_iso(),
        "nonce": secrets.token_urlsafe(9),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).decode()
    signature = hmac.new(_signing_key(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{signature}"


def verify_key(key: str, school_id: int, raw_text: str,
               roster_sha: str | None = None) -> dict:
    """Check a key belongs to this school, this text, and is still fresh.

    Binding the key to a hash of the pasted text is what stops a sponsor from
    previewing one roster, editing the textarea, and committing the key against
    different names than the ones they reviewed.
    """
    try:
        body, signature = key.rsplit(".", 1)
        expected = hmac.new(_signing_key(), body.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body))
    except Exception:
        raise RosterError(
            "That preview is no longer valid. Paste your roster again and "
            "review it once more before confirming."
        ) from None

    if payload["school_id"] != school_id:
        raise RosterError("That preview belongs to a different chapter.")
    if payload["text_sha"] != hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:32]:
        raise RosterError(
            "The names changed since you previewed them. Review the list again "
            "before confirming."
        )
    age = (clock.now_utc() - clock.parse_iso(payload["issued_at"])).total_seconds()
    if age > PREVIEW_TTL_MINUTES * 60:
        raise RosterError("That preview has expired. Paste your roster again.")

    # THE ROSTER ITSELF CHANGED WHILE THIS PREVIEW WAS OPEN.
    #
    # A chapter can have two sponsors, and both may write. The key already
    # binds the pasted TEXT, so a sponsor cannot review one list and commit
    # another -- but it said nothing about the roster those names were checked
    # against. Two sponsors pasting the same twenty students at the same time
    # both previewed against an empty roster, both saw no duplicates, and both
    # committed. The chapter ended up with forty.
    #
    # Older keys carry no fingerprint. They are accepted rather than rejected:
    # a preview open across a deploy is a worse failure than the race this
    # closes, and the race needs two sponsors acting inside five minutes.
    if roster_sha is not None and payload.get("roster_sha") not in (None, roster_sha):
        raise RosterError(
            "Somebody else changed this chapter's roster while you were "
            "reviewing this list, so the duplicate check you saw is out of "
            "date. Paste it again and look at the warnings before confirming."
        )
    return payload


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def preview(tx: Tx, school: dict, raw_text: str,
            *, default_person_type: str = "delegate") -> dict:
    """Parse a paste into an editable preview. WRITES NOTHING.

    The existing roster is fetched ONCE and handed to the parser, so duplicate
    detection never issues a query per pasted line.
    """
    line_count = sum(1 for line in raw_text.splitlines() if line.strip())
    if line_count > MAX_PASTE_LINES:
        raise RosterError(
            f"That is {line_count:,} lines, and the most this accepts at once is "
            f"{MAX_PASTE_LINES:,}. Paste your roster in smaller batches."
        )

    existing = [dict(r) for r in tx.all("people.existing_names_for_dedupe", (school["id"],))]
    rows = parse_roster(
        raw_text,
        school_level=school["level"],
        existing=existing,
        default_person_type=default_person_type,
    )
    return {
        "rows": [r.to_dict() for r in rows],
        "idempotency_key": issue_key(school["id"], raw_text,
                                     roster_fingerprint(existing)),
        "parsed_count": len(rows),
        "warning_count": sum(1 for r in rows if r.warnings),
    }


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------

def commit(tx: Tx, school: dict, actor: auth.Principal, raw_text: str,
           key: str, rows: list[dict]) -> dict:
    """Create the roster. Idempotent on `key`.

    Everything here happens in ONE transaction: the import record, every person,
    every code, the audit entry, and both counter caches. A failure anywhere
    rolls back all of it, which is why a half-imported roster is not a state
    this system can reach.
    """
    # THE DOUBLE-CLICK GUARD RUNS FIRST, AND THE ORDER IS LOAD-BEARING.
    #
    # If this key has been seen, this roster already exists: return what the
    # first commit produced rather than a plausible approximation of it.
    #
    # It has to come before the staleness check below, because the first press
    # is itself what changes the roster. Checked the other way round, the second
    # press of a double-click is rejected as "somebody else changed this
    # roster" -- which is true, and is the same person, half a second ago.
    #
    # Skipping verification here is safe: a key only reaches this row by having
    # been verified when that row was written, and a forged key matches nothing.
    seen = tx.one("roster.import_by_key", (key,))
    if seen is not None:
        created = tx.all("roster.people_of_import", (seen["id"],))
        return {
            "created": [dict(r) for r in created],
            "committed_count": seen["committed_count"],
            "already_committed": True,
        }

    # Now the roster as it is NOW, against what the preview was reviewed
    # against.
    existing = [dict(r) for r in tx.all("people.existing_names_for_dedupe",
                                        (school["id"],))]
    verify_key(key, school["id"], raw_text, roster_fingerprint(existing))

    if not rows:
        raise RosterError("There is nobody in that list to add.")

    created_at = clock.now_iso()
    import_id = tx.insert("roster.import_create", (
        school["id"], actor.person_id, key, raw_text, len(rows), len(rows), created_at,
    ))

    created = []
    for row in rows:
        created.append(_insert_person(tx, school, row, created_at,
                                      import_id=import_id))

    delegates = sum(1 for r in rows if r.get("person_type") == "delegate")
    adults = len(rows) - delegates
    parts = []
    if delegates:
        parts.append(f"{delegates} delegate{'s' if delegates != 1 else ''}")
    if adults:
        parts.append(f"{adults} adult{'s' if adults != 1 else ''}")

    tx.audit(
        "roster.import",
        f"{actor.display_name} added {' and '.join(parts)} to {school['name']}.",
        actor_person_id=actor.person_id,
        impersonator_person_id=actor.impersonator_person_id,
        school_id=school["id"],
        entity_type="school", entity_id=school["id"],
    )
    stats.recompute(tx, school["id"], settings=settings.fee_settings(tx))

    return {"created": created, "committed_count": len(created), "already_committed": False}


def _insert_person(tx: Tx, school: dict, row: dict, created_at: str,
                   *, import_id: int | None = None) -> dict:
    """Insert one parsed row and mint their code.

    The database CHECK constraints are the real enforcement of the person-type
    split; this function simply avoids handing them anything they would reject,
    so a sponsor sees a clear message instead of a constraint violation.
    """
    person_type = row.get("person_type", "delegate")
    is_delegate = person_type == "delegate"
    adult_type = None if is_delegate else (row.get("adult_type") or "chaperone")

    if not (row.get("first_name") or row.get("last_name")):
        raise RosterError("One of those rows has no name at all.")

    person_id = tx.insert("people.create", (
        school["id"], person_type, adult_type, row.get("adult_type_other"),
        row.get("first_name") or "", row.get("middle_name") or None,
        row.get("last_name") or "", row.get("suffix") or None,
        row.get("raw"),
        row.get("grade") if is_delegate else None,
        row.get("latin_level") if is_delegate else None,
        row.get("meal"), row.get("cell_phone"),
        None if is_delegate else row.get("email"),
        None if is_delegate else row.get("latin_knowledge"),
        None if is_delegate else row.get("availability_note"),
        row.get("guardian_name") if is_delegate else None,
        row.get("guardian_phone") if is_delegate else None,
        f"pending-{secrets.token_hex(16)}",   # replaced by issue_code below
        "DEL" if is_delegate else "VOL", 1, created_at,
        created_at, created_at, import_id,
    ))

    role_key = "delegate" if is_delegate else "sponsor" if adult_type == "sponsor" else "delegate"
    role = tx.one("roles.by_key", (role_key,))
    tx.run("people.grant_role", (person_id, role["id"], None, created_at))

    prefix = auth.code_prefix_for(person_type, adult_type)
    auth.issue_code(tx, person_id, prefix)

    return {
        "id": person_id,
        "first_name": row.get("first_name") or "",
        "last_name": row.get("last_name") or "",
        "person_type": person_type,
    }


# ---------------------------------------------------------------------------
# Per-person operations
# ---------------------------------------------------------------------------

def cancel(tx: Tx, school: dict, actor: auth.Principal, person: dict) -> str:
    """Mark someone cancelled. Returns the status applied.

    THERE ARE NO REFUNDS. Which of the two cancelled states applies depends on
    whether the chapter has already paid:

      - nothing paid yet  -> 'cancelled', and the invoice falls by their fee.
      - anything paid     -> 'cancelled_paid'. They still count toward the
                             amount owed, so the balance keeps reading zero
                             instead of turning into a credit nobody will refund.

    Decided here, from the payment record, rather than asked of the sponsor --
    a sponsor should not have to know the billing policy to remove a student.
    """
    paid = tx.value("stats.paid_for_school", (school["id"],), default=0) or 0
    status = "cancelled_paid" if paid > 0 else "cancelled"

    now = clock.now_iso()
    tx.run("people.cancel", (status, now, now, person["id"]))
    # Their sessions die with their registration: they are not attending, and
    # the printed sheet in their bag is now a credential to nothing.
    tx.run("auth.session_revoke_all_for_person", (now, person["id"]))

    name = f"{person['first_name']} {person['last_name']}".strip()
    note = (" Their fee still counts, because the chapter has already paid."
            if status == "cancelled_paid" else "")
    tx.audit(
        "person.cancel",
        f"{actor.display_name} cancelled {name} at {school['name']}.{note}",
        actor_person_id=actor.person_id,
        impersonator_person_id=actor.impersonator_person_id,
        school_id=school["id"], entity_type="person", entity_id=person["id"],
        changed_fields=["status"],
    )
    stats.recompute(tx, school["id"], settings=settings.fee_settings(tx))
    return status


def restore(tx: Tx, school: dict, actor: auth.Principal, person: dict) -> None:
    """Undo a cancellation. Their old code and sessions stay revoked.

    Restoring puts them back on the roster; it does NOT resurrect the sessions
    that were killed when they were cancelled. If they still have their printed
    sheet the code on it works, because the code itself was never changed.
    """
    tx.run("people.restore", (clock.now_iso(), person["id"]))
    name = f"{person['first_name']} {person['last_name']}".strip()
    tx.audit(
        "person.restore",
        f"{actor.display_name} restored {name} to the roster at {school['name']}.",
        actor_person_id=actor.person_id,
        impersonator_person_id=actor.impersonator_person_id,
        school_id=school["id"], entity_type="person", entity_id=person["id"],
        changed_fields=["status"],
    )
    stats.recompute(tx, school["id"], settings=settings.fee_settings(tx))


def regenerate_code(tx: Tx, school: dict, actor: auth.Principal, person: dict) -> str:
    """Issue a new code and kill everything derived from the old one.

    Returns the new code ONCE. The caller must immediately offer a
    single-attendee reprint: without it the sponsor is holding a packet page
    whose QR no longer works, with no obvious way to produce a new one.
    """
    new_code = auth.issue_code(tx, person["id"], person["code_prefix"])
    tx.run("auth.session_revoke_all_for_person", (clock.now_iso(), person["id"]))

    name = f"{person['first_name']} {person['last_name']}".strip()
    tx.audit(
        "person.code_regenerate",
        f"{actor.display_name} issued a new access code for {name}. "
        f"The previous code and every device signed in with it stopped working.",
        actor_person_id=actor.person_id,
        impersonator_person_id=actor.impersonator_person_id,
        school_id=school["id"], entity_type="person", entity_id=person["id"],
        changed_fields=["code_hmac"],
    )
    return new_code


def mark_paper_form(tx: Tx, school: dict, actor: auth.Principal, person: dict,
                    form_type: str, received: bool) -> None:
    """Record the sponsor's attestation that a signed paper form arrived.

    Records the attestation ONLY. No medical information, no file, no Drive
    pointer. Chairs see this; only scope '*' sees the Drive folder link; nobody
    else touches minors' medical information.
    """
    expected = ("student_waiver", "student_medical") if person["person_type"] == "delegate" \
        else ("adult_medical",)
    if form_type not in expected:
        raise RosterError(f"{form_type} is not a form this person has to return.")

    tx.run("forms.mark_paper", (
        person["id"], form_type, 1 if received else 0,
        actor.person_id, clock.now_iso(),
    ))
    name = f"{person['first_name']} {person['last_name']}".strip()
    label = form_type.replace("_", " ")
    tx.audit(
        "paper_form.mark",
        f"{actor.display_name} marked {name}'s {label} as "
        f"{'received' if received else 'not received'}.",
        actor_person_id=actor.person_id,
        impersonator_person_id=actor.impersonator_person_id,
        school_id=school["id"], entity_type="person", entity_id=person["id"],
        changed_fields=[form_type],
    )
    stats.recompute(tx, school["id"], settings=settings.fee_settings(tx))
