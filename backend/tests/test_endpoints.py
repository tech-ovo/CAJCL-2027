"""Every endpoint, against a wrong-scope and a wrong-school credential.

docs/stack.md: "The repository is public, so every endpoint is documented to
anyone curious. The realistic threat is not a database dump; it is a sponsor at
one school reading another school's roster because an endpoint checked identity
but not scope."

This file is that check. ROUTES below lists every guarded endpoint, and
test_every_guard_is_covered asserts the list matches the guards the application
actually registered -- so an endpoint added without a test here fails the suite
rather than shipping unexamined.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]

from backend import api
from backend.lib import auth

from .helpers import Fixture


@pytest.fixture
def fx(tmp_path, monkeypatch):
    with Fixture(tmp_path) as f:
        monkeypatch.setattr(api, "_db", f.db)
        yield f


@pytest.fixture
def client(fx):
    from fastapi.testclient import TestClient
    return TestClient(api.app, raise_server_exceptions=False)


def as_(fx, who: str) -> dict:
    return {"Authorization": f"Bearer {fx.sign_in(who)}"}


# ---------------------------------------------------------------------------
# The route table
# ---------------------------------------------------------------------------
# (guard name, method, path template, body)
#
# `{person}` and `{school}` are substituted with ids belonging to the OTHER
# school, so the same table drives both the wrong-scope and the wrong-school
# pass. A route that ignores school scoping will return 200 for a resource it
# should never have shown, and that is precisely the bug being hunted.

ROUTES = [
    ("auth.impersonate", "POST", "/auth/impersonate",
     {"target_person_id": "{person}", "admin_code": "x"}),

    ("sponsor.roster", "GET", "/sponsor/roster?school_id={school}", None),
    ("sponsor.roster.parse", "POST", "/sponsor/roster/parse",
     {"school_id": "{school}", "text": "Ann Example"}),
    ("sponsor.roster.commit", "POST", "/sponsor/roster/commit",
     {"school_id": "{school}", "text": "Ann Example",
      "idempotency_key": "nope", "rows": []}),
    ("sponsor.people.add", "POST", "/sponsor/people",
     {"school_id": "{school}", "first_name": "Ann", "last_name": "Example"}),
    ("sponsor.people.edit", "PATCH", "/sponsor/people/{person}", {"first_name": "X"}),
    ("sponsor.people.cancel", "POST", "/sponsor/people/{person}/cancel", {}),
    ("sponsor.people.restore", "POST", "/sponsor/people/{person}/restore", {}),
    ("sponsor.people.regenerate", "POST",
     "/sponsor/people/{person}/regenerate-code", {}),
    ("sponsor.chapter_leader", "POST",
     "/sponsor/people/{person}/chapter-leader", {"granted": True}),
    ("sponsor.paper_forms", "POST", "/sponsor/paper-forms",
     {"person_id": "{person}", "form_type": "student_waiver", "received": True}),
    ("sponsor.chapter_entries.list", "GET",
     "/sponsor/chapter-entries?school_id={school}", None),
    ("sponsor.chapter_entries.create", "POST", "/sponsor/chapter-entries",
     {"school_id": "{school}", "item_id": 1}),
    ("sponsor.chapter_entries.delete", "DELETE",
     "/sponsor/chapter-entries/{entry}", None),
    ("sponsor.invoice", "GET", "/sponsor/invoice?school_id={school}", None),
    ("sponsor.packet", "GET", "/sponsor/packet?school_id={school}", None),
    ("sponsor.invoice.html", "GET", "/sponsor/invoice.html?school_id={school}", None),

    ("me.activity_sheet", "GET", "/me/activity-sheet", None),
    ("me.activity_sheet.save", "PUT", "/me/activity-sheet", {"selected": []}),

    ("admin.schools.list", "GET", "/admin/schools", None),
    ("admin.schools.create", "POST", "/admin/schools",
     {"name": "New Chapter", "level": "HS"}),
    ("admin.schools.update", "PATCH", "/admin/schools/{school}", {"city": "Nowhere"}),
    ("admin.schools.people", "POST", "/admin/schools/{school}/people",
     {"first_name": "Ann", "last_name": "Example"}),
    ("admin.registration", "GET", "/admin/registration", None),
    ("admin.payments.list", "GET", "/admin/payments?school_id={school}", None),
    ("admin.payments.record", "POST", "/admin/payments",
     {"school_id": "{school}", "amount_cents": 100}),
    ("admin.people.unlock", "POST", "/admin/people/{person}/unlock-forms", {}),
    ("admin.audit", "GET", "/admin/audit", None),
    ("admin.settings.get", "GET", "/admin/settings", None),
    ("admin.settings.put", "PUT", "/admin/settings",
     {"settings": {"convention.year": "2027"}}),
    ("admin.documents.put", "PUT", "/admin/documents/welcome_body", {"title": "x"}),
    ("admin.catalog.get", "GET", "/admin/catalog", None),
    ("admin.catalog.put", "PUT", "/admin/catalog/items/1", {"name": "x"}),
    ("admin.announcements.list", "GET", "/admin/announcements", None),
    ("admin.announcements.create", "POST", "/admin/announcements", {"body_md": "hi"}),
    ("admin.roles.list", "GET", "/admin/roles", None),
    ("admin.roles.create", "POST", "/admin/roles",
     {"key": "x", "name": "X", "scopes": ["awards"]}),
    ("admin.people.roles", "POST", "/admin/people/{person}/roles",
     {"role_key": "delegate"}),
    ("admin.announcements.set_active", "POST",
     "/admin/announcements/1/active", {"active": False}),
    ("sponsor.people.regenerate_many", "POST", "/sponsor/regenerate-codes",
     {"person_ids": ["{person}"]}),
    ("admin.overview", "GET", "/admin/overview", None),
    ("admin.checkin", "GET", "/admin/checkin", None),
    ("admin.checkin.mark", "POST", "/admin/checkin/{school}", {"arrived": True}),
    ("admin.people.waive", "POST",
     "/admin/people/{person}/waive-activity-sheet", {"waived": True}),
    ("admin.academics.counts", "GET", "/admin/academics/counts", None),
    ("admin.academics.item", "GET", "/admin/academics/item/1", None),
    ("admin.academics.sheet", "GET", "/admin/academics/item/1/sheet", None),
    ("admin.board.list", "GET", "/admin/board", None),
    ("admin.people.rename", "PATCH", "/admin/people/{person}/name",
     {"first_name": "Renamed", "last_name": "Person"}),
    ("admin.people.search", "GET", "/admin/people?school_id={school}", None),
    ("admin.warm.get", "GET", "/admin/warm", None),
    ("admin.warm.put", "PUT", "/admin/warm", {"hours": 1}),
    ("admin.export", "POST", "/admin/export", {"format": "sql"}),
    ("admin.usage", "GET", "/admin/usage", None),
    ("admin.demo.reset", "POST", "/admin/demo/reset", {}),
]


def fill(value, fx):
    """Substitute ids belonging to the OTHER school."""
    if isinstance(value, str):
        return (value.replace("{person}", str(fx.other_delegate_id))
                     .replace("{school}", str(fx.other_id))
                     .replace("{entry}", "1"))
    if isinstance(value, dict):
        return {k: fill(v, fx) for k, v in value.items()}
    if isinstance(value, list):
        # Without this, a route taking a list of ids was probed with the
        # literal string "{person}" -- which tested the parser, not the
        # authorization, and passed for the wrong reason.
        return [fill(v, fx) for v in value]
    return value


def call(client, method, path, body, headers):
    return client.request(method, path, json=body, headers=headers)


def without_scope(guard: api.Guard) -> str:
    """A fixture identity holding NONE of this guard's scopes.

    Deliberately computed from the guard rather than hard-coded per route: a
    route whose scopes change gets a correspondingly changed negative test with
    no edit here.
    """
    holdings = {
        "delegate": {"delegate"},
        "uni_sponsor": {"sponsor", "chapter"},
        "chair": {"registration"},
    }
    for who, scopes in holdings.items():
        if not (set(guard.scopes) & scopes):
            return who
    raise AssertionError(f"no identity lacks all of {guard.scopes}")


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------

def test_every_guard_is_covered_by_this_file():
    """An endpoint added without an authorization test fails here.

    This is the load-bearing assertion in the file. Without it, the suite would
    quietly stop covering new endpoints the moment somebody forgot.
    """
    listed = {name for name, *_ in ROUTES}
    registered = set(api.GUARDS)
    assert listed == registered, (
        f"untested endpoints: {sorted(registered - listed)}; "
        f"stale entries: {sorted(listed - registered)}"
    )


def test_no_route_is_accidentally_public():
    """Only the public and auth surfaces may be reached with no credential."""
    allowed = {
        "/public/stats", "/public/convention", "/public/announcements",
        "/auth/redeem", "/health",
        # These take any valid session and check authority in the handler.
        "/auth/me", "/auth/logout", "/auth/impersonate/end",
        "/me/adult-sheet",
        "/auth/sessions/{session_id}/revoke",
    }
    guarded_paths = set()
    for name, method, path, _ in ROUTES:
        guarded_paths.add(path.split("?")[0])

    for route in api.app.routes:
        path = getattr(route, "path", None)
        if not path or not hasattr(route, "methods"):
            continue
        if path in allowed:
            continue
        template = path.replace("{person_id}", "{person}") \
                       .replace("{school_id}", "{school}") \
                       .replace("{entry_id}", "{entry}") \
                       .replace("{item_id}", "1") \
                       .replace("{announcement_id}", "1") \
                       .replace("{key}", "welcome_body")
        assert template in guarded_paths, f"{path} has no declared guard"


# ---------------------------------------------------------------------------
# Wrong scope
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,method,path,body",
                         ROUTES, ids=[r[0] for r in ROUTES])
def test_rejects_a_wrong_scope_credential(fx, client, name, method, path, body):
    guard = api.GUARDS[name]
    headers = as_(fx, without_scope(guard))
    response = call(client, method, fill(path, fx), fill(body, fx), headers)
    assert response.status_code == 403, (
        f"{name} accepted a credential without {guard.scopes}: "
        f"{response.status_code} {response.text[:200]}"
    )


@pytest.mark.parametrize("name,method,path,body",
                         ROUTES, ids=[r[0] for r in ROUTES])
def test_rejects_a_missing_credential(fx, client, name, method, path, body):
    response = call(client, method, fill(path, fx), fill(body, fx), {})
    assert response.status_code == 401, (
        f"{name} accepted no credential at all: {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Wrong school -- the bug this system actually has to survive
# ---------------------------------------------------------------------------

SCHOOL_SCOPED = [r for r in ROUTES
                 if api.GUARDS[r[0]].school_rule == "own"
                 and ("{school}" in r[2] or "{person}" in r[2]
                      or "{school}" in str(r[3]) or "{person}" in str(r[3]))]


@pytest.mark.parametrize("name,method,path,body",
                         SCHOOL_SCOPED, ids=[r[0] for r in SCHOOL_SCOPED])
def test_a_sponsor_cannot_reach_another_school(fx, client, name, method, path, body):
    """University High's sponsor, aimed at Rival High's roster.

    The credential is entirely valid and carries exactly the right scope. The
    only thing standing between it and another chapter's data is the
    school-scoping rule.
    """
    headers = as_(fx, "uni_sponsor")
    response = call(client, method, fill(path, fx), fill(body, fx), headers)
    assert response.status_code == 403, (
        f"{name} let University High's sponsor reach Rival High: "
        f"{response.status_code} {response.text[:200]}"
    )


def test_a_sponsor_reaches_their_own_school_normally(fx, client):
    """The negative tests would pass trivially if everything returned 403."""
    headers = as_(fx, "uni_sponsor")
    assert client.get("/sponsor/roster", headers=headers).status_code == 200
    assert client.get(f"/sponsor/roster?school_id={fx.uni_id}",
                      headers=headers).status_code == 200
    assert client.get("/sponsor/invoice", headers=headers).status_code == 200


def test_an_administrative_scope_reaches_any_school(fx, client):
    """Administrative scopes are global; identity scopes never are."""
    headers = as_(fx, "chair")
    for school_id in (fx.uni_id, fx.other_id):
        assert client.get(f"/sponsor/roster?school_id={school_id}",
                          headers=headers).status_code == 200


# ---------------------------------------------------------------------------
# The Drive folder
# ---------------------------------------------------------------------------

def test_the_drive_folder_is_hidden_from_registration_chairs(fx, client):
    """It points at scanned waivers and medical forms for minors. Only the
    Convention Presidents -- scope '*' -- ever see the link."""
    with fx.db.tx() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        tx.run("schools.update", (
            school["name"], school["level"], school["city"], 0, 0, None,
            "active", None, "https://drive.example/secret-folder",
            "2026-09-01T00:00:00Z", fx.uni_id))
        tx.audit("school.update", "Test set a Drive folder.", school_id=fx.uni_id)

    chair = client.get("/admin/schools", headers=as_(fx, "chair")).json()
    assert all("drive_folder_id" not in s for s in chair["schools"])
    assert "secret-folder" not in str(chair)

    admin = client.get("/admin/schools", headers=as_(fx, "admin")).json()
    assert any(s.get("drive_folder_id") for s in admin["schools"])


def test_a_registration_chair_cannot_set_the_drive_folder(fx, client):
    response = client.patch(
        f"/admin/schools/{fx.uni_id}",
        json={"drive_folder_id": "https://drive.example/mine"},
        headers=as_(fx, "chair"))
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Impersonation over HTTP
# ---------------------------------------------------------------------------

def test_impersonation_end_to_end(fx, client):
    admin = as_(fx, "admin")
    response = client.post("/auth/impersonate", headers=admin, json={
        "target_person_id": fx.delegate_id, "admin_code": fx.codes["admin"]})
    assert response.status_code == 200
    body = response.json()
    assert body["person"]["impersonation"]["active"] is True
    assert body["person"]["impersonation"]["can_write"] is False

    # The impersonation session sees what the delegate sees...
    imp = {"Authorization": f"Bearer {body['token']}"}
    assert client.get("/me/activity-sheet", headers=imp).status_code == 200

    # ...but cannot write, because it is read-only unless explicitly toggled.
    assert client.put("/me/activity-sheet", headers=imp,
                      json={"selected": []}).status_code == 403


def test_impersonation_requires_the_admins_own_code_over_http(fx, client):
    response = client.post("/auth/impersonate", headers=as_(fx, "admin"), json={
        "target_person_id": fx.delegate_id,
        "admin_code": fx.codes["uni_sponsor"]})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Sign-out
# ---------------------------------------------------------------------------

def test_sign_out_is_server_side(fx, client):
    headers = as_(fx, "delegate")
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401


# ---------------------------------------------------------------------------
# Request size
# ---------------------------------------------------------------------------

def test_an_oversized_body_is_refused_before_it_is_parsed(fx, client):
    """The roster paste is capped at 500 lines, but that check runs after
    FastAPI has read and parsed the whole body. The middleware refuses on the
    declared Content-Length, so nothing large is ever parsed at all."""
    headers = as_(fx, "uni_sponsor")
    huge = "x" * (api.MAX_BODY_BYTES + 1024)
    response = client.post("/sponsor/roster/parse",
                           json={"text": huge}, headers=headers)
    assert response.status_code == 413
    assert "smaller batches" in response.text


def test_a_body_under_the_cap_still_gets_through(fx, client):
    headers = as_(fx, "uni_sponsor")
    response = client.post("/sponsor/roster/parse",
                           json={"text": "Aurelia Vance\nMarcus Reed"},
                           headers=headers)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# The scheduled work
# ---------------------------------------------------------------------------

def test_autoexport_is_not_scheduled_outside_convention():
    """It runs every ten minutes during live grading and never otherwise.

    Left scheduled all year, it starts a container 144 times a day to read one
    setting, find it off, and stop. `LIVE_GRADING` in backend/app.py is the
    switch, and this test exists so that flipping it on for convention and
    forgetting to flip it back is caught by CI rather than by a bill.

    If this fails and convention is over, set LIVE_GRADING = False and deploy.
    """
    source = (ROOT / "backend" / "app.py").read_text(encoding="utf-8")

    assert re.search(r"^LIVE_GRADING = (True|False)$", source, re.MULTILINE), \
        "LIVE_GRADING should be a plain module-level flag in backend/app.py"

    # The reconciler is unconditional on purpose: it is what makes the "keep
    # warm" button survive a deploy, and it is the cheapest thing here.
    assert 'schedule=modal.Period(minutes=5)' in source, \
        "the warm reconciler must stay scheduled -- a deploy resets the autoscaler"

    if re.search(r"^LIVE_GRADING = True$", source, re.MULTILINE):
        pytest.skip("LIVE_GRADING is on; remember to turn it off after convention")

    assert "schedule=modal.Period(minutes=10) if LIVE_GRADING else None" in source, \
        "auto-export should only carry a schedule when LIVE_GRADING is on"


# ---------------------------------------------------------------------------
# Things that must work on a machine with nothing set up
# ---------------------------------------------------------------------------

def test_the_time_zone_database_is_a_declared_dependency():
    """`zoneinfo` reads the OPERATING SYSTEM's time-zone database.

    Linux and macOS ship one. Windows does not, and neither does every slim
    container base — so `ZoneInfo("America/Los_Angeles")` in clock.py raises at
    import time and the entire application fails before running a line.

    This passed for weeks on a Windows machine that happened to have `tzdata`
    installed as a dependency of pandas. It failed on the first clean virtual
    environment. Declaring it is the fix; this is the reminder.
    """
    text = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()
             if line.strip() and not line.strip().startswith("#")]
    assert any(line.split(";")[0].strip() == "tzdata" for line in lines), \
        "backend/requirements.txt must declare tzdata"

    # And unconditionally: a marker would leave Linux depending on whatever the
    # base image happens to ship.
    tz = next(line for line in lines if line.split(";")[0].strip() == "tzdata")
    assert ";" not in tz, "tzdata should have no platform marker"


def test_clock_explains_itself_when_the_time_zone_data_is_missing():
    """The real traceback is twenty frames of importlib naming neither the
    cause nor the fix. Anyone who hits this is on their first day."""
    source = (ROOT / "backend" / "lib" / "clock.py").read_text(encoding="utf-8")
    assert "pip install tzdata" in source
    assert "Windows" in source


def test_the_board_script_loads_without_importing_the_backend():
    """`modal run backend/app.py::board` reads board.json ON YOUR MACHINE and
    does the database work in the container.

    If importing scripts/add_board.py pulls in backend.lib, that local half
    needs a working backend environment — a time-zone database, the Turso
    driver — for a job that only reads a JSON file. It failed exactly that way
    on Windows.
    """
    import subprocess
    import sys as _sys

    probe = (
        "import sys; sys.path.insert(0, r'%s');"
        "import scripts.add_board;"
        "print([m for m in sys.modules if m.startswith('backend')])"
    ) % str(ROOT)

    result = subprocess.run([_sys.executable, "-c", probe],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]", (
        "importing scripts.add_board pulled in " + result.stdout.strip())


def test_the_roster_page_never_offers_a_button_the_api_refuses():
    """The roster is served to two different people and it must not lie to
    either.

    A sponsor opens it for their own chapter; a registration chair opens the
    same page for somebody else's. Every control on it is therefore reachable
    by both -- unless it is wrapped in a `hasScope` check, which the page does
    for the two that genuinely need `*`.

    "Make leader" was not wrapped and was not shared: it took `sponsor` alone,
    so a chair saw a button that answered 403. Nothing failed until somebody
    pressed it.
    """
    page = (pathlib.Path(__file__).resolve().parents[2]
            / "frontend/public/js/pages/roster.js").read_text(encoding="utf-8")

    shared = {name: guard for name, guard in api.GUARDS.items()
              if name.startswith("sponsor.")}
    offenders = []
    for name, guard in sorted(shared.items()):
        # The endpoint the page calls, derived from the guard's own route.
        path = next((route[2] for route in ROUTES if route[0] == name), None)
        if path is None:
            continue
        stem = path.split("{")[0].split("?")[0].rstrip("/")
        if stem not in page:
            continue
        if not {"sponsor", "registration"} <= set(guard.scopes):
            offenders.append(f"{name} takes {guard.scopes}")

    assert offenders == [], (
        "the roster page offers these to a chair the API turns away: "
        + "; ".join(offenders))


def test_the_overview_counts_everybody_who_is_attending(fx, client):
    """The Overview totals must not stop at chapter boundaries.

    CHAPTERS are counted, because that figure means "how many delegations".
    PEOPLE are counted wherever they come from: SCL, the state board and --
    later -- members at large all attend and all eat, so they belong in the
    totals. The table of chapters underneath still leaves them out, because
    they have no sponsor to chase and no invoice to settle.

    Both halves used to come from a query filtered to `kind = 'chapter'`, which
    made the meal figures short by however many people registered outside a
    chapter. Those figures are what the caterer is given.
    """
    body = client.get("/admin/overview", headers=as_(fx, "chair")).json()
    totals = body["totals"]

    kinds = {row["school_name"]: row["kind"] for row in body["chapters"]}
    assert "CAJCL State Board" in kinds, (
        "an organization was filtered out of the rows the totals are built "
        "from, so its attendees are missing from the meal figures")
    assert kinds["CAJCL State Board"] == "organization"
    assert totals["chapters"] == len(
        [k for k in kinds.values() if k == "chapter"]), (
        "an organization is not a chapter")

    # Counted straight off the table, not through the registry: the point of
    # the check is that the cached totals match the rows.
    import sqlite3
    raw = sqlite3.connect(fx.path)
    attending = raw.execute(
        "SELECT COUNT(*) FROM people WHERE status = 'active'").fetchone()[0]
    raw.close()

    assert totals["people"] == attending, (
        "somebody registered outside a chapter is still attending")


def test_a_chair_can_give_a_new_chapter_its_sponsor(fx, client):
    """The step that closes the loop on creating a chapter.

    A chair adds a chapter from the Chapters page, and until the roster grew an
    "Add the sponsor" button that chapter sat there with nobody able to sign in
    to it. The endpoint was always here; nothing called it, and the roster's
    own banner said to use Settings, which grants roles to people who already
    have accounts.
    """
    headers = as_(fx, "chair")
    made = client.post("/admin/schools",
                       json={"name": "Brand New High School", "city": "Irvine",
                             "level": "HS"},
                       headers=headers)
    assert made.status_code == 200, made.text
    school_id = made.json()["id"]

    roster = client.get(f"/sponsor/roster?school_id={school_id}",
                        headers=headers).json()
    assert roster["people"] == [], "a new chapter starts empty"

    created = client.post(f"/admin/schools/{school_id}/people",
                          json={"first_name": "Nia", "last_name": "Okafor",
                                "email": "nia@example.edu",
                                "adult_type": "sponsor"},
                          headers=headers)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["code"].startswith("SPO-"), "a sponsor gets a sponsor's prefix"

    roster = client.get(f"/sponsor/roster?school_id={school_id}",
                        headers=headers).json()
    sponsors = [p for p in roster["people"] if p.get("adult_type") == "sponsor"]
    assert len(sponsors) == 1 and sponsors[0]["first_name"] == "Nia"

    # And the code signs them in, which is the whole point of issuing it.
    signed_in = client.post("/auth/redeem", json={"code": body["code"]})
    assert signed_in.status_code == 200, signed_in.text
    assert (signed_in.json()["person"]["school"]["name"]
            == "Brand New High School")
