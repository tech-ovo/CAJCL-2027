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
export async function request(path, { method = "GET", body, statusHost, signal } = {}) {
  const headers = { "Accept": "application/json" };
  const auth = token.get();
  if (auth) headers["Authorization"] = `Bearer ${auth}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const controller = new AbortController();
  if (signal) signal.addEventListener("abort", () => controller.abort());

  const timers = statusHost ? startColdStartLadder(statusHost, controller) : null;

  try {
    const response = await fetch(base() + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });

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
export const post = (path, body, opts) => request(path, { ...opts, method: "POST", body });
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

/* ------------------------------------------------------------------------ */

function startColdStartLadder(host, controller) {
  const node = el("div", { class: "waking", role: "status", "aria-live": "polite" });
  let failed = false;

  const waking = setTimeout(() => {
    clear(host);
    add(node, 
      el("span", { class: "waking__dot", "aria-hidden": "true" }),
      el("span", {}, "Waking up the server…")
    );
    add(host, node);
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
