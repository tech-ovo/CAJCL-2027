"""The SQL registry.

ALL SQL IN THIS SYSTEM LIVES IN backend/queries/*.sql. Nothing anywhere else
builds a statement out of string pieces. Two reasons, both load-bearing:

1. CI runs EXPLAIN QUERY PLAN over every statement in this registry and fails
   the build on a SCAN of any table expected to exceed 200 rows. A query hidden
   inside a Python f-string is a query nobody checked, and one unindexed query
   in a list view can burn the entire monthly read quota in a week. Exceeding
   the quota is not a bill -- it is a BLOCKED error and an outage you cannot buy
   your way out of during convention.

2. A future commissioner can read every question this system asks the database
   by opening one directory.

FILE FORMAT
    -- name: some.query_name
    -- Any comment explaining WHY this query is shaped the way it is.
    SELECT ...;

Names are dotted and grouped by area (`roster.list`, `auth.person_by_code`).
A duplicate name anywhere in the directory is a hard error -- silently shadowing
one query with another is exactly the sort of thing nobody would find.
"""

from __future__ import annotations

import pathlib
import re

QUERIES_DIR = pathlib.Path(__file__).resolve().parent.parent / "queries"

_NAME_RE = re.compile(r"^--\s*name:\s*([A-Za-z0-9_.]+)\s*$")

# A statement that changes data. Used to enforce the audit-log rule in db.py.
#
# The comment lines have to come off FIRST. Every query in this registry is
# documented, so the keyword is almost never on the first physical line -- and
# an earlier version matched against the raw text, which quietly classified 14
# of 91 queries as read-only. Among them were `payments.create`,
# `people.cancel`, and `stats.upsert_school`: the audit invariant that db.py
# advertises as unbreakable simply did not apply to them, and a read-only
# transaction would have run them without complaint.
#
# The bug was invisible precisely because it hit the queries that were best
# explained. test_queries.py now checks every flag.
_MUTATING = re.compile(r"^\s*(INSERT|UPDATE|DELETE|REPLACE)\b", re.IGNORECASE)
_LEADING_COMMENTS = re.compile(r"\A(?:\s*--[^\n]*\n)+")


def _strip_leading_comments(sql: str) -> str:
    return _LEADING_COMMENTS.sub("", sql).lstrip()


class Query:
    """One named statement, with the source location for error messages."""

    __slots__ = ("name", "sql", "source", "mutating")

    def __init__(self, name: str, sql: str, source: str):
        self.name = name
        self.sql = sql.strip()
        self.source = source
        self.mutating = bool(_MUTATING.match(_strip_leading_comments(self.sql)))

    def __repr__(self) -> str:
        return f"<Query {self.name} from {self.source}>"


def _parse_file(path: pathlib.Path) -> dict[str, Query]:
    found: dict[str, Query] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is None:
            return
        body = "\n".join(buffer).strip()
        if not body:
            raise ValueError(f"{path.name}: query '{current}' has no statement")
        found[current] = Query(current, body.rstrip(";"), f"{path.name}")

    for line in path.read_text(encoding="utf-8").splitlines():
        match = _NAME_RE.match(line)
        if match:
            flush()
            current = match.group(1)
            buffer = []
        elif current is not None:
            buffer.append(line)
    flush()
    return found


def load_all() -> dict[str, Query]:
    """Every named query in backend/queries/, keyed by name."""
    registry: dict[str, Query] = {}
    for path in sorted(QUERIES_DIR.glob("*.sql")):
        for name, query in _parse_file(path).items():
            if name in registry:
                raise ValueError(
                    f"duplicate query name {name!r}: defined in "
                    f"{registry[name].source} and again in {query.source}"
                )
            registry[name] = query
    return registry


# Loaded once at import. The whole registry is a few dozen small strings, and
# re-reading files per request would be silly.
REGISTRY: dict[str, Query] = load_all() if QUERIES_DIR.exists() else {}


def get(name: str) -> Query:
    try:
        return REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"no query named {name!r}. Queries live in backend/queries/*.sql "
            f"and are declared with a `-- name:` comment."
        ) from None


def sql(name: str) -> str:
    return get(name).sql
