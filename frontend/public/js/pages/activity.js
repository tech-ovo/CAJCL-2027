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
         draft, check, tell } from "../ui.js";

/* "No meal" is LAST and is never the default.
 *
 * It is the one answer with a consequence nobody can undo on the day: a
 * delegate who picked it by accident, or by leaving a default alone, arrives
 * to nothing to eat. Last in the list and spelled out in full, so choosing it
 * takes a decision.
 *
 * It is for somebody bringing their own, usually for an allergy the caterer
 * cannot safely cover — not for somebody who has not decided, which is what
 * the empty first option is for. */
const MEALS = [["", "Choose one"], ["regular", "Regular"],
               ["vegetarian", "Vegetarian"], ["gluten_free", "Gluten free"],
               ["none", "No meal — I am bringing my own"]];

export async function activitySheetPage(host, params = []) {
  /* A delegate opens this at #/activity-sheet and it is their own.
   *
   * A sponsor or a chair opens it at #/activity-sheet/412 for a delegate who
   * has lost their sheet, or is eleven and has given up, and whose roster row
   * would otherwise say "Not yet" with nobody able to move it.
   *
   * ONE PAGE, NOT A COPY. Every rule on it -- the test-count minimum, the
   * eligibility gating, the save dialogs -- is the same code, so it cannot
   * drift from what the delegate sees. Only the endpoint changes. */
  const personId = params[0] ? Number(params[0]) : null;
  const onBehalf = personId !== null;
  const base = onBehalf
    ? `/sponsor/people/${personId}/activity-sheet`
    : "/me/activity-sheet";

  let sheet = await api.get(base, { statusHost: host });
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
        right: personNumber(sheet.school || {}, person),
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
      onBehalf
        ? el("div", { class: "banner banner--info", style: "margin-bottom:1.5rem" },
            el("span", { class: "banner__label" }, "On their behalf"),
            el("span", {}, `This is ${sheet.person.first_name} `
                         + `${sheet.person.last_name}'s form, not yours. `
                         + "Anything you save here is recorded in the log as "
                         + "your doing, which is what it is."))
        : null,
      deadlineNote(),
      paperNote(),
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
            // No help text. It said "this decides which tests you may take",
            // which is one of several things it decides and not the delegate's
            // problem -- and a third field with a line under it threw the row
            // of three out of alignment.
            id: "latin", label: "Latin level", required: true,
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
    // `type: "button"`, not "submit". A submit button hands the wait to the
    // form, which cannot disable anything; this one runs `save()` itself, so
    // it disables and shows a spinner in place of its label while the request
    // is out. The form's own submit handler is kept for the Enter key and
    // calls the same function.
    submitButton = button("Save my answers",
                          { variant: "btn--primary", onclick: () => save() });
    unsavedNote = el("p", { class: "form-note", "aria-live": "polite" });

    add(form, el("div", { class: "btn-row" }, submitButton, unsavedNote));
    add(host, form);
    // Now that the boxes exist in the document, close any category that is
    // already at its limit -- somebody returning to a finished sheet must see
    // the same cap as somebody who just reached it.
    for (const category of sheet.catalog) applyCap(category);
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

  /* The paper half, on the delegate's own screen.
   *
   * Two of the three things that make a delegate "complete" are pieces of
   * paper their parent signs, and nothing on this page said whether either had
   * arrived. A delegate who had filled in every box here believed they were
   * done — and their sponsor was looking at a roster that said otherwise.
   *
   * READ ONLY. The sponsor ticks these, because the sponsor is holding the
   * paper. This says where it got to, and who to give it to.
   */
  function paperNote() {
    const paper = sheet.paper || {};
    const forms = [["student_waiver", "Waiver"],
                   ["student_medical", "Medical form"]];
    const outstanding = forms.filter(([key]) => !paper[key]);

    return el("div", { class: "panel", style: "margin-bottom:1.5rem" },
      el("p", { class: "label label--ink" }, "Your paper forms"),
      el("dl", { class: "detail" },
        ...forms.flatMap(([key, label]) => [
          el("dt", {}, label),
          el("dd", {}, paper[key]
            ? el("span", { class: "pill pill--done" }, "✓ Received")
            : el("span", { class: "pill" }, "Not yet")),
        ])),
      el("p", { class: "small muted" },
        outstanding.length
          ? "Your sponsor ticks these off as they reach them. Until both are "
            + "in you are not fully registered, however much of this form you "
            + "have filled in."
          : "Both are in. Nothing further is needed on paper."));
  }

  function deadlineNote() {
    if (!sheet.deadline) return null;
    const when = localDate(sheet.deadline);
    if (!when) return null;
    return el("p", { class: "deadline" },
      `Due ${when}. You can change your answers freely until then.`);
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
      "data-category": category.key,
      "data-item": String(item.id),
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
        applyCap(category);
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

  /* A HARD CAP, in the interface, on a category with a maximum.
   *
   * The database cannot express "no more than three of these" -- a CHECK
   * constraint cannot count rows in another table -- so the server warns and
   * accepts. That is the right server behaviour and the wrong thing to show a
   * fourteen-year-old: a warning they can save straight past reads as advice,
   * and they find out it was not at the convention.
   *
   * The unchosen boxes simply stop responding once the limit is reached.
   * Nothing is taken away and nothing shouts; unticking one frees another.
   * Only `max` is capped. Being UNDER a minimum is fine at any moment -- they
   * are allowed to be half-finished, and most of them are for weeks.
   */
  function applyCap(category) {
    const high = category.max_selections;
    if (!high) return;
    const chosen = category.items.filter((i) => selected.has(i.id)).length;
    const full = chosen >= high;

    for (const item of category.items) {
      const box = document.getElementById(`item-${item.id}`);
      if (!box) continue;
      const isChosen = selected.has(item.id);
      const blocked = !item.eligible_now;
      box.disabled = blocked || sheet.locked || (full && !isChosen);
      const label = box.closest(".choice");
      if (label) label.classList.toggle("choice--capped",
                                        full && !isChosen && !blocked);
    }
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

    /* ONLY BEING UNDER A MINIMUM IS A PROBLEM WORTH COLOURING.
     *
     * Going over a maximum is no longer reachable -- `applyCap` stops the
     * fourth box responding -- so the old "you have 4, this is a suggestion,
     * not a rule" state cannot occur, and saying it would have been a lie
     * anyway now that it IS a rule here.
     *
     * Under a minimum is not coloured either. They are allowed to be
     * half-finished; most of them are, for weeks. The count states the fact
     * and leaves it there. */
    const full = high && chosen >= high;
    note.className = "count-note";
    add(note, text,
        full ? " That is the most you can pick." : null,
        low && chosen < low && enforcement === "warn"
          ? " You can save and come back to this." : null);
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

  /* What is still missing, in the words the delegate would use.
   *
   * Not the same as the server's validation: the server refuses a save with no
   * grade, and accepts one with no events at all, because saving half a sheet
   * in January is the intended way to use this page. This list is about
   * whether their REGISTRATION is finished, which is a different question and
   * one nobody was answering out loud.
   */
  function missing() {
    const gaps = [];
    if (!grade) gaps.push("your grade");
    if (!level) gaps.push("your Latin level");
    if (!meal) gaps.push("a meal choice");
    for (const category of sheet.catalog) {
      const low = category.min_selections;
      if (!low) continue;
      const chosen = category.items.filter((i) => selected.has(i.id)).length;
      if (chosen < low) {
        gaps.push(`at least ${low} in ${category.name} `
                  + `(you have ${chosen})`);
      }
    }
    return gaps;
  }

  async function save() {
    /* ASK BEFORE SAVING AN UNFINISHED SHEET, and say what is unfinished.
     *
     * A delegate who saves a half-filled form and closes the tab believes they
     * have registered. Nothing on the page contradicted them: it said "Saved",
     * which was true and not the thing they wanted to know. */
    const gaps = missing();
    if (gaps.length) {
      const ok = await check({
        title: "Your registration is not complete",
        body: [
          el("p", {}, "You can save this and come back — nothing is lost. But "
                    + "as it stands you are not fully registered, because "
                    + "this is still missing:"),
          el("ul", {}, ...gaps.map((gap) => el("li", {}, gap))),
          el("p", {}, "Your sponsor sees the same thing on their roster."),
        ],
        confirmLabel: "Save anyway",
        cancelLabel: "Go back and finish",
      });
      if (!ok) return;
    }

    errors = [];
    warnings = [];
    try {
      const result = await api.put(base, {
        grade: grade ? Number(grade) : null,
        latin_level: level || null,
        meal: meal || null,
        selected: [...selected],
        selected_options: options,
      });          // the button shows the wait; see ui.js button()

      warnings = result.warnings || [];
      saved = true;
      sheet = await api.get(base);
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

      // And say so when it IS finished. "Saved" in small grey type under a
      // button is not an answer to "am I registered?", which is the only
      // question a delegate actually has.
      if (!gaps.length) {
        const paper = sheet.paper || {};
        const waiting = [["student_waiver", "your waiver"],
                         ["student_medical", "your medical form"]]
          .filter(([key]) => !paper[key]).map(([, label]) => label);

        await tell({
          title: waiting.length ? "This form is done" : "You are registered",
          body: [
            el("p", {}, "Everything this form needs is filled in and saved."),
            waiting.length
              ? el("p", {}, "Still outstanding on paper: "
                          + waiting.join(" and ")
                          + ". Give them to your sponsor — you are not fully "
                          + "registered until both are in.")
              : el("p", {}, "Your waiver and medical form are both in, so "
                          + "there is nothing else to do."),
            el("p", {}, "You can change any of these answers until the "
                      + "deadline."),
          ],
        });
      }
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
