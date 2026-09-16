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


def test_the_seeded_rubrics_match_the_convention_book(fx):
    with fx.db.read() as tx:
        by_key = {c["key"]: c for c in contests.load(tx)}
    assert set(by_key) == {"digital_art", "modern_myth", "poetry",
                           "slogan_english", "slogan_latin", "publicity"}
    assert [c["max_points"] for c in by_key["modern_myth"]["criteria"]] == [25] * 4
    assert [c["max_points"] for c in by_key["poetry"]["criteria"]] == \
        [20, 20, 15, 15, 10, 20]
    assert len(by_key["publicity"]["facet_list"]) == 8
    assert by_key["publicity"]["must_attend"] == 0


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


# ---------------------------------------------------------------------------
# Judging
# ---------------------------------------------------------------------------

def test_judges_see_entries_without_names_and_score_them(fx, client):
    myth = item(client, fx, "modern_myth")
    client.post(f"/me/contests/{myth}", headers=as_(fx, "delegate"), json={
        "title": "The Owl", "file": upload("Dana Delegate.docx", docx(1248))})

    judge = as_(fx, "judge")
    listing = client.get(f"/judge/contests/{myth}", headers=judge)
    assert listing.status_code == 200
    text = listing.text
    assert "Dana" not in text and "Delegate" not in text
    assert "University" not in text
    assert "Dana Delegate.docx" not in text
    entry = listing.json()["entries"][0]
    assert entry["penalty"] == 3               # 1,250 words: 50 over
    assert "word word" in entry["text"]

    file = client.get(f"/judge/entries/{entry['id']}/file", headers=judge)
    assert file.status_code == 200
    assert f'filename="Entry {entry["id"]}.docx"' in file.headers["content-disposition"]

    criteria = listing.json()["contest"]["criteria"]
    url = f"/judge/entries/{entry['id']}/score"

    incomplete = client.put(url, headers=judge, json={
        "points": {str(criteria[0]["id"]): 20}, "submit": True})
    assert incomplete.status_code == 422

    too_many = client.put(url, headers=judge, json={
        "points": {str(criteria[0]["id"]): 26}})
    assert too_many.status_code == 422

    draft = client.put(url, headers=judge, json={
        "points": {str(criteria[0]["id"]): 20}})
    assert draft.json()["status"] == "draft"

    handed_in = client.put(url, headers=judge, json={
        "points": {str(c["id"]): 20 for c in criteria}, "comment": "Lovely owl.",
        "submit": True})
    assert handed_in.status_code == 200
    assert handed_in.json()["total"] == 77     # 80 less the length penalty

    mine = client.get(f"/judge/contests/{myth}", headers=judge).json()["entries"][0]
    assert mine["scores"][""]["status"] == "submitted"

    # A judge cannot read the results, which carry names.
    assert client.get(f"/admin/contests/{myth}/results",
                      headers=judge).status_code == 403
    assert client.get(f"/admin/contests/entries/{entry['id']}/file",
                      headers=judge).status_code == 403


def test_the_academics_chairs_do_not_judge(fx, client):
    """They read the results with names attached, so they do not also score."""
    english = item(client, fx, "slogan_english")
    client.post(f"/me/contests/{english}", headers=as_(fx, "delegate"),
                json={"text": "Slogan"})
    chair = as_(fx, "academics")
    assert client.get("/judge/contests", headers=chair).status_code == 403
    assert client.get(f"/judge/contests/{english}", headers=chair).status_code == 403
    listing = client.get("/admin/contests", headers=chair).json()
    entry_id = client.get(f"/admin/contests/{english}/results",
                          headers=chair).json()["groups"][0]["entries"][0]["entry_id"]
    assert client.put(f"/judge/entries/{entry_id}/score", headers=chair,
                      json={"points": {}, "submit": False}).status_code == 403
    assert next(c for c in listing["contests"]
                if c["item_id"] == english)["entries"] == 1


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


def test_publicity_is_judged_per_category(fx, client):
    publicity = item(client, fx, "publicity")
    client.post(f"/sponsor/contests/{publicity}", headers=as_(fx, "uni_sponsor"), json={
        "link_url": "https://docs.google.com/document/d/abc", "facets": ["Media"]})
    judge = as_(fx, "judge")
    body = client.get(f"/judge/contests/{publicity}", headers=judge).json()
    entry = body["entries"][0]
    assert entry["facets"] == ["Media"]
    points = {str(c["id"]): 10 for c in body["contest"]["criteria"]}

    wrong = client.put(f"/judge/entries/{entry['id']}/score", headers=judge,
                       json={"facet": "Best Club Swag", "points": points, "submit": True})
    assert wrong.status_code == 422
    right = client.put(f"/judge/entries/{entry['id']}/score", headers=judge,
                       json={"facet": "Media", "points": points, "submit": True})
    assert right.status_code == 200


def test_results_rank_by_mean_and_skip_drafts_and_absent_delegates(fx, client):
    english = item(client, fx, "slogan_english")
    client.post(f"/me/contests/{english}", headers=as_(fx, "delegate"),
                json={"text": "Dana's"})
    # Rory is in grade 9 at Rival High: the same division as Dana.
    client.post(f"/me/contests/{english}", headers=as_(fx, "other_delegate"),
                json={"text": "Rory's"})

    entries = client.get(f"/judge/contests/{english}",
                         headers=as_(fx, "judge")).json()
    criterion = str(entries["contest"]["criteria"][0]["id"])
    ids = {e["text"]: e["id"] for e in entries["entries"]}

    def score(who, entry, points, submit=True):
        response = client.put(f"/judge/entries/{entry}/score", headers=as_(fx, who),
                              json={"points": {criterion: points}, "submit": submit})
        assert response.status_code == 200, response.text

    score("judge", ids["Dana's"], 80)
    score("judge2", ids["Dana's"], 90)
    score("judge", ids["Rory's"], 95)
    score("judge2", ids["Rory's"], 10, submit=False)        # a draft: ignored

    chair = as_(fx, "academics")
    results = client.get(f"/admin/contests/{english}/results", headers=chair).json()
    group = results["groups"][0]
    assert group["division"] == "HS 9–10"
    assert [(e["first_name"], e["average"], e["place"]) for e in group["entries"]] == \
        [("Rory", 95, 1), ("Dana", 85, 2)]
    assert results["rubric_locked"] is True

    # Rory withdraws from convention: listed, not placed.
    client.post(f"/sponsor/people/{fx.other_delegate_id}/cancel",
                headers=as_(fx, "other_sponsor"))
    group = client.get(f"/admin/contests/{english}/results",
                       headers=chair).json()["groups"][0]
    assert [(e["first_name"], e["place"], e["eligible"]) for e in group["entries"]] == \
        [("Dana", 1, True), ("Rory", None, False)]


def test_replacing_an_entry_clears_its_scores_and_trashes_the_old_file(fx, client):
    myth = item(client, fx, "modern_myth")
    headers = as_(fx, "delegate")
    client.post(f"/me/contests/{myth}", headers=headers,
                json={"title": "One", "file": upload("a.txt", b"word " * 600)})
    body = client.get(f"/judge/contests/{myth}", headers=as_(fx, "judge")).json()
    entry_id = body["entries"][0]["id"]
    points = {str(c["id"]): 5 for c in body["contest"]["criteria"]}
    client.put(f"/judge/entries/{entry_id}/score", headers=as_(fx, "judge"),
               json={"points": points, "submit": True})

    client.post(f"/me/contests/{myth}", headers=headers,
                json={"title": "Two", "file": upload("b.txt", b"verse " * 700)})
    after = client.get(f"/judge/contests/{myth}", headers=as_(fx, "judge")).json()
    assert after["entries"][0]["id"] == entry_id          # same number
    assert after["entries"][0]["scores"] == {}
    live = [p for p in fx.drive_root.rglob("*.txt") if ".trash" not in p.parts]
    assert len(live) == 1 and live[0].read_bytes().startswith(b"verse")

    assert client.delete(f"/me/contests/{myth}", headers=headers).status_code == 200
    assert client.get(f"/judge/contests/{myth}",
                      headers=as_(fx, "judge")).json()["entries"] == []
    assert "contest.withdraw" in fx.audit_actions()


def test_a_rubric_is_fixed_once_scored(fx, client):
    english = item(client, fx, "slogan_english")
    chair = as_(fx, "academics")
    ok = client.put(f"/admin/contests/{english}", headers=chair, json={
        "criteria": [{"label": "Effectiveness", "max_points": 60},
                     {"label": "Originality", "max_points": 40}]})
    assert ok.status_code == 200, ok.text

    client.post(f"/me/contests/{english}", headers=as_(fx, "delegate"),
                json={"text": "Slogan"})
    body = client.get(f"/judge/contests/{english}", headers=as_(fx, "judge")).json()
    criteria = body["contest"]["criteria"]
    assert [c["max_points"] for c in criteria] == [60, 40]
    client.put(f"/judge/entries/{body['entries'][0]['id']}/score",
               headers=as_(fx, "judge"),
               json={"points": {str(c["id"]): 1 for c in criteria}, "submit": True})

    reshaped = client.put(f"/admin/contests/{english}", headers=chair, json={
        "criteria": [{"label": "Everything", "max_points": 100}]})
    assert reshaped.status_code == 422

    reworded = client.put(f"/admin/contests/{english}", headers=chair, json={
        "criteria": [{"id": criteria[0]["id"], "label": "Impact", "max_points": 60},
                     {"id": criteria[1]["id"], "label": "Originality", "max_points": 40}]})
    assert reworded.status_code == 200

    # Divisions have no screen: a request to change them changes nothing.
    client.put(f"/admin/contests/{english}", headers=chair, json={"divisions": "none"})
    with fx.db.read() as tx:
        assert contests.by_item(tx, english)["divisions"] == "level_grade"
