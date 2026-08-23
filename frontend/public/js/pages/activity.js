/* The Student Activity Sheet.
 *
 * Submitted once rather than saved on every keystroke, and editable until the
 * deadline.
 *
 * INELIGIBLE TESTS ARE DISABLED WITH AN EXPLANATION, NEVER HIDDEN. A delegate
 * who cannot find Grammar 2 assumes the site is broken. The server sends every
 * item with its rule attached, so changing Latin level re-gates the list
 * instantly with no round trip -- which matters on a cold container.
 *
 * The test count is a HARD BLOCK. Everything else is a preference.
 */

import * as api from "../api.js";
import {
  el, clear, tabula, field, select, button, errorSummary, renderMarkdown,
} from "../ui.js";

const MEALS = [["", "Choose one"], ["regular", "Regular"],
               ["vegetarian", "Vegetarian"], ["gluten_free", "Gluten free"]];

export async function activitySheetPage(host) {
  let sheet = await api.get("/me/activity-sheet", { statusHost: host });
  let selected = new Set(sheet.selected);
  let options = { ...(sheet.selected_options || {}) };
  let level = sheet.person.latin_level || "";
  let grade = sheet.person.grade || "";
  let meal = sheet.person.meal || "";
  let errors = [];
  let warnings = [];
  let saved = false;

  const levels = sheet.school_level === "MS"
    ? ["MS-1", "MS-2", "MS-3"]
    : ["HS-1", "HS-2", "HS-3", "HS-Adv"];
  const grades = sheet.school_level === "MS" ? [6, 7, 8] : [9, 10, 11, 12];

  render();

  function render() {
    clear(host);
    const person = sheet.person;

    host.append(
      tabula({
        label: "Delegate",
        name: `${person.first_name} ${person.last_name}`,
        left: level || "Latin level not set",
        right: `№  ${String(person.id).padStart(4, "0")}`,
      }));

    if (sheet.locked) {
      host.append(el("div", { class: "waking waking--failed" },
        el("p", { class: "label label--ink" }, "Forms are closed"),
        el("p", {}, "The deadline has passed. If something needs to change, ask " +
                    "your sponsor — they can ask a chair to reopen your form.")));
    }

    if (saved) {
      host.append(el("div", { class: "form-errors", role: "status" },
        el("h2", {}, "Your activity sheet is saved"),
        el("p", { style: "margin:0" },
          "You can come back and change it any time before the deadline."),
        ...warnings.map((w) => el("p", { style: "margin:.5rem 0 0" }, w))));
    }

    host.append(
      el("h1", {}, "Student Activity Sheet"),
      renderMarkdown(
        "Choose the events you would like to enter. **None of these choices " +
        "are binding** — they exist so the Academics, Activities, and Athletics " +
        "chairs know how many students to prepare for. You can change your " +
        "answers until the deadline."),
      errors.length ? errorSummary(errors) : null);

    const form = el("form", {
      novalidate: true,
      onsubmit: (event) => { event.preventDefault(); save(); },
    });

    // -- about you -------------------------------------------------------
    form.append(
      el("fieldset", {},
        el("legend", {}, el("h2", {}, "About you")),
        el("div", { class: "grid" },
          el("div", { class: "span-4" }, field({
            id: "grade", label: "Grade", required: true,
            control: select([["", "Choose one"], ...grades.map((g) => [g, g, g == grade])],
              { onchange: (e) => { grade = e.target.value; } }),
          })),
          el("div", { class: "span-4" }, field({
            id: "latin", label: "Latin level", required: true,
            help: "This decides which tests you may take.",
            control: select([["", "Choose one"],
                             ...levels.map((l) => [l, l, l === level])],
              { onchange: (e) => { level = e.target.value; regate(); } }),
          })),
          el("div", { class: "span-4" }, field({
            id: "meal", label: "Meal preference",
            control: select(MEALS.map(([v, t]) => [v, t, v === meal]),
              { onchange: (e) => { meal = e.target.value; } }),
          })))));

    // -- catalog ---------------------------------------------------------
    for (const category of sheet.catalog) {
      form.append(categorySection(category));
    }

    // -- chapter entries, read-only --------------------------------------
    if (sheet.chapter_entries && sheet.chapter_entries.length) {
      form.append(el("fieldset", {},
        el("legend", {}, el("h2", {}, "Your chapter's team entries")),
        el("p", { class: "muted" },
          "Your sponsor enters these for the whole chapter. You cannot change " +
          "them here."),
        el("ul", {}, ...sheet.chapter_entries.map((entry) =>
          el("li", {}, `${entry.item_name} — team ${entry.team_label}`)))));
    }

    const submit = button(sheet.status === "submitted" ? "Save changes" : "Submit my sheet",
      { variant: "btn--primary", type: "submit", disabled: sheet.locked });

    form.append(el("div", { class: "btn-row" }, submit));
    host.append(form);
  }

  function categorySection(category) {
    const chosen = category.items.filter((i) => selected.has(i.id)).length;
    const note = countNote(category, chosen);

    return el("fieldset", { id: `cat-${category.key}` },
      el("legend", {}, el("h2", {}, category.name)),
      category.description ? el("p", { class: "muted" }, category.description) : null,
      note,
      el("div", { class: "choices choices--two" },
        ...category.items.map((item) => choice(category, item))));
  }

  function choice(category, item) {
    const blocked = !item.eligible_now;
    const isSelected = selected.has(item.id);

    const box = el("input", {
      type: "checkbox",
      checked: isSelected,
      disabled: blocked || sheet.locked,
      id: `item-${item.id}`,
      onchange: (event) => {
        if (event.target.checked) selected.add(item.id);
        else { selected.delete(item.id); delete options[item.id]; }
        render();
      },
    });

    const label = el("label", {
      class: "choice" + (blocked ? " choice--blocked" : "") +
             (isSelected ? " choice--selected" : ""),
      for: `item-${item.id}`,
    },
      box,
      el("span", {},
        el("span", { class: "choice__name" }, item.name),
        // The requirement is stated, not implied by absence.
        blocked ? el("span", { class: "choice__why" }, item.reason) : null,
        item.description ? el("span", { class: "choice__why" }, item.description) : null));

    if (isSelected && item.options.length) {
      label.append(subOptions(item));
    }
    return label;
  }

  function subOptions(item) {
    const picked = new Set(options[item.id] || []);
    return el("span", { style: "grid-column: 2; display:block; margin-top:.5rem" },
      el("span", { class: "label" },
        item.max_sub_selections
          ? `Choose up to ${item.max_sub_selections}`
          : "Choose any"),
      el("span", { style: "display:flex; gap:1rem; flex-wrap:wrap; margin-top:.25rem" },
        ...item.options.map((option) => el("label", {
          class: "small",
          style: "display:inline-flex; gap:.35rem; align-items:center",
        },
          el("input", {
            type: "checkbox", checked: picked.has(option.id),
            disabled: sheet.locked,
            onchange: (event) => {
              const next = new Set(options[item.id] || []);
              if (event.target.checked) next.add(option.id); else next.delete(option.id);
              options[item.id] = [...next];
              render();
            },
          }),
          option.name))));
  }

  function countNote(category, chosen) {
    const { min_selections: low, max_selections: high, enforcement } = category;
    if (!low && !high) return null;

    let text;
    if (low && high) text = `Choose between ${low} and ${high}. You have ${chosen}.`;
    else if (low) text = `Choose at least ${low}. You have ${chosen}.`;
    else text = `Choose no more than ${high}. You have ${chosen}.`;

    const over = (low && chosen < low) || (high && chosen > high);
    return el("p", {
      class: over ? "count-note count-note--over" : "count-note",
      "aria-live": "polite",
    }, text, over && enforcement === "warn" ? " This is a suggestion, not a rule." : "");
  }

  /* Latin level changed: re-evaluate eligibility locally, with no request.
   * The rules came down with the catalog for exactly this. */
  function regate() {
    for (const category of sheet.catalog) {
      for (const item of category.items) {
        const levels = item.eligible_latin_levels || [];
        if (!levels.length) { item.eligible_now = true; item.reason = ""; continue; }
        item.eligible_now = !!level && levels.includes(level);
        item.reason = level
          ? `Open to ${joinWords(levels)}.`
          : `Choose your Latin level first. Open to ${joinWords(levels)}.`;
        // A test that just became ineligible cannot stay ticked.
        if (!item.eligible_now) selected.delete(item.id);
      }
    }
    render();
  }

  async function save() {
    errors = [];
    warnings = [];
    try {
      const result = await api.put("/me/activity-sheet", {
        grade: grade ? Number(grade) : null,
        latin_level: level || null,
        meal: meal || null,
        selected: [...selected],
        selected_options: options,
      }, { statusHost: host });

      warnings = result.warnings || [];
      saved = true;
      sheet = await api.get("/me/activity-sheet");
      selected = new Set(sheet.selected);
      options = { ...(sheet.selected_options || {}) };
      render();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      errors = error.errors && error.errors.length ? error.errors : [error.message];
      saved = false;
      render();
    }
  }
}

function joinWords(values) {
  if (values.length === 1) return values[0];
  return `${values.slice(0, -1).join(", ")} and ${values[values.length - 1]}`;
}
