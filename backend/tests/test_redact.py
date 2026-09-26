"""Tests for the attendee redaction capability (PRIVACY.md §2.4, §8 item 5)."""

from __future__ import annotations

import sqlite3
import pytest

from backend import api
from backend.lib import clock
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


@pytest.fixture
def sponsor(fx):
    return {"Authorization": f"Bearer {fx.sign_in('uni_sponsor')}"}


def test_redact_delegate_details(fx, client, sponsor):
    """Delegate's personal details become 'REDACTED', row is retained, stats updated."""
    orig_id = fx.delegate_id
    with fx.db.read() as tx:
        delegate = tx.one("people.get", (orig_id,))
    assert delegate is not None
    orig_name = f"{delegate['first_name']} {delegate['last_name']}"

    # Sign in as delegate to create an active session
    fx.sign_in("delegate")

    with fx.db.tx() as tx:
        # grant chapter leader
        role = tx.one("roles.by_key", ("chapter_leader",))
        tx.run("people.grant_role", (orig_id, role["id"], fx.uni_sponsor_id, clock.now_iso()))
        tx.audit("role.grant", f"Sponsor made {orig_name} chapter leader.", school_id=fx.uni_id)

    # Perform redaction via HTTP endpoint
    res = client.post(f"/sponsor/people/{orig_id}/redact", headers=sponsor)
    assert res.status_code == 200, res.text
    assert res.json() == {"ok": True}

    # Verify database state
    with fx.db.read() as tx:
        p = tx.one("people.get", (orig_id,))
        assert p is not None
        assert p["id"] == orig_id
        assert p["school_id"] == fx.uni_id
        assert p["first_name"] == "REDACTED"
        assert p["last_name"] == "REDACTED"
        assert p["middle_name"] is None
        assert p["suffix"] is None
        assert p["raw_name_input"] == "REDACTED"
        assert p["cell_phone"] == "REDACTED"
        assert p["guardian_name"] == "REDACTED"
        assert p["guardian_phone"] == "REDACTED"
        assert p["grade"] is None
        assert p["latin_level"] is None
        assert p["meal"] is None
        assert p["status"] in ("cancelled", "cancelled_paid")

        # Code HMAC is randomized so old code cannot work
        assert p["code_hmac"].startswith("redacted-")

        # Sessions revoked
        active_sessions = tx._backend.execute(
            "SELECT * FROM sessions WHERE person_id = ? AND revoked_at IS NULL", (orig_id,)
        )
        assert len(active_sessions) == 0

        # Roles revoked
        roles = tx._backend.execute(
            "SELECT * FROM person_roles WHERE person_id = ?", (orig_id,)
        )
        assert len(roles) == 0

        # Audit log entries for this person were scrubbed of their name
        audit_rows = tx._backend.execute(
            "SELECT * FROM audit_log WHERE school_id = ?", (fx.uni_id,)
        )
        for row in audit_rows:
            summary = row["summary"]
            assert orig_name not in summary, f"Name leaked in summary: {summary}"

        # Audit log has person.redact entry with no name
        redact_entries = tx._backend.execute(
            "SELECT * FROM audit_log WHERE action = 'person.redact' AND entity_id = ?", (orig_id,)
        )
        assert len(redact_entries) >= 1
        assert orig_name not in redact_entries[0]["summary"]
        assert f"attendee #{orig_id}" in redact_entries[0]["summary"]


def test_redact_adult_details(fx, client, sponsor):
    """Adult details (email, notes) are redacted and grants removed."""
    adult_id = fx.chaperone_id
    with fx.db.read() as tx:
        adult = tx.one("people.get", (adult_id,))
    orig_name = f"{adult['first_name']} {adult['last_name']}"

    with fx.db.tx() as tx:
        tx.run("grants.create", (adult_id, fx.other_id, fx.uni_sponsor_id, clock.now_iso(), "Note"))
        tx.audit("sponsor.grant", f"Granted {orig_name} access.", school_id=fx.uni_id)

    res = client.post(f"/sponsor/people/{adult_id}/redact", headers=sponsor)
    assert res.status_code == 200

    with fx.db.read() as tx:
        p = tx.one("people.get", (adult_id,))
        assert p["first_name"] == "REDACTED"
        assert p["last_name"] == "REDACTED"
        assert p["email"] == "REDACTED"
        assert p["availability_note"] == "REDACTED"
        assert p["cell_phone"] == "REDACTED"

        # Grant deleted
        grants = tx._backend.execute(
            "SELECT * FROM sponsor_school_grants WHERE person_id = ?", (adult_id,)
        )
        assert len(grants) == 0

        # Audit log check
        audit_rows = tx._backend.execute(
            "SELECT * FROM audit_log WHERE school_id = ?", (fx.uni_id,)
        )
        for row in audit_rows:
            assert orig_name not in row["summary"], f"Name leaked in summary: {row['summary']}"


def test_redact_contest_entries(fx, client, sponsor):
    """Contest submissions are unranked and personal text redacted."""
    delegate_id = fx.delegate_id
    with fx.db.read() as tx:
        delegate = tx.one("people.get", (delegate_id,))
        contests = tx.all("contests.all")
        contest = contests[0]

    now = clock.now_iso()
    with fx.db.tx() as tx:
        tx.run("contests.entry_create", (
            contest["item_id"], fx.uni_id, delegate_id, "Open",
            "My Secret Title", "My Secret Poem text", None, None, None,
            10, "counted", "drive-123", "drive-folder", "my_poem.txt", "text/plain", 100,
            delegate_id, now, now
        ))
        tx.audit("contest.submit", f"{delegate['first_name']} {delegate['last_name']} submitted an entry.",
                 actor_person_id=delegate_id, entity_type="contest_entry", school_id=fx.uni_id)

    # Redact
    res = client.post(f"/sponsor/people/{delegate_id}/redact", headers=sponsor)
    assert res.status_code == 200

    with fx.db.read() as tx:
        entry = tx.one("contests.entry_for_person", (delegate_id, contest["item_id"]))
        assert entry is not None
        assert entry["title"] == "REDACTED"
        assert entry["body_text"] == "REDACTED"
        assert entry["original_name"] == "REDACTED"
        assert entry["drive_file_id"] is None


def test_redacted_person_cannot_be_restored_or_edited(fx, client, sponsor):
    """A redacted attendee cannot be restored, edited, or reissued a code."""
    delegate_id = fx.delegate_id
    res = client.post(f"/sponsor/people/{delegate_id}/redact", headers=sponsor)
    assert res.status_code == 200

    # Attempt to restore
    res = client.post(f"/sponsor/people/{delegate_id}/restore", headers=sponsor)
    assert res.status_code == 409
    assert "redacted" in res.text.lower()

    # Attempt to edit
    res = client.patch(f"/sponsor/people/{delegate_id}", headers=sponsor, json={"first_name": "NewName"})
    assert res.status_code == 403
    assert "redacted" in res.text.lower()

    # Attempt to regenerate code
    res = client.post(f"/sponsor/people/{delegate_id}/regenerate-code", headers=sponsor)
    assert res.status_code == 409
    assert "redacted" in res.text.lower()


def test_redaction_school_scoping(fx, client, sponsor):
    """Sponsor at one school cannot redact an attendee at another school."""
    other_delegate_id = fx.other_delegate_id
    res = client.post(f"/sponsor/people/{other_delegate_id}/redact", headers=sponsor)
    assert res.status_code == 403


def test_audit_trigger_rejects_illegal_updates(fx):
    """The trigger rejects updates to audit_log unless only summary changes and contains REDACTED."""
    with fx.db.tx() as tx:
        tx.audit("school.create", "Sample log entry.", school_id=fx.uni_id)
        row = tx._backend.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1", ())[0]

    # Regular update fails
    with pytest.raises(sqlite3.IntegrityError, match="audit_log is append-only"):
        with fx.db.tx() as tx:
            tx._backend.execute("UPDATE audit_log SET summary = 'Something else' WHERE id = ?", (row["id"],))

    # Changing another column even with REDACTED fails
    with pytest.raises(sqlite3.IntegrityError, match="audit_log is append-only"):
        with fx.db.tx() as tx:
            tx._backend.execute("UPDATE audit_log SET school_id = 999, summary = 'REDACTED' WHERE id = ?", (row["id"],))

    # Permitted redaction update succeeds
    with fx.db.tx() as tx:
        tx._backend.execute("UPDATE audit_log SET summary = 'Sample log entry with REDACTED.' WHERE id = ?", (row["id"],))
        updated = tx._backend.execute("SELECT summary FROM audit_log WHERE id = ?", (row["id"],))[0]
        assert "REDACTED" in updated["summary"]


def test_redact_scrubs_roster_import_raw_text(fx, client, sponsor):
    """Raw text in roster_imports has the attendee's name redacted."""
    raw = "UniqueStudentName,10,HS-2\n"
    # Preview
    res = client.post("/sponsor/roster/parse", headers=sponsor, json={"school_id": fx.uni_id, "text": raw})
    assert res.status_code == 200
    key = res.json()["idempotency_key"]
    rows = res.json()["rows"]

    # Commit
    res = client.post("/sponsor/roster/commit", headers=sponsor, json={
        "school_id": fx.uni_id, "text": raw, "idempotency_key": key, "rows": rows,
    })
    assert res.status_code == 200
    person_id = res.json()["created"][0]["id"]

    # Check imported text initially has name
    with fx.db.read() as tx:
        p = tx.one("people.get", (person_id,))
        imp = tx.one("roster.import_get", (p["roster_import_id"],))
        assert "UniqueStudentName" in imp["raw_text"]

    # Redact attendee
    res = client.post(f"/sponsor/people/{person_id}/redact", headers=sponsor)
    assert res.status_code == 200

    # Verify raw_text is scrubbed
    with fx.db.read() as tx:
        imp = tx.one("roster.import_get", (p["roster_import_id"],))
        assert "UniqueStudentName" not in imp["raw_text"]
        assert "REDACTED" in imp["raw_text"]


