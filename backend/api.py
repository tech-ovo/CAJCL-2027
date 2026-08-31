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

from fastapi import Body, Depends, FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response

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
# An unbounded request body is a free way to make a container work hard: the
# roster paste is capped at 500 lines, but that check runs after FastAPI has
# already read and parsed however much was sent.
#
# 1 MB is roughly forty times the largest legitimate paste (500 lines of names)
# and larger than any other body this API accepts. Anything above it is a
# mistake or a probe, and either way the answer is the same.
MAX_BODY_BYTES = 1_048_576


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "That is too large to send. If you are "
                                       "pasting a roster, paste it in smaller "
                                       "batches."})
        except ValueError:
            return JSONResponse(status_code=400,
                                content={"detail": "Malformed request."})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Headers every response carries.

    None of these is the control that keeps a roster private -- that is the
    scope check on each endpoint. These close the gaps around it: a hostile
    page framing the sign-in form and collecting a code typed into it, and a
    browser guessing that a JSON body is really HTML.

    `frame-ancestors 'none'` is the modern form and `X-Frame-Options` is the
    old one; both are sent because the audience includes school Chromebooks
    that are not always current.
    """
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # FRAME-ANCESTORS AND BASE-URI ONLY, deliberately.
    #
    # A `default-src 'none'` here would also apply to the two responses that
    # are real HTML documents -- the printed packet and the printed invoice --
    # both of which carry an inline <style> and would have rendered as
    # unstyled text. The packet is the most important thing this system
    # produces on paper, and a policy that breaks it to defend a JSON endpoint
    # is a bad trade.
    #
    # What is left is the part that was actually missing: nothing may frame
    # this API, and nothing may retarget its relative URLs.
    response.headers["Content-Security-Policy"] = (
        "frame-ancestors 'none'; base-uri 'none'")
    return response


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
    # A READ transaction. Authentication happens on every request, and libSQL
    # has one writer -- opening a write transaction here meant every request
    # queued behind every other one, and two clicks in quick succession
    # returned SQLITE_BUSY to somebody standing at a check-in desk.
    with database().read() as tx:
        principal = auth.authenticate(tx, token)

    # The last-seen timestamp, if it has actually gone stale: a separate, tiny
    # write that the request does not wait on the lock for. Failing to record
    # it is not worth failing the request over -- it is a column shown on the
    # account page, not a fact anything depends on.
    if principal.needs_touch:
        try:
            with database().tx() as tx:
                auth.touch_session(tx, principal.session_id)
        except Exception:
            pass

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

    # `demo_mode` so the caller does not have to turn round and ask /auth/me
    # for it. Signing in used to cost two requests -- one to exchange the code,
    # one to find out who that was -- which on a cold container is two waits
    # where the delegate can see only the second one.
    #
    # `sessions` is deliberately NOT here. It is a list that grows with every
    # device a person has ever used, only the account page wants it, and that
    # page fetches /auth/me for itself.
    with database().read() as tx:
        demo = settings.get_bool(tx, "ops.demo_mode")
        own = tx.one("forms.own_completeness", (principal.person_id,))

    body = principal.to_public_dict()
    body["demo_mode"] = demo
    # So the navigation can mark their own Registration tab from the first
    # frame, rather than only after /auth/me is next called.
    body["registration_complete"] = _own_registration_complete(own)
    return {"token": token, "person": body}


@app.get("/auth/me")
def me(principal: auth.Principal = Depends(any_session)):
    with database().read() as tx:
        sessions = [dict(r) for r in tx.all("auth.sessions_for_person",
                                            (principal.person_id,))]
        demo = settings.get_bool(tx, "ops.demo_mode")
        # IS THEIR OWN REGISTRATION FINISHED? One row, by primary key, so the
        # navigation can mark the tab that still needs them. Same definition
        # the chapter counters use, so a delegate and their sponsor never
        # disagree about whether that person is done.
        own = tx.one("forms.own_completeness", (principal.person_id,))
    body = principal.to_public_dict()
    body["sessions"] = sessions
    body["demo_mode"] = demo
    body["registration_complete"] = _own_registration_complete(own)
    return body


def _own_registration_complete(row) -> bool:
    if row is None:
        return False
    if not row["form_done"]:
        return False
    if row["person_type"] == "delegate":
        return bool(row["waiver_received"] and row["medical_received"])
    return bool(row["adult_medical_received"])


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
    with database().read() as tx:
        demo = settings.get_bool(tx, "ops.demo_mode")
    body = target.to_public_dict()
    body["demo_mode"] = demo
    return {"token": token, "person": body}


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


def _person_of(tx, principal: auth.Principal, person_id: int) -> dict:
    """Resolve one person this request acts on, and check the caller may.

    The scope check comes FIRST and is not optional. Every endpoint that names
    a person in its path is one missing line away from letting a sponsor at one
    chapter edit a delegate at another, and the two steps were written out by
    hand at seven call sites. Here they cannot be separated.
    """
    auth.require_person_in_scope(tx, principal, person_id)
    person = tx.one("people.get", (person_id,))
    if person is None:
        raise auth.ForbiddenError("no such person")
    return dict(person)


def _person_and_school(tx, principal: auth.Principal,
                       person_id: int) -> tuple[dict, dict]:
    """The same, plus the school they belong to -- which `roster` needs in
    order to recount it after the change."""
    person = _person_of(tx, principal, person_id)
    school = tx.one("schools.get", (person["school_id"],))
    if school is None:
        raise auth.ForbiddenError("no such school")
    return person, dict(school)


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
        # Whether the deadline has passed at all. Reopening a form is only
        # meaningful once it has: before that every form is already open, and a
        # "Reopen form" button on every row is a control that does nothing.
        forms_closed = clock.is_past(
            settings.get_datetime(tx, "deadline.forms_lock"))
    return {
        "school": _school_public(school, principal),
        "people": people,
        "stats": dict(counters) if counters else {},
        "chapter_entries": entries,
        "forms_closed": forms_closed,
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
        person = _person_of(tx, principal, person_id)
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
        person, school = _person_and_school(tx, principal, person_id)
        status = roster.cancel(tx, school, principal, person)
    return {"ok": True, "status": status}


@app.post("/sponsor/people/{person_id}/restore")
def restore_person(person_id: int, request: Request,
                   principal: auth.Principal = guard("sponsor.people.restore",
                                                     "sponsor", "registration",
                                                     writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        person, school = _person_and_school(tx, principal, person_id)
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
        person, school = _person_and_school(tx, principal, person_id)
        code = roster.regenerate_code(tx, school, principal, person)
    return {
        "code": code,
        "person_id": person_id,
        "reprint_url": f"/sponsor/packet?person_id={person_id}",
        "note": "This is the only time this code is shown. Reprint the sheet now.",
    }


@app.post("/sponsor/regenerate-codes")
def regenerate_many(request: Request, payload: dict = Body(...),
                    principal: auth.Principal = guard(
                        "sponsor.people.regenerate_many",
                        "sponsor", "registration", writes=True)):
    """Issue new codes for a chosen few, and return them with their sheets.

    WHY THIS IS A LIST AND NOT A BUTTON THAT SAYS "EVERYONE"
        A code is stored only as an HMAC, so a code that was never written down
        cannot be recovered -- the packet prints blocks where it would go. The
        way out is to mint new ones, and the way that stays safe is to mint them
        for the people who actually need them. A whole-chapter reissue would
        sign out every delegate who was already using the site, most of whom
        have their sheet and are perfectly fine.

        The caller therefore names each person. There is no "all" shortcut on
        purpose; the checklist in the roster is the safeguard.

    Every code comes back ONCE, together with a print link, because a code
    nobody printed is exactly the problem this endpoint exists to fix.
    """
    ids = payload.get("person_ids")
    if not isinstance(ids, list) or not ids:
        raise catalog.ValidationError(["Choose at least one person."])
    if len(ids) > 200:
        raise catalog.ValidationError(["That is more people than one chapter has."])

    try:
        wanted = [int(raw) for raw in ids]
    except (TypeError, ValueError):
        raise catalog.ValidationError(["That is not a list of people."])

    school_id = payload.get("school_id")
    issued = []

    with database().tx(request_id=request_id(request)) as tx:
        school = _school_of(tx, principal, school_id)
        for person_id in wanted:
            auth.require_person_in_scope(tx, principal, person_id)
            person = tx.one("people.get", (person_id,))
            if person is None:
                raise auth.ForbiddenError("no such person")
            if person["school_id"] != school["id"]:
                raise auth.ForbiddenError("that belongs to a different school")

            code = roster.regenerate_code(tx, school, principal, dict(person))
            issued.append({
                "person_id": person_id,
                "name": f"{person['first_name']} {person['last_name']}".strip(),
                "code": code,
            })

    return {
        "issued": issued,
        "print_url": "/sponsor/packet?person_ids="
                     + ",".join(str(row["person_id"]) for row in issued),
        "note": "These codes are shown once. Print the sheets before leaving "
                "this page.",
    }


@app.post("/sponsor/people/{person_id}/chapter-leader")
def set_chapter_leader(person_id: int, request: Request, payload: dict = Body(...),
                       principal: auth.Principal = guard("sponsor.chapter_leader",
                                                         "sponsor", "registration",
                                                         writes=True)):
    """Grant or revoke the chapter_leader ROLE on an existing account.

    A scope is never attached to a person directly. The only path is
    person_roles -> roles -> role_scopes, and this endpoint inserts or deletes
    exactly one person_roles row. There is never a second code.
    """
    grant = bool(payload.get("granted", True))
    with database().tx(request_id=request_id(request)) as tx:
        person = _person_of(tx, principal, person_id)
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


@app.put("/sponsor/chapter-note")
def put_chapter_note(request: Request, payload: dict = Body(...),
                     principal: auth.Principal = guard("sponsor.chapter_note",
                                                       "sponsor", "registration",
                                                       writes=True)):
    """A note about the chapter, tied to no particular person.

    How many Certamen machines they are bringing, roughly when they expect to
    arrive, that their bus has to leave by four. None of it belongs on a
    delegate's row, and all of it was going in emails that the person on the
    desk in March never saw.

    TEXT, NOT A TIME. "Some time after three, depending on traffic" is the true
    answer and a time field cannot hold it. A field that forces a precision
    nobody has gets filled in with a lie.

    Distinct from `checkin_note`, which the desk writes on the Friday about
    what actually turned up.
    """
    note = (payload.get("note") or "").strip() or None
    with database().tx(request_id=request_id(request)) as tx:
        school = _school_of(tx, principal, payload.get("school_id"))
        tx.run("schools.set_note", (note, clock.now_iso(), school["id"]))
        tx.audit("school.update",
                 f"{principal.display_name} "
                 + ("updated" if note else "cleared")
                 + f" the chapter note for {school['name']}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 school_id=school["id"], entity_type="school",
                 entity_id=school["id"], changed_fields=["notes"])
    return {"ok": True, "note": note}


@app.post("/sponsor/paper-forms")
def mark_paper(request: Request, payload: dict = Body(...),
               principal: auth.Principal = guard("sponsor.paper_forms", "sponsor",
                                                 "registration", writes=True)):
    with database().tx(request_id=request_id(request)) as tx:
        person_id = int(payload.get("person_id") or 0)
        person, school = _person_and_school(tx, principal, person_id)
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


@app.get("/sponsor/people/{person_id}/activity-sheet")
def get_activity_sheet_for(person_id: int,
                           principal: auth.Principal = guard(
                               "sponsor.activity_sheet", "sponsor",
                               "registration")):
    """A delegate's activity sheet, opened by their sponsor or a chair.

    THE SAME FORM, NOT A COPY OF IT. The delegate's own screen and this one
    read and write the same shape, so a rule enforced on one is enforced on the
    other -- the test-count minimum, the eligibility gating, all of it.

    Why this exists: a delegate who has lost their sheet, or who is eleven and
    has given up, leaves their sponsor with a roster row that says "Not yet"
    and no way to move it. The sponsor is the person the chapter holds
    responsible for that row.
    """
    with database().read() as tx:
        person = _person_of(tx, principal, person_id)
        if person["person_type"] != "delegate":
            raise auth.ForbiddenError("that form is for delegates")
        school = tx.one("schools.get", (person["school_id"],))
        person = {**person, "school_level": school["level"],
                  "school_name": school["name"],
                  "school_number": school["number"]}
        return forms.activity_sheet(tx, person)


@app.put("/sponsor/people/{person_id}/activity-sheet")
def put_activity_sheet_for(person_id: int, request: Request,
                           payload: dict = Body(...),
                           principal: auth.Principal = guard(
                               "sponsor.activity_sheet.save", "sponsor",
                               "registration", writes=True)):
    """Save a delegate's sheet on their behalf.

    Audited as the SPONSOR's action, because it is one. `save_activity_sheet`
    writes the audit entry from the principal it is handed, so the log says who
    actually did this rather than crediting it to the delegate -- which is the
    difference between a record and a fiction.
    """
    with database().tx(request_id=request_id(request)) as tx:
        person = _person_of(tx, principal, person_id)
        if person["person_type"] != "delegate":
            raise auth.ForbiddenError("that form is for delegates")
        school = tx.one("schools.get", (person["school_id"],))
        person = {**person, "school_level": school["level"]}
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


def _self(tx, principal: auth.Principal) -> dict:
    """The caller's own person row, joined to their school.

    Under impersonation this is the TARGET's row, which is the whole point: an
    admin debugging a confused sponsor sees exactly what that sponsor sees.
    """
    person = dict(tx.one("people.get", (principal.person_id,)))
    school = tx.one("schools.get", (person["school_id"],))
    person["school_level"] = school["level"]
    person["school_name"] = school["name"]
    # The chapter half of the number printed beside their name: 07014.
    person["school_number"] = school["number"]
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
    # The city is not optional. It appears on the tabula beside every chapter
    # name, and a blank one renders as a stray separator -- and at a fifty-
    # chapter convention "Lincoln High School" is genuinely ambiguous without
    # it. Cheap to ask for once; awkward to backfill for everyone later.
    city = (payload.get("city") or "").strip()

    problems = []
    if not name:
        problems.append("Give the chapter a name.")
    if level not in ("MS", "HS"):
        problems.append("Say whether it is a middle school or a high school.")
    if not city:
        problems.append("Give the chapter's city.")
    if problems:
        raise catalog.ValidationError(problems)

    now = clock.now_iso()
    with database().tx(request_id=request_id(request)) as tx:
        school_id = tx.insert("schools.create", (
            name, level, "chapter", city,
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
        # `_insert_person` already minted one. Issuing a second here replaced it
        # a millisecond later, which worked and was one wasted write plus one
        # dead code per sponsor created.
        code = created["code"]
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


@app.get("/admin/checkin")
def checkin_board(principal: auth.Principal = guard("admin.checkin", "registration",
                                                    school_rule="any")):
    """The Friday desk.

    Chapters arrive after school, fifty of them, in about ninety minutes.
    Everything here is per CHAPTER: they arrive together, in a bus, and ticking
    sixty individual boxes with a queue behind you is not a thing anybody does.

    Not-yet-arrived chapters sort first, because the desk works down a list of
    who is still outstanding.
    """
    with database().read() as tx:
        rows = [dict(r) for r in tx.all("stats.checkin_board")]

    arrived = sum(1 for r in rows if r["arrived_at"])
    return {
        "chapters": rows,
        "totals": {
            "chapters": len(rows),
            "arrived": arrived,
            "waiting": len(rows) - arrived,
            "people_arrived": sum(r["delegates_active"] + r["adults_active"]
                                  for r in rows if r["arrived_at"]),
        },
    }


@app.post("/admin/checkin/{school_id}")
def checkin_school(school_id: int, request: Request, payload: dict = Body(...),
                   principal: auth.Principal = guard("admin.checkin.mark",
                                                     "registration",
                                                     school_rule="any",
                                                     writes=True)):
    """Mark a chapter arrived, or un-mark it, and save its note.

    Un-marking has to be possible: the commonest mistake at a desk is ticking
    the row above the one you meant.

    The time is the server's, not the client's. A phone with the wrong clock
    would otherwise write a check-in time nobody can reconcile with anything.
    """
    with database().tx(request_id=request_id(request)) as tx:
        school = tx.one("schools.get", (school_id,))
        if school is None:
            raise auth.ForbiddenError("no such chapter")

        now = clock.now_iso()
        changed = []

        if "arrived" in payload:
            arrived_at = now if payload.get("arrived") else None
            tx.run("stats.set_arrived", (arrived_at, now, school_id))
            changed.append("arrived_at")

        if "note" in payload:
            note = (payload.get("note") or "").strip() or None
            tx.run("schools.set_checkin_note", (note, now, school_id))
            changed.append("checkin_note")

        if not changed:
            raise catalog.ValidationError(["Nothing to record."])

        summary = (f"{principal.display_name} "
                   + ("marked " + school["name"] + " arrived"
                      if payload.get("arrived")
                      else ("un-marked " + school["name"] + " as arrived"
                            if "arrived" in payload
                            else "noted something about " + school["name"]))
                   + ".")
        tx.audit("checkin.update", summary, school_id=school_id,
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 entity_type="school", entity_id=school_id,
                 changed_fields=changed)

    with database().read() as tx:
        row = dict(tx.one("schools.get", (school_id,)))
        stats_row = dict(tx.one("stats.for_school", (school_id,)) or {})
    return {"ok": True, "arrived_at": stats_row.get("arrived_at"),
            "note": row.get("checkin_note")}


@app.post("/admin/people/{person_id}/waive-activity-sheet")
def waive_activity_sheet(person_id: int, request: Request,
                         payload: dict = Body(...),
                         principal: auth.Principal = guard(
                             "admin.people.waive", "registration",
                             school_rule="any", writes=True)):
    """A delegate added at the desk to replace somebody who could not come.

    Their waiver and medical are still required -- those are safety documents
    and nobody is exempt. Their activity sheet is waived, because the tests
    were printed and the food ordered weeks ago and there is nothing left for
    their answers to change.

    They are excluded from the academic counts entirely: they are entered in
    nothing, so a proctor's sheet must not carry their name.
    """
    waived = 1 if payload.get("waived", True) else 0
    with database().tx(request_id=request_id(request)) as tx:
        person = tx.one("people.get", (person_id,))
        if person is None:
            raise auth.ForbiddenError("no such person")

        tx.run("people.waive_activity_sheet", (waived, clock.now_iso(), person_id))
        name = f"{person['first_name']} {person['last_name']}"
        tx.audit("person.update",
                 f"{principal.display_name} "
                 + ("waived" if waived else "un-waived")
                 + f" {name}'s activity sheet.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 school_id=person["school_id"],
                 entity_type="person", entity_id=person_id,
                 changed_fields=["activity_sheet_waived"])
        stats.recompute(tx, person["school_id"],
                        settings=settings.fee_settings(tx))
    return {"ok": True, "waived": bool(waived)}


@app.get("/admin/overview")
def registration_overview(principal: auth.Principal = guard("admin.overview",
                                                            "registration",
                                                            school_rule="any")):
    """Everything a registration chair wants on one screen.

    Reads `school_stats` -- about fifty rows -- and never `people`. Every
    number here was counted inside the transaction that changed it; see
    migration 012.
    """
    with database().read() as tx:
        rows = [dict(r) for r in tx.all("stats.registration_overview")]

    totals = {
        "chapters": 0, "chapters_started": 0, "chapters_paid": 0,
        "delegates": 0, "delegates_ms": 0, "delegates_hs": 0,
        "adults": 0, "sponsors": 0, "chaperones": 0,
        "other_adults": 0, "complete": 0, "people": 0,
        "meal_regular": 0, "meal_vegetarian": 0, "meal_gluten_free": 0,
        "meal_unanswered": 0, "meal_none": 0,
        "owed_cents": 0, "paid_cents": 0, "outstanding_cents": 0,
    }

    for row in rows:
        row["other_adults"] = max(0, row["adults_active"]
                                  - row["adults_sponsors"]
                                  - row["adults_chaperones"])
        row["people"] = row["delegates_active"] + row["adults_active"]
        row["complete"] = row["delegates_complete"] + row["adults_complete"]
        row["balance_cents"] = row["amount_owed_cents"] - row["amount_paid_cents"]
        row["has_sponsor"] = row["adults_sponsors"] > 0

        if row["status"] != "active":
            continue

        # CHAPTERS are counted; PEOPLE are counted wherever they come from.
        # SCL is not a chapter and must not inflate the chapter figure, but its
        # attendees are attending, and the meal totals below feed a caterer.
        is_chapter = row["kind"] == "chapter"
        if is_chapter:
            totals["chapters"] += 1
            if row["people"]:
                totals["chapters_started"] += 1
        # An exempt chapter owes nothing, so "paid" is not a useful thing to
        # say about it. Counting it as unpaid would make the figure read as a
        # problem that cannot be solved.
        if is_chapter and (row["billing_exempt"] or row["balance_cents"] <= 0):
            totals["chapters_paid"] += 1

        for key in ("delegates_active", "adults_active", "adults_sponsors",
                    "adults_chaperones", "other_adults", "complete", "people",
                    "meal_regular", "meal_vegetarian", "meal_gluten_free",
                    "meal_unanswered", "meal_none"):
            target = {"delegates_active": "delegates", "adults_active": "adults",
                      "adults_sponsors": "sponsors",
                      "adults_chaperones": "chaperones"}.get(key, key)
            totals[target] += row[key]

        # Delegates by school level. Almost every question a chair is asked
        # about numbers is really about one level: how many papers at each
        # level, how many rooms, which Certamen bracket. A school is wholly
        # one or the other -- a school sending both registers as two chapters.
        if row["level"] == "MS":
            totals["delegates_ms"] += row["delegates_active"]
        else:
            totals["delegates_hs"] += row["delegates_active"]

        totals["owed_cents"] += row["amount_owed_cents"]
        totals["paid_cents"] += row["amount_paid_cents"]
        if not row["billing_exempt"]:
            totals["outstanding_cents"] += max(0, row["balance_cents"])

    return {"chapters": rows, "totals": totals}


@app.patch("/admin/academics/item/{item_id}/code")
def set_item_code(item_id: int, request: Request, payload: dict = Body(...),
                  principal: auth.Principal = guard("admin.academics.code",
                                                    "academics", "awards",
                                                    school_rule="any",
                                                    writes=True)):
    """The four-digit number printed on a test's answer sheet.

    A NARROW HOLE ON PURPOSE. The Academics chairs need this one field and hold
    `academics`, not `*` -- they have no business renaming a test, changing who
    may enter it, or touching the fee, and the catalog editor next door does
    all three. So this endpoint sets exactly one column and nothing else.

    The alternative was a scoped view of Settings, which would have meant
    deciding per setting who may see it and getting that right forever. One
    endpoint that can only write one column is a smaller thing to be sure of.
    """
    raw = (payload.get("item_code") or "").strip()
    code = raw or None
    if code is not None and (len(code) != 4 or not code.isdigit()):
        raise catalog.ValidationError([
            "A test number is four digits, like 0142."])

    with database().tx(request_id=request_id(request)) as tx:
        item = catalog.load(tx)["items_by_id"].get(item_id)
        if item is None:
            raise catalog.ValidationError(["There is no such test or activity."])

        if code is not None:
            holder = tx.one("catalog.item_by_code", (code,))
            if holder is not None and holder["id"] != item_id:
                raise catalog.ValidationError([
                    f"{code} is already {holder['name']}. Two tests cannot "
                    "share a number: the answer sheets would be unsortable."])

        tx.run("catalog.item_set_code", (code, item_id))
        tx.audit("catalog.update",
                 f"{principal.display_name} "
                 + (f"numbered {item['name']} {code}." if code
                    else f"cleared the number on {item['name']}."),
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 entity_type="catalog_item", entity_id=item_id,
                 changed_fields=["item_code"])
        catalog.invalidate()
    return {"ok": True, "item_code": code}


@app.get("/admin/academics/counts")
def academics_counts(principal: auth.Principal = guard("admin.academics.counts",
                                                       "academics", "awards",
                                                       school_rule="any")):
    """How many delegates have registered for each test and activity.

    THIS IS REGISTRATION DATA, NOT GRADING. It answers "how many papers do we
    print, and how many rooms do we need", which is a question the Academics,
    Activities and Athletics chairs have to answer weeks before anybody sits
    anything. Scores, placings and Certamen are not built.

    One indexed seek per catalog item -- about fifty -- rather than a scan of
    every selection at the convention. See academics.sql.
    """
    with database().read() as tx:
        rows = [dict(r) for r in tx.all("academics.item_counts")]

    for row in rows:
        row["chosen_hs"] = row["chosen"] - row["chosen_ms"]
    with database().read() as tx2:
        deadline = settings.get(tx2, "deadline.forms_lock")

    return {
        "items": rows,
        "deadline": deadline,
        "totals": {
            "items_offered": len(rows),
            "entries": sum(r["chosen"] for r in rows),
            "chapter_entries": sum(r["chapter_entries"] for r in rows),
        },
    }


@app.get("/admin/academics/item/{item_id}")
def academics_item(item_id: int,
                   principal: auth.Principal = guard("admin.academics.item",
                                                     "academics", "awards",
                                                     school_rule="any")):
    """One item: which chapters, and who.

    The names are what a proctor's sign-in sheet is made of, and they are
    bounded by the number of people who chose this item rather than by the size
    of the convention.
    """
    with database().read() as tx:
        item = tx.one("academics.item", (item_id,))
        if item is None:
            raise auth.ForbiddenError("no such item")
        chapters = [dict(r) for r in tx.all("academics.item_by_chapter", (item_id,))]
        people = [dict(r) for r in tx.all("academics.item_people", (item_id,))]

    return {
        "item": dict(item),
        "chapters": chapters,
        "people": people,
        "total": len(people),
    }


@app.get("/admin/schools/{school_id}/history")
def school_history(school_id: int, limit: int = Query(default=60, le=200),
                   principal: auth.Principal = guard("admin.school.history",
                                                     "registration",
                                                     school_rule="any")):
    """Why this chapter's balance is what it is.

    The payments list says what arrived. It does not say why the amount OWED
    moved -- a delegate added, somebody cancelled, a discount applied, or the
    eleventh delegate quietly making a second adult free. When a sponsor
    disputes a figure in March, that is the argument, and until now the only
    record of it was the full audit log behind scope `*`.

    A NARROWER READ THAN /admin/audit, not a widening of it. This is one
    school, capped, and only the actions that can move a number: it is not a
    way for a registration chair to read the whole log.
    """
    with database().read() as tx:
        school = tx.one("schools.get", (school_id,))
        if school is None:
            raise auth.ForbiddenError("no such school")
        rows = [dict(r) for r in
                tx.all("audit.recent_by_school", (school_id, 2 ** 62, limit))]

    kinds = ("person.create", "person.cancel", "person.restore",
             "roster.commit", "payment.record", "school.update")
    entries = [
        {
            "ts_utc": row["ts_utc"],
            "action": row["action"],
            "summary": row["summary"],
            "entity_id": row["entity_id"],
            "entity_type": row["entity_type"],
            "by": " ".join(filter(None, [row["actor_first_name"],
                                         row["actor_last_name"]])) or None,
        }
        for row in rows if row["action"] in kinds
    ]
    return {"school_id": school_id, "history": entries}


@app.get("/admin/logins")
def recent_logins(limit: int = Query(default=100, le=500),
                  principal: auth.Principal = guard("admin.logins", "*",
                                                    school_rule="any")):
    """Recent sign-in attempts, successful and not.

    What this answers is "is somebody grinding at this", and the shape of the
    answer is repetition: the same address failing over and over, or one prefix
    being tried across many addresses. Both are visible without knowing whose
    address it is.

    THE IP NEVER BECOMES AN ADDRESS AGAIN. It is a peppered HMAC in the
    database and it is returned as one, truncated to twelve characters -- long
    enough to tell two places apart by eye, short enough to be no use for
    anything else. The pepper is in Modal Secrets, so even this program cannot
    turn it back into an address.
    """
    with database().read() as tx:
        rows = [dict(r) for r in tx.all("audit.recent_logins", (limit,))]
    for row in rows:
        row["ip_hash"] = row["ip_hash"][:12]
        row["succeeded"] = bool(row["succeeded"])
    return {"logins": rows}


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
        rows = []
        for row in settings.rows(tx):
            item = dict(row)
            # The dashboard renders from this, not from value_type. See
            # settings.render_hint for why the server is the one that decides.
            item["render_as"] = settings.render_hint(row)
            rows.append(item)
        return {"settings": rows,
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
            hint = settings.render_hint(row)
            if hint == "deadline" and value and "T" not in str(value):
                value = clock.end_of_day_utc(str(value))
            elif hint == "date" and value:
                # A calendar date, not an instant. Stored exactly as typed, so
                # `convention.start_date` stays the string every other part of
                # the system already parses.
                value = str(value).strip()
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
    """The whole catalog, for the screen that edits it.

    Items and options as well as categories: the editor needs all three, the
    whole thing is about 150 rows, and it is already loaded into memory once
    per container. Sending it in three requests would be three round trips to
    assemble one page.
    """
    with database().read() as tx:
        data = catalog.load(tx)
        # `categories` already carries its items, and each item its active
        # options. `options` is the full list including retired ones, which is
        # the only way the editor can bring one back.
        return {"categories": data["categories"], "options": data["options"]}


@app.post("/admin/catalog/items")
def create_catalog_item(request: Request, payload: dict = Body(...),
                        principal: auth.Principal = guard("admin.catalog.create",
                                                          "*", school_rule="any",
                                                          writes=True)):
    """A new test or event, without a migration.

    docs/structure.md puts this in scope in as many words: "adding a new *ludus*
    for 2028 should require no code". Until now it required a migration, a
    deploy, and somebody who knew what a migration was -- which in a system
    handed to different students every year is the same as not being possible.

    The CATEGORY is not created here. Categories carry the rules a form is
    validated against -- how many you must pick, whether that is a block or a
    warning -- and inventing one from a text box is how a delegate ends up
    unable to submit for a reason nobody can find. Those stay in a migration.
    """
    name = (payload.get("name") or "").strip()
    category_id = int(payload.get("category_id") or 0)

    problems = []
    if not name:
        problems.append("Give it a name.")
    if not category_id:
        problems.append("Say which category it belongs to.")
    if problems:
        raise catalog.ValidationError(problems)

    with database().tx(request_id=request_id(request)) as tx:
        categories = {c["id"]: c for c in catalog.load(tx)["categories"]}
        if category_id not in categories:
            raise catalog.ValidationError(["There is no such category."])

        sort_order = payload.get("sort_order")
        if sort_order in (None, ""):
            sort_order = tx.value("catalog.next_sort_order", (category_id,),
                                  default=10)

        item_id = tx.insert("catalog.item_create", (
            category_id, name,
            (payload.get("description") or "").strip() or None,
            _csv(payload.get("eligible_latin_levels")),
            payload.get("registration_scope") or "individual",
            payload.get("max_sub_selections"),
            payload.get("min_latin_knowledge"),
            int(sort_order)))
        tx.audit("catalog.create",
                 f"{principal.display_name} added {name} to "
                 f"{categories[category_id]['name']}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 entity_type="catalog_item", entity_id=item_id)
        catalog.invalidate()
    return {"ok": True, "id": item_id}


@app.post("/admin/catalog/items/{item_id}/options")
def create_catalog_option(item_id: int, request: Request, payload: dict = Body(...),
                          principal: auth.Principal = guard("admin.catalog.option",
                                                            "*", school_rule="any",
                                                            writes=True)):
    """A sub-choice under one item: a medium under Drawing/Painting.

    Adding one to an item whose `max_sub_selections` is unset would produce a
    list nobody may choose from, so that is refused rather than silently
    accepted -- it is the sort of thing found by a delegate at midnight.
    """
    name = (payload.get("name") or "").strip()
    if not name:
        raise catalog.ValidationError(["Give the option a name."])

    with database().tx(request_id=request_id(request)) as tx:
        loaded = catalog.load(tx)
        item = loaded["items_by_id"].get(item_id)
        if item is None:
            raise catalog.ValidationError(["There is no such catalog entry."])
        if not item.get("max_sub_selections"):
            raise catalog.ValidationError([
                f"{item['name']} does not take sub-choices. Set how many may be "
                "picked first, then add them."])

        existing = [o for o in loaded["options"] if o["item_id"] == item_id]
        order = max([o["sort_order"] for o in existing] or [0]) + 10
        option_id = tx.insert("catalog.option_create", (item_id, name, order))
        tx.audit("catalog.update",
                 f"{principal.display_name} added the option {name} to "
                 f"{item['name']}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 entity_type="catalog_item", entity_id=item_id)
        catalog.invalidate()
    return {"ok": True, "id": option_id}


@app.put("/admin/catalog/options/{option_id}")
def put_catalog_option(option_id: int, request: Request, payload: dict = Body(...),
                       principal: auth.Principal = guard("admin.catalog.option.put",
                                                         "*", school_rule="any",
                                                         writes=True)):
    """Rename an option, reorder it, or switch it off.

    SWITCHED OFF, NEVER DELETED. A delegate may already have chosen it, and
    deleting the row would either fail on the foreign key or take their choice
    with it. Inactive means "not offered from now on", which is what retiring a
    medium actually means.
    """
    with database().tx(request_id=request_id(request)) as tx:
        loaded = catalog.load(tx)
        option = next((o for o in loaded["options"] if o["id"] == option_id), None)
        if option is None:
            raise catalog.ValidationError(["There is no such option."])

        tx.run("catalog.option_update", (
            (payload.get("name") or option["name"]).strip(),
            payload.get("sort_order", option["sort_order"]),
            1 if payload.get("active", option["active"]) else 0,
            option_id))
        tx.audit("catalog.update",
                 f"{principal.display_name} updated the option "
                 f"{payload.get('name', option['name'])}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 entity_type="catalog_item", entity_id=option["item_id"],
                 changed_fields=sorted(payload.keys()))
        catalog.invalidate()
    return {"ok": True}


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
    """A banner on every page, without touching code.

    `ends_at` arrives as a plain California date and becomes the end of that
    day, the same as every other deadline here -- nobody hand-types a UTC
    instant. See clock.py for why that matters.
    """
    body = (payload.get("body_md") or "").strip()
    if not body:
        raise catalog.ValidationError(["Write the announcement first."])

    ends_at = payload.get("ends_at") or None
    if ends_at:
        try:
            ends_at = clock.end_of_day_utc(ends_at)
        except Exception:
            raise catalog.ValidationError(
                ["That is not a date the announcement can end on."])

    with database().tx(request_id=request_id(request)) as tx:
        announcement_id = tx.insert("announcements.create", (
            body, payload.get("level") or "info",
            1 if payload.get("active", True) else 0,
            payload.get("starts_at"), ends_at,
            principal.person_id, clock.now_iso()))
        tx.audit("announcement.update",
                 f"{principal.display_name} published an announcement.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 entity_type="announcement", entity_id=announcement_id)
    return {"ok": True, "id": announcement_id}


@app.post("/admin/announcements/{announcement_id}/active")
def set_announcement_active(announcement_id: int, request: Request,
                            payload: dict = Body(...),
                            principal: auth.Principal = guard(
                                "admin.announcements.set_active", "*",
                                school_rule="any", writes=True)):
    """Take a banner down, or put one back up.

    Not a delete. An announcement is a thing that was shown to everybody at the
    convention, and the audit log refers to it by id; removing the row would
    leave entries pointing at nothing. Taking it down is the action people
    actually want, and it is reversible -- which matters at 8am on a Saturday
    when somebody pulls the wrong one.
    """
    active = 1 if payload.get("active") else 0
    with database().tx(request_id=request_id(request)) as tx:
        changed = tx.run("announcements.set_active", (active, announcement_id))
        if not changed:
            raise auth.ForbiddenError("no such announcement")
        tx.audit("announcement.update",
                 f"{principal.display_name} "
                 f"{'put an announcement back up' if active else 'took an announcement down'}.",
                 actor_person_id=principal.person_id,
                 impersonator_person_id=principal.impersonator_person_id,
                 entity_type="announcement", entity_id=announcement_id)
    return {"ok": True, "active": bool(active)}


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


@app.get("/admin/board")
def list_board(principal: auth.Principal = guard("admin.board.list", "*",
                                                 school_rule="any")):
    """Everyone who holds a role beyond delegate or chapter leader.

    This is the list a president needs when a chair changes in October: who has
    what, in one place, without knowing which chapter each person is filed
    under.
    """
    with database().read() as tx:
        return {"people": [dict(r) for r in tx.all("admin.board_members")]}


@app.patch("/admin/people/{person_id}/name")
def rename_person(person_id: int, request: Request, payload: dict = Body(...),
                  principal: auth.Principal = guard("admin.people.rename", "*",
                                                    school_rule="any",
                                                    writes=True)):
    """Correct a board member's name or title.

    A sponsor can already do this for their own chapter. This is the same
    action for the people who belong to no chapter -- and for the ones whose
    name was typed by somebody else at provisioning time.
    """
    first = (payload.get("first_name") or "").strip()
    last = (payload.get("last_name") or "").strip()
    if not first or not last:
        raise catalog.ValidationError(["A first and last name are both needed."])

    with database().tx(request_id=request_id(request)) as tx:
        person = tx.one("people.get", (person_id,))
        if person is None:
            raise auth.ForbiddenError("no such person")

        before = f"{person['first_name']} {person['last_name']}"
        # `board_title`, not `adult_type_other`: almost everybody on the board
        # is a delegate, and adult_type_other is an adult-only column that
        # means something else entirely. See migration 011.
        title = payload.get("board_title")
        title = title.strip() if isinstance(title, str) else person["board_title"]

        tx.run("people.rename", (
            first, (payload.get("middle_name") or "").strip() or None, last,
            title or None, clock.now_iso(), person_id))

        after = f"{first} {last}"
        tx.audit("person.update",
                 f"{principal.display_name} renamed {before} to {after}."
                 if before != after
                 else f"{principal.display_name} updated {after}'s title.",
                 school_id=person["school_id"],
                 entity_type="person", entity_id=person_id,
                 changed_fields=["first_name", "middle_name", "last_name",
                                 "board_title"])
    return {"ok": True, "name": after}


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

@app.post("/sponsor/packet.pdf")
def packet_pdf(request: Request, payload: dict = Body(...),
               principal: auth.Principal = guard("sponsor.packet.pdf",
                                                 "sponsor", "registration")):
    """The packet as a PDF, rendered from the same HTML the print view serves.

    SLOW ON PURPOSE, AND SAY SO. WeasyPrint needs Pango and Cairo, which live
    on a second, heavier Modal image that only cold-starts when somebody asks
    for a PDF -- thirty seconds or more the first time. Putting it on the web
    image would make every delegate on a phone pay for it.

    The print view is the fast path and produces the same document. This is for
    somebody who wants a file to keep or to email.

    Codes come in the body, as they do for the HTML version, because a stored
    code is an HMAC and cannot be read back. Without them every sheet prints
    blocks -- which is what this path did before it had a caller.
    """
    raw = payload.get("codes") or []
    if not isinstance(raw, list):
        raise catalog.ValidationError(["That is not a list of codes."])
    if len(raw) > 200:
        raise catalog.ValidationError(["That is too many sheets at once."])

    codes: dict[int, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise catalog.ValidationError(["That is not a list of codes."])
        try:
            codes[int(entry.get("person_id"))] = str(entry.get("code") or "")
        except (TypeError, ValueError):
            raise catalog.ValidationError(["That is not a list of codes."])

    with database().read() as tx:
        school = _school_of(tx, principal, payload.get("school_id"))
        for person_id in codes:
            auth.require_person_in_scope(tx, principal, person_id)

    try:
        import modal

        renderer = modal.Function.from_name("cajcl-2027", "render_pdf")
        pdf = renderer.remote(document="packet", school_id=school["id"],
                              codes={str(k): v for k, v in codes.items()})
    except Exception as error:
        # Never take the page down for this. The print view is right there and
        # produces the same document.
        raise catalog.ValidationError([
            f"The PDF renderer did not answer ({error}). Use Print instead — "
            "it is the same document."])

    name = school["name"].replace(" ", "-").lower()
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition":
                             f'attachment; filename="packet-{name}.pdf"'})


@app.post("/sponsor/packet", response_class=HTMLResponse)
def packet_with_codes(request: Request, payload: dict = Body(...),
                      principal: auth.Principal = guard("sponsor.packet.print",
                                                        "sponsor", "registration")):
    """The packet, printed with codes that were minted seconds ago.

    THE ONLY WAY TO PRODUCE A SHEET SOMEBODY CAN USE. Codes are stored as an
    HMAC and cannot be read back, so the GET above prints blocks -- correct for
    a preview, useless for the packet a sponsor is about to hand out. Whoever
    just minted a code holds the only readable copy, and posts it back here to
    have it typeset.

    A POST, not a GET, for one reason: the codes are in the BODY. In a query
    string they would be in the browser's history, in the referrer of anything
    the printed page links to, and in every access log between here and Modal.

    Nothing is stored. The codes are read, rendered, and dropped; this endpoint
    does not open a write transaction and writes no audit entry, because
    printing is not a change to anything.
    """
    # A LIST, not a map keyed by id. The printed stack comes out in the order
    # given, which is the order the sponsor is holding on screen, and a JSON
    # object would not have preserved it.
    raw = payload.get("codes") or []
    if not isinstance(raw, list) or not raw:
        raise catalog.ValidationError(["There are no codes to print."])
    if len(raw) > 200:
        raise catalog.ValidationError(["That is too many sheets at once."])

    order: list[int] = []
    codes: dict[int, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise catalog.ValidationError(["That is not a list of codes."])
        try:
            person_id = int(entry.get("person_id"))
        except (TypeError, ValueError):
            raise catalog.ValidationError(["That is not a list of codes."])
        order.append(person_id)
        codes[person_id] = str(entry.get("code") or "")

    with database().read() as tx:
        # The school first. A sponsor naming somebody else's chapter is refused
        # here, before any of the ids below are looked at.
        school = _school_of(tx, principal, payload.get("school_id"))
        for person_id in order:
            auth.require_person_in_scope(tx, principal, person_id)
        return HTMLResponse(printing.render_packet(
            tx, school, only_people=order, codes=codes))


@app.get("/sponsor/packet", response_class=HTMLResponse)
def packet(school_id: int | None = Query(default=None),
           person_id: int | None = Query(default=None),
           person_ids: str | None = Query(default=None),
           principal: auth.Principal = guard("sponsor.packet", "sponsor",
                                             "registration")):
    """The printable packet, one attendee's sheet, or a chosen few.

    `person_ids` is the reprint after a selective code reissue: exactly the
    sheets that just changed, and nothing else. Printing the whole packet to
    hand out three new sheets is how a sponsor ends up with two versions of the
    same page in circulation.
    """
    chosen: list[int] | None = None
    if person_ids:
        try:
            chosen = [int(part) for part in person_ids.split(",") if part.strip()]
        except ValueError:
            raise catalog.ValidationError(["That is not a list of people."])
        if not chosen or len(chosen) > 200:
            raise catalog.ValidationError(["Choose between one and 200 people."])

    with database().read() as tx:
        school = _school_of(tx, principal, school_id)
        for one in ([person_id] if person_id is not None else []) + (chosen or []):
            auth.require_person_in_scope(tx, principal, one)
        return HTMLResponse(printing.render_packet(
            tx, school, only_person=person_id, only_people=chosen))


@app.get("/admin/academics/item/{item_id}/sheet", response_class=HTMLResponse)
def academics_sheet(item_id: int,
                    principal: auth.Principal = guard("admin.academics.sheet",
                                                      "academics", "awards",
                                                      school_rule="any")):
    """A proctor's sign-in sheet for one item. Printed and carried into a room."""
    with database().read() as tx:
        item = tx.one("academics.item", (item_id,))
        if item is None:
            raise auth.ForbiddenError("no such item")
        people = [dict(r) for r in tx.all("academics.item_people", (item_id,))]
        return HTMLResponse(printing.render_signin_sheet(tx, dict(item), people))


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
