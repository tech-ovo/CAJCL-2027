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
# Opening a SQLite connection costs microseconds, and the Turso client is HTTP,
# so a handle per transaction is cheap in both directions.

class _SqliteHandle:
    """One connection to a local file. Used by tests, dev, and every worker."""

    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, isolation_level=None)
        # Without this every foreign key in the schema is decorative. SQLite
        # defaults it OFF and the failure is completely silent.
        self._conn.execute("PRAGMA foreign_keys = ON")
        # WAL lets a reader -- an export, a Colab session -- run while the app
        # writes. Ignored harmlessly on :memory:.
        if path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
            # Rather than failing instantly when another writer holds the lock.
            self._conn.execute("PRAGMA busy_timeout = 5000")
        self._conn.row_factory = sqlite3.Row
        self.last_insert_id = None
        self.rows_changed = 0

    def execute(self, sql: str, params: Sequence[Any]) -> list[Row]:
        cursor = self._conn.execute(sql, tuple(params))
        rows = [Row(zip(r.keys(), tuple(r))) for r in cursor.fetchall()]
        self.last_insert_id = cursor.lastrowid
        self.rows_changed = cursor.rowcount
        return rows

    def begin(self) -> None:
        self._conn.execute("BEGIN IMMEDIATE")

    def commit(self) -> None:
        self._conn.execute("COMMIT")

    def rollback(self) -> None:
        self._conn.execute("ROLLBACK")

    def close(self) -> None:
        self._conn.close()


class _TursoHandle:
    """One libSQL transaction over the shared HTTP client."""

    def __init__(self, client):
        self._client = client
        self._tx = None
        self.last_insert_id = None
        self.rows_changed = 0

    def execute(self, sql: str, params: Sequence[Any]) -> list[Row]:
        target = self._tx if self._tx is not None else self._client
        result = target.execute(sql, list(params))
        self.last_insert_id = result.last_insert_rowid
        self.rows_changed = result.rows_affected
        return [Row(zip(result.columns, tuple(r))) for r in result.rows]

    def begin(self) -> None:
        self._tx = self._client.transaction()

    def commit(self) -> None:
        self._tx.commit()
        self._tx = None

    def rollback(self) -> None:
        if self._tx is not None:
            self._tx.rollback()
            self._tx = None

    def close(self) -> None:
        # The client is shared and outlives this handle; only the transaction
        # belonged to us, and commit/rollback has already disposed of it.
        self._tx = None


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
        rather than several months of registration all stamped one Tuesday.
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

    def __init__(self, *, path: str | None = None, client=None):
        self._path = path
        self._client = client

    def _open(self):
        if self._client is not None:
            return _TursoHandle(self._client)
        return _SqliteHandle(self._path)

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
        if self._client is not None:
            self._client.close()
            self._client = None


def connect(url: str | None = None, *, auth_token: str | None = None) -> Database:
    """Open the database.

    With no arguments, reads TURSO_DATABASE_URL and TURSO_AUTH_TOKEN from the
    environment -- which on Modal come from Modal Secrets and are never in the
    repository. Falls back to a local dev.db so a fresh checkout runs with no
    configuration at all.
    """
    url = url or os.environ.get("TURSO_DATABASE_URL") or "dev.db"
    auth_token = auth_token or os.environ.get("TURSO_AUTH_TOKEN")

    if url.startswith(("libsql://", "https://", "http://", "wss://", "ws://")):
        import libsql_client

        return Database(client=libsql_client.create_client_sync(url, auth_token=auth_token))

    if url.startswith("file:"):
        url = url[5:]
    if url == ":memory:":
        raise ValueError(
            ":memory: gives each connection its own empty database, and this "
            "opens one per transaction. Use a file -- tmp_path in tests."
        )
    return Database(path=url)
