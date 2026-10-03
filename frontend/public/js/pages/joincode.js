/* A chapter's join code: show it, copy it, print the sheet, close it, replace it.
 *
 * Shared by the sponsor's roster and the chairs' chapter list, because both
 * manage the same thing and a chair is often the one reading the code out in an
 * email to a sponsor who has not signed in yet.
 *
 * THE CODE IS NOT A SECRET LIKE AN LOGIN TOKEN. It is printed on every handout
 * and shown here whenever it is wanted, which is why it can be shown at all:
 * login tokens are stored scrambled and can be read once. All the join code can
 * do is create a PENDING delegate in this one chapter, and a sponsor can close
 * it or replace it at any moment.
 */

import * as api from "../api.js";
import { add, el, clear, button, check, tell } from "../ui.js";

/** ABCDEFGH -> ABCD-EFGH, for reading aloud and for the page. */
export function formatJoinCode(code) {
  const raw = String(code || "").replace(/[^A-Za-z0-9]/g, "").toUpperCase();
  return raw.length > 4 ? `${raw.slice(0, 4)}-${raw.slice(4)}` : raw;
}

/**
 * @param school   a row carrying `id`, `name`, `join_code`, `join_open`
 * @param reload   called after any change, to fetch the page's data again
 * @param print    opens the printable join sheet for this chapter
 * @param forChair true when a chair is looking: the same facts, told to someone
 *                 who is not the one approving the students
 * @param onDone   when given, the panel is a popup and carries its own Close
 * @param margin   space below the panel; the caller sets it where the panel is
 *                 followed by something other than the page's own spacing
 */
export function joinCodePanel({ school, reload, print, forChair = false,
                                onDone = null, margin = "1.5rem" }) {
  const open = !!school.join_open;
  const shown = formatJoinCode(school.join_code);
  const status = el("span", { class: "form-note", "aria-live": "polite" });

  async function post(path, body) {
    try {
      return await api.post(path, { school_id: school.id, ...body });
    } catch (error) {
      await tell({ body: error.message });
      return null;
    }
  }

  if (!school.join_code) {
    return el("section", { class: "panel", style: `margin-bottom:${margin}` },
      el("p", { class: "label label--ink" }, "Join code"),
      el("p", { class: "muted" },
        "This chapter has no join code yet. Make one and students can register "
        + "themselves, without you pasting a roster first."),
      el("div", { class: "btn-row" },
        button("Make a join code", {
          variant: "btn--primary",
          onclick: async () => { if (await post("/sponsor/join/code", {})) await reload(); },
        })));
  }

  // The two readers are told the same thing from where they stand. A chair is
  // not the one who approves, so "waiting for you" was wrong for them.
  const where = forChair
    ? "They show up on the chapter's roster as waiting for the sponsor, who "
      + "approves them."
    : "They show up below, under Waiting for approval, until you approve them.";
  const approver = forChair ? "the sponsor approves them" : "you approve them";

  return el("section", { class: "panel", style: `margin-bottom:${margin}` },
    el("p", { class: "label label--ink" }, `Join code for ${school.name}`),
    el("p", { style: "margin:.25rem 0 .75rem" },
      el("span", { class: "tabula__code mono",
                   style: "font-size:1.75rem;letter-spacing:.08em" }, shown),
      el("span", { class: open ? "pill pill--done" : "pill",
                   style: "margin-left:.75rem" },
        open ? "Joining is open" : "Joining is closed")),
    el("p", { class: "small muted" },
      forChair
        ? "Send this code to the sponsor, or print the handout for them. "
        : "Print one handout for every student who might come. ",
      "Students go to the site, choose ",
      el("span", { class: "term" }, "Join your chapter"),
      ", type this code with their name, grade and Latin level, and are given "
      + "their own login token. ", where),
    el("p", { class: "small muted" },
      "They can fill in all of their forms straight away, without waiting for "
      + `approval. Until ${approver} they are marked preliminary and are left `
      + "out of the invoice and every total."),
    open
      ? null
      : el("p", { class: "small" },
          "Joining is closed. The code is kept but admits no one until "
          + (forChair ? "it is" : "you") + " reopened."),
    el("div", { class: "btn-row" },
      button("Print the join sheet", { variant: "btn--primary", onclick: print }),
      button("Copy the code", {
        onclick: async () => {
          clear(status);
          try {
            await navigator.clipboard.writeText(shown);
            add(status, "Copied.");
          } catch (ignored) {
            add(status, `Select and copy it from above: ${shown}`);
          }
        },
      }),
      // The default button, not the quiet one: replacing a code is something a
      // person comes here to do, and the confirmation carries the warning.
      button("New code", {
        onclick: async () => {
          const ok = await check({
            title: "Replace the join code?",
            body: ["The old code stops working at once, including on every "
                   + "handout already printed.",
                   "Students who already joined are not affected."],
            confirmLabel: "Replace it", danger: true,
          });
          if (!ok) return;
          if (await post("/sponsor/join/code", {})) await reload();
        },
      }),
      button(open ? "Close joining" : "Reopen joining", {
        variant: open ? "btn--danger" : "",
        onclick: async () => {
          if (open) {
            const ok = await check({
              title: "Close joining?",
              body: "Nobody new can join with this code until it is reopened. "
                  + "Students who already joined are not affected.",
              confirmLabel: "Close joining", danger: true,
            });
            if (!ok) return;
          }
          if (await post("/sponsor/join/open", { open: !open })) await reload();
        },
      }),
      onDone ? button("Close", { variant: "btn--quiet", onclick: onDone }) : null,
      status));
}
