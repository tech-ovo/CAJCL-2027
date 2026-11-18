/* potluck.js — the "Activities potluck" section of the two registration sheets.
 *
 * One list, used by the Student Activity Sheet and the Adult Registration
 * Sheet. The server sends every activity that is taking helpers (and any the
 * person has already picked), with the person's own status on each:
 *
 *   pending    waiting for the sponsor            (delegates only)
 *   approved   yes
 *   declined   the sponsor said no; ticking it again asks again
 *
 * An adult's pick is approved at once, so an adult sees no status at all.
 *
 * TWO PICKS AT THE SAME TIME ARE A NOTE, NOT A BLOCK. The server says the same
 * thing in its save warnings; saying it here as well means it is seen while
 * choosing rather than after.
 *
 * Ticking updates the box in place and never rebuilds the page: the sheets are
 * long, and a rebuild scrolls the reader back to the top.
 */

import { el, add, clear } from "./ui.js";
import { whenText } from "./when.js";

/* Minutes since an arbitrary day zero, from a California date and "HH:MM".
 * Plain arithmetic on the pieces the server sent; no zone is involved. */
function minutes(date, time) {
  const [year, month, day] = date.split("-").map(Number);
  const [hour, minute] = time.split(":").map(Number);
  return Math.floor(Date.UTC(year, month - 1, day) / 60000) + hour * 60 + minute;
}

function span(activity) {
  if (!activity.date || !activity.start) return null;
  const start = minutes(activity.date, activity.start);
  const end = activity.end
    ? minutes(activity.end_date || activity.date, activity.end)
    : start + 1;
  return [start, end];
}

function overlaps(chosen) {
  const spans = chosen.map((a) => [a, span(a)]).filter(([, s]) => s);
  const notes = [];
  spans.forEach(([first, [s1, e1]], i) => {
    spans.slice(i + 1).forEach(([second, [s2, e2]]) => {
      if (s1 < e2 && s2 < e1) {
        notes.push(`“${first.name}” and “${second.name}” are at the same time.`);
      }
    });
  });
  return notes;
}

function placesText(activity) {
  if (activity.capacity === null || activity.capacity === undefined) return "";
  const left = activity.spots_left;
  return left > 0
    ? `${left} of ${activity.capacity} places left.`
    : `All ${activity.capacity} places are taken.`;
}

/**
 * @param potluck  the server's `sheet.potluck`
 * @param selected a Set of activity ids, changed in place as boxes are ticked
 * @param locked   true when the sheet is closed
 * @param onChange called after every tick
 * @returns the section, or null when there is nothing to show
 */
export function potluckSection({ potluck, selected, locked, onChange }) {
  if (!potluck || !potluck.activities.length) return null;

  const needsApproval = !!potluck.needs_approval;
  const note = el("p", { class: "count-note", "aria-live": "polite" });

  function refreshNote() {
    clear(note);
    const chosen = potluck.activities.filter((a) => selected.has(a.id));
    const clashes = overlaps(chosen);
    note.className = clashes.length ? "count-note" : "";
    if (clashes.length) add(note, ...clashes.map((text) => el("span", { style: "display:block" }, text)));
  }

  function statusPill(activity) {
    if (!needsApproval) return null;
    if (activity.status === "approved") {
      return el("span", { class: "pill pill--done" }, "✓ Approved");
    }
    if (activity.status === "pending" && selected.has(activity.id)) {
      return el("span", { class: "pill" }, "Waiting for your sponsor");
    }
    return null;
  }

  function choice(activity) {
    const picked = selected.has(activity.id);
    // A full or closed activity cannot be newly picked, but a pick already
    // made can always be taken back.
    const full = activity.spots_left === 0 && activity.status !== "pending"
                 && activity.status !== "approved";
    const closed = !activity.open && !picked;
    const blocked = full || closed;

    const box = el("input", {
      type: "checkbox", checked: picked,
      disabled: locked || blocked,
      id: `potluck-${activity.id}`,
      onchange: (event) => {
        if (event.target.checked) selected.add(activity.id);
        else selected.delete(activity.id);
        label.classList.toggle("choice--selected", event.target.checked);
        refreshNote();
        onChange();
      },
    });

    const when = whenText(activity);
    const details = [when, activity.location].filter(Boolean).join(" · ");
    const label = el("label", {
      class: "choice" + (blocked ? " choice--blocked" : "")
             + (picked ? " choice--selected" : ""),
      for: `potluck-${activity.id}`,
    },
      box,
      el("span", {},
        el("span", { class: "choice__name" }, activity.name, " ", statusPill(activity)),
        details ? el("span", { class: "choice__why" }, details) : null,
        activity.description
          ? el("span", { class: "choice__why" }, activity.description) : null,
        activity.status === "declined" && needsApproval
          ? el("span", { class: "choice__why" },
              "Your sponsor said no to this one. Tick it to ask again.")
          : null,
        closed ? el("span", { class: "choice__why" }, "Not taking more helpers.") : null,
        !closed && placesText(activity)
          ? el("span", { class: "choice__why" }, placesText(activity)) : null));
    return label;
  }

  const section = el("fieldset", { id: "cat-potluck" },
    el("legend", {}, el("h2", {}, "Activities potluck")),
    el("p", { class: "muted" },
      needsApproval
        ? "Tick any activity you would like to help run at convention. "
          + "Your sponsor approves each one; until they do it shows as waiting. "
          + "Choosing one is a promise to help, so only tick what you can do."
        : "Tick any activity you would like to help run at convention."),
    note,
    el("div", { class: "choices choices--two" },
      ...potluck.activities.map(choice)));
  refreshNote();
  return section;
}

/** The ids as a sorted list, for comparing a sheet with what was loaded. */
export function potluckKey(selected) {
  return [...selected].sort((a, b) => a - b);
}
