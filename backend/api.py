"""The FastAPI application. All business logic; the only thing that talks to
the database.

This module is deliberately free of Modal imports so the whole API can be
exercised by the test suite with `TestClient` and run locally with
`uvicorn backend.api:app`. `backend/app.py` is the thin Modal wrapper.

EVERY ENDPOINT DECLARES ITS SCOPE AND ITS SCHOOL RULE
    Not in a comment -- in `Guard`, which is a real object the test suite walks.
    `test_endpoints.py` enumerates every route and asserts that each one rejects
    a wrong-scope credential and a wrong-school credential. A route added
    without a Guard fails that test, which is the point.

    The repository is public, so every endpoint here is documented to anyone
    curious. The realistic threat is not a database dump; it is a sponsor at one
    school reading another school's roster because an endpoint checked identity
    but not scope.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from .lib import auth, catalog, clock, codes, forms, printing, roster, settings, stats
from .lib.db import connect

# GitHub Pages plus the custom domain, and nothing else. The frontend never
# holds a database credential and never talks to Turso.
ALLOWED_ORIGINS = [
    "https://state.uhsjcl.org",
    "https://tech-ovo.github.io",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# No /docs, /redoc, or /openapi.json. The repository is public so the endpoints
# are already documented to anyone curious -- but an auto-generated schema is a
# route with no declared scope, and this app allows none of those.
app = FastAPI(title="CAJCL 2027 Convention",
              docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,   # the token travels in a header, never a cookie
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
)

_db = None


def database():
    """One Database per container. It is a connection factory, not a connection."""
    global _db
    if _db is None:
        _db = connect()
    return _db


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Guard:
    """What an endpoint requires. Enumerated by the authorization tests."""

    scopes: tuple[str, ...]
    # 'own'    -- identity scopes are limited to the caller's own school
    # 'any'    -- administrative scope required; school comes from the request
    # 'self'   -- acts only on the caller's own person row
    # 'public' -- no credential at all
    school_rule: str = "own"
    writes: bool = False


GUARDS: dict[str, Guard] = {}


def guard(name: str, *scopes: str, school_rule: str = "own", writes: bool = False):
    """Register an endpoint's requirements and return its dependency."""
    GUARDS[name] = Guard(scopes, school_rule, writes)

    def dependency(request: Request,
                   authorization: str | None = Header(default=None)) -> auth.Principal:
        principal = _authenticate(request, authorization)
        if scopes:
            auth.require_scope(principal, *scopes)
        if writes:
            auth.require_writable(principal)
        return principal

    return Depends(dependency)


def _authenticate(request: Request, authorization: str | None) -> auth.Principal:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    with database().tx() as tx:
        principal = auth.authenticate(tx, token)
    request.state.principal = principal
    return principal


def any_session(request: Request,
                authorization: str | None = Header(default=None)) -> auth.Principal:
    return _authenticate(request, authorization)


# ---------------------------------------------------------------------------
# Errors -- one shape, always, so the frontend never guesses
# ---------------------------------------------------------------------------

@app.exception_handler(auth.AuthError)
async def _auth_error(request: Request, exc: auth.AuthError):
    return JSONResponse({"error": str(exc), "kind": "auth"}, status_code=401)


@app.exception_handler(auth.ForbiddenError)
async def _forbidden(request: Request, exc: auth.ForbiddenError):
    return JSONResponse({"error": str(exc), "kind": "forbidden"}, status_code=403)


@app.exception_handler(auth.RateLimited)
async def _rate_limited(request: Request, exc: auth.RateLimited):
    return JSONResponse({"error": str(exc), "kind": "rate_limited"}, status_code=429)


@app.exception_handler(catalog.ValidationError)
async def _validation(request: Request, exc: catalog.ValidationError):
    return JSONResponse({"error": exc.errors[0], "errors": exc.errors,
                         "kind": "validation"}, status_code=422)


@app.exception_handler(roster.RosterError)
async def _roster_error(request: Request, exc: roster.RosterError):
    return JSONResponse({"error": str(exc), "kind": "roster"}, status_code=409)


def request_id(request: Request) -> str:
    return request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


# ===========================================================================
# Public -- no credential, cached, cheap
# ===========================================================================

@app.get("/public/stats")
def public_stats():
    """Served from public_stats_cache. ONE row read per request.

    COUNT(*) over `people` here would be 1,150 reads per hit on an endpoint
    crawlers can reach. See docs/stack.md.
    """
    with database().read() as tx:
        row = tx.one("stats.public")
    body = dict(row) if row else {
        "schools_ms": 0, "schools_hs": 0, "delegates": 0, "adults": 0,
        "updated_at": None,
    }
    return JSONResponse(body, headers={"Cache-Control": "public, max-age=60"})


@app.get("/public/convention")
def public_convention():
    with database().read() as tx:
        body = settings.public_convention(tx)
        body["demo_mode"] = settings.get_bool(tx, "ops.demo_mode")
    return JSONResponse(body, headers={"Cache-Control": "public, max-age=300"})


@app.get("/public/announcements")
def public_announcements():
    now = clock.now_iso()
    with database().read() as tx:
        rows = [dict(r) for r in tx.all("announcements.active", (now, now))]
    return JSONResponse({"announcements": rows},
                        headers={"Cache-Control": "public, max-age=30"})


# ===========================================================================
# Auth
# ===========================================================================

@app.post("/auth/redeem")
def redeem(request: Request, payload: dict = Body(...)):
    """Exchange a code for a session token.

    `via_magic_link` only affects the audit entry. The code itself travels in
    the POST body either way -- the QR puts it in the URL FRAGMENT, which the
    browser never sends to a server, and the frontend reads `location.hash` and
    posts it here before calling history.replaceState() to strip it.
    """
    token, principal = auth.redeem(
        database(),
        (payload.get("code") or "").strip(),
        ip=client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        via_magic_link=bool(payload.get("via_magic_link")),
    )
    return {"token": token, "person": principal.to_public_dict()}


@app.get("/auth/me")
def me(principal: auth.Principal = Depends(any_session)):
    with database().read() as tx:
        sessions = [dict(r) for r in tx.all("auth.sessions_for_person",
                                            (principal.person_id,))]
        demo = settings.get_bool(tx, "ops.demo_mode")
    body = principal.to_public_dict()
    body["sessions"] = sessions
    body["demo_mode"] = demo
    return body


@app.post("/auth/logout")
def logout(principal: auth.Principal = Depends(any_session)):
    with database().tx() as tx:
        auth.logout(tx, principal)
    return {"ok": True}


@app.post("/auth/sessions/{session_id}/revoke")
def revoke_session(session_id: int, principal: auth.Principal = Depends(any_session)):
    with database().tx() as tx:
        auth.revoke_session(tx, principal, session_id)
    return {"ok": True}


@app.post("/auth/impersonate")
def impersonate(request: Request, payload: dict = Body(...),
                principal: auth.Principal = guard("auth.impersonate", "*",
                                                  school_rule="any")):
    """Open a read-only view of exactly what another person sees.

    Requires a STEP-UP re-entry of the admin's own code, expires in 30 minutes,
    is read-only unless explicitly toggled, and never reveals the target's code.
    The frontend shows a permanent banner naming both identities.
    """
    with database().tx(request_id=request_id(request)) as tx:
        token, target = auth.start_impersonation(
            tx, principal,
            int(payload.get("target_person_id") or 0),
            (payload.get("admin_code") or "").strip(),
            ip=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )
    return {"token": token, "person": target.to_public_dict()}


@app.post("/auth/impersonate/end")
def impersonate_end(principal: auth.Principal = Depends(any_session)):
    with database().tx() as tx:
        auth.end_impersonation(tx, principal)
    return {"ok": True}


# ===========================================================================
# Sponsor
# ===========================================================================

def _school_of(tx, principal: auth.Principal, school_id: int | None) -> dict:
    """Resolve which school this request acts on, and check the caller may.

    An administrative scope may name any school. An identity scope means the
    caller's own school and nothing else.

    A named school that is not the caller's is REFUSED, not quietly replaced
    with their own. Silently serving a sponsor their own roster when they asked
    for someone else's would hide the bug -- or the probe -- behind a page that
    looks entirely correct, and it would make the wrong-school tests pass
    without proving anything.
    """
    if school_id and not (principal.scopes & auth.ADMIN_SCOPES):
        if int(school_id) != principal.school_id:
            raise auth.ForbiddenError("that belongs to a different school")

    target = int(school_id) if school_id else principal.school_id
    auth.require_school(principal, target)
    school = tx.one("schools.get", (target,))
    if school is None:
        raise auth.ForbiddenError("no such school")
    return dict(school)


@app.get("/sponsor/roster")
def get_roster(school_id: int | None = Query(default=None),
               principal: auth.Principal = guard("sponsor.roster", "sponsor",
                                                 "registration")):
    """ONE query with four indexed LEFT JOINs. Never a query per delegate."""
    with database().read() as tx:
        school = _school_of(tx, principal, school_id)
        people = [dict(r) for r in tx.all("roster.list", (school["id"],))]
        counters = tx.one("stats.for_school", (school["id"],))
        entries = [dict(r) for r in tx.all("forms.chapter_entries_for_school",
                                           (school["id"],))]
    return {
        "school": _school_public(school, principal),
        "people": people,
        "stats": dict(counters) if counters else {},
        "chapter_entries": entries,
    }


def _school_public(school: dict, principal: auth.Principal) -> dict:
    """The Drive folder link is visible to scope '*' and nobody else.

    Registration chairs never see it. It points at scanned waivers and medical
    forms for minors, uploaded by the sponsor with their own Google account to a
    folder no code in this repository reads.
    """
    body = {k: v for k, v in school.items() if k != "drive_folder_id"}
    if principal.is_admin and "drive_folder_id" in school:
        body["drive_folder_id"] = school["drive_folder_id"]
    return body


@app.post("/sponsor/roster/parse")
def parse_roster(payload: dict = Body(...),
                 principal: auth.Principal = guard("sponsor.roster.parse",
                                                   "sponsor", "registration")):
    """Preview a paste. WRITES NOTHING -- not a row, not an audit entry.

    Returns a signed idempotency key. An abandoned preview leaves nothing
    behind and stores no copy of the pasted text.
    """
    with database().read() as tx:
        school = _school_of(tx, principal, payload.get("school_id"))
        return roster.preview(
            tx, school, payload.get("text") or "",
            default_person_type=payload.get("person_type") or "delegate")


@app.post("/sponsor/roster/commit")
def commit_roster(request: Request, payload: dict = Body(...),
                  principal: auth.Principal = guard("sponsor.roster.commit",
                                                    "sponsor", "registration",
                                                    writes=True)):
    """Create the roster. IDEMPOTENT on the key issued with the preview.

    A double-click, a flaky connection, and an impatient refresh all land here
    and all produce exactly one roster.
    """
    with database().tx(request_id=request_id(request)) as tx:
        school = _school_of(tx, principal, payload.get("school_id"))
        return roster.commit(
            tx, school, principal,
            payload.get("text") or "",
            payload.get("idempotency_key") or "",
            payload.get("rows") or [],
        )


@app.post("/sponsor/people")
def add_person(request: Request, payload: dict = Body(...),
               principal: auth.Principal = guard("sponsor.people.add", "sponsor",
                                                 "registration", writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        school = _school_of(tx, principal, payload.get("school_id"))
        created = roster._insert_person(tx, school, payload, clock.now_iso())
        name = f"{created['first_name']} {created['last_name']}".strip()
        tx.audit("person.create",
                 f"{principal.display_name} added {name} to {school['name']}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 school_id=school["id"], entity_type="person",
                 entity_id=created["id"])
        stats.recompute(tx, school["id"], settings=settings.fee_settings(tx))
        return created


@app.patch("/sponsor/people/{person_id}")
def edit_person(person_id: int, request: Request, payload: dict = Body(...),
                principal: auth.Principal = guard("sponsor.people.edit", "sponsor",
                                                  "registration", writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        auth.require_person_in_scope(tx, principal, person_id)
        person = dict(tx.one("people.get", (person_id,)))
        now = clock.now_iso()

        if person["person_type"] == "delegate":
            tx.run("people.update_details", (
                payload.get("first_name", person["first_name"]),
                payload.get("middle_name", person["middle_name"]),
                payload.get("last_name", person["last_name"]),
                payload.get("suffix", person["suffix"]),
                payload.get("grade", person["grade"]),
                payload.get("latin_level", person["latin_level"]),
                payload.get("meal", person["meal"]),
                payload.get("cell_phone", person["cell_phone"]),
                payload.get("guardian_name", person["guardian_name"]),
                payload.get("guardian_phone", person["guardian_phone"]),
                now, person_id))
        else:
            tx.run("people.update_adult_details", (
                payload.get("first_name", person["first_name"]),
                payload.get("middle_name", person["middle_name"]),
                payload.get("last_name", person["last_name"]),
                payload.get("suffix", person["suffix"]),
                payload.get("adult_type", person["adult_type"]),
                payload.get("adult_type_other", person["adult_type_other"]),
                payload.get("meal", person["meal"]),
                payload.get("cell_phone", person["cell_phone"]),
                payload.get("email", person["email"]),
                payload.get("latin_knowledge", person["latin_knowledge"]),
                payload.get("availability_note", person["availability_note"]),
                now, person_id))

        name = f"{payload.get('first_name', person['first_name'])} " \
               f"{payload.get('last_name', person['last_name'])}".strip()
        tx.audit("person.update",
                 f"{principal.display_name} updated {name}'s details.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 school_id=person["school_id"], entity_type="person",
                 entity_id=person_id,
                 changed_fields=sorted(payload.keys()))
        stats.recompute(tx, person["school_id"], settings=settings.fee_settings(tx))
    return {"ok": True}


@app.post("/sponsor/people/{person_id}/cancel")
def cancel_person(person_id: int, request: Request,
                  principal: auth.Principal = guard("sponsor.people.cancel",
                                                    "sponsor", "registration",
                                                    writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        auth.require_person_in_scope(tx, principal, person_id)
        person = dict(tx.one("people.get", (person_id,)))
        school = dict(tx.one("schools.get", (person["school_id"],)))
        status = roster.cancel(tx, school, principal, person)
    return {"ok": True, "status": status}


@app.post("/sponsor/people/{person_id}/restore")
def restore_person(person_id: int, request: Request,
                   principal: auth.Principal = guard("sponsor.people.restore",
                                                     "sponsor", "registration",
                                                     writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        auth.require_person_in_scope(tx, principal, person_id)
        person = dict(tx.one("people.get", (person_id,)))
        school = dict(tx.one("schools.get", (person["school_id"],)))
        roster.restore(tx, school, principal, person)
    return {"ok": True}


@app.post("/sponsor/people/{person_id}/regenerate-code")
def regenerate(person_id: int, request: Request,
               principal: auth.Principal = guard("sponsor.people.regenerate",
                                                 "sponsor", "registration",
                                                 writes=True)):
    """Returns the new code ONCE, with a reprint link.

    The reprint is not a nicety: without it the sponsor is holding a packet page
    whose QR no longer works and no obvious way to produce a new one.
    """
    with database().tx(request_id=request_id(request)) as tx:
        auth.require_person_in_scope(tx, principal, person_id)
        person = dict(tx.one("people.get", (person_id,)))
        school = dict(tx.one("schools.get", (person["school_id"],)))
        code = roster.regenerate_code(tx, school, principal, person)
    return {
        "code": code,
        "person_id": person_id,
        "reprint_url": f"/sponsor/packet?person_id={person_id}",
        "note": "This is the only time this code is shown. Reprint the sheet now.",
    }


@app.post("/sponsor/people/{person_id}/chapter-leader")
def set_chapter_leader(person_id: int, request: Request, payload: dict = Body(...),
                       principal: auth.Principal = guard("sponsor.chapter_leader",
                                                         "sponsor", writes=True)):
    """Grant or revoke the chapter_leader ROLE on an existing account.

    A scope is never attached to a person directly. The only path is
    person_roles -> roles -> role_scopes, and this endpoint inserts or deletes
    exactly one person_roles row. There is never a second code.
    """
    grant = bool(payload.get("granted", True))
    with database().tx(request_id=request_id(request)) as tx:
        auth.require_person_in_scope(tx, principal, person_id)
        person = dict(tx.one("people.get", (person_id,)))
        if person["person_type"] != "delegate":
            raise catalog.ValidationError(["Only a delegate can be a chapter leader."])
        role = tx.one("roles.by_key", ("chapter_leader",))
        name = f"{person['first_name']} {person['last_name']}".strip()
        if grant:
            tx.run("people.grant_role",
                   (person_id, role["id"], principal.person_id, clock.now_iso()))
            tx.audit("role.grant",
                     f"{principal.display_name} made {name} a chapter leader.",
                     actor_person_id=principal.person_id,
                     impersonator_person_id=principal.impersonator_person_id,
                     school_id=person["school_id"], entity_type="person",
                     entity_id=person_id)
        else:
            tx.run("people.revoke_role", (person_id, role["id"]))
            tx.audit("role.revoke",
                     f"{principal.display_name} removed chapter leader from {name}.",
                     actor_person_id=principal.person_id,
                     impersonator_person_id=principal.impersonator_person_id,
                     school_id=person["school_id"], entity_type="person",
                     entity_id=person_id)
        # Their existing sessions carry the old scope set, so a promotion would
        # not take effect until they signed in again. Revoking is blunt but
        # honest, and a chapter leader is promoted once.
        tx.run("auth.session_revoke_all_for_person", (clock.now_iso(), person_id))
    return {"ok": True, "granted": grant}


@app.post("/sponsor/paper-forms")
def mark_paper(request: Request, payload: dict = Body(...),
               principal: auth.Principal = guard("sponsor.paper_forms", "sponsor",
                                                 "registration", writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        person_id = int(payload.get("person_id") or 0)
        auth.require_person_in_scope(tx, principal, person_id)
        person = dict(tx.one("people.get", (person_id,)))
        school = dict(tx.one("schools.get", (person["school_id"],)))
        roster.mark_paper_form(tx, school, principal, person,
                               payload.get("form_type") or "",
                               bool(payload.get("received")))
    return {"ok": True}


@app.get("/sponsor/chapter-entries")
def list_chapter_entries(school_id: int | None = Query(default=None),
                         principal: auth.Principal = guard("sponsor.chapter_entries.list",
                                                           "chapter", "registration")):
    with database().read() as tx:
        school = _school_of(tx, principal, school_id)
        return {
            "entries": [dict(r) for r in tx.all("forms.chapter_entries_for_school",
                                                (school["id"],))],
            "available": catalog.chapter_items(tx, school_level=school["level"]),
        }


@app.post("/sponsor/chapter-entries")
def create_chapter_entry(request: Request, payload: dict = Body(...),
                         principal: auth.Principal = guard("sponsor.chapter_entries.create",
                                                           "chapter", "registration",
                                                           writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        school = _school_of(tx, principal, payload.get("school_id"))
        item_id = int(payload.get("item_id") or 0)
        item = catalog.load(tx)["items_by_id"].get(item_id)
        if item is None or item["registration_scope"] != "chapter":
            raise catalog.ValidationError(["That is not a chapter team entry."])
        entry_id = tx.insert("forms.chapter_entry_create", (
            school["id"], item_id, (payload.get("team_label") or "A").strip()[:8],
            payload.get("notes"), principal.person_id, clock.now_iso()))
        tx.audit("chapter_entry.create",
                 f"{principal.display_name} entered a {item['name']} team for "
                 f"{school['name']}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 school_id=school["id"], entity_type="chapter_entry",
                 entity_id=entry_id)
    return {"ok": True, "id": entry_id}


@app.delete("/sponsor/chapter-entries/{entry_id}")
def delete_chapter_entry(entry_id: int, request: Request,
                         principal: auth.Principal = guard("sponsor.chapter_entries.delete",
                                                           "chapter", "registration",
                                                           writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        entry = tx.one("forms.chapter_entry_get", (entry_id,))
        if entry is None:
            raise auth.ForbiddenError("no such entry")
        auth.require_school(principal, entry["school_id"])
        tx.run("forms.chapter_entry_delete", (entry_id, entry["school_id"]))
        tx.audit("chapter_entry.delete",
                 f"{principal.display_name} withdrew a chapter team entry.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 school_id=entry["school_id"], entity_type="chapter_entry",
                 entity_id=entry_id)
    return {"ok": True}


@app.get("/sponsor/invoice")
def invoice(school_id: int | None = Query(default=None),
            principal: auth.Principal = guard("sponsor.invoice", "sponsor",
                                              "registration")):
    with database().read() as tx:
        school = _school_of(tx, principal, school_id)
        return printing.invoice_context(tx, school)


# ===========================================================================
# Attendee
# ===========================================================================

@app.get("/me/activity-sheet")
def get_activity_sheet(principal: auth.Principal = guard("me.activity_sheet",
                                                         "delegate",
                                                         school_rule="self")):
    with database().read() as tx:
        person = _self(tx, principal)
        return forms.activity_sheet(tx, person)


@app.put("/me/activity-sheet")
def put_activity_sheet(request: Request, payload: dict = Body(...),
                       principal: auth.Principal = guard("me.activity_sheet.save",
                                                         "delegate",
                                                         school_rule="self",
                                                         writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        person = _self(tx, principal)
        return forms.save_activity_sheet(tx, principal, person, payload)


@app.get("/me/adult-sheet")
def get_adult_sheet(principal: auth.Principal = Depends(any_session)):
    with database().read() as tx:
        person = _self(tx, principal)
        if person["person_type"] != "adult":
            raise auth.ForbiddenError("that form is for adults")
        return forms.adult_sheet(tx, person)


@app.put("/me/adult-sheet")
def put_adult_sheet(request: Request, payload: dict = Body(...),
                    principal: auth.Principal = Depends(any_session)):
    auth.require_writable(principal)
    with database().tx(request_id=request_id(request)) as tx:
        person = _self(tx, principal)
        if person["person_type"] != "adult":
            raise auth.ForbiddenError("that form is for adults")
        return forms.save_adult_sheet(tx, principal, person, payload)


@app.get("/me/catalog")
def my_catalog(principal: auth.Principal = Depends(any_session)):
    with database().read() as tx:
        person = _self(tx, principal)
        return {"catalog": catalog.for_person(
            tx, person_type=person["person_type"],
            school_level=person["school_level"],
            latin_level=person["latin_level"],
            latin_knowledge=person["latin_knowledge"])}


def _self(tx, principal: auth.Principal) -> dict:
    """The caller's own person row, joined to their school.

    Under impersonation this is the TARGET's row, which is the whole point: an
    admin debugging a confused sponsor sees exactly what that sponsor sees.
    """
    person = dict(tx.one("people.get", (principal.person_id,)))
    school = tx.one("schools.get", (person["school_id"],))
    person["school_level"] = school["level"]
    person["school_name"] = school["name"]
    return person


# ===========================================================================
# Admin
# ===========================================================================

@app.get("/admin/schools")
def list_schools(principal: auth.Principal = guard("admin.schools.list",
                                                   "registration",
                                                   school_rule="any")):
    with database().read() as tx:
        rows = [_school_public(dict(r), principal) for r in tx.all("schools.list")]
    return {"schools": rows}


@app.post("/admin/schools")
def create_school(request: Request, payload: dict = Body(...),
                  principal: auth.Principal = guard("admin.schools.create",
                                                    "registration",
                                                    school_rule="any", writes=True)):
    name = (payload.get("name") or "").strip()
    level = payload.get("level")
    if not name or level not in ("MS", "HS"):
        raise catalog.ValidationError(
            ["Give the chapter a name and say whether it is middle or high school."])

    now = clock.now_iso()
    with database().tx(request_id=request_id(request)) as tx:
        school_id = tx.insert("schools.create", (
            name, level, "chapter", payload.get("city"),
            1 if payload.get("billing_exempt") else 0,
            int(payload.get("discount_cents") or 0),
            payload.get("discount_reason"),
            payload.get("notes"), now, now))
        tx.run("schools.stats_init", (school_id, now))
        tx.audit("school.create",
                 f"{principal.display_name} added {name} to the convention.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 school_id=school_id, entity_type="school", entity_id=school_id)
        stats.recompute(tx, school_id, settings=settings.fee_settings(tx))
    return {"id": school_id, "name": name, "level": level}


@app.patch("/admin/schools/{school_id}")
def update_school(school_id: int, request: Request, payload: dict = Body(...),
                  principal: auth.Principal = guard("admin.schools.update",
                                                    "registration",
                                                    school_rule="any", writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        school = dict(tx.one("schools.get", (school_id,)) or {})
        if not school:
            raise auth.ForbiddenError("no such school")

        # The Drive folder points at minors' medical scans. Only '*' may set it,
        # and a registration chair silently keeps whatever is already there.
        drive = school["drive_folder_id"]
        if "drive_folder_id" in payload:
            if not principal.is_admin:
                raise auth.ForbiddenError(
                    "only a Convention President can set the Drive folder")
            drive = payload["drive_folder_id"]

        tx.run("schools.update", (
            payload.get("name", school["name"]),
            payload.get("level", school["level"]),
            payload.get("city", school["city"]),
            1 if payload.get("billing_exempt", school["billing_exempt"]) else 0,
            int(payload.get("discount_cents", school["discount_cents"]) or 0),
            payload.get("discount_reason", school["discount_reason"]),
            payload.get("status", school["status"]),
            payload.get("notes", school["notes"]),
            drive, clock.now_iso(), school_id))
        tx.audit("school.update",
                 f"{principal.display_name} updated "
                 f"{payload.get('name', school['name'])}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 school_id=school_id, entity_type="school", entity_id=school_id,
                 changed_fields=sorted(payload.keys()))
        stats.recompute(tx, school_id, settings=settings.fee_settings(tx))
    return {"ok": True}


@app.post("/admin/schools/{school_id}/people")
def create_sponsor(school_id: int, request: Request, payload: dict = Body(...),
                   principal: auth.Principal = guard("admin.schools.people",
                                                     "registration",
                                                     school_rule="any", writes=True)):
    """Create a sponsor account. Returns the code ONCE.

    An admin then sends it by hand from the official CAJCL account. Nothing
    about that is automated; there is no bulk mailing anywhere in this system.
    """
    with database().tx(request_id=request_id(request)) as tx:
        school = dict(tx.one("schools.get", (school_id,)) or {})
        if not school:
            raise auth.ForbiddenError("no such school")
        payload = {**payload, "person_type": "adult",
                   "adult_type": payload.get("adult_type") or "sponsor"}
        created = roster._insert_person(tx, school, payload, clock.now_iso())
        person = tx.one("people.get", (created["id"],))
        code = auth.issue_code(tx, created["id"],
                               auth.code_prefix_for("adult", payload["adult_type"]))
        name = f"{created['first_name']} {created['last_name']}".strip()
        tx.audit("person.create",
                 f"{principal.display_name} created a sponsor account for {name} "
                 f"at {school['name']}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 school_id=school_id, entity_type="person", entity_id=created["id"])
        stats.recompute(tx, school_id, settings=settings.fee_settings(tx))
    return {**created, "code": code,
            "note": "This is the only time this code is shown. Send it to the "
                    "sponsor from the official CAJCL account."}


@app.get("/admin/registration")
def chair_dashboard(principal: auth.Principal = guard("admin.registration",
                                                      "registration",
                                                      school_rule="any")):
    """Fifty schools, ONE query, served from school_stats. No loop, no COUNT."""
    with database().read() as tx:
        rows = [dict(r) for r in tx.all("stats.dashboard")]
        fees = settings.fee_settings(tx)

    # Exempt chapters are excluded from the outstanding total so the number
    # stays meaningful -- a chair looking at "still owed" wants the figure they
    # can actually chase.
    outstanding = sum(
        max(0, (r["amount_owed_cents"] or 0) - (r["amount_paid_cents"] or 0))
        for r in rows if not r["billing_exempt"] and r["status"] == "active"
    )
    return {
        "schools": rows,
        "fees": fees,
        "totals": {
            "chapters": len(rows),
            "delegates": sum(r["delegates_active"] or 0 for r in rows),
            "adults": sum(r["adults_active"] or 0 for r in rows),
            "delegates_complete": sum(r["delegates_complete"] or 0 for r in rows),
            "outstanding_cents": outstanding,
            "collected_cents": sum(r["amount_paid_cents"] or 0 for r in rows),
        },
    }


@app.get("/admin/payments")
def list_payments(school_id: int = Query(...),
                  principal: auth.Principal = guard("admin.payments.list",
                                                    "registration",
                                                    school_rule="any")):
    with database().read() as tx:
        return {"payments": [dict(r) for r in tx.all("payments.for_school", (school_id,))]}


@app.post("/admin/payments")
def record_payment(request: Request, payload: dict = Body(...),
                   principal: auth.Principal = guard("admin.payments.record",
                                                     "registration",
                                                     school_rule="any", writes=True)):
    """Append-only. A correction is a NEW row, possibly negative, never an edit."""
    school_id = int(payload.get("school_id") or 0)
    amount = payload.get("amount_cents")
    if amount is None or not isinstance(amount, int):
        raise catalog.ValidationError(
            ["Enter the exact amount received, in cents, as a whole number."])

    with database().tx(request_id=request_id(request)) as tx:
        school = dict(tx.one("schools.get", (school_id,)) or {})
        if not school:
            raise auth.ForbiddenError("no such school")
        previous = tx.value("stats.paid_for_school", (school_id,), default=0) or 0
        payment_id = tx.insert("payments.create", (
            school_id, amount, payload.get("method") or "check",
            payload.get("reference"), payload.get("received_on"),
            payload.get("note"), principal.person_id, clock.now_iso()))
        tx.audit(
            "payment.record",
            f"{principal.display_name} recorded {_money(amount)} from "
            f"{school['name']}.",
            actor_person_id=principal.person_id,
            impersonator_person_id=principal.impersonator_person_id,
            school_id=school_id, entity_type="payment", entity_id=payment_id,
            # The ONE action that records values, not just field names. Money
            # disputes are exactly when you need them.
            value_detail={"amount_cents": amount,
                          "previous_total_cents": previous,
                          "new_total_cents": previous + amount,
                          "reference": payload.get("reference")},
        )
        stats.recompute(tx, school_id, settings=settings.fee_settings(tx))
    return {"ok": True, "id": payment_id}


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}" if cents >= 0 else f"-${abs(cents) / 100:,.2f}"


@app.post("/admin/people/{person_id}/unlock-forms")
def unlock_forms(person_id: int, request: Request, payload: dict = Body(default={}),
                 principal: auth.Principal = guard("admin.people.unlock",
                                                   "registration",
                                                   school_rule="any", writes=True)):
    unlocked = bool(payload.get("unlocked", True))
    with database().tx(request_id=request_id(request)) as tx:
        person = dict(tx.one("people.get", (person_id,)) or {})
        if not person:
            raise auth.ForbiddenError("no such person")
        tx.run("people.set_forms_unlocked",
               (1 if unlocked else 0, clock.now_iso(), person_id))
        name = f"{person['first_name']} {person['last_name']}".strip()
        tx.audit("form.unlock",
                 f"{principal.display_name} "
                 f"{'reopened' if unlocked else 'closed'} forms for {name}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 school_id=person["school_id"], entity_type="person",
                 entity_id=person_id, changed_fields=["forms_unlocked"])
    return {"ok": True, "unlocked": unlocked}


@app.get("/admin/audit")
def audit_log(cursor: int | None = Query(default=None),
              school_id: int | None = Query(default=None),
              limit: int = Query(default=50, le=200),
              principal: auth.Principal = guard("admin.audit", "*",
                                                school_rule="any")):
    """Keyset pagination, not OFFSET.

    OFFSET makes page 50 scan every row before it, which is how a log viewer
    quietly becomes the most expensive page on the site.
    """
    with database().read() as tx:
        start = cursor or (tx.value("audit.max_id", (), default=1) or 1)
        if school_id:
            rows = tx.all("audit.recent_by_school", (school_id, start, limit))
        else:
            rows = tx.all("audit.recent", (start, limit))
        rows = [dict(r) for r in rows]
    return {"entries": rows,
            "next_cursor": rows[-1]["id"] if len(rows) == limit else None}


@app.get("/admin/settings")
def get_settings(principal: auth.Principal = guard("admin.settings.get", "*",
                                                   school_rule="any")):
    with database().read() as tx:
        return {"settings": [dict(r) for r in settings.rows(tx)],
                "documents": [dict(r) for r in tx.all("documents.all")]}


@app.put("/admin/settings")
def put_settings(request: Request, payload: dict = Body(...),
                 principal: auth.Principal = guard("admin.settings.put", "*",
                                                   school_rule="any", writes=True)):
    """Update settings by key.

    A deadline is given as a California DATE and converted here. Nobody
    hand-types a UTC string -- see backend/lib/clock.py for why.
    """
    updates = payload.get("settings") or {}
    now = clock.now_iso()
    with database().tx(request_id=request_id(request)) as tx:
        for key, value in updates.items():
            row = tx.one("settings.get", (key,))
            if row is None:
                raise catalog.ValidationError([f"There is no setting called {key}."])
            if row["value_type"] == "datetime" and value and "T" not in str(value):
                value = clock.end_of_day_utc(str(value))
            tx.run("settings.update", (str(value), now, principal.person_id, key))
        tx.audit("settings.update",
                 f"{principal.display_name} changed "
                 f"{len(updates)} setting{'' if len(updates) == 1 else 's'}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 changed_fields=sorted(updates.keys()))
        settings.invalidate()
        # A fee or discount change re-prices every chapter, so the counters have
        # to move with it rather than waiting for the next roster edit.
        if any(k.startswith("fee.") for k in updates):
            settings.load(tx, force=True)
            stats.recompute_all(tx, settings=settings.fee_settings(tx))
    return {"ok": True}


@app.put("/admin/documents/{key}")
def put_document(key: str, request: Request, payload: dict = Body(...),
                 principal: auth.Principal = guard("admin.documents.put", "*",
                                                   school_rule="any", writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        existing = tx.one("documents.get", (key,))
        if existing is None:
            raise catalog.ValidationError([f"There is no document called {key}."])
        tx.run("documents.update", (
            payload.get("title", existing["title"]),
            payload.get("body_md", existing["body_md"]),
            clock.now_iso(), principal.person_id, key))
        tx.audit("settings.update",
                 f"{principal.display_name} reworded the "
                 f"{existing['title'].lower()}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 entity_type="document", changed_fields=["body_md"])
    return {"ok": True}


@app.get("/admin/catalog")
def get_catalog(principal: auth.Principal = guard("admin.catalog.get", "*",
                                                  school_rule="any")):
    with database().read() as tx:
        data = catalog.load(tx)
        return {"categories": data["categories"]}


@app.put("/admin/catalog/items/{item_id}")
def put_catalog_item(item_id: int, request: Request, payload: dict = Body(...),
                     principal: auth.Principal = guard("admin.catalog.put", "*",
                                                       school_rule="any",
                                                       writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        item = catalog.load(tx)["items_by_id"].get(item_id)
        if item is None:
            raise catalog.ValidationError(["There is no such catalog entry."])
        tx.run("catalog.item_update", (
            payload.get("name", item["name"]),
            payload.get("description", item["description"]),
            _csv(payload.get("eligible_latin_levels", item["eligible_latin_levels"])),
            _csv(payload.get("eligible_school_levels", item["eligible_school_levels"])),
            payload.get("registration_scope", item["registration_scope"]),
            payload.get("max_sub_selections", item["max_sub_selections"]),
            payload.get("min_latin_knowledge", item.get("min_latin_knowledge")),
            payload.get("sort_order", item["sort_order"]),
            1 if payload.get("active", item["active"]) else 0,
            item_id))
        tx.audit("catalog.update",
                 f"{principal.display_name} updated the catalog entry "
                 f"{payload.get('name', item['name'])}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 entity_type="catalog_item", entity_id=item_id,
                 changed_fields=sorted(payload.keys()))
        catalog.invalidate()
    return {"ok": True}


def _csv(value) -> str | None:
    if value in (None, "", []):
        return None
    if isinstance(value, str):
        return value
    return ",".join(str(v) for v in value)


@app.get("/admin/announcements")
def list_announcements(principal: auth.Principal = guard("admin.announcements.list",
                                                         "*", school_rule="any")):
    with database().read() as tx:
        return {"announcements": [dict(r) for r in tx.all("announcements.all")]}


@app.post("/admin/announcements")
def create_announcement(request: Request, payload: dict = Body(...),
                        principal: auth.Principal = guard("admin.announcements.create",
                                                          "*", school_rule="any",
                                                          writes=True)):
    """A banner on every page in under a minute, without touching code."""
    body = (payload.get("body_md") or "").strip()
    if not body:
        raise catalog.ValidationError(["Write the announcement first."])
    with database().tx(request_id=request_id(request)) as tx:
        announcement_id = tx.insert("announcements.create", (
            body, payload.get("level") or "info",
            1 if payload.get("active", True) else 0,
            payload.get("starts_at"), payload.get("ends_at"),
            principal.person_id, clock.now_iso()))
        tx.audit("announcement.update",
                 f"{principal.display_name} published an announcement.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 entity_type="announcement", entity_id=announcement_id)
    return {"ok": True, "id": announcement_id}


@app.get("/admin/roles")
def list_roles(principal: auth.Principal = guard("admin.roles.list", "*",
                                                 school_rule="any")):
    with database().read() as tx:
        return {"roles": [dict(r) for r in tx.all("roles.all")]}


@app.post("/admin/roles")
def create_role(request: Request, payload: dict = Body(...),
                principal: auth.Principal = guard("admin.roles.create", "*",
                                                  school_rule="any", writes=True)):
    """Any combination of scopes, so a future chair is provisioned without a deploy."""
    key = (payload.get("key") or "").strip().lower().replace(" ", "_")
    name = (payload.get("name") or "").strip()
    scopes = payload.get("scopes") or []
    valid = {"*", "registration", "academics", "awards", "sponsor", "delegate", "chapter"}
    if not key or not name or not scopes or not set(scopes) <= valid:
        raise catalog.ValidationError(
            ["Give the role a key, a name, and at least one valid scope."])

    with database().tx(request_id=request_id(request)) as tx:
        role_id = tx.insert("roles.create", (key, name, payload.get("description"),
                                             clock.now_iso()))
        for scope in scopes:
            tx.run("roles.add_scope", (role_id, scope))
        tx.audit("role.create",
                 f"{principal.display_name} created the role {name} "
                 f"({', '.join(sorted(scopes))}).",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 entity_type="role", entity_id=role_id)
    return {"ok": True, "id": role_id}


@app.post("/admin/people/{person_id}/roles")
def grant_role(person_id: int, request: Request, payload: dict = Body(...),
               principal: auth.Principal = guard("admin.people.roles", "*",
                                                 school_rule="any", writes=True)):
    role_key = payload.get("role_key")
    grant = bool(payload.get("granted", True))
    with database().tx(request_id=request_id(request)) as tx:
        person = dict(tx.one("people.get", (person_id,)) or {})
        role = tx.one("roles.by_key", (role_key,))
        if not person or role is None:
            raise catalog.ValidationError(["No such person or role."])
        name = f"{person['first_name']} {person['last_name']}".strip()
        if grant:
            tx.run("people.grant_role",
                   (person_id, role["id"], principal.person_id, clock.now_iso()))
            tx.audit("role.grant",
                     f"{principal.display_name} granted {name} the role {role['name']}.",
                     actor_person_id=principal.person_id,
                     impersonator_person_id=principal.impersonator_person_id,
                     school_id=person["school_id"], entity_type="person",
                     entity_id=person_id)
        else:
            tx.run("people.revoke_role", (person_id, role["id"]))
            tx.audit("role.revoke",
                     f"{principal.display_name} removed the role {role['name']} "
                     f"from {name}.",
                     actor_person_id=principal.person_id,
                     impersonator_person_id=principal.impersonator_person_id,
                     school_id=person["school_id"], entity_type="person",
                     entity_id=person_id)
        tx.run("auth.session_revoke_all_for_person", (clock.now_iso(), person_id))
    return {"ok": True}


@app.get("/admin/people")
def search_people(school_id: int = Query(...),
                  principal: auth.Principal = guard("admin.people.search", "*",
                                                    school_rule="any")):
    with database().read() as tx:
        return {"people": [dict(r) for r in tx.all("admin.people_search", (school_id,))]}


@app.get("/admin/warm")
def get_warm(principal: auth.Principal = guard("admin.warm.get", "*",
                                               school_rule="any")):
    with database().read() as tx:
        warm_until = settings.get_datetime(tx, "ops.warm_until")
    return {"warm_until": warm_until, "warm_now": not clock.is_past(warm_until)
            if warm_until else False}


@app.put("/admin/warm")
def set_warm(request: Request, payload: dict = Body(...),
             principal: auth.Principal = guard("admin.warm.put", "*",
                                               school_rule="any", writes=True)):
    """Set how long containers stay warm.

    The DATABASE is the source of truth, not the Modal API: deploying resets the
    autoscaler to whatever is in code, so a one-shot button press would be
    silently undone by the first hotfix during convention. A cron reconciles
    reality to this value every five minutes.
    """
    hours = float(payload.get("hours") or 0)
    value = clock.plus_hours(hours) if hours > 0 else ""
    with database().tx(request_id=request_id(request)) as tx:
        tx.run("settings.update", (value, clock.now_iso(), principal.person_id,
                                   "ops.warm_until"))
        tx.audit("warm.set",
                 f"{principal.display_name} asked for warm containers for the "
                 f"next {hours:g} hours." if hours > 0 else
                 f"{principal.display_name} turned off warm containers.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 changed_fields=["ops.warm_until"])
        settings.invalidate()
    return {"ok": True, "warm_until": value}


@app.post("/admin/export")
def export(payload: dict = Body(default={}),
           principal: auth.Principal = guard("admin.export", "*",
                                             school_rule="any")):
    """Export the database and hand the file straight back as a download.

    Runs INLINE rather than spawning the fat worker: the SQL writer needs
    nothing beyond the standard library and openpyxl is pure Python, so an
    export arrives immediately instead of waiting on a cold container. The same
    code is `backend/workers/export.py`, which also runs standalone in a Colab
    given a `.db` file -- that is the fallback every other fallback rests on.

    Writing exports to Drive is a separate concern that goes through the Apps
    Script puppet. This path deliberately does not need it: an admin who can
    reach this endpoint can always get a file out, even with Drive unavailable.
    """
    import tempfile

    from .workers import export as exporter

    fmt = (payload.get("format") or "sql").lower()
    if fmt not in ("sql", "xlsx"):
        raise catalog.ValidationError(["Choose either sql or xlsx."])
    anonymized = bool(payload.get("anonymized"))

    with tempfile.TemporaryDirectory() as work:
        source = _local_database_copy(work)
        conn = exporter.open_db(source)
        try:
            writer = exporter.export_sql if fmt == "sql" else exporter.export_xlsx
            path = writer(conn, __import__("pathlib").Path(work), anonymized)
            body = path.read_bytes()
            name = path.name
        finally:
            conn.close()

    with database().tx() as tx:
        tx.audit(
            "export.run",
            f"{principal.display_name} exported the database as "
            f"{'an anonymised' if anonymized else 'a full'} {fmt.upper()} file.",
            actor_person_id=principal.person_id,
            impersonator_person_id=principal.impersonator_person_id,
        )

    media = ("application/sql" if fmt == "sql"
             else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    from fastapi.responses import Response
    return Response(content=body, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        # A full export carries names and guardian phone numbers. Nothing
        # should keep a copy of it lying around.
        "Cache-Control": "no-store",
    })


def _local_database_copy(work: str) -> str:
    """A real .db file to export from, whichever backend is in use.

    Local development already has one. On Turso this mirrors the live database
    into a file first -- libSQL *is* SQLite, so the result opens in DB Browser
    and loads into a Colab, which is the property the fallbacks depend on.
    """
    url = os.environ.get("TURSO_DATABASE_URL", "dev.db")
    if not url.startswith(("libsql://", "https://", "http://", "wss://", "ws://")):
        return url[5:] if url.startswith("file:") else url

    from .workers.export import mirror_turso_to_file
    return mirror_turso_to_file(work)


@app.get("/admin/usage")
def usage(principal: auth.Principal = guard("admin.usage", "*",
                                            school_rule="any")):
    """Current Turso usage, so quota drift is visible before it is an outage.

    Exceeding a read quota returns BLOCKED and the database stops answering --
    a state no amount of money resolves during convention. This page is the
    early warning.

    Degrades honestly: without a platform token it says what is missing and
    where to look instead, rather than showing zeros that read as "plenty of
    room".
    """
    token = os.environ.get("TURSO_PLATFORM_TOKEN")
    org = os.environ.get("TURSO_ORG")
    db_name = os.environ.get("TURSO_DB_NAME")

    if not (token and org and db_name):
        return {
            "configured": False,
            "message": "Turso usage is not wired up. Set TURSO_PLATFORM_TOKEN, "
                       "TURSO_ORG and TURSO_DB_NAME in Modal Secrets, or read "
                       "the figures on the Turso dashboard.",
            "dashboard": "https://turso.tech/app",
            "free_tier": {"rows_read": 500_000_000, "rows_written": 10_000_000,
                          "storage_bytes": 5 * 1024 ** 3},
        }

    import urllib.error
    import urllib.request

    url = (f"https://api.turso.tech/v1/organizations/{org}"
           f"/databases/{db_name}/usage")
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        # Never let the usage page take the site down with it.
        return {"configured": True, "error": f"Could not reach Turso: {error}",
                "dashboard": "https://turso.tech/app"}

    used = (body.get("database", {}) or {}).get("usage", {}) or {}
    reads = used.get("rows_read", 0)
    writes = used.get("rows_written", 0)
    storage = used.get("storage_bytes", 0)
    return {
        "configured": True,
        "rows_read": reads,
        "rows_written": writes,
        "storage_bytes": storage,
        "percent": {
            "rows_read": round(reads / 500_000_000 * 100, 2),
            "rows_written": round(writes / 10_000_000 * 100, 2),
            "storage": round(storage / (5 * 1024 ** 3) * 100, 2),
        },
    }


@app.post("/admin/demo/reset")
def reset_demo(request: Request,
               principal: auth.Principal = guard("admin.demo.reset", "*",
                                                 school_rule="any", writes=True)):
    """Rebuild the demonstration data from scratch.

    Behind scope '*' so a presentation can be rerun cleanly if something goes
    wrong mid-demo. Refuses outright unless the database is already flagged as
    demonstration data -- this drops every table, and doing that to a live
    convention because someone clicked the wrong button is unrecoverable.
    """
    with database().read() as tx:
        if not settings.get_bool(tx, "ops.demo_mode"):
            raise auth.ForbiddenError(
                "This database is not marked as demonstration data, so the "
                "reset is disabled. Turn on ops.demo_mode first if you really "
                "mean to erase everything.")

    import scripts.seed as seed_script

    db = database()
    seed_script.wipe(db)
    seed_script.migrate(db)
    settings.invalidate()
    catalog.invalidate()
    codes_issued = seed_script.Seeder(db).run()
    return {"ok": True, "codes": codes_issued}


# ===========================================================================
# Print -- one HTML template per document, served as a print view and fed to
# WeasyPrint for the PDF. One layout, two renderers.
# ===========================================================================

@app.get("/sponsor/packet", response_class=HTMLResponse)
def packet(school_id: int | None = Query(default=None),
           person_id: int | None = Query(default=None),
           principal: auth.Principal = guard("sponsor.packet", "sponsor",
                                             "registration")):
    """The printable packet, or one attendee's sheet for a reprint."""
    with database().read() as tx:
        school = _school_of(tx, principal, school_id)
        if person_id is not None:
            auth.require_person_in_scope(tx, principal, person_id)
        return HTMLResponse(printing.render_packet(tx, school, only_person=person_id))


@app.get("/sponsor/invoice.html", response_class=HTMLResponse)
def invoice_html(school_id: int | None = Query(default=None),
                 principal: auth.Principal = guard("sponsor.invoice.html", "sponsor",
                                                   "registration")):
    with database().read() as tx:
        school = _school_of(tx, principal, school_id)
        return HTMLResponse(printing.render_invoice(tx, school))


@app.get("/health")
def health():
    """Cheap liveness check. Touches no table."""
    return {"ok": True, "service": "cajcl-2027",
            "env": os.environ.get("CAJCL_ENV", "development")}
