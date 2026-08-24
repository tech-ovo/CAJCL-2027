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
import { add, el, clear, tabula, field, select, button, errorSummary,
         renderMarkdown, localDate, personNumber, guardUnsaved,
         draft } from "../ui.js";

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

  // What was on the server when this page loaded. Every comparison for "are
  // there unsaved changes" is against this, not against the last render, so
  // ticking a box and unticking it again correctly counts as no change.
  let original = snapshot();
  let dirty = false;

  const noteNodes = new Map();
  let submitButton = null;
  let unsavedNote = null;

  // A safety net for the school Chromebook whose lesson ends mid-form. Never
  // the record -- see the note on draft() in ui.js.
  const held = draft(`activity.${sheet.person.id}`);
  let restored = false;

  const levels = sheet.school_level === "MS"
    ? ["MS-1", "MS-2", "MS-3"]
    : ["HS-1", "HS-2", "HS-3", "HS-Adv"];
  const grades = sheet.school_level === "MS" ? [6, 7, 8] : [9, 10, 11, 12];

  restoreDraft();
  render();
  guardUnsaved(() => dirty, "unsaved changes to your activity sheet");

  /* Anything typed and not saved before the tab closed. Applied silently and
   * said so on screen -- a delegate should not have to accept a dialog to get
   * their own answers back, but they do need to know why the form is not the
   * one the server has. */
  function restoreDraft() {
    const stored = held.read();
    if (!stored || !stored.value) return;
    if (stored.value.snapshot === original) {
      // The server already has it. Nothing to restore, and nothing to warn
      // about.
      held.clear();
      return;
    }

    const value = stored.value;
    grade = value.grade || grade;
    level = value.level || level;
    meal = value.meal || meal;
    selected = new Set(value.selected || []);
    options = { ...(value.options || {}) };
    restored = true;
    dirty = true;
  }

  function render() {
    // A full rebuild throws away the scroll position. This runs rarely now --
    // only on save and on a Latin-level change -- but when it does run, the
    // page must not jump.
    const scroll = window.scrollY;
    clear(host);
    const person = sheet.person;

    add(host,
      tabula({
        label: "Delegate",
        name: `${person.first_name} ${person.last_name}`,
        left: level || "Latin level not set",
        right: personNumber(person.id),
      }));

    if (sheet.locked) {
      add(host, el("div", { class: "waking waking--failed" },
        el("p", { class: "label label--ink" }, "Forms are closed"),
        el("p", {}, "The deadline has passed. If something needs to change, ask " +
                    "your sponsor — they can ask a chair to reopen your form.")));
    }

    if (saved) {
      add(host, el("div", { class: "form-errors", role: "status" },
        el("h2", {}, "Your activity sheet is saved"),
        el("p", { style: "margin:0" },
          "You can come back and change it any time before the deadline."),
        ...warnings.map((w) => el("p", { style: "margin:.5rem 0 0" }, w))));
    }

    add(host,
      el("h1", {}, "Activities"),
      renderMarkdown(
        "Choose the events you would like to enter. **None of these choices " +
        "are binding** — they exist so the Academics, Activities, and Athletics " +
        "chairs know how many students to prepare for.\n\n" +
        "**Save whenever you like.** This is not a one-time submission: save " +
        "what you have decided so far and come back as often as you want " +
        "before the deadline."),
      deadlineNote(),
      restored
        ? el("div", { class: "banner banner--info", style: "margin-bottom:1.5rem" },
            el("span", { class: "banner__label" }, "Restored"),
            el("span", {}, "These are the answers you had open last time on "
                         + "this device, which were never saved. Check them "
                         + "over and press Save my answers."))
        : null,
      errors.length ? errorSummary(errors) : null);

    const form = el("form", {
      novalidate: true,
      onsubmit: (event) => { event.preventDefault(); save(); },
    });

    // -- about you -------------------------------------------------------
    add(form, 
      el("fieldset", {},
        el("legend", {}, el("h2", {}, "About you")),
        el("div", { class: "grid" },
          el("div", { class: "span-4" }, field({
            id: "grade", label: "Grade", required: true,
            control: select([["", "Choose one"], ...grades.map((g) => [g, g, g == grade])],
              { onchange: (e) => { grade = e.target.value; touch(); } }),
          })),
          el("div", { class: "span-4" }, field({
            id: "latin", label: "Latin level", required: true,
            help: "This decides which tests you may take.",
            control: select([["", "Choose one"],
                             ...levels.map((l) => [l, l, l === level])],
              { onchange: (e) => { level = e.target.value; touch(); regate(); } }),
          })),
          el("div", { class: "span-4" }, field({
            id: "meal", label: "Meal preference", required: true,
            control: select(MEALS.map(([v, t]) => [v, t, v === meal]),
              { onchange: (e) => { meal = e.target.value; touch(); } }),
          })))));

    // -- catalog ---------------------------------------------------------
    for (const category of sheet.catalog) {
      add(form, categorySection(category));
    }

    // -- chapter entries, read-only --------------------------------------
    if (sheet.chapter_entries && sheet.chapter_entries.length) {
      add(form, el("fieldset", {},
        el("legend", {}, el("h2", {}, "Your chapter's team entries")),
        el("p", { class: "muted" },
          "Your sponsor enters these for the whole chapter. You cannot change " +
          "them here."),
        el("ul", {}, ...sheet.chapter_entries.map((entry) =>
          el("li", {}, `${entry.item_name} — team ${entry.team_label}`)))));
    }

    // "Submit my sheet" read as final, and a delegate who thinks a form can be
    // submitted once waits until they have decided everything -- which for a
    // convention in March means waiting until March, and losing the lot when
    // the tab closes. It has always been a save. Say so.
    submitButton = button("Save my answers",
                          { variant: "btn--primary", type: "submit" });
    unsavedNote = el("p", { class: "form-note", "aria-live": "polite" });

    add(form, el("div", { class: "btn-row" }, submitButton, unsavedNote));
    add(host, form);
    refreshSubmit();
    window.scrollTo({ top: scroll });
  }

  /* The button is live only when there is something to save. A button that is
   * always clickable teaches people that clicking it means nothing. */
  function refreshSubmit() {
    if (!submitButton) return;
    submitButton.disabled = sheet.locked || !dirty;

    clear(unsavedNote);
    unsavedNote.className = "form-note";
    if (sheet.locked) {
      add(unsavedNote, "Forms are closed.");
    } else if (dirty) {
      // Red, because it is the one state on this page that costs something to
      // ignore. Everything else here is deliberately quiet.
      unsavedNote.className = "form-note form-note--unsaved";
      add(unsavedNote, "Unsaved changes — press Save my answers.");
    } else if (sheet.status === "submitted") {
      add(unsavedNote, "Saved. You can change any of this until the deadline.");
    }
  }

  /* Something changed. Compare against what the server sent, so that undoing a
   * change also undoes the warning. */
  function touch() {
    dirty = snapshot() !== original;
    refreshSubmit();
    // Written on every change, not on a timer: the whole point is to survive a
    // close that gives no warning.
    if (dirty) {
      held.save({
        snapshot: snapshot(), grade, level, meal,
        selected: [...selected], options,
      });
    } else {
      held.clear();
    }
  }

  function snapshot() {
    return JSON.stringify({
      grade: String(grade || ""),
      level: level || "",
      meal: meal || "",
      selected: [...selected].sort(),
      options: Object.fromEntries(Object.entries(options)
        .filter(([, list]) => list && list.length)
        .map(([key, list]) => [key, [...list].sort()])),
    });
  }

  function deadlineNote() {
    if (!sheet.deadline) return null;
    const when = localDate(sheet.deadline);
    if (!when) return null;
    return el("p", { class: "deadline" },
      el("span", { class: "label label--ink" }, "Due"),
      ` ${when}. You can change your answers freely until then.`);
  }

  function categorySection(category) {
    const note = el("p", { "aria-live": "polite" });
    noteNodes.set(category.key, note);
    refreshCount(category);

    return el("fieldset", { id: `cat-${category.key}` },
      el("legend", {}, el("h2", {}, category.name)),
      category.description ? el("p", { class: "muted" }, category.description) : null,
      note,
      el("div", { class: "choices choices--two" },
        ...category.items.map((item) => choice(category, item))));
  }

  /* Ticking a box used to re-render the entire page, which scrolled the reader
   * back to the top and took the focus off the box they had just clicked. On a
   * sheet with forty checkboxes that is unusable. Everything a tick changes --
   * the label's own styling, its sub-options, and the category's count -- is
   * updated in place instead. */
  function choice(category, item) {
    const blocked = !item.eligible_now;
    const isSelected = selected.has(item.id);

    const box = el("input", {
      type: "checkbox",
      checked: isSelected,
      disabled: blocked || sheet.locked,
      id: `item-${item.id}`,
      onchange: (event) => {
        const on = event.target.checked;
        if (on) {
          selected.add(item.id);
        } else {
          selected.delete(item.id);
          delete options[item.id];
        }
        label.classList.toggle("choice--selected", on);

        const existing = label.querySelector(".choice__options");
        if (existing) existing.remove();
        if (on && item.options.length) add(label, subOptions(item));

        refreshCount(category);
        touch();
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
      add(label, subOptions(item));
    }
    return label;
  }

  function subOptions(item) {
    const picked = new Set(options[item.id] || []);
    return el("span", {
      class: "choice__options",
      style: "grid-column: 2; display:block; margin-top:.5rem",
    },
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
              touch();
            },
          }),
          option.name))));
  }

  function refreshCount(category) {
    const note = noteNodes.get(category.key);
    if (!note) return;

    const { min_selections: low, max_selections: high, enforcement } = category;
    clear(note);
    if (!low && !high) { note.className = ""; return; }

    const chosen = category.items.filter((i) => selected.has(i.id)).length;
    let text;
    if (low && high) text = `Choose between ${low} and ${high}. You have ${chosen}.`;
    else if (low) text = `Choose at least ${low}. You have ${chosen}.`;
    else text = `Choose no more than ${high}. You have ${chosen}.`;

    const over = (low && chosen < low) || (high && chosen > high);
    note.className = over ? "count-note count-note--over" : "count-note";
    add(note, text,
      over && enforcement === "warn" ? " This is a suggestion, not a rule." : null);
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
    touch();
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
      grade = sheet.person.grade || "";
      level = sheet.person.latin_level || "";
      meal = sheet.person.meal || "";
      // What is now on the server becomes the new baseline, so the page is
      // clean again and the leave-warning goes quiet.
      original = snapshot();
      dirty = false;
      restored = false;
      // The server has it now, so the local copy is only a way to get confused.
      held.clear();
      render();
      window.scrollTo({ top: 0 });
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
