"""The at-convention photo contest: categories, uploads, and the chair's page.

Drive is a folder under the test's tmp_path (drive.LocalDrive), so a photo
really is written somewhere and really is read back for the chair.
"""

from __future__ import annotations

import base64
import struct

import pytest

from backend import api
from backend.lib import drive, photos
from backend.lib.catalog import ValidationError

from .helpers import Fixture


@pytest.fixture
def fx(tmp_path, monkeypatch):
    with Fixture(tmp_path) as f:
        monkeypatch.setattr(api, "_db", f.db)
        local = drive.LocalDrive(str(tmp_path / "drive"))
        drive.use(local)
        f.drive_root = local.root
        with f.db.tx() as tx:
            f.activities_id = f._person(
                tx, "activities", f.board_id, person_type="adult", adult_type="other",
                first="Ace", last="Activities", role="activities_chair",
                email="act@example.org")
            tx.audit("person.create", "Test fixture added an Activities chair.")
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


def segment(marker: int, body: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(body) + 2) + body


def jpeg(secret: bytes = b"GPS 33.6N 117.8W") -> bytes:
    """A JPEG with a JFIF header, an Exif block holding `secret`, and a scan."""
    return (b"\xff\xd8"
            + segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
            + segment(0xE1, b"Exif\x00\x00" + secret)
            + segment(0xFE, b"a comment")
            + segment(0xDA, b"\x01\x01\x00\x00\x3f\x00")
            + b"\x12\x34\x56\xff\x00\x78"
            + b"\xff\xd9")


def png() -> bytes:
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + b"\x00\x00\x00\x00"
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", b"\x00" * 13)
            + chunk(b"tEXt", b"Location\x00Irvine")
            + chunk(b"IDAT", b"\x00\x01\x02")
            + chunk(b"IEND", b""))


def folder_of(fx):
    """The category's folder, under whatever root Settings names."""
    return next(fx.drive_root.rglob("Best flower photo"))


def files_in(fx):
    return [p for p in folder_of(fx).iterdir() if p.is_file()]


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def flower_id(fx) -> int:
    with fx.db.read() as tx:
        return next(r["id"] for r in tx.all("photos.categories")
                    if r["name"] == "Best flower photo")


def open_flowers(fx, client) -> int:
    category = flower_id(fx)
    response = client.patch(f"/admin/photos/categories/{category}",
                            json={"accepting": True}, headers=as_(fx, "activities"))
    assert response.status_code == 200, response.text
    return category


def send(client, fx, category, who="delegate", **extra):
    body = {"photo": {"name": "IMG_0042.jpg", "data": b64(jpeg())},
            "thumbnail": b64(jpeg(b"thumb")), **extra}
    return client.post(f"/me/photos/{category}", json=body, headers=as_(fx, who))


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------

def test_location_and_comments_are_stripped_from_a_jpeg():
    cleaned = photos.strip_metadata("jpg", jpeg())
    assert b"GPS" not in cleaned and b"a comment" not in cleaned
    assert b"JFIF" in cleaned, "the header the picture needs stays"
    assert cleaned.endswith(b"\x12\x34\x56\xff\x00\x78\xff\xd9"), "the scan is untouched"


def test_text_chunks_are_stripped_from_a_png():
    cleaned = photos.strip_metadata("png", png())
    assert b"Irvine" not in cleaned
    assert b"IHDR" in cleaned and b"IDAT" in cleaned and cleaned.endswith(
        b"IEND\x00\x00\x00\x00")


def test_a_damaged_photo_is_refused_rather_than_passed_through():
    with pytest.raises(ValidationError):
        photos.strip_metadata("jpg", jpeg()[:30])


def test_a_renamed_file_is_not_a_photo():
    with pytest.raises(ValidationError):
        photos.check_photo("rose.jpg", b"%PDF-1.4 not a photo")


def test_an_edit_keeps_what_it_does_not_mention():
    current = {"name": "Best flower photo", "description": "Flowers.",
               "accepting": 0, "sort_order": 10}
    fields = photos.check_category({"accepting": True}, current)
    assert fields == {"name": "Best flower photo", "description": "Flowers.",
                      "accepting": 1, "sort_order": 10}


# ---------------------------------------------------------------------------
# A delegate
# ---------------------------------------------------------------------------

def test_a_closed_category_takes_no_photos(fx, client):
    category = flower_id(fx)
    listed = client.get("/me/photos", headers=as_(fx, "delegate")).json()
    assert [c["accepting"] for c in listed["categories"]] == [False]
    response = send(client, fx, category)
    assert response.status_code == 422, response.text
    assert "not taking photos" in response.json()["errors"][0]


def test_a_delegate_uploads_a_photo_to_drive_without_its_location(fx, client):
    category = open_flowers(fx, client)
    response = send(client, fx, category, caption="  A  rose  ")
    assert response.status_code == 200, response.text
    entry = response.json()["entry"]
    assert entry["caption"] == "A rose" and entry["has_thumb"] is True

    folder = folder_of(fx)
    assert folder.parent.name == "Photo Contest"
    saved = files_in(fx)
    assert [p.name for p in saved] == [
        "02 University High School - Delegate, Dana.jpg"]
    assert b"GPS" not in saved[0].read_bytes()
    assert (folder / "Thumbnails").is_dir()

    mine = client.get(f"/me/photos/{category}/file?size=thumb",
                      headers=as_(fx, "delegate"))
    assert mine.status_code == 200
    thumbs = list((folder / "Thumbnails").iterdir())
    assert [p.name for p in thumbs] == [
        "02 University High School - Delegate, Dana (thumbnail).jpg"]
    assert mine.content == thumbs[0].read_bytes()


def test_replacing_a_photo_trashes_the_old_one(fx, client):
    category = open_flowers(fx, client)
    assert send(client, fx, category).status_code == 200
    assert send(client, fx, category).status_code == 200
    assert len(files_in(fx)) == 1
    assert len(list((fx.drive_root / ".trash").iterdir())) == 2   # photo + thumbnail


def test_a_caption_can_change_without_sending_the_photo_again(fx, client):
    category = open_flowers(fx, client)
    send(client, fx, category, caption="First")
    response = client.post(f"/me/photos/{category}", json={"caption": "Second"},
                           headers=as_(fx, "delegate"))
    assert response.status_code == 200
    assert response.json()["entry"]["caption"] == "Second"


def test_an_adult_cannot_enter(fx, client):
    """A chaperone holds the delegate role for their own form, and is still
    not a student."""
    category = open_flowers(fx, client)
    response = send(client, fx, category, who="chaperone")
    assert response.status_code == 422
    assert "for delegates" in response.json()["errors"][0]


def test_a_delegate_withdraws_even_after_the_category_closes(fx, client):
    category = open_flowers(fx, client)
    send(client, fx, category)
    client.patch(f"/admin/photos/categories/{category}", json={"accepting": False},
                 headers=as_(fx, "activities"))
    response = client.delete(f"/me/photos/{category}", headers=as_(fx, "delegate"))
    assert response.status_code == 200
    listed = client.get("/me/photos", headers=as_(fx, "delegate")).json()
    assert listed["categories"][0]["entry"] is None


# ---------------------------------------------------------------------------
# The Activities chair
# ---------------------------------------------------------------------------

def test_the_chair_sees_every_photo_with_its_name_and_chapter(fx, client):
    category = open_flowers(fx, client)
    send(client, fx, category)
    send(client, fx, category, who="other_delegate")
    data = client.get("/admin/photos", headers=as_(fx, "activities")).json()
    assert data["categories"][0]["photos"] == 2
    assert {(e["last_name"], e["school_name"]) for e in data["entries"]} == {
        ("Delegate", "University High School"), ("Rival", "Rival High School")}

    entry = data["entries"][0]
    full = client.get(f"/admin/photos/entries/{entry['id']}/file",
                      headers=as_(fx, "activities"))
    assert full.status_code == 200 and full.headers["content-type"] == "image/jpeg"


def test_other_chairs_do_not_see_the_photos(fx, client):
    """`activities` is narrow: a registration chair's global scope does not
    include it, and it reaches no roster either."""
    assert client.get("/admin/photos", headers=as_(fx, "chair")).status_code == 403
    assert client.get(f"/sponsor/roster?school_id={fx.uni_id}",
                      headers=as_(fx, "activities")).status_code == 403


def test_the_chair_adds_edits_and_deletes_categories(fx, client):
    chair = as_(fx, "activities")
    made = client.post("/admin/photos/categories", headers=chair, json={
        "name": "Best stuffed animal photo", "description": "Bring a friend."})
    assert made.status_code == 200, made.text
    new_id = made.json()["category"]["id"]

    twin = client.post("/admin/photos/categories", headers=chair,
                       json={"name": "best STUFFED animal photo"})
    assert twin.status_code == 422
    assert "already a category" in twin.json()["errors"][0]

    edited = client.patch(f"/admin/photos/categories/{new_id}", headers=chair,
                          json={"name": "Best plush photo", "accepting": False})
    assert edited.json()["category"]["name"] == "Best plush photo"
    assert edited.json()["category"]["accepting"] is False

    names = [c["name"] for c in client.get("/admin/photos", headers=chair)
             .json()["categories"]]
    assert names == ["Best flower photo", "Best plush photo"], "new ones go last"

    assert client.delete(f"/admin/photos/categories/{new_id}",
                         headers=chair).status_code == 200
    assert len(client.get("/admin/photos", headers=chair).json()["categories"]) == 1


def test_deleting_a_category_removes_its_photos(fx, client):
    category = open_flowers(fx, client)
    send(client, fx, category)
    response = client.delete(f"/admin/photos/categories/{category}",
                             headers=as_(fx, "activities"))
    assert response.json()["removed"] == 1
    assert not files_in(fx)
    listed = client.get("/me/photos", headers=as_(fx, "delegate")).json()
    assert listed["categories"] == []


def test_the_chair_takes_down_one_photo(fx, client):
    category = open_flowers(fx, client)
    send(client, fx, category)
    chair = as_(fx, "activities")
    entry = client.get("/admin/photos", headers=chair).json()["entries"][0]
    assert client.delete(f"/admin/photos/entries/{entry['id']}",
                         headers=chair).status_code == 200
    assert client.get("/admin/photos", headers=chair).json()["entries"] == []


def test_redacting_a_delegate_removes_their_photos(fx, client):
    category = open_flowers(fx, client)
    send(client, fx, category)
    response = client.post(f"/sponsor/people/{fx.delegate_id}/redact",
                           headers=as_(fx, "uni_sponsor"))
    assert response.status_code == 200, response.text
    assert client.get("/admin/photos", headers=as_(fx, "activities")).json()["entries"] == []
    assert not files_in(fx)
