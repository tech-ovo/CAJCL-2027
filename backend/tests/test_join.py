"""Joining a chapter with its join code, and approving who joined.

The promises worth pinning down:

  * a student joins, is signed in, and holds a working access code -- all
    without a sponsor lifting a finger;
  * until approved they are in NO money or meal figure, and approval moves them
    into all of it;
  * denying them removes their data and can never bill anybody;
  * a join code can be closed or replaced, and a wrong one cannot lock people
    out of signing in.
"""

from __future__ import annotations

import pytest

from backend import api
from backend.lib import auth, clock, joining

from .helpers import Fixture


@pytest.fixture
def fx(tmp_path, monkeypatch):
    with Fixture(tmp_path) as f:
        monkeypatch.setattr(api, "_db", f.db)
        yield f


@pytest.fixture
def client(fx):
    from fastapi.testclient import TestClient
    with TestClient(api.app, raise_server_exceptions=False) as c:
        yield c


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def sponsor(fx):
    return bearer(fx.sign_in("uni_sponsor"))


def code_of(fx, school="University High School"):
    return fx.join_codes[school]


def join(client, fx, first="Jo", last="Joiner", *, grade=10, level="HS-2",
         code=None, school="University High School"):
    return client.post("/auth/join", json={
        "join_code": code or code_of(fx, school),
        "first_name": first, "last_name": last,
        "grade": grade, "latin_level": level})


# --- the join itself -------------------------------------------------------

def test_a_student_joins_is_signed_in_and_holds_a_working_code(fx, client):
    response = join(client, fx)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["person"]["approval"] == "pending"
    assert body["person"]["first_name"] == "Jo"
    assert body["person"]["scopes"] == ["delegate"]
    assert body["school"]["name"] == "University High School"

    # The session works...
    me = client.get("/auth/me", headers=bearer(body["token"])).json()
    assert me["approval"] == "pending"
    # ...and so does the access code, on a fresh sign-in.
    again = client.post("/auth/redeem", json={"code": body["code"]})
    assert again.status_code == 200
    assert again.json()["person"]["approval"] == "pending"


def test_the_join_code_is_forgiving_about_how_it_is_typed(fx, client):
    code = code_of(fx)
    typed = f" {code[:4].lower()}-{code[4:].lower()} "
    assert join(client, fx, code=typed).status_code == 200


def test_a_pending_student_can_use_their_own_forms_straight_away(fx, client):
    body = join(client, fx).json()
    response = client.get("/me/activity-sheet", headers=bearer(body["token"]))
    assert response.status_code == 200


def test_a_wrong_code_is_refused_with_a_sentence(fx, client):
    response = join(client, fx, code="ZZZZZZZZ")
    assert response.status_code == 422
    assert "Check that join code" in response.json()["error"]

    response = join(client, fx, code="ABCDEFGH")
    assert response.status_code == 422
    assert "not recognised" in response.json()["error"]


def test_each_chapter_has_its_own_code(fx, client):
    other = code_of(fx, "Rival High School")
    assert other != code_of(fx)
    body = join(client, fx, code=other).json()
    assert body["school"]["name"] == "Rival High School"
    assert body["person"]["school"]["name"] == "Rival High School"


def test_grade_and_level_must_suit_the_chapter(fx, client):
    # University High is a high school.
    assert join(client, fx, grade=7).status_code == 422
    assert join(client, fx, level="MS-1").status_code == 422
    assert join(client, fx, level=None).status_code == 422
    assert join(client, fx, grade=None).status_code == 422
    assert join(client, fx, first="  ").status_code == 422


def test_names_are_tidied_but_deliberate_capitals_are_left_alone(fx, client):
    body = join(client, fx, first="dana jo", last="McDonald").json()
    assert body["person"]["first_name"] == "Dana Jo"
    assert body["person"]["last_name"] == "McDonald"


def test_the_same_name_cannot_join_twice(fx, client):
    assert join(client, fx, "Sam", "Student").status_code == 200
    again = join(client, fx, "sam", "STUDENT")
    assert again.status_code == 422
    assert "ask your sponsor" in again.json()["error"]
    # Also stops a name already on the sponsor's pasted roster.
    clash = join(client, fx, "Dana", "Delegate")
    assert clash.status_code == 422


def test_a_cancelled_student_can_join_again(fx, client):
    first = join(client, fx, "Sam", "Student").json()
    pid = first["person"]["person_id"]
    h = sponsor(fx)
    assert client.post(f"/sponsor/people/{pid}/approve", headers=h).status_code == 200
    assert client.post(f"/sponsor/people/{pid}/cancel", headers=h).status_code == 200
    assert join(client, fx, "Sam", "Student").status_code == 200


# --- the code can be closed and replaced -----------------------------------

def test_closing_joining_stops_it_and_reopening_restores_it(fx, client):
    h = sponsor(fx)
    closed = client.post("/sponsor/join/open", headers=h, json={"open": False})
    assert closed.status_code == 200 and closed.json()["join_open"] is False

    refused = join(client, fx)
    assert refused.status_code == 422
    assert "closed" in refused.json()["error"]

    client.post("/sponsor/join/open", headers=h, json={"open": True})
    assert join(client, fx).status_code == 200


def test_regenerating_replaces_the_code_and_keeps_existing_students(fx, client):
    h = sponsor(fx)
    old = code_of(fx)
    joined = join(client, fx).json()

    new = client.post("/sponsor/join/code", headers=h, json={}).json()["join_code"]
    assert new != old

    assert join(client, fx, "Late", "Comer", code=old).status_code == 422
    assert join(client, fx, "Late", "Comer", code=new).status_code == 200
    # The student who joined under the old code is untouched.
    assert client.get("/auth/me", headers=bearer(joined["token"])).status_code == 200


def test_the_sponsor_sees_the_code_and_whether_joining_is_open(fx, client):
    roster = client.get("/sponsor/roster", headers=sponsor(fx)).json()
    assert roster["school"]["join_code"] == code_of(fx)
    assert roster["school"]["join_open"] == 1


def test_a_chair_can_manage_any_chapters_code(fx, client):
    chair = bearer(fx.sign_in("chair"))
    response = client.post("/sponsor/join/code", headers=chair,
                           json={"school_id": fx.other_id})
    assert response.status_code == 200


def test_a_new_chapter_gets_a_code_the_chair_can_forward(fx, client):
    chair = bearer(fx.sign_in("chair"))
    created = client.post("/admin/schools", headers=chair, json={
        "name": "Fresh High", "level": "HS", "city": "Irvine"})
    assert created.status_code == 200
    body = created.json()
    assert len(body["join_code"]) == joining.CODE_LENGTH
    assert body["join_open"] is True
    assert join(client, fx, code=body["join_code"]).status_code == 200

    listed = client.get("/admin/schools", headers=chair).json()["schools"]
    assert any(s.get("join_code") == body["join_code"] for s in listed)


def test_the_sponsor_account_response_carries_the_join_code(fx, client):
    chair = bearer(fx.sign_in("chair"))
    response = client.post(f"/admin/schools/{fx.other_id}/people", headers=chair,
                           json={"first_name": "New", "last_name": "Sponsor"})
    assert response.status_code == 200
    assert response.json()["join_code"] == code_of(fx, "Rival High School")


# --- pending is not billed, fed, or counted ---------------------------------

def figures(fx):
    stats = fx.stats_for(fx.uni_id)
    return {k: stats[k] for k in (
        "delegates_active", "delegates_pending", "amount_owed_cents",
        "meal_regular", "meal_unanswered")} | {
        "public_delegates": fx.public_stats()["delegates"]}


def test_pending_students_are_in_no_money_or_meal_figure(fx, client):
    before = figures(fx)
    join(client, fx, "One", "Pending")
    join(client, fx, "Two", "Pending")
    after = figures(fx)

    assert after["delegates_pending"] == before["delegates_pending"] + 2
    for key in ("delegates_active", "amount_owed_cents", "meal_regular",
                "meal_unanswered", "public_delegates"):
        assert after[key] == before[key], key


def test_approving_moves_a_student_into_every_figure(fx, client):
    before = figures(fx)
    joined = join(client, fx, "One", "Pending").json()
    pid = joined["person"]["person_id"]

    response = client.post(f"/sponsor/people/{pid}/approve", headers=sponsor(fx))
    assert response.status_code == 200
    after = figures(fx)

    assert after["delegates_pending"] == before["delegates_pending"]
    assert after["delegates_active"] == before["delegates_active"] + 1
    assert after["public_delegates"] == before["public_delegates"] + 1
    assert after["amount_owed_cents"] > before["amount_owed_cents"]
    assert after["meal_unanswered"] == before["meal_unanswered"] + 1
    assert "person.approve" in fx.audit_actions()

    # And they are told so.
    me = client.get("/auth/me", headers=bearer(joined["token"])).json()
    assert me["approval"] == "approved"


def test_approve_all(fx, client):
    for n in range(3):
        join(client, fx, f"Student{n}", "Many")
    before = figures(fx)
    response = client.post("/sponsor/approve-all", headers=sponsor(fx), json={})
    assert response.json()["approved"] == 3
    after = figures(fx)
    assert after["delegates_pending"] == 0
    assert after["delegates_active"] == before["delegates_active"] + 3


def test_an_approved_student_cannot_be_approved_again(fx, client):
    pid = join(client, fx).json()["person"]["person_id"]
    h = sponsor(fx)
    client.post(f"/sponsor/people/{pid}/approve", headers=h)
    assert client.post(f"/sponsor/people/{pid}/approve", headers=h).status_code == 409
    assert client.post(f"/sponsor/people/{pid}/deny", headers=h).status_code == 409


def test_a_pending_student_cannot_be_cancelled_only_approved_or_denied(fx, client):
    pid = join(client, fx).json()["person"]["person_id"]
    response = client.post(f"/sponsor/people/{pid}/cancel", headers=sponsor(fx))
    assert response.status_code == 409


def test_pending_students_appear_on_the_roster_marked_as_such(fx, client):
    pid = join(client, fx, "Mark", "Me").json()["person"]["person_id"]
    people = client.get("/sponsor/roster", headers=sponsor(fx)).json()["people"]
    row = next(p for p in people if p["id"] == pid)
    assert row["approval"] == "pending"
    assert all(p["approval"] == "approved" for p in people if p["id"] != pid)


def test_the_chair_dashboard_shows_pending_beside_the_totals(fx, client):
    join(client, fx)
    dash = client.get("/admin/registration", headers=bearer(fx.sign_in("chair"))).json()
    assert dash["totals"]["delegates_pending"] == 1
    overview = client.get("/admin/overview", headers=bearer(fx.sign_in("chair"))).json()
    assert overview["totals"]["delegates_pending"] == 1
    row = next(r for r in overview["chapters"] if r["school_id"] == fx.uni_id)
    assert row["delegates_pending"] == 1


def test_pending_students_get_no_printed_access_sheet(fx, client):
    join(client, fx, "Zed", "Zzyzx")
    html = client.get("/sponsor/packet", headers=sponsor(fx)).text
    assert "Zzyzx" not in html


def test_the_join_sheet_carries_the_code_and_no_one_elses_name(fx, client):
    join(client, fx, "Zed", "Zzyzx")
    html = client.get("/sponsor/join-sheet", headers=sponsor(fx)).text
    code = code_of(fx)
    assert f"{code[:4]}-{code[4:]}" in html
    assert f"/#/join/{code}" not in html   # inside the QR, not as text
    assert "<svg" in html
    assert "Zzyzx" not in html


# --- denial ----------------------------------------------------------------

def test_denying_removes_their_data_and_their_way_in(fx, client):
    joined = join(client, fx, "Gone", "Soon").json()
    pid = joined["person"]["person_id"]

    response = client.post(f"/sponsor/people/{pid}/deny", headers=sponsor(fx))
    assert response.status_code == 200

    with fx.db.read() as tx:
        row = dict(tx.one("people.get", (pid,)))
    assert row["approval"] == "denied"
    assert row["first_name"] == "REDACTED" and row["last_name"] == "REDACTED"
    assert row["grade"] is None and row["latin_level"] is None

    assert client.post("/auth/redeem", json={"code": joined["code"]}).status_code == 401
    assert client.get("/auth/me", headers=bearer(joined["token"])).status_code == 401

    # Gone from the roster, and their name gone from the audit trail.
    people = client.get("/sponsor/roster", headers=sponsor(fx)).json()["people"]
    assert pid not in [p["id"] for p in people]
    with fx.db.read() as tx:
        summaries = " ".join(r["summary"] for r in tx.all("audit.recent", (10 ** 9, 200)))
    assert "Gone Soon" not in summaries
    assert "person.deny" in fx.audit_actions()


def test_a_denied_student_is_never_billed_even_after_a_payment(fx, client):
    chair = bearer(fx.sign_in("chair"))
    client.post("/admin/payments", headers=chair,
                json={"school_id": fx.uni_id, "amount_cents": 100, "method": "check"})
    before = figures(fx)

    pid = join(client, fx).json()["person"]["person_id"]
    client.post(f"/sponsor/people/{pid}/deny", headers=sponsor(fx))
    after = figures(fx)

    stats = fx.stats_for(fx.uni_id)
    assert stats["delegates_cancelled_paid"] == 0
    assert after == before


def test_redacting_a_pending_student_the_old_way_is_a_denial(fx, client):
    pid = join(client, fx).json()["person"]["person_id"]
    assert client.post(f"/sponsor/people/{pid}/redact",
                       headers=sponsor(fx)).status_code == 200
    with fx.db.read() as tx:
        assert tx.one("people.get", (pid,))["approval"] == "denied"
    assert fx.stats_for(fx.uni_id)["delegates_pending"] == 0


# --- abuse -----------------------------------------------------------------

def test_a_leaked_code_cannot_bury_the_approval_list(fx, client, monkeypatch):
    monkeypatch.setattr(joining, "MAX_PENDING", 3)
    for n in range(3):
        assert join(client, fx, f"Spam{n}", "Bot").status_code == 200
    blocked = join(client, fx, "Spam4", "Bot")
    assert blocked.status_code == 422
    assert "waiting for approval" in blocked.json()["error"]


def test_wrong_join_codes_are_limited_but_never_block_signing_in(fx, client):
    for _ in range(joining.JOIN_IP_LIMIT):
        assert join(client, fx, code="ABCDEFGH").status_code == 422
    limited = join(client, fx, code="ABCDEFGH")
    assert limited.status_code == 429

    # The real code is limited too -- the cost of a flood from one network --
    # but signing in with an access code is a separate limiter entirely.
    assert join(client, fx).status_code == 429
    assert client.post("/auth/redeem",
                       json={"code": fx.codes["delegate"]}).status_code == 200


def test_sign_in_failures_do_not_count_against_joining(fx, client):
    for _ in range(auth.IP_LIMIT - 1):
        client.post("/auth/redeem", json={"code": "DEL-AAAAA-AAAAA"})
    assert join(client, fx).status_code == 200


def test_organizations_never_take_joiners(fx, client):
    # A code that somehow reached an organization is refused.
    with fx.db.tx() as tx:
        tx.run("schools.set_join_code", ("ORGCODE1", clock.now_iso(), fx.board_id))
        tx.audit("school.join_code", "Test planted a code.", school_id=fx.board_id)
    assert join(client, fx, code="ORGCODE1").status_code == 422
