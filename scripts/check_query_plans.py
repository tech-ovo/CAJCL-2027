"""Run EXPLAIN QUERY PLAN over every query in the registry. Fail on a SCAN.

WHY THIS EXISTS
    In Turso a "row read" is a row SCANNED, not a row returned. A query that
    cannot use an index incurs one read per row in the table. One unindexed
    query in a list view can burn the entire 500M/month read quota in a week,
    and exceeding the quota does not produce a bill -- it produces a BLOCKED
    error and the database stops answering. During convention that is an outage
    nobody can buy their way out of.

    So this is not a style check. It is the guard on the one failure mode that
    can take the site down on the Friday of convention.

WHAT IT DOES
    Builds a fresh in-memory database from the migrations, then asks SQLite for
    the plan of every statement in backend/queries/*.sql. Any plan containing a
    SCAN of a table expected to exceed 200 rows fails the build.

    Small tables are allowed to be scanned: scanning 22 settings rows or 50
    school_stats rows costs less than the index would.

Run it with `python scripts/check_query_plans.py`. CI runs the same command.
"""

from __future__ import annotations

import pathlib
import re
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.lib.migrate import migration_files  # noqa: E402
from backend.lib.queries import REGISTRY  # noqa: E402

# Tables small enough that a full scan is cheaper than an index lookup, with the
# size each is expected to reach. If you add a table here, justify the number.
SMALL_TABLES = {
    "settings": 25,             # fixed set of operational knobs
    "documents": 10,            # blocks of editable prose
    "roles": 15,                # seven system roles plus whatever chairs add
    "role_scopes": 30,
    "catalog_categories": 10,
    "catalog_items": 80,        # ~60 seeded, room to grow
    "catalog_item_options": 40,
    "schools": 60,              # 50 chapters plus the board, upper bound
    "school_stats": 60,         # one row per school
    "public_stats_cache": 1,
    "announcements": 50,
    "roster_imports": 200,      # one row per committed import
    "schema_migrations": 50,
}

# Tables that WILL exceed 200 rows and must always be reached by an index.
# people ~1,150, sessions and login_attempts grow without bound during
# convention, activity_selections ~12,000, audit_log ~100,000.
BIG_TABLES = {
    "people", "sessions", "login_attempts", "audit_log", "form_submissions",
    "paper_forms", "activity_selections", "activity_selection_options",
    "adult_role_selections", "chapter_entries", "payments", "person_roles",
    "contest_submissions", "scores",
}

# Queries allowed to scan a large table, each with the reason. Keep this list
# very short: every entry is a query nobody is checking any more.
EXEMPT: dict[str, str] = {
    "auth.attempts_prune": (
        "Daily cron over login_attempts, which is pruned to 7 days and holds a "
        "few thousand rows at convention peak. An index on attempted_at would "
        "cost a write on every login attempt to save one scan a day."
    ),
}

_SCAN_RE = re.compile(r"\bSCAN\s+(?:TABLE\s+)?([A-Za-z_][A-Za-z0-9_]*)")

# `FROM people p` / `JOIN schools AS s` -- SQLite reports the plan using the
# ALIAS, so without resolving these back to table names every aliased query
# looks like a scan of an unknown table.
_ALIAS_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
_NOT_ALIASES = {
    "on", "where", "group", "order", "limit", "left", "inner", "outer", "cross",
    "join", "using", "set", "values", "select", "and", "or", "having",
}

_COMMENT_RE = re.compile(r"--[^\n]*")


def resolve_aliases(sql: str) -> dict[str, str]:
    """Map each table alias in a statement back to its real table name."""
    mapping: dict[str, str] = {}
    for table, alias in _ALIAS_RE.findall(sql):
        if alias.lower() not in _NOT_ALIASES:
            mapping[alias] = table
    return mapping


def build_schema() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    for path in migration_files():
        conn.executescript(path.read_text(encoding="utf-8"))
    # ANALYZE so the planner has statistics resembling a populated database.
    # Without it SQLite sometimes prefers a scan on an empty table, which would
    # produce failures that do not reflect production.
    conn.execute("ANALYZE")
    return conn


def placeholders_for(sql: str) -> list:
    # Count only real placeholders. A `?` inside an explanatory comment -- and
    # these queries are heavily commented on purpose -- is not a binding.
    return [None] * _COMMENT_RE.sub("", sql).count("?")


def plan_for(conn: sqlite3.Connection, sql: str) -> list[str]:
    rows = conn.execute(f"EXPLAIN QUERY PLAN {sql}", placeholders_for(sql)).fetchall()
    return [r[3] for r in rows]


def main() -> int:
    conn = build_schema()
    failures: list[str] = []
    exempted: list[str] = []
    checked = 0

    for name, query in sorted(REGISTRY.items()):
        try:
            steps = plan_for(conn, query.sql)
        except sqlite3.Error as exc:
            failures.append(f"{name} ({query.source}): will not compile -- {exc}")
            continue

        checked += 1
        if name in EXEMPT:
            exempted.append(name)
            continue

        aliases = resolve_aliases(query.sql)
        for step in steps:
            for found in _SCAN_RE.findall(step):
                table = aliases.get(found, found)
                if table in BIG_TABLES:
                    failures.append(
                        f"{name} ({query.source}): SCAN of {table!r}, which is "
                        f"expected to exceed 200 rows.\n      plan: {step}"
                    )
                elif table not in SMALL_TABLES and not table.startswith("sqlite_"):
                    failures.append(
                        f"{name} ({query.source}): SCAN of unclassified table "
                        f"{table!r}. Add it to SMALL_TABLES with its expected "
                        f"size, or to BIG_TABLES if it will grow.\n      plan: {step}"
                    )

    print(f"checked {checked} queries from "
          f"{len(set(q.source for q in REGISTRY.values()))} files")
    for name in exempted:
        print(f"  exempt: {name} - {EXEMPT[name]}")

    if failures:
        print(f"\n{len(failures)} problem(s):\n")
        for failure in failures:
            print(f"  - {failure}")
        print(
            "\nA SCAN of a large table is billed one row read per row in the "
            "table.\nAdd an index in the migration that creates the table, or "
            "reshape the query."
        )
        return 1

    print("all query plans clean - no SCAN of any table over 200 rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
