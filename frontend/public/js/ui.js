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

export function fragment(...children) {
  const f = document.createDocumentFragment();
  append(f, children);
  return f;
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
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const options = {
    timeZone: "America/Los_Angeles",
    year: "numeric", month: "long", day: "numeric",
  };
  if (withTime) { options.hour = "numeric"; options.minute = "2-digit"; }
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
export function button(text, { variant = "", ...attrs } = {}) {
  return el("button", { type: "button", class: `btn ${variant}`.trim(), ...attrs }, text);
}

/* --------------------------------------------------------------------------
 * Feedback
 * ----------------------------------------------------------------------- */

/** A summary of blocking errors, announced politely and focusable. */
export function errorSummary(errors) {
  if (!errors || !errors.length) return null;
  const node = el("div", { class: "form-errors", role: "alert", tabindex: "-1" },
    el("h2", {}, errors.length === 1
      ? "There is one thing to fix"
      : `There are ${errors.length} things to fix`),
    el("ul", {}, ...errors.map((message) => el("li", {}, message))));
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

    const ok = window.confirm(
      `You have ${what}.\n\nLeave this page and lose them?`);
    if (ok) { release(); return; }
    event.preventDefault();
    event.stopPropagation();
  };

  function release() {
    window.removeEventListener("beforeunload", onBeforeUnload);
    document.removeEventListener("click", onClick, true);
  }

  window.addEventListener("beforeunload", onBeforeUnload);
  document.addEventListener("click", onClick, true);
  return release;
}

/* --------------------------------------------------------------------------
 * A modal question
 * ----------------------------------------------------------------------- */

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
  return new Promise((resolve) => {
    const input = el("input", {
      type: secret ? "password" : "text",
      class: secret ? "mono" : null,
      id: "ask-value",
      autocomplete: secret ? "off" : null,
      autocapitalize: secret ? "characters" : null,
      spellcheck: "false",
    });

    let answer = null;
    const form = el("form", { method: "dialog" });
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
          onclick: () => { answer = null; dialog.close(); },
        })));

    const dialog = el("dialog", { class: "dialog" }, form);
    dialog.addEventListener("close", () => {
      dialog.remove();
      resolve(answer || null);
    });

    add(document.body, dialog);
    dialog.showModal();
    input.focus();
  });
}
