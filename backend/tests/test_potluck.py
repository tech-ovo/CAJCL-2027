"""The activities potluck: the chair's list, picks on the sheets, a sponsor's
decision, the cap, overlaps, the master schedule, and erasure.
"""

from __future__ import annotations

import pytest

from backend import api
from backend.lib import potluck
from backend.lib.catalog import ValidationError

from .helpers import Fixture


@pytest.fixture
def fx(tmp_path, monkeypatch):
    with Fixture(tmp_path) as f:
        monkeypatch.setattr(api, "_db", f.db)
        with f.db.tx() as tx:
            f.activities_id = f._person(
                tx, "activities", f.board_id, person_type="adult", adult_type="other",
                first="Ace", last="Activities", role="activities_chair",
                email="act@example.org")
            tx.audit("person.create", "Test fixture added an Activities chair.")
        yield f


@pytest.fixture
def client(fx):
    from fastapi.testclient import TestClient
    with TestClient(api.app, raise_server_exceptions=False) as client:
        yield client


def as_(fx, who):
    return {"Authorization": f"Bearer {fx.sign_in(who)}"}


def make(client, fx, name="Face painting", **extra):
    body = {"name": name, "description": "Paint faces.", **extra}
    response = client.post("/admin/potluck", headers=as_(fx, "activities"), json=body)
    assert response.status_code == 200, response.text
    return response.json()["activity"]


def delegate_save(client, headers, potluck_ids, sheet_url="/me/activity-sheet"):
    """Save the delegate's sheet with the minimum it needs, plus their picks."""
    sheet = client.get(sheet_url, headers=headers).json()
    testing = next(c for c in sheet["catalog"] if c["key"] == "academic_testing")
    eligible = [i["id"] for i in testing["items"] if i["eligible_now"]]
    return client.put(sheet_url, headers=headers, json={
        "grade": 10, "latin_level": "HS-2", "meal": "regular",
        "selected": eligible[:1], "potluck": potluck_ids})


def status_of(client, headers, activity_id):
    sheet = client.get("/me/activity-sheet", headers=headers).json()
    return next((a["status"] for a in sheet["potluck"]["activities"]
                 if a["id"] == activity_id), "absent")


# ---------------------------------------------------------------------------
# The chair's activities
# ---------------------------------------------------------------------------

def test_the_chair_adds_an_activity_and_it_reaches_the_sheets(fx, client):
    activity = make(client, fx, location="Quad", capacity=3)
    assert activity["capacity"] == 3 and activity["open"] is True

    delegate = as_(fx, "delegate")
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    assert [a["name"] for a in sheet["potluck"]["activities"]] == ["Face painting"]
    assert sheet["potluck"]["needs_approval"] is True

    adult = client.get("/me/adult-sheet", headers=as_(fx, "chaperone")).json()
    assert [a["name"] for a in adult["potluck"]["activities"]] == ["Face painting"]
    assert adult["potluck"]["needs_approval"] is False


def test_two_activities_cannot_share_a_name(fx, client):
    make(client, fx)
    again = client.post("/admin/potluck", headers=as_(fx, "activities"),
                        json={"name": "face PAINTING"})
    assert again.status_code == 422
    assert "already an activity" in again.json()["error"]


def test_activity_rules_are_checked():
    for bad in ({"name": ""}, {"name": "x", "capacity": 0}, {"name": "x", "capacity": "two"},
                {"name": "x", "date": "2027-03-12", "start": "10:00", "end": "09:00"},
                {"name": "x", "date": "2027-03-12"}):
        with pytest.raises(ValidationError):
            potluck.check_activity(bad)
    fields = potluck.check_activity({"name": "  Sand  art ", "capacity": ""})
    assert fields["name"] == "Sand art" and fields["capacity"] is None
    assert fields["starts_at"] is None


# ---------------------------------------------------------------------------
# Picks and the sponsor's decision
# ---------------------------------------------------------------------------

def test_a_delegates_pick_waits_for_their_sponsor(fx, client):
    activity = make(client, fx)
    delegate = as_(fx, "delegate")
    assert delegate_save(client, delegate, [activity["id"]]).status_code == 200
    assert status_of(client, delegate, activity["id"]) == "pending"

    # The chair sees nothing until it is approved, only that one is waiting.
    chair = client.get("/admin/potluck", headers=as_(fx, "activities")).json()
    row = chair["activities"][0]
    assert row["volunteers"] == [] and row["waiting"] == 1

    roster = client.get("/sponsor/roster", headers=as_(fx, "uni_sponsor")).json()
    request = roster["potluck_requests"][0]
    assert (request["person_id"], request["activity_id"]) == (fx.delegate_id, activity["id"])

    approve = client.post(
        f"/sponsor/people/{fx.delegate_id}/potluck/{activity['id']}/approve",
        headers=as_(fx, "uni_sponsor"), json={})
    assert approve.status_code == 200
    assert status_of(client, delegate, activity["id"]) == "approved"

    chair = client.get("/admin/potluck", headers=as_(fx, "activities")).json()
    helpers = chair["activities"][0]["volunteers"]
    assert [(h["name"], h["school_name"]) for h in helpers] == [
        ("Dana Delegate", "University High School")]
    assert client.get("/sponsor/roster", headers=as_(fx, "uni_sponsor")
                      ).json()["potluck_requests"] == []


def test_saving_the_sheet_again_keeps_the_sponsors_decision(fx, client):
    activity = make(client, fx)
    delegate = as_(fx, "delegate")
    delegate_save(client, delegate, [activity["id"]])
    client.post(f"/sponsor/people/{fx.delegate_id}/potluck/{activity['id']}/approve",
                headers=as_(fx, "uni_sponsor"), json={})
    delegate_save(client, delegate, [activity["id"]])
    assert status_of(client, delegate, activity["id"]) == "approved"


def test_a_sheet_saved_without_the_potluck_leaves_it_alone(fx, client):
    activity = make(client, fx)
    delegate = as_(fx, "delegate")
    delegate_save(client, delegate, [activity["id"]])
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    testing = next(c for c in sheet["catalog"] if c["key"] == "academic_testing")
    eligible = [i["id"] for i in testing["items"] if i["eligible_now"]]
    client.put("/me/activity-sheet", headers=delegate, json={
        "grade": 10, "latin_level": "HS-2", "meal": "regular",
        "selected": eligible[:1]})
    assert status_of(client, delegate, activity["id"]) == "pending"


def test_unticking_withdraws_a_pick(fx, client):
    activity = make(client, fx)
    delegate = as_(fx, "delegate")
    delegate_save(client, delegate, [activity["id"]])
    delegate_save(client, delegate, [])
    assert status_of(client, delegate, activity["id"]) is None


def test_a_declined_pick_stays_visible_and_can_be_picked_again(fx, client):
    activity = make(client, fx)
    delegate = as_(fx, "delegate")
    delegate_save(client, delegate, [activity["id"]])
    client.post(f"/sponsor/people/{fx.delegate_id}/potluck/{activity['id']}/decline",
                headers=as_(fx, "uni_sponsor"), json={})
    assert status_of(client, delegate, activity["id"]) == "declined"

    # Saving without it leaves the decline on the sheet.
    delegate_save(client, delegate, [])
    assert status_of(client, delegate, activity["id"]) == "declined"

    # Picking it again asks the sponsor again.
    delegate_save(client, delegate, [activity["id"]])
    assert status_of(client, delegate, activity["id"]) == "pending"


def test_an_adults_pick_is_approved_at_once(fx, client):
    activity = make(client, fx)
    adult = as_(fx, "chaperone")
    sheet = client.get("/me/adult-sheet", headers=adult).json()
    response = client.put("/me/adult-sheet", headers=adult, json={
        "adult_type": "chaperone", "latin_knowledge": "none", "meal": "regular",
        "selected": [], "potluck": [activity["id"]]})
    assert response.status_code == 200, response.text
    sheet = client.get("/me/adult-sheet", headers=adult).json()
    assert sheet["potluck"]["activities"][0]["status"] == "approved"
    helpers = client.get("/admin/potluck", headers=as_(fx, "activities")
                         ).json()["activities"][0]["volunteers"]
    assert [h["name"] for h in helpers] == ["Chris Chaperone"]


def test_a_sponsor_entering_a_pick_for_a_delegate_approves_it(fx, client):
    activity = make(client, fx)
    response = delegate_save(client, as_(fx, "uni_sponsor"), [activity["id"]],
                             f"/sponsor/people/{fx.delegate_id}/activity-sheet")
    assert response.status_code == 200, response.text
    assert status_of(client, as_(fx, "delegate"), activity["id"]) == "approved"


def test_a_sponsor_cannot_decide_another_chapters_picks(fx, client):
    activity = make(client, fx)
    delegate_save(client, as_(fx, "delegate"), [activity["id"]])
    response = client.post(
        f"/sponsor/people/{fx.delegate_id}/potluck/{activity['id']}/approve",
        headers=as_(fx, "other_sponsor"), json={})
    assert response.status_code == 403


def test_approve_all_decides_everything_waiting(fx, client):
    first = make(client, fx, "Face painting")
    second = make(client, fx, "Sand art")
    delegate_save(client, as_(fx, "delegate"), [first["id"], second["id"]])
    response = client.post("/sponsor/potluck/approve-all", headers=as_(fx, "uni_sponsor"),
                           json={})
    assert response.json()["approved"] == 2
    assert status_of(client, as_(fx, "delegate"), second["id"]) == "approved"


# ---------------------------------------------------------------------------
# The cap, closing, overlaps
# ---------------------------------------------------------------------------

def test_a_full_activity_takes_no_more_picks_and_a_decline_frees_a_place(fx, client):
    activity = make(client, fx, capacity=1)
    delegate = as_(fx, "delegate")
    assert delegate_save(client, delegate, [activity["id"]]).status_code == 200

    # The adult is refused: the one place is the delegate's, even pending.
    adult = as_(fx, "chaperone")
    refused = client.put("/me/adult-sheet", headers=adult, json={
        "adult_type": "chaperone", "latin_knowledge": "none", "meal": "regular",
        "selected": [], "potluck": [activity["id"]]})
    assert refused.status_code == 422
    assert "all the helpers" in refused.json()["error"]

    client.post(f"/sponsor/people/{fx.delegate_id}/potluck/{activity['id']}/decline",
                headers=as_(fx, "uni_sponsor"), json={})
    ok = client.put("/me/adult-sheet", headers=adult, json={
        "adult_type": "chaperone", "latin_knowledge": "none", "meal": "regular",
        "selected": [], "potluck": [activity["id"]]})
    assert ok.status_code == 200

    # The decline cannot now be reversed: the activity has filled since.
    back = client.post(
        f"/sponsor/people/{fx.delegate_id}/potluck/{activity['id']}/approve",
        headers=as_(fx, "uni_sponsor"), json={})
    assert back.status_code == 422 and "filled" in back.json()["error"]


def test_a_closed_activity_takes_no_new_picks_but_keeps_the_old(fx, client):
    activity = make(client, fx)
    delegate = as_(fx, "delegate")
    delegate_save(client, delegate, [activity["id"]])
    client.patch(f"/admin/potluck/{activity['id']}", headers=as_(fx, "activities"),
                 json={"open": False})

    assert status_of(client, delegate, activity["id"]) == "pending"
    adult = as_(fx, "chaperone")
    # Not even listed to somebody who has not picked it.
    assert client.get("/me/adult-sheet", headers=adult
                      ).json()["potluck"]["activities"] == []
    refused = client.put("/me/adult-sheet", headers=adult, json={
        "adult_type": "chaperone", "latin_knowledge": "none", "meal": "regular",
        "selected": [], "potluck": [activity["id"]]})
    assert refused.status_code == 422


def test_overlapping_picks_warn_but_save(fx, client):
    first = make(client, fx, "Face painting", date="2027-03-12", start="10:00", end="11:00")
    second = make(client, fx, "Sand art", date="2027-03-12", start="10:30", end="11:30")
    third = make(client, fx, "Bubbles", date="2027-03-12", start="11:00", end="12:00")
    delegate = as_(fx, "delegate")

    response = delegate_save(client, delegate, [first["id"], second["id"]])
    assert response.status_code == 200
    assert any("Face painting" in w and "Sand art" in w
               for w in response.json()["warnings"])

    # Back to back is not an overlap.
    back_to_back = delegate_save(client, delegate, [first["id"], third["id"]])
    assert not [w for w in back_to_back.json()["warnings"] if "same time" in w]


# ---------------------------------------------------------------------------
# The master schedule
# ---------------------------------------------------------------------------

def schedule_rows(client):
    return client.get("/public/schedule").json()["items"]


def test_an_activity_with_a_time_is_on_the_schedule_and_follows_it(fx, client):
    assert schedule_rows(client) == []
    activity = make(client, fx, location="Quad",
                    date="2027-03-12", start="10:00", end="11:00")
    rows = schedule_rows(client)
    assert [(r["title"], r["source"], r["location"], r["start"]) for r in rows] == [
        ("Face painting", "potluck", "Quad", "10:00")]

    client.patch(f"/admin/potluck/{activity['id']}", headers=as_(fx, "activities"),
                 json={"name": "Face art", "start": "10:15"})
    rows = schedule_rows(client)
    assert [(r["title"], r["start"]) for r in rows] == [("Face art", "10:15")]

    # The activity, not its helpers: no person is on the public schedule.
    assert "Dana" not in str(rows)

    # Taking the time away takes it off.
    client.patch(f"/admin/potluck/{activity['id']}", headers=as_(fx, "activities"),
                 json={"date": "", "start": "", "end": ""})
    assert schedule_rows(client) == []


def test_an_activity_without_a_time_is_not_on_the_schedule(fx, client):
    make(client, fx)
    assert schedule_rows(client) == []


def test_the_logistics_chair_cannot_edit_a_potluck_row(fx, client):
    with fx.db.tx() as tx:
        fx._person(tx, "logistics", fx.board_id, person_type="adult",
                   adult_type="other", first="Lo", last="Gistics",
                   role="logistics_chair", email="lo@example.org")
        tx.audit("person.create", "Test fixture added a Logistics chair.")
    make(client, fx, date="2027-03-12", start="10:00")
    item = client.get("/admin/schedule", headers=as_(fx, "logistics")).json()["items"][0]
    assert item["editable"] is False
    response = client.patch(f"/admin/schedule/{item['id']}",
                            headers=as_(fx, "logistics"), json={"title": "Mine"})
    assert response.status_code == 422 and "potluck" in response.json()["error"].lower()


def test_deleting_an_activity_removes_its_picks_and_schedule_row(fx, client):
    activity = make(client, fx, date="2027-03-12", start="10:00")
    delegate = as_(fx, "delegate")
    delegate_save(client, delegate, [activity["id"]])
    response = client.delete(f"/admin/potluck/{activity['id']}",
                             headers=as_(fx, "activities"))
    assert response.status_code == 200
    assert schedule_rows(client) == []
    assert client.get("/me/activity-sheet", headers=delegate
                      ).json()["potluck"]["activities"] == []


# ---------------------------------------------------------------------------
# Erasure
# ---------------------------------------------------------------------------

def test_redacting_a_person_deletes_their_picks(fx, client):
    activity = make(client, fx)
    delegate_save(client, as_(fx, "delegate"), [activity["id"]])
    response = client.post(f"/sponsor/people/{fx.delegate_id}/redact",
                           headers=as_(fx, "uni_sponsor"), json={})
    assert response.status_code == 200, response.text
    with fx.db.read() as tx:
        assert tx.all("potluck.signups_for_person", (fx.delegate_id,)) == []
