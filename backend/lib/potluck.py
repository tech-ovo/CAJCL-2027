"""The activities potluck: activities that need helpers, and who offered.

The endpoints in api.py do the authorization; this module holds the rules, so
the tests can reach them without HTTP:

    what an activity may be                 check_activity
    an activity as the pages receive it     view
    the section on an attendee's sheet      sheet_view
    saving an attendee's picks              save_picks
    a sponsor's decision on one pick        decide
    writing the activity onto the schedule  sync_schedule
    erasing a person                        forget_person

WHO DECIDES.
    An ADULT's pick is approved at once: they speak for themselves.
    A DELEGATE's pick is `pending` until their sponsor approves or declines it.
    A pick entered FOR a delegate by their sponsor (or a chair), through the
    same sheet, is approved at once -- the person entering it is the sponsor.

THE CAP COUNTS PENDING AND APPROVED. A full activity stops taking picks, so a
sponsor is never asked to approve a place that is not there. A declined pick
frees its place; reversing a decline is refused if the activity has filled
since.

THE SHEET IS SAVED WHOLE, THE SIGNUPS ARE NOT REPLACED WHOLE. The sponsor's
decision lives in the signup row, so `save_picks` keeps the rows a person
keeps and touches only what changed. A declined pick stays on the sheet, shown
as declined, until the person picks it again (which makes it pending again).

OVERLAPS ARE WARNINGS. Two picks that run at the same time come back as
warnings for the sheet to show; they never block a save.

THE SCHEDULE FOLLOWS. An activity with a time is written onto the master
schedule by `sync_schedule`, in the same transaction as every change to it, as
a row marked source = 'potluck'. That is the activity itself, not its helpers:
no name of a person ever reaches the public schedule.
"""

from __future__ import annotations

import datetime as _dt

from . import clock, schedule
from .catalog import ValidationError

MAX_NAME = 80
MAX_DESCRIPTION = 1000
MAX_LOCATION = 120
MAX_CAPACITY = 500


def _clean(value) -> str:
    return " ".join(str(value or "").split())


# ---------------------------------------------------------------------------
# What an activity may be
# ---------------------------------------------------------------------------

def check_activity(payload: dict, current: dict | None = None) -> dict:
    """The columns for a new or edited activity. A field left out of an edit
    keeps its current value. The time is optional: an activity the chair has
    not scheduled yet has none, and is not on the master schedule."""
    current = current or {}
    errors: list[str] = []

    def given(key):
        return key in payload or key not in current

    name = _clean(payload.get("name", current.get("name")))
    if not name:
        errors.append("Give the activity a name, like “Face painting”.")
    elif len(name) > MAX_NAME:
        errors.append(f"Keep the name under {MAX_NAME} characters.")

    description = (str(payload.get("description") or "").strip()
                   if given("description") else current.get("description") or "")
    if len(description) > MAX_DESCRIPTION:
        errors.append(f"Keep the description under {MAX_DESCRIPTION} characters.")

    location = (_clean(payload.get("location"))
                if given("location") else current.get("location") or "")
    if len(location) > MAX_LOCATION:
        errors.append(f"Keep the location under {MAX_LOCATION} characters.")

    capacity = current.get("capacity")
    if "capacity" in payload:
        raw = payload.get("capacity")
        if raw in (None, ""):
            capacity = None
        else:
            try:
                capacity = int(raw)
                if isinstance(raw, bool) or str(raw).strip() != str(capacity):
                    raise ValueError
            except (ValueError, TypeError):
                capacity = None
                errors.append("Give the number of helpers as a whole number, "
                              "or leave it empty for no limit.")
            else:
                if not 1 <= capacity <= MAX_CAPACITY:
                    errors.append(f"Helpers wanted must be between 1 and {MAX_CAPACITY}.")

    is_open = (bool(payload.get("open")) if "open" in payload
               else bool(current.get("open", True)))

    sort_order = current.get("sort_order", 0)
    if "sort_order" in payload:
        try:
            sort_order = int(payload["sort_order"])
        except (ValueError, TypeError):
            errors.append("The order has to be a number.")

    starts_at = ends_at = None
    try:
        starts_at, ends_at = schedule.parse_span(payload, current, require_start=False)
    except ValidationError as error:
        errors.extend(error.errors)

    if errors:
        raise ValidationError(errors)
    return {"name": name, "description": description or None,
            "location": location or None, "starts_at": starts_at,
            "ends_at": ends_at, "capacity": capacity,
            "open": 1 if is_open else 0, "sort_order": sort_order}


def view(row, *, status: str | None = None) -> dict:
    """An activity as the pages receive it. `status` is the viewer's own pick
    (pending, approved, declined) or None."""
    capacity = row["capacity"]
    taken = row["taken"] if "taken" in row.keys() else 0
    return {
        "id": row["id"], "name": row["name"],
        "description": row["description"], "location": row["location"],
        **schedule.when(row["starts_at"], row["ends_at"]),
        "capacity": capacity, "taken": taken,
        "spots_left": None if capacity is None else max(capacity - taken, 0),
        "open": bool(row["open"]), "status": status,
    }


# ---------------------------------------------------------------------------
# The section on an attendee's sheet
# ---------------------------------------------------------------------------

def sheet_view(tx, person: dict) -> dict:
    """The list on a sheet: every open activity, plus any closed one the person
    already picked (so they can see it), each with their own status.

    `selected` is what they are signed up for -- pending or approved. A
    declined pick is listed with status 'declined' and is not in `selected`.
    """
    mine = {r["activity_id"]: r["status"]
            for r in tx.all("potluck.signups_for_person", (person["id"],))}
    activities = [view(r, status=mine.get(r["id"]))
                  for r in tx.all("potluck.activities")
                  if r["open"] or r["id"] in mine]
    return {
        "activities": activities,
        "selected": [a["id"] for a in activities
                     if a["status"] in ("pending", "approved")],
        # Said on the sheet so nobody wonders why a pick of theirs is still
        # waiting. True for delegates only.
        "needs_approval": person["person_type"] == "delegate",
    }


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

def _span(row) -> tuple[_dt.datetime, _dt.datetime] | None:
    if not row["starts_at"]:
        return None
    start = clock.parse_iso(row["starts_at"])
    end = clock.parse_iso(row["ends_at"]) if row["ends_at"] else None
    # An activity with no end is a moment; give it a minute so two that start
    # together are seen to overlap.
    return start, end or start + _dt.timedelta(minutes=1)


def overlap_warnings(activities: list) -> list[str]:
    """One sentence for each pair of these that run at the same time.
    Back-to-back is not overlapping."""
    spans = [(a, _span(a)) for a in activities]
    spans = [(a, s) for a, s in spans if s]
    warnings = []
    for i, (first, (s1, e1)) in enumerate(spans):
        for second, (s2, e2) in spans[i + 1:]:
            if s1 < e2 and s2 < e1:
                warnings.append(f"“{first['name']}” and “{second['name']}” "
                                f"are at the same time.")
    return warnings


def save_picks(tx, actor, person: dict, activity_ids, now: str) -> list[str]:
    """Make this person's potluck picks what they ticked. Returns warnings.

    Raises ValidationError for a pick that cannot be made: an activity that
    does not exist, has stopped taking picks, or is full.
    """
    wanted = {int(i) for i in activity_ids}
    activities = {r["id"]: r for r in tx.all("potluck.activities")}
    current = {r["activity_id"]: r
               for r in tx.all("potluck.signups_for_person", (person["id"],))}

    errors = []
    for activity_id in sorted(wanted):
        if activity_id not in activities:
            raise ValidationError(["One of the activities you chose does not "
                                   "exist any more. Reload the page."])

    # Approved at once when the person is an adult, or somebody else (their
    # sponsor, a chair) is the one saving.
    decided_here = (person["person_type"] == "adult"
                    or actor.person_id != person["id"])
    status = "approved" if decided_here else "pending"
    decided_at = now if decided_here else None
    decided_by = actor.person_id if decided_here else None

    to_add = [a for a in sorted(wanted)
              if a not in current or current[a]["status"] == "declined"]
    for activity_id in to_add:
        activity = activities[activity_id]
        if not activity["open"]:
            errors.append(f"“{activity['name']}” is not taking more helpers.")
        elif activity["capacity"] is not None and \
                tx.one("potluck.taken", (activity_id, person["id"]))["n"] >= activity["capacity"]:
            errors.append(f"“{activity['name']}” already has all the helpers "
                          f"it needs.")
    if errors:
        raise ValidationError(errors)

    for activity_id in to_add:
        if activity_id in current:
            tx.run("potluck.signup_set", (status, now, decided_at, decided_by,
                                          person["id"], activity_id))
        else:
            tx.run("potluck.signup_add", (person["id"], activity_id, status, now,
                                          decided_at, decided_by))
    for activity_id, row in current.items():
        # A declined pick the person leaves alone stays, so they can see it.
        if activity_id not in wanted and row["status"] != "declined":
            tx.run("potluck.signup_delete", (person["id"], activity_id))

    changed = bool(to_add) or any(a not in wanted and r["status"] != "declined"
                                  for a, r in current.items())
    if changed:
        name = f"{person['first_name']} {person['last_name']}".strip()
        count = len(wanted)
        tx.audit(
            "potluck.update",
            f"{name}'s activities potluck picks were saved by "
            f"{actor.display_name} ({count} chosen).",
            actor_person_id=actor.person_id,
            impersonator_person_id=actor.impersonator_person_id,
            school_id=person["school_id"],
            entity_type="person", entity_id=person["id"],
            changed_fields=["potluck"])

    return overlap_warnings([activities[a] for a in sorted(wanted)])


def decide(tx, actor, person: dict, activity_id: int, *, approve: bool,
           now: str) -> None:
    """A sponsor (or a chair) approves or declines one pick. Quietly does
    nothing if it is already so."""
    row = tx.one("potluck.signup_get", (person["id"], activity_id))
    activity = tx.one("potluck.activity_get", (activity_id,))
    if row is None or activity is None:
        raise ValidationError(["That pick is not there any more. It may have "
                               "just been withdrawn; reload the page."])
    wanted = "approved" if approve else "declined"
    if row["status"] == wanted:
        return
    if approve and row["status"] == "declined" and activity["capacity"] is not None:
        taken = tx.one("potluck.taken", (activity_id, person["id"]))["n"]
        if taken >= activity["capacity"]:
            raise ValidationError([f"“{activity['name']}” has filled since you "
                                   f"declined this. Decline someone else first."])
    tx.run("potluck.signup_set", (wanted, row["requested_at"], now,
                                  actor.person_id, person["id"], activity_id))
    name = f"{person['first_name']} {person['last_name']}".strip()
    tx.audit(
        "potluck.approve" if approve else "potluck.decline",
        f"{actor.display_name} {'approved' if approve else 'declined'} "
        f"{name}'s offer to help with {activity['name']}.",
        actor_person_id=actor.person_id,
        impersonator_person_id=actor.impersonator_person_id,
        school_id=person["school_id"],
        entity_type="person", entity_id=person["id"],
        changed_fields=["potluck"])


def forget_person(tx, person_id: int) -> None:
    """Redaction: their picks go."""
    tx.run("potluck.signups_delete_for_person", (person_id,))


# ---------------------------------------------------------------------------
# The master schedule
# ---------------------------------------------------------------------------

def sync_schedule(tx, activity_id: int, now: str) -> None:
    """Make the master schedule's row for this activity match it: add it when
    it gains a time, change it when it moves, remove it when it loses the time
    or is deleted. Idempotent, and quiet when nothing changed."""
    activity = tx.one("potluck.activity_get", (activity_id,))
    existing = tx.one("schedule.for_potluck", (activity_id,))

    if activity is None or not activity["starts_at"]:
        if existing is not None:
            tx.run("schedule.delete_for_potluck", (activity_id,))
        return

    wanted = (activity["name"], activity["description"], activity["location"],
              activity["starts_at"], activity["ends_at"])
    if existing is None:
        tx.run("schedule.sync_insert_potluck",
               (*wanted, f"potluck:{activity_id}", activity_id, now, now))
    elif (existing["title"], existing["description"], existing["location"],
          existing["starts_at"], existing["ends_at"]) != wanted:
        tx.run("schedule.sync_update_potluck", (*wanted, now, existing["id"]))
