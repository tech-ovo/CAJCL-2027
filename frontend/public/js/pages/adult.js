/* The Adult Registration Sheet.
 *
 * "Please sign up for at least two roles" is a WARNING, not a block. An adult
 * who ignores it can still submit -- some of them genuinely can only do one
 * thing, and refusing the form teaches them the site is broken.
 *
 * Roles needing Latin are shown DISABLED with the requirement stated, the same
 * treatment as an ineligible test, for the same reason.
 *
 * There are no time blocks. Adults say which events they are willing to run,
 * and the notes field carries availability and anything else a chair should
 * know.
 */

import * as api from "../api.js";
import { add, el, clear, tabula, field, input, select, button, errorSummary,
         renderMarkdown, personNumber, guardUnsaved, draft } from "../ui.js";

// See the note in activity.js: a "no meal" option lands with the reset.
const MEALS = [["", "Choose one"], ["regular", "Regular"],
               ["vegetarian", "Vegetarian"], ["gluten_free", "Gluten free"]];

/* The original four-level scale. Every current role needs either nothing or
 * advanced, but all four are here so a future chair can mark a role as needing
 * intermediate Latin from the dashboard without a schema change. */
const LATIN = [
  ["none", "None"],
  ["novice", "Novice"],
  ["intermediate", "Intermediate"],
  ["advanced", "Advanced"],
];

/* Two labels each. The long one is for the menu, where somebody is deciding
 * which they are and the extra words are the whole point. The short one is for
 * the tabula, where it sits beside a name in small capitals and "Latin teacher
 * or sponsor" wraps onto two lines to say what "Sponsor" says. */
const TYPES = [
  ["sponsor", "Latin teacher or sponsor", "Sponsor"],
  ["chaperone", "Parent or chaperone", "Chaperone"],
  ["scl", "SCL", "SCL"],
  ["other", "Other", "Adult"],
];

function shortType(value) {
  const found = TYPES.find(([key]) => key === value);
  return found ? found[2] : "Adult";
}

export async function adultSheetPage(host) {
  let sheet = await api.get("/me/adult-sheet", { statusHost: host });
  let selected = new Set(sheet.selected);
  let person = { ...sheet.person };
  /* A SPONSOR IS A LATIN TEACHER. Defaulting them to "None" made every one of
   * them correct the form, and the ones who did not were quietly excluded from
   * the roles that need Latin — Certamen moderating above all.
   *
   * A chaperone is a parent, and "None" is the right default for them.
   *
   * This is only the starting position of a control they can change. Nothing
   * downstream assumes it. */
  let knowledge = person.latin_knowledge
    || (person.adult_type === "sponsor" ? "advanced" : "none");
  let errors = [];
  let warnings = [];
  let saved = false;
  const countNotes = new Map();

  // Same idea as the activity sheet: compare against what the server sent, so
  // that changing something and changing it back counts as no change.
  let original = snapshot();
  let dirty = false;

  // Same safety net as the activity sheet: an adult filling this in on a phone
  // between classes should not lose it to a closed tab.
  const held = draft(`adult.${sheet.person.id}`);
  let restored = false;
  let submitButton = null;
  let unsavedNote = null;

  restoreDraft();
  render();
  guardUnsaved(() => dirty, "unsaved changes to your registration form");

  function restoreDraft() {
    const stored = held.read();
    if (!stored || !stored.value) return;
    if (stored.value.snapshot === original) { held.clear(); return; }

    const value = stored.value;
    person = { ...person, ...(value.person || {}) };
    knowledge = value.knowledge || knowledge;
    selected = new Set(value.selected || []);
    restored = true;
    dirty = true;
  }

  function refreshSubmit() {
    if (!submitButton) return;
    submitButton.disabled = sheet.locked || !dirty;

    clear(unsavedNote);
    unsavedNote.className = "form-note";
    if (sheet.locked) {
      add(unsavedNote, "Forms are closed.");
    } else if (dirty) {
      unsavedNote.className = "form-note form-note--unsaved";
      add(unsavedNote, "Unsaved changes — press Save my answers.");
    } else if (sheet.status === "submitted") {
      add(unsavedNote, "Saved. You can change any of this until the deadline.");
    }
  }

  function snapshot() {
    return JSON.stringify({
      email: person.email || "",
      cell_phone: person.cell_phone || "",
      adult_type: person.adult_type || "",
      meal: person.meal || "",
      availability_note: person.availability_note || "",
      knowledge,
      selected: [...selected].sort(),
    });
  }

  function touch() {
    dirty = snapshot() !== original;
    refreshSubmit();
    if (dirty) {
      held.save({ snapshot: snapshot(), person, knowledge,
                  selected: [...selected] });
    } else {
      held.clear();
    }
  }

  function render() {
    clear(host);

    add(host, tabula({
      label: "Adult",
      name: `${person.first_name} ${person.last_name}`,
      left: shortType(person.adult_type),
      right: personNumber(sheet.school || {}, person),
    }));

    if (restored) {
      add(host, el("div", { class: "banner banner--info",
                            style: "margin-bottom:1.5rem" },
        el("span", { class: "banner__label" }, "Restored"),
        el("span", {}, "These are the answers you had open last time on this "
                     + "device, which were never saved. Check them over and "
                     + "press Save my answers.")));
    }

    if (sheet.locked) {
      add(host, el("div", { class: "waking waking--failed" },
        el("p", { class: "label label--ink" }, "Forms are closed"),
        el("p", {}, "The deadline has passed. Ask a registration chair if " +
                    "something needs to change.")));
    }

    if (saved) {
      add(host, el("div", { class: "form-errors", role: "status" },
        el("h2", {}, "Your registration is saved"),
        ...(warnings.length
          ? warnings.map((w) => el("p", { style: "margin:0" }, w))
          : [el("p", { style: "margin:0" },
              "You can change it any time before the deadline.")])));
    }

    add(host, 
      el("h1", {}, "Adult Registration Sheet"),
      renderMarkdown(
        "Tell us which events you are willing to help run. There are no time " +
        "blocks to choose — chairs build the schedule around who is available, " +
        "and the notes field at the bottom is where to explain anything they " +
        "should know."),
      errors.length ? errorSummary(errors) : null);

    const form = el("form", {
      novalidate: true,
      onsubmit: (event) => { event.preventDefault(); save(); },
    });

    add(form, 
      el("fieldset", {},
        el("legend", {}, el("h2", {}, "About you")),
        el("div", { class: "grid" },
          el("div", { class: "span-6" }, field({
            id: "email", label: "Email", required: true,
            help: "Chairs use this to reach you about your shifts.",
            control: input({
              type: "email", value: person.email || "",
              oninput: (e) => { person.email = e.target.value; touch(); },
            }),
          })),
          el("div", { class: "span-6" }, field({
            id: "phone", label: "Cell phone",
            help: "Used only during convention weekend.",
            control: input({
              type: "tel", value: person.cell_phone || "",
              oninput: (e) => { person.cell_phone = e.target.value; touch(); },
            }),
          })),
          el("div", { class: "span-6" }, field({
            id: "type", label: "You are a", required: true,
            control: select(TYPES.map(([v, t]) => [v, t, v === person.adult_type]),
              { onchange: (e) => { person.adult_type = e.target.value; touch(); } }),
          })),
          el("div", { class: "span-6" }, field({
            id: "meal", label: "Meal preference",
            control: select(MEALS.map(([v, t]) => [v, t, v === person.meal]),
              { onchange: (e) => { person.meal = e.target.value; touch(); } }),
          })),
          el("div", { class: "span-12" }, field({
            id: "latin", label: "How much Latin do you know?", required: true,
            help: "Some roles need advanced Latin. Answering honestly here is " +
                  "what opens or closes them below.",
            wide: true,
            control: select(LATIN.map(([v, t]) => [v, t, v === knowledge]),
              { onchange: (e) => { knowledge = e.target.value; touch(); regate(); } }),
          })))));

    for (const category of sheet.catalog) {
      const note = el("p", { class: "count-note", "aria-live": "polite" });
      countNotes.set(category.key, { note, category });
      add(form, el("fieldset", {},
        el("legend", {}, el("h2", {}, category.name)),
        category.description ? el("p", { class: "muted" }, category.description) : null,
        note,
        el("div", { class: "choices choices--two" },
          ...category.items.map((item) => choice(category, item)))));
    }

    add(form, 
      el("fieldset", {},
        el("legend", {}, el("h2", {}, "Anything else")),
        field({
          id: "note", label: "Notes for the chairs", wide: true,
          help: "When you can and cannot be there, what you would rather not do, " +
                "anyone you need to be near — anything at all.",
          control: el("textarea", {
            oninput: (e) => { person.availability_note = e.target.value; touch(); },
          }, person.availability_note || ""),
        })),
      el("div", { class: "btn-row" }, buttonRow()));

    add(host, form);
    for (const category of sheet.catalog) refreshCategory(category);
    refreshSubmit();
  }

  /* "Wherever needed!" is an ANSWER, not one role among many.
   *
   * Somebody who ticks it has said "put me anywhere", which makes every other
   * box in the list meaningless — and makes "please choose at least two"
   * meaningless too, since they have already given the most useful answer
   * there is. Both used to stay on screen, so the form went on asking for
   * more after it had got what it wanted.
   */
  function anywhereItem(category) {
    return category.items.find((item) => /^wherever needed/i.test(item.name))
        || null;
  }

  function refreshCategory(category) {
    const entry = countNotes.get(category.key);
    if (!entry) return;

    const anywhere = anywhereItem(category);
    const openToAnything = anywhere ? selected.has(anywhere.id) : false;

    for (const item of category.items) {
      const box = document.getElementById(`role-${item.id}`);
      if (!box) continue;
      const isAnywhere = anywhere && item.id === anywhere.id;
      const off = openToAnything && !isAnywhere;
      box.disabled = !item.eligible_now || sheet.locked || off;
      const label = box.closest(".choice");
      if (label) label.classList.toggle("choice--capped", off);
    }

    const chosen = category.items.filter((i) => selected.has(i.id)).length;
    clear(entry.note);
    if (openToAnything) {
      add(entry.note, "You have said you will go wherever you are needed, "
                    + "which is the most useful answer there is. Untick it if "
                    + "you would rather pick particular roles.");
      return;
    }
    add(entry.note, `You have chosen ${chosen}.`
      + (category.min_selections && chosen < category.min_selections
          ? ` Please choose at least ${category.min_selections} if you can — `
            + "you can still submit either way."
          : ""));
  }

  /* "Submit my registration" read as one-and-final, which is how an adult ends
   * up holding a half-finished form until the deadline. It has always been a
   * save. */
  function buttonRow() {
    // Not a submit button: this one runs `save()` itself, so it can disable
    // itself and show the wait in place of its label. The form's onsubmit
    // stays for the Enter key and calls the same function.
    submitButton = button("Save my answers",
                          { variant: "btn--primary", onclick: () => save() });
    unsavedNote = el("p", { class: "form-note", "aria-live": "polite" });
    return [submitButton, unsavedNote];
  }

  function choice(category, item) {
    const blocked = !item.eligible_now;
    const isSelected = selected.has(item.id);
    return el("label", {
      class: "choice" + (blocked ? " choice--blocked" : "") +
             (isSelected ? " choice--selected" : ""),
      for: `role-${item.id}`,
    },
      el("input", {
        type: "checkbox", id: `role-${item.id}`,
        checked: isSelected, disabled: blocked || sheet.locked,
        onchange: (event) => {
          const on = event.target.checked;
          if (on) selected.add(item.id); else selected.delete(item.id);

          // Ticking "wherever needed" clears the specific roles it replaces.
          const anywhere = anywhereItem(category);
          if (on && anywhere && item.id === anywhere.id) {
            for (const other of category.items) {
              if (other.id !== anywhere.id) selected.delete(other.id);
            }
            for (const other of category.items) {
              const box = document.getElementById(`role-${other.id}`);
              if (box && other.id !== anywhere.id) box.checked = false;
              const label = box && box.closest(".choice");
              if (label && other.id !== anywhere.id) {
                label.classList.remove("choice--selected");
              }
            }
          }

          // IN PLACE, NOT A FULL RE-RENDER. `render()` rebuilt the whole form,
          // which threw the reader back to the top of the page every time they
          // ticked a box near the bottom of it.
          const label = event.target.closest(".choice");
          if (label) label.classList.toggle("choice--selected", on);
          refreshCategory(category);
          touch();
        },
      }),
      el("span", {},
        el("span", { class: "choice__name" }, item.name),
        blocked ? el("span", { class: "choice__why" }, item.reason) : null));
  }

  /* Latin knowledge changed: re-gate locally with the rules already in hand. */
  function regate() {
    const rank = { none: 0, novice: 1, intermediate: 2, advanced: 3 };
    for (const category of sheet.catalog) {
      for (const item of category.items) {
        const needed = item.min_latin_knowledge;
        if (!needed) { item.eligible_now = true; item.reason = ""; continue; }
        item.eligible_now = rank[knowledge] >= rank[needed];
        item.reason = `Needs ${needed} Latin.`;
        if (!item.eligible_now) selected.delete(item.id);
      }
    }
    render();
  }

  async function save() {
    errors = [];
    warnings = [];
    try {
      const result = await api.put("/me/adult-sheet", {
        email: person.email || null,
        cell_phone: person.cell_phone || null,
        adult_type: person.adult_type,
        meal: person.meal || null,
        latin_knowledge: knowledge,
        availability_note: person.availability_note || null,
        selected: [...selected],
      });          // the button shows the wait; see ui.js button()

      warnings = result.warnings || [];
      saved = true;
      sheet = await api.get("/me/adult-sheet");
      person = { ...sheet.person };
      selected = new Set(sheet.selected);
      knowledge = person.latin_knowledge
        || (person.adult_type === "sponsor" ? "advanced" : "none");
      // What is now on the server becomes the new baseline, and the local
      // copy is only a way to get confused.
      original = snapshot();
      dirty = false;
      restored = false;
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
