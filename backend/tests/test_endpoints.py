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
    ("sponsor.activity_sheet", "GET",
     "/sponsor/people/{person}/activity-sheet", None),
    ("sponsor.activity_sheet.save", "PUT",
     "/sponsor/people/{person}/activity-sheet",
     {"grade": 10, "latin_level": "HS-2", "meal": "regular",
      "selected": []}),
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
    ("sponsor.packet.print", "POST", "/sponsor/packet",
     {"school_id": "{school}",
      "codes": [{"person_id": "{person}", "code": "DEL-K7M2N-9PQ4T"}]}),
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
    ("admin.logins", "GET", "/admin/logins", None),
    ("admin.school.history", "GET", "/admin/schools/{school}/history", None),

    ("admin.settings.get", "GET", "/admin/settings", None),
    ("admin.settings.put", "PUT", "/admin/settings",
     {"settings": {"convention.year": "2027"}}),
    ("admin.documents.put", "PUT", "/admin/documents/welcome_body", {"title": "x"}),
    ("admin.catalog.get", "GET", "/admin/catalog", None),
    ("admin.catalog.put", "PUT", "/admin/catalog/items/1", {"name": "x"}),
    ("admin.catalog.create", "POST", "/admin/catalog/items",
     {"name": "New Test", "category_id": 1}),
    ("admin.catalog.option", "POST", "/admin/catalog/items/1/options",
     {"name": "An option"}),
    ("admin.catalog.option.put", "PUT", "/admin/catalog/options/1",
     {"name": "Renamed"}),
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
                       .replace("{option_id}", "1") \
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


# ---------------------------------------------------------------------------
# The five jobs that had a working endpoint and no button
# ---------------------------------------------------------------------------
# Each of these was reachable only from a terminal until the screens caught up,
# and each is now promised to the registration chairs in docs/REGISTRATION.md.


def test_a_chair_can_paste_a_roster_for_another_chapter(fx, client):
    """A sponsor whose spreadsheet will not paste is a support call, and the
    only previous answer was to find a president to sign in as them."""
    headers = as_(fx, "chair")
    text = "Nia Okafor\nJoon Park"

    preview = client.post("/sponsor/roster/parse",
                          json={"text": text, "person_type": "delegate",
                                "school_id": fx.other_id},
                          headers=headers)
    assert preview.status_code == 200, preview.text
    assert len(preview.json()["rows"]) == 2

    done = client.post("/sponsor/roster/commit",
                       json={"text": text,
                             "idempotency_key": preview.json()["idempotency_key"],
                             "rows": preview.json()["rows"],
                             "school_id": fx.other_id},
                       headers=headers)
    assert done.status_code == 200, done.text
    assert done.json()["committed_count"] == 2

    # It landed in the chapter that was named, not in the chair's own.
    roster = client.get(f"/sponsor/roster?school_id={fx.other_id}",
                        headers=headers).json()
    assert "Okafor" in [p["last_name"] for p in roster["people"]]


def test_adding_one_person_returns_a_code_that_works(fx, client):
    """The screens that add a single person have to hand over a code.

    `_insert_person` minted one and dropped it, which was invisible while the
    only caller was a paste -- thirty codes nobody reads, printed later from
    the packet. A screen that adds ONE person has no packet to fall back on.
    """
    created = client.post("/sponsor/people",
                          json={"school_id": fx.other_id,
                                "first_name": "Nia", "last_name": "Okafor",
                                "person_type": "delegate"},
                          headers=as_(fx, "chair"))
    assert created.status_code == 200, created.text
    code = created.json().get("code")
    assert code and code.startswith("DEL-"), f"no usable code came back: {code!r}"

    signed_in = client.post("/auth/redeem", json={"code": code})
    assert signed_in.status_code == 200, "the code returned does not sign anybody in"


def test_a_paste_returns_the_codes_it_just_minted(fx, client):
    """The one moment a pasted roster's codes are readable.

    They are stored as an HMAC, so nothing can read them back -- not this test,
    not the packet renderer, not a chair with a terminal. The commit response
    is the only place they exist in the clear, and the sponsor needs them to
    print sheets anybody can sign in with.

    A REPLAYED commit cannot return them, because it reads its rows back from
    the database. The screen has to say so rather than show a print button that
    would produce blocks.
    """
    text = "Ann Example" + chr(10) + "Beth Sample"
    headers = as_(fx, "chair")
    preview = client.post("/sponsor/roster/parse",
                          json={"text": text, "school_id": fx.other_id},
                          headers=headers).json()
    body = {"text": text, "idempotency_key": preview["idempotency_key"],
            "rows": preview["rows"], "school_id": fx.other_id}

    first = client.post("/sponsor/roster/commit", json=body, headers=headers).json()
    codes = [row.get("code") for row in first["created"]]
    assert all(codes), "a paste must hand back the codes it minted"
    assert all(code.startswith("DEL-") for code in codes)

    # And they work, which is the whole point of printing them.
    assert client.post("/auth/redeem", json={"code": codes[0]}).status_code == 200

    replay = client.post("/sponsor/roster/commit", json=body, headers=headers).json()
    assert replay["already_committed"] is True
    assert all(not row.get("code") for row in replay["created"]), (
        "a replay reads the database, where the code is a hash")


def test_a_packet_prints_a_code_only_when_it_is_handed_one(fx, client):
    """GET prints blocks; POST prints what it is given.

    The blocks are right for a preview and were wrong for everything else: for
    months there was no way to produce a sheet carrying a usable code, while
    the sponsor instructions said to print the packet and hand it out.
    """
    headers = as_(fx, "uni_sponsor")
    preview = client.get(f"/sponsor/packet?person_id={fx.delegate_id}",
                         headers=headers).text
    assert "█" in preview, "a preview must not invent a code it cannot know"

    printed = client.post("/sponsor/packet",
                          json={"codes": [{"person_id": fx.delegate_id,
                                           "code": "DEL-K7M2N-9PQ4T"}]},
                          headers=headers)
    assert printed.status_code == 200, printed.text
    assert "DEL-K7M2N-9PQ4T" in printed.text
    assert "█" not in printed.text, "a real code must replace the blocks"


def test_a_chair_can_reopen_one_persons_form(fx, client):
    """The deadline stops a DELEGATE editing their own answers. It was never
    meant to stop a chair, and until the button existed it did."""
    headers = as_(fx, "chair")
    opened = client.post(f"/admin/people/{fx.other_delegate_id}/unlock-forms",
                         json={"unlocked": True}, headers=headers)
    assert opened.status_code == 200, opened.text

    roster = client.get(f"/sponsor/roster?school_id={fx.other_id}",
                        headers=headers).json()
    row = [p for p in roster["people"] if p["id"] == fx.other_delegate_id][0]
    assert row["forms_unlocked"] == 1, (
        "the roster must show that a form is open, or the button has no visible "
        "effect and gets pressed twice")

    closed = client.post(f"/admin/people/{fx.other_delegate_id}/unlock-forms",
                         json={"unlocked": False}, headers=headers)
    assert closed.status_code == 200


def test_a_chair_can_correct_a_chapter_after_creating_it(fx, client):
    """Chapters are typed in a hurry from the Chapters page, so a typo in a
    name is normal. It used to be permanent."""
    headers = as_(fx, "chair")
    fixed = client.patch(f"/admin/schools/{fx.other_id}",
                         json={"name": "Rival Renamed High School",
                               "city": "Tustin", "level": "MS",
                               "billing_exempt": False,
                               "discount_cents": 5000,
                               "discount_reason": "New chapter"},
                         headers=headers)
    assert fixed.status_code == 200, fixed.text

    rows = client.get("/admin/registration", headers=headers).json()["schools"]
    row = [r for r in rows if r["id"] == fx.other_id][0]
    assert row["name"] == "Rival Renamed High School"
    assert row["city"] == "Tustin"
    assert row["level"] == "MS"
    assert row["discount_cents"] == 5000


def test_a_delegate_added_at_the_desk_is_not_left_permanently_unfinished(fx, client):
    """The Friday desk, and the reason the waiver flag exists.

    Their activity sheet is waived because the tests were printed and the food
    ordered weeks ago. Their WAIVER AND MEDICAL are not waived -- those are
    safety documents and nobody is exempt -- so they are still not complete
    until the paper is in, which is what the desk is checking anyway.
    """
    headers = as_(fx, "chair")
    created = client.post("/sponsor/people",
                          json={"school_id": fx.other_id,
                                "first_name": "Late", "last_name": "Arrival",
                                "person_type": "delegate"},
                          headers=headers)
    assert created.status_code == 200, created.text
    person_id = created.json()["id"]

    waived = client.post(f"/admin/people/{person_id}/waive-activity-sheet",
                         json={"waived": True}, headers=headers)
    assert waived.status_code == 200, waived.text

    roster = client.get(f"/sponsor/roster?school_id={fx.other_id}",
                        headers=headers).json()
    row = [p for p in roster["people"] if p["id"] == person_id][0]
    assert row["activity_sheet_waived"] == 1, (
        "the roster must carry the flag, or the desk cannot see what it did")
    assert row["form_status"] is None, "they never submitted a sheet, and will not"

    stats = fx.stats_for(fx.other_id)
    assert stats["delegates_active"] >= 1
    assert stats["delegates_complete"] == 0, (
        "waiving the sheet must not waive the paper: no waiver, no medical, "
        "not complete")


def test_a_name_can_be_corrected_from_the_roster(fx, client):
    """A pasted roster reads whatever the spreadsheet had.

    The name is printed on their sheet and read out at awards, so it is the
    field most worth being able to fix -- and `PATCH /sponsor/people/{id}` had
    no button anywhere, for a sponsor or a chair, so nothing on the site could
    fix a delegate's name at all.

    Both roles can, because both see the roster it sits on.
    """
    for who in ("chair", "other_sponsor"):
        fixed = client.patch(f"/sponsor/people/{fx.other_delegate_id}",
                             json={"first_name": "Rory", "last_name": f"By{who}"},
                             headers=as_(fx, who))
        assert fixed.status_code == 200, f"{who}: {fixed.text}"

    roster = client.get(f"/sponsor/roster?school_id={fx.other_id}",
                        headers=as_(fx, "chair")).json()
    row = [p for p in roster["people"] if p["id"] == fx.other_delegate_id][0]
    assert row["last_name"] == "Byother_sponsor"

    # Their code is untouched: renaming somebody must not invalidate the sheet
    # in their hand.
    assert client.post("/auth/redeem",
                       json={"code": fx.codes["other_delegate"]}).status_code == 200


def test_a_person_is_told_whether_their_own_registration_is_finished(fx, client):
    """The marker on their own Registration tab.

    Same definition the chapter counters use, so a delegate and their sponsor
    never disagree about whether that person is done: the online form plus,
    for a delegate, both pieces of paper.
    """
    signed_in = client.post("/auth/redeem",
                            json={"code": fx.codes["delegate"]}).json()
    assert signed_in["person"]["registration_complete"] is False, (
        "a delegate who has submitted nothing is not complete")

    me = client.get("/auth/me", headers=as_(fx, "delegate")).json()
    assert me["registration_complete"] is False, (
        "/auth/me and /auth/redeem must agree; the nav is drawn from both")

    # Their sponsor ticks both papers, and they submit the form.
    sponsor = as_(fx, "uni_sponsor")
    for form_type in ("student_waiver", "student_medical"):
        client.post("/sponsor/paper-forms",
                    json={"person_id": fx.delegate_id, "form_type": form_type,
                          "received": True}, headers=sponsor)
    # Academic Testing is a hard minimum, so a sheet with nothing on it is
    # refused. One test is enough to make this one complete.
    sheet = client.get("/me/activity-sheet", headers=as_(fx, "delegate")).json()
    testing = next(category for category in sheet["catalog"]
                   if category["min_selections"])
    saved = client.put("/me/activity-sheet",
                       json={"grade": 10, "latin_level": "HS-2",
                             "meal": "regular",
                             "selected": [testing["items"][0]["id"]]},
                       headers=as_(fx, "delegate"))
    assert saved.status_code == 200, saved.text

    me = client.get("/auth/me", headers=as_(fx, "delegate")).json()
    assert me["registration_complete"] is True


def test_a_sponsor_can_fill_in_a_delegates_form_for_them(fx, client):
    """For the delegate who lost their sheet, or is eleven and has given up.

    Their roster row otherwise reads "Not yet" and nobody can move it, while
    the sponsor is the person their chapter holds responsible for that row.

    The same form and the same rules, not a copy: this goes through
    `save_activity_sheet`, so the test-count minimum and the eligibility gating
    apply exactly as they do on the delegate's own screen.
    """
    headers = as_(fx, "uni_sponsor")
    sheet = client.get(f"/sponsor/people/{fx.delegate_id}/activity-sheet",
                       headers=headers)
    assert sheet.status_code == 200, sheet.text
    body = sheet.json()
    assert body["person"]["first_name"] == "Dana"

    testing = next(c for c in body["catalog"] if c["min_selections"])
    saved = client.put(f"/sponsor/people/{fx.delegate_id}/activity-sheet",
                       json={"grade": 10, "latin_level": "HS-2",
                             "meal": "vegetarian",
                             "selected": [testing["items"][0]["id"]]},
                       headers=headers)
    assert saved.status_code == 200, saved.text

    # The delegate sees what their sponsor saved.
    theirs = client.get("/me/activity-sheet", headers=as_(fx, "delegate")).json()
    assert theirs["person"]["meal"] == "vegetarian"
    assert theirs["status"] == "submitted"

    # And the log credits the SPONSOR, not the delegate. Anything else is a
    # record that says something untrue about who did it.
    entries = client.get("/admin/audit", headers=as_(fx, "admin")).json()["entries"]
    mine = [e for e in entries if e["entity_id"] == fx.delegate_id
            and e["action"].startswith("form.")]
    assert mine, "saving a sheet must be logged"
    assert mine[0]["actor_person_id"] == fx.uni_sponsor_id


def test_a_sponsor_cannot_open_another_chapters_delegate(fx, client):
    """The scope check is the same one the rest of the roster uses."""
    refused = client.get(
        f"/sponsor/people/{fx.other_delegate_id}/activity-sheet",
        headers=as_(fx, "uni_sponsor"))
    assert refused.status_code == 403


def test_an_adult_has_no_activity_sheet_to_open(fx, client):
    """Adults fill in a different form. Asking for this one is a mistake worth
    a clear refusal rather than an empty delegate sheet."""
    refused = client.get(f"/sponsor/people/{fx.chaperone_id}/activity-sheet",
                         headers=as_(fx, "uni_sponsor"))
    assert refused.status_code == 403


def test_guardian_contact_details_can_be_corrected(fx, client):
    """The one contact detail somebody might need at eleven at night.

    The roster paste used to offer a "their phone" column that the parser never
    filled and nobody usefully typed into while checking thirty names. Dropping
    it left `guardian_phone` with no screen at all.
    """
    fixed = client.patch(f"/sponsor/people/{fx.delegate_id}",
                         json={"first_name": "Dana", "last_name": "Delegate",
                               "guardian_name": "Alex Delegate",
                               "guardian_phone": "555-0143"},
                         headers=as_(fx, "uni_sponsor"))
    assert fixed.status_code == 200, fixed.text

    roster = client.get("/sponsor/roster", headers=as_(fx, "uni_sponsor")).json()
    row = [p for p in roster["people"] if p["id"] == fx.delegate_id][0]
    assert row["guardian_name"] == "Alex Delegate"
    assert row["guardian_phone"] == "555-0143"


def test_a_chapter_can_enter_more_than_one_team_in_the_same_event(fx, client):
    """Kickball A and Kickball B are two entries, not one with a count.

    A bracket is built from entries, so a chapter bringing two teams has to
    appear twice with something to tell them apart. All three endpoints existed
    and were tested; until the Teams page there was no caller for any of them,
    so a chapter could not say it was bringing a team at all.
    """
    headers = as_(fx, "uni_sponsor")
    available = client.get("/sponsor/chapter-entries",
                           headers=headers).json()["available"]
    assert available, "the catalog must offer some chapter team events"
    item = available[0]

    for label in ("A", "B"):
        made = client.post("/sponsor/chapter-entries",
                           json={"item_id": item["id"], "team_label": label},
                           headers=headers)
        assert made.status_code == 200, made.text

    entries = client.get("/sponsor/chapter-entries", headers=headers).json()["entries"]
    mine = [e for e in entries if e["item_id"] == item["id"]]
    assert sorted(e["team_label"] for e in mine) == ["A", "B"]

    gone = client.delete(f"/sponsor/chapter-entries/{mine[0]['id']}", headers=headers)
    assert gone.status_code == 200
    left = client.get("/sponsor/chapter-entries", headers=headers).json()["entries"]
    assert len(left) == len(entries) - 1


def test_an_individual_event_cannot_be_entered_as_a_chapter_team(fx, client):
    """Chess and Track are entered by the delegate who is running or playing.

    Entering one as a chapter would tell the Athletics chair that a school is
    bringing "a chess team", which is not a thing that can be scheduled.
    """
    headers = as_(fx, "uni_sponsor")
    catalog = client.get("/me/activity-sheet", headers=as_(fx, "delegate")).json()
    individual = next(item for category in catalog["catalog"]
                      for item in category["items"]
                      if item.get("registration_scope") != "chapter")

    refused = client.post("/sponsor/chapter-entries",
                          json={"item_id": individual["id"], "team_label": "A"},
                          headers=headers)
    assert refused.status_code == 422, refused.text
    assert "chapter team" in refused.json()["error"]


def test_a_chair_can_see_why_a_chapters_balance_moved(fx, client):
    """The payments list says what arrived; this says what changed the amount
    owed.

    When a sponsor disputes a figure in March, the difference between those two
    is the whole argument, and the only record of it used to be the full audit
    log behind scope `*`.
    """
    headers = as_(fx, "chair")
    client.post("/sponsor/people",
                json={"school_id": fx.uni_id, "first_name": "New",
                      "last_name": "Delegate", "person_type": "delegate"},
                headers=headers)
    client.post(f"/sponsor/people/{fx.delegate_id}/cancel", json={},
                headers=headers)
    client.post("/admin/payments",
                json={"school_id": fx.uni_id, "amount_cents": 14000,
                      "method": "check", "reference": "1041"}, headers=headers)

    history = client.get(f"/admin/schools/{fx.uni_id}/history",
                         headers=headers).json()["history"]
    actions = {entry["action"] for entry in history}
    assert {"person.create", "person.cancel", "payment.record"} <= actions

    # NARROWER than /admin/audit, not a widening of it: one school only, and a
    # registration chair still cannot read the whole log.
    assert client.get("/admin/audit", headers=headers).status_code == 403
    other = client.get(f"/admin/schools/{fx.other_id}/history", headers=headers)
    assert other.status_code == 200
    assert all(e["action"] in {"person.create", "person.cancel", "person.restore",
                               "roster.commit", "payment.record", "school.update"}
               for e in other.json()["history"])


def test_a_new_ludus_can_be_added_without_a_migration(fx, client):
    """docs/structure.md, in as many words: "adding a new *ludus* for 2028
    should require no code".

    It used to mean a migration, a deploy, and somebody who knew what a
    migration was -- which, in a system handed to different students every
    year, is the same as not being possible.

    The whole round trip: create it, give it a sub-choice, see it on a
    delegate's form, retire it, see it gone.
    """
    headers = as_(fx, "admin")
    catalog = client.get("/admin/catalog", headers=headers).json()
    ludi = next(c for c in catalog["categories"] if c["key"] == "ludi")

    made = client.post("/admin/catalog/items",
                       json={"name": "Roman Bake Off", "category_id": ludi["id"],
                             "description": "A new ludus for 2028.",
                             "max_sub_selections": 2},
                       headers=headers)
    assert made.status_code == 200, made.text
    item_id = made.json()["id"]

    option = client.post(f"/admin/catalog/items/{item_id}/options",
                         json={"name": "Sweet"}, headers=headers)
    assert option.status_code == 200, option.text

    def on_the_form():
        sheet = client.get("/me/activity-sheet", headers=as_(fx, "delegate")).json()
        return [item["name"] for category in sheet["catalog"]
                for item in category["items"]]

    assert "Roman Bake Off" in on_the_form()

    # NOT OFFERED, never deleted: anybody who already chose it keeps their
    # entry, and the chairs still see them in the counts.
    client.put(f"/admin/catalog/items/{item_id}", json={"active": False},
               headers=headers)
    assert "Roman Bake Off" not in on_the_form()


def test_a_sub_choice_cannot_be_added_where_none_may_be_picked(fx, client):
    """An item whose `max_sub_selections` is unset would show a list nobody may
    choose from -- the sort of thing a delegate finds at midnight."""
    headers = as_(fx, "admin")
    catalog = client.get("/admin/catalog", headers=headers).json()
    plain = next(item for category in catalog["categories"]
                 for item in category["items"]
                 if not item.get("max_sub_selections"))

    refused = client.post(f"/admin/catalog/items/{plain['id']}/options",
                          json={"name": "Nope"}, headers=headers)
    assert refused.status_code == 422
    assert "does not take sub-choices" in refused.json()["error"]
