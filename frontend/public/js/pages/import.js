/* Paste a roster: preview, correct inline, then commit once.
 *
 * This is the most visible part of the demo and the part a board will judge, so
 * the behaviour matters more here than anywhere else on the site.
 *
 * ACCEPT ANY FORMAT. Sponsors paste from a spreadsheet with tabs, from Word
 * with bullets and numbering, from an email with commas, `Last, First` in some
 * rows and `First Last` in the next.
 *
 * PARSING NEVER WRITES. The preview is editable and nothing is stored until the
 * sponsor confirms.
 *
 * THE COMMIT IS IDEMPOTENT. The button disables on click and the request
 * carries the key issued with the preview, so a double-click, a flaky
 * connection, and an impatient refresh all produce exactly one roster.
 */

import * as api from "../api.js";
import { add, el, clear, field, button, errorSummary, table, emptyState } from "../ui.js";

/* Warning copy. Warnings must be rare enough that a sponsor reads them --
 * flagging every third row teaches people to click through without looking. */
const WARNINGS = {
  multi_token_name: "Four or more names — check which is the surname.",
  single_token_name: "Only one name. Add a surname, or confirm it is correct.",
  duplicate_in_paste: "The same name appears twice in this paste.",
  duplicate_in_roster: "Someone with this name is already on your roster.",
  unexpected_character: "This line held an unusual or invisible character.",
  email_discarded: "Email removed — we never collect delegates' email addresses.",
  ambiguous_delimiter: "Several columns here. Check the fields are in the right place.",
  possible_header_row: "This looks like a header row rather than a person.",
};

const MEALS = [["", "—"], ["regular", "Regular"],
               ["vegetarian", "Vegetarian"], ["gluten_free", "Gluten free"]];

export async function importPage(host) {
  const roster = await api.get("/sponsor/roster", { statusHost: host });
  const school = roster.school;
  const levels = school.level === "MS"
    ? ["MS-1", "MS-2", "MS-3"]
    : ["HS-1", "HS-2", "HS-3", "HS-Adv"];
  const grades = school.level === "MS" ? [6, 7, 8] : [9, 10, 11, 12];

  let text = "";
  let preview = null;
  let personType = "delegate";
  let errors = [];
  let committing = false;

  renderPaste();

  /* -------------------------------------------------------------------- */

  function renderPaste() {
    clear(host);

    const area = el("textarea", {
      class: "paste", id: "paste",
      placeholder: "Chen, Timothy Wei\nde la Cruz, Mary Beth\nRobert McDonald Jr.\n" +
                   "Smith,John,9,HS-1",
      oninput: (event) => { text = event.target.value; },
    });
    area.value = text;

    const typeChoice = el("div", { class: "field" },
      el("span", { class: "field__label" }, "These people are"),
      el("div", { class: "choices choices--two" },
        radio("delegate", "Delegates"),
        radio("adult", "Adults — sponsors and chaperones")));

    function radio(value, label) {
      return el("label", { class: "choice" },
        el("input", {
          type: "radio", name: "person-type", value,
          checked: personType === value,
          onchange: () => { personType = value; },
        }),
        el("span", { class: "choice__name" }, label));
    }

    add(host, 
      el("section", { class: "with-rail" },
        el("div", { class: "rail" },
          el("p", { class: "label" }, "Chapter"),
          el("p", { class: "small" }, school.name),
          el("p", { class: "label" }, "Currently"),
          el("p", { class: "small muted" },
            `${roster.people.filter((p) => p.status === "active").length} on the roster`)),

        el("div", {},
          el("h1", {}, "Paste your roster"),
          el("p", { class: "lede" },
            "One name per line. Paste straight from a spreadsheet, a document, " +
            "or an email — tabs, commas, bullets and numbering are all handled."),

          errors.length ? errorSummary(errors) : null,

          typeChoice,
          field({
            id: "paste",
            label: "Names",
            help: "You will see exactly what will be added before anything is " +
                  "saved, and you can correct it there.",
            control: area,
            wide: true,
          }),

          el("div", { class: "btn-row" },
            button("Preview these names", {
              variant: "btn--primary",
              onclick: async () => {
                errors = [];
                if (!text.trim()) {
                  errors = ["Paste some names first."];
                  renderPaste();
                  return;
                }
                try {
                  preview = await api.post("/sponsor/roster/parse",
                    { text, person_type: personType }, { statusHost: host });
                  renderPreview();
                } catch (error) {
                  errors = error.errors && error.errors.length
                    ? error.errors : [error.message];
                  renderPaste();
                }
              },
            }),
            el("a", { class: "btn", href: "#/roster" }, "Back to roster")),

          el("hr", { class: "hair" }),
          el("details", {},
            el("summary", { class: "label" }, "What this understands"),
            el("ul", { class: "small muted" },
              el("li", {}, "Last, First — and First Last, in the same paste"),
              el("li", {}, "Tabs from a spreadsheet, commas from an email"),
              el("li", {}, "Bullets and 1. 2. 3. numbering, which are stripped"),
              el("li", {}, "Grade and Latin level in any column, including last " +
                           "year's spellings like AP Latin"),
              el("li", {}, "Particles: de la Cruz and van der Berg stay whole"))))));
  }

  /* -------------------------------------------------------------------- */

  function renderPreview() {
    clear(host);
    const rows = preview.rows;
    const flagged = rows.filter((r) => r.warnings.length).length;

    add(host, 
      el("h1", {}, `Check these ${rows.length} ${rows.length === 1 ? "person" : "people"}`),
      el("p", { class: "lede" },
        "Nothing has been saved yet. Correct anything that is wrong, then " +
        "confirm at the bottom."),

      flagged
        ? el("p", { class: "field__warning", style: "max-width:34rem" },
            `${flagged} ${flagged === 1 ? "row needs" : "rows need"} a look. ` +
            "Everything else parsed cleanly.")
        : el("p", { class: "muted" }, "Every line parsed cleanly."),

      errors.length ? errorSummary(errors) : null,

      rows.length
        ? table(previewColumns(), rows, {
            rowClass: (row) => row.warnings.length ? "is-flagged" : null,
            caption: "Names to be added",
          })
        : emptyState("Nothing to add", "No names were found in that paste."),

      el("div", { class: "btn-row" },
        button(`Add ${rows.length} ${rows.length === 1 ? "person" : "people"}`, {
          variant: "btn--primary",
          id: "commit",
          disabled: !rows.length,
          onclick: commit,
        }),
        button("Start over", {
          onclick: () => { preview = null; errors = []; renderPaste(); },
        })),

      el("p", { class: "small muted" },
        "Each person is given their own access code. You will be able to print " +
        "their sheets from the roster."));
  }

  function previewColumns() {
    const cell = (row, key, control) => control;

    return [
      { key: "type", label: "Type",
        render: (row) => selectFor(row, "person_type",
          [["delegate", "Delegate"], ["adult", "Adult"]]) },
      { key: "first_name", label: "First",
        render: (row) => textFor(row, "first_name") },
      { key: "middle_name", label: "Middle",
        render: (row) => textFor(row, "middle_name") },
      { key: "last_name", label: "Last",
        render: (row) => textFor(row, "last_name") },
      { key: "suffix", label: "Suffix",
        render: (row) => textFor(row, "suffix", { size: 4 }) },
      { key: "grade", label: "Grade",
        render: (row) => row.person_type === "delegate"
          ? selectFor(row, "grade", [["", "—"], ...grades.map((g) => [g, g])])
          : el("span", { class: "muted" }, "—") },
      { key: "latin_level", label: "Latin",
        render: (row) => row.person_type === "delegate"
          ? selectFor(row, "latin_level", [["", "—"], ...levels.map((l) => [l, l])])
          : el("span", { class: "muted" }, "—") },
      { key: "meal", label: "Meal", render: (row) => selectFor(row, "meal", MEALS) },
      { key: "guardian_name", label: "Parent or guardian",
        render: (row) => row.person_type === "delegate"
          ? textFor(row, "guardian_name")
          : el("span", { class: "muted" }, "—") },
      { key: "guardian_phone", label: "Their phone",
        render: (row) => row.person_type === "delegate"
          ? textFor(row, "guardian_phone")
          : el("span", { class: "muted" }, "—") },
      { key: "warnings", label: "Check", render: (row) => warningsFor(row) },
    ];
  }

  function textFor(row, key, { size } = {}) {
    return el("input", {
      type: "text", value: row[key] || "", size: size || 10,
      "aria-label": key.replace(/_/g, " "),
      oninput: (event) => { row[key] = event.target.value; },
    });
  }

  function selectFor(row, key, options) {
    return el("select", {
      "aria-label": key.replace(/_/g, " "),
      onchange: (event) => {
        row[key] = event.target.value || null;
        if (key === "person_type") renderPreview();
      },
    }, ...options.map(([value, label]) =>
      el("option", {
        value,
        selected: String(row[key] === null || row[key] === undefined
                         ? "" : row[key]) === String(value),
      }, label)));
  }

  function warningsFor(row) {
    if (!row.warnings.length) return el("span", { class: "muted" }, "—");
    return el("span", {},
      ...row.warnings.map((code) => el("span", { class: "choice__why" },
        WARNINGS[code] || code)),
      button("Dismiss", {
        variant: "btn--small btn--quiet",
        onclick: () => { row.warnings = []; renderPreview(); },
      }));
  }

  /* -------------------------------------------------------------------- */

  async function commit() {
    if (committing) return;          // the first half of the double-click guard
    committing = true;

    const commitButton = document.getElementById("commit");
    if (commitButton) {
      commitButton.disabled = true;
      commitButton.textContent = "Adding…";
    }

    try {
      // The second and load-bearing half: the key was issued with the preview
      // and is UNIQUE in the database. Even if this request is sent twice, the
      // roster is created once.
      const result = await api.post("/sponsor/roster/commit", {
        text,
        idempotency_key: preview.idempotency_key,
        rows: preview.rows,
      });

      clear(host);
      add(host, 
        el("h1", {}, result.already_committed
          ? "Already added"
          : `Added ${result.committed_count} ` +
            `${result.committed_count === 1 ? "person" : "people"}`),
        el("p", { class: "lede" }, result.already_committed
          ? "This roster was already saved, so nothing was added twice."
          : "Everyone now has an access code. Print their sheets and hand each " +
            "one to the person named on it."),
        el("div", { class: "btn-row" },
          el("a", { class: "btn btn--primary", href: "#/roster" }, "Go to roster")));
    } catch (error) {
      committing = false;
      errors = error.errors && error.errors.length ? error.errors : [error.message];
      renderPreview();
    }
  }
}
