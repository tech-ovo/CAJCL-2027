"""The connection pool, and the four things it must never break.

WHY THIS FILE EXISTS AT ALL. Reusing connections was attempted twice before and
reverted twice, both times for a reason that only shows up under threads: a
connection opened on one thread and used on another. `sqlite3` catches that and
the remote driver does not, so the third attempt puts the check in `_Handle`
where it covers both -- and these tests are what say the check works and that
nothing else moved.

What is being protected, in order of how much it would hurt:

  1. A transaction is still isolated. A read opened inside a write must not
     join it, commit it, or see its uncommitted rows.
  2. A rollback still rolls back, on a connection that will be reused.
  3. A connection is only ever used by the thread that opened it.
  4. A connection the far end has dropped is replaced, not handed out.

The speed is not tested here and cannot be, because against a local file there
is nothing to save: a handshake to Turso is what this exists to avoid, and a
file open costs microseconds. What is tested is that the reuse HAPPENS -- the
counters -- and that everything above still holds while it does.
"""

from __future__ import annotations

import threading

import pytest

from backend.lib import clock
from backend.lib import db as dbmod
from backend.lib.db import AuditRequired, connect

from .helpers import Fixture


@pytest.fixture
def fx(tmp_path):
    with Fixture(tmp_path) as f:
        yield f


# ---------------------------------------------------------------------------
# It reuses
# ---------------------------------------------------------------------------

def test_a_second_transaction_reuses_the_first_connection(fx):
    """The whole point. Two sequential reads, one connection.

    An authenticated request does exactly this: the guard reads the session,
    then the handler reads the data. That second open was a TLS handshake to
    Turso, and it is now nothing.
    """
    with fx.db.read() as tx:            # whatever the fixture left behind
        tx.one("schools.get", (fx.uni_id,))
    settled = fx.db.opens

    with fx.db.read() as tx:
        tx.one("schools.get", (fx.uni_id,))
    with fx.db.read() as tx:
        tx.one("schools.get", (fx.uni_id,))

    assert fx.db.opens == settled, "a warm pool opened another connection"
    assert fx.db.reuses >= 2


def test_the_pool_can_be_switched_off_without_touching_the_code(tmp_path):
    """`DB_POOL=0` in the Modal secret. The escape hatch has to work, because
    it is the thing that makes deploying this reversible in a minute."""
    with Fixture(tmp_path) as f:
        f.db.close()
        f.db._pool_enabled = False
        opens, reuses = f.db.opens, f.db.reuses
        for _ in range(3):
            with f.db.read() as tx:
                tx.one("schools.get", (f.uni_id,))
        assert f.db.opens == opens + 3
        assert f.db.reuses == reuses, "the pool was used with the pool off"


def test_the_environment_variable_is_read(tmp_path):
    """Belt and braces on the spelling, because the escape hatch is worthless
    if `DB_POOL=0` is not what turns it off. Unset means on: a fresh checkout
    with no configuration gets the fast path."""
    assert dbmod._pool_setting("0") is False
    assert dbmod._pool_setting("false") is False
    assert dbmod._pool_setting("off") is False
    assert dbmod._pool_setting(" 0 ") is False
    assert dbmod._pool_setting(None) is True
    assert dbmod._pool_setting("1") is True

    # And a Database with nothing said about it follows that setting.
    assert dbmod.Database(path=str(tmp_path / "x.db"))._pool_enabled \
        is dbmod.POOL_ENABLED


# ---------------------------------------------------------------------------
# It does not hand the same connection to two transactions
# ---------------------------------------------------------------------------
#
# THESE GO THROUGH THE POOL RATHER THAN THROUGH TWO REAL TRANSACTIONS, and the
# reason is worth writing down. Against a local file, `BEGIN IMMEDIATE` takes
# the write lock, so a second transaction opened while the first is still open
# waits for it and then fails -- pool or no pool, before this change or after.
# Two overlapping transactions is a SQLite locking question and is tested as
# one in test_db_drivers.py.
#
# What is a pool question is whether the pool could ever hand the same
# connection to both, which is what would turn an ordinary lock wait into two
# transactions silently sharing one -- an inner exit committing an outer's
# half-finished work. Checked directly, at the level where it would happen.

def test_a_checked_out_connection_is_not_also_idle(fx):
    """The property the whole thing rests on. While a transaction holds a
    connection it is out of the pool, so nothing else can be given it."""
    with fx.db.read() as tx:
        assert tx._backend not in fx.db._idle()


def test_a_checkout_takes_the_connection_out_of_the_pool(fx):
    """Taken, not borrowed. If checkout only PEEKED, the next transaction
    would be handed the same connection and its BEGIN would land inside a
    transaction that is already open -- and its exit would commit work that
    belongs to somebody else.
    """
    with fx.db.read():
        assert fx.db._idle() == [], "a connection in use was left in the pool"


def test_a_released_connection_goes_back(fx):
    """The other half of the same property, and the half that makes it fast."""
    handle = fx.db._checkout()
    handle.rollback()
    fx.db._release(handle)
    assert handle in fx.db._idle()


def test_only_so_many_are_kept(fx):
    """Two per thread, because two is what a request uses. A burst must not
    leave a pile of idle connections behind.

    `_open` rather than `_checkout`: this is about what the pool keeps, and
    four open transactions against one local file is a write-lock question
    that has nothing to do with it.
    """
    fx.db.close()
    for handle in [fx.db._open() for _ in range(4)]:
        fx.db._release(handle)

    assert len(fx.db._idle()) == dbmod.POOL_PER_THREAD


def test_a_rolled_back_transaction_leaves_a_clean_connection_behind(fx):
    """A connection goes back into the pool after a failure, so the next
    transaction on it must not inherit anything: not the rolled-back rows, and
    not an open transaction."""
    with pytest.raises(AuditRequired):
        with fx.db.tx() as tx:
            tx.run("schools.set_note", ("never committed", clock.now_iso(),
                                        fx.uni_id))

    with fx.db.read() as tx:
        assert tx.one("schools.get", (fx.uni_id,))["notes"] != "never committed"

    # And the connection still works for a write, which it would not if a
    # transaction were still open on it.
    with fx.db.tx() as tx:
        tx.run("schools.set_note", ("committed fine", clock.now_iso(),
                                    fx.uni_id))
        tx.audit("school.update", "Wrote a note after a rollback.")
    with fx.db.read() as tx:
        assert tx.one("schools.get", (fx.uni_id,))["notes"] == "committed fine"


def test_an_application_error_does_not_throw_the_connection_away(fx):
    """A validation error inside a `with db.tx()` is the ordinary way an
    endpoint refuses something. Closing the connection every time one is raised
    would mean the busiest paths -- the ones that check things -- never reuse
    anything."""
    with fx.db.read() as tx:
        tx.one("schools.get", (fx.uni_id,))
    kept = fx.db.discards

    with pytest.raises(ValueError):
        with fx.db.read() as tx:
            tx.one("schools.get", (fx.uni_id,))
            raise ValueError("the delegate typed something impossible")

    assert fx.db.discards == kept, "a refused request closed its connection"


# ---------------------------------------------------------------------------
# One connection, one thread
# ---------------------------------------------------------------------------

def test_using_a_connection_from_another_thread_is_refused_by_name(fx):
    """The mistake that sank both earlier attempts, and the reason the driver's
    own check could be turned off: this one covers the remote driver too, and
    says which thread rather than only that something is wrong."""
    with fx.db.read() as tx:
        handle = tx._backend
        failure = {}

        def from_elsewhere():
            try:
                handle.execute("SELECT 1", ())
            except Exception as error:
                failure["error"] = error

        thread = threading.Thread(target=from_elsewhere)
        thread.start()
        thread.join()

    assert isinstance(failure.get("error"), RuntimeError)
    assert "opened on thread" in str(failure["error"])
    assert "Open a transaction where you use it" in str(failure["error"])


def test_two_threads_never_hold_the_same_connection(fx):
    """The pool is thread-local, so this is true by construction -- which is
    exactly the kind of claim that stops being true during a later edit."""
    seen: list[int] = []
    lock = threading.Lock()

    def work():
        for _ in range(3):
            with fx.db.read() as tx:
                with lock:
                    seen.append(id(tx._backend))

    threads = [threading.Thread(target=work) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with fx.db._live_lock:
        owners = {handle.thread_id for handle in fx.db._live}
    assert len(owners) == len({h.thread_id for h in fx.db._live})
    assert seen, "the threads did no work"


def test_close_leaves_another_thread_s_connections_alone(tmp_path):
    """The rule with no exception, and it was learned the hard way.

    An earlier version closed every connection this Database had open, on any
    thread, so that one idle on a retired threadpool worker could be released.
    Closing a connection that another LIVE thread still holds is a use from the
    wrong thread, and `sqlite3` with `check_same_thread=False` does not refuse
    it -- it segfaults. It showed up as a test run that hung, and once as
    `Windows fatal exception: access violation`.

    A thread that has ended has already closed what it was holding, which is
    the test below, so nothing is left needing this.
    """
    opened = threading.Event()
    finish = threading.Event()

    with Fixture(tmp_path) as f:
        def work():
            with f.db.read() as tx:
                tx.one("schools.get", (f.uni_id,))
            opened.set()
            finish.wait(5)

        thread = threading.Thread(target=work)
        thread.start()
        opened.wait(5)

        f.db.close()

        with f.db._live_lock:
            still_open = [h.thread_id for h in f.db._live]
        assert thread.ident in still_open, (
            "close() reached into another live thread's pool, which is the "
            "cross-thread use that crashes the interpreter")

        finish.set()
        thread.join()


def test_a_thread_that_ends_closes_what_it_was_holding(fx):
    """The leak both earlier attempts died of, in the form it actually takes.

    anyio retires a threadpool worker after ten seconds idle, which on a quiet
    evening is after almost every request. Whatever that thread was holding
    becomes unreachable at that moment -- and left to the garbage collector it
    is closed eventually, untidily, and with a ResourceWarning. The finalizer
    on the thread's idle list closes it as the thread goes.
    """
    import gc

    def work():
        with fx.db.read() as tx:
            tx.one("schools.get", (fx.uni_id,))

    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    gc.collect()

    with fx.db._live_lock:
        owners = {handle.thread_id for handle in fx.db._live}
    assert thread.ident not in owners, (
        "a connection outlived the thread that owned it, which is the leak "
        "this design exists to avoid")


# ---------------------------------------------------------------------------
# A connection the far end dropped
# ---------------------------------------------------------------------------

def test_a_stale_connection_is_replaced_without_the_caller_noticing(fx):
    """Turso may close an idle connection at any time, and the first thing to
    find out is the BEGIN. Nothing has run inside a transaction at that point,
    so opening a fresh one and starting again is safe -- and is the difference
    between a pool and a source of intermittent 500s.
    """
    with fx.db.read() as tx:
        tx.one("schools.get", (fx.uni_id,))

    idle = fx.db._idle()[-1]
    original = idle.begin

    def dropped():
        raise ConnectionError("stream closed")

    idle.begin = dropped
    discards = fx.db.discards

    with fx.db.read() as tx:
        row = tx.one("schools.get", (fx.uni_id,))

    assert row["id"] == fx.uni_id
    assert fx.db.discards == discards + 1, "the dead connection was kept"
    assert original is not None


def test_a_connection_older_than_the_cap_is_not_handed_out(fx, monkeypatch):
    """A connection nobody has touched for five minutes is more likely dropped
    than alive, and finding out at BEGIN costs the round trip that opening a
    new one would have spent anyway."""
    with fx.db.read() as tx:
        tx.one("schools.get", (fx.uni_id,))

    fx.db._idle()[-1].opened_at -= dbmod.POOL_MAX_AGE + 1
    opens = fx.db.opens

    with fx.db.read() as tx:
        tx.one("schools.get", (fx.uni_id,))

    assert fx.db.opens == opens + 1


# ---------------------------------------------------------------------------
# What an operator sees
# ---------------------------------------------------------------------------

def test_the_counters_say_whether_it_is_working(fx):
    """Settings -> Operations shows these. `reuses` climbing while `opens`
    stays flat is the pool working; `opens` climbing in step with requests
    means it is not."""
    for _ in range(5):
        with fx.db.read() as tx:
            tx.one("schools.get", (fx.uni_id,))

    stats = fx.db.stats()
    assert stats["pool"] is True
    assert stats["reuses"] >= 4
    assert 0 < stats["reuse_rate"] <= 1
    assert stats["idle_on_this_thread"] <= dbmod.POOL_PER_THREAD


def test_a_database_with_no_path_and_no_url_still_refuses(tmp_path):
    """The invariant that predates the pool, checked because `_open` was
    rearranged around it."""
    from backend.lib.db import Database

    with pytest.raises(ValueError, match="either a path or a url"):
        with Database().read():
            pass


def test_connect_still_refuses_an_in_memory_database():
    """Each connection would get its own empty database, and the pool makes
    that worse rather than better: which empty database you get would depend on
    what happened to be idle."""
    with pytest.raises(ValueError, match=":memory:"):
        connect(":memory:")


# ---------------------------------------------------------------------------
# What a request actually costs
# ---------------------------------------------------------------------------

def test_an_authenticated_request_opens_one_connection_not_two(fx, monkeypatch):
    """THE MEASUREMENT THIS WHOLE THING EXISTS FOR.

    An authenticated request reads twice: the guard reads the session to find
    out who is asking, and the handler reads the data. Against Turso each of
    those was a TLS handshake, and the browser saw about 350 ms per connection
    -- so the second one was most of the wait on every page a sponsor opened.

    Both reads happen on the same threadpool worker, so the second finds the
    first's connection idle and takes it. Asserted against the API rather than
    against the pool, because "one connection per request" is a property of how
    FastAPI dispatches, not only of the pool: if a future version runs guards
    somewhere else, this is what notices.
    """
    from fastapi.testclient import TestClient

    from backend import api

    monkeypatch.setattr(api, "_db", fx.db)
    headers = {"Authorization": f"Bearer {fx.sign_in('uni_sponsor')}"}

    with TestClient(api.app) as client:
        client.get("/sponsor/roster", headers=headers)  # warm the worker
        opens = fx.db.opens

        response = client.get("/sponsor/roster", headers=headers)
        assert response.status_code == 200

    assert fx.db.opens - opens <= 1, (
        f"a warm request opened {fx.db.opens - opens} connections; the guard "
        f"and the handler should be sharing one")
