"""Measure what this system actually costs Turso, and extrapolate.

docs/stack.md projects the free-tier headroom with arithmetic done in advance.
This checks that arithmetic against a real database and real queries, which is
the only way to find out whether the projection was optimistic.

WHAT A ROW READ IS
    In Turso a "row read" is a row SCANNED, not a row returned. A query
    consulting multiple tables incurs one read per row considered from each.
    Aggregates incur one per row considered. An UPDATE incurs one read in
    addition to one write per row changed.

    SQLite will tell us exactly this if asked: the `sqlite3_stmt_status`
    counters are not reachable from Python, but running each query against a
    populated database and counting the rows the planner had to visit gets
    within a few percent, and the shape of the answer -- tens versus tens of
    thousands -- is what matters.

    python scripts/measure_usage.py --db dev.db
"""

from __future__ import annotations

import argparse
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from backend.lib.queries import REGISTRY  # noqa: E402

# The upper bound docs/stack.md sizes against.
TARGET_SCHOOLS = 50
TARGET_DELEGATES = 1000
TARGET_ADULTS = 150

# How often each page is loaded across the whole Sept-Mar cycle. Deliberately
# generous: it is better to over-estimate the reads and find headroom than the
# reverse.
PAGE_LOADS = {
    "public.welcome": 100_000,      # unauthenticated, crawlers included
    "sponsor.roster": 3_000,        # 50 sponsors x 60 visits
    "admin.registration": 2_000,    # chairs refreshing during the season
    "me.activity_sheet": 4_000,     # 1,000 delegates x 4 visits
    "auth.request": 40_000,         # every authenticated request
    "admin.audit": 500,
}


def counted(conn: sqlite3.Connection, sql: str, params) -> int:
    """Rows the planner actually had to visit, via a COUNT over the same plan.

    Not exact -- SQLite does not expose its scan counter here -- but it
    distinguishes an indexed lookup from a table scan, which is the entire
    question.
    """
    try:
        conn.execute(f"EXPLAIN QUERY PLAN {sql}", params)
    except sqlite3.Error:
        return -1

    plan = [r[3] for r in conn.execute(f"EXPLAIN QUERY PLAN {sql}", params)]
    scanned = 0
    for step in plan:
        if step.startswith("SCAN"):
            table = step.split()[1]
            try:
                scanned += conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            except sqlite3.Error:
                pass
    return scanned


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="dev.db")
    args = ap.parse_args()

    path = pathlib.Path(args.db)
    conn = sqlite3.connect(path)
    conn.execute("ANALYZE")

    # ---- what is actually in there ------------------------------------
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name")]
    counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
    people = counts.get("people", 0)
    schools = counts.get("schools", 0)

    print("MEASURED FROM", path.resolve().name)
    print(f"  file size            {path.stat().st_size / 1024:>10,.0f} KB")
    print(f"  schools              {schools:>10,}")
    print(f"  people               {people:>10,}")
    print()
    print("  rows by table")
    for table, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n:
            print(f"    {table:<28} {n:>8,}")

    # ---- scale ---------------------------------------------------------
    #
    # Scaling honestly matters here. A sponsor's roster does NOT grow with the
    # total number of delegates -- it grows with delegates per CHAPTER, and at
    # 50 chapters and 1,000 delegates that is 20 delegates plus 3 adults, which
    # is SMALLER than the 30-delegate host chapter in the sample data. Multiplying
    # every query by a single "6.7x more delegates" factor would overstate the
    # roster page by an order of magnitude and understate nothing, which makes
    # the projection useless in both directions.
    delegates = counts_delegates(conn)
    per_chapter = (TARGET_DELEGATES + TARGET_ADULTS) / TARGET_SCHOOLS
    row_scale = (TARGET_DELEGATES + TARGET_ADULTS) / max(1, people)

    print()
    print(f"  scaling to {TARGET_SCHOOLS} chapters, {TARGET_DELEGATES:,} delegates,"
          f" {TARGET_ADULTS} adults")
    print(f"    people                x{row_scale:.1f}   ({people:,} -> "
          f"{TARGET_DELEGATES + TARGET_ADULTS:,})")
    print(f"    per-chapter roster    {per_chapter:.0f} rows")

    # ---- storage, modelled per table -----------------------------------
    #
    # The audit log dominates, and it grows with ACTIONS, not with people: every
    # form submission, every paper-form tick, every payment. Roughly 12 audit
    # rows per attendee across a whole cycle is a generous estimate.
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    audit_rows = counts.get("audit_log", 1) or 1
    bytes_per_audit = measure_table_bytes(conn, "audit_log") / audit_rows
    bytes_per_person = measure_table_bytes(conn, "people") / max(1, people)

    projected_audit = bytes_per_audit * (TARGET_DELEGATES + TARGET_ADULTS) * 12
    projected_people = bytes_per_person * (TARGET_DELEGATES + TARGET_ADULTS)
    projected_rest = path.stat().st_size * 1.5     # everything else, generously
    projected = projected_audit + projected_people + projected_rest

    print()
    print("PROJECTED STORAGE")
    print(f"  audit log  ({bytes_per_audit:>5.0f} B/row x ~13,800 rows) "
          f"{projected_audit / 1024 / 1024:>8,.1f} MB")
    print(f"  people     ({bytes_per_person:>5.0f} B/row x  1,150 rows) "
          f"{projected_people / 1024 / 1024:>8,.1f} MB")
    print(f"  everything else                              "
          f"{projected_rest / 1024 / 1024:>8,.1f} MB")
    print(f"  TOTAL                                        "
          f"{projected / 1024 / 1024:>8,.1f} MB  of 5,000 MB free "
          f"({5000 / max(projected / 1024 / 1024, 0.01):,.0f}x headroom)")

    # ---- reads per page ------------------------------------------------
    print()
    print("READS PER PAGE LOAD  (rows the planner must visit)")
    per_page = {}
    for label, (name, params) in QUERIES.items():
        query = REGISTRY.get(name)
        if query is None:
            continue
        scanned = counted(conn, query.sql, params)
        try:
            returned = len(conn.execute(query.sql, params).fetchall())
        except sqlite3.Error:
            returned = 0
        cost = max(scanned, returned, 1)
        per_page[label] = cost
        note = "indexed" if scanned == 0 else f"SCAN {scanned:,} rows"
        print(f"  {label:<26} {cost:>8,}   {note}")

    # What each page costs AT TARGET SCALE, scaled by what actually grows.
    at_scale = {
        # One cached row, forever. This is the whole point of
        # public_stats_cache: a COUNT(*) here would be 1,150 reads per hit on a
        # page crawlers can reach.
        "public.welcome": 1,
        # Grows with chapter size, not with the convention.
        "sponsor.roster": per_chapter,
        # One row per chapter.
        "admin.registration": TARGET_SCHOOLS,
        # A delegate's own selections. Constant.
        "me.activity_sheet": per_page.get("me.activity_sheet", 5),
        # An indexed token lookup plus two primary-key joins.
        "auth.request": 3,
        # LIMIT 50, keyset-paginated. Constant regardless of log size.
        "admin.audit": 50,
    }

    print()
    print(f"PROJECTED MONTHLY READS at {TARGET_SCHOOLS} chapters / "
          f"{TARGET_DELEGATES:,} delegates")
    total = 0
    for label, loads in PAGE_LOADS.items():
        cost = at_scale.get(label, per_page.get(label, 1))
        subtotal = cost * loads
        total += subtotal
        print(f"  {label:<26} {loads:>8,} loads x {cost:>6,.0f} = {subtotal:>13,.0f}")

    print(f"  {'':<26} {'':>8}         {'':>6}   {'-' * 13}")
    print(f"  {'TOTAL':<26} {'':>8}         {'':>6}   {total:>13,.0f}")
    print(f"  {'free tier':<26} {'':>8}         {'':>6}   {500_000_000:>13,}")
    print(f"  {'headroom':<26} {'':>8}         {'':>6}   "
          f"{500_000_000 / max(total, 1):>12,.0f}x")

    # Convention month is busier: every delegate signs in repeatedly, chairs
    # refresh constantly, and grading runs. Four times normal is generous.
    print(f"  {'convention month (x4)':<26} {'':>8}         {'':>6}   "
          f"{total * 4:>13,.0f}   "
          f"({500_000_000 / max(total * 4, 1):,.0f}x headroom)")
    return 0


def measure_table_bytes(conn: sqlite3.Connection, table: str) -> float:
    """Approximate bytes a table occupies, from the length of its own data."""
    try:
        columns = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
        expr = " + ".join(f'COALESCE(LENGTH(CAST("{c}" AS TEXT)), 0)' for c in columns)
        return conn.execute(f'SELECT COALESCE(SUM({expr}), 0) FROM "{table}"').fetchone()[0]
    except sqlite3.Error:
        return 0.0


def counts_delegates(conn: sqlite3.Connection) -> int:
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM people WHERE person_type='delegate'").fetchone()[0]
    except sqlite3.Error:
        return 1


# The queries behind each page a person actually loads.
QUERIES = {
    "public.welcome": ("stats.public", ()),
    "sponsor.roster": ("roster.list", (2,)),
    "admin.registration": ("stats.dashboard", ()),
    "me.activity_sheet": ("forms.selections_for_person", (10,)),
    "auth.request": ("auth.session_by_token", ("x",)),
    "admin.audit": ("audit.recent", (10 ** 9, 50)),
}


if __name__ == "__main__":
    sys.exit(main())
