/* Settings, prose, announcements, roles, warmth, impersonation, and the demo
 * reset.
 *
 * THIS PAGE IS WHAT MAKES THE SITE INHERITABLE. Every value a future
 * commissioner would otherwise need a deploy to change lives here: convention
 * facts, fee amounts, deadlines, the warm window, printed prose, the
 * announcement banner, and role provisioning.
 *
 * Deadlines are entered as a CALIFORNIA DATE and converted server-side. Nobody
 * hand-types a UTC string -- see backend/lib/clock.py for what goes wrong.
 */

import * as api from "../api.js";
import { add, el, clear, field, input, select, button, errorSummary, table,
         localDate, loadingRows, guardUnsaved, ask, check,
         tell } from "../ui.js";
import { state, route, adopt, hasScope } from "../main.js";

export async function adminPage(host) {
  let tab = "settings";
  let settings = null;
  let message = null;
  let errors = [];

  /* Edits typed into the Values tab and not yet saved.
   *
   * It lives out here rather than inside renderSettings so the leave-warning
   * can see it. A key is REMOVED when the field is typed back to its stored
   * value, so undoing an edit really does clear the warning rather than
   * leaving the form permanently "dirty" after one keystroke. */
  let pending = {};

  add(host, loadingRows(6, "Loading settings"));
  settings = await api.get("/admin/settings", { statusHost: host });
  render();
  guardUnsaved(() => Object.keys(pending).length > 0,
               "unsaved changes to the convention settings");

  function render() {
    clear(host);
    add(host, 
      el("h1", {}, "Convention settings"),
      el("p", { class: "lede" },
        "Everything here changes without a deploy. Colours, fonts and page " +
        "layout are the only things that still live in the repository."),

      el("nav", { class: "nav", "aria-label": "Settings sections" },
        ...[["settings", "Values"], ["documents", "Printed wording"],
            ["announcements", "Announcements"], ["catalog", "Catalog"],
            ["roles", "Roles"],
            ["ops", "Operations"]].map(([key, label]) => {
          const a = el("a", { href: "#/admin", onclick: async (e) => {
            e.preventDefault();
            // Leaving the Values tab abandons whatever is typed into it just
            // as surely as leaving the page does.
            if (tab === "settings" && key !== "settings"
                && Object.keys(pending).length) {
              const ok = await check({
                title: "Leave this tab and lose your changes?",
                body: "You have unsaved changes to the convention settings.",
                confirmLabel: "Leave and lose them",
                cancelLabel: "Stay here", danger: true,
              });
              if (!ok) return;
            }
            if (key !== "settings") pending = {};
            tab = key;
            message = null;
            render();
          } }, label);
          if (tab === key) a.setAttribute("aria-current", "page");
          return a;
        })),

      message ? el("div", { class: "form-errors", role: "status" },
        el("h2", {}, message)) : null,
      errors.length ? errorSummary(errors) : null,
    );

    if (tab === "settings") renderSettings();
    else if (tab === "documents") renderDocuments();
    else if (tab === "announcements") renderAnnouncements();
    else if (tab === "catalog") renderCatalog();
    else if (tab === "roles") renderRoles();
    else renderOps();
  }


  /* ---------------------------------------------------------------------
   * Catalog
   * ------------------------------------------------------------------ */

  /* WHAT THIS PAGE IS FOR, in one line from docs/structure.md: "adding a new
   * ludus for 2028 should require no code."
   *
   * Until this existed, a new test or event meant a migration, a deploy, and
   * somebody who knew what a migration was — which, in a system handed to
   * different students every year, is the same as not being possible.
   *
   * CATEGORIES ARE NOT CREATED HERE, and that is deliberate. A category
   * carries the rules a form is validated against: how many you must pick,
   * whether that is a hard block or a warning. Inventing one from a text box
   * is how a delegate ends up unable to submit for a reason nobody can find.
   * Adding a category stays a migration; adding things TO one does not.
   */
  const LATIN_LEVELS = ["MS-1", "MS-2", "MS-3", "HS-1", "HS-2", "HS-3", "HS-Adv"];
  const SCHOOL_LEVELS = ["MS", "HS"];

  async function renderCatalog() {
    const data = await api.get("/admin/catalog");
    const optionsByItem = new Map();
    for (const option of data.options || []) {
      if (!optionsByItem.has(option.item_id)) optionsByItem.set(option.item_id, []);
      optionsByItem.get(option.item_id).push(option);
    }

    add(host,
      el("h2", {}, "Tests, events and activities"),
      el("p", { class: "muted" },
        "Everything a delegate can enter. Changes take effect at once — a "
        + "delegate with the form already open sees them the next time they "
        + "load it."),
      el("p", { class: "small muted" },
        "Categories and their rules — how many you must pick, and whether "
        + "that is a block or a warning — are set in a migration, because a "
        + "wrong rule stops delegates submitting for a reason nobody can "
        + "find. Everything inside a category is editable here."),

      ...data.categories.map((category) => categoryBlock(category, optionsByItem)));
  }

  function categoryBlock(category, optionsByItem) {
    const rule = category.min_selections || category.max_selections
      ? `${describeRule(category)} · ${category.enforcement === "block"
          ? "enforced" : "a suggestion"}`
      : "No limit on how many.";

    return el("section", { class: "panel", style: "margin-bottom:1.5rem" },
      el("div", { class: "tabula__row" },
        el("h3", {}, category.name),
        el("span", { class: "label" }, category.applies_to === "adult"
          ? "Adults" : "Delegates")),
      el("p", { class: "small muted" }, rule),

      category.items.length
        ? el("div", { class: "catalog-items" },
            ...category.items.map((item) =>
              itemRow(item, optionsByItem.get(item.id) || [])))
        : el("p", { class: "muted" }, "Nothing in this category yet."),

      el("div", { class: "btn-row" },
        button("Add to this category", {
          variant: "btn--small",
          onclick: () => addItem(category),
        })));
  }

  function describeRule(category) {
    const low = category.min_selections;
    const high = category.max_selections;
    if (low && high) return `Choose between ${low} and ${high}.`;
    if (low) return `Choose at least ${low}.`;
    return `Choose no more than ${high}.`;
  }

  function itemRow(item, allOptions) {
    const facts = [
      item.eligible_latin_levels && item.eligible_latin_levels.length
        ? item.eligible_latin_levels.join(", ") : "Any Latin level",
      item.eligible_school_levels && item.eligible_school_levels.length
        ? item.eligible_school_levels.join(", ") : null,
      item.registration_scope === "chapter" ? "Entered by the chapter" : null,
      item.min_latin_knowledge ? `Needs ${item.min_latin_knowledge} Latin` : null,
      item.max_sub_selections
        ? `Up to ${item.max_sub_selections} sub-choices` : null,
    ].filter(Boolean);

    return el("div", { class: "catalog-item" },
      el("div", {},
        el("span", { class: "catalog-item__name" }, item.name),
        item.active ? null : el("span", { class: "pill", style: "margin-left:.5rem" },
                                "Not offered"),
        el("span", { class: "choice__why" }, facts.join(" · ")),
        allOptions.length
          ? el("span", { class: "choice__why" },
              "Sub-choices: "
              + allOptions.map((o) => o.active ? o.name : `${o.name} (off)`)
                          .join(", "))
          : null),
      el("span", { style: "display:flex;gap:.5rem;flex-wrap:wrap" },
        button("Edit", {
          variant: "btn--small btn--quiet",
          onclick: () => editItem(item),
        }),
        item.max_sub_selections
          ? button("Sub-choices", {
              variant: "btn--small btn--quiet",
              onclick: () => editOptions(item, allOptions),
            })
          : null,
        button(item.active ? "Stop offering" : "Offer again", {
          variant: item.active ? "btn--small btn--quiet btn--danger"
                               : "btn--small btn--quiet",
          onclick: () => setItemActive(item, !item.active),
        })));
  }

  /* The same fields whether adding or editing, for the same reason the chapter
   * panel is one form: written twice they drift, and the difference only shows
   * up when somebody cannot correct the thing they just typed. */
  function itemFields(item) {
    const name = input({ id: "cat-name", value: item ? item.name : "" });
    const description = input({ id: "cat-desc",
                                value: item ? item.description || "" : "" });
    const latin = el("div", { class: "choices choices--two" });
    const school = el("div", { class: "choices choices--two" });
    const subs = input({ id: "cat-subs", type: "number", min: "0", max: "12",
                         value: item && item.max_sub_selections
                           ? String(item.max_sub_selections) : "" });
    const chapter = el("input", { type: "checkbox" });
    if (item && item.registration_scope === "chapter") chapter.checked = true;

    const chosenLatin = new Set(item && item.eligible_latin_levels
      ? item.eligible_latin_levels : []);
    for (const level of LATIN_LEVELS) {
      const box = el("input", { type: "checkbox", checked: chosenLatin.has(level),
        onchange: (event) => {
          if (event.target.checked) chosenLatin.add(level);
          else chosenLatin.delete(level);
        } });
      add(latin, el("label", { class: "choice" }, box,
                    el("span", {}, el("span", { class: "choice__name" }, level))));
    }

    const chosenSchool = new Set(item && item.eligible_school_levels
      ? item.eligible_school_levels : []);
    for (const level of SCHOOL_LEVELS) {
      const box = el("input", { type: "checkbox", checked: chosenSchool.has(level),
        onchange: (event) => {
          if (event.target.checked) chosenSchool.add(level);
          else chosenSchool.delete(level);
        } });
      add(school, el("label", { class: "choice" }, box,
                     el("span", {}, el("span", { class: "choice__name" },
                        level === "MS" ? "Middle school" : "High school"))));
    }

    return {
      name, description, subs, chapter, chosenLatin, chosenSchool,
      body: [
        field({ id: "cat-name", label: "Name", control: name, wide: true }),
        field({ id: "cat-desc", label: "Description", control: description,
                wide: true, help: "Shown under the name on the form. Optional." }),
        el("p", { class: "label label--ink" }, "Open to which Latin levels"),
        el("p", { class: "small muted" },
          "Leave all unticked for any level. Ticking some hides it from "
          + "everybody else, which is how Grammar 1 and Grammar 3 stay apart."),
        latin,
        el("p", { class: "label label--ink" }, "Open to which school levels"),
        el("p", { class: "small muted" }, "Leave both unticked for either."),
        school,
        field({ id: "cat-subs", label: "Sub-choices allowed", control: subs,
                wide: true,
                help: "How many sub-choices somebody may pick — a medium under "
                    + "Drawing/Painting. Leave empty for none." }),
        el("label", { class: "choice" }, chapter,
          el("span", {},
            el("span", { class: "choice__name" }, "Entered by the chapter"),
            el("span", { class: "choice__why" },
              "For team events. A chapter enters these from its Teams page; a "
              + "delegate does not see them on their own form."))),
      ],
    };
  }

  function itemPayload(fields) {
    return {
      name: fields.name.value.trim(),
      description: fields.description.value.trim() || null,
      eligible_latin_levels: [...fields.chosenLatin],
      eligible_school_levels: [...fields.chosenSchool],
      registration_scope: fields.chapter.checked ? "chapter" : "individual",
      max_sub_selections: fields.subs.value ? Number(fields.subs.value) : null,
    };
  }

  async function addItem(category) {
    const fields = itemFields(null);
    const ok = await check({
      title: `Add to ${category.name}`,
      body: fields.body,
      confirmLabel: "Add it",
    });
    if (!ok) return;
    if (!fields.name.value.trim()) {
      await tell({ title: "That needs a name",
                   body: "Give it a name, then try again." });
      return;
    }
    try {
      await api.post("/admin/catalog/items",
                     { ...itemPayload(fields), category_id: category.id });
      message = `${fields.name.value.trim()} added to ${category.name}.`;
      render();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  async function editItem(item) {
    const fields = itemFields(item);
    const ok = await check({
      title: `Edit ${item.name}`,
      body: fields.body,
      confirmLabel: "Save",
    });
    if (!ok) return;
    try {
      await api.put(`/admin/catalog/items/${item.id}`, itemPayload(fields));
      message = `${fields.name.value.trim()} saved.`;
      render();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  /* NOT OFFERED, NEVER DELETED. Somebody may already have chosen it, and a
   * delete would either fail on the foreign key or quietly take their entry
   * with it. "Stop offering" is what retiring an event actually means. */
  async function setItemActive(item, active) {
    if (!active) {
      const ok = await check({
        title: `Stop offering ${item.name}?`,
        body: ["Nobody will be able to choose it from now on. Anybody who has "
               + "already chosen it keeps their entry, and the chairs still "
               + "see them in the counts.",
               "You can offer it again at any time."],
        confirmLabel: "Stop offering it", danger: true,
      });
      if (!ok) return;
    }
    try {
      await api.put(`/admin/catalog/items/${item.id}`, { active });
      message = active ? `${item.name} is offered again.`
                       : `${item.name} is no longer offered.`;
      render();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  async function editOptions(item, existing) {
    const fresh = input({ id: "opt-new" });
    const rows = el("div", {});

    for (const option of existing) {
      add(rows, el("div", { class: "catalog-item" },
        el("span", {}, option.name,
          option.active ? null
            : el("span", { class: "pill", style: "margin-left:.5rem" }, "Off")),
        button(option.active ? "Stop offering" : "Offer again", {
          variant: "btn--small btn--quiet",
          onclick: async () => {
            try {
              await api.put(`/admin/catalog/options/${option.id}`,
                            { active: !option.active });
              message = `${option.name} updated.`;
              render();
            } catch (error) { await tell({ body: error.message }); }
          },
        })));
    }

    const ok = await check({
      title: `Sub-choices for ${item.name}`,
      body: [
        el("p", {}, `Somebody entering ${item.name} may pick up to `
                  + `${item.max_sub_selections} of these.`),
        existing.length ? rows : el("p", { class: "muted" }, "None yet."),
        field({ id: "opt-new", label: "Add one", control: fresh, wide: true }),
      ],
      confirmLabel: "Add it",
      cancelLabel: "Done",
    });
    if (!ok || !fresh.value.trim()) return;

    try {
      await api.post(`/admin/catalog/items/${item.id}/options`,
                     { name: fresh.value.trim() });
      message = `${fresh.value.trim()} added to ${item.name}.`;
      render();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  /* -------------------------------------------------------------------- */

  function renderSettings() {
    const groups = {};
    for (const row of settings.settings) {
      if (row.key.startsWith("ops.")) continue;   // Operations tab owns these
      if (!groups[row.group_name]) groups[row.group_name] = [];
      groups[row.group_name].push(row);
    }

    const form = el("form", {
      onsubmit: async (event) => {
        event.preventDefault();
        errors = [];
        try {
          const count = Object.keys(pending).length;
          if (!count) { message = "Nothing had changed."; render(); return; }
          await api.put("/admin/settings", { settings: pending });
          settings = await api.get("/admin/settings");
          pending = {};
          message = count === 1
            ? "Saved. That value is live everywhere on the site."
            : `Saved ${count} values. They are live everywhere on the site.`;
          render();
        } catch (error) {
          errors = error.errors && error.errors.length ? error.errors : [error.message];
          render();
        }
      },
    });

    for (const [group, rows] of Object.entries(groups)) {
      add(form, el("fieldset", {},
        el("legend", {}, el("h2", {}, group)),
        el("div", { class: "grid" },
          ...rows.map((row) => el("div", { class: "span-6" }, settingField(row))))));
    }

    add(form, el("div", { class: "btn-row" },
      button("Save settings", { variant: "btn--primary", type: "submit" })));
    add(host, form);
  }

  function settingField(row) {
    // The SERVER says how to render this; see settings.render_hint. The
    // convention's first and last day used to arrive as plain text purely
    // because they are stored as strings, so the two dates everybody actually
    // knows were the only ones you had to type by hand.
    const hint = row.render_as || "text";
    const isDeadline = hint === "deadline";
    const isDate = hint === "date";
    const isMoney = hint === "money";

    // `shown` is what this field displays untouched, and what every keystroke
    // is compared against -- so typing a change and typing it back removes the
    // entry rather than leaving the form permanently unsaved.
    const shown = isDeadline ? toDateInput(row.value)
      : isMoney ? (Number(row.value || 0) / 100).toFixed(2)
      : (row.value === null || row.value === undefined ? "" : String(row.value));

    const control = input({
      type: (isDeadline || isDate) ? "date" : "text",
      value: shown,
      class: isMoney ? "mono" : null,
      oninput: (event) => {
        if (event.target.value === shown) {
          delete pending[row.key];
          return;
        }
        pending[row.key] = isMoney
          ? String(Math.round(Number(event.target.value || 0) * 100))
          : event.target.value;
      },
    });

    return field({
      id: `set-${row.key}`,
      label: row.label,
      // A dollar sign in front of the box says "dollars" without a sentence
      // underneath saying it. The help line below a field is for something a
      // person could not work out by looking.
      help: isDeadline ? "The end of this day, California time." : null,
      control: isMoney
        ? el("span", { class: "input-prefix" }, el("span", {}, "$"), control)
        : control,
    });
  }

  function toDateInput(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    // Render the CALIFORNIA date, not the browser's, so a commissioner in a
    // different time zone still sees February 13.
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Los_Angeles",
      year: "numeric", month: "2-digit", day: "2-digit",
    }).format(date);
    return parts;
  }

  /* -------------------------------------------------------------------- */

  function renderDocuments() {
    add(host,
      el("p", { class: "muted" },
        "Every block of wording that gets printed or displayed."),
      // Said once, at the top. It used to sit under all nine boxes, which is
      // eight repetitions of the same sentence and a column of identical
      // "WORDING" labels doing no work: the heading above each box already
      // says which document it is.
      el("p", { class: "small muted" },
        "Blank lines make paragraphs. ",
        el("strong", {}, "**Two asterisks**"), " make bold. ",
        "A line starting with - makes a bullet."));

    for (const document_ of settings.documents) {
      const body = el("textarea", {
        id: `doc-${document_.key}`,
        "aria-label": document_.title,
        style: "min-height:12rem",
      }, document_.body_md);
      add(host, el("section", { class: "panel", style: "margin-bottom:1.5rem" },
        el("h2", {}, document_.title),
        body,
        el("div", { class: "btn-row" },
          button("Save wording", {
            variant: "btn--primary",
            onclick: async () => {
              try {
                await api.put(`/admin/documents/${document_.key}`, {
                  title: document_.title, body_md: body.value });
                message = `Saved the ${document_.title.toLowerCase()}.`;
                settings = await api.get("/admin/settings");
                render();
              } catch (error) { errors = [error.message]; render(); }
            },
          }))));
    }
  }

  /* -------------------------------------------------------------------- */

  async function renderAnnouncements() {
    const body = el("textarea", { placeholder:
      "Certamen has moved to the gym. Follow the signs from the quad." });
    const level = el("select", {},
      el("option", { value: "info" }, "Notice"),
      el("option", { value: "warning" }, "Important"),
      el("option", { value: "critical" }, "Urgent"));
    const until = input({ type: "date" });

    add(host, 
      el("section", { class: "panel" },
        el("h2", {}, "Put a banner on every page"),
        el("p", { class: "muted" },
          // NOTHING POLLS. There is no background request anywhere on this
          // site asking whether an announcement has appeared, so a page
          // already open stays as it is until the person using it does
          // something. Saying "within seconds" promised a mechanism that does
          // not exist, which is the worst thing to be wrong about on the one
          // screen used when something has gone wrong.
          "For a schedule change, a room change, or anything that cannot wait. "
          + "It appears at the top of every page for anyone arriving, and for "
          + "anyone already on the site the next time they move between "
          + "pages. A page sitting open and untouched will not change on its "
          + "own — so this reaches people as they use the site, not the "
          + "instant you save it."),
        field({ id: "ann-body", label: "What it should say", wide: true,
                required: true, control: body }),
        el("div", { class: "grid" },
          el("div", { class: "span-6" },
            field({ id: "ann-level", label: "How urgent", control: level })),
          el("div", { class: "span-6" },
            field({ id: "ann-until", label: "Take it down after",
                    help: "Optional. A California date; it disappears at the "
                        + "end of that day whether or not anyone remembers.",
                    control: until }))),
        el("div", { class: "btn-row" },
          button("Publish announcement", {
            variant: "btn--primary",
            onclick: async () => {
              if (!body.value.trim()) { errors = ["Write the announcement first."]; render(); return; }
              try {
                await api.post("/admin/announcements", {
                  body_md: body.value, level: level.value, active: true,
                  ends_at: until.value || null });
                message = until.value
                  ? `Published. It comes down after ${until.value}.`
                  : "Published. It stays up until you take it down.";
                render();
              } catch (error) { errors = [error.message]; render(); }
            },
          }))),
      el("p", { class: "small muted", style: "margin-top:1rem" },
        "If the server is down entirely, edit ",
        el("a", {
          href: "https://github.com/tech-ovo/CAJCL-2027/edit/main/frontend/public/announcement.json",
          target: "_blank", rel: "noreferrer",
        }, "announcement.json"),
        " on GitHub and commit it. That file is the second layer: it is part " +
        "of the site itself, so it shows even with nothing running behind it."));

    const existing = await api.get("/admin/announcements");
    if (existing.announcements.length) {
      add(host, el("h2", {}, "Recent announcements"),
        table([
          { key: "body_md", label: "Message" },
          { key: "level", label: "Level" },
          { key: "active", label: "Live",
            render: (row) => row.active
              ? el("span", { class: "pill pill--done" }, "On screen")
              : el("span", { class: "pill" }, "Down") },
          { key: "ends_at", label: "Comes down",
            render: (row) => row.ends_at ? localDate(row.ends_at) : "—" },
          { key: "created_at", label: "Created",
            render: (row) => localDate(row.created_at) },
          { key: "actions", label: "Actions",
            render: (row) => button(row.active ? "Take down" : "Put back up", {
              variant: row.active ? "btn--small btn--danger" : "btn--small",
              onclick: async (event) => {
                event.target.disabled = true;
                try {
                  await api.post(`/admin/announcements/${row.id}/active`,
                                 { active: !row.active });
                  message = row.active
                    ? "Taken down. It is gone from every page."
                    : "Back up on every page.";
                  render();
                } catch (error) {
                  event.target.disabled = false;
                  errors = [error.message];
                  render();
                }
              },
            }) },
        ], existing.announcements, { caption: "Announcements" }));
    }
  }

  /* -------------------------------------------------------------------- */

  /* One cell per person per field, kept so a single change can repaint a
   * single cell.
   *
   * Renaming used to call render(), which threw away the whole Settings page
   * and fetched every section again -- so correcting one surname looked like a
   * page load and, for a second, like nothing had happened at all. */
  const cells = new Map();

  function cell(row, field, text) {
    const node = el("span", {}, text);
    cells.set(`${row.id}.${field}`, node);
    return node;
  }

  function repaint(personId, field, text) {
    const node = cells.get(`${personId}.${field}`);
    if (!node) return false;
    clear(node);
    add(node, text);
    // Brief, and only on the thing that changed. Long enough to be seen,
    // short enough not to be a feature.
    node.classList.add("just-changed");
    setTimeout(() => node.classList.remove("just-changed"), 1200);
    return true;
  }

  async function renderRoles() {
    const roles = await api.get("/admin/roles");
    const board = await api.get("/admin/board");
    cells.clear();

    add(host,
      el("h2", {}, "Who holds what"),
      el("p", { class: "muted" },
        "Everyone with a role beyond delegate or chapter leader. Changes take "
        + "effect the next time that person loads a page — there is no "
        + "second code and nothing to reissue. To retire somebody from the "
        + "board, remove their roles: they keep the account and the code they "
        + "still need as a sponsor or a delegate."),
      board.people.length
        ? table([
            { key: "name", label: "Name",
              render: (row) => cell(row, "name",
                `${row.first_name} ${row.last_name}`) },
            { key: "board_title", label: "Position",
              render: (row) => cell(row, "position",
                row.board_title || row.adult_type_other || "—") },
            { key: "school_name", label: "Chapter" },
            { key: "role_names", label: "Roles",
              render: (row) => cell(row, "roles",
                (row.role_names || "").split(",").filter(Boolean).join(", ")
                  || "—") },
            { key: "actions", label: "Actions",
              render: (row) => el("span",
                { style: "display:flex;gap:.5rem;flex-wrap:wrap" },
                // "Rename" hid the fact that this is also where a board
                // POSITION is set — the one field the roles dialog next door
                // deliberately does not touch.
                button("Name & position", {
                  variant: "btn--small btn--quiet",
                  onclick: () => renamePerson(row),
                }),
                button("Roles", {
                  variant: "btn--small",
                  onclick: () => editRoles(row, roles.roles),
                })) },
          ], board.people, { caption: "Board members and their roles" })
        : el("p", { class: "muted" }, "Nobody has been given a role yet."),

      el("div", { style: "height:var(--space-6)" }),

      /* GRANTING A ROLE TO SOMEBODY WHO HAS NONE.
       *
       * The table above lists people who already hold one, which made it a
       * list you could edit and never add to — so the first role anybody got
       * had to come from a script. A new academics chair is a delegate at
       * their own chapter until somebody says otherwise, and that is the
       * common case, not the exception.
       */
      el("section", { class: "panel", style: "margin-bottom:1.5rem" },
        el("h2", {}, "Give somebody their first role"),
        el("p", { class: "muted" },
          "Anybody on any roster. They keep their own code and their own "
          + "registration; the role is granted on top."),
        grantForm(roles.roles)),

      el("hr", { class: "hair" }));

    const key = input({ placeholder: "colloquia_chair" });
    const name = input({ placeholder: "Colloquia Chair" });
    const scopes = ["registration", "academics", "awards", "sponsor",
                    "delegate", "chapter", "*"];
    const chosen = new Set();

    add(host, 
      el("h2", {}, "Roles"),
      el("p", { class: "muted" },
        "A scope reaches a person only through a role. Create a role with the " +
        "combination a new chair needs, then grant it to their account."),
      table([
        { key: "name", label: "Role" },
        { key: "key", label: "Key" },
        { key: "scopes", label: "Scopes" },
        { key: "is_system", label: "Built in",
          render: (row) => row.is_system ? "Yes" : "No" },
      ], roles.roles, { caption: "Roles" }),

      el("section", { class: "panel" },
        el("h2", {}, "Create a role"),
        el("div", { class: "grid" },
          el("div", { class: "span-5" },
            field({ id: "role-key", label: "Key", required: true,
                    help: "Lowercase, no spaces.", control: key })),
          el("div", { class: "span-7" },
            field({ id: "role-name", label: "Name", required: true, control: name }))),
        el("fieldset", {},
          el("legend", { class: "field__label" }, "Scopes"),
          el("div", { class: "choices choices--two" },
            ...scopes.map((scope) => el("label", { class: "choice" },
              el("input", { type: "checkbox",
                onchange: (e) => e.target.checked ? chosen.add(scope) : chosen.delete(scope) }),
              el("span", {},
                el("span", { class: "choice__name" }, scope),
                el("span", { class: "choice__why" }, describeScope(scope))))))),
        el("div", { class: "btn-row" },
          button("Create role", {
            variant: "btn--primary",
            onclick: async () => {
              try {
                await api.post("/admin/roles", {
                  key: key.value, name: name.value, scopes: [...chosen] });
                message = `Created the role ${name.value}.`;
                render();
              } catch (error) {
                errors = error.errors && error.errors.length
                  ? error.errors : [error.message];
                render();
              }
            },
          }))));
  }

  /* Roles are toggled one at a time against the endpoint that already exists.
   * There is no bulk save: each grant and each revoke is its own audited
   * action, which is what makes the log readable six months later. */
  /* Pick a chapter, then a person from it, then open the roles dialog.
   *
   * A person id would have been one field instead of two, and it is what the
   * impersonation form asks for — but that number is printed on a sheet the
   * chair granting a role has never seen. Two dropdowns beat asking somebody
   * to go and find a number. */
  function grantForm(allRoles) {
    const chapter = select([["", "Choose a chapter…"]], { id: "grant-school" });
    const who = select([["", "Choose a chapter first"]], { id: "grant-person" });
    who.disabled = true;
    let people = [];

    api.get("/admin/schools").then((data) => {
      for (const school of data.schools) {
        add(chapter, el("option", { value: String(school.id) }, school.name));
      }
    }).catch(() => { /* the error surfaces when they try to use it */ });

    chapter.onchange = async () => {
      who.disabled = true;
      clear(who);
      add(who, el("option", { value: "" }, "Loading…"));
      if (!chapter.value) {
        clear(who);
        add(who, el("option", { value: "" }, "Choose a chapter first"));
        return;
      }
      try {
        const data = await api.get(`/admin/people?school_id=${chapter.value}`);
        people = data.people.filter((person) => person.status === "active");
        clear(who);
        add(who, el("option", { value: "" },
                    people.length ? "Choose a person…" : "Nobody on this roster"));
        for (const person of people) {
          add(who, el("option", { value: String(person.id) },
                      `${person.first_name} ${person.last_name}`));
        }
        who.disabled = !people.length;
      } catch (error) {
        clear(who);
        add(who, el("option", { value: "" }, error.message));
      }
    };

    return el("div", {},
      el("div", { class: "grid" },
        el("div", { class: "span-6" },
          field({ id: "grant-school", label: "Chapter", control: chapter })),
        el("div", { class: "span-6" },
          field({ id: "grant-person", label: "Person", control: who }))),
      el("div", { class: "btn-row" },
        button("Choose their roles", {
          variant: "btn--primary",
          onclick: async () => {
            const person = people.find((row) => String(row.id) === who.value);
            if (!person) {
              await tell({ title: "Pick somebody first",
                           body: "Choose a chapter, then a person on it." });
              return;
            }
            await editRoles(person, allRoles);
          },
        })));
  }

  /* IDENTITY ROLES ARE NOT GRANTED FROM HERE.
   *
   * `sponsor`, `delegate` and `chapter_leader` say what somebody IS, and they
   * follow from the roster: a sponsor is a sponsor because their person row is
   * an adult of that type, and a chapter leader is set from the roster where
   * the delegate can be seen. Ticking "Sponsor" here would have given a
   * fourteen-year-old delegate a sponsor's scope over their own chapter while
   * their row still said delegate — two records disagreeing about the same
   * person, which is the shape of every authorisation bug worth having.
   *
   * What is left is exactly what this screen is for: the convention roles a
   * board appoints.
   */
  const IDENTITY_ROLES = new Set(["sponsor", "delegate", "chapter_leader"]);

  async function editRoles(person, allRoles) {
    const held = new Set((person.role_keys || "").split(",").filter(Boolean));
    const name = `${person.first_name} ${person.last_name}`;
    const grantable = allRoles.filter((role) => !IDENTITY_ROLES.has(role.key));

    const boxes = grantable.map((role) => el("label", { class: "choice" },
      el("input", {
        type: "checkbox", checked: held.has(role.key),
        onchange: async (event) => {
          event.target.disabled = true;
          try {
            await api.post(`/admin/people/${person.id}/roles`, {
              role_key: role.key, granted: event.target.checked });
            event.target.disabled = false;
            if (event.target.checked) held.add(role.key);
            else held.delete(role.key);
            // Keep the row behind the dialog honest, so closing it does not
            // reveal a stale list.
            const names = allRoles
              .filter((one) => held.has(one.key)).map((one) => one.name);
            person.role_keys = [...held].join(",");
            person.role_names = names.join(",");
            repaint(person.id, "roles", names.join(", ") || "—");
          } catch (error) {
            event.target.checked = !event.target.checked;
            event.target.disabled = false;
            await tell({ body: error.message });
          }
        },
      }),
      el("span", {},
        el("span", { class: "choice__name" }, role.name),
        el("span", { class: "choice__why" }, role.description || role.key))));

    const panel = el("form", { method: "dialog" },
      el("h2", {}, `Roles for ${name}`),
      el("p", { class: "muted" },
        "Each change is saved as you make it, and each one is logged."),
      el("div", { class: "choices choices--two" }, ...boxes),
      el("p", { class: "small muted", style: "margin-top:1.25rem" },
        "Sponsor, delegate and chapter leader are not here. Those say what "
        + "somebody IS and follow from the roster — a chapter leader is set on "
        + "the chapter's own roster, where you can see who they are."),
      el("p", { class: "small muted" },
        "Somebody who has left the board keeps their account and their code "
        + "— they are a real person who may still be a sponsor or a "
        + "delegate. Take away the roles and you have taken away the powers."),
      el("div", { class: "btn-row" },
        button("Remove every role", {
          variant: "btn--quiet btn--danger",
          onclick: async () => {
            if (!held.size) return;
            const ok = await check({
              title: `Remove every role from ${name}?`,
              body: "Their account and their code keep working. They simply "
                    + "lose the powers those roles carried.",
              confirmLabel: "Remove them all", danger: true,
            });
            if (!ok) return;
            for (const box of boxes) {
              const input_ = box.querySelector("input");
              if (input_.checked) {
                input_.checked = false;
                input_.dispatchEvent(new Event("change"));
              }
            }
          },
        }),
        button("Done", { variant: "btn--primary",
                         onclick: () => dialog.close() })));

    const dialog = el("dialog", { class: "dialog" }, panel);
    dialog.addEventListener("close", () => dialog.remove());
    add(document.body, dialog);
    dialog.showModal();
  }

  /* The same step-up the roster uses: the admin's own code, typed again, into
   * a masked field. A walked-away laptop should not be one click from reading
   * the site as somebody else. */
  async function viewAs(person) {
    const name = `${person.first_name} ${person.last_name}`;
    const code = await ask({
      title: `Sign in as ${name}`,
      body: "You will see exactly what they see, read-only, for thirty "
          + "minutes. Both names appear in a banner on every page, and this is "
          + "recorded in the log.",
      label: "Your own access code",
      confirmLabel: "Sign in as them",
      secret: true,
    });
    if (!code) return;

    try {
      const result = await api.post("/auth/impersonate", {
        target_person_id: person.id, admin_code: code.trim() });
      api.adminToken.set(api.token.get());
      api.token.set(result.token);
      adopt(result.person);
      // Somewhere they can actually open: a registration chair has no roster
      // of their own, and a delegate has no settings page.
      location.hash = hasScope("*") ? "#/admin" : "#/";
      await route();
    } catch (error) {
      errors = [error.message];
      render();
    }
  }

  /* One dialog with three fields, not three prompts in a row. Chained prompts
   * meant cancelling the third silently discarded the first two, and none of
   * them showed whose name was being corrected. */
  function renamePerson(person) {
    const first = input({ value: person.first_name || "" });
    const last = input({ value: person.last_name || "" });
    const title = input({ value: person.board_title || person.adult_type_other || "" });
    let save = false;

    const form = el("form", { method: "dialog" });
    add(form,
      el("h2", {}, `Correct ${person.first_name} ${person.last_name}`),
      field({ id: "ren-first", label: "First name", required: true, control: first }),
      field({ id: "ren-last", label: "Last name", required: true, control: last }),
      field({ id: "ren-title", label: "Position",
              help: "Shown on their access sheet and in this list.",
              control: title }),
      el("div", { class: "btn-row" },
        button("Save", { variant: "btn--primary", type: "submit",
                         onclick: () => { save = true; } }),
        button("Cancel", { variant: "btn--quiet",
                           onclick: () => { save = false; dialog.close(); } })));

    const dialog = el("dialog", { class: "dialog" }, form);
    dialog.addEventListener("close", async () => {
      dialog.remove();
      if (!save) return;

      const name = `${first.value.trim()} ${last.value.trim()}`;
      const position = title.value.trim();

      // Show it immediately. One field changed, so one field is repainted --
      // the request goes out behind it and only the failure is disruptive.
      const painted = repaint(person.id, "name", name)
                    & repaint(person.id, "position", position || "—");

      try {
        await api.patch(`/admin/people/${person.id}/name`, {
          first_name: first.value, last_name: last.value,
          board_title: title.value });
        person.first_name = first.value.trim();
        person.last_name = last.value.trim();
        person.board_title = position;
        if (!painted) render();          // the row was not on screen after all
      } catch (error) {
        // Put back what the server still believes, then say why.
        repaint(person.id, "name", `${person.first_name} ${person.last_name}`);
        repaint(person.id, "position", person.adult_type_other || "—");
        errors = error.errors && error.errors.length
          ? error.errors : [error.message];
        render();
      }
    });

    add(document.body, dialog);
    dialog.showModal();
    first.focus();
  }

  function describeScope(scope) {
    return {
      "*": "Everything, including the audit log, exports, roles, impersonation, " +
           "and the Drive folder links.",
      registration: "Rosters, chapters, payments, check-in.",
      academics: "Tests and activities, contests, grading, Certamen.",
      awards: "Score entry, test printing, tabulation.",
      sponsor: "One chapter's roster. Always limited to their own school.",
      delegate: "Their own activity sheet.",
      chapter: "Chapter team entries for their own school.",
    }[scope] || "";
  }

  /* -------------------------------------------------------------------- */

  async function renderOps() {
    const warm = await api.get("/admin/warm");
    const hours = input({ type: "number", value: "6", min: "0", max: "72" });

    /* IS IT WARM NOW, not "is there a date in this column".
     *
     * `warm_until` keeps its last value after it passes, so the panel went on
     * reporting "Warm until 2:00 PM" long after two o'clock, next to a "Let it
     * sleep" button that would have done nothing. Both are about a state the
     * server is no longer in. */
    const until = warm.warm_until ? new Date(warm.warm_until) : null;
    const isWarm = !!until && until.getTime() > Date.now();

    add(host, 
      el("section", { class: "grid" },
        el("div", { class: "span-6" },
          el("h2", {}, "Keep the server warm"),
          el("p", { class: "muted" },
            "The server sleeps when nobody is using it, which is what keeps it " +
            "free. Before a live event, keep it awake so nobody waits."),
          el("dl", { class: "detail" },
            el("dt", {}, "Right now"),
            el("dd", {}, isWarm
              ? el("span", {},
                  el("span", { class: "pill pill--done" }, "Awake"),
                  el("span", { class: "small muted" },
                    ` until ${localDate(warm.warm_until, { withTime: true })}`))
              : el("span", { class: "pill" }, "Sleeping when idle"))),
          field({ id: "warm-hours", label: "Keep warm for", help: "Hours from now.",
                  control: hours }),
          el("div", { class: "btn-row" },
            button("Keep warm", {
              variant: "btn--primary",
              onclick: async () => {
                await api.put("/admin/warm", { hours: Number(hours.value) });
                message = `Containers will stay warm for ${hours.value} hours.`;
                render();
              },
            }),
            // Only offered when there is something to stop. Pressing it while
            // the server is already sleeping did nothing and looked broken.
            isWarm
              ? button("Let it sleep", {
                  onclick: async () => {
                    await api.put("/admin/warm", { hours: 0 });
                    message = "Containers will sleep when idle.";
                    render();
                  },
                })
              : null)),

        el("div", { class: "span-6" },
          el("h2", {}, "Database quota"),
          el("p", { class: "muted" },
            "Exceeding the read quota does not slow the site down — it stops "
            + "answering, and no amount of money fixes that during a "
            + "convention. This is the early warning."),
          quotaBlock(),
          el("p", { class: "small muted" },
            "Reads are the one to watch. A row read is a row SCANNED, not a "
            + "row returned, which is why every list on this site is one "
            + "indexed query and no total is ever counted live.")),

        el("div", { class: "span-6" },
          el("h2", {}, "Impersonate someone"),
          el("p", { class: "muted" },
            "Open a read-only view of exactly what another person sees. You will " +
            "be asked for your own code, and both names appear in a banner on " +
            "every page and in the log."),
          impersonateForm(),

          el("hr", { class: "rule" }),
          el("h2", {}, "Export everything"),
          el("p", { class: "muted" },
            "Downloads immediately. The full files contain names and guardian " +
            "contact details; the anonymised ones do not, and are the ones you " +
            "can share or hand to someone helping out."),
          el("div", { class: "btn-row" },
            button("Full SQL", { onclick: () => download("sql", false) }),
            button("Full Excel", { onclick: () => download("xlsx", false) }),
            button("Anonymised SQL", { variant: "btn--quiet",
                                       onclick: () => download("sql", true) }),
            button("Anonymised Excel", { variant: "btn--quiet",
                                         onclick: () => download("xlsx", true) })),

          el("hr", { class: "rule" }),
          el("h2", {}, "Demonstration data"),
          state.demoMode
            ? el("div", {},
                el("p", { class: "muted" },
                  "This database holds invented data. Resetting rebuilds it " +
                  "exactly as it started — useful if a demo goes sideways."),
                el("div", { class: "btn-row" },
                  button("Reset demo data", {
                    variant: "btn--danger",
                    onclick: async () => {
                      const ok = await check({
                        title: "Erase everything and rebuild the "
                               + "demonstration data?",
                        body: "This drops every table. It is only possible "
                              + "because this database is flagged as "
                              + "demonstration data.",
                        confirmLabel: "Erase and rebuild", danger: true,
                      });
                      if (!ok) return;
                      await api.post("/admin/demo/reset", {});
                      message = "Demonstration data rebuilt. New codes were issued.";
                      render();
                    },
                  })))
            : el("p", { class: "muted" },
                "This database is not flagged as demonstration data, so the " +
                "reset is disabled."))));
  }

  /* The export arrives as a real file rather than a link, because the request
   * needs the Authorization header and a plain <a href> cannot carry one. */
  async function download(format, anonymized) {
    message = "Preparing the export…";
    render();
    try {
      const response = await fetch(
        (window.CAJCL_CONFIG.apiBase || "") + "/admin/export",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api.token.get(),
          },
          body: JSON.stringify({ format, anonymized }),
        });
      if (!response.ok) throw new Error("The export failed. Try again.");

      const disposition = response.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="([^"]+)"/);
      const blob = await response.blob();

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = match ? match[1] : `cajcl-export.${format}`;
      add(document.body, link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);

      message = `Downloaded the ${anonymized ? "anonymised" : "full"} ` +
                `${format.toUpperCase()} export.`;
    } catch (error) {
      errors = [error.message];
    }
    render();
  }

  /* What Turso has counted this month, against the free tier.
   *
   * Fetched on its own and drawn where it lands: it is one call to somebody
   * else's API, over the network, from a page that is already useful without
   * it. A failure leaves a sentence rather than taking Operations down.
   */
  function quotaBlock() {
    const host_ = el("div", {}, el("p", { class: "muted" }, "Checking…"));

    api.get("/admin/usage").then((usage) => {
      clear(host_);
      if (usage.configured === false) {
        add(host_, el("p", { class: "small" }, usage.message),
                   el("p", {}, el("a", { href: usage.dashboard, target: "_blank",
                                         rel: "noopener noreferrer" },
                                  "Open the database dashboard")));
        return;
      }
      if (usage.error) {
        add(host_, el("p", { class: "form-note form-note--unsaved" }, usage.error),
                   el("p", {}, el("a", { href: usage.dashboard, target: "_blank",
                                         rel: "noopener noreferrer" },
                                  "Open the database dashboard")));
        return;
      }

      const rows = [
        ["Rows read", usage.rows_read, usage.percent.rows_read, "500,000,000"],
        ["Rows written", usage.rows_written, usage.percent.rows_written,
         "10,000,000"],
        ["Storage", `${(usage.storage_bytes / 1024 ** 3).toFixed(2)} GB`,
         usage.percent.storage, "5 GB"],
      ];

      add(host_, el("div", { class: "totals" },
        ...rows.map(([label, value, percent, ceiling]) =>
          el("div", { class: "totals__row" },
            el("span", {}, label,
              el("span", { class: "small muted" }, ` of ${ceiling}`)),
            el("span", { class: "mono" },
              typeof value === "number" ? value.toLocaleString("en-US") : value,
              // Colour would be the obvious thing and would be the only
              // signal; the number and the word carry it instead.
              el("span", { class: percent >= 80 ? "pill" : "small muted" },
                 `  ${percent}%`))))));
    }).catch((error) => {
      clear(host_);
      add(host_, el("p", { class: "form-note form-note--unsaved" },
                    `Could not read the quota: ${error.message}`));
    });

    return host_;
  }

  function impersonateForm() {
    const personId = input({ type: "number", placeholder: "Person ID" });
    const code = input({ class: "mono", placeholder: "Your own code" });

    return el("div", {},
      field({ id: "imp-person", label: "Person ID", control: personId,
              help: "The number printed on their sheet." }),
      field({ id: "imp-code", label: "Re-enter your own code", control: code,
              help: "Proves it is you at the keyboard, not someone who found " +
                    "your laptop unlocked." }),
      el("div", { class: "btn-row" },
        button("View as this person", {
          onclick: async () => {
            errors = [];
            try {
              const result = await api.post("/auth/impersonate", {
                target_person_id: Number(personId.value),
                admin_code: code.value,
              });
              // Keep the admin's own session so ending impersonation returns to
              // it rather than signing them out.
              api.adminToken.set(api.token.get());
              api.token.set(result.token);
              state.me = null;
              location.hash = "#/";
              location.reload();
            } catch (error) {
              errors = [error.message];
              render();
            }
          },
        })));
  }
}
