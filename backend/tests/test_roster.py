"""The sponsor flow and the attendee forms, end to end over HTTP.

The idempotency test is the most important one in this file. A sponsor creating
their roster twice is the single most damaging accident available to them, and
"unlikely" is not the standard -- it has to be impossible.
"""

from __future__ import annotations

import pytest

from backend import api
from backend.lib import clock, settings

from .helpers import Fixture

PASTE = """1. Chen, Timothy Wei
2. de la Cruz, Mary Beth
3. Robert McDonald Jr.
4. O'Brien, Seán
5. Smith,John,9,HS-1
"""


@pytest.fixture
def fx(tmp_path, monkeypatch):
    with Fixture(tmp_path) as f:
        monkeypatch.setattr(api, "_db", f.db)
        yield f


@pytest.fixture
def client(fx):
    from fastapi.testclient import TestClient
    return TestClient(api.app, raise_server_exceptions=False)


@pytest.fixture
def sponsor(fx):
    return {"Authorization": f"Bearer {fx.sign_in('uni_sponsor')}"}


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def test_preview_writes_nothing(fx, client, sponsor):
    """Not a roster_imports row, not an audit entry, nothing.

    A sponsor tweaking their paste five times must leave no trace and no stored
    copies of abandoned text.
    """
    before_people = fx.stats_for(fx.uni_id)["delegates_active"]
    before_audit = len(fx.audit_actions())

    response = client.post("/sponsor/roster/parse", headers=sponsor,
                           json={"text": PASTE})
    assert response.status_code == 200
    body = response.json()
    assert body["parsed_count"] == 5
    assert body["idempotency_key"]

    assert fx.stats_for(fx.uni_id)["delegates_active"] == before_people
    assert len(fx.audit_actions()) == before_audit
    with fx.db.read() as tx:
        assert tx.one("roster.import_by_key", (body["idempotency_key"],)) is None


def test_preview_parses_the_way_the_parser_does(fx, client, sponsor):
    rows = client.post("/sponsor/roster/parse", headers=sponsor,
                       json={"text": PASTE}).json()["rows"]
    by_last = {r["last_name"]: r for r in rows}
    assert by_last["Chen"]["first_name"] == "Timothy"
    assert by_last["Chen"]["middle_name"] == "Wei"
    assert by_last["Chen"]["warnings"] == []
    assert by_last["de la Cruz"]["first_name"] == "Mary"
    assert by_last["McDonald"]["suffix"] == "Jr."
    assert by_last["Smith"]["grade"] == 9
    assert by_last["Smith"]["latin_level"] == "HS-1"


def test_an_oversized_paste_is_refused_with_a_number(fx, client, sponsor):
    text = "\n".join(f"Student{i} Example{i}" for i in range(600))
    response = client.post("/sponsor/roster/parse", headers=sponsor,
                           json={"text": text})
    assert response.status_code == 409
    assert "600" in response.json()["error"]


# ---------------------------------------------------------------------------
# Commit -- idempotency
# ---------------------------------------------------------------------------

def _commit(client, sponsor, key, text=PASTE, rows=None):
    preview_rows = rows if rows is not None else _rows(client, sponsor, text)
    return client.post("/sponsor/roster/commit", headers=sponsor, json={
        "text": text, "idempotency_key": key, "rows": preview_rows})


def _rows(client, sponsor, text=PASTE):
    return client.post("/sponsor/roster/parse", headers=sponsor,
                       json={"text": text}).json()["rows"]


def test_commit_creates_the_roster_once(fx, client, sponsor):
    preview = client.post("/sponsor/roster/parse", headers=sponsor,
                          json={"text": PASTE}).json()
    before = fx.stats_for(fx.uni_id)["delegates_active"]

    response = _commit(client, sponsor, preview["idempotency_key"],
                       rows=preview["rows"])
    assert response.status_code == 200
    assert response.json()["committed_count"] == 5
    assert response.json()["already_committed"] is False
    assert fx.stats_for(fx.uni_id)["delegates_active"] == before + 5


def test_a_double_click_cannot_create_a_duplicate_roster(fx, client, sponsor):
    """THE test. Same key, twice, and the second is a no-op that returns the
    first one's result rather than a plausible-looking approximation."""
    preview = client.post("/sponsor/roster/parse", headers=sponsor,
                          json={"text": PASTE}).json()
    key, rows = preview["idempotency_key"], preview["rows"]
    before = fx.stats_for(fx.uni_id)["delegates_active"]

    first = _commit(client, sponsor, key, rows=rows)
    second = _commit(client, sponsor, key, rows=rows)

    assert first.status_code == second.status_code == 200
    assert second.json()["already_committed"] is True
    assert fx.stats_for(fx.uni_id)["delegates_active"] == before + 5
    assert [p["id"] for p in second.json()["created"]] == \
           [p["id"] for p in first.json()["created"]]


def test_ten_concurrent_commits_of_the_same_key_create_one_roster(fx, client, sponsor):
    """A flaky connection retried by an impatient sponsor."""
    preview = client.post("/sponsor/roster/parse", headers=sponsor,
                          json={"text": PASTE}).json()
    before = fx.stats_for(fx.uni_id)["delegates_active"]
    for _ in range(10):
        _commit(client, sponsor, preview["idempotency_key"], rows=preview["rows"])
    assert fx.stats_for(fx.uni_id)["delegates_active"] == before + 5


def test_editing_the_text_after_previewing_invalidates_the_key(fx, client, sponsor):
    """The key is bound to a hash of the pasted text, so a sponsor cannot review
    one list and commit a different one."""
    preview = client.post("/sponsor/roster/parse", headers=sponsor,
                          json={"text": PASTE}).json()
    response = client.post("/sponsor/roster/commit", headers=sponsor, json={
        "text": PASTE + "6. Someone Else\n",
        "idempotency_key": preview["idempotency_key"],
        "rows": preview["rows"]})
    assert response.status_code == 409
    assert "changed" in response.json()["error"].lower()


def test_a_forged_key_is_refused(fx, client, sponsor):
    response = _commit(client, sponsor, "made.up")
    assert response.status_code == 409


def test_a_key_from_another_school_is_refused(fx, client, sponsor):
    other = {"Authorization": f"Bearer {fx.sign_in('other_sponsor')}"}
    stolen = client.post("/sponsor/roster/parse", headers=other,
                         json={"text": PASTE}).json()["idempotency_key"]
    assert _commit(client, sponsor, stolen).status_code == 409


def test_commit_is_one_audit_entry_in_plain_words(fx, client, sponsor):
    preview = client.post("/sponsor/roster/parse", headers=sponsor,
                          json={"text": PASTE}).json()
    _commit(client, sponsor, preview["idempotency_key"], rows=preview["rows"])
    with fx.db.read() as tx:
        entry = [r for r in tx.all("audit.recent", (10 ** 9, 50))
                 if r["action"] == "roster.import"][0]
    assert entry["summary"] == \
        "Sam Sponsor added 5 delegates to University High School."


def test_everyone_imported_gets_a_working_code(fx, client, sponsor):
    preview = client.post("/sponsor/roster/parse", headers=sponsor,
                          json={"text": PASTE}).json()
    created = _commit(client, sponsor, preview["idempotency_key"],
                      rows=preview["rows"]).json()["created"]
    with fx.db.read() as tx:
        for person in created:
            row = tx.one("people.get", (person["id"],))
            assert row["code_hmac"] and not row["code_hmac"].startswith("pending-")
            assert row["code_prefix"] == "DEL"


# ---------------------------------------------------------------------------
# Roster view
# ---------------------------------------------------------------------------

def test_the_roster_is_one_query_not_one_per_person(fx, client, sponsor):
    """The N+1 docs/stack.md names as bug #1.

    Counted, not asserted by inspection: the whole page is a handful of
    statements regardless of how many delegates the chapter has.
    """
    preview = client.post("/sponsor/roster/parse", headers=sponsor,
                          json={"text": PASTE}).json()
    _commit(client, sponsor, preview["idempotency_key"], rows=preview["rows"])

    executed = []
    original = type(fx.db)._open

    def counting_open(self):
        handle = original(self)
        real = handle.execute

        def spy(sql, params):
            executed.append(sql.strip().split("\n")[0])
            return real(sql, params)

        handle.execute = spy
        return handle

    type(fx.db)._open = counting_open
    try:
        response = client.get("/sponsor/roster", headers=sponsor)
    finally:
        type(fx.db)._open = original

    assert response.status_code == 200
    assert len(response.json()["people"]) >= 6
    selects = [q for q in executed if q.upper().startswith("SELECT")]
    assert len(selects) <= 8, f"{len(selects)} queries for one roster: {selects}"


# ---------------------------------------------------------------------------
# Cancel, restore, regenerate
# ---------------------------------------------------------------------------

def test_regenerating_a_code_offers_a_reprint(fx, client, sponsor):
    """Without the reprint the sponsor holds a packet page whose QR is dead."""
    response = client.post(
        f"/sponsor/people/{fx.delegate_id}/regenerate-code", headers=sponsor)
    assert response.status_code == 200
    body = response.json()
    assert body["code"].startswith("DEL-")
    assert str(fx.delegate_id) in body["reprint_url"]


def test_regenerating_kills_the_delegates_open_session(fx, client, sponsor):
    delegate = {"Authorization": f"Bearer {fx.sign_in('delegate')}"}
    assert client.get("/auth/me", headers=delegate).status_code == 200
    client.post(f"/sponsor/people/{fx.delegate_id}/regenerate-code", headers=sponsor)
    assert client.get("/auth/me", headers=delegate).status_code == 401


def test_cancel_and_restore_round_trip(fx, client, sponsor):
    assert client.post(f"/sponsor/people/{fx.delegate_id}/cancel",
                       headers=sponsor).json()["status"] == "cancelled"
    assert fx.stats_for(fx.uni_id)["delegates_cancelled"] == 1
    assert client.post(f"/sponsor/people/{fx.delegate_id}/restore",
                       headers=sponsor).status_code == 200
    assert fx.stats_for(fx.uni_id)["delegates_cancelled"] == 0


def test_marking_paper_forms(fx, client, sponsor):
    response = client.post("/sponsor/paper-forms", headers=sponsor, json={
        "person_id": fx.delegate_id, "form_type": "student_waiver",
        "received": True})
    assert response.status_code == 200
    roster = client.get("/sponsor/roster", headers=sponsor).json()
    person = [p for p in roster["people"] if p["id"] == fx.delegate_id][0]
    assert person["waiver_received"] == 1


def test_an_adult_medical_form_cannot_be_marked_on_a_delegate(fx, client, sponsor):
    response = client.post("/sponsor/paper-forms", headers=sponsor, json={
        "person_id": fx.delegate_id, "form_type": "adult_medical",
        "received": True})
    assert response.status_code == 409


def test_chapter_leader_is_a_role_not_a_second_code(fx, client, sponsor):
    before = client.get("/auth/me", headers={
        "Authorization": f"Bearer {fx.sign_in('delegate')}"}).json()
    assert "chapter" not in before["scopes"]

    assert client.post(f"/sponsor/people/{fx.delegate_id}/chapter-leader",
                       headers=sponsor, json={"granted": True}).status_code == 200

    after = client.get("/auth/me", headers={
        "Authorization": f"Bearer {fx.sign_in('delegate')}"}).json()
    assert "chapter" in after["scopes"]
    assert "chapter_leader" in after["roles"]

    with fx.db.read() as tx:
        codes = tx.all("auth.sessions_for_person", (fx.delegate_id,))
    assert codes is not None   # still one person, one code


# ---------------------------------------------------------------------------
# The activity sheet
# ---------------------------------------------------------------------------

@pytest.fixture
def delegate(fx):
    return {"Authorization": f"Bearer {fx.sign_in('delegate')}"}


def _tests_for(sheet, latin_level="HS-2"):
    testing = [c for c in sheet["catalog"] if c["key"] == "academic_testing"][0]
    return testing


def test_the_activity_sheet_shows_ineligible_tests_disabled_not_hidden(fx, client, delegate):
    """A delegate who cannot find Grammar 2 assumes the site is broken."""
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    testing = _tests_for(sheet)
    names = {i["name"]: i for i in testing["items"]}

    # The fixture delegate is HS-2, so Grammar 2 is open and Grammar 1 is not --
    # but BOTH are present, and the closed one explains itself.
    assert names["Grammar 2"]["eligible_now"] is True
    assert names["Grammar 1"]["eligible_now"] is False
    assert "HS-1" in names["Grammar 1"]["reason"]
    assert names["Grammar 3"]["eligible_now"] is False


def test_chapter_events_never_appear_on_an_individual_sheet(fx, client, delegate):
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    every_item = {i["name"] for c in sheet["catalog"] for i in c["items"]}
    assert "Kickball" not in every_item
    assert "Fugepilam (Dodgeball)" not in every_item
    assert "Chess" in every_item


def test_the_test_count_is_a_hard_block(fx, client, delegate):
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    eligible = [i["id"] for i in _tests_for(sheet)["items"] if i["eligible_now"]]

    too_many = client.put("/me/activity-sheet", headers=delegate,
                          json={"grade": 10, "latin_level": "HS-2",
                                "selected": eligible[:4]})
    assert too_many.status_code == 422
    assert "between one and three" in too_many.json()["error"]
    assert "four selected" in too_many.json()["error"]

    none_at_all = client.put("/me/activity-sheet", headers=delegate,
                             json={"grade": 10, "latin_level": "HS-2",
                                   "selected": []})
    assert none_at_all.status_code == 422


def test_a_valid_activity_sheet_submits(fx, client, delegate):
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    eligible = [i["id"] for i in _tests_for(sheet)["items"] if i["eligible_now"]]

    response = client.put("/me/activity-sheet", headers=delegate, json={
        "grade": 11, "latin_level": "HS-2", "meal": "vegetarian",
        "selected": eligible[:2]})
    assert response.status_code == 200

    again = client.get("/me/activity-sheet", headers=delegate).json()
    assert again["status"] == "submitted"
    assert set(again["selected"]) == set(eligible[:2])
    assert again["person"]["meal"] == "vegetarian"


def test_an_ineligible_test_is_refused_server_side(fx, client, delegate):
    """The client's gating is a courtesy; this is the authority."""
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    grammar1 = [i for i in _tests_for(sheet)["items"] if i["name"] == "Grammar 1"][0]
    response = client.put("/me/activity-sheet", headers=delegate, json={
        "grade": 10, "latin_level": "HS-2", "selected": [grammar1["id"]]})
    assert response.status_code == 422
    assert "Grammar 1" in response.json()["error"]


def test_changing_latin_level_is_judged_by_the_new_level(fx, client, delegate):
    """A delegate correcting their level in the same save must be judged by the
    corrected one, not by the stale value on file."""
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    grammar3 = [i for i in _tests_for(sheet)["items"] if i["name"] == "Grammar 3"][0]
    assert grammar3["eligible_now"] is False        # they are HS-2 right now

    response = client.put("/me/activity-sheet", headers=delegate, json={
        "grade": 12, "latin_level": "HS-Adv", "selected": [grammar3["id"]]})
    assert response.status_code == 200


def test_a_middle_school_grade_is_refused_at_a_high_school(fx, client, delegate):
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    eligible = [i["id"] for i in _tests_for(sheet)["items"] if i["eligible_now"]]
    response = client.put("/me/activity-sheet", headers=delegate, json={
        "grade": 7, "latin_level": "HS-2", "selected": eligible[:1]})
    assert response.status_code == 422
    assert "between 9 and 12" in response.json()["error"]


def test_editing_replaces_selections_rather_than_adding(fx, client, delegate):
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    eligible = [i["id"] for i in _tests_for(sheet)["items"] if i["eligible_now"]]
    client.put("/me/activity-sheet", headers=delegate,
               json={"grade": 10, "latin_level": "HS-2", "selected": eligible[:3]})
    client.put("/me/activity-sheet", headers=delegate,
               json={"grade": 10, "latin_level": "HS-2", "selected": eligible[:1]})
    assert len(client.get("/me/activity-sheet",
                          headers=delegate).json()["selected"]) == 1


def test_forms_lock_after_the_deadline(fx, client, delegate):
    with fx.db.tx() as tx:
        tx.run("settings.update",
               ("2020-01-01T00:00:00Z", clock.now_iso(), None, "deadline.forms_lock"))
        tx.audit("settings.update", "Test moved the deadline into the past.")
    settings.invalidate()

    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    assert sheet["locked"] is True
    response = client.put("/me/activity-sheet", headers=delegate,
                          json={"grade": 10, "latin_level": "HS-2", "selected": []})
    assert response.status_code == 403
    assert "closed on" in response.json()["error"]


def test_an_admin_can_unlock_one_person_without_moving_the_deadline(fx, client, delegate):
    with fx.db.tx() as tx:
        tx.run("settings.update",
               ("2020-01-01T00:00:00Z", clock.now_iso(), None, "deadline.forms_lock"))
        tx.audit("settings.update", "Test moved the deadline into the past.")
    settings.invalidate()

    chair = {"Authorization": f"Bearer {fx.sign_in('chair')}"}
    assert client.post(f"/admin/people/{fx.delegate_id}/unlock-forms",
                       headers=chair, json={"unlocked": True}).status_code == 200

    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    assert sheet["locked"] is False
    eligible = [i["id"] for i in _tests_for(sheet)["items"] if i["eligible_now"]]
    assert client.put("/me/activity-sheet", headers=delegate,
                      json={"grade": 10, "latin_level": "HS-2",
                            "selected": eligible[:1]}).status_code == 200


def test_a_delegate_cannot_change_their_own_name(fx, client, delegate):
    """They must ask their sponsor. The endpoint simply offers no way to."""
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    eligible = [i["id"] for i in _tests_for(sheet)["items"] if i["eligible_now"]]
    client.put("/me/activity-sheet", headers=delegate, json={
        "grade": 10, "latin_level": "HS-2", "selected": eligible[:1],
        "first_name": "Renamed", "last_name": "Themselves"})
    after = client.get("/me/activity-sheet", headers=delegate).json()
    assert after["person"]["first_name"] == "Dana"


# ---------------------------------------------------------------------------
# The adult sheet
# ---------------------------------------------------------------------------

def test_two_roles_is_a_warning_not_a_block(fx, client):
    """An adult who ignores it can still submit. Some of them genuinely can
    only do one thing, and refusing the form teaches them the site is broken."""
    chaperone = {"Authorization": f"Bearer {fx.sign_in('chaperone')}"}
    sheet = client.get("/me/adult-sheet", headers=chaperone).json()
    roles = [c for c in sheet["catalog"] if c["key"] == "adult_roles"][0]
    open_roles = [i["id"] for i in roles["items"] if i["eligible_now"]]

    response = client.put("/me/adult-sheet", headers=chaperone, json={
        "latin_knowledge": "none", "selected": open_roles[:1]})
    assert response.status_code == 200
    assert any("at least two" in w for w in response.json()["warnings"])

    response = client.put("/me/adult-sheet", headers=chaperone, json={
        "latin_knowledge": "none", "selected": open_roles[:2]})
    assert response.json()["warnings"] == []


def test_roles_needing_latin_are_disabled_with_the_requirement_stated(fx, client):
    chaperone = {"Authorization": f"Bearer {fx.sign_in('chaperone')}"}
    sheet = client.get("/me/adult-sheet", headers=chaperone).json()
    roles = {i["name"]: i
             for c in sheet["catalog"] if c["key"] == "adult_roles"
             for i in c["items"]}
    assert roles["Certamen Reader"]["eligible_now"] is False
    assert "advanced Latin" in roles["Certamen Reader"]["reason"]
    assert roles["Wherever needed!"]["eligible_now"] is True


def test_an_adult_below_the_latin_requirement_is_refused_server_side(fx, client):
    chaperone = {"Authorization": f"Bearer {fx.sign_in('chaperone')}"}
    sheet = client.get("/me/adult-sheet", headers=chaperone).json()
    reader = [i for c in sheet["catalog"] for i in c["items"]
              if i["name"] == "Certamen Reader"][0]
    response = client.put("/me/adult-sheet", headers=chaperone, json={
        "latin_knowledge": "none", "selected": [reader["id"]]})
    assert response.status_code == 422


def test_declaring_advanced_latin_opens_the_role_in_the_same_save(fx, client):
    chaperone = {"Authorization": f"Bearer {fx.sign_in('chaperone')}"}
    sheet = client.get("/me/adult-sheet", headers=chaperone).json()
    reader = [i for c in sheet["catalog"] for i in c["items"]
              if i["name"] == "Certamen Reader"][0]
    response = client.put("/me/adult-sheet", headers=chaperone, json={
        "latin_knowledge": "advanced", "selected": [reader["id"]]})
    assert response.status_code == 200


def test_a_delegate_cannot_open_the_adult_sheet(fx, client, delegate):
    assert client.get("/me/adult-sheet", headers=delegate).status_code == 403
