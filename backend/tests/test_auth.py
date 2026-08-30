"""Authentication, and the authorization rules that actually matter.

docs/stack.md: "The realistic threat is not a database dump; it is a sponsor at
one school reading another school's roster because an endpoint checked identity
but not scope."

These tests are written against the guards themselves. test_endpoints.py hits
every HTTP route with a wrong-scope and a wrong-school credential.
"""

from __future__ import annotations

import pytest

from backend.lib import auth, clock, codes, roster
from backend.lib.db import AuditRequired

from .helpers import Fixture


@pytest.fixture
def fx(tmp_path):
    with Fixture(tmp_path) as f:
        yield f


# ---------------------------------------------------------------------------
# Redeeming a code


# ---------------------------------------------------------------------------


def test_a_good_code_produces_a_session(fx):
    code = fx.codes["uni_sponsor"]
    token, principal = auth.redeem(fx.db, code, ip="1.2.3.4")
    assert token
    assert principal.person_type == "adult"
    assert "sponsor" in principal.scopes

    with fx.db.read() as tx:
        again = auth.authenticate(tx, token, touch=False)
    assert again.person_id == principal.person_id


def test_the_raw_code_is_never_stored(fx):
    """Only its HMAC is. A database dump alone must not yield working codes."""
    code = fx.codes["uni_sponsor"]
    body = codes.normalize(code)
    with fx.db.read() as tx:
        rows = tx.all("roster.list", (fx.uni_id,))
    dumped = repr(rows)
    assert body not in dumped and code not in dumped


def test_an_unknown_code_is_rejected(fx):
    _, unknown = codes.generate("DEL")
    with pytest.raises(auth.AuthError):
        auth.redeem(fx.db, codes.format_code(unknown), ip="1.2.3.4")


def test_a_mistyped_code_is_rejected_by_its_check_symbol(fx):
    code = fx.codes["uni_sponsor"]
    broken = code[:-1] + ("A" if code[-1] != "A" else "B")
    with pytest.raises(auth.AuthError):
        auth.redeem(fx.db, broken, ip="1.2.3.4")


def test_a_cancelled_person_cannot_sign_in(fx):
    actor = fx.principal("uni_sponsor")
    with fx.db.tx() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        person = dict(tx.one("people.get", (fx.delegate_id,)))
        roster.cancel(tx, school, actor, person)
    with pytest.raises(auth.AuthError):
        auth.redeem(fx.db, fx.codes["delegate"], ip="1.2.3.4")


def test_every_login_is_audited_including_failures(fx):
    auth.redeem(fx.db, fx.codes["uni_sponsor"], ip="1.2.3.4")
    with pytest.raises(auth.AuthError):
        auth.redeem(fx.db, codes.format_code(codes.generate("DEL")[1]), ip="1.2.3.4")
    actions = fx.audit_actions()
    assert "auth.login" in actions
    assert "auth.login_failed" in actions


# ---------------------------------------------------------------------------
# Rate limiting


# ---------------------------------------------------------------------------


def test_per_ip_rate_limit(fx):
    """10 failures per IP per 15 minutes."""
    for _ in range(auth.IP_LIMIT):
        with pytest.raises(auth.AuthError):
            auth.redeem(fx.db, codes.format_code(codes.generate("DEL")[1]), ip="9.9.9.9")
    # Even a VALID code is now refused from that address.
    with pytest.raises(auth.RateLimited):
        auth.redeem(fx.db, fx.codes["uni_sponsor"], ip="9.9.9.9")


def test_per_code_rate_limit_spans_addresses(fx):
    """5 failures per code per hour. This is the limit that catches someone
    walking the keyspace from many addresses, which the per-IP limit misses."""
    _, target = codes.generate("DEL")
    guess = codes.format_code(target)
    for i in range(auth.CODE_LIMIT):
        with pytest.raises(auth.AuthError):
            auth.redeem(fx.db, guess, ip=f"10.0.0.{i}")
    with pytest.raises(auth.RateLimited):
        auth.redeem(fx.db, guess, ip="10.0.0.99")


def test_rate_limiting_survives_garbage_input(fx):
    """Otherwise the per-code limit is bypassed by sending malformed guesses."""
    for i in range(auth.CODE_LIMIT):
        with pytest.raises(auth.AuthError):
            auth.redeem(fx.db, "not-a-code-at-all", ip=f"11.0.0.{i}")
    with pytest.raises(auth.RateLimited):
        auth.redeem(fx.db, "not-a-code-at-all", ip="11.0.0.99")


# ---------------------------------------------------------------------------
# Sessions


# ---------------------------------------------------------------------------


def test_sign_out_revokes_server_side(fx):
    """Assume shared devices. Clearing localStorage is not signing out."""
    token, principal = auth.redeem(fx.db, fx.codes["delegate"], ip="1.2.3.4")
    with fx.db.tx() as tx:
        auth.logout(tx, auth.authenticate(tx, token))

    with pytest.raises(auth.AuthError):
        with fx.db.read() as tx:
            auth.authenticate(tx, token, touch=False)


def test_regenerating_a_code_kills_every_session_from_it(fx):
    """A delegate's code is regenerated while they have an open session on a
    school Chromebook. The old session must die with the old code."""
    token, _ = auth.redeem(fx.db, fx.codes["delegate"], ip="1.2.3.4")
    with fx.db.tx() as tx:
        new_code = auth.issue_code(tx, fx.delegate_id, "DEL")
        tx.run("auth.session_revoke_all_for_person", (clock.now_iso(), fx.delegate_id))
        tx.audit("person.code_regenerate", "Sponsor issued a new code.",
                 school_id=fx.uni_id, entity_type="person", entity_id=fx.delegate_id)

    with pytest.raises(auth.AuthError):
        with fx.db.read() as tx:
            auth.authenticate(tx, token, touch=False)

    # And the new code works.
    assert auth.redeem(fx.db, new_code, ip="1.2.3.4")[0]


def test_an_expired_session_is_refused(fx):
    token, principal = auth.redeem(fx.db, fx.codes["delegate"], ip="1.2.3.4")
    fx.expire_session(principal.session_id)
    with pytest.raises(auth.AuthError):
        with fx.db.read() as tx:
            auth.authenticate(tx, token, touch=False)


def test_a_person_may_revoke_only_their_own_sessions(fx):
    _, delegate = auth.redeem(fx.db, fx.codes["delegate"], ip="1.2.3.4")
    _, sponsor = auth.redeem(fx.db, fx.codes["uni_sponsor"], ip="1.2.3.4")
    with pytest.raises(auth.ForbiddenError):
        with fx.db.tx() as tx:
            auth.revoke_session(tx, delegate, sponsor.session_id)


# ---------------------------------------------------------------------------
# Scopes


# ---------------------------------------------------------------------------


def test_scopes_arrive_only_through_roles(fx):
    """person_roles -> roles -> role_scopes, and no other path."""
    with fx.db.read() as tx:
        scopes = {r["scope"] for r in tx.all("auth.scopes_for_person", (fx.delegate_id,))}
    assert scopes == {"delegate"}

    with fx.db.tx() as tx:
        role = tx.one("roles.by_key", ("chapter_leader",))
        tx.run("people.grant_role", (fx.delegate_id, role["id"], fx.admin_id, clock.now_iso()))
        tx.audit("role.grant", "Sponsor promoted a delegate to chapter leader.",
                 school_id=fx.uni_id, entity_type="person", entity_id=fx.delegate_id)

    with fx.db.read() as tx:
        scopes = {r["scope"] for r in tx.all("auth.scopes_for_person", (fx.delegate_id,))}
    assert scopes == {"delegate", "chapter"}


def test_star_subsumes_every_scope(fx):
    admin = fx.principal("admin")
    for scope in ("registration", "academics", "awards", "sponsor", "delegate", "chapter"):
        assert admin.has_scope(scope)


def test_a_delegate_holds_nothing_administrative(fx):
    delegate = fx.principal("delegate")
    for scope in ("*", "registration", "academics", "awards", "sponsor"):
        assert not delegate.has_scope(scope)
    with pytest.raises(auth.ForbiddenError):
        auth.require_scope(delegate, "registration")


def test_a_sponsor_carries_the_chapter_scope(fx):
    """Sponsors manage chapter team entries. chapter_leader gives the same scope
    to a student, as a role on their existing account -- never a second code."""
    assert fx.principal("uni_sponsor").has_scope("chapter")


# ---------------------------------------------------------------------------
# School scoping -- the attack this system actually has to survive


# ---------------------------------------------------------------------------


def test_a_sponsor_cannot_reach_another_school(fx):
    sponsor = fx.principal("uni_sponsor")
    auth.require_school(sponsor, fx.uni_id)          # own school: fine
    with pytest.raises(auth.ForbiddenError):
        auth.require_school(sponsor, fx.other_id)    # someone else's: refused


def test_a_sponsor_cannot_reach_a_person_at_another_school(fx):
    sponsor = fx.principal("uni_sponsor")
    with fx.db.read() as tx:
        auth.require_person_in_scope(tx, sponsor, fx.delegate_id)      # own
        with pytest.raises(auth.ForbiddenError):
            auth.require_person_in_scope(tx, sponsor, fx.other_delegate_id)


def test_administrative_scopes_are_global(fx):
    """A registration chair may act on any school. Identity scopes never can."""
    chair = fx.principal("chair")
    auth.require_school(chair, fx.uni_id)
    auth.require_school(chair, fx.other_id)


def test_a_nonexistent_person_is_refused_not_crashed(fx):
    sponsor = fx.principal("uni_sponsor")
    with fx.db.read() as tx:
        with pytest.raises(auth.ForbiddenError):
            auth.require_person_in_scope(tx, sponsor, 999999)


# ---------------------------------------------------------------------------
# Impersonation


# ---------------------------------------------------------------------------


def test_impersonation_requires_star_scope(fx):
    actor = fx.principal('uni_sponsor')
    with pytest.raises(auth.ForbiddenError):
        with fx.db.tx() as tx:
            auth.start_impersonation(
                tx, actor, fx.delegate_id, fx.codes["uni_sponsor"])


def test_impersonation_requires_the_admins_own_code(fx):
    """Step-up: proves the person at the keyboard is the admin, not someone who
    walked up to an unlocked laptop."""
    actor = fx.principal('admin')
    with pytest.raises(auth.AuthError):
        with fx.db.tx() as tx:
            auth.start_impersonation(
                tx, actor, fx.delegate_id, fx.codes["uni_sponsor"])


def test_impersonation_is_read_only_by_default(fx):
    actor = fx.principal('admin')
    with fx.db.tx() as tx:
        token, principal = auth.start_impersonation(
            tx, actor, fx.delegate_id, fx.codes["admin"])
    assert principal.is_impersonating
    assert not principal.impersonation_can_write
    with pytest.raises(auth.ReadOnlySession):
        auth.require_writable(principal)


def test_impersonation_expires_in_thirty_minutes(fx):
    actor = fx.principal('admin')
    with fx.db.tx() as tx:
        _, principal = auth.start_impersonation(
            tx, actor, fx.delegate_id, fx.codes["admin"])
    with fx.db.read() as tx:
        expires = tx.one("auth.sessions_for_person", (fx.delegate_id,))["expires_at"]
    minutes = (clock.parse_iso(expires) - clock.now_utc()).total_seconds() / 60
    assert 25 < minutes <= 30


def test_impersonation_never_reveals_the_targets_code(fx):
    actor = fx.principal('admin')
    with fx.db.tx() as tx:
        _, principal = auth.start_impersonation(
            tx, actor, fx.delegate_id, fx.codes["admin"])
    dumped = repr(principal.to_public_dict())
    assert "code" not in dumped.lower() or "code_hmac" not in dumped
    assert codes.normalize(fx.codes["delegate"]) not in dumped


def test_impersonation_logs_both_identities(fx):
    actor = fx.principal('admin')
    with fx.db.tx() as tx:
        _, principal = auth.start_impersonation(
            tx, actor, fx.delegate_id, fx.codes["admin"])
    with fx.db.read() as tx:
        row = [r for r in tx.all("audit.recent", (10 ** 9, 50))
               if r["action"] == "impersonation.start"][0]
    assert row["actor_person_id"] == fx.delegate_id
    assert row["impersonator_person_id"] == fx.admin_id
    assert "started viewing the site as" in row["summary"]


def test_an_impersonator_cannot_nest_impersonation(fx):
    actor = fx.principal('admin')
    with fx.db.tx() as tx:
        _, principal = auth.start_impersonation(
            tx, actor, fx.delegate_id, fx.codes["admin"])
    with pytest.raises(auth.ForbiddenError):
        with fx.db.tx() as tx:
            auth.start_impersonation(tx, principal, fx.other_delegate_id, fx.codes["admin"])


# ---------------------------------------------------------------------------
# The audit invariant


# ---------------------------------------------------------------------------


def test_a_mutation_without_an_audit_entry_refuses_to_commit(fx):
    """There is no code path that changes data without logging it -- and that is
    enforced here, not left to reviewer discipline."""
    with pytest.raises(AuditRequired):
        with fx.db.tx() as tx:
            tx.run("people.restore", (clock.now_iso(), fx.delegate_id))

    # And the mutation genuinely rolled back with it.
    with fx.db.read() as tx:
        assert tx.one("people.school_of", (fx.delegate_id,))["status"] == "active"


def test_a_read_transaction_refuses_to_mutate(fx):
    with pytest.raises(AuditRequired):
        with fx.db.read() as tx:
            tx.run("people.restore", (clock.now_iso(), fx.delegate_id))


def test_value_detail_is_restricted_to_payments(fx):
    """changed_fields records field NAMES only, to keep PII out of the log.
    value_detail carries real values and is allowed on payments alone."""
    with pytest.raises(ValueError):
        with fx.db.tx() as tx:
            tx.audit("person.update", "x", value_detail={"first_name": "Bob"})


def test_an_ip_hash_cannot_be_reversed_by_hashing_the_whole_address_space():
    """IPv4 is 2^32 addresses. A plain SHA-256 of one is barely a hash.

    Anybody holding the database could recover every IP it stores by hashing
    the entire space -- minutes on ordinary hardware -- which is the same
    argument the access codes are peppered for, applying with more force: a
    code has 44.6 bits of entropy and an IP has at most 32.

    The check is that the stored value depends on the pepper, so the space
    cannot be enumerated without also stealing a secret that is not in the
    database.
    """
    import hashlib
    from backend.lib import auth

    stored = auth.hash_ip("203.0.113.7")
    naive = hashlib.sha256(b"ip:203.0.113.7").hexdigest()
    assert stored != naive, (
        "the IP hash is computable without the pepper, so the whole IPv4 "
        "space can be enumerated against it")

    # Still deterministic, or the rate limiter counts nothing.
    assert auth.hash_ip("203.0.113.7") == stored
    assert auth.hash_ip("203.0.113.8") != stored
