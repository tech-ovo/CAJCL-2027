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
import { add, el, clear, field, input, button, errorSummary, table,
         localDate, loadingRows, guardUnsaved, ask } from "../ui.js";
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
            ["announcements", "Announcements"], ["roles", "Roles"],
            ["ops", "Operations"]].map(([key, label]) => {
          const a = el("a", { href: "#/admin", onclick: (e) => {
            e.preventDefault();
            // Leaving the Values tab abandons whatever is typed into it just
            // as surely as leaving the page does.
            if (tab === "settings" && key !== "settings"
                && Object.keys(pending).length
                && !confirm("You have unsaved changes to the convention "
                          + "settings.\n\nLeave this tab and lose them?")) {
              return;
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
    else if (tab === "roles") renderRoles();
    else renderOps();
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
          "For a schedule change, a room change, or anything that cannot wait. "
          + "It appears at the top of every page, for everybody, the next time "
          + "they load or move between pages — so within seconds for "
          + "anyone using the site, and immediately for anyone arriving."),
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
                button("Rename", {
                  variant: "btn--small btn--quiet",
                  onclick: () => renamePerson(row),
                }),
                button("Roles", {
                  variant: "btn--small",
                  onclick: () => editRoles(row, roles.roles),
                })) },
          ], board.people, { caption: "Board members and their roles" })
        : el("p", { class: "muted" }, "Nobody has been given a role yet."),
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
  async function editRoles(person, allRoles) {
    const held = new Set((person.role_keys || "").split(",").filter(Boolean));
    const name = `${person.first_name} ${person.last_name}`;

    const boxes = allRoles.map((role) => el("label", { class: "choice" },
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
              .filter((r) => held.has(r.key)).map((r) => r.name);
            person.role_keys = [...held].join(",");
            person.role_names = names.join(",");
            repaint(person.id, "roles", names.join(", ") || "—");
          } catch (error) {
            event.target.checked = !event.target.checked;
            event.target.disabled = false;
            alert(error.message);
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
      el("p", { class: "small muted" },
        "Somebody who has left the board keeps their account and their code "
        + "— they are a real person who may still be a sponsor or a "
        + "delegate. Take away the roles and you have taken away the powers."),
      el("div", { class: "btn-row" },
        button("Remove every role", {
          variant: "btn--quiet btn--danger",
          onclick: async () => {
            if (!held.size) return;
            if (!confirm(
              `Remove every role from ${name}?

`
              + "Their account and their code keep working. They simply lose "
              + "the powers those roles carried.")) return;
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

    add(host, 
      el("section", { class: "grid" },
        el("div", { class: "span-6" },
          el("h2", {}, "Keep the server warm"),
          el("p", { class: "muted" },
            "The server sleeps when nobody is using it, which is what keeps it " +
            "free. Before a live event, keep it awake so nobody waits."),
          el("dl", { class: "detail" },
            el("dt", {}, "Warm until"),
            el("dd", { class: "mono" },
              warm.warm_until ? localDate(warm.warm_until, { withTime: true }) : "Not warm")),
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
            button("Let it sleep", {
              onclick: async () => {
                await api.put("/admin/warm", { hours: 0 });
                message = "Containers will sleep when idle.";
                render();
              },
            }))),

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
                      if (!confirm(
                        "Erase everything and rebuild the demonstration data?\n\n" +
                        "This drops every table. It is only possible because " +
                        "this database is flagged as demonstration data."
                      )) return;
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
