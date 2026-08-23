"""Deadlines, and the timezone trap docs/schema.md calls out by name."""

from __future__ import annotations

import datetime as dt

import pytest

from backend.lib import clock


def test_the_forms_deadline_offset():
    """February 13, 2027 is in PST (UTC-8). End of that California day is
    07:59:59Z on the 14th. Storing 23:59:59Z on the 13th would lock delegates
    out eight hours early."""
    assert clock.end_of_day_utc("2027-02-13") == "2027-02-14T07:59:59Z"


def test_a_deadline_moved_into_daylight_time_changes_offset_by_itself():
    """The whole reason nobody hand-types the UTC string."""
    assert clock.end_of_day_utc("2027-07-13") == "2027-07-14T06:59:59Z"


def test_deadlines_round_trip_back_to_the_date_a_human_typed():
    for date in ("2027-02-13", "2027-07-13", "2027-03-14", "2027-11-07"):
        assert clock.local_date_of(clock.end_of_day_utc(date)) == date


def test_dst_boundary_days_do_not_crash():
    """March 14 2027 is the spring-forward day and November 7 the fall-back.
    A naive implementation produces an ambiguous or non-existent local time."""
    assert clock.end_of_day_utc("2027-03-14").endswith("Z")
    assert clock.end_of_day_utc("2027-11-07").endswith("Z")


def test_rendering_works_on_windows():
    """%-d and %-I are a glibc extension: they work on Modal and raise
    ValueError on Windows, where both commissioners develop."""
    assert clock.render_local("2027-02-14T07:59:59Z") == "February 13, 2027 at 11:59 p.m."
    assert clock.render_local("2027-03-12T17:00:00Z", with_time=False) == "March 12, 2027"


def test_midnight_and_noon_render_correctly():
    """The two hours a 12-hour clock always gets wrong."""
    assert "12:00 a.m." in clock.render_local(clock.start_of_day_utc("2027-03-12"))
    noon = clock.to_iso(dt.datetime(2027, 3, 12, 12, 0, tzinfo=clock.CONVENTION_TZ))
    assert "12:00 p.m." in clock.render_local(noon)


def test_is_past():
    assert clock.is_past("2020-01-01T00:00:00Z")
    assert not clock.is_past("2099-01-01T00:00:00Z")


def test_an_empty_deadline_never_passes():
    """`ops.warm_until` is seeded empty and means 'not warm', not 'warm since
    the beginning of time'. An empty string must never read as elapsed."""
    assert not clock.is_past("")
    assert not clock.is_past(None)
    assert not clock.is_past("   ")


def test_naive_datetimes_are_refused():
    """A naive datetime is the bug that stores local time as if it were UTC."""
    with pytest.raises(ValueError):
        clock.to_iso(dt.datetime(2027, 2, 13, 23, 59, 59))


def test_stored_format_is_exactly_what_the_schema_expects():
    assert clock.now_iso().endswith("Z")
    assert len(clock.now_iso()) == len("2027-02-13T23:59:59Z")
