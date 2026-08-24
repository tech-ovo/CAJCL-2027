"""Settings: the values a convention is operated from.

Every one of these is editable from the admin dashboard. Brand and layout are
code and are expected to change when the 73rd convention moves to a different
school; convention operations are data and must never be code. If running a
convention requires a deploy, something is in the wrong layer.

CACHING
    ~22 rows, read on nearly every request. Loaded once per container and
    refreshed when a setting is written. Not per-request: 22 row reads on every
    page load across a season is real money against the Turso read quota, for
    values that change a handful of times a year.

    The cache is per-container and Modal runs several. A setting written on one
    container is not visible on another until its own cache expires, so there is
    a short TTL as well -- see CACHE_SECONDS.
"""

from __future__ import annotations

import time

from .db import Tx

# How long a container may serve a stale setting. Long enough that the cache
# does its job; short enough that an admin changing the announcement banner or
# a deadline sees it take effect across all containers within a minute.
CACHE_SECONDS = 60

_cache: dict[str, str] | None = None
_cache_types: dict[str, str] = {}
_cache_loaded_at: float = 0.0


def load(tx: Tx, *, force: bool = False) -> dict[str, str]:
    """All settings as {key: raw string value}."""
    global _cache, _cache_loaded_at, _cache_types

    fresh_enough = (
        _cache is not None
        and not force
        and (time.monotonic() - _cache_loaded_at) < CACHE_SECONDS
    )
    if fresh_enough:
        return _cache

    rows = tx.all("settings.all")
    _cache = {row["key"]: row["value"] for row in rows}
    _cache_types = {row["key"]: row["value_type"] for row in rows}
    _cache_loaded_at = time.monotonic()
    return _cache


def invalidate() -> None:
    """Drop this container's cache. Called after a settings write."""
    global _cache, _cache_loaded_at
    _cache = None
    _cache_loaded_at = 0.0


def rows(tx: Tx) -> list:
    """Full setting rows, for the dashboard editor."""
    return tx.all("settings.all")


# --- typed accessors -------------------------------------------------------
# Values are stored as TEXT because settings is a heterogeneous key-value table.
# These are the only sanctioned way to read one as something other than a
# string, so a stray int() on a cents value cannot appear in three places with
# three different fallbacks.

def get(tx: Tx, key: str, default: str = "") -> str:
    return load(tx).get(key, default)


def get_int(tx: Tx, key: str, default: int = 0) -> int:
    raw = load(tx).get(key, "").strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def get_bool(tx: Tx, key: str, default: bool = False) -> bool:
    raw = load(tx).get(key, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def get_datetime(tx: Tx, key: str) -> str:
    """A stored UTC instant, or '' when unset.

    Empty means "no deadline"/"not warm" -- never "since the beginning of time".
    clock.is_past('') returns False for exactly this reason.
    """
    return load(tx).get(key, "").strip()


def fee_settings(tx: Tx) -> dict[str, int]:
    """The three numbers the invoice is computed from."""
    return {
        "fee.delegate_cents": get_int(tx, "fee.delegate_cents", 14000),
        "fee.extra_adult_cents": get_int(tx, "fee.extra_adult_cents", 7500),
        "fee.adult_ratio": get_int(tx, "fee.adult_ratio", 10),
    }


def public_convention(tx: Tx) -> dict[str, str]:
    """The subset the unauthenticated welcome page is allowed to see.

    An explicit allowlist, not a prefix match: `ops.*` holds the warm window and
    the auto-export schedule, and none of that belongs on a public endpoint.
    """
    values = load(tx)
    keys = (
        "convention.year", "convention.ordinal",
        "convention.start_date", "convention.end_date",
        "convention.venue_name", "convention.venue_address",
        "convention.hosts",
        "convention.theme_latin", "convention.theme_english",
        "convention.theme_citation", "convention.contact_email",
    )
    return {key: values.get(key, "") for key in keys}
