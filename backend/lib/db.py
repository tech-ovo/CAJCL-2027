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
import random
import re
import sqlite3
import threading
import time
import weakref
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


# ---------------------------------------------------------------------------
# Waiting for the write lock
# ---------------------------------------------------------------------------
#
# libSQL, like SQLite, has ONE writer. Two requests that both want to write --
# a sponsor ticking a paper form while a delegate saves an activity sheet --
# and the loser gets SQLITE_BUSY. Left alone that surfaces as a 500 to somebody
# who did nothing wrong and whose obvious next move is to click again.
#
# A busy error means the statement DID NOT RUN. Nothing was half-applied, so
# running it again is safe -- which is what makes retrying at this level
# correct rather than merely convenient. Anything else is re-raised untouched.
#
# Five attempts over roughly a second and a half. Long enough to ride out the
# contention a fifty-chapter convention actually produces, short enough that a
# genuinely stuck lock still fails while somebody is looking at the screen
# rather than after they have given up.
BUSY_ATTEMPTS = 5
BUSY_BASE_DELAY = 0.05      # seconds; doubles each time, plus jitter


# ---------------------------------------------------------------------------
# The connection pool
# ---------------------------------------------------------------------------
#
# TWO PER THREAD, because two is what a request uses: the guard reads the
# session, then the handler reads the data, and nothing nests deeper than that.
# A third is opened on demand and closed again rather than kept.
#
# FIVE MINUTES, because a connection nobody has used for longer than that may
# well have been dropped at the far end, and finding that out at BEGIN costs a
# round trip that opening a fresh one would have spent anyway.
POOL_PER_THREAD = 2
POOL_MAX_AGE = 300.0        # seconds

# The escape hatch. `DB_POOL=0` in the Modal secret restores connection-per
# transaction without a deploy. Read once, at import, so it cannot change under
# a running container mid-request.


def _pool_setting(value: str | None) -> bool:
    """Is the pool on? Anything that reads as "no" turns it off.

    Written out rather than inlined so it can be tested without reloading this
    module, which would replace every class in it and leave anything holding a
    reference to the old ones -- `AuditRequired`, most confusingly -- comparing
    against a class that is no longer the one being raised.
    """
    return (value or "1").strip().lower() not in ("0", "false", "no", "off", "")


POOL_ENABLED = _pool_setting(os.environ.get("DB_POOL"))

_BUSY_MARKERS = ("database is locked", "database is busy",
                 "sqlite_busy", "sqlite_locked")


def _is_busy(error: BaseException) -> bool:
    """Is this the single-writer lock, or a real failure?

    Matched on the message because the two drivers raise different types for
    it -- sqlite3.OperationalError locally, a plain ValueError wrapping Hrana's
    text remotely -- and neither exposes the SQLite result code.
    """
    text = str(error).lower()
    return any(marker in text for marker in _BUSY_MARKERS)


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
        # For the pool: when it was opened, and which thread may touch it.
        # `sqlite3` refuses cross-thread use outright and the remote driver is
        # not documented to allow it, so the pool guarantees by construction
        # that a connection is only ever handed back to the thread that opened
        # it. This field is what makes that assertable rather than hoped for.
        self.opened_at = time.monotonic()
        self.thread_id = threading.get_ident()

    def execute(self, sql: str, params: Sequence[Any]) -> list[Row]:
        self._check_thread()
        cursor = self._run_with_retry(sql, tuple(params))

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

    def _run_with_retry(self, sql: str, params: tuple):
        """Execute, waiting out the write lock rather than failing on it.

        See BUSY_ATTEMPTS above for why retrying here is safe: a busy error
        means the statement never ran.
        """
        for attempt in range(BUSY_ATTEMPTS):
            try:
                return self._conn.execute(sql, params)
            except Exception as error:
                last = attempt == BUSY_ATTEMPTS - 1
                if last or not _is_busy(error):
                    raise
                # Jittered, so two containers that collided do not wake up
                # together and collide again.
                delay = BUSY_BASE_DELAY * (2 ** attempt)
                time.sleep(delay + random.uniform(0, delay))
        raise AssertionError("unreachable")

    def _check_thread(self) -> None:
        """One connection, one thread. Enforced here rather than by the driver.

        `sqlite3` used to enforce this itself and is now told not to, for the
        reason given in `_open_local`; the remote driver never did. So it is
        checked in the one place both go through, and it says which thread
        rather than only that something is wrong.
        """
        if threading.get_ident() != self.thread_id:
            raise RuntimeError(
                f"this connection was opened on thread {self.thread_id} and is "
                f"being used from thread {threading.get_ident()}. The pool in "
                f"db.py hands a connection back only to the thread that opened "
                f"it, so this means something is holding a Tx across a thread "
                f"boundary -- middleware, or a handler that hands a Tx to a "
                f"worker. Open a transaction where you use it."
            )

    def begin(self) -> None:
        self._check_thread()
        self._run_with_retry(self._begin_sql, ())

    def commit(self) -> None:
        self._conn.execute("COMMIT")

    def rollback(self) -> None:
        self._conn.execute("ROLLBACK")

    def close(self) -> None:
        self._conn.close()


def _open_local(path: str) -> _Handle:
    # `check_same_thread=False` needs justifying, because it switches off the
    # exact guard that caught two earlier attempts at pooling.
    #
    # What it actually guards is "this connection is used by one thread at a
    # time", and the pool now guarantees that by construction: a connection is
    # only ever handed to the thread it was opened on, and only ever to one
    # transaction at a time. What the driver's version ALSO forbids is closing
    # a connection from another thread, which left `Database.close()` unable to
    # release anything the threadpool was holding -- connections nothing could
    # close, which is precisely how the second attempt failed.
    #
    # The check is not gone. `_Handle.execute` makes it itself, below, where it
    # covers the remote driver too -- which never had one.
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
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

    # ONLY foreign_keys. Turso allows a short list of pragmas and rejects the
    # rest outright:
    #
    #     SQL not allowed statement: PRAGMA busy_timeout = 5000
    #
    # `busy_timeout` was added here to match the local handle, on the reasoning
    # that contention is a hosted database's problem rather than a laptop's.
    # That reasoning was right and the mechanism was wrong: this is not a file
    # being opened, it is a statement sent over the wire to a server that
    # decides what it will run. It failed at CONNECTION time, which took the
    # whole API down rather than one query.
    #
    # The wait is done in Python instead, in _run_with_retry above, which does
    # not need the server's permission.
    conn.execute("PRAGMA foreign_keys = ON")

    # Plain BEGIN, not IMMEDIATE: a hosted database has a single writer already,
    # and IMMEDIATE is a local-file locking concern that remote need not honour.
    return _Handle(conn, begin_sql="BEGIN")


class _ThreadIdle:
    """The idle connections belonging to one thread, and a way to know when
    that thread is gone.

    WHY THIS IS NOT JUST A LIST. anyio retires a threadpool worker after ten
    seconds idle, which on a quiet evening is after almost every request. The
    connections that worker was holding become unreachable at that moment, and
    left to the garbage collector they are closed eventually, untidily, and
    with a ResourceWarning -- a socket to Turso held open for no reason and
    closed by nobody in particular.

    So the list lives on an object with a finalizer. When the thread ends, its
    thread-local storage is released, this object dies, and the finalizer
    closes what it was holding -- deterministically, under CPython, at the
    moment the thread goes away. The finalizer is given the LIST rather than
    this object, because a callback holding the object would keep it alive and
    it would never fire at all.
    """

    __slots__ = ("idle", "__weakref__")

    def __init__(self) -> None:
        self.idle: list[_Handle] = []


def _close_abandoned(handles: list) -> None:
    """Close the connections a dead thread was holding."""
    while handles:
        try:
            handles.pop().close()
        except Exception:
            # The thread that owned it is gone; there is nobody to tell and
            # nothing to do.
            pass


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
        so the seed can lay down a log that spans the weeks it claims to,
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
    """A connection factory, with a small pool in front of it.

    WHY THERE IS A POOL AT ALL, since a connection per transaction is simpler
    and is what this did first:

        Opening a connection to Turso costs a TLS handshake. Measured from the
        browser: a request that opens one takes about 350 ms, and one that
        opened three took about three seconds. An authenticated request opens
        two as a matter of course -- the guard reads the session, then the
        handler reads the data -- so the handshake, not the query, was most of
        what a sponsor was waiting for.

    WHAT IS POOLED, PRECISELY:

        Idle connections, per thread, never shared between threads. A
        transaction checks one out and it is gone from the pool until it is
        released, so the nesting hazard that a handle per transaction existed
        to avoid is still avoided: a read opened inside a write gets a
        DIFFERENT connection, exactly as before, because the outer one is not
        idle.

        Handlers run on the threadpool and the pool is thread-local, so a
        connection is only ever used by the thread that opened it. Two earlier
        attempts at this failed by ignoring that: a connection opened in
        middleware, which runs on the event loop, is then used cross-thread by
        the handler, and `sqlite3` refuses outright.

    HOW TO TURN IT OFF, without a deploy:

        Set `DB_POOL=0` in the Modal secret and restart. Every transaction then
        opens and closes its own connection, which is what this did for months
        and is known to work. If production behaviour looks wrong and the pool
        is a suspect, turn it off first and diagnose second.
    """

    def __init__(self, *, path: str | None = None,
                 url: str | None = None, auth_token: str | None = None,
                 pool: bool | None = None):
        self._path = path
        self._url = url
        self._auth_token = auth_token
        self._pool_enabled = POOL_ENABLED if pool is None else pool
        self._local = threading.local()
        # Every connection currently open, on any thread. Only close() reads
        # it, and only to shut everything down: without it, a connection idle
        # on a threadpool thread is unreachable from anywhere.
        #
        # WEAK, AND THAT IS THE WHOLE POINT. anyio retires a threadpool worker
        # after ten seconds idle, which on a quiet evening is after almost
        # every request. The connection it was holding becomes unreachable at
        # that moment, and a strong reference here would keep it -- and its
        # socket -- alive for the life of the container while nothing could
        # ever use it again. That is the leak both earlier attempts died of,
        # and a set that does not own its contents is what fixes it: the
        # handle is collected with the thread, and the driver closes the
        # connection as it goes.
        self._live: weakref.WeakSet[_Handle] = weakref.WeakSet()
        self._live_lock = threading.Lock()
        # Plain ints, incremented without a lock. They are counters for a human
        # reading Settings -> Operations, not a control input, and a lost
        # increment under contention costs nothing worth a lock on every query.
        self.opens = 0
        self.reuses = 0
        self.discards = 0

    # -- the pool -----------------------------------------------------------

    def _idle(self) -> list[_Handle]:
        holder = getattr(self._local, "holder", None)
        if holder is None:
            holder = self._local.holder = _ThreadIdle()
            # Fires when this thread ends and its local storage is released.
            weakref.finalize(holder, _close_abandoned, holder.idle)
        return holder.idle

    def _open(self) -> _Handle:
        if self._url is not None:
            handle = _open_remote(self._url, self._auth_token)
        elif self._path is None:
            # An `assert` here vanishes under `python -O`, and this is a real
            # invariant rather than a debugging aid: a Database with neither a
            # path nor a url would otherwise fail somewhere less obvious.
            raise ValueError("a Database has either a path or a url")
        else:
            handle = _open_local(self._path)

        self.opens += 1
        with self._live_lock:
            self._live.add(handle)
        return handle

    def _checkout(self) -> _Handle:
        """An open connection with a transaction started on it.

        A pooled one if this thread has a usable one, otherwise a new one. The
        BEGIN happens here rather than in the caller because it is the first
        thing to touch the wire, and therefore the first thing to discover that
        a connection the server quietly dropped is no longer a connection.
        """
        while self._pool_enabled and self._idle():
            handle = self._idle().pop()
            if time.monotonic() - handle.opened_at > POOL_MAX_AGE:
                # Old enough that the far end may well have dropped it. Cheaper
                # to open a new one than to find out mid-request.
                self._discard(handle)
                continue
            try:
                handle.begin()
            except Exception:
                # Stale. Nothing has run inside a transaction yet, so there is
                # no half-applied work and starting over is safe.
                self._discard(handle)
                continue
            self.reuses += 1
            return handle

        handle = self._open()
        handle.begin()
        return handle

    def _release(self, handle: _Handle) -> None:
        """Put a finished connection back, or close it.

        Called only after a commit or a rollback, so what goes back has no
        transaction on it. Anything else is closed rather than reasoned about.
        """
        if not self._pool_enabled or len(self._idle()) >= POOL_PER_THREAD:
            self._discard(handle)
            return
        self._idle().append(handle)

    def _discard(self, handle: _Handle) -> None:
        self.discards += 1
        with self._live_lock:
            self._live.discard(handle)
        try:
            handle.close()
        except Exception:
            # A connection being closed because it is already broken is not
            # news, and there is nothing to be done about it either way.
            pass

    def stats(self) -> dict:
        """Connection counters, for Settings -> Operations.

        `reuses` climbing while `opens` stays flat is the pool working. `opens`
        climbing in step with requests means it is not, and the first thing to
        check is whether `DB_POOL=0` is set.
        """
        total = self.opens + self.reuses
        return {"pool": self._pool_enabled, "opens": self.opens,
                "reuses": self.reuses, "discards": self.discards,
                "reuse_rate": round(self.reuses / total, 3) if total else None,
                "idle_on_this_thread": len(self._idle())}

    @contextmanager
    def tx(self, *, request_id: str | None = None) -> Iterator[Tx]:
        """A transaction. Commits on clean exit, rolls back on any exception.

        If the mutation rolls back, so does its audit entry -- which is exactly
        the point of writing them together.
        """
        handle = self._checkout()
        transaction = Tx(handle, request_id=request_id)
        try:
            yield transaction
            transaction._check_before_commit()
        except BaseException:
            self._unwind(handle)
            raise
        try:
            handle.commit()
        except BaseException:
            self._discard(handle)
            raise
        self._release(handle)

    @contextmanager
    def read(self) -> Iterator[Tx]:
        """A read-only transaction. Refuses to commit a mutation.

        Used by every GET endpoint, so a query accidentally written as an UPDATE
        cannot slip through unlogged.
        """
        handle = self._checkout()
        transaction = Tx(handle)
        try:
            yield transaction
            if transaction._mutated:
                raise AuditRequired(
                    "a read-only transaction ran "
                    + ", ".join(sorted(set(transaction._mutated)))
                )
        except BaseException:
            self._unwind(handle)
            raise
        try:
            handle.rollback()
        except BaseException:
            self._discard(handle)
            raise
        self._release(handle)

    def _unwind(self, handle: _Handle) -> None:
        """Roll a failed transaction back, and decide whether to keep the
        connection.

        MOST FAILURES ARE THE APPLICATION'S, not the connection's: a validation
        error raised inside a `with db.tx()` block is the ordinary way an
        endpoint refuses something, and the connection under it is perfectly
        healthy. So: roll back, and if the rollback works, the connection goes
        back in the pool. A rollback that itself fails is the only reliable
        signal that the connection is the problem, and that one is closed.
        """
        try:
            handle.rollback()
        except BaseException:
            self._discard(handle)
            return
        self._release(handle)

    def close(self) -> None:
        """Close every connection this Database has open, on any thread.

        FOR SHUTDOWN, NOT FOR HOUSEKEEPING. A connection in the middle of a
        transaction on another thread is closed along with the rest, so calling
        this while requests are in flight breaks them. Nothing in the request
        path calls it; a Modal container is torn down whole and the operating
        system closes the sockets.

        It matters in the test suite. Handlers run on threadpool threads, and a
        connection left idle on one is reachable from nowhere else -- which on
        Windows keeps a temporary file undeletable, and in pytest surfaces as
        an unraisable ResourceWarning from whichever test happens to trigger
        the collection.
        """
        with self._live_lock:
            handles, self._live = list(self._live), weakref.WeakSet()
        for handle in handles:
            self.discards += 1
            try:
                handle.close()
            except Exception:
                pass
        del self._idle()[:]


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
