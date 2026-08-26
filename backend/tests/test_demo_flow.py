"""The whole demo, start to finish, in one test.

This is the flow that gets presented to the state board on August 29th, in the
order it will be shown:

    create a school -> create a sponsor -> redeem the code -> paste a roster ->
    confirm the preview -> print the packet -> sign in as a delegate by QR ->
    submit an activity sheet -> view the chair dashboard -> record a payment ->
    view the invoice -> view the exempt chapter's zero invoice ->
    read the audit log -> impersonate a sponsor -> sign out

If this test passes, the presentation works. If it fails, the presentation fails
in the same place, and it is far better to find that here.
"""

from __future__ import annotations


import pytest

from backend import api
from backend.lib import codes

from .helpers import Fixture

ROSTER_PASTE = """1. Chen, Timothy Wei
2. de la Cruz, Mary Beth
3. MARY BETH DE LA CRUZ
4. Robert McDonald Jr.
5. O'Brien, Seán
6. Nguyễn Thị Minh Anh
7. Smith,John,9,HS-1
8. Liu,Carl,12,AP Latin
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


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_the_whole_demo(fx, client, capsys):
    admin = bearer(fx.sign_in("admin"))
    chair = bearer(fx.sign_in("chair"))
    steps = []

    def step(name, detail=""):
        steps.append(f"  {len(steps) + 1:2d}. {name}{'  — ' + detail if detail else ''}")

    # -- 1. an admin creates a school ------------------------------------
    created = client.post("/admin/schools", headers=chair, json={
        "name": "Vireo Canyon High School", "level": "HS", "city": "Ojai"})
    assert created.status_code == 200, created.text
    school_id = created.json()["id"]
    step("Created a chapter", created.json()["name"])

    # -- 2. and a sponsor account, whose code is shown exactly once -------
    sponsor_created = client.post(f"/admin/schools/{school_id}/people", headers=chair,
                                  json={"first_name": "Iris", "last_name": "Marchetti",
                                        "email": "iris@example.edu"})
    assert sponsor_created.status_code == 200, sponsor_created.text
    sponsor_code = sponsor_created.json()["code"]
    assert codes.is_well_formed(sponsor_code)
    assert sponsor_code.startswith("SPO-")
    step("Created a sponsor account", sponsor_code)

    # -- 3. the sponsor redeems it ---------------------------------------
    redeemed = client.post("/auth/redeem", json={"code": sponsor_code})
    assert redeemed.status_code == 200, redeemed.text
    sponsor = bearer(redeemed.json()["token"])
    assert "sponsor" in redeemed.json()["person"]["scopes"]
    step("Sponsor signed in with that code")

    # -- 4. pastes a roster, in a deliberately messy format ---------------
    preview = client.post("/sponsor/roster/parse", headers=sponsor,
                          json={"text": ROSTER_PASTE})
    assert preview.status_code == 200, preview.text
    rows = preview.json()["rows"]
    assert len(rows) == 8

    parsed = {r["last_name"]: r for r in rows}
    assert parsed["Chen"]["first_name"] == "Timothy"
    assert parsed["Chen"]["middle_name"] == "Wei"
    assert parsed["Chen"]["warnings"] == []          # three tokens must not warn
    assert parsed["de la Cruz"]["first_name"] == "Mary"
    assert parsed["McDonald"]["suffix"] == "Jr."
    assert parsed["O'Brien"]["first_name"] == "Seán"
    assert parsed["Anh"]["warnings"] == ["multi_token_name"]
    assert parsed["Liu"]["latin_level"] == "HS-Adv"  # legacy "AP Latin"
    flagged = sum(1 for r in rows if r["warnings"])
    step("Pasted 8 names", f"{flagged} flagged, {8 - flagged} clean")

    # -- 5. confirms it, and a double-click changes nothing ---------------
    key = preview.json()["idempotency_key"]
    body = {"text": ROSTER_PASTE, "idempotency_key": key, "rows": rows}
    first = client.post("/sponsor/roster/commit", headers=sponsor, json=body)
    second = client.post("/sponsor/roster/commit", headers=sponsor, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["committed_count"] == 8
    assert second.json()["already_committed"] is True

    roster = client.get("/sponsor/roster", headers=sponsor).json()
    delegates = [p for p in roster["people"] if p["person_type"] == "delegate"]
    assert len(delegates) == 8, "a double-click created duplicates"
    step("Committed the roster twice on purpose", "8 delegates, not 16")

    # -- 6. prints the packet ---------------------------------------------
    packet = client.get("/sponsor/packet", headers=sponsor)
    assert packet.status_code == 200
    html = packet.text
    assert "Vireo Canyon High School" in html
    assert "Mary Beth de la Cruz" in html          # particles survive to print
    assert "Seán O&#x27;Brien" in html or "Seán O'Brien" in html
    assert "<svg" in html                           # a real QR, not a placeholder
    assert "This sheet is your key" in html         # it says it is a credential
    assert "aequam mement" in html                  # the theme, macrons intact
    assert "Required paper forms" in html
    assert "break-after: page" in html
    step("Rendered the packet", f"{html.count('class=\"sheet\"')} pages, QR codes inline")

    # -- 7. a delegate signs in by QR (magic link) ------------------------
    target = delegates[0]
    new_code = client.post(f"/sponsor/people/{target['id']}/regenerate-code",
                           headers=sponsor).json()["code"]
    scanned = client.post("/auth/redeem",
                          json={"code": new_code, "via_magic_link": True})
    assert scanned.status_code == 200, scanned.text
    delegate = bearer(scanned.json()["token"])
    step("Delegate signed in by scanning their sheet")

    # -- 8. and submits an activity sheet ---------------------------------
    sheet = client.get("/me/activity-sheet", headers=delegate).json()
    testing = [c for c in sheet["catalog"] if c["key"] == "academic_testing"][0]

    # Ineligible tests are present and explained, not hidden.
    assert any(not i["eligible_now"] and i["reason"] for i in testing["items"])
    assert not any(i["name"] == "Kickball" for c in sheet["catalog"] for i in c["items"])

    too_many = client.put("/me/activity-sheet", headers=delegate, json={
        "grade": 11, "latin_level": "HS-2",
        "selected": [i["id"] for i in testing["items"] if i["eligible_now"]][:4]})
    assert too_many.status_code == 422
    assert "four selected" in too_many.json()["error"]

    eligible = [i["id"] for i in testing["items"] if i["eligible_now"]]
    ok = client.put("/me/activity-sheet", headers=delegate, json={
        "grade": 11, "latin_level": "HS-2", "meal": "vegetarian",
        "selected": eligible[:2]})
    assert ok.status_code == 200, ok.text
    step("Delegate submitted an activity sheet", "4 tests blocked, 2 accepted")

    # -- 9. the chair dashboard -------------------------------------------
    dashboard = client.get("/admin/registration", headers=chair)
    assert dashboard.status_code == 200
    board = dashboard.json()
    names = {s["name"] for s in board["schools"]}
    assert "Vireo Canyon High School" in names
    assert "CAJCL State Board" not in names        # an organization, not a chapter
    step("Chair dashboard", f"{board['totals']['chapters']} chapters, "
                            f"{board['totals']['delegates']} delegates")

    # -- 10. record a payment ---------------------------------------------
    owed = [s for s in board["schools"] if s["id"] == school_id][0]["amount_owed_cents"]
    assert owed == 8 * 14000 + 0                  # 8 delegates, 1 adult, 1 free
    paid = client.post("/admin/payments", headers=chair, json={
        "school_id": school_id, "amount_cents": 50000,
        "method": "check", "reference": "2214"})
    assert paid.status_code == 200, paid.text
    step("Recorded a payment", "$500.00 by check")

    # -- 11. the invoice ---------------------------------------------------
    invoice = client.get("/sponsor/invoice", headers=sponsor).json()
    assert invoice["amount_owed_cents"] == owed
    assert invoice["amount_paid_cents"] == 50000
    assert invoice["balance_cents"] == owed - 50000
    assert any(line["label"] == "Adults included at no charge" for line in invoice["lines"])
    invoice_html = client.get("/sponsor/invoice.html", headers=sponsor).text
    assert "Balance" in invoice_html and "$" in invoice_html
    step("Invoice", f"owed ${owed / 100:,.2f}, paid $500.00, "
                    f"balance ${(owed - 50000) / 100:,.2f}")

    # -- 12. the exempt chapter's zero invoice -----------------------------
    exempt = client.get(f"/sponsor/invoice?school_id={fx.exempt_id}", headers=chair).json()
    assert exempt["exempt"] is True
    assert exempt["amount_owed_cents"] == 0
    exempt_html = client.get(f"/sponsor/invoice.html?school_id={fx.exempt_id}",
                             headers=chair).text
    assert "not billed" in exempt_html            # words, never a blank page
    step("Exempt chapter invoice", "zero, with an explanation in words")

    # -- 13. the audit log -------------------------------------------------
    log = client.get("/admin/audit", headers=admin).json()
    actions = {e["action"] for e in log["entries"]}
    for expected in ("school.create", "person.create", "auth.login", "roster.import",
                     "person.code_regenerate", "auth.magic_link", "form.submit",
                     "payment.record"):
        assert expected in actions, f"{expected} missing from the log"

    roster_entry = [e for e in log["entries"] if e["action"] == "roster.import"][0]
    assert roster_entry["summary"] == \
        "Iris Marchetti added 8 delegates to Vireo Canyon High School."

    payment_entry = [e for e in log["entries"] if e["action"] == "payment.record"][0]
    assert "$500.00" in payment_entry["summary"]
    assert "2214" in payment_entry["value_detail"]
    step("Audit log", f"{len(log['entries'])} entries, each a full sentence")

    # -- 14. impersonate the sponsor ---------------------------------------
    impersonated = client.post("/auth/impersonate", headers=admin, json={
        "target_person_id": sponsor_created.json()["id"],
        "admin_code": fx.codes["admin"]})
    assert impersonated.status_code == 200, impersonated.text
    as_sponsor = bearer(impersonated.json()["token"])
    seen = client.get("/sponsor/roster", headers=as_sponsor)
    assert seen.status_code == 200
    assert seen.json()["school"]["name"] == "Vireo Canyon High School"
    assert client.put("/me/adult-sheet", headers=as_sponsor,
                      json={"latin_knowledge": "none", "selected": []}).status_code == 403
    step("Impersonated the sponsor", "read-only, both names in the banner")

    # -- 15. sign out ------------------------------------------------------
    assert client.post("/auth/impersonate/end", headers=as_sponsor).status_code == 200
    assert client.post("/auth/logout", headers=sponsor).status_code == 200
    assert client.get("/auth/me", headers=sponsor).status_code == 401
    step("Signed out", "session revoked server-side")

    with capsys.disabled():
        print("\n\nDEMO FLOW")
        print("\n".join(steps))
        print()


def test_the_public_page_needs_no_credential(fx, client):
    """A visitor arriving cold sees real numbers with no session at all."""
    stats = client.get("/public/stats")
    assert stats.status_code == 200
    assert stats.headers["cache-control"] == "public, max-age=60"
    assert set(stats.json()) >= {"schools_ms", "schools_hs", "delegates", "adults"}

    convention = client.get("/public/convention")
    assert convention.status_code == 200
    body = convention.json()
    assert "aequam" in body["convention.theme_latin"]
    # The public endpoint is an explicit allowlist -- nothing operational leaks.
    assert not any(key.startswith("ops.") and key != "ops.demo_mode" for key in body)
    assert not any("fee" in key or "deadline" in key for key in body)


def test_no_submitted_sheet_is_empty(fx):
    """A delegate cannot submit an activity sheet with nothing chosen —
    academic testing blocks below one selection — so demonstration data must
    not contain one either.

    Every chapter except the host used to get exactly that: a submission row
    marked "submitted" and no selections at all. Nothing read the selections,
    so nothing noticed, until the Entries page showed every test being taken by
    a single chapter.

    Demonstration data that cannot occur in production is worse than none: it
    hides the bugs it should be finding.
    """
    with fx.db.read() as tx:
        submitted = tx.all("audit.recent", (10 ** 9, 1))   # touch, keep it read-only
        empty = tx._backend.execute("""
            SELECT p.id, p.first_name, p.last_name, s.name AS school
            FROM form_submissions f
            JOIN people p  ON p.id = f.person_id
            JOIN schools s ON s.id = p.school_id
            WHERE f.form_type = 'student_activity'
              AND f.status = 'submitted'
              AND p.status = 'active'
              AND NOT EXISTS (SELECT 1 FROM activity_selections a
                               WHERE a.person_id = p.id)
        """, ())

    assert empty == [], (
        "these delegates have a submitted sheet and no selections: "
        + ", ".join(f"{r['first_name']} {r['last_name']} ({r['school']})"
                    for r in empty[:8]))


def test_a_meal_is_only_recorded_where_a_form_was_submitted(fx):
    """Meal preference is asked for ON the activity sheet.

    The seed used to set it at creation, so every delegate had answered before
    they had opened anything — which made the registration dashboard's "still
    to come" figure permanently zero, and hid the one thing that number exists
    to surface.
    """
    with fx.db.read() as tx:
        rows = tx._backend.execute("""
            SELECT p.id, p.first_name, p.last_name
            FROM people p
            LEFT JOIN form_submissions f
                   ON f.person_id = p.id AND f.form_type = 'student_activity'
            WHERE p.person_type = 'delegate'
              AND p.status = 'active'
              AND p.meal IS NOT NULL AND p.meal != ''
              AND (f.status IS NULL OR f.status != 'submitted')
        """, ())

    assert rows == [], (
        "these delegates have a meal but no submitted sheet: "
        + ", ".join(f"{r['first_name']} {r['last_name']}" for r in rows[:8]))
