"""One sponsor, more than one chapter.

WHAT A GRANT IS. `people.school_id` says which chapter somebody belongs to, and
that stays true: it is where their number comes from and it is the shape almost
everybody has. A grant records the ADDITIONAL chapters a sponsor may act for --
a teacher who moved schools mid-year, a district where one person covers the
middle school and the high school, somebody covering for a colleague on leave.

WHAT IT IS NOT, and this is the whole reason the tests below are as suspicious
as they are. It is not a way to get a scope. Scopes reach a person only through
roles -- person_roles, roles, role_scopes -- and a grant cannot conjure one. It
widens WHICH CHAPTERS an existing scope reaches, and nothing else.

This is the most safety-critical change in the system, because the realistic
attack on it is one sponsor reading another chapter's roster and every endpoint
funnels through `require_school`. So: the grant works, the grant is narrow, and
everybody without one is exactly as fenced in as they were before.
"""

from __future__ import annotations

import pytest

from backend import api
from backend.lib import auth, clock

from .helpers import Fixture


@pytest.fixture
def fx(tmp_path, monkeypatch):
    with Fixture(tmp_path) as f:
        monkeypatch.setattr(api, "_db", f.db)
        yield f


@pytest.fixture
def client(fx):
    from fastapi.testclient import TestClient
    # AS A CONTEXT MANAGER, so the portal and its threadpool shut down when
    # the test ends. A TestClient that is never closed leaves its worker
    # threads running, and each holds an idle database connection for the
    # rest of the session -- hundreds of open handles on files the tests
    # have finished with, which turned a two-minute suite into a
    # seven-minute one.
    with TestClient(api.app, raise_server_exceptions=False) as client:
        yield client


def as_(fx, who: str) -> dict:
    return {"Authorization": f"Bearer {fx.sign_in(who)}"}


def grant(fx, person_id: int, school_id: int, note: str | None = None) -> None:
    """Write a grant directly, for tests about what one does rather than about
    how one is created."""
    with fx.db.tx() as tx:
        tx.insert("grants.create",
                  (person_id, school_id, fx.admin_id, clock.now_iso(), note))
        tx.audit("sponsor.grant", "Test fixture granted a second chapter.")


# ---------------------------------------------------------------------------
# Nobody has one, and nothing changed
# ---------------------------------------------------------------------------

def test_a_sponsor_with_no_grant_still_sees_one_chapter(fx, client):
    """The case that is true for every sponsor at this convention. If this ever
    fails, the feature has widened access rather than added a way to."""
    response = client.get(f"/sponsor/roster?school_id={fx.other_id}",
                          headers=as_(fx, "uni_sponsor"))
    assert response.status_code == 403


def test_a_delegate_gains_nothing_from_the_table_existing(fx):
    """A grant only means something alongside the sponsor role, and the
    endpoint refuses to write one otherwise -- but if a row appeared by some
    other route, it must still not turn a delegate into a sponsor."""
    grant(fx, fx.delegate_id, fx.other_id)
    principal = fx.principal("delegate")

    assert not principal.has_scope("sponsor")
    with pytest.raises(auth.ForbiddenError):
        auth.require_school(principal, fx.other_id)


def test_a_grant_is_not_loaded_for_people_who_cannot_use_one(fx):
    """A read-quota decision as much as a correctness one: this runs on every
    authenticated request, and asking it for every delegate would cost a lookup
    per page view for a case that applies to a handful of adults."""
    assert fx.principal("delegate").granted_school_ids == frozenset()
    assert fx.principal("chaperone").granted_school_ids == frozenset()


# ---------------------------------------------------------------------------
# What a grant does
# ---------------------------------------------------------------------------

def test_a_granted_sponsor_reaches_the_other_chapter(fx, client):
    grant(fx, fx.uni_sponsor_id, fx.other_id)

    response = client.get(f"/sponsor/roster?school_id={fx.other_id}",
                          headers=as_(fx, "uni_sponsor"))
    assert response.status_code == 200
    assert response.json()["school"]["id"] == fx.other_id


def test_a_granted_sponsor_still_defaults_to_their_own_chapter(fx, client):
    """Their own chapter is where their number comes from, and it is what the
    roster opens on. A grant adds a chapter to reach, it does not move them."""
    grant(fx, fx.uni_sponsor_id, fx.other_id)

    response = client.get("/sponsor/roster", headers=as_(fx, "uni_sponsor"))
    assert response.json()["school"]["id"] == fx.uni_id


def test_a_grant_does_not_reach_a_third_chapter(fx, client):
    """The obvious failure mode of a set-membership check written as a boolean:
    "has any grant" is not "may act on this one"."""
    grant(fx, fx.uni_sponsor_id, fx.other_id)

    response = client.get(f"/sponsor/roster?school_id={fx.exempt_id}",
                          headers=as_(fx, "uni_sponsor"))
    assert response.status_code == 403


def test_a_grant_does_not_add_a_scope(fx):
    """The invariant that matters most. A sponsor covering two chapters is
    still a sponsor: no registration scope, no admin scope, no reach into
    anything a sponsor could not already do at their own chapter."""
    grant(fx, fx.uni_sponsor_id, fx.other_id)
    principal = fx.principal("uni_sponsor")

    assert principal.granted_school_ids == frozenset({fx.other_id})
    assert not principal.has_scope("registration")
    assert not principal.has_scope("*")
    assert not principal.has_scope("academics")


def test_a_granted_sponsor_can_act_on_a_person_at_that_chapter(fx, client):
    """`require_person_in_scope` is the other door into the same check, and an
    endpoint taking a person id from the URL uses it rather than
    `require_school` directly."""
    grant(fx, fx.uni_sponsor_id, fx.other_id)

    response = client.patch(f"/sponsor/people/{fx.other_delegate_id}",
                            headers=as_(fx, "uni_sponsor"),
                            json={"first_name": "Rowan"})
    assert response.status_code == 200

    response = client.patch(f"/sponsor/people/{fx.delegate_id}",
                            headers=as_(fx, "other_sponsor"),
                            json={"first_name": "Nope"})
    assert response.status_code == 403


def test_me_lists_both_chapters_so_one_can_be_reached(fx, client):
    """Access nothing offers is access nobody has. The roster page reads this
    to draw the line of chapters to switch between."""
    grant(fx, fx.uni_sponsor_id, fx.other_id)

    body = client.get("/auth/me", headers=as_(fx, "uni_sponsor")).json()
    assert [s["id"] for s in body["schools"]] == [fx.uni_id, fx.other_id]


def test_me_says_nothing_about_chapters_for_everybody_else(fx, client):
    """An empty list, not a list of one: the page shows the switcher only when
    there is something to switch to."""
    body = client.get("/auth/me", headers=as_(fx, "uni_sponsor")).json()
    assert body["schools"] == []


# ---------------------------------------------------------------------------
# Making one
# ---------------------------------------------------------------------------

def test_a_chair_grants_and_the_sponsor_can_then_reach_it(fx, client):
    response = client.post(f"/admin/schools/{fx.other_id}/sponsors",
                           headers=as_(fx, "chair"),
                           json={"person_id": fx.uni_sponsor_id,
                                 "note": "Covering while Robin is on leave."})
    assert response.status_code == 200, response.text

    response = client.get(f"/sponsor/roster?school_id={fx.other_id}",
                          headers=as_(fx, "uni_sponsor"))
    assert response.status_code == 200


def test_granting_someone_who_is_not_a_sponsor_is_refused_with_a_reason(fx, client):
    """A row for somebody with no sponsor role would do nothing at all, which
    is a worse outcome than a refusal: the chair would believe they had given
    access, and the person would find none."""
    response = client.post(f"/admin/schools/{fx.other_id}/sponsors",
                           headers=as_(fx, "chair"),
                           json={"person_id": fx.delegate_id})
    assert response.status_code == 422
    assert "is not a sponsor" in response.json()["error"]

    with fx.db.read() as tx:
        assert tx.one("grants.get", (fx.delegate_id, fx.other_id)) is None


def test_granting_somebody_their_own_chapter_is_refused(fx, client):
    """It would be a second way of saying something `people.school_id` already
    says, and two sources for one fact is how they disagree."""
    response = client.post(f"/admin/schools/{fx.uni_id}/sponsors",
                           headers=as_(fx, "chair"),
                           json={"person_id": fx.uni_sponsor_id})
    assert response.status_code == 422
    assert "already belongs" in response.json()["error"]


def test_granting_twice_is_refused_rather_than_duplicated(fx, client):
    """The unique index would refuse it anyway; this makes it a sentence."""
    payload = {"person_id": fx.uni_sponsor_id}
    client.post(f"/admin/schools/{fx.other_id}/sponsors",
                headers=as_(fx, "chair"), json=payload)
    response = client.post(f"/admin/schools/{fx.other_id}/sponsors",
                           headers=as_(fx, "chair"), json=payload)

    assert response.status_code == 422
    assert "can already act for" in response.json()["error"]


def test_a_sponsor_cannot_grant_themselves_anything(fx, client):
    """The attack this feature would be worth mounting. `registration` is a
    chair's scope and a sponsor does not have it."""
    response = client.post(f"/admin/schools/{fx.other_id}/sponsors",
                           headers=as_(fx, "uni_sponsor"),
                           json={"person_id": fx.uni_sponsor_id})
    assert response.status_code == 403

    with fx.db.read() as tx:
        assert tx.one("grants.get", (fx.uni_sponsor_id, fx.other_id)) is None


def test_the_grant_is_written_in_the_same_transaction_as_its_audit_entry(fx, client):
    """The rule the whole database enforces, checked here because a new write
    path is exactly where it gets forgotten."""
    client.post(f"/admin/schools/{fx.other_id}/sponsors",
                headers=as_(fx, "chair"),
                json={"person_id": fx.uni_sponsor_id, "note": "Two schools."})

    with fx.db.read() as tx:
        rows = [dict(r) for r in tx.all("audit.recent", (10 ** 9, 50))]
    entry = next(r for r in rows if r["action"] == "sponsor.grant")

    assert "Rival High School" in entry["summary"]
    assert "Sam Sponsor" in entry["summary"]
    assert "Note: Two schools." in entry["summary"]
    assert entry["entity_id"] == fx.uni_sponsor_id
    assert entry["school_id"] == fx.other_id


# ---------------------------------------------------------------------------
# Taking one back
# ---------------------------------------------------------------------------

def test_revoking_ends_the_access_immediately(fx, client):
    grant(fx, fx.uni_sponsor_id, fx.other_id)

    response = client.delete(
        f"/admin/schools/{fx.other_id}/sponsors/{fx.uni_sponsor_id}",
        headers=as_(fx, "chair"))
    assert response.status_code == 200

    response = client.get(f"/sponsor/roster?school_id={fx.other_id}",
                          headers=as_(fx, "uni_sponsor"))
    assert response.status_code == 403


def test_revoking_leaves_their_own_chapter_alone(fx, client):
    """Somebody's own chapter is `people.school_id` and is not reachable from
    here. Removing that is "they have left", which is a different action with
    different consequences."""
    grant(fx, fx.uni_sponsor_id, fx.other_id)
    client.delete(f"/admin/schools/{fx.other_id}/sponsors/{fx.uni_sponsor_id}",
                  headers=as_(fx, "chair"))

    response = client.get("/sponsor/roster", headers=as_(fx, "uni_sponsor"))
    assert response.status_code == 200
    assert response.json()["school"]["id"] == fx.uni_id


def test_revoking_what_was_never_granted_says_so(fx, client):
    response = client.delete(
        f"/admin/schools/{fx.other_id}/sponsors/{fx.uni_sponsor_id}",
        headers=as_(fx, "chair"))
    assert response.status_code == 422
    assert "already been removed" in response.json()["error"]
