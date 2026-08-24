"""Time. All of it, in one place.

THE RULE
    Store a UTC instant. Render in America/Los_Angeles. Never store local time,
    and never let a human hand-type a UTC string.

THE TRAP
    `deadline.forms_lock` and `deadline.payment` are stored as UTC but MEAN
    "end of day in California". February 13, 2027 falls in PST (UTC-8), so end
    of that day is 2027-02-14T07:59:59Z -- not 2027-02-13T23:59:59Z, which
    would lock every delegate out eight hours early, in the middle of the last
    afternoon anyone actually uses the site.

    A future commissioner WILL move a deadline. If they move it into a DST
    month the offset becomes -7, and a hand-typed string will be an hour wrong
    in whichever direction is most confusing. That is why the dashboard takes a
    wall-clock date and calls end_of_day_utc() rather than accepting a UTC
    string: the offset is computed, never typed.

Standard library only. zoneinfo ships with Python 3.9+, so this needs no
dependency and works unchanged in a Colab.
"""

from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo

try:
    CONVENTION_TZ = ZoneInfo("America/Los_Angeles")
except Exception as error:                        # ZoneInfoNotFoundError
    # `zoneinfo` reads the operating system's time-zone database. Windows has
    # none, so a fresh checkout there fails on THIS LINE, before anything has
    # run -- and the traceback is twenty frames of importlib that name neither
    # the cause nor the fix.
    raise RuntimeError(
        "The time-zone database is missing, so 'America/Los_Angeles' cannot "
        "be loaded.\n\n"
        "This is normal on Windows: Python reads the operating system's copy, "
        "and Windows does not ship one.\n\n"
        "Install it:\n"
        "    pip install -r backend/requirements.txt\n"
        "or, on its own:\n"
        "    pip install tzdata\n\n"
        "If that does not fix it, you are probably running a different Python "
        "from the one you installed into. Check that your prompt shows "
        "(.venv)."
    ) from error

UTC = _dt.timezone.utc

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def now_utc() -> _dt.datetime:
    return _dt.datetime.now(UTC)


def now_iso() -> str:
    """The timestamp string written into every `created_at` in this system."""
    return now_utc().strftime(ISO_FORMAT)


def to_iso(moment: _dt.datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("refusing to serialise a naive datetime; attach a timezone")
    return moment.astimezone(UTC).strftime(ISO_FORMAT)


def parse_iso(text: str) -> _dt.datetime:
    """Parse a stored timestamp. Accepts the trailing Z we always write."""
    cleaned = text.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    moment = _dt.datetime.fromisoformat(cleaned)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def end_of_day_utc(local_date: str | _dt.date) -> str:
    """The last second of a California day, as a UTC instant string.

    This is the ONLY way a deadline should ever be set. Give it '2027-02-13'
    and it returns '2027-02-14T07:59:59Z', having worked out the -8 offset
    itself. Give it a date in July and it works out -7 instead.
    """
    if isinstance(local_date, str):
        local_date = _dt.date.fromisoformat(local_date.strip())
    local = _dt.datetime.combine(
        local_date, _dt.time(23, 59, 59), tzinfo=CONVENTION_TZ
    )
    return to_iso(local)


def start_of_day_utc(local_date: str | _dt.date) -> str:
    if isinstance(local_date, str):
        local_date = _dt.date.fromisoformat(local_date.strip())
    local = _dt.datetime.combine(local_date, _dt.time(0, 0, 0), tzinfo=CONVENTION_TZ)
    return to_iso(local)


def local_date_of(utc_iso: str) -> str:
    """The California calendar date a stored instant falls on.

    The inverse of end_of_day_utc, so the dashboard can show a commissioner the
    date they typed rather than the UTC string we derived from it.
    """
    return parse_iso(utc_iso).astimezone(CONVENTION_TZ).date().isoformat()


def render_local(utc_iso: str, *, with_time: bool = True) -> str:
    """Human-readable California time, for screens and printed pages.

    Built by hand rather than with strftime because the obvious format strings
    for an unpadded day and hour -- %-d and %-I -- are a glibc extension. They
    work on Modal and raise ValueError on Windows, where both commissioners
    develop. A formatter that works in production and crashes on your laptop is
    worse than one that is slightly tedious to read.
    """
    local = parse_iso(utc_iso).astimezone(CONVENTION_TZ)
    date_part = f"{local.strftime('%B')} {local.day}, {local.year}"
    if not with_time:
        return date_part
    hour = local.hour % 12 or 12
    meridiem = "a.m." if local.hour < 12 else "p.m."
    return f"{date_part} at {hour}:{local.minute:02d} {meridiem}"


def is_past(utc_iso: str | None, *, at: _dt.datetime | None = None) -> bool:
    """True if the given instant has passed. An empty deadline never passes."""
    if not utc_iso or not utc_iso.strip():
        return False
    return (at or now_utc()) > parse_iso(utc_iso)


def plus_days(days: int, *, at: _dt.datetime | None = None) -> str:
    return to_iso((at or now_utc()) + _dt.timedelta(days=days))


def plus_minutes(minutes: int, *, at: _dt.datetime | None = None) -> str:
    return to_iso((at or now_utc()) + _dt.timedelta(minutes=minutes))


def plus_hours(hours: float, *, at: _dt.datetime | None = None) -> str:
    return to_iso((at or now_utc()) + _dt.timedelta(hours=hours))
