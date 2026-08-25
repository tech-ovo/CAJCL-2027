/* main.js — the shell: routing, session, banners, and sign-out.
 *
 * MAGIC LINKS
 *   The printed sheet carries a QR pointing at #/enter/DEL-K7M2N-9PQ4Z. The
 *   code travels in the URL FRAGMENT, never the query string, so it is never
 *   sent to a server, never lands in an access log, and never leaks through a
 *   Referer header. We read location.hash, exchange it for a session token, and
 *   immediately call history.replaceState() to strip it.
 *
 * SHARED DEVICES
 *   Sign-out is visible on every page, not buried in a menu, and it revokes the
 *   session server-side rather than only clearing localStorage.
 */

import * as api from "./api.js";
import { add, el, clear, button } from "./ui.js";
import { checkSymbolOk } from "./codes.js";

import { welcomePage } from "./pages/welcome.js";
import { signInPage } from "./pages/signin.js";
import { rosterPage } from "./pages/roster.js";
import { importPage } from "./pages/import.js";
import { activitySheetPage } from "./pages/activity.js";
import { adultSheetPage } from "./pages/adult.js";
import { invoicePage } from "./pages/invoice.js";
import { dashboardPage } from "./pages/dashboard.js";
import { adminPage } from "./pages/admin.js";
import { auditPage } from "./pages/audit.js";
import { academicsPage } from "./pages/academics.js";
import { overviewPage } from "./pages/overview.js";
import { accountPage } from "./pages/account.js";

export const state = {
  me: null,          // /auth/me, or null when signed out
  convention: {},    // public settings
  demoMode: false,
};

const ROUTES = [
  [/^\/?$/,                      welcomePage,       { public: true }],
  [/^\/enter\/(.+)$/,            magicLink,         { public: true }],
  [/^\/sign-in$/,                signInPage,        { public: true }],
  [/^\/account$/,                accountPage,       {}],
  [/^\/roster$/,                 rosterPage,        { scope: "sponsor" }],
  // A chair opening one chapter's roster. Same page, same endpoint -- the
  // server already accepts ?school_id for an administrative scope and refuses
  // it for everyone else, so this adds a route and no new authority.
  [/^\/roster\/(\d+)$/,          rosterPage,        { scope: "registration" }],
  [/^\/roster\/import$/,         importPage,        { scope: "sponsor" }],
  [/^\/invoice$/,                invoicePage,       { scope: "sponsor" }],
  [/^\/activity-sheet$/,         activitySheetPage, { scope: "delegate" }],
  [/^\/adult-sheet$/,            adultSheetPage,    {}],
  [/^\/overview$/,               overviewPage,      { scope: "registration" }],
  [/^\/dashboard$/,              dashboardPage,     { scope: "registration" }],
  [/^\/entries$/,                academicsPage,     { scope: ["academics", "awards"] }],
  [/^\/admin$/,                  adminPage,         { scope: "*" }],
  [/^\/audit$/,                  auditPage,         { scope: "*" }],
];

const appNode = () => document.getElementById("app");

/* The welcome page's markup lives in index.html, not in JavaScript, so that a
 * visitor arriving while Modal is cold sees a finished page rather than a
 * spinner -- and so scripts/build_snapshot.py has one place to write the
 * numbers into.
 *
 * The router clears #app before every render, which would destroy it. So the
 * original children are lifted into a fragment once, at boot, before anything
 * has had a chance to clear them, and welcomePage appends a fresh clone.
 * index.html stays the single source of truth and nothing is duplicated in JS.
 */
let snapshotTemplate = null;

function captureSnapshot() {
  // COPIES, and leaves the markup on screen.
  //
  // This used to move the children into the fragment, which emptied #app the
  // instant this module ran -- so a visitor saw the finished welcome page
  // painted, then watched it vanish and be replaced by "Waking up the
  // server…". The page they already had was the one they wanted.
  //
  // Leaving it in place means the only thing that ever replaces it is the
  // router, synchronously, with a clone of the same markup.
  snapshotTemplate = document.createDocumentFragment();
  for (const child of Array.from(appNode().childNodes)) {
    add(snapshotTemplate, child.cloneNode(true));
  }
}

export function snapshotMarkup() {
  return snapshotTemplate ? snapshotTemplate.cloneNode(true) : null;
}

/* ------------------------------------------------------------------------ */

async function boot() {
  // Before anything can clear #app.
  captureSnapshot();

  api.setUnauthorizedHandler(() => {
    api.token.clear();
    state.me = null;
  });

  // The static snapshot in index.html is already on screen. Replace it quietly
  // once the API answers, and leave it alone if the API never does.
  loadPublicFacts();

  window.addEventListener("hashchange", route);
  await route();
}

async function loadPublicFacts() {
  try {
    const convention = await api.get("/public/convention");
    state.convention = convention;
    state.demoMode = !!convention.demo_mode;
    applySnapshot(convention);
  } catch (ignored) {
    /* The build-time snapshot stands. A visitor arriving at a cold site sees a
       complete page; they simply see slightly older numbers. */
  }
  renderBanners();
  loadAnnouncements();
}

export function applySnapshot(convention) {
  const set = (key, value) => {
    if (value === undefined || value === null || value === "") return;
    document.querySelectorAll(`[data-snapshot="${key}"]`)
      .forEach((node) => { node.textContent = value; });
  };
  set("theme_latin", convention["convention.theme_latin"]);
  set("theme_english", convention["convention.theme_english"]);
  set("theme_citation", convention["convention.theme_citation"]);
  set("masthead_line",
    `${convention["convention.ordinal"]} State Convention · ` +
    `${convention["convention.venue_name"]}`);
  set("heading",
    `The ${convention["convention.ordinal"]} California Junior Classical ` +
    `League State Convention`);
}

/* ------------------------------------------------------------------------ */

async function route() {
  const path = location.hash.replace(/^#/, "") || "/";

  for (const [pattern, page, options] of ROUTES) {
    const match = pattern.exec(path);
    if (!match) continue;

    if (!options.public) {
      await ensureSession();
      if (!state.me) { location.hash = "#/sign-in"; return; }
      // `scope` may be a list: some pages are open to more than one chair.
      // The server's guard already allows both; without this the route was
      // narrower than the endpoint, so an awards chair was refused a page the
      // API would happily have served them.
      const needed = [].concat(options.scope || []);
      if (needed.length && !needed.some(hasScope)) {
        renderNoAccess(needed.join(" or "));
        return;
      }
    } else if (api.token.get() && !state.me) {
      // No statusHost: this is a PUBLIC page and it is already readable. The
      // cold-start ladder clears whatever it is given before drawing itself,
      // so passing #app here blanked a finished welcome page to show a spinner
      // for a request the visitor did not ask for and does not need.
      await ensureSession({ quiet: true });
    }

    renderNav();
    renderBanners();
    clear(appNode());
    try {
      await page(appNode(), match.slice(1));
    } catch (error) {
      renderFailure(error);
    }
    return;
  }

  location.hash = "#/";
}

async function ensureSession({ quiet = false } = {}) {
  if (state.me || !api.token.get()) return;
  try {
    state.me = await api.get("/auth/me",
                             quiet ? {} : { statusHost: appNode() });
    state.demoMode = !!state.me.demo_mode;
  } catch (ignored) {
    state.me = null;
    api.token.clear();
  }
}

/**
 * Take up a session the server has just handed us, without asking who it is.
 *
 * `/auth/redeem` and `/auth/impersonate` both return the same body `/auth/me`
 * would, so calling it afterwards is a second round trip for an answer already
 * in hand. On a cold container that is two waits where the person can only see
 * the second one, and it happens at the single worst moment: the very first
 * thing anybody does on the site.
 *
 * `sessions` is the one field not in that body. Only the account page wants it
 * and that page fetches /auth/me for itself.
 */
/**
 * Where somebody lands after signing in.
 *
 * NOT the welcome page. They have just typed a code or scanned a QR, which is
 * an act with an intention behind it, and the welcome page answers none of
 * them. A delegate wants their form; a sponsor wants their roster.
 *
 * Whatever this returns has to be a page that person can actually open, or the
 * router bounces them straight back to the sign-in screen.
 */
export function landingFor(person) {
  if (!person) return "#/";
  const scopes = person.scopes || [];
  const can = (scope) => scopes.includes("*") || scopes.includes(scope);

  if (person.person_type === "delegate") return "#/activity-sheet";
  if (can("sponsor")) return "#/roster";
  if (person.person_type === "adult") return "#/adult-sheet";
  return "#/";
}

export function adopt(person) {
  state.me = person || null;
  state.demoMode = !!(person && person.demo_mode);
}

export function hasScope(scope) {
  if (!state.me) return false;
  const scopes = state.me.scopes || [];
  return scopes.includes("*") || scopes.includes(scope);
}

/* ------------------------------------------------------------------------ */

async function magicLink(host, [raw]) {
  const code = decodeURIComponent(raw);

  // Strip the credential from the address bar before anything else, so it does
  // not survive in history, a screenshot, or a shared tab.
  history.replaceState(null, "", location.pathname + location.search + "#/");

  add(host, el("p", { class: "label" }, "Signing you in"));

  if (!checkSymbolOk(code)) {
    add(host, el("div", { class: "waking waking--failed" },
      el("p", { class: "label label--ink" }, "That code did not scan cleanly"),
      el("p", {}, "Try scanning again, or type the code from your sheet."),
      el("a", { class: "btn", href: "#/sign-in" }, "Type it instead")));
    return;
  }

  try {
    const result = await api.post("/auth/redeem",
      { code, via_magic_link: true }, { statusHost: host });
    api.token.set(result.token);
    adopt(result.person);
    // A scanned QR is even more purposeful than a typed code: somebody has
    // their sheet in their hand.
    location.hash = landingFor(result.person);
    await route();
  } catch (error) {
    clear(host);
    add(host, el("div", { class: "waking waking--failed" },
      el("p", { class: "label label--ink" }, "That code did not work"),
      el("p", {}, error.message),
      el("a", { class: "btn", href: "#/sign-in" }, "Type your code instead")));
  }
}

/* ------------------------------------------------------------------------ */

function renderNav() {
  const nav = document.getElementById("nav");
  clear(nav);

  const link = (href, text) => {
    const a = el("a", { href }, text);
    if (location.hash === href) a.setAttribute("aria-current", "page");
    return a;
  };

  add(nav, link("#/", "Welcome"));

  if (state.me) {
    /* TWO GROUPS, AND THE ORDER IS THE POINT.
     *
     * First what this person has to DO -- their own registration, their
     * chapter's roster. Then, set apart, what they can do because of a role
     * they hold. A convention president is a delegate with an activity sheet
     * to fill in like everybody else, and running the two together made their
     * own form the seventh item in a row of eight.
     */
    if (state.me.person_type === "delegate") {
      add(nav, link("#/activity-sheet", "Registration"));
    } else if (state.me.person_type === "adult") {
      // NOT gated on scope. This used to be hidden from anyone holding `*`,
      // on the assumption that an administrator is not an attendee -- but a
      // sponsor with admin rights is very much attending, and their own form
      // sat there reading "Not yet" with no way to reach it.
      add(nav, link("#/adult-sheet", "Registration"));
    }
    if (hasScope("sponsor")) {
      add(nav, link("#/roster", "Roster"), link("#/invoice", "Invoice"));
    }

    const administrative = [];
    if (hasScope("registration")) {
      administrative.push(["#/overview", "Registration"],
                          ["#/dashboard", "Chapters"]);
    }
    if (hasScope("academics") || hasScope("awards")) {
      administrative.push(["#/entries", "Entries"]);
    }
    if (hasScope("*")) {
      administrative.push(["#/admin", "Settings"], ["#/audit", "Log"]);
    }
    if (administrative.length) {
      add(nav, el("span", { class: "nav__divider", "aria-hidden": "true" }));
      add(nav, ...administrative.map(([href, text]) => link(href, text)));
    }

    add(nav, el("span", { class: "nav__spacer" }));
    add(nav, link("#/account", state.me.first_name || "Account"));
    // Visible on every page. Not in a menu. Assume shared devices.
    add(nav, el("button", {
      class: "btn btn--small nav__signout", type: "button", onclick: signOut,
    }, "Sign out"));
  } else {
    add(nav, el("span", { class: "nav__spacer" }));
    add(nav, link("#/sign-in", "Sign in"));
  }
}

function signOut() {
  /* INSTANT, AND THE ORDER IS THE POINT.
   *
   * Forget the session here first, then leave. The server call is fired and
   * NOT awaited: on a cold container it took several seconds, during which
   * somebody who had just asked to be signed out was still looking at their
   * own roster on a shared computer.
   *
   * Nothing is lost by not waiting. The token is already gone from this
   * browser, so this device cannot use it either way. The request revokes it
   * server-side so no OTHER device can — and if it never arrives, the session
   * expires on its own and they can sign out again from the account page.
   *
   * `keepalive` is what makes that true: the browser finishes the request even
   * though the page has already moved on.
   */
  api.token.clear();
  api.adminToken.clear();
  state.me = null;
  location.hash = "#/";
  route();

  api.post("/auth/logout", {}, { keepalive: true })
     .catch(() => { /* the token is gone from this browser regardless */ });
}

export async function endImpersonation() {
  try { await api.post("/auth/impersonate/end", {}); } catch (ignored) { /* ignore */ }
  const admin = api.adminToken.get();
  api.adminToken.clear();
  if (admin) api.token.set(admin); else api.token.clear();
  state.me = null;
  location.hash = "#/dashboard";
  await route();
}

/* ------------------------------------------------------------------------ */

function renderBanners() {
  const host = document.getElementById("banners");
  clear(host);

  // The demonstration-data marker. The demo is projected in a room full of
  // teachers; nobody should have to wonder whether these are real children.
  //
  // The wording is narrower than it was, and deliberately. Real board members
  // now have real accounts here, so "every name is invented" became false the
  // moment scripts/add_board.py first ran. The promise worth making is the one
  // about minors, and it is still true: no delegate, parent, or chapter on this
  // site is a real person.
  if (state.demoMode) {
    add(host, el("div", { class: "banner banner--demo" },
      el("span", { class: "banner__label" }, "Demonstration data"),
      el("span", {}, "Every chapter, delegate, and parent on this site is " +
                     "invented. No real student appears anywhere.")));
  }

  const impersonation = state.me && state.me.impersonation;
  if (impersonation && impersonation.active) {
    add(host, el("div", { class: "banner banner--impersonating on-dark" },
      el("span", { class: "banner__label" }, "Viewing as another person"),
      el("span", {},
        `${impersonation.by} is viewing the site as ` +
        `${state.me.first_name} ${state.me.last_name}` +
        (impersonation.can_write ? " and can make changes." : ", read-only.")),
      button("Stop", { variant: "btn--small", onclick: endImpersonation })));
  }

  for (const announcement of state.announcements || []) {
    add(host, el("div", { class: `banner banner--${announcement.level}` },
      el("span", { class: "banner__label" },
        announcement.level === "critical" ? "Important" : "Notice"),
      el("span", {}, announcement.body_md)));
  }
}

async function loadAnnouncements() {
  // Two layers. The live value wins; the committed static file is what still
  // works with Modal completely down.
  let announcements = [];
  try {
    const body = await api.get("/public/announcements");
    announcements = body.announcements || [];
  } catch (ignored) {
    try {
      const response = await fetch("announcement.json", { cache: "no-cache" });
      if (response.ok) {
        const fallback = await response.json();
        if (fallback && fallback.active && fallback.body_md) announcements = [fallback];
      }
    } catch (ignored) { /* nothing to show */ }
  }
  state.announcements = announcements;
  renderBanners();
}

/* ------------------------------------------------------------------------ */

function renderNoAccess(scope) {
  clear(appNode());
  add(appNode(), 
    el("h1", {}, "You do not have access to that page"),
    el("p", {}, "Your account does not carry the permission this page needs " +
                `(${scope}). If you think it should, ask a convention president.`),
    el("a", { class: "btn", href: "#/" }, "Back to the welcome page"));
}

function renderFailure(error) {
  clear(appNode());
  add(appNode(), 
    el("div", { class: "waking waking--failed" },
      el("p", { class: "label label--ink" }, "This page could not load"),
      el("p", {}, error && error.message ? error.message
        : "Something went wrong. Nothing you entered has been lost."),
      el("div", { class: "btn-row" },
        button("Try again", { variant: "btn--primary", onclick: () => route() }),
        el("a", { class: "btn", href: "#/" }, "Back to the welcome page"))));
}

export { route };

boot();
