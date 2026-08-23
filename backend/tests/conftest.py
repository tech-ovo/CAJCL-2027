"""Shared test fixtures.

Every test gets a fresh, fully-migrated in-memory database. Migrations run in
about 20ms, so there is no reason to share state between tests and every reason
not to.
"""

from __future__ import annotations

import pathlib
import sqlite3
import sys

import pytest

# Latin text with macrons appears in settings, in fixtures, and in failure
# messages. On Windows the console codepage is cp1252 and printing a macron
# raises UnicodeEncodeError -- which looks exactly like a test failure and is
# not one. Reconfiguring here means `pytest` just works, with no wrapper script.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from backend.lib.migrate import migration_files  # noqa: E402


@pytest.fixture
def db() -> sqlite3.Connection:
    """A migrated, empty (but seeded) database.

    Seeded means the system roles, settings, documents, and catalog from
    migrations 005 and 006 are present -- those are part of the schema's
    definition of "empty", not test data.
    """
    conn = sqlite3.connect(":memory:")
    # Without this every foreign key in the schema is decorative. SQLite
    # defaults it OFF and the failure is silent.
    conn.execute("PRAGMA foreign_keys = ON")
    for path in migration_files():
        conn.executescript(path.read_text(encoding="utf-8"))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def school(db) -> int:
    """One ordinary high-school chapter. Returns its id."""
    cur = db.execute(
        "INSERT INTO schools (name, level, city, created_at, updated_at) "
        "VALUES ('Test High School', 'HS', 'Irvine', '2026-09-01T00:00:00Z', '2026-09-01T00:00:00Z')"
    )
    return cur.lastrowid


def make_person(db, school_id: int, **overrides) -> int:
    """Insert a delegate, overriding any column. Returns the new id.

    Deliberately does no validation of its own: several tests need to attempt
    inserts that the schema must reject.
    """
    row = {
        "school_id": school_id,
        "person_type": "delegate",
        "first_name": "Test",
        "last_name": "Person",
        "code_hmac": f"hmac-{overrides.pop('_hmac_seed', 'default')}",
        "code_prefix": "DEL",
        "code_issued_at": "2026-09-01T00:00:00Z",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
    }
    row.update(overrides)
    cols = ", ".join(row)
    marks = ", ".join("?" * len(row))
    cur = db.execute(f"INSERT INTO people ({cols}) VALUES ({marks})", list(row.values()))
    return cur.lastrowid
