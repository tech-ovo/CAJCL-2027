/* api.js — every request to Modal, and the cold-start state.
 *
 * COLD START IS A DESIGNED STATE, NOT A FAILURE.
 *   Modal scales to zero, which is what keeps the bill near zero. The first
 *   request after an idle period takes several seconds. The ladder is:
 *
 *     after 400ms   "Waking up the server..."
 *     after 8s      "This is taking longer than usual. Retrying..." + retry
 *     after 20s     a clear failure naming what to do instead
 *
 *   Never spin forever. Never show a blank page. The message is inline in the
 *   content region -- not a modal, not a full-page block.
 */

import { add, el, clear } from "./ui.js";

const WAKING_MS = 400;
const LATE_MS = 8000;
const FAILED_MS = 20000;

export class ApiError extends Error {
  constructor(message, { status, kind, errors } = {}) {
    super(message);
    this.status = status;
    this.kind = kind;
    this.errors = errors || [];
  }
}

function base() {
  return (window.CAJCL_CONFIG && window.CAJCL_CONFIG.apiBase) || "";
}

/* The session token lives in localStorage. The RAW CODE never does: it is
 * exchanged for a token once and then forgotten by the device. */
const TOKEN_KEY = "cajcl.session";

export const token = {
  get: () => {
    try { return localStorage.getItem(TOKEN_KEY); } catch (ignored) { return null; }
  },
  set: (value) => {
    try { localStorage.setItem(TOKEN_KEY, value); } catch (ignored) { /* private mode */ }
  },
  clear: () => {
    try { localStorage.removeItem(TOKEN_KEY); } catch (ignored) { /* private mode */ }
  },
};

/* An impersonation session is kept separately so ending it returns to the
 * admin's own session rather than signing them out entirely. */
const ADMIN_TOKEN_KEY = "cajcl.session.admin";

export const adminToken = {
  get: () => { try { return localStorage.getItem(ADMIN_TOKEN_KEY); } catch (ignored) { return null; } },
  set: (v) => { try { localStorage.setItem(ADMIN_TOKEN_KEY, v); } catch (ignored) {} },
  clear: () => { try { localStorage.removeItem(ADMIN_TOKEN_KEY); } catch (ignored) {} },
};

/* ------------------------------------------------------------------------ */

let onUnauthorized = null;
export function setUnauthorizedHandler(fn) { onUnauthorized = fn; }

/**
 * Make a request, showing the cold-start ladder in `statusHost` if one is given.
 */
export async function request(path,
    { method = "GET", body, statusHost, signal, keepalive = false } = {}) {
  const headers = { "Accept": "application/json" };
  const auth = token.get();
  if (auth) headers["Authorization"] = `Bearer ${auth}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const controller = new AbortController();
  if (signal) signal.addEventListener("abort", () => controller.abort());

  const timers = statusHost ? startColdStartLadder(statusHost, controller) : null;

  try {
    const response = await fetch(base() + path, {
      // `keepalive` lets a request finish after the page has moved on. Used by
      // sign-out, which must not make somebody wait on a shared computer.
      keepalive,
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });

    // ANY answer means the server is up, including a 403 or a 404. What the
    // next wait is about is loading, not waking.
    serverIsAwake = true;

    let payload = null;
    const text = await response.text();
    if (text) {
      try { payload = JSON.parse(text); } catch (ignored) { payload = { raw: text }; }
    }

    if (!response.ok) {
      if (response.status === 401 && onUnauthorized) onUnauthorized(payload);
      throw new ApiError(
        (payload && payload.error) || `Something went wrong (${response.status}).`,
        { status: response.status, kind: payload && payload.kind,
          errors: payload && payload.errors });
    }
    return payload;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error.name === "AbortError") {
      throw new ApiError(
        "The server did not answer. Check your connection and try again.",
        { kind: "timeout" });
    }
    throw new ApiError(
      "Could not reach the server. Check your connection and try again.",
      { kind: "network" });
  } finally {
    if (timers) timers.stop();
  }
}

export const get = (path, opts) => request(path, { ...opts, method: "GET" });
export const post = (path, body, opts) =>
  request(path, { ...opts, method: "POST", body });
export const put = (path, body, opts) => request(path, { ...opts, method: "PUT", body });
export const patch = (path, body, opts) => request(path, { ...opts, method: "PATCH", body });
export const del = (path, opts) => request(path, { ...opts, method: "DELETE" });

/* Text responses -- the print views, which are HTML rather than JSON. */
export async function getText(path) {
  const headers = {};
  const auth = token.get();
  if (auth) headers["Authorization"] = `Bearer ${auth}`;
  const response = await fetch(base() + path, { headers });
  if (!response.ok) throw new ApiError(`Could not load that page (${response.status}).`);
  return response.text();
}

/* The same, for a print view whose input will not fit in a URL.
 *
 * The packet is posted rather than fetched because the request body carries
 * access codes. In a query string they would sit in the browser's history, in
 * the referrer of anything the printed page links to, and in every access log
 * between here and Modal. */
export async function postText(path, body) {
  const headers = { "Content-Type": "application/json" };
  const auth = token.get();
  if (auth) headers["Authorization"] = `Bearer ${auth}`;
  const response = await fetch(base() + path,
                               { method: "POST", headers,
                                 body: JSON.stringify(body) });
  if (!response.ok) {
    throw new ApiError(`Could not build those sheets (${response.status}).`);
  }
  return response.text();
}

/* ------------------------------------------------------------------------ */

// Set the first time any request comes back. Modal sleeps when idle, so the
// FIRST wait really is the server waking up -- but every wait after that is
// just a page loading, and saying "Waking up the server" twice in ten seconds
// makes a working site look broken.
let serverIsAwake = false;

function startColdStartLadder(host, controller) {
  const node = el("div", { class: "waking", role: "status", "aria-live": "polite" });
  let failed = false;

  /* THE PAGE STAYS. The notice goes at the top of it.
   *
   * This used to `clear(host)` first, so a slow request wiped whatever the
   * person was reading and replaced it with a loading bar — and when the
   * request came back, the whole screen was rebuilt underneath them. On a page
   * they had already read, that is a flash of nothing for no reason; on one
   * with a half-finished form, it looked like the form had been thrown away.
   *
   * Nothing on this site should replace the screen to say it is busy. A button
   * that started something disables itself and shows a spinner (see `button`
   * in ui.js); a page that is still loading its FIRST content has nothing to
   * lose and shows this notice above an empty region. Either way the rule is
   * the same: never take away what somebody is already looking at.
   */
  const waking = setTimeout(() => {
    add(node,
      el("span", { class: "waking__dot", "aria-hidden": "true" }),
      el("span", {}, serverIsAwake ? "Loading…" : "Waking up the server…")
    );
    host.insertBefore(node, host.firstChild);
  }, WAKING_MS);

  const late = setTimeout(() => {
    node.className = "waking waking--late";
    clear(node);
    add(node, 
      el("span", { class: "waking__dot", "aria-hidden": "true" }),
      el("span", {}, "This is taking longer than usual. Still trying…")
    );
  }, LATE_MS);

  const giveUp = setTimeout(() => {
    failed = true;
    node.className = "waking waking--failed";
    clear(node);
    add(node, 
      el("p", { class: "label label--ink" }, "The server is not responding"),
      el("p", {},
        "Nothing you did caused this and nothing you entered has been lost. " +
        "Wait a minute and try again. If it keeps happening, ask your sponsor, " +
        "or write to "),
      el("p", {}, el("a", { href: "mailto:state@uhsjcl.org" }, "state@uhsjcl.org")),
      el("button", { class: "btn", onclick: () => location.reload() }, "Try again")
    );
    // Put it where it can be seen even if the page under it has content.
    if (!node.parentNode) host.insertBefore(node, host.firstChild);
    controller.abort();
  }, FAILED_MS);

  return {
    stop() {
      clearTimeout(waking); clearTimeout(late); clearTimeout(giveUp);
      // A failure message stays on screen; a successful one is swept away by
      // whatever renders next.
      if (!failed && node.parentNode) node.remove();
    },
  };
}
