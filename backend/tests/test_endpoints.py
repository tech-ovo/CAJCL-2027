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

import pytest

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
        "/me/adult-sheet", "/me/catalog",
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
