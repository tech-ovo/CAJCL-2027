"""The master convention schedule: what a schedule entry may be.

The endpoints in api.py do the authorization; this module holds the rules, so
the tests can reach them without HTTP:

    what an entry may say                  check_item
    a date and times -> UTC instants       parse_span
    an entry as the pages receive it       view

TIMES TRAVEL AS A CALIFORNIA DATE AND A CLOCK TIME. An editor sends
{"date": "2027-03-12", "start": "09:30", "end": "10:15"}, and `parse_span`
turns that into the UTC instants that are stored (lib/clock.py has the rule
and the reason). Every entry goes back out as the same three pieces, so no
page ever does time-zone arithmetic.
"""

from __future__ import annotations

import re

from . import clock
from .catalog import ValidationError

MAX_TITLE = 120
MAX_DESCRIPTION = 1000
MAX_LOCATION = 120

_CLOCK = re.compile(r"^\d{1,2}:\d{2}$")


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def _instant(date, time, what: str, errors: list) -> str | None:
    """One California date and time as a UTC instant, or None with a message."""
    try:
        if not _CLOCK.match(str(time).strip()):
            raise ValueError
        hour, minute = (int(part) for part in str(time).strip().split(":"))
        if hour > 23 or minute > 59:
            raise ValueError
        return clock.local_to_utc(str(date), str(time))
    except (ValueError, TypeError):
        errors.append(f"Give the {what} as a real date and a time like 9:30.")
        return None


def parse_span(payload: dict, current: dict | None = None, *,
               require_start: bool = True) -> tuple[str | None, str | None]:
    """(starts_at, ends_at) as UTC instants, from the payload's `date`,
    `start`, `end` and optional `end_date`. Anything left out keeps its
    current value, so an edit can change one field.

    With `require_start` False (a heat the Director has not timed yet) an
    entirely empty start is allowed and gives (None, None).
    """
    current = current or {}
    cur_date, cur_start = clock.local_parts(current.get("starts_at"))
    cur_end_date, cur_end = clock.local_parts(current.get("ends_at"))

    date = payload.get("date", cur_date)
    start = payload.get("start", cur_start)
    end = payload.get("end", cur_end)
    end_date = payload.get("end_date", cur_end_date if cur_end else None) or date

    errors: list[str] = []
    if not _clean(start) and not _clean(date):
        if require_start:
            raise ValidationError(["Give the date and the time it starts."])
        return None, None
    if not _clean(date) or not _clean(start):
        raise ValidationError(["Give both the date and the time it starts."])

    starts_at = _instant(date, start, "start time", errors)
    ends_at = None
    if _clean(end):
        ends_at = _instant(end_date, end, "end time", errors)
    if errors:
        raise ValidationError(errors)
    if ends_at is not None and ends_at <= starts_at:
        raise ValidationError(["It has to end after it starts."])
    return starts_at, ends_at


def check_item(payload: dict, current: dict | None = None) -> dict:
    """The columns for a new or edited entry. A field left out of an edit
    keeps its current value."""
    current = current or {}
    errors: list[str] = []

    def given(key):
        return key in payload or key not in current

    title = _clean(payload.get("title", current.get("title")))
    if not title:
        errors.append("Give the entry a title, like “Opening ceremony”.")
    elif len(title) > MAX_TITLE:
        errors.append(f"Keep the title under {MAX_TITLE} characters.")

    description = (str(payload.get("description") or "").strip()
                   if given("description") else current.get("description") or "")
    if len(description) > MAX_DESCRIPTION:
        errors.append(f"Keep the description under {MAX_DESCRIPTION} characters.")

    location = (_clean(payload.get("location"))
                if given("location") else current.get("location") or "")
    if len(location) > MAX_LOCATION:
        errors.append(f"Keep the location under {MAX_LOCATION} characters.")

    published = (bool(payload.get("published", True)) if given("published")
                 else bool(current.get("published")))

    starts_at = ends_at = None
    try:
        starts_at, ends_at = parse_span(payload, current)
    except ValidationError as error:
        errors.extend(error.errors)

    if errors:
        raise ValidationError(errors)
    return {"title": title, "description": description or None,
            "location": location or None, "starts_at": starts_at,
            "ends_at": ends_at, "published": 1 if published else 0}


def when(starts_at: str | None, ends_at: str | None) -> dict:
    """The California pieces of a span, for a page to show as they are."""
    date, start = clock.local_parts(starts_at)
    end_date, end = clock.local_parts(ends_at)
    return {"date": date, "start": start, "end": end,
            "end_date": end_date if end_date != date else None}


def view(row, *, admin: bool = False) -> dict:
    """An entry as the pages receive it. The public view carries nothing the
    Logistics chair would not print on the wall."""
    body = {"id": row["id"], "title": row["title"],
            "description": row["description"], "location": row["location"],
            **when(row["starts_at"], row["ends_at"]),
            "source": row["source"],
            "olympika_event_id": row["olympika_event_id"]}
    if admin:
        body["published"] = bool(row["published"])
        body["editable"] = row["source"] == "manual"
    return body
