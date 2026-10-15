"""The master schedule and Olympika: the rules, then the whole flow over HTTP.

The rules (heat dealing, bracket drawing, timing) are exercised directly with
a seeded random generator. The flow is exercised through the API as each of
the people who use it: the Logistics chair, the Athletics Director, delegates.
"""

from __future__ import annotations

import random

import pytest

from backend import api
from backend.lib import clock, olympika, schedule
from backend.lib.catalog import ValidationError

from .helpers import Fixture


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fx(tmp_path, monkeypatch):
    with Fixture(tmp_path) as f:
        monkeypatch.setattr(api, "_db", f.db)
        with f.db.tx() as tx:
            f.director_id = f._person(
                tx, "director", f.board_id, person_type="adult", adult_type="other",
                first="Ari", last="Athletic", role="athletics_director",
                email="ari@example.org")
            f.logistics_id = f._person(
                tx, "logistics", f.board_id, person_type="adult", adult_type="other",
                first="Lou", last="Logistics", role="logistics_chair",
                email="lou@example.org")
            tx.audit("person.create", "Test fixture added the Olympika chairs.")
        yield f


@pytest.fixture
def client(fx):
    from fastapi.testclient import TestClient
    with TestClient(api.app, raise_server_exceptions=False) as client:
        yield client


def as_(fx, who):
    return {"Authorization": f"Bearer {fx.sign_in(who)}"}


def add_delegates(fx, school_id, count, prefix):
    """`count` approved, active delegates at one chapter; returns their keys."""
    keys = []
    with fx.db.tx() as tx:
        for n in range(count):
            key = f"{prefix}{n}"
            fx._person(tx, key, school_id, first=f"{prefix.title()}{n}",
                       last="Runner", role="delegate", grade=9, latin_level="HS-1")
            keys.append(key)
        tx.audit("person.create", f"Test fixture added {count} delegates.")
    return keys


def event_named(fx, name):
    with fx.db.read() as tx:
        return next(dict(r) for r in tx.all("olympika.events") if r["name"] == name)


def make_event(client, fx, **fields):
    body = {"name": "100 m dash", "kind": "individual", "signup_open": True, **fields}
    response = client.post("/admin/athletics/events", json=body, headers=as_(fx, "director"))
    assert response.status_code == 200, response.text
    return response.json()["event"]


# ---------------------------------------------------------------------------
# Wall-clock times
# ---------------------------------------------------------------------------

def test_a_californian_clock_time_becomes_the_right_utc_instant():
    # March 12 2027 is before daylight time starts on the 14th: UTC-8.
    assert clock.local_to_utc("2027-03-12", "09:30") == "2027-03-12T17:30:00Z"
    # July is UTC-7. Nobody types the offset.
    assert clock.local_to_utc("2027-07-12", "09:30") == "2027-07-12T16:30:00Z"


def test_local_parts_is_the_inverse():
    for date, time in (("2027-03-12", "09:30"), ("2027-03-13", "23:45"),
                       ("2027-07-12", "00:05")):
        assert clock.local_parts(clock.local_to_utc(date, time)) == (date, time)


@pytest.mark.parametrize("payload", [
    {"date": "2027-03-12", "start": "25:00"},
    {"date": "2027-03-12", "start": "9.30"},
    {"date": "2027-13-45", "start": "09:30"},
    {"date": "2027-03-12", "start": "09:30", "end": "09:00"},
    {"start": "09:30"},
    {},
])
def test_a_bad_span_is_refused_with_a_sentence(payload):
    with pytest.raises(ValidationError) as caught:
        schedule.parse_span(payload)
    assert caught.value.errors


def test_an_edit_that_names_one_field_keeps_the_rest():
    current = {"starts_at": clock.local_to_utc("2027-03-12", "09:30"),
               "ends_at": clock.local_to_utc("2027-03-12", "10:15")}
    starts, ends = schedule.parse_span({"start": "09:45"}, current)
    assert clock.local_parts(starts) == ("2027-03-12", "09:45")
    assert clock.local_parts(ends) == ("2027-03-12", "10:15")


# ---------------------------------------------------------------------------
# Dealing heats
# ---------------------------------------------------------------------------

def entrants(*per_school):
    rows, next_id = [], 1
    for school, count in enumerate(per_school, start=1):
        for _ in range(count):
            rows.append({"id": next_id, "school_id": school})
            next_id += 1
    return rows


@pytest.mark.parametrize("people,heats", [(17, 4), (8, 8), (3, 5), (40, 6), (1, 1)])
def test_heats_differ_in_size_by_at_most_one(people, heats):
    dealt = olympika.deal_heats(entrants(people), list(range(1, heats + 1)),
                                random.Random(7))
    sizes = [sum(1 for _, h, _ in dealt if h == heat) for heat in range(1, heats + 1)]
    assert sum(sizes) == people
    assert max(sizes) - min(sizes) <= 1


def test_every_entrant_is_dealt_once_and_lanes_run_one_to_n():
    dealt = olympika.deal_heats(entrants(5, 4, 6), [10, 20, 30], random.Random(1))
    assert sorted(signup for signup, _, _ in dealt) == list(range(1, 16))
    for heat in (10, 20, 30):
        lanes = sorted(lane for _, h, lane in dealt if h == heat)
        assert lanes == list(range(1, len(lanes) + 1))


def test_one_chapters_runners_are_spread_across_heats():
    for seed in range(20):
        rows = entrants(3, 5, 4, 2)
        by_id = {r["id"]: r["school_id"] for r in rows}
        dealt = olympika.deal_heats(rows, [1, 2, 3, 4], random.Random(seed))
        for school in (1, 2, 3, 4):
            heats_used = [h for s, h, _ in dealt if by_id[s] == school]
            # No more than ceil(n / heats) of a chapter share a heat.
            worst = max(heats_used.count(h) for h in set(heats_used))
            assert worst <= -(-len(heats_used) // 4)


# ---------------------------------------------------------------------------
# Drawing brackets
# ---------------------------------------------------------------------------

def teams(count, schools=None):
    return [{"id": i, "school_id": (schools[i - 1] if schools else i)}
            for i in range(1, count + 1)]


def test_standard_seed_order():
    assert olympika.bracket_positions(2) == [1, 2]
    assert olympika.bracket_positions(4) == [1, 4, 2, 3]
    assert olympika.bracket_positions(8) == [1, 8, 4, 5, 2, 7, 3, 6]


@pytest.mark.parametrize("count", list(range(2, 34)))
def test_a_bracket_of_any_size_is_sound(count):
    order, games = olympika.draw_bracket(teams(count), random.Random(count))
    rounds = olympika.rounds_for(count)
    size = 2 ** rounds

    assert sorted(t["id"] for t in order) == list(range(1, count + 1))
    assert len(games) == size - 1
    first = [g for g in games if g["round"] == 1]
    assert len(first) == size // 2

    # Each team stands in exactly one first-round game.
    placed = [t for g in first for t in (g["team_a_id"], g["team_b_id"]) if t]
    assert sorted(placed) == list(range(1, count + 1))

    # The byes are exactly the empty places, and the bye team is through.
    byes = [g for g in first if olympika.is_bye(g)]
    assert len(byes) == size - count
    for game in byes:
        assert game["winner_id"] == (game["team_a_id"] or game["team_b_id"])
    # ...and already stands in the second round.
    if rounds > 1:
        second = {(g["slot"]): g for g in games if g["round"] == 2}
        for game in byes:
            nxt = second[game["slot"] // 2]
            side = "team_a_id" if game["slot"] % 2 == 0 else "team_b_id"
            assert nxt[side] == game["winner_id"]
    # Real games have no winner yet.
    assert all(g["winner_id"] is None for g in first if not olympika.is_bye(g))


def test_byes_go_to_the_best_seeds():
    order, games = olympika.draw_bracket(teams(6), random.Random(3))
    seeds = {t["id"]: seed for seed, t in enumerate(order, start=1)}
    bye_teams = [g["winner_id"] for g in games if olympika.is_bye(g)]
    assert sorted(seeds[t] for t in bye_teams) == [1, 2]


def test_the_draw_keeps_a_chapter_out_of_its_own_first_round_game():
    # Eight teams from four chapters, two each: it can always be avoided.
    schools = [1, 1, 2, 2, 3, 3, 4, 4]
    for seed in range(30):
        _, games = olympika.draw_bracket(teams(8, schools), random.Random(seed))
        for game in (g for g in games if g["round"] == 1):
            assert schools[game["team_a_id"] - 1] != schools[game["team_b_id"] - 1]


def test_fewer_than_two_teams_cannot_make_a_bracket():
    with pytest.raises(ValidationError):
        olympika.draw_bracket(teams(1), random.Random(0))


def test_round_names():
    assert [olympika.round_name(r, 4) for r in (1, 2, 3, 4)] == [
        "Round of 16", "Quarterfinals", "Semifinals", "Final"]
    assert [olympika.round_name(r, 2) for r in (1, 2)] == ["Semifinals", "Final"]
    assert olympika.round_name(1, 1) == "Final"


def test_games_are_timed_in_waves_by_field_and_round():
    order, games = olympika.draw_bracket(teams(8), random.Random(0))
    for number, game in enumerate(games, start=100):
        game["id"] = number
    timed = olympika.time_games(games, "2027-03-13T20:00:00Z", 30, ["A", "B"])
    first = [timed[g["id"]] for g in games if g["round"] == 1]
    # Four games, two fields: two waves.
    assert sorted(s for s, _, _ in first) == ["2027-03-13T20:00:00Z"] * 2 + [
        "2027-03-13T20:30:00Z"] * 2
    assert {f for _, _, f in first} == {"A", "B"}
    # The next round starts when the last wave finished, and nothing overlaps
    # on a field.
    semi = [timed[g["id"]] for g in games if g["round"] == 2]
    assert min(s for s, _, _ in semi) == "2027-03-13T21:00:00Z"
    for field in ("A", "B"):
        spans = sorted((s, e) for s, e, f in timed.values() if f == field)
        for (_, end), (start, _) in zip(spans, spans[1:]):
            assert end <= start


def test_a_bye_is_never_timed():
    _, games = olympika.draw_bracket(teams(6), random.Random(0))
    for number, game in enumerate(games, start=1):
        game["id"] = number
    timed = olympika.time_games(games, "2027-03-13T20:00:00Z", 30, [])
    assert not {g["id"] for g in games if olympika.is_bye(g)} & set(timed)
    assert len(timed) == sum(1 for g in games if not olympika.is_bye(g))


# ---------------------------------------------------------------------------
# The Logistics chair
# ---------------------------------------------------------------------------

def test_the_logistics_chair_adds_edits_and_deletes_entries(fx, client):
    headers = as_(fx, "logistics")
    made = client.post("/admin/schedule", headers=headers, json={
        "title": "Opening ceremony", "location": "Auditorium",
        "date": "2027-03-12", "start": "09:00", "end": "09:45"})
    assert made.status_code == 200, made.text
    item = made.json()["item"]
    assert (item["date"], item["start"], item["end"]) == ("2027-03-12", "09:00", "09:45")
    assert item["editable"] is True

    changed = client.patch(f"/admin/schedule/{item['id']}", headers=headers,
                           json={"start": "09:15", "title": "Opening assembly"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["item"]["start"] == "09:15"
    assert changed.json()["item"]["end"] == "09:45"          # kept

    assert client.delete(f"/admin/schedule/{item['id']}", headers=headers).status_code == 200
    assert client.get("/admin/schedule", headers=headers).json()["items"] == []

    actions = fx.audit_actions()
    assert {"schedule.create", "schedule.update", "schedule.delete"} <= set(actions)


def test_the_public_sees_published_entries_only_and_no_one_needs_a_credential(fx, client):
    headers = as_(fx, "logistics")
    for title, published in (("Lunch", True), ("Secret plan", False)):
        client.post("/admin/schedule", headers=headers, json={
            "title": title, "date": "2027-03-12", "start": "12:00",
            "published": published})
    body = client.get("/public/schedule").json()
    assert [i["title"] for i in body["items"]] == ["Lunch"]
    assert set(body["now"]) == {"date", "time"}
    assert "Secret plan" in str(client.get("/admin/schedule", headers=headers).json())


def test_the_schedule_is_in_time_order(fx, client):
    headers = as_(fx, "logistics")
    for title, start in (("Dinner", "18:00"), ("Breakfast", "07:30"), ("Lunch", "12:00")):
        client.post("/admin/schedule", headers=headers,
                    json={"title": title, "date": "2027-03-12", "start": start})
    titles = [i["title"] for i in client.get("/public/schedule").json()["items"]]
    assert titles == ["Breakfast", "Lunch", "Dinner"]


def test_only_the_logistics_chair_edits_the_schedule(fx, client):
    body = {"title": "x", "date": "2027-03-12", "start": "09:00"}
    for who in ("delegate", "uni_sponsor", "chair", "director"):
        assert client.post("/admin/schedule", json=body,
                           headers=as_(fx, who)).status_code == 403, who
    # `*` holds every scope.
    assert client.post("/admin/schedule", json=body,
                       headers=as_(fx, "admin")).status_code == 200


# ---------------------------------------------------------------------------
# Individual events: sign-up, heats, the push to the master schedule
# ---------------------------------------------------------------------------

def set_heats(client, fx, event_id, **payload):
    response = client.put(f"/admin/athletics/events/{event_id}/heats",
                          headers=as_(fx, "director"), json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_delegate_signs_up_and_withdraws(fx, client):
    event = make_event(client, fx)
    headers = as_(fx, "delegate")

    mine = client.get("/me/olympika", headers=headers).json()
    entry = next(e for e in mine["events"] if e["id"] == event["id"])
    assert mine["can_enter"] and entry["entry"] is None

    assert client.post(f"/me/olympika/{event['id']}", json={}, headers=headers).status_code == 200
    again = client.post(f"/me/olympika/{event['id']}", json={}, headers=headers)
    assert again.status_code == 422 and "already signed up" in again.text

    detail = client.get(f"/admin/athletics/events/{event['id']}",
                        headers=as_(fx, "director")).json()
    assert [s["last_name"] for s in detail["signups"]] == ["Delegate"]
    assert detail["signups"][0]["school_name"] == "University High School"

    assert client.delete(f"/me/olympika/{event['id']}", headers=headers).status_code == 200
    detail = client.get(f"/admin/athletics/events/{event['id']}",
                        headers=as_(fx, "director")).json()
    assert detail["signups"] == []


def test_signing_up_needs_an_open_event(fx, client):
    event = make_event(client, fx, signup_open=False)
    response = client.post(f"/me/olympika/{event['id']}", json={},
                           headers=as_(fx, "delegate"))
    assert response.status_code == 422 and "not open" in response.text
    client.patch(f"/admin/athletics/events/{event['id']}", json={"signup_open": True},
                 headers=as_(fx, "director"))
    assert client.post(f"/me/olympika/{event['id']}", json={},
                       headers=as_(fx, "delegate")).status_code == 200


def test_a_pending_delegate_cannot_sign_up_until_approved(fx, client):
    event = make_event(client, fx)
    with fx.db.tx() as tx:
        tx.run("people.set_approval", ("pending", clock.now_iso(), fx.delegate_id))
        tx.audit("person.update", "Test made a delegate pending.")
    headers = as_(fx, "delegate")
    assert client.get("/me/olympika", headers=headers).json()["can_enter"] is False
    response = client.post(f"/me/olympika/{event['id']}", json={}, headers=headers)
    assert response.status_code == 422 and "approve" in response.text


def test_an_adult_cannot_sign_up(fx, client):
    event = make_event(client, fx)
    assert client.post(f"/me/olympika/{event['id']}", json={},
                       headers=as_(fx, "uni_sponsor")).status_code == 403


def test_a_chapter_limit_applies_to_each_event(fx, client):
    event = make_event(client, fx, max_per_school=2)
    keys = add_delegates(fx, fx.uni_id, 2, "extra") + ["delegate"]
    results = [client.post(f"/me/olympika/{event['id']}", json={},
                           headers=as_(fx, key)).status_code for key in keys]
    assert results == [200, 200, 422]
    # Another chapter is unaffected.
    assert client.post(f"/me/olympika/{event['id']}", json={},
                       headers=as_(fx, "other_delegate")).status_code == 200


def test_the_director_sets_heats_and_they_reach_the_master_schedule(fx, client):
    event = make_event(client, fx, location="Track")
    set_heats(client, fx, event["id"], count=3, date="2027-03-13", start="10:00",
              minutes_between=20, minutes_long=15)

    items = client.get("/public/schedule").json()["items"]
    assert [(i["title"], i["start"], i["end"], i["location"], i["source"])
            for i in items] == [
        ("100 m dash — Heat 1", "10:00", "10:15", "Track", "olympika"),
        ("100 m dash — Heat 2", "10:20", "10:35", "Track", "olympika"),
        ("100 m dash — Heat 3", "10:40", "10:55", "Track", "olympika"),
    ]

    # Move one heat: the schedule follows in the same request.
    detail = client.get(f"/admin/athletics/events/{event['id']}",
                        headers=as_(fx, "director")).json()
    second = detail["heats"][1]
    moved = client.patch(f"/admin/athletics/heats/{second['id']}",
                         headers=as_(fx, "director"),
                         json={"start": "14:00", "end": "14:20", "label": "Final"})
    assert moved.status_code == 200, moved.text
    items = client.get("/public/schedule").json()["items"]
    assert [i["title"] for i in items] == [
        "100 m dash — Heat 1", "100 m dash — Heat 3", "100 m dash — Final"]
    assert items[-1]["start"] == "14:00"

    # Fewer heats: the removed one leaves the schedule.
    set_heats(client, fx, event["id"], count=1)
    items = client.get("/public/schedule").json()["items"]
    assert [i["title"] for i in items] == ["100 m dash"]            # one heat: no number

    # Renaming the event renames its entries.
    client.patch(f"/admin/athletics/events/{event['id']}", json={"name": "Sprint"},
                 headers=as_(fx, "director"))
    assert [i["title"] for i in client.get("/public/schedule").json()["items"]] == ["Sprint"]

    # Deleting it takes them off.
    client.delete(f"/admin/athletics/events/{event['id']}", headers=as_(fx, "director"))
    assert client.get("/public/schedule").json()["items"] == []


def test_the_logistics_chair_cannot_touch_what_athletics_scheduled(fx, client):
    event = make_event(client, fx)
    set_heats(client, fx, event["id"], count=1, date="2027-03-13", start="10:00")
    listed = client.get("/admin/schedule", headers=as_(fx, "logistics")).json()["items"]
    assert len(listed) == 1 and listed[0]["editable"] is False

    for method, body in (("patch", {"title": "x"}), ("delete", None)):
        response = getattr(client, method)(
            f"/admin/schedule/{listed[0]['id']}", headers=as_(fx, "logistics"),
            **({"json": body} if body else {}))
        assert response.status_code == 422
        assert "Athletics" in response.text


def test_assign_heats_deals_every_entrant_and_tells_each_delegate(fx, client):
    event = make_event(client, fx)
    keys = (add_delegates(fx, fx.uni_id, 5, "uni")
            + add_delegates(fx, fx.other_id, 4, "riv"))
    for key in keys:
        assert client.post(f"/me/olympika/{event['id']}", json={},
                           headers=as_(fx, key)).status_code == 200

    director = as_(fx, "director")
    # Nothing to deal into yet.
    refused = client.post(f"/admin/athletics/events/{event['id']}/assign", headers=director)
    assert refused.status_code == 422 and "heats" in refused.text

    set_heats(client, fx, event["id"], count=3, date="2027-03-13", start="09:00",
              minutes_between=10)
    done = client.post(f"/admin/athletics/events/{event['id']}/assign", headers=director)
    assert done.status_code == 200, done.text
    detail = done.json()
    assert all(s["heat_id"] and s["lane"] for s in detail["signups"])
    assert sorted(h["entrants"] for h in detail["heats"]) == [3, 3, 3]

    mine = next(e for e in client.get("/me/olympika", headers=as_(fx, keys[0])).json()["events"]
                if e["id"] == event["id"])["entry"]
    assert mine["heat_number"] in (1, 2, 3) and mine["lane"] >= 1
    assert mine["start"] in ("09:00", "09:10", "09:20")


def test_the_director_can_move_and_remove_entrants(fx, client):
    event = make_event(client, fx)
    client.post(f"/me/olympika/{event['id']}", json={}, headers=as_(fx, "delegate"))
    set_heats(client, fx, event["id"], count=2)
    director = as_(fx, "director")
    detail = client.get(f"/admin/athletics/events/{event['id']}", headers=director).json()
    signup, heat = detail["signups"][0], detail["heats"][1]

    moved = client.patch(f"/admin/athletics/signups/{signup['id']}", headers=director,
                         json={"heat_id": heat["id"], "lane": 4})
    assert moved.status_code == 200, moved.text
    assert (moved.json()["signups"][0]["heat_number"], moved.json()["signups"][0]["lane"]) == (2, 4)

    elsewhere = make_event(client, fx, name="Mile")
    other = set_heats(client, fx, elsewhere["id"], count=1)["heats"][0]
    wrong = client.patch(f"/admin/athletics/signups/{signup['id']}", headers=director,
                         json={"heat_id": other["id"]})
    assert wrong.status_code == 422

    gone = client.delete(f"/admin/athletics/signups/{signup['id']}", headers=director)
    assert gone.status_code == 200 and gone.json()["signups"] == []


def test_cancelled_delegates_are_not_dealt_into_heats(fx, client):
    event = make_event(client, fx)
    for key in ("delegate", "other_delegate"):
        client.post(f"/me/olympika/{event['id']}", json={}, headers=as_(fx, key))
    with fx.db.tx() as tx:
        tx.run("people.cancel", ("cancelled", clock.now_iso(), clock.now_iso(),
                            fx.other_delegate_id))
        tx.audit("person.cancel", "Test cancelled a delegate.")
    detail = client.get(f"/admin/athletics/events/{event['id']}",
                        headers=as_(fx, "director")).json()
    assert [s["last_name"] for s in detail["signups"]] == ["Delegate"]


def test_events_are_added_renamed_and_removed(fx, client):
    director = as_(fx, "director")
    event = make_event(client, fx, name="Long jump")
    clash = client.post("/admin/athletics/events", headers=director,
                        json={"name": "long JUMP", "kind": "individual"})
    assert clash.status_code == 422 and "already" in clash.text

    bad = client.post("/admin/athletics/events", headers=director, json={"name": "", "kind": "x"})
    assert bad.status_code == 422 and len(bad.json()["errors"]) == 2

    client.post(f"/me/olympika/{event['id']}", json={}, headers=as_(fx, "delegate"))
    switched = client.patch(f"/admin/athletics/events/{event['id']}", headers=director,
                            json={"kind": "team"})
    assert switched.status_code == 422 and "already entered" in switched.text

    removed = client.delete(f"/admin/athletics/events/{event['id']}", headers=director)
    assert removed.status_code == 200 and removed.json()["removed"] == 1
    names = [e["name"] for e in client.get("/admin/athletics", headers=director).json()["events"]]
    assert "Long jump" not in names


def test_heats_belong_to_individual_events_and_brackets_to_teams(fx, client):
    director = as_(fx, "director")
    frisbee = event_named(fx, "Ultimate Frisbee")
    race = make_event(client, fx)
    assert client.put(f"/admin/athletics/events/{frisbee['id']}/heats",
                      json={"count": 2}, headers=director).status_code == 422
    assert client.post(f"/admin/athletics/events/{race['id']}/bracket", json={},
                       headers=director).status_code == 422


# ---------------------------------------------------------------------------
# Team events: Ultimate Frisbee
# ---------------------------------------------------------------------------

def frisbee_id(fx):
    return event_named(fx, "Ultimate Frisbee")["id"]


def open_frisbee(client, fx, **fields):
    response = client.patch(f"/admin/athletics/events/{frisbee_id(fx)}",
                            headers=as_(fx, "director"),
                            json={"signup_open": True, **fields})
    assert response.status_code == 200, response.text


def sign_up_teams(client, fx, keys):
    for key in keys:
        response = client.post(f"/me/olympika/{frisbee_id(fx)}",
                               json={"team_name": f"Team {key}"}, headers=as_(fx, key))
        assert response.status_code == 200, response.text


def test_ultimate_frisbee_exists_as_a_team_event_and_starts_closed(fx):
    frisbee = event_named(fx, "Ultimate Frisbee")
    assert frisbee["kind"] == "team" and frisbee["signup_open"] == 0


def test_one_delegate_signs_up_a_team_and_is_its_captain(fx, client):
    open_frisbee(client, fx)
    headers = as_(fx, "delegate")
    made = client.post(f"/me/olympika/{frisbee_id(fx)}", json={"team_name": "  Mighty   Owls "},
                       headers=headers)
    assert made.status_code == 200, made.text

    entry = next(e for e in client.get("/me/olympika", headers=headers).json()["events"]
                 if e["id"] == frisbee_id(fx))["entry"]
    assert entry["team"] == "Mighty Owls"

    again = client.post(f"/me/olympika/{frisbee_id(fx)}", json={}, headers=headers)
    assert again.status_code == 422 and "already signed up a team" in again.text

    detail = client.get(f"/admin/athletics/events/{frisbee_id(fx)}",
                        headers=as_(fx, "director")).json()
    assert [(t["name"], t["last_name"], t["school_name"]) for t in detail["teams"]] == [
        ("Mighty Owls", "Delegate", "University High School")]

    renamed = client.patch(f"/me/olympika/{frisbee_id(fx)}", json={"team_name": "Owls II"},
                           headers=headers)
    assert renamed.status_code == 200
    assert client.delete(f"/me/olympika/{frisbee_id(fx)}", headers=headers).status_code == 200


def test_an_unnamed_team_takes_its_chapters_name_with_a_number(fx, client):
    open_frisbee(client, fx)
    keys = add_delegates(fx, fx.uni_id, 2, "cap")
    names = []
    for key in ["delegate"] + keys:
        client.post(f"/me/olympika/{frisbee_id(fx)}", json={}, headers=as_(fx, key))
    detail = client.get(f"/admin/athletics/events/{frisbee_id(fx)}",
                        headers=as_(fx, "director")).json()
    names = sorted(t["name"] for t in detail["teams"])
    assert names == ["University High School", "University High School 2",
                     "University High School 3"]


def test_two_teams_cannot_share_a_name(fx, client):
    open_frisbee(client, fx)
    client.post(f"/me/olympika/{frisbee_id(fx)}", json={"team_name": "Hawks"},
                headers=as_(fx, "delegate"))
    clash = client.post(f"/me/olympika/{frisbee_id(fx)}", json={"team_name": "hawks"},
                        headers=as_(fx, "other_delegate"))
    assert clash.status_code == 422 and "Pick another" in clash.text


def test_a_chapter_can_be_limited_to_one_team(fx, client):
    open_frisbee(client, fx, max_per_school=1)
    cap = add_delegates(fx, fx.uni_id, 1, "cap")[0]
    assert client.post(f"/me/olympika/{frisbee_id(fx)}", json={},
                       headers=as_(fx, "delegate")).status_code == 200
    second = client.post(f"/me/olympika/{frisbee_id(fx)}", json={}, headers=as_(fx, cap))
    assert second.status_code == 422 and "most it can" in second.text


def draw(client, fx, **payload):
    response = client.post(f"/admin/athletics/events/{frisbee_id(fx)}/bracket",
                           json=payload, headers=as_(fx, "director"))
    assert response.status_code == 200, response.text
    return response.json()


def test_form_bracket_needs_two_teams(fx, client):
    open_frisbee(client, fx)
    sign_up_teams(client, fx, ["delegate"])
    response = client.post(f"/admin/athletics/events/{frisbee_id(fx)}/bracket", json={},
                           headers=as_(fx, "director"))
    assert response.status_code == 422 and "two teams" in response.text


def test_form_bracket_draws_times_and_publishes_the_games(fx, client):
    open_frisbee(client, fx, location="Main lawn")
    keys = (["delegate", "other_delegate"] + add_delegates(fx, fx.uni_id, 3, "u")
            + add_delegates(fx, fx.other_id, 3, "r"))
    sign_up_teams(client, fx, keys)                                # eight teams

    body = draw(client, fx, date="2027-03-13", start="13:00", minutes=30,
                fields="Field A, Field B")
    assert body["rounds"] == 3
    games = body["matches"]
    assert len(games) == 7 and not any(g["bye"] for g in games)
    assert {g["field"] for g in games if g["round"] == 1} == {"Field A", "Field B"}
    assert sorted(t["seed"] for t in body["teams"]) == list(range(1, 9))

    items = client.get("/public/schedule").json()["items"]
    assert [(i["title"], i["start"], i["end"]) for i in items] == [
        ("Ultimate Frisbee — Quarterfinals", "13:00", "14:00"),
        ("Ultimate Frisbee — Semifinals", "14:00", "14:30"),
        ("Ultimate Frisbee — Final", "14:30", "15:00"),
    ]
    assert items[0]["location"] == "Main lawn · Field A, Field B"

    # A delegate sees their own team's game.
    mine = next(e for e in client.get("/me/olympika", headers=as_(fx, "delegate")).json()["events"]
                if e["id"] == frisbee_id(fx))["entry"]
    assert mine["games"][0]["round_name"] == "Quarterfinals"
    assert mine["games"][0]["opponent"].startswith("Team ")
    assert mine["games"][0]["start"] in ("13:00", "13:30")   # either wave


def test_results_advance_the_winner_and_are_guarded(fx, client):
    open_frisbee(client, fx)
    sign_up_teams(client, fx, ["delegate", "other_delegate"] + add_delegates(fx, fx.uni_id, 2, "u"))
    body = draw(client, fx)                                       # four teams: 2 rounds
    director = as_(fx, "director")
    first = [g for g in body["matches"] if g["round"] == 1]
    final = next(g for g in body["matches"] if g["round"] == 2)
    assert final["team_a_id"] is None and final["team_b_id"] is None

    # The final cannot be scored before its teams are known.
    early = client.patch(f"/admin/athletics/matches/{final['id']}", headers=director,
                         json={"winner_id": first[0]["team_a_id"]})
    assert early.status_code == 422 and "waiting" in early.text

    # Not a team in the game.
    stranger = client.patch(f"/admin/athletics/matches/{first[0]['id']}", headers=director,
                            json={"winner_id": first[1]["team_a_id"]})
    assert stranger.status_code == 422

    scored = client.patch(f"/admin/athletics/matches/{first[0]['id']}", headers=director,
                          json={"winner_id": first[0]["team_b_id"], "score_a": 7, "score_b": 11})
    assert scored.status_code == 200, scored.text
    final = next(g for g in scored.json()["matches"] if g["round"] == 2)
    assert final["team_a_id"] == first[0]["team_b_id"]

    second = client.patch(f"/admin/athletics/matches/{first[1]['id']}", headers=director,
                          json={"winner_id": first[1]["team_a_id"]})
    final = next(g for g in second.json()["matches"] if g["round"] == 2)
    assert final["team_b_id"] == first[1]["team_a_id"]

    # Changing a result is fine until the next round is played from it...
    flipped = client.patch(f"/admin/athletics/matches/{first[0]['id']}", headers=director,
                           json={"winner_id": first[0]["team_a_id"]})
    assert flipped.status_code == 200
    final = next(g for g in flipped.json()["matches"] if g["round"] == 2)
    assert final["team_a_id"] == first[0]["team_a_id"]

    champion = final["team_a_id"]
    client.patch(f"/admin/athletics/matches/{final['id']}", headers=director,
                 json={"winner_id": champion})
    # ...and not after.
    blocked = client.patch(f"/admin/athletics/matches/{first[0]['id']}", headers=director,
                           json={"winner_id": first[0]["team_b_id"]})
    assert blocked.status_code == 422 and "Clear that result first" in blocked.text

    # Clearing the final and then the semifinal puts things back.
    client.patch(f"/admin/athletics/matches/{final['id']}", headers=director,
                 json={"winner_id": None})
    cleared = client.patch(f"/admin/athletics/matches/{first[0]['id']}", headers=director,
                           json={"winner_id": None})
    assert cleared.status_code == 200
    assert next(g for g in cleared.json()["matches"] if g["round"] == 2)["team_a_id"] is None


def test_the_director_can_retime_and_move_a_game(fx, client):
    open_frisbee(client, fx)
    sign_up_teams(client, fx, ["delegate", "other_delegate"])
    body = draw(client, fx, date="2027-03-13", start="13:00", minutes=30)
    director = as_(fx, "director")
    game = body["matches"][0]

    moved = client.patch(f"/admin/athletics/matches/{game['id']}", headers=director,
                         json={"start": "16:00", "end": "16:45", "field": "Field C"})
    assert moved.status_code == 200, moved.text
    [item] = client.get("/public/schedule").json()["items"]
    assert (item["title"], item["start"], item["end"]) == (
        "Ultimate Frisbee — Final", "16:00", "16:45")

    retimed = client.post(f"/admin/athletics/events/{frisbee_id(fx)}/bracket/times",
                          headers=director, json={"date": "2027-03-13", "start": "09:00",
                                                  "minutes": 20})
    assert retimed.status_code == 200, retimed.text
    [item] = client.get("/public/schedule").json()["items"]
    assert item["start"] == "09:00"


def test_clearing_the_bracket_takes_its_games_off_the_schedule(fx, client):
    open_frisbee(client, fx)
    sign_up_teams(client, fx, ["delegate", "other_delegate"])
    draw(client, fx, date="2027-03-13", start="13:00")
    assert client.get("/public/schedule").json()["items"]
    cleared = client.delete(f"/admin/athletics/events/{frisbee_id(fx)}/bracket",
                            headers=as_(fx, "director"))
    assert cleared.status_code == 200 and cleared.json()["matches"] == []
    assert client.get("/public/schedule").json()["items"] == []


def test_a_drawn_bracket_cannot_be_walked_out_of_by_one_team(fx, client):
    open_frisbee(client, fx)
    sign_up_teams(client, fx, ["delegate", "other_delegate"])
    draw(client, fx)
    assert client.delete(f"/me/olympika/{frisbee_id(fx)}",
                         headers=as_(fx, "delegate")).status_code == 422
    late = add_delegates(fx, fx.uni_id, 1, "late")[0]
    assert client.post(f"/me/olympika/{frisbee_id(fx)}", json={},
                       headers=as_(fx, late)).status_code == 422
    team = client.get(f"/admin/athletics/events/{frisbee_id(fx)}",
                      headers=as_(fx, "director")).json()["teams"][0]
    assert client.delete(f"/admin/athletics/teams/{team['id']}",
                         headers=as_(fx, "director")).status_code == 422


def test_the_director_can_rename_and_remove_a_team_before_the_draw(fx, client):
    open_frisbee(client, fx)
    sign_up_teams(client, fx, ["delegate", "other_delegate"])
    director = as_(fx, "director")
    teams_ = client.get(f"/admin/athletics/events/{frisbee_id(fx)}", headers=director).json()["teams"]
    renamed = client.patch(f"/admin/athletics/teams/{teams_[0]['id']}", headers=director,
                           json={"name": "Renamed"})
    assert renamed.status_code == 200
    removed = client.delete(f"/admin/athletics/teams/{teams_[1]['id']}", headers=director)
    assert removed.status_code == 200
    assert [t["name"] for t in removed.json()["teams"]] == ["Renamed"]


# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------

def test_redacting_a_delegate_deletes_their_signups_and_team(fx, client):
    race = make_event(client, fx)
    open_frisbee(client, fx)
    client.post(f"/me/olympika/{race['id']}", json={}, headers=as_(fx, "delegate"))
    sign_up_teams(client, fx, ["delegate"])
    res = client.post(f"/sponsor/people/{fx.delegate_id}/redact", headers=as_(fx, "uni_sponsor"))
    assert res.status_code == 200, res.text

    with fx.db.read() as tx:
        assert tx.all("olympika.signups_for_person", (fx.delegate_id,)) == []
        assert tx.all("olympika.teams_for_captain", (fx.delegate_id,)) == []


def test_redacting_a_captain_after_the_draw_keeps_the_bracket_whole(fx, client):
    open_frisbee(client, fx)
    sign_up_teams(client, fx, ["delegate", "other_delegate"])
    draw(client, fx)
    client.post(f"/sponsor/people/{fx.delegate_id}/redact", headers=as_(fx, "uni_sponsor"))

    detail = client.get(f"/admin/athletics/events/{frisbee_id(fx)}",
                        headers=as_(fx, "director")).json()
    assert len(detail["teams"]) == 2 and len(detail["matches"]) == 1
    orphan = next(t for t in detail["teams"] if t["captain_id"] is None)
    assert orphan["name"].startswith("Withdrawn team")
    assert orphan["first_name"] is None
    assert "Delegate" not in str(detail)
