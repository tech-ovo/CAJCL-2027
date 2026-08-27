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
import { add, el, clear, button, unsavedWork,
         forgetGuards } from "./ui.js";
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
import { checkinPage } from "./pages/checkin.js";
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
  // A chair pasting for a chapter that cannot get its own spreadsheet in.
  // Same page and the same two endpoints, both of which already accept a
  // school_id from an administrative scope and refuse it from everyone else.
  [/^\/roster\/(\d+)\/import$/,   importPage,        { scope: "registration" }],
  [/^\/invoice$/,                invoicePage,       { scope: "sponsor" }],
  [/^\/activity-sheet$/,         activitySheetPage, { scope: "delegate" }],
  [/^\/adult-sheet$/,            adultSheetPage,    {}],
  [/^\/overview$/,               overviewPage,      { scope: "registration" }],
  [/^\/check-in$/,               checkinPage,       { scope: "registration" }],
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

/* WHICH NAVIGATION IS CURRENT.
 *
 * Every page fetches, so `route()` sits at an `await` for as long as the
 * network takes. Click one tab and then another quickly and there are two of
 * these in flight; whichever finishes LAST wins the screen, which is not
 * necessarily the one that was clicked last. The nav highlight comes from
 * `location.hash` and is right, so the symptom is a page showing one tab's
 * contents under another tab's highlight.
 *
 * Two things fix it, and both are needed. `stale()` stops an overtaken
 * navigation from writing anything more itself; and each navigation renders
 * into its OWN container, so a page that is still fetching when a newer one
 * arrives finds its container detached and paints into nothing.
 */
let navigation = 0;

async function route() {
  const ticket = ++navigation;
  const stale = () => ticket !== navigation;
  const path = location.hash.replace(/^#/, "") || "/";

  for (const [pattern, page, options] of ROUTES) {
    const match = pattern.exec(path);
    if (!match) continue;

    if (!options.public) {
      await ensureSession();
      if (stale()) return;
      if (!state.me) { location.hash = "#/sign-in"; return; }

      // THE NAV IS DRAWN FIRST, before anything can return early.
      //
      // It used to come after the scope check, so a signed-in person refused a
      // page was left looking at the SIGNED-OUT navigation — "Welcome" and
      // "Sign in" — with no way to reach anything and every reason to believe
      // signing in had failed.
      renderNav();

      // `scope` may be a list: some pages are open to more than one chair.
      // The server's guard already allows both; without this the route was
      // narrower than the endpoint, so an awards chair was refused a page the
      // API would happily have served them.
      const needed = [].concat(options.scope || []);
      if (needed.length && !needed.some(hasScope)) {
        renderBanners();
        renderNoAccess(needed.join(" or "));
        return;
      }
    } else if (api.token.get() && !state.me) {
      // No statusHost: this is a PUBLIC page and it is already readable. The
      // cold-start ladder clears whatever it is given before drawing itself,
      // so passing #app here blanked a finished welcome page to show a spinner
      // for a request the visitor did not ask for and does not need.
      await ensureSession({ quiet: true });
      if (stale()) return;
    }

    renderNav();
    renderBanners();

    // The page's own container, replaced wholesale on every navigation. A
    // slower page that resolves after this point is holding a node that is no
    // longer in the document, so its render is a no-op rather than a surprise.
    const host = el("div");
    clear(appNode());
    add(appNode(), host);
    // The page being replaced no longer answers for unsaved work. Its own
    // guard, if it had one, went with its DOM.
    forgetGuards();
    try {
      await page(host, match.slice(1));
    } catch (error) {
      if (!stale()) renderFailure(error);
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

  // Their own form comes first, whatever else they do here. Matched on the
  // ROLE rather than the scope: `*` says yes to everything, and would send a
  // delegate administrator to a sponsor's roster instead of their own sheet.
  const roles = person.roles || [];
  if (person.person_type === "delegate") return "#/activity-sheet";
  if (roles.includes("sponsor")) return "#/roster";
  if (person.person_type === "adult") return "#/adult-sheet";
  if (can("registration")) return "#/overview";
  return "#/";
}

/**
 * Does this person hold a role BY NAME, rather than a scope that covers it?
 *
 * `hasScope` answers "may they", and `*` says yes to everything — right for
 * authorisation, wrong for navigation. An administrator may open any roster;
 * that does not make their own chapter's roster their job. The sponsor still
 * runs the chapter, and a chair who needs to change something signs in as
 * them from Chapters, which the audit log records.
 */
export function holdsRole(role) {
  return !!state.me && (state.me.roles || []).includes(role);
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

/* The theme toggle.
 *
 * ONE ICON, NO LABEL, at the far end of the nav. It is the only control on the
 * site that changes nothing about the convention, so it sits apart from
 * everything that does and never competes for the eye.
 *
 * Three states, two of them reachable from here. With nothing stored the site
 * follows the operating system, which is what most people want and what they
 * get without ever finding this button. Pressing it writes an explicit choice
 * that then outlives their system switching over at sunset.
 *
 * The icon shows what you would GET, not what you are in: a moon means "go
 * dark". Showing the current state is the other convention and it is the one
 * people misread, because a button usually pictures its effect.
 */
function currentTheme() {
  const stored = safeRead();
  if (stored) return stored;
  return window.matchMedia
      && window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark" : "light";
}

function safeRead() {
  try {
    const value = localStorage.getItem("theme");
    return value === "dark" || value === "light" ? value : null;
  } catch (error) {
    return null;                         // private mode, or storage blocked
  }
}

function themeToggle() {
  const dark = currentTheme() === "dark";
  const label = dark ? "Switch to light mode" : "Switch to dark mode";

  const svg = (paths) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    node.setAttribute("viewBox", "0 0 24 24");
    node.setAttribute("width", "18");
    node.setAttribute("height", "18");
    node.setAttribute("fill", "none");
    node.setAttribute("stroke", "currentColor");
    node.setAttribute("stroke-width", "1.7");
    node.setAttribute("stroke-linecap", "round");
    node.setAttribute("aria-hidden", "true");
    for (const d of paths) {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      node.appendChild(path);
    }
    return node;
  };

  // A sun to go back to light; a crescent to go dark.
  const sun = ["M12 4.5v-2", "M12 21.5v-2", "M4.5 12h-2", "M21.5 12h-2",
               "M6.7 6.7 5.3 5.3", "M18.7 18.7l-1.4-1.4",
               "M6.7 17.3l-1.4 1.4", "M18.7 5.3l-1.4 1.4",
               "M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z"];
  const moon = ["M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"];

  const control = el("button", {
    type: "button",
    class: "nav__theme",
    "aria-label": label,
    title: label,
    onclick: () => {
      const next = currentTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem("theme", next);
      } catch (error) { /* the page still switches; it just will not persist */ }
      renderNav();
    },
  });
  control.appendChild(svg(dark ? sun : moon));
  return control;
}

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
    if (holdsRole("sponsor")) {
      add(nav, link("#/roster", "Roster"), link("#/invoice", "Invoice"));
    }

    const administrative = [];
    if (hasScope("registration")) {
      // "Overview", not "Registration". Almost every board member is a
      // STUDENT — a delegate at their own chapter who also holds a convention
      // role — so the personal link above already says Registration, and two
      // identical words in one nav bar is a coin toss. Its siblings are nouns
      // for what they show: Overview, Chapters, Check-in.
      administrative.push(["#/overview", "Overview"],
                          ["#/dashboard", "Chapters"],
                          ["#/check-in", "Check-in"]);
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

  // Last, on every page, signed in or not. It is the only control here that
  // has nothing to do with the convention.
  add(nav, themeToggle());
}

function signOut() {
  /* ASK FIRST IF THERE IS UNSAVED WORK.
   *
   * `guardUnsaved` catches a closing tab and a followed link. Sign-out is
   * neither — it throws the token away and re-renders — so a delegate could
   * sign out from the middle of a half-filled activity sheet, lose all of it,
   * and be told about it on their NEXT sign-in, when the draft was already
   * gone. The confirm is synchronous for the same reason it is in
   * `guardUnsaved`: this has to decide before it clears the token.
   */
  if (unsavedWork()
      && !window.confirm("You have unsaved answers.\n\n"
                         + "Sign out and lose them?")) {
    return;
  }

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
    el("p", {}, "You are signed in — this page just needs a permission your "
              + `account does not carry (${scope}).`),
    el("p", {}, "If it should, write to ",
      el("a", { href: "mailto:state@uhsjcl.org" }, "state@uhsjcl.org"),
      " and say which page you were trying to open. A convention president can "
      + "grant it, and you will not need a new code."),
    el("div", { class: "btn-row" },
      el("a", { class: "btn btn--primary", href: landingFor(state.me) },
        "Go to your own page"),
      el("a", { class: "btn", href: "#/" }, "Back to the welcome page")));
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
