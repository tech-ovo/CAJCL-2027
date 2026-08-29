/* ui.js — small helpers for building DOM.
 *
 * No framework and no build step. The whole frontend is plain ES modules served
 * by GitHub Pages, which means a future commissioner can open a file, change a
 * line, and see the result without installing anything. That is worth more here
 * than any framework's conveniences.
 *
 * Everything below builds real elements with real text nodes, so nothing on
 * this site interpolates user data into HTML. There is no innerHTML anywhere
 * outside renderMarkdown, which escapes first.
 */

/** Create an element. Attributes starting with `on` become listeners. */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "class") {
      node.className = value;
    } else if (key === "dataset") {
      Object.assign(node.dataset, value);
    } else if (value === true) {
      node.setAttribute(key, "");
    } else {
      node.setAttribute(key, String(value));
    }
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

/**
 * Append children to an existing node. USE THIS, NEVER `node.append(...)`.
 *
 * The DOM's own `append` stringifies whatever it is given, so a conditional
 * child written the ordinary way --
 *
 *     host.append(error ? errorSummary(error) : null, field({...}))
 *
 * -- puts the literal word "null" on the page when there is no error. It is a
 * text node, so it survives every review that looks at markup, and it appeared
 * above roughly half the headings on this site before anyone noticed.
 *
 * `el()` has always filtered its children through the same helper this uses.
 * The rule is enforced by backend/tests/test_frontend.py rather than left to
 * memory.
 */
export function add(node, ...children) {
  append(node, children);
  return node;
}

export function clear(node) {
  while (node.firstChild) node.firstChild.remove();
  return node;
}

/* --------------------------------------------------------------------------
 * Formatting
 * ----------------------------------------------------------------------- */

export function money(cents) {
  const value = (cents || 0) / 100;
  const text = value.toLocaleString("en-US", { style: "currency", currency: "USD" });
  return text;
}

/** Render a stored UTC instant in California time, which is the only time
 *  zone this convention has ever cared about. */
export function localDate(iso, { withTime = false } = {}) {
  if (!iso) return "";

  /* A BARE DATE IS A CALENDAR DATE, NOT AN INSTANT.
   *
   * `received_on` is stored as "2027-01-12" — the day somebody wrote on a
   * cheque, with no time and no time zone. `new Date("2027-01-12")` reads it
   * as UTC midnight, which in California is four o'clock the PREVIOUS
   * afternoon, so every cheque was logged a day early. Rendered here from its
   * own parts, it stays the day it was written.
   */
  const calendarDay = /^\d{4}-\d{2}-\d{2}$/.test(iso);
  const date = calendarDay
    ? new Date(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1,
               Number(iso.slice(8, 10)))
    : new Date(iso);
  if (Number.isNaN(date.getTime())) return "";

  const options = { year: "numeric", month: "long", day: "numeric" };
  // A calendar day has no zone to convert into. Everything else is a real
  // instant and is shown in California time, because that is where the
  // convention is and where every deadline falls.
  if (!calendarDay) options.timeZone = "America/Los_Angeles";
  if (withTime && !calendarDay) {
    options.hour = "numeric";
    options.minute = "2-digit";
  }
  return date.toLocaleString("en-US", options);
}

/**
 * The number printed beside a name or a chapter.
 *
 * `№` was unreadable at the size the tabula uses it -- at 11px it is a grey
 * smudge, and half the people who saw it did not know what it was. `#` is the
 * sign everyone already reads as "number".
 */
export function personNumber(id) {
  const text = (id === null || id === undefined) ? "" : String(id);
  return `#${text.padStart(4, "0")}`;
}

export function fullName(person) {
  return [person.first_name, person.middle_name, person.last_name, person.suffix]
    .filter(Boolean).join(" ");
}

/* --------------------------------------------------------------------------
 * The tabula — the site's signature element.
 *
 * Used wherever the site identifies a person, a chapter, or an entry. There is
 * deliberately no second signature device, so this is the only such helper.
 * ----------------------------------------------------------------------- */

export function tabula({ label, name, left, right }) {
  return el("div", { class: "tabula" },
    el("p", { class: "label" }, label),
    el("p", { class: "tabula__name" }, name),
    (left || right) && el("div", { class: "tabula__row" },
      left ? el("span", { class: "tabula__code" }, left) : el("span"),
      right ? el("span", { class: "tabula__id" }, right) : null
    )
  );
}

/* --------------------------------------------------------------------------
 * Forms
 * ----------------------------------------------------------------------- */

/**
 * A labelled field. Help text sits between the label and the input, so a person
 * reads the guidance before the field rather than after failing it.
 */
export function field({ id, label, help, required, error, warning, control, wide }) {
  const describedBy = [];
  if (help) describedBy.push(`${id}-help`);
  if (error) describedBy.push(`${id}-error`);

  if (control) {
    control.id = id;
    if (describedBy.length) control.setAttribute("aria-describedby", describedBy.join(" "));
    if (error) control.setAttribute("aria-invalid", "true");
    if (required) control.required = true;
  }

  return el("div", { class: wide ? "field field--wide" : "field" },
    el("label", { for: id }, label,
      required ? el("span", { class: "field__required" }, "required") : null),
    help ? el("p", { class: "field__help", id: `${id}-help` }, help) : null,
    control,
    error ? el("p", { class: "field__error", id: `${id}-error` }, error) : null,
    warning ? el("p", { class: "field__warning" }, warning) : null,
  );
}

export function input(attrs = {}) { return el("input", { type: "text", ...attrs }); }

export function select(options, attrs = {}) {
  return el("select", attrs, ...options.map(([value, text, selected]) =>
    el("option", { value, selected: selected || null }, text)));
}

/** Buttons carry active, specific labels: "Add 28 delegates", not "Submit". */
/**
 * A button. If its `onclick` returns a promise, the button handles the wait.
 *
 * EVERY BUTTON THAT TALKS TO THE SERVER MUST BE IDEMPOTENT OR DISABLED, and
 * this makes the second one automatic. While the promise is outstanding the
 * button is disabled, keeps its width, and shows a spinner in place of its
 * label; a second click cannot land at all. It comes back by itself whether
 * the promise resolves or rejects.
 *
 * The alternative people actually do — replacing the screen with a loading
 * bar — is worse than doing nothing: the thing you just pressed vanishes, so
 * you cannot tell whether the press registered, and the page you were reading
 * goes with it.
 *
 * The width is frozen before the label is swapped. Without that, "Record
 * payment" becomes a spinner and the button collapses to 3rem, moving every
 * button beside it while somebody is still looking at where they clicked.
 */
export function button(text, { variant = "", onclick, ...attrs } = {}) {
  const node = el("button",
    { type: "button", class: `btn ${variant}`.trim(), ...attrs }, text);

  if (typeof onclick === "function") {
    node.onclick = async (event) => {
      const result = onclick(event);
      if (!result || typeof result.then !== "function") return result;

      const width = node.getBoundingClientRect().width;
      if (width) node.style.minWidth = `${Math.ceil(width)}px`;
      node.disabled = true;
      node.setAttribute("aria-busy", "true");
      const label = Array.from(node.childNodes);
      clear(node);
      add(node, el("span", { class: "btn__spinner", "aria-hidden": "true" }),
                el("span", { class: "visually-hidden" }, "Working"));
      try {
        return await result;
      } finally {
        clear(node);
        add(node, ...label);
        node.removeAttribute("aria-busy");
        node.disabled = false;
        node.style.minWidth = "";
      }
    };
  }
  return node;
}

/* --------------------------------------------------------------------------
 * Feedback
 * ----------------------------------------------------------------------- */

/**
 * A summary of blocking errors, announced politely and focusable.
 *
 * ONE ERROR GETS NO HEADING AND NO BULLET. "There is one thing to fix",
 * followed by a single bullet, is two lines of packaging around one sentence —
 * and on the sign-in form, where the only thing that can ever be wrong is the
 * code, the heading was pure ceremony. A list earns its shape when there is
 * more than one thing in it.
 */
export function errorSummary(errors) {
  const list = (errors || []).filter(Boolean);
  if (!list.length) return null;

  const node = el("div", { class: "form-errors", role: "alert", tabindex: "-1" });
  if (list.length === 1) {
    add(node, el("p", { style: "margin:0" }, list[0]));
  } else {
    add(node,
      el("h2", {}, `There are ${list.length} things to fix`),
      el("ul", {}, ...list.map((message) => el("li", {}, message))));
  }
  requestAnimationFrame(() => node.focus());
  return node;
}

export function emptyState(heading, message, action) {
  return el("div", { class: "empty" },
    el("h3", {}, heading),
    el("p", {}, message),
    action || null);
}

/** A designed loading state shaped like the thing being loaded. */
export function loadingRows(count = 5, what = "Loading") {
  return el("div", { class: "loading-rows", "aria-hidden": "true" },
    ...Array.from({ length: count }, () => el("div", {}, what)));
}

/* --------------------------------------------------------------------------
 * A very small Markdown subset, matching the one the printed documents use.
 * Escapes first, then allows bold and lists. Deliberately not a library.
 * ----------------------------------------------------------------------- */

export function renderMarkdown(text) {
  const wrap = el("div", { class: "prose" });
  let list = null;

  for (const raw of String(text || "").split("\n")) {
    const line = raw.trim();
    if (line.startsWith("- ") || line.startsWith("* ")) {
      if (!list) { list = el("ul"); wrap.append(list); }
      list.append(el("li", {}, ...inline(line.slice(2))));
      continue;
    }
    list = null;
    if (line) wrap.append(el("p", {}, ...inline(line)));
  }
  return wrap;
}

function inline(text) {
  const parts = [];
  let index = 0;
  const pattern = /\*\*(.+?)\*\*/g;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > index) parts.push(text.slice(index, match.index));
    parts.push(el("strong", {}, match[1]));
    index = match.index + match[0].length;
  }
  if (index < text.length) parts.push(text.slice(index));
  return parts;
}

/* --------------------------------------------------------------------------
 * Tables
 * ----------------------------------------------------------------------- */

/**
 * A sortable, responsive table. `columns` is
 *   { key, label, num?, render?, sortable? }
 * Every cell carries data-label so the mobile row-group layout can name it.
 */
export function table(columns, rows, { sort, onSort, rowClass, caption } = {}) {
  const head = el("tr", {}, ...columns.map((column) => {
    const th = el("th", { class: column.num ? "num" : null, scope: "col" });
    if (column.sortable && onSort) {
      const active = sort && sort.key === column.key;
      th.setAttribute("aria-sort", active
        ? (sort.direction === "asc" ? "ascending" : "descending")
        : "none");
      th.append(el("button", {
        class: "table__sort", type: "button",
        onclick: () => onSort(column.key),
      }, column.label));
    } else {
      th.append(document.createTextNode(column.label));
    }
    return th;
  }));

  const body = el("tbody", {}, ...rows.map((row) =>
    el("tr", { class: rowClass ? rowClass(row) : null },
      ...columns.map((column) => el("td", {
        class: column.num ? "num" : null,
        "data-label": column.label,
      }, column.render ? column.render(row) : row[column.key]))
    )));

  return el("div", { class: "table-wrap" },
    el("table", { class: "table table--responsive" },
      caption ? el("caption", { class: "visually-hidden" }, caption) : null,
      el("thead", {}, head), body));
}

/* --------------------------------------------------------------------------
 * Leaving a page with unsaved work
 * ----------------------------------------------------------------------- */

/**
 * Warn before abandoning unsaved changes. Returns a function that stops it.
 *
 * `isDirty()` is called at the moment of leaving, not when this is set up, so
 * the caller can keep its own state however it likes.
 *
 * TWO WAYS TO LEAVE, TWO MECHANISMS.
 *   Closing the tab or reloading is `beforeunload`, where the browser shows its
 *   own wording and ignores anything passed to it.
 *
 *   Following a link inside the site is a click on an anchor, and it is caught
 *   in the CAPTURE phase — before the hash changes. A `hashchange` listener
 *   would be too late: by then the router has rebuilt the page and the answers
 *   are already gone. Hash changes cannot be cancelled, which is why this hooks
 *   the click instead.
 */
/* Every page currently guarding unsaved work.
 *
 * `guardUnsaved` catches the two ways a browser leaves a page: closing it, and
 * following a link. Sign-out is neither -- it is a button that throws the
 * token away and re-renders -- so it walked straight past the guard, and the
 * warning only appeared on the NEXT sign-in, about work that was already gone.
 *
 * Anything that navigates by means of its own can ask here first.
 */
const guards = new Set();

/* Forget every guard. The router calls this as it swaps pages, so a page that
 * left one registered -- most do, since `release()` is only returned, never
 * required -- does not answer for a page that is no longer on screen. */
export function forgetGuards() {
  guards.clear();
}

export function unsavedWork() {
  for (const isDirty of guards) {
    try {
      if (isDirty()) return true;
    } catch (error) { /* a page mid-teardown is not dirty */ }
  }
  return false;
}

export function guardUnsaved(isDirty, what = "unsaved changes") {
  const onBeforeUnload = (event) => {
    if (!isDirty()) return;
    event.preventDefault();
    event.returnValue = "";
  };

  const onClick = (event) => {
    if (!isDirty() || event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    const anchor = event.target.closest && event.target.closest('a[href^="#"]');
    if (!anchor || anchor.getAttribute("href") === location.hash) return;

    // THE ONE NATIVE DIALOG LEFT, and it has to be. Everything else on the
    // site uses `check()` below, which looks like the site rather than like
    // the browser -- but `check()` returns a promise, and this handler must
    // decide before it returns whether to cancel the click. By the time a
    // promise resolves, the navigation has already happened.
    const ok = window.confirm(
      `You have ${what}.\n\nLeave this page and lose them?`);
    if (ok) { release(); return; }
    event.preventDefault();
    event.stopPropagation();
  };

  function release() {
    guards.delete(isDirty);
    window.removeEventListener("beforeunload", onBeforeUnload);
    document.removeEventListener("click", onClick, true);
  }

  guards.add(isDirty);
  window.addEventListener("beforeunload", onBeforeUnload);
  document.addEventListener("click", onClick, true);
  return release;
}

/* --------------------------------------------------------------------------
 * A modal question
 * ----------------------------------------------------------------------- */

/**
 * The scaffolding every dialog here shares: a <dialog> holding a
 * `method="dialog"` form, removed from the document when it closes.
 *
 * `showModal()` traps focus, closes on Escape, restores focus to whatever
 * opened it, and paints a backdrop — none of which is worth reimplementing,
 * and all of which native `alert()` and `confirm()` also do. What those two
 * cannot do is look like this site. Projected in a room, a browser dialog
 * reads as something having gone wrong.
 *
 * `build` receives (form, close) and returns the value the promise resolves
 * to, read at close time rather than returned directly, because the dialog may
 * also be dismissed with Escape or the backdrop.
 */
function dialogue(build) {
  return new Promise((resolve) => {
    const form = el("form", { method: "dialog" });
    const dialog = el("dialog", { class: "dialog" }, form);
    const read = build(form, () => dialog.close());

    dialog.addEventListener("close", () => {
      dialog.remove();
      resolve(read());
    });

    add(document.body, dialog);
    dialog.showModal();
    const first = form.querySelector("input, textarea, button");
    if (first) first.focus();
  });
}

/**
 * Yes or no. Resolves true only if the confirming button was pressed.
 *
 * Replaces `window.confirm`. Escape, the backdrop and Cancel all resolve
 * false, so the safe answer is the one you get by doing nothing — which is the
 * opposite of a native confirm's OK-focused default.
 *
 * NOT usable where the answer must be known synchronously. `guardUnsaved` has
 * to decide inside a click handler whether to cancel the navigation, and a
 * promise resolves a turn too late; it keeps `window.confirm` deliberately.
 */
export function check({ title, body, confirmLabel = "Continue",
                        cancelLabel = "Cancel", danger = false } = {}) {
  return dialogue((form, close) => {
    let yes = false;
    add(form,
      el("h2", {}, title),
      ...(Array.isArray(body) ? body : [body]).filter(Boolean)
        .map((line) => (typeof line === "string" ? el("p", {}, line) : line)),
      el("div", { class: "btn-row" },
        button(confirmLabel, {
          variant: danger ? "btn--danger" : "btn--primary",
          type: "submit",
          onclick: () => { yes = true; },
        }),
        button(cancelLabel, { variant: "btn--quiet", onclick: () => close() })));
    return () => yes;
  });
}

/**
 * Say something and wait for it to be acknowledged. Replaces `window.alert`.
 *
 * Used for the failures a person must see before carrying on — a save that did
 * not happen, a pop-up the browser blocked. Anything a page can show inline
 * should be shown inline instead; this is for the moment when there is no
 * inline place left to put it.
 */
export function tell({ title = "That did not work", body } = {}) {
  return dialogue((form, close) => {
    add(form,
      el("h2", {}, title),
      ...(Array.isArray(body) ? body : [body]).filter(Boolean)
        .map((line) => (typeof line === "string" ? el("p", {}, line) : line)),
      el("div", { class: "btn-row" },
        button("Close", { variant: "btn--primary", type: "submit" })));
    return () => undefined;
  });
}


/**
 * Ask for something in a real dialog. Resolves to the value, or null.
 *
 * WHY NOT window.prompt
 *   `prompt()` renders a plain text field with no way to mask it, so an admin
 *   re-entering their own access code typed a live credential in the clear —
 *   visible over a shoulder, offered to the browser's autofill store, and kept
 *   in its history. It also cannot be styled, so it looked like a browser
 *   error rather than part of the site.
 *
 *   `<dialog>` with showModal() traps focus, closes on Escape, restores focus
 *   to whatever opened it, and renders a backdrop, all without a line of
 *   JavaScript to manage any of it.
 *
 * `secret: true` masks the field and turns off autocomplete, so nothing about
 * the value is remembered by the browser.
 */
export function ask({ title, body, label, confirmLabel = "Continue",
                      secret = false, danger = false } = {}) {
  return dialogue((form, close) => {
    const input = el("input", {
      type: secret ? "password" : "text",
      class: secret ? "mono" : null,
      id: "ask-value",
      autocomplete: secret ? "off" : null,
      autocapitalize: secret ? "characters" : null,
      spellcheck: "false",
    });

    let answer = null;
    add(form,
      el("h2", {}, title),
      body ? el("p", {}, body) : null,
      field({ id: "ask-value", label, control: input, wide: true }),
      el("div", { class: "btn-row" },
        button(confirmLabel, {
          variant: danger ? "btn--danger" : "btn--primary",
          type: "submit",
          onclick: () => { answer = input.value.trim(); },
        }),
        button("Cancel", {
          variant: "btn--quiet",
          onclick: () => { answer = null; close(); },
        })));
    return () => answer || null;
  });
}

/* --------------------------------------------------------------------------
 * A draft kept in the browser
 * ----------------------------------------------------------------------- */

/**
 * Remember unsaved form state on this device. A safety net, never the record.
 *
 * WHAT THIS IS FOR
 *   A delegate fills in half an activity sheet on a school Chromebook, the
 *   lesson ends, and the tab closes. The server has nothing, because they had
 *   not pressed save. This gets their answers back.
 *
 * WHAT IT IS NOT
 *   Storage. It is per-browser and per-device, invisible to the sponsor, to
 *   the chairs, and to every report. The saved sheet on the server is the only
 *   thing that counts, and the draft is cleared the moment one exists.
 *
 * Every call is wrapped: localStorage throws outright in a private window, in
 * an iframe with site data blocked, and on a browser with storage disabled.
 * None of those should take a form down, so a failure here does nothing at all.
 */
export function draft(key) {
  const name = `cajcl.draft.${key}`;

  return {
    save(value) {
      try {
        localStorage.setItem(name, JSON.stringify(
          { at: new Date().toISOString(), value }));
      } catch (ignored) { /* a draft is a nicety; never fail a form over it */ }
    },

    read() {
      try {
        const raw = localStorage.getItem(name);
        if (!raw) return null;
        const held = JSON.parse(raw);
        // A draft older than the convention is noise, not help.
        const age = Date.now() - new Date(held.at).getTime();
        if (!Number.isFinite(age) || age > 1000 * 60 * 60 * 24 * 30) {
          this.clear();
          return null;
        }
        return held;
      } catch (ignored) {
        return null;
      }
    },

    clear() {
      try { localStorage.removeItem(name); } catch (ignored) { /* nothing */ }
    },
  };
}
