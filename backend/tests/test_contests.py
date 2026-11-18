"""Pre-convention contests, end to end: entering, judging blind, and results.

Drive is a folder under the test's tmp_path (drive.LocalDrive), so a file
entry really is written somewhere and really is read back for the judge.
"""

from __future__ import annotations

import base64
import io
import zipfile

import pytest

from backend import api
from backend.lib import contests, drive

from .helpers import Fixture


@pytest.fixture
def fx(tmp_path, monkeypatch):
    with Fixture(tmp_path) as f:
        monkeypatch.setattr(api, "_db", f.db)
        local = drive.LocalDrive(str(tmp_path / "drive"))
        drive.use(local)
        f.drive_root = local.root
        with f.db.tx() as tx:
            f.judge_id = f._person(
                tx, "judge", f.board_id, person_type="adult", adult_type="other",
                first="Jo", last="Judge", role="contest_judge",
                email="judge@example.org")
            f.judge2_id = f._person(
                tx, "judge2", f.board_id, person_type="adult", adult_type="other",
                first="Lee", last="Second", role="contest_judge",
                email="judge2@example.org")
            f.academics_id = f._person(
                tx, "academics", f.board_id, person_type="adult", adult_type="other",
                first="Ari", last="Academic", role="academics_chair",
                email="aa@example.org")
            tx.audit("person.create", "Test fixture added two judges and a chair.")
        try:
            yield f
        finally:
            drive.use(None)


@pytest.fixture
def client(fx):
    from fastapi.testclient import TestClient
    with TestClient(api.app, raise_server_exceptions=False) as client:
        yield client


def as_(fx, who):
    return {"Authorization": f"Bearer {fx.sign_in(who)}"}


def item(client, fx, key):
    with fx.db.read() as tx:
        return next(c["item_id"] for c in contests.load(tx) if c["key"] == key)


def docx(words: int) -> bytes:
    body = " ".join(["word"] * words)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body>'
           f'<w:p><w:r><w:t>The Tale</w:t></w:r></w:p>'
           f'<w:p><w:r><w:t>{body}</w:t></w:r></w:p>'
           '</w:body></w:document>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return out.getvalue()


def upload(name: str, data: bytes) -> dict:
    return {"name": name, "data": base64.b64encode(data).decode()}


# ---------------------------------------------------------------------------
# Rules that need no HTTP
# ---------------------------------------------------------------------------

def test_the_length_penalty_counts_started_hundreds():
    myth = {"words_penalty": 3, "min_words": 500, "max_words": 1200}
    assert contests.penalty_for(myth, 800) == 0
    assert contests.penalty_for(myth, 1200) == 0
    assert contests.penalty_for(myth, 1210) == 3
    assert contests.penalty_for(myth, 1301) == 6
    assert contests.penalty_for(myth, 450) == 3
    assert contests.penalty_for(myth, None) == 0


def test_words_are_counted_as_a_reader_counts_them():
    # Don't / stop / the / well-known / Hercules / twice -- the dash is not a word.
    assert contests.count_words("Don't stop — the well-known Hercules, twice.") == 6


def test_divisions():
    grade = {"divisions": "level_grade"}
    hs, ms = {"name": "H", "level": "HS"}, {"name": "M", "level": "MS"}
    assert contests.division_for(grade, hs, {"grade": 9}) == "HS 9–10"
    assert contests.division_for(grade, hs, {"grade": 12}) == "HS 11–12"
    assert contests.division_for(grade, ms, {"grade": 7}) == "MS"
    assert contests.division_for({"divisions": "level"}, hs, None) == "HS"
    assert contests.division_for({"divisions": "none"}, hs, None) == "Open"
    with pytest.raises(contests.ValidationError):
        contests.division_for(grade, hs, {"grade": None})


def test_digital_art_has_exactly_the_seven_latin_divisions():
    art = {"divisions": "latin_level"}
    hs, ms = {"name": "H", "level": "HS"}, {"name": "M", "level": "MS"}
    got = {level: contests.division_for(art, hs if level.startswith("HS") else ms,
                                        {"latin_level": level})
           for level in ("MS-1", "MS-2", "MS-3", "HS-1", "HS-2", "HS-3", "HS-Adv")}
    assert got == {"MS-1": "MS-I", "MS-2": "MS-II", "MS-3": "MS-III",
                   "HS-1": "HS-I", "HS-2": "HS-II",
                   "HS-3": "HS-III", "HS-Adv": "HS-Advanced"}
    with pytest.raises(contests.ValidationError):
        contests.division_for(art, hs, {"latin_level": None})


def test_a_renamed_file_is_refused():
    art = {"name": "Digital Art/Poster", "accepted": ["png", "pdf"]}
    with pytest.raises(contests.ValidationError):
        contests.check_file(art, "poster.png", b"MZ\x90\x00 not a png")
    with pytest.raises(contests.ValidationError):
        contests.check_file(art, "poster.exe", b"MZ")
    assert contests.check_file(art, "poster.PNG", b"\x89PNG\r\n\x1a\nrest") == \
        ("png", "image/png")


def test_the_seeded_contests_match_the_convention_book(fx):
    with fx.db.read() as tx:
        by_key = {c["key"]: c for c in contests.load(tx)}
    assert set(by_key) == {"digital_art", "modern_myth", "poetry",
                           "slogan_english", "slogan_latin", "publicity"}
    assert len(by_key["publicity"]["facet_list"]) == 8
    assert by_key["publicity"]["must_attend"] == 0
    # Every contest awards three places until the Academics chairs say otherwise.
    assert {c["places"] for c in by_key.values()} == {3}
    view = contests.public_view(by_key["modern_myth"])
    assert view["places"] == 3
    assert "criteria" not in view and "max_points" not in view


def test_rank_adds_points_and_breaks_ties_by_first_places():
    contest = {"places": 3, "must_attend": 1, "facet_list": []}

    def entry(entry_id, first, status="active"):
        return {"id": entry_id, "division": "HS 9–10", "facets": None,
                "title": None, "body_text": first, "translation": None,
                "link_url": None, "has_file": 0, "word_count": None,
                "person_id": entry_id, "person_status": status,
                "first_name": first, "last_name": "X", "school_id": 1,
                "school_name": "U", "school_number": 1, "school_seq": 1}

    def ballot(ballot_id, judge, places, comment=None):
        return [{"id": ballot_id, "division": "HS 9–10", "facet": "",
                 "comment": comment, "judge_first": judge, "judge_last": "J",
                 "place": place, "entry_id": entry_id}
                for place, entry_id in enumerate(places, 1)]

    entries = [entry(1, "A"), entry(2, "B"), entry(3, "C"), entry(4, "D"),
               entry(5, "E", status="cancelled"), entry(6, "F")]
    ballots = (ballot(10, "One", [1, 2, 3], comment="Close call.")
               + ballot(11, "Two", [4, 2, 1])
               + ballot(12, "Three", [3, 4, 5]))

    def standings(places):
        group, = contests.rank({**contest, "places": places}, entries, ballots)
        assert group["ballots"] == 3
        assert group["comments"] == [{"name": "One J", "comment": "Close call."}]
        return [(r["first_name"], r["points"], r["place"], r["awarded"],
                 r["tie_broken"]) for r in group["entries"]]

    # A 1st+3rd = 4, B 2nd+2nd = 4, C 3rd+1st = 4, D 1st+2nd = 5. A and C have
    # a 1st each, B none: A and C share 2nd, B is 4th. E is not attending,
    # F got no votes; both are listed, not placed, the ineligible last.
    assert standings(3) == [
        ("D", 5, 1, True, False),
        ("A", 4, 2, True, True),
        ("C", 4, 2, True, True),
        ("B", 4, 4, False, True),
        ("F", 0, None, False, False),
        ("E", 1, None, False, False),
    ]
    # N lowered to 2: every 3rd place is now worth nothing.
    assert standings(2) == [
        ("D", 3, 1, True, False),
        ("A", 2, 2, True, True),
        ("C", 2, 2, True, True),
        ("B", 2, 4, False, True),
        ("F", 0, None, False, False),
        ("E", 0, None, False, False),
    ]
    group, = contests.rank(contest, entries, ballots)
    a = next(r for r in group["entries"] if r["first_name"] == "A")
    assert a["votes"] == [{"name": "One J", "place": 1},
                          {"name": "Two J", "place": 3}]


def test_ordinals():
    assert [contests.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 111)] == \
        ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th",
         "21st", "22nd", "23rd", "111th"]


# ---------------------------------------------------------------------------
# Entering
# ---------------------------------------------------------------------------

def test_a_delegate_sees_their_contests_and_division(fx, client):
    body = client.get("/me/contests", headers=as_(fx, "delegate")).json()
    keys = [c["key"] for c in body["contests"]]
    assert "publicity" not in keys           # a chapter enters that
    myth = next(c for c in body["contests"] if c["key"] == "modern_myth")
    assert myth["division"] == "HS 9–10"      # Dana is in grade 10
    art = next(c for c in body["contests"] if c["key"] == "digital_art")
    assert art["division"] == "HS-II"         # Dana takes HS-2
    assert myth["entry"] is None
    assert myth["places"] == 3 and "criteria" not in myth     # no rubric any more
    assert body["can_enter"] is True


def test_slogans(fx, client):
    headers = as_(fx, "delegate")
    english = item(client, fx, "slogan_english")
    latin = item(client, fx, "slogan_latin")

    ok = client.post(f"/me/contests/{english}", headers=headers,
                     json={"text": "  Latin:   not dead yet  "})
    assert ok.status_code == 200, ok.text
    assert ok.json()["entry"]["text"] == "Latin: not dead yet"

    too_long = client.post(f"/me/contests/{english}", headers=headers,
                           json={"text": "x" * 101})
    assert too_long.status_code == 422

    untranslated = client.post(f"/me/contests/{latin}", headers=headers,
                               json={"text": "Lingua Latina vivit"})
    assert untranslated.status_code == 422
    assert "translation" in untranslated.json()["error"]

    assert client.post(f"/me/contests/{latin}", headers=headers,
                       json={"text": "Lingua Latina vivit",
                             "translation": "The Latin language lives"}).status_code == 200

    mine = client.get("/me/contests", headers=headers).json()["contests"]
    assert sum(1 for c in mine if c["entry"]) == 2
    assert "contest.enter" in fx.audit_actions()


def test_a_chaperone_holding_the_delegate_role_cannot_enter(fx, client):
    english = item(client, fx, "slogan_english")
    response = client.post(f"/me/contests/{english}", headers=as_(fx, "chaperone"),
                           json={"text": "Hello"})
    assert response.status_code == 422


def test_a_myth_is_uploaded_counted_and_filed_by_chapter(fx, client):
    headers = as_(fx, "delegate")
    myth = item(client, fx, "modern_myth")
    response = client.post(f"/me/contests/{myth}", headers=headers, json={
        "title": "The Owl of Irvine", "file": upload("Dana myth FINAL.docx", docx(1300))})
    assert response.status_code == 200, response.text
    entry = response.json()["entry"]
    assert entry["word_count"] == 1302 and entry["word_count_source"] == "counted"
    assert entry["original_name"] == "Dana myth FINAL.docx"

    files = [p for p in fx.drive_root.rglob("*.docx")]
    assert len(files) == 1
    assert files[0].parent.name.endswith("University High School")
    assert files[0].parent.parent.name == "Modern Myth"

    # The student can get their own file back.
    own = client.get(f"/me/contests/{myth}/file", headers=headers)
    assert own.status_code == 200 and own.content == files[0].read_bytes()


def test_a_pdf_needs_a_declared_length(fx, client):
    headers = as_(fx, "delegate")
    myth = item(client, fx, "modern_myth")
    pdf = upload("myth.pdf", b"%PDF-1.7\n...")
    refused = client.post(f"/me/contests/{myth}", headers=headers,
                          json={"title": "T", "file": pdf})
    assert refused.status_code == 422
    accepted = client.post(f"/me/contests/{myth}", headers=headers,
                           json={"title": "T", "file": pdf, "word_count": 900})
    assert accepted.json()["entry"]["word_count_source"] == "declared"

    # A title change needs no second upload.
    retitled = client.post(f"/me/contests/{myth}", headers=headers,
                           json={"title": "Better", "word_count": 950})
    assert retitled.status_code == 200
    assert retitled.json()["entry"]["title"] == "Better"
    assert retitled.json()["entry"]["word_count"] == 950


def test_nothing_is_accepted_after_the_deadline(fx, client):
    client.put("/admin/settings", headers=as_(fx, "admin"),
               json={"settings": {"deadline.contests": "2020-01-01"}})
    english = item(client, fx, "slogan_english")
    response = client.post(f"/me/contests/{english}", headers=as_(fx, "delegate"),
                           json={"text": "Too late"})
    assert response.status_code == 422
    assert "closed" in response.json()["error"]
    assert client.get("/me/contests", headers=as_(fx, "delegate")).json()["closed"]


def test_uploads_fail_plainly_when_drive_is_not_configured(fx, client, monkeypatch):
    drive.use(None)
    for name in ("APPS_SCRIPT_URL", "APPS_SCRIPT_KEY", "DRIVE_LOCAL_DIR"):
        monkeypatch.delenv(name, raising=False)
    myth = item(client, fx, "modern_myth")
    response = client.post(f"/me/contests/{myth}", headers=as_(fx, "delegate"),
                           json={"title": "T", "file": upload("m.txt", b"words " * 600)})
    assert response.status_code == 503
    assert "Nothing was saved" in response.json()["error"]


def test_publicity_is_a_chapter_entry(fx, client):
    publicity = item(client, fx, "publicity")
    sponsor = as_(fx, "uni_sponsor")

    assert client.post(f"/me/contests/{publicity}", headers=as_(fx, "delegate"),
                       json={"link_url": "https://docs.google.com/x"}).status_code == 422

    bad = client.post(f"/sponsor/contests/{publicity}", headers=sponsor,
                      json={"link_url": "https://evil.example/x", "facets": ["Media"]})
    assert bad.status_code == 422

    ok = client.post(f"/sponsor/contests/{publicity}", headers=sponsor, json={
        "link_url": "https://docs.google.com/document/d/abc/edit",
        "facets": ["Media", "Best Club Swag", "Not a category"]})
    assert ok.status_code == 200, ok.text

    page = client.get("/sponsor/contests", headers=sponsor).json()
    entry = page["contests"][0]["entry"]
    assert entry["facets"] == ["Media", "Best Club Swag"]
    assert entry["division"] == "HS"


def test_a_sponsor_sees_their_delegates_entries_and_nobody_elses(fx, client):
    english = item(client, fx, "slogan_english")
    client.post(f"/me/contests/{english}", headers=as_(fx, "delegate"),
                json={"text": "Uni slogan"})
    client.post(f"/me/contests/{english}", headers=as_(fx, "other_delegate"),
                json={"text": "Rival slogan"})

    students = client.get("/sponsor/contests", headers=as_(fx, "uni_sponsor")).json()["students"]
    assert [s["text"] for s in students] == ["Uni slogan"]
    assert client.get(f"/sponsor/contests?school_id={fx.other_id}",
                      headers=as_(fx, "uni_sponsor")).status_code == 403


def test_a_sponsor_downloads_their_delegates_files_and_nobody_elses(fx, client):
    myth = item(client, fx, "modern_myth")
    mine = client.post(f"/me/contests/{myth}", headers=as_(fx, "delegate"), json={
        "title": "Ours", "file": upload("ours.docx", docx(1300))}).json()["entry"]
    theirs = client.post(f"/me/contests/{myth}", headers=as_(fx, "other_delegate"), json={
        "title": "Theirs", "file": upload("theirs.docx", docx(1300))}).json()["entry"]

    students = client.get("/sponsor/contests", headers=as_(fx, "uni_sponsor")).json()["students"]
    assert [(s["id"], s["has_file"]) for s in students] == [(mine["id"], True)]

    own = client.get(f"/sponsor/contests/entries/{mine['id']}/file",
                     headers=as_(fx, "uni_sponsor"))
    assert own.status_code == 200 and own.content == docx(1300)
    assert "Modern Myth" in own.headers["content-disposition"]

    assert client.get(f"/sponsor/contests/entries/{theirs['id']}/file",
                      headers=as_(fx, "uni_sponsor")).status_code == 403
    # A chapter leader sees the portfolio, not classmates' work.
    assert client.get(f"/sponsor/contests/entries/{mine['id']}/file",
                      headers=as_(fx, "delegate")).status_code == 403
    # The registration chairs may open any chapter's.
    assert client.get(f"/sponsor/contests/entries/{theirs['id']}/file",
                      headers=as_(fx, "chair")).status_code == 200


def test_the_registration_chairs_see_every_submission(fx, client):
    english = item(client, fx, "slogan_english")
    publicity = item(client, fx, "publicity")
    client.post(f"/me/contests/{english}", headers=as_(fx, "delegate"),
                json={"text": "Uni slogan"})
    client.post(f"/me/contests/{english}", headers=as_(fx, "other_delegate"),
                json={"text": "Rival slogan"})
    client.post(f"/sponsor/contests/{publicity}", headers=as_(fx, "uni_sponsor"), json={
        "link_url": "https://docs.google.com/document/d/abc/edit", "facets": ["Media"]})

    response = client.get("/admin/contests/submissions", headers=as_(fx, "chair"))
    assert response.status_code == 200, response.text
    data = response.json()
    counts = {c["item_id"]: c["entries"] for c in data["contests"]}
    assert counts[english] == 2 and counts[publicity] == 1
    slogans = sorted(e["text"] for e in data["entries"] if e["item_id"] == english)
    assert slogans == ["Rival slogan", "Uni slogan"]
    portfolio = next(e for e in data["entries"] if e["item_id"] == publicity)
    assert portfolio["person_id"] is None and portfolio["facets"] == ["Media"]
    assert portfolio["school_name"].endswith("University High School")

    for who in ("uni_sponsor", "delegate", "judge"):
        assert client.get("/admin/contests/submissions",
                          headers=as_(fx, who)).status_code == 403


# ---------------------------------------------------------------------------
# Judging
# ---------------------------------------------------------------------------

def add_tess(fx):
    """A third delegate in Dana and Rory's division, for three-way rankings."""
    with fx.db.tx() as tx:
        person_id = fx._person(tx, "tess", fx.uni_id, first="Tess", last="Third",
                               role="delegate", grade=10, latin_level="HS-2")
        tx.audit("person.create", "Test added a third delegate.")
    return person_id


def slogans(client, fx, *who) -> tuple[int, dict]:
    """Each named delegate enters the English slogan; returns the contest and
    each delegate's entry id, keyed by first name."""
    english = item(client, fx, "slogan_english")
    for key in who:
        response = client.post(f"/me/contests/{english}", headers=as_(fx, key),
                               json={"text": f"{key}'s slogan"})
        assert response.status_code == 200, response.text
    with fx.db.read() as tx:
        rows = tx.all("contests.results_entries", (english,))
    return english, {r["first_name"]: r["id"] for r in rows}


def rank(client, fx, who, item_id, places, *, submit=True, division="HS 9–10",
         facet="", comment=None):
    return client.put(f"/judge/contests/{item_id}/ballot", headers=as_(fx, who),
                      json={"division": division, "facet": facet,
                            "places": {str(e): p for e, p in places.items()},
                            "comment": comment, "submit": submit})


def results(client, fx, item_id, facet=""):
    body = client.get(f"/admin/contests/{item_id}/results",
                      headers=as_(fx, "academics")).json()
    return next(g for g in body["groups"] if g["facet"] == facet)


def standings(group):
    return [(e["first_name"], e["points"], e["place"]) for e in group["entries"]]


def test_judges_rank_entries_without_seeing_names(fx, client):
    myth = item(client, fx, "modern_myth")
    client.post(f"/me/contests/{myth}", headers=as_(fx, "delegate"), json={
        "title": "The Owl", "file": upload("Dana Delegate.docx", docx(1248))})
    client.post(f"/me/contests/{myth}", headers=as_(fx, "other_delegate"), json={
        "title": "The Fox", "file": upload("Rory Rival.docx", docx(900))})

    judge = as_(fx, "judge")
    listing = client.get(f"/judge/contests/{myth}", headers=judge)
    assert listing.status_code == 200
    text = listing.text
    for secret in ("Dana", "Delegate", "Rory", "Rival", "University", ".docx"):
        assert secret not in text
    body = listing.json()
    owl, fox = body["entries"]
    assert owl["title"] == "The Owl" and owl["penalty"] == 3   # 1,250 words: 50 over
    assert "word word" in owl["text"]
    assert "scores" not in owl
    assert body["contest"]["places"] == 3
    assert body["groups"] == [{"division": "HS 9–10", "facet": "",
                               "entry_ids": [owl["id"], fox["id"]], "needed": 2,
                               "ballot": None, "complete": False}]

    file = client.get(f"/judge/entries/{owl['id']}/file", headers=judge)
    assert file.status_code == 200
    assert f'filename="Entry {owl["id"]}.docx"' in file.headers["content-disposition"]

    def refused(places, **kw):
        response = rank(client, fx, "judge", myth, places, **kw)
        assert response.status_code == 422, response.text
        return response.json()["error"]

    assert "both placed 1st" in refused({owl["id"]: 1, fox["id"]: 1})
    assert "listed twice" in refused({str(owl["id"]): 1, f"0{owl['id']}": 2},
                                     submit=False)
    assert "1 to 3" in refused({owl["id"]: 4}, submit=False)
    assert "not in HS 9–10" in refused({9999: 1}, submit=False)
    assert refused({owl["id"]: 1}, division="HS 11–12", submit=False)
    assert "2nd" in refused({owl["id"]: 1})                    # incomplete
    assert "2nd" in refused({owl["id"]: 1, fox["id"]: 3})      # a gap

    draft = rank(client, fx, "judge", myth, {owl["id"]: 1}, submit=False)
    assert draft.status_code == 200, draft.text
    assert draft.json()["status"] == "draft"
    group = client.get(f"/judge/contests/{myth}", headers=judge).json()["groups"][0]
    assert group["ballot"]["status"] == "draft"
    assert group["ballot"]["places"] == {str(owl["id"]): 1}
    assert group["complete"] is False

    handed_in = rank(client, fx, "judge", myth, {fox["id"]: 1, owl["id"]: 2},
                     comment="Two good fables.")
    assert handed_in.status_code == 200, handed_in.text
    assert handed_in.json() == {"ok": True, "status": "submitted",
                                "places": {str(fox["id"]): 1, str(owl["id"]): 2}}
    group = client.get(f"/judge/contests/{myth}", headers=judge).json()["groups"][0]
    assert group["complete"] is True
    assert group["ballot"]["comment"] == "Two good fables."
    assert group["ballot"]["places"] == {str(fox["id"]): 1, str(owl["id"]): 2}
    assert "contest.rank" in fx.audit_actions()

    # The other judge's page is their own.
    other = client.get(f"/judge/contests/{myth}", headers=as_(fx, "judge2")).json()
    assert other["groups"][0]["ballot"] is None

    front = client.get("/judge/contests", headers=judge).json()["contests"]
    mine = next(c for c in front if c["item_id"] == myth)
    assert (mine["places"], mine["entries"], mine["groups"], mine["handed_in"]) == \
        (3, 2, 1, 1)

    # A judge cannot read the results, which carry names.
    assert client.get(f"/admin/contests/{myth}/results",
                      headers=judge).status_code == 403
    assert client.get(f"/admin/contests/entries/{owl['id']}/file",
                      headers=judge).status_code == 403


def test_the_academics_chairs_do_not_judge(fx, client):
    """They read the results with names attached, so they do not also rank."""
    english, ids = slogans(client, fx, "delegate")
    chair = as_(fx, "academics")
    assert client.get("/judge/contests", headers=chair).status_code == 403
    assert client.get(f"/judge/contests/{english}", headers=chair).status_code == 403
    assert rank(client, fx, "academics", english, {ids["Dana"]: 1}).status_code == 403
    listing = client.get("/admin/contests", headers=chair).json()
    row = next(c for c in listing["contests"] if c["item_id"] == english)
    assert (row["entries"], row["ballots"], row["judges"], row["places"]) == (1, 0, 0, 3)


def test_a_chair_given_the_judge_role_as_well_still_cannot_judge(fx, client):
    with fx.db.tx() as tx:
        role = tx.one("roles.by_key", ("contest_judge",))
        tx.run("people.grant_role", (fx.academics_id, role["id"], None, "2026-09-01T00:00:00Z"))
        tx.audit("person.roles", "Test gave the chair the judge role too.")
    response = client.get("/judge/contests", headers=as_(fx, "academics"))
    assert response.status_code == 403
    assert "do not judge" in response.json()["error"]


def test_a_judge_holds_nothing_else(fx, client):
    judge = as_(fx, "judge")
    assert client.get("/admin/academics/counts", headers=judge).status_code == 403
    assert client.get(f"/sponsor/roster?school_id={fx.uni_id}",
                      headers=judge).status_code == 403


def test_publicity_is_ranked_per_category(fx, client):
    publicity = item(client, fx, "publicity")
    client.post(f"/sponsor/contests/{publicity}", headers=as_(fx, "uni_sponsor"), json={
        "link_url": "https://docs.google.com/document/d/abc",
        "facets": ["Media", "Best Club Swag"]})
    client.post(f"/sponsor/contests/{publicity}", headers=as_(fx, "other_sponsor"), json={
        "link_url": "https://docs.google.com/document/d/def", "facets": ["Media"]})

    body = client.get(f"/judge/contests/{publicity}", headers=as_(fx, "judge")).json()
    uni, rival = (e["id"] for e in body["entries"])
    groups = {(g["division"], g["facet"]): (g["entry_ids"], g["needed"])
              for g in body["groups"]}
    assert groups == {("HS", "Media"): ([uni, rival], 2),
                      ("HS", "Best Club Swag"): ([uni], 1)}

    def ballot(facet, places):
        return rank(client, fx, "judge", publicity, places, division="HS", facet=facet)

    assert ballot("Best Club Swag", {rival: 1}).status_code == 422   # not entered there
    assert ballot("Not a category", {uni: 1}).status_code == 422
    assert ballot("", {uni: 1}).status_code == 422
    assert ballot("Media", {rival: 1, uni: 2}).status_code == 200
    assert ballot("Best Club Swag", {uni: 1}).status_code == 200

    groups = client.get(f"/judge/contests/{publicity}",
                        headers=as_(fx, "judge")).json()["groups"]
    assert all(g["complete"] for g in groups)

    media = results(client, fx, publicity, "Media")
    assert [(e["school_name"].split()[0], e["points"], e["place"])
            for e in media["entries"]] == [("Rival", 3, 1), ("University", 2, 2)]
    swag = results(client, fx, publicity, "Best Club Swag")
    assert [(e["entry_id"], e["place"]) for e in swag["entries"]] == [(uni, 1)]


def test_results_add_judges_points_and_ignore_drafts(fx, client):
    english, ids = slogans(client, fx, "delegate", "other_delegate")
    dana, rory = ids["Dana"], ids["Rory"]

    assert rank(client, fx, "judge", english, {dana: 1, rory: 2},
                comment="Both catchy.").status_code == 200
    assert rank(client, fx, "judge2", english, {rory: 1, dana: 2}).status_code == 200

    # 3 + 2 each, one 1st and one 2nd each: level on everything, so they share.
    group = results(client, fx, english)
    assert group["division"] == "HS 9–10" and group["ballots"] == 2
    assert standings(group) == [("Dana", 5, 1), ("Rory", 5, 1)]
    assert all(e["awarded"] and not e["tie_broken"] for e in group["entries"])
    assert group["entries"][0]["votes"] == [{"name": "Jo Judge", "place": 1},
                                            {"name": "Lee Second", "place": 2}]
    assert group["comments"] == [{"name": "Jo Judge", "comment": "Both catchy."}]

    row = next(c for c in client.get("/admin/contests", headers=as_(fx, "academics"))
               .json()["contests"] if c["item_id"] == english)
    assert (row["entries"], row["ballots"], row["judges"]) == (2, 2, 2)

    # Taken back to a draft, the second judge's list stops counting.
    assert rank(client, fx, "judge2", english, {dana: 1, rory: 2},
                submit=False).status_code == 200
    group = results(client, fx, english)
    assert group["ballots"] == 1
    assert standings(group) == [("Dana", 3, 1), ("Rory", 2, 2)]

    assert rank(client, fx, "judge2", english, {dana: 1, rory: 2}).status_code == 200
    assert standings(results(client, fx, english)) == [("Dana", 6, 1), ("Rory", 4, 2)]


def test_equal_points_are_split_by_first_places(fx, client):
    add_tess(fx)
    english, ids = slogans(client, fx, "delegate", "other_delegate", "tess")
    dana, rory, tess = ids["Dana"], ids["Rory"], ids["Tess"]
    rank(client, fx, "judge", english, {dana: 1, rory: 2, tess: 3})
    rank(client, fx, "judge2", english, {tess: 1, rory: 2, dana: 3})

    # All on 4 points. Dana and Tess each have a 1st; Rory has two 2nds.
    group = results(client, fx, english)
    assert standings(group) == [("Dana", 4, 1), ("Tess", 4, 1), ("Rory", 4, 3)]
    assert all(e["tie_broken"] for e in group["entries"])
    assert all(e["awarded"] for e in group["entries"])       # 3rd of 3


def test_a_delegate_no_longer_attending_is_listed_not_placed(fx, client):
    english, ids = slogans(client, fx, "delegate", "other_delegate")
    rank(client, fx, "judge", english, {ids["Rory"]: 1, ids["Dana"]: 2})
    assert standings(results(client, fx, english)) == [("Rory", 3, 1), ("Dana", 2, 2)]

    client.post(f"/sponsor/people/{fx.other_delegate_id}/cancel",
                headers=as_(fx, "other_sponsor"))
    group = results(client, fx, english)
    assert [(e["first_name"], e["place"], e["eligible"]) for e in group["entries"]] == \
        [("Dana", 1, True), ("Rory", None, False)]


def test_the_chairs_set_how_many_places(fx, client):
    add_tess(fx)
    english, ids = slogans(client, fx, "delegate", "other_delegate", "tess")
    dana, rory = ids["Dana"], ids["Rory"]
    chair = as_(fx, "academics")

    def set_places(value):
        return client.put(f"/admin/contests/{english}", headers=chair,
                          json={"places": value})

    def judge_group():
        return client.get(f"/judge/contests/{english}",
                          headers=as_(fx, "judge")).json()["groups"][0]

    for bad in (0, 21, "three", None):
        assert set_places(bad).status_code == 422, bad
    assert set_places(2).status_code == 200
    assert "contest.update" in fx.audit_actions()

    assert judge_group()["needed"] == 2
    assert "1 to 2" in rank(client, fx, "judge", english, {dana: 3},
                            submit=False).json()["error"]
    assert rank(client, fx, "judge", english, {dana: 1, rory: 2}).status_code == 200
    assert judge_group()["complete"] is True
    assert standings(results(client, fx, english)) == \
        [("Dana", 2, 1), ("Rory", 1, 2), ("Tess", 0, None)]

    # Raised: the ballot handed in is now short, and counts as it stands.
    assert set_places(3).status_code == 200
    group = judge_group()
    assert (group["needed"], group["complete"], group["ballot"]["status"]) == \
        (3, False, "submitted")
    assert standings(results(client, fx, english)) == \
        [("Dana", 3, 1), ("Rory", 2, 2), ("Tess", 0, None)]

    # Lowered: places beyond N count for nothing, but still show.
    assert set_places(1).status_code == 200
    assert judge_group()["complete"] is True
    body = client.get(f"/admin/contests/{english}/results", headers=chair).json()
    assert body["contest"]["places"] == 1
    assert "rubric_locked" not in body
    group = body["groups"][0]
    assert standings(group) == [("Dana", 1, 1), ("Rory", 0, None), ("Tess", 0, None)]
    assert group["entries"][1]["votes"] == [{"name": "Jo Judge", "place": 2}]

    # The rules text is the other thing the chairs edit.
    assert client.put(f"/admin/contests/{english}", headers=chair,
                      json={"rules_md": "Be brief."}).status_code == 200
    assert client.get(f"/admin/contests/{english}/results",
                      headers=chair).json()["contest"]["rules_md"] == "Be brief."
    # Only the Academics chairs edit.
    assert client.put(f"/admin/contests/{english}", headers=as_(fx, "judge"),
                      json={"places": 5}).status_code == 403

    # Divisions have no screen: a request to change them changes nothing.
    client.put(f"/admin/contests/{english}", headers=chair, json={"divisions": "none"})
    with fx.db.read() as tx:
        assert contests.by_item(tx, english)["divisions"] == "level_grade"


def test_replacing_or_withdrawing_an_entry_takes_it_off_ballots(fx, client):
    myth = item(client, fx, "modern_myth")
    dana_h = as_(fx, "delegate")
    client.post(f"/me/contests/{myth}", headers=dana_h,
                json={"title": "One", "file": upload("a.txt", b"word " * 600)})
    client.post(f"/me/contests/{myth}", headers=as_(fx, "other_delegate"),
                json={"title": "Fox", "file": upload("f.txt", b"fox " * 600)})
    body = client.get(f"/judge/contests/{myth}", headers=as_(fx, "judge")).json()
    dana, rory = (e["id"] for e in body["entries"])
    assert rank(client, fx, "judge", myth, {dana: 1, rory: 2}).status_code == 200
    assert rank(client, fx, "judge2", myth, {rory: 1, dana: 2}).status_code == 200

    def ballot(who):
        return client.get(f"/judge/contests/{myth}",
                          headers=as_(fx, who)).json()["groups"][0]

    client.post(f"/me/contests/{myth}", headers=dana_h,
                json={"title": "Two", "file": upload("b.txt", b"verse " * 700)})
    after = client.get(f"/judge/contests/{myth}", headers=as_(fx, "judge")).json()
    assert after["entries"][0]["id"] == dana                   # same number
    for who, left in (("judge", {str(rory): 2}), ("judge2", {str(rory): 1})):
        group = ballot(who)
        assert group["ballot"]["status"] == "draft"
        assert group["ballot"]["places"] == left
        assert group["complete"] is False
    assert results(client, fx, myth)["ballots"] == 0
    live = [p for p in fx.drive_root.rglob("*.txt") if ".trash" not in p.parts]
    assert sorted(p.read_bytes()[:3] for p in live) == [b"fox", b"ver"]

    # Handed in again, then withdrawn.
    assert rank(client, fx, "judge", myth, {dana: 1, rory: 2}).status_code == 200
    assert client.delete(f"/me/contests/{myth}", headers=dana_h).status_code == 200
    group = ballot("judge")
    assert group["entry_ids"] == [rory]
    assert group["ballot"]["status"] == "draft"
    assert group["ballot"]["places"] == {str(rory): 2}
    assert "contest.withdraw" in fx.audit_actions()
    # Rory is now the only entry, so a complete list is one long.
    assert rank(client, fx, "judge", myth, {rory: 1}).status_code == 200
    assert ballot("judge")["complete"] is True
