"""Database access, and the two invariants that are enforced rather than trusted.

ONE SYNC INTERFACE, TWO BACKENDS
    Local development, the test suite, and every worker run against a plain
    SQLite file. Production runs against Turso. libSQL *is* SQLite, so the same
    statements, the same `.db` exports, and the same mental model apply to both.
    A worker handed a `.db` file runs unmodified in a Google Colab, which is the
    foundation of every fallback plan in docs/stack.md.

INVARIANT 1 -- NOTHING CHANGES DATA WITHOUT AN AUDIT ENTRY
    A transaction that ran a mutating statement and did not write an audit row
    refuses to commit. This is checked in code, not left to reviewer discipline,
    because "remember to log it" is the kind of rule that survives exactly as
    long as nobody is in a hurry.

INVARIANT 2 -- COUNTERS MOVE WITH THE DATA
    `school_stats` and `public_stats_cache` are recomputed inside the same
    transaction as the mutation that changes them. Never afterwards, never on a
    timer, never live for a page view. See stats.py.

READS ARE THE QUOTA THAT MATTERS
    In Turso a "row read" is a row *scanned*, not a row returned. Every query
    here comes from the registry in queries.py so CI can check its plan. There
    is no execute-arbitrary-string method on purpose.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

from . import clock
from .queries import get as get_query

# Actions that legitimately change nothing a human needs told about. Everything
# else must audit. Kept deliberately short -- if you are adding to this list,
# ask whether the action really is invisible to a future commissioner reading
# the log to work out what happened.
SILENT_ACTIONS = frozenset({
    # Session bookkeeping on every authenticated request. Auditing a
    # last_seen_at bump would drown the log in noise and tell nobody anything.
    "session.touch",
    # Rate-limit bookkeeping. Failed logins ARE audited, via auth.login_failed;
    # this is the row that makes counting possible.
    "login_attempt.record",
    # The counter caches. They are derived data; the mutation that moved them is
    # already audited, and logging both would double every entry.
    "stats.recompute",
})


class Row(dict):
    """A result row. A dict, so workers and exporters need no special type."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None


class AuditRequired(RuntimeError):
    """Raised when a transaction changed data and wrote no audit entry."""


# ---------------------------------------------------------------------------
# Backend adapters
# ---------------------------------------------------------------------------

# Each transaction gets its OWN connection handle rather than sharing one.
#
# Two reasons, both of which bit during the build:
#   - Modal runs several containers and serves concurrent requests. A single
#     shared connection means two requests interleaving inside one transaction,
#     and whichever commits first commits the other's half-finished work.
#   - Nesting. A helper that opens a read transaction, called from inside a
#     write transaction, fails with "cannot start a transaction within a
#     transaction" -- and the natural fix (silently joining the outer one) makes
#     rollback boundaries invisible.
#
# Opening a connection costs microseconds locally and one HTTP round trip
# remotely, so a handle per transaction is cheap in both directions.
#
# ONE HANDLE CLASS SERVES BOTH BACKENDS.
#   `sqlite3` (standard library) drives a local file. `libsql` (the current
#   Turso driver) drives a remote database. Both are DB-API 2.0 with qmark
#   parameters, so the code below does not care which it is holding -- only the
#   two statements that genuinely differ are parameterised.
#
#   The previous version used `libsql-client`, which was archived in June 2025.
#   It spoke the WebSocket (hrana) protocol, and current Turso endpoints reject
#   that handshake with `WSServerHandshakeError: 400` before any SQL runs. The
#   symptom is confusing because the CLI connects to the same database happily.
#   If you see that error again, check the driver before checking anything else.


class _Handle:
    """One connection, local or remote. The only place a driver is touched."""

    def __init__(self, conn, *, begin_sql: str):
        self._conn = conn
        self._begin_sql = begin_sql
        self.last_insert_id = None
        self.rows_changed = 0

    def execute(self, sql: str, params: Sequence[Any]) -> list[Row]:
        cursor = self._conn.execute(sql, tuple(params))

        # The two drivers disagree about how to say "this returned no rows",
        # and they disagree in opposite directions:
        #
        #   sqlite3   description = None   fetchall() = []
        #   libsql    description = []     fetchall() = None
        #
        # Treating either signal alone as authoritative crashes on the other
        # driver, so both are checked. This is the only place in the codebase
        # that has to know the difference.
        columns = [column[0] for column in (cursor.description or ())]
        rows: list[Row] = []
        if columns:
            records = cursor.fetchall() or ()
            rows = [Row(zip(columns, record)) for record in records]

        self.last_insert_id = cursor.lastrowid
        self.rows_changed = cursor.rowcount
        return rows

    def begin(self) -> None:
        self._conn.execute(self._begin_sql)

    def commit(self) -> None:
        self._conn.execute("COMMIT")

    def rollback(self) -> None:
        self._conn.execute("ROLLBACK")

    def close(self) -> None:
        self._conn.close()


def _open_local(path: str) -> _Handle:
    conn = sqlite3.connect(path, isolation_level=None)
    # Without this every foreign key in the schema is decorative. SQLite
    # defaults it OFF and the failure is completely silent.
    conn.execute("PRAGMA foreign_keys = ON")
    if path != ":memory:":
        # WAL lets a reader -- an export, a Colab session -- run while the app
        # writes.
        conn.execute("PRAGMA journal_mode = WAL")
        # Wait for another writer rather than failing instantly.
        conn.execute("PRAGMA busy_timeout = 5000")
    # BEGIN IMMEDIATE takes the write lock up front, so two local writers fail
    # fast instead of deadlocking halfway through a transaction.
    return _Handle(conn, begin_sql="BEGIN IMMEDIATE")


# Anything outside printable ASCII cannot go in an HTTP header. The driver
# sends the auth token as `Authorization: Bearer <token>`, so a single stray
# newline -- from a copy-paste of a line-wrapped token, or from a browser text
# box -- makes the request unbuildable before it is ever sent.
_HEADER_SAFE = re.compile(r"\A[ -~]*\Z")

_NAMES = {chr(9): "a tab", chr(10): "a newline", chr(13): "a carriage return"}


def _clean_credential(value: str | None, variable: str) -> str | None:
    """Trim a credential, and refuse one that cannot be sent.

    A trailing newline is the single most common way this configuration goes
    wrong, and the driver's own report of it is
    `Hrana: http error: http::Error(InvalidHeaderValue)` -- which names neither
    the variable nor the character. Strip what is safely strippable, and be
    specific about what is not.
    """
    if value is None:
        return None

    cleaned = value.strip()
    if _HEADER_SAFE.match(cleaned):
        return cleaned

    bad = sorted({char for char in cleaned if not _HEADER_SAFE.match(char)})
    described = ", ".join(_NAMES.get(char, f"U+{ord(char):04X}") for char in bad)
    raise ValueError(
        f"{variable} contains {described}, which cannot be sent in an HTTP "
        f"header. The value is {len(cleaned)} characters long.\n\n"
        f"This is almost always a copy-paste artefact: a long token wraps in "
        f"the terminal, and the line break is copied along with it.\n\n"
        f"Set it again without typing it out, so nothing can be introduced by "
        f"hand:\n"
        f'    TURSO_AUTH_TOKEN="$(turso db tokens create cajcl-2027)"\n'
        f'    TURSO_DATABASE_URL="$(turso db show cajcl-2027 --url)"\n'
        f"then re-create the Modal secret with --force. See docs/DEPLOY.md, "
        f"step 2."
    )


def _open_remote(url: str, auth_token: str | None) -> _Handle:
    try:
        import libsql
    except ImportError:
        # The most likely reason by far is ARM64 Linux, where libsql publishes
        # no wheel and pip tries to compile it from Rust source. Say so, because
        # "No module named libsql" sends people to `pip install libsql`, which
        # is exactly the thing that just failed.
        raise RuntimeError(
            "The `libsql` driver is not installed, so this cannot reach a "
            "hosted Turso database.\n\n"
            "If you are on ARM64 Linux (a Snapdragon laptop, or Linux in a VM "
            "on Apple silicon) there is no wheel for your platform and building "
            "it from source needs cmake and a Rust toolchain.\n\n"
            "You almost certainly do not need it. Either:\n"
            "  - work against a local file:  --db dev.db\n"
            "  - or run this on Modal:       modal run backend/app.py::setup\n\n"
            "See docs/RUNBOOK.md, 'Working with the real database from an ARM "
            "machine'."
        ) from None

    # isolation_level=None puts the driver in autocommit, so the explicit
    # BEGIN/COMMIT in Database.tx() is the only thing managing transactions.
    # Leaving it at the DB-API default would have the driver open its own
    # transaction as well, and the two would fight.
    url = _clean_credential(url, "TURSO_DATABASE_URL")
    auth_token = _clean_credential(auth_token, "TURSO_AUTH_TOKEN")

    conn = libsql.connect(url, auth_token=auth_token or "", isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    # Plain BEGIN, not IMMEDIATE: a hosted database has a single writer already,
    # and IMMEDIATE is a local-file locking concern that remote need not honour.
    return _Handle(conn, begin_sql="BEGIN")


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class Tx:
    """One transaction. Every write in this system goes through one of these."""

    def __init__(self, backend, *, request_id: str | None = None):
        self._backend = backend
        self.request_id = request_id
        self._mutated: list[str] = []
        self._audited = False

    # -- reading ------------------------------------------------------------

    def all(self, name: str, params: Sequence[Any] = ()) -> list[Row]:
        query = get_query(name)
        rows = self._backend.execute(query.sql, params)
        if query.mutating:
            self._mutated.append(name)
        return rows

    def one(self, name: str, params: Sequence[Any] = ()) -> Row | None:
        rows = self.all(name, params)
        return rows[0] if rows else None

    def value(self, name: str, params: Sequence[Any] = (), default: Any = None) -> Any:
        row = self.one(name, params)
        if row is None:
            return default
        return next(iter(row.values()))

    # -- writing ------------------------------------------------------------

    def run(self, name: str, params: Sequence[Any] = ()) -> int:
        """Execute a mutating query. Returns rows affected."""
        self.all(name, params)
        return self._backend.rows_changed

    def insert(self, name: str, params: Sequence[Any] = ()) -> int:
        """Execute an INSERT. Returns the new row id."""
        self.all(name, params)
        return self._backend.last_insert_id

    # -- the audit log ------------------------------------------------------

    def audit(
        self,
        action: str,
        summary: str,
        *,
        actor_person_id: int | None = None,
        actor_role_snapshot: str | None = None,
        impersonator_person_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        school_id: int | None = None,
        changed_fields: Sequence[str] | None = None,
        value_detail: dict | None = None,
        ip_hash: str | None = None,
        ts: str | None = None,
    ) -> None:
        """Write one audit entry, inside this transaction.

        `summary` must be a complete human-readable sentence, rendered now:
        "Mark Michalak added 28 delegates to University High School." A future
        commissioner reads this log with no access to the source.

        `changed_fields` is field NAMES only, never values. This keeps PII out
        of the log and matches the requirement that it show "Bob updated their
        forms" rather than what Bob wrote. `value_detail` carries before/after
        values for payments ONLY, because money disputes are exactly when you
        need them.

        `ts` overrides the timestamp. Request paths never pass it -- it exists
        so the demo seed can lay down a log that spans the weeks it claims to,
        rather than months of registration all stamped one Tuesday.
        """
        if value_detail is not None and action != "payment.record":
            raise ValueError(
                "value_detail carries real values and is permitted on "
                "payment.record only -- everything else records field names"
            )
        self._backend.execute(
            get_query("audit.insert").sql,
            (
                ts or clock.now_iso(), actor_person_id, actor_role_snapshot,
                impersonator_person_id, action, entity_type, entity_id,
                school_id, summary,
                json.dumps(list(changed_fields)) if changed_fields else None,
                json.dumps(value_detail) if value_detail is not None else None,
                self.request_id, ip_hash,
            ),
        )
        self._audited = True

    def mark_silent(self, reason: str) -> None:
        """Declare that this transaction's writes need no audit entry.

        Only for the handful of actions in SILENT_ACTIONS -- session touches,
        rate-limit rows, counter recomputes. Anything else must audit.
        """
        if reason not in SILENT_ACTIONS:
            raise ValueError(
                f"{reason!r} is not a recognised silent action. If this really "
                f"changes nothing a human needs told about, add it to "
                f"SILENT_ACTIONS with a comment explaining why."
            )
        self._audited = True

    # -- lifecycle ----------------------------------------------------------

    def _check_before_commit(self) -> None:
        if self._mutated and not self._audited:
            raise AuditRequired(
                "this transaction ran "
                + ", ".join(sorted(set(self._mutated)))
                + " but wrote no audit entry. Every change to data is logged in "
                  "the same transaction as the change -- call tx.audit(...), or "
                  "tx.mark_silent(...) if it genuinely needs no entry."
            )


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

class Database:
    """A connection factory. Every transaction gets its own handle."""

    def __init__(self, *, path: str | None = None,
                 url: str | None = None, auth_token: str | None = None):
        self._path = path
        self._url = url
        self._auth_token = auth_token

    def _open(self) -> _Handle:
        if self._url is not None:
            return _open_remote(self._url, self._auth_token)
        assert self._path is not None, "a Database has either a path or a url"
        return _open_local(self._path)

    @contextmanager
    def tx(self, *, request_id: str | None = None) -> Iterator[Tx]:
        """A transaction. Commits on clean exit, rolls back on any exception.

        If the mutation rolls back, so does its audit entry -- which is exactly
        the point of writing them together.
        """
        handle = self._open()
        transaction = Tx(handle, request_id=request_id)
        handle.begin()
        try:
            yield transaction
            transaction._check_before_commit()
        except BaseException:
            handle.rollback()
            handle.close()
            raise
        handle.commit()
        handle.close()

    @contextmanager
    def read(self) -> Iterator[Tx]:
        """A read-only transaction. Refuses to commit a mutation.

        Used by every GET endpoint, so a query accidentally written as an UPDATE
        cannot slip through unlogged.
        """
        handle = self._open()
        transaction = Tx(handle)
        handle.begin()
        try:
            yield transaction
            if transaction._mutated:
                raise AuditRequired(
                    "a read-only transaction ran "
                    + ", ".join(sorted(set(transaction._mutated)))
                )
        except BaseException:
            handle.rollback()
            handle.close()
            raise
        handle.rollback()
        handle.close()

    def close(self) -> None:
        """Nothing to release.

        Connections are opened and closed per transaction, so a Database holds
        no resources of its own. This exists because callers reasonably expect
        it to.
        """
        return None


REMOTE_SCHEMES = ("libsql://", "https://", "http://", "wss://", "ws://")


def connect(url: str | None = None, *, auth_token: str | None = None) -> Database:
    """Open the database.

    With no arguments, reads TURSO_DATABASE_URL and TURSO_AUTH_TOKEN from the
    environment -- which on Modal come from Modal Secrets and are never in the
    repository. Falls back to a local dev.db so a fresh checkout runs with no
    configuration at all.
    """
    url = url or os.environ.get("TURSO_DATABASE_URL") or "dev.db"
    auth_token = auth_token or os.environ.get("TURSO_AUTH_TOKEN")

    # Checked here as well as at connection time, so a malformed secret is
    # reported by whatever runs first rather than by whichever code path
    # happens to open a transaction first.
    url = _clean_credential(url, "TURSO_DATABASE_URL") or "dev.db"
    auth_token = _clean_credential(auth_token, "TURSO_AUTH_TOKEN")

    if url.startswith(REMOTE_SCHEMES):
        return Database(url=url, auth_token=auth_token)

    if url.startswith("file:"):
        url = url[5:]
    if url == ":memory:":
        raise ValueError(
            ":memory: gives each connection its own empty database, and this "
            "opens one per transaction. Use a file -- tmp_path in tests."
        )
    return Database(path=url)
