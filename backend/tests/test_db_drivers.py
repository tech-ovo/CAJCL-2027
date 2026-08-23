"""Both database drivers, exercised through the same code path.

Local development, the test suite, and every worker use `sqlite3` from the
standard library. Production uses `libsql`, the current Turso driver. Both are
DB-API 2.0 with qmark parameters, and `backend/lib/db.py` holds one handle class
for both -- so the thing these tests are really checking is that the shared
handle behaves identically no matter which driver is underneath.

WHAT THIS CANNOT CHECK
    The network. `libsql` here talks to a local file, which exercises the
    driver, the transaction handling, the row shaping, and the pragmas -- but not
    the wire protocol or the auth token. If production fails after these pass,
    the problem is credentials, the URL, or the network, and not this code.

WHY IT MATTERS
    `libsql-client`, the previous driver, was archived in June 2025. It speaks
    the WebSocket (hrana) protocol and current Turso endpoints reject that
    handshake with a 400 before any SQL runs -- while the Turso CLI connects to
    the same database perfectly happily, which makes the failure look like
    anything except a driver problem. These tests exist so the next driver
    change is caught here rather than at a board meeting.
"""

from __future__ import annotations

import pathlib

import pytest

from backend.lib import clock
from backend.lib.db import AuditRequired, Database, Row, _open_local, _open_remote
from backend.lib.migrate import migration_files

libsql = pytest.importorskip("libsql")


def build(handle) -> None:
    """Run every migration through a handle, one statement at a time."""
    from backend.lib.migrate import split_statements

    handle.begin()
    for path in migration_files():
        for statement in split_statements(path.read_text(encoding="utf-8")):
            handle.execute(statement, ())
    handle.commit()


@pytest.fixture(params=["sqlite3", "libsql"])
def handle(request, tmp_path):
    """The same database, opened by each driver in turn."""
    path = str(tmp_path / f"{request.param}.db")
    made = _open_local(path) if request.param == "sqlite3" else _open_remote(path, None)
    yield made
    made.close()


# ---------------------------------------------------------------------------
# The shared handle behaves the same either way
# ---------------------------------------------------------------------------

def test_the_whole_schema_builds(handle):
    build(handle)
    handle.begin()
    tables = {r["name"] for r in handle.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'", ())}
    handle.rollback()
    for expected in ("people", "schools", "audit_log", "settings", "catalog_items"):
        assert expected in tables


def test_rows_come_back_as_named_mappings(handle):
    build(handle)
    handle.begin()
    rows = handle.execute(
        "SELECT key, value FROM settings WHERE key = ?", ("fee.delegate_cents",))
    handle.rollback()

    assert len(rows) == 1
    assert isinstance(rows[0], Row)
    assert rows[0]["key"] == "fee.delegate_cents"
    assert rows[0].value == "14000"          # attribute access too


def test_a_statement_returning_nothing_yields_no_rows(handle):
    """`description` is None for a non-SELECT in both drivers, and the handle
    relies on exactly that to tell the two cases apart."""
    build(handle)
    handle.begin()
    rows = handle.execute(
        "UPDATE settings SET value = ? WHERE key = ?",
        ("15000", "fee.delegate_cents"))
    assert rows == []
    assert handle.rows_changed == 1
    handle.rollback()


def test_last_insert_id_and_rows_changed(handle):
    build(handle)
    handle.begin()
    handle.execute(
        "INSERT INTO schools (name, level, kind, created_at, updated_at) "
        "VALUES (?, ?, 'chapter', ?, ?)",
        ("Driver Test High School", "HS", clock.now_iso(), clock.now_iso()))
    assert handle.last_insert_id > 0
    assert handle.rows_changed == 1
    handle.rollback()


def test_rollback_actually_discards(handle):
    build(handle)
    handle.begin()
    before = handle.execute("SELECT COUNT(*) AS n FROM schools", ())[0]["n"]
    handle.execute(
        "INSERT INTO schools (name, level, kind, created_at, updated_at) "
        "VALUES ('Gone', 'HS', 'chapter', '2026-01-01T00:00:00Z', "
        "'2026-01-01T00:00:00Z')", ())
    handle.rollback()

    handle.begin()
    after = handle.execute("SELECT COUNT(*) AS n FROM schools", ())[0]["n"]
    handle.rollback()
    assert after == before


def test_foreign_keys_are_enforced(handle):
    """SQLite defaults foreign keys OFF, and the failure is completely silent.
    Both drivers must have them ON before anything else runs."""
    build(handle)
    handle.begin()
    with pytest.raises(Exception):
        handle.execute(
            "INSERT INTO people (school_id, person_type, first_name, last_name, "
            "code_hmac, code_prefix, code_issued_at, created_at, updated_at) "
            "VALUES (999999, 'delegate', 'A', 'B', 'x', 'DEL', ?, ?, ?)",
            (clock.now_iso(), clock.now_iso(), clock.now_iso()))
    handle.rollback()


def test_check_constraints_are_enforced(handle):
    """The person-type split is enforced by the database, not by application
    code -- so it has to survive a change of driver."""
    build(handle)
    handle.begin()
    handle.execute(
        "INSERT INTO schools (name, level, kind, created_at, updated_at) "
        "VALUES ('X', 'HS', 'chapter', ?, ?)", (clock.now_iso(), clock.now_iso()))
    school = handle.last_insert_id

    with pytest.raises(Exception):
        # A delegate may not have an email. Several delegates are eleven.
        handle.execute(
            "INSERT INTO people (school_id, person_type, first_name, last_name, "
            "email, code_hmac, code_prefix, code_issued_at, created_at, updated_at) "
            "VALUES (?, 'delegate', 'A', 'B', 'kid@example.com', 'x', 'DEL', ?, ?, ?)",
            (school, clock.now_iso(), clock.now_iso(), clock.now_iso()))
    handle.rollback()


def test_the_audit_log_stays_append_only(handle):
    """A trigger, not a convention. Triggers have to survive the driver too."""
    build(handle)
    handle.begin()
    handle.execute(
        "INSERT INTO audit_log (ts_utc, action, summary) VALUES (?, 'x', 'y')",
        (clock.now_iso(),))
    with pytest.raises(Exception):
        handle.execute("UPDATE audit_log SET summary = 'rewritten'", ())
    handle.rollback()


# ---------------------------------------------------------------------------
# The Database wrapper over the remote driver
# ---------------------------------------------------------------------------

def test_database_drives_the_libsql_path_end_to_end(tmp_path, monkeypatch):
    """Everything a real request does, through the production driver.

    Only the network is left unproven.
    """
    path = str(tmp_path / "remote-shaped.db")

    # Force the remote branch, then hand it a local file so there is no network.
    db = Database(url=path, auth_token=None)
    monkeypatch.setattr("backend.lib.db._open_remote",
                        lambda url, token: _open_remote(url, token))

    from backend.lib.migrate import run
    run(db, verbose=False)

    with db.tx() as tx:
        school_id = tx.insert("schools.create", (
            "Remote Path High School", "HS", "chapter", "Irvine", 0, 0, None,
            None, clock.now_iso(), clock.now_iso()))
        tx.run("schools.stats_init", (school_id, clock.now_iso()))
        tx.audit("school.create", "Driver test created a chapter.",
                 school_id=school_id, entity_type="school", entity_id=school_id)

    with db.read() as tx:
        school = tx.one("schools.get", (school_id,))
        assert school["name"] == "Remote Path High School"
        entries = tx.all("audit.recent", (10 ** 9, 10))
        assert any(e["action"] == "school.create" for e in entries)

    # The audit invariant survives the driver change.
    with pytest.raises(AuditRequired):
        with db.tx() as tx:
            tx.run("schools.stats_init", (school_id, clock.now_iso()))

    db.close()


def test_connect_routes_urls_to_the_right_driver(monkeypatch, tmp_path):
    from backend.lib import db as db_module

    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    local = db_module.connect(str(tmp_path / "x.db"))
    assert local._url is None and local._path is not None

    for url in ("libsql://example.turso.io", "https://example.turso.io"):
        remote = db_module.connect(url, auth_token="t")
        assert remote._url == url
        assert remote._auth_token == "t"
        assert remote._path is None


def test_nothing_imports_the_archived_driver():
    """`libsql-client` was archived in June 2025 and its handshake is rejected
    by current Turso endpoints. If it comes back, it comes back deliberately."""
    import re

    root = pathlib.Path(__file__).resolve().parents[2]
    # An actual import statement, not the name appearing in a comment or in
    # this test's own source.
    pattern = re.compile(r"^\s*(?:import|from)\s+libsql_client", re.MULTILINE)

    offenders = []
    for path in list(root.glob("backend/**/*.py")) + list(root.glob("scripts/*.py")):
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"the archived driver is imported by {offenders}"


def test_audit_accepts_a_backdated_timestamp(tmp_path):
    """The demo seed lays down a log spanning ten weeks.

    Without this, every entry is stamped with the moment the seed ran, and the
    activity log at a board meeting shows several months of registration all
    happening one Tuesday afternoon. Request paths never pass `ts`.

    This has now been dropped twice while rewriting `db.py`, hence the test.
    """
    from backend.lib.db import Database
    from backend.lib.migrate import run

    db = Database(path=str(tmp_path / "backdated.db"))
    run(db, verbose=False)

    with db.tx() as tx:
        tx.audit("school.create", "Something happened a while ago.",
                 ts="2026-06-10T12:00:00Z")

    with db.read() as tx:
        entry = tx.all("audit.recent", (10 ** 9, 5))[0]
    assert entry["ts_utc"] == "2026-06-10T12:00:00Z"

    # And the default is still now.
    with db.tx() as tx:
        tx.audit("school.create", "Something happened just now.")
    with db.read() as tx:
        newest = tx.all("audit.recent", (10 ** 9, 5))[0]
    assert newest["ts_utc"].startswith(clock.now_iso()[:13])
    db.close()


# ---------------------------------------------------------------------------
# Credentials that cannot be sent
# ---------------------------------------------------------------------------

def test_surrounding_whitespace_is_trimmed_from_credentials(monkeypatch):
    """A trailing newline is what you get from `echo`, from a browser text box,
    and from most ways of putting a token into a file. It must not be fatal."""
    from backend.lib import db as db_module

    monkeypatch.setenv("TURSO_DATABASE_URL", "  libsql://example.turso.io\n")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "ey.J.token\n")

    database = db_module.connect()
    assert database._url == "libsql://example.turso.io"
    assert database._auth_token == "ey.J.token"


def test_a_credential_with_an_interior_newline_is_named_and_refused(monkeypatch):
    """The driver's own report of this is

        Hrana: `http error: `http::Error(InvalidHeaderValue)``

    which names neither the setting nor the character, arrives only when a
    transaction opens, and looks for all the world like a network problem. It
    happens when a long token wraps in the terminal and the break is copied
    with it.
    """
    from backend.lib import db as db_module

    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "ey.J.first\nsecond.half")

    with pytest.raises(ValueError) as caught:
        db_module.connect()

    message = str(caught.value)
    assert "TURSO_AUTH_TOKEN" in message
    assert "a newline" in message
    # Never the token itself: this message ends up in Modal's logs.
    assert "ey.J.first" not in message


def test_a_non_ascii_credential_is_refused_by_codepoint(monkeypatch):
    from backend.lib import db as db_module

    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "ey.J\u00a0token")     # non-breaking space

    with pytest.raises(ValueError, match=r"U\+00A0"):
        db_module.connect()


def test_a_local_path_is_left_alone(monkeypatch, tmp_path):
    """The check is about HTTP headers. A local file has none, and a Windows
    path or a directory with a space in it is perfectly legitimate."""
    from backend.lib import db as db_module

    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    path = tmp_path / "a folder with spaces" / "dev.db"
    path.parent.mkdir()
    assert db_module.connect(str(path))._path == str(path)
