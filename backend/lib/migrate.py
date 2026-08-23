"""Forward-only migration runner.

Runs every .sql file in backend/migrations/ that has not run yet, in filename
order, each inside its own transaction. Records what ran in schema_migrations.

Why forward-only with no down-migrations: a down-migration is a script you write
once, never test, and then run for the first time at the worst possible moment.
If a migration is wrong, write another one that corrects it. The audit log and
the most recent export are the actual recovery path -- see docs/RUNBOOK.md.

Runs identically against a local .db file and against Turso, because libSQL is
SQLite and because everything here goes through backend/lib/db.py rather than
touching sqlite3 directly:

    python -m backend.lib.migrate --db dev.db
    TURSO_DATABASE_URL=libsql://... python -m backend.lib.migrate
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sqlite3
import sys

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"

BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  filename   TEXT PRIMARY KEY,
  sha256     TEXT NOT NULL,
  applied_at TEXT NOT NULL
)
"""


def migration_files() -> list[pathlib.Path]:
    """Every migration, in filename order.

    Filenames are zero-padded and numbered so lexical order is execution order.
    """
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def split_statements(sql: str) -> list[str]:
    """Split a migration file into individual statements.

    Uses sqlite3.complete_statement rather than splitting on ';'. A CREATE
    TRIGGER body contains its own semicolons, so a naive split cuts it in half
    and the migration fails with what looks like a syntax error in unrelated
    SQL. This is the same primitive the sqlite3 shell uses.

    One copy of this lives here. The seed script and anything else that has to
    replay migrations imports it rather than writing its own.
    """
    statements, buffer = [], []
    for line in sql.splitlines(keepends=True):
        buffer.append(line)
        candidate = "".join(buffer)
        if candidate.strip() and sqlite3.complete_statement(candidate):
            statements.append(candidate.strip())
            buffer = []
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)

    # Drop chunks that are only comments -- a header block before the first
    # statement is not a statement, and SQLite rejects it as an empty query.
    return [
        s for s in statements
        if any(line.strip() and not line.strip().startswith("--")
               for line in s.splitlines())
    ]


def run(db_or_path, *, verbose: bool = True) -> int:
    """Apply pending migrations. Accepts a path string or a Database."""
    from .db import Database, connect

    db = db_or_path if isinstance(db_or_path, Database) else connect(str(db_or_path))
    owned = not isinstance(db_or_path, Database)

    try:
        with db.tx() as tx:
            tx._backend.execute(BOOTSTRAP, ())
            tx.mark_silent("stats.recompute")
            already = {
                row["filename"]: row["sha256"]
                for row in tx._backend.execute(
                    "SELECT filename, sha256 FROM schema_migrations", ())
            }

        ran = 0
        for path in migration_files():
            sql = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(sql.encode("utf-8")).hexdigest()

            if path.name in already:
                # A migration that has run is frozen. If its contents changed,
                # somebody edited history and this database no longer matches
                # the repository -- fail loudly rather than guessing which is
                # right.
                if already[path.name] != digest:
                    raise SystemExit(
                        f"{path.name} has already been applied but its contents "
                        f"have changed.\nMigrations are forward-only: add a new "
                        f"migration instead of editing this one.\nIf this is a "
                        f"development database, delete it and re-run."
                    )
                continue

            if verbose:
                print(f"  applying {path.name}")
            # One transaction per migration, so a failure rolls that file back
            # whole and leaves schema_migrations honest about what ran.
            with db.tx() as tx:
                for statement in split_statements(sql):
                    tx._backend.execute(statement, ())
                tx._backend.execute(
                    "INSERT INTO schema_migrations (filename, sha256, applied_at) "
                    "VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
                    (path.name, digest))
                tx.mark_silent("stats.recompute")
            ran += 1
        return ran
    finally:
        if owned:
            db.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=None,
                    help="path to a SQLite file; defaults to TURSO_DATABASE_URL, "
                         "then dev.db")
    args = ap.parse_args()

    from .db import connect

    db = connect(args.db)
    print("migrating")
    ran = run(db)
    db.close()
    print(f"done - {ran} migration(s) applied" if ran else "done - already current")


if __name__ == "__main__":
    sys.exit(main())
