"""The Student Activity Sheet and the Adult Registration Sheet.

Both are submitted once rather than saved on every keystroke, and stay editable
by their owner until the deadline.

THE DEADLINE
    `deadline.forms_lock` is a UTC instant meaning "end of day in California".
    An admin can unlock one person past it -- `people.forms_unlocked` -- for a
    legitimate exception, without moving the deadline for everyone.

WHOLE-FORM REPLACE
    Editing replaces ALL selections for that person inside one transaction:
    delete, then insert. Do not diff. Diffing is where the bugs live and there
    are never more than a few dozen rows.
"""

from __future__ import annotations

from . import catalog, clock, settings, stats
from .auth import ForbiddenError, Principal
from .db import Tx


class FormLocked(ForbiddenError):
    """Past the deadline, and this person has no individual exception."""


def is_locked(tx: Tx, person: dict) -> bool:
    if person.get("forms_unlocked"):
        return False
    return clock.is_past(settings.get_datetime(tx, "deadline.forms_lock"))


def assert_open(tx: Tx, person: dict) -> None:
    if is_locked(tx, person):
        deadline = settings.get_datetime(tx, "deadline.forms_lock")
        raise FormLocked(
            f"Forms closed on {clock.render_local(deadline, with_time=False)}. "
            f"Ask your sponsor if you need a change made."
        )


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def activity_sheet(tx: Tx, person: dict) -> dict:
    """Everything the delegate's form needs, in ONE round trip.

    The catalog comes from the per-container cache, and the person's existing
    selections are two indexed queries -- not one per item.
    """
    submission = tx.one("forms.get_submission", (person["id"], "student_activity"))
    selections = tx.all("forms.selections_for_person", (person["id"],))
    options = tx.all("forms.selection_options_for_person", (person["id"],))

    chosen_options: dict[int, list[int]] = {}
    for row in options:
        chosen_options.setdefault(row["item_id"], []).append(row["option_id"])

    return {
        "person": {
            "id": person["id"],
            "first_name": person["first_name"],
            "last_name": person["last_name"],
            "grade": person["grade"],
            "latin_level": person["latin_level"],
            "meal": person["meal"],
        },
        "school_level": person["school_level"],
        "status": submission["status"] if submission else "draft",
        "submitted_at": submission["submitted_at"] if submission else None,
        "locked": is_locked(tx, person),
        # Sent so the form can say when it closes. A delegate who does not know
        # the date has no reason to finish today.
        "deadline": settings.get(tx, "deadline.forms_lock"),
        "selected": [r["item_id"] for r in selections],
        "selected_options": chosen_options,
        "catalog": catalog.for_person(
            tx, person_type="delegate", school_level=person["school_level"],
            latin_level=person["latin_level"]),
        # A delegate's chapter's team entries, shown read-only so they know
        # whether their chapter is fielding a kickball team without being able
        # to sign the chapter up for one.
        "chapter_entries": [
            dict(r) for r in tx.all("forms.chapter_entries_for_school",
                                    (person["school_id"],))
        ],
    }


def adult_sheet(tx: Tx, person: dict) -> dict:
    roles = tx.all("forms.adult_roles_for_person", (person["id"],))
    submission = tx.one("forms.get_submission", (person["id"], "adult_registration"))
    return {
        "person": {
            "id": person["id"],
            "first_name": person["first_name"],
            "last_name": person["last_name"],
            "adult_type": person["adult_type"],
            "email": person["email"],
            "cell_phone": person["cell_phone"],
            "meal": person["meal"],
            "latin_knowledge": person["latin_knowledge"],
            "availability_note": person["availability_note"],
        },
        "status": submission["status"] if submission else "draft",
        "submitted_at": submission["submitted_at"] if submission else None,
        "locked": is_locked(tx, person),
        "deadline": settings.get(tx, "deadline.forms_lock"),
        "selected": [r["item_id"] for r in roles],
        "catalog": catalog.for_person(
            tx, person_type="adult", school_level=person["school_level"],
            latin_knowledge=person["latin_knowledge"]),
    }


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def save_activity_sheet(tx: Tx, actor: Principal, person: dict, payload: dict) -> dict:
    """Replace the delegate's whole activity sheet in one transaction.

    Returns any non-blocking warnings. Raises catalog.ValidationError with a
    list of messages for anything that blocks -- the test count above all.
    """
    assert_open(tx, person)

    grade = payload.get("grade")
    latin_level = payload.get("latin_level")
    meal = payload.get("meal")
    _check_delegate_basics(person["school_level"], grade, latin_level, meal)

    item_ids = [int(i) for i in payload.get("selected", [])]
    options = {int(k): [int(v) for v in vs]
               for k, vs in (payload.get("selected_options") or {}).items()}

    # Validate against the level being SUBMITTED, not the one on file: a
    # delegate who corrects their Latin level in the same save must be judged
    # by the corrected one.
    warnings = catalog.validate_selections(
        tx, item_ids, person_type="delegate",
        school_level=person["school_level"], latin_level=latin_level)
    for item_id, option_ids in options.items():
        catalog.validate_options(tx, item_id, option_ids)

    now = clock.now_iso()
    tx.run("people.update_self_delegate", (grade, latin_level, meal, now, person["id"]))

    tx.run("forms.clear_selections", (person["id"],))
    for item_id in item_ids:
        selection_id = tx.insert("forms.add_selection", (person["id"], item_id, now))
        for option_id in options.get(item_id, []):
            tx.run("forms.add_selection_option", (selection_id, option_id))

    existing = tx.one("forms.get_submission", (person["id"], "student_activity"))
    first_time = existing is None or existing["status"] != "submitted"
    tx.run("forms.upsert_submission",
           (person["id"], "student_activity", "submitted", now, now))

    name = f"{person['first_name']} {person['last_name']}".strip()
    tx.audit(
        "form.submit" if first_time else "form.update",
        f"{name} {'submitted' if first_time else 'updated'} their Student "
        f"Activity Sheet ({len(item_ids)} entr{'y' if len(item_ids) == 1 else 'ies'}).",
        actor_person_id=actor.person_id,
        impersonator_person_id=actor.impersonator_person_id,
        school_id=person["school_id"],
        entity_type="form", entity_id=person["id"],
        # Field NAMES only. The log says Bob updated his forms, never what Bob
        # chose -- these are minors and the log is read by many people.
        changed_fields=["grade", "latin_level", "meal", "selections"],
    )
    stats.recompute(tx, person["school_id"], settings=settings.fee_settings(tx))
    return {"warnings": warnings}


def save_adult_sheet(tx: Tx, actor: Principal, person: dict, payload: dict) -> dict:
    """Replace the adult's registration sheet.

    "Please sign up for at least two roles" is a WARNING, not a block. An adult
    who ignores it can still submit -- some of them genuinely can only do one
    thing, and refusing the form teaches them the site is broken.
    """
    assert_open(tx, person)

    latin_knowledge = payload.get("latin_knowledge") or "none"
    if latin_knowledge not in catalog.LATIN_RANK:
        raise catalog.ValidationError(["Choose your level of Latin knowledge."])

    adult_type = payload.get("adult_type") or person["adult_type"] or "chaperone"
    item_ids = [int(i) for i in payload.get("selected", [])]

    warnings = catalog.validate_selections(
        tx, item_ids, person_type="adult", school_level=person["school_level"],
        latin_knowledge=latin_knowledge)

    now = clock.now_iso()
    tx.run("people.update_self_adult", (
        payload.get("meal"), payload.get("cell_phone"), payload.get("email"),
        latin_knowledge, payload.get("availability_note"),
        adult_type, payload.get("adult_type_other"), now, person["id"]))

    tx.run("forms.clear_adult_roles", (person["id"],))
    for item_id in item_ids:
        tx.run("forms.add_adult_role", (person["id"], item_id, now))

    existing = tx.one("forms.get_submission", (person["id"], "adult_registration"))
    first_time = existing is None or existing["status"] != "submitted"
    tx.run("forms.upsert_submission",
           (person["id"], "adult_registration", "submitted", now, now))

    name = f"{person['first_name']} {person['last_name']}".strip()
    tx.audit(
        "form.submit" if first_time else "form.update",
        f"{name} {'submitted' if first_time else 'updated'} their Adult "
        f"Registration Sheet ({len(item_ids)} role"
        f"{'' if len(item_ids) == 1 else 's'}).",
        actor_person_id=actor.person_id,
        impersonator_person_id=actor.impersonator_person_id,
        school_id=person["school_id"],
        entity_type="form", entity_id=person["id"],
        changed_fields=["meal", "cell_phone", "email", "latin_knowledge",
                        "availability_note", "roles"],
    )
    stats.recompute(tx, person["school_id"], settings=settings.fee_settings(tx))
    return {"warnings": warnings}


def _check_delegate_basics(school_level: str, grade, latin_level, meal) -> None:
    """A middle school chapter's delegates see only grades 6-8 and MS levels.

    Checked server-side as well as in the form, because the form is a courtesy
    and this is the authority.
    """
    errors = []
    allowed_grades = range(6, 9) if school_level == "MS" else range(9, 13)
    if grade is not None and int(grade) not in allowed_grades:
        low, high = allowed_grades[0], allowed_grades[-1]
        errors.append(f"Choose a grade between {low} and {high}.")

    if latin_level:
        prefix = "MS" if school_level == "MS" else "HS"
        if not latin_level.startswith(prefix):
            errors.append(
                f"Choose a {'middle' if prefix == 'MS' else 'high'} school Latin level.")

    if meal and meal not in ("regular", "vegetarian", "gluten_free"):
        errors.append("Choose a meal preference.")

    if errors:
        raise catalog.ValidationError(errors)
