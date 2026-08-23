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
import {
  el, clear, field, input, button, errorSummary, table, localDate, loadingRows,
} from "../ui.js";
import { state } from "../main.js";

export async function adminPage(host) {
  let tab = "settings";
  let settings = null;
  let message = null;
  let errors = [];

  host.append(loadingRows(6, "Loading settings"));
  settings = await api.get("/admin/settings", { statusHost: host });
  render();

  function render() {
    clear(host);
    host.append(
      el("h1", {}, "Convention settings"),
      el("p", { class: "lede" },
        "Everything here can be changed without touching code or redeploying " +
        "anything. Colours, fonts and page layout are the only things that " +
        "still live in the repository."),

      el("nav", { class: "nav", "aria-label": "Settings sections" },
        ...[["settings", "Values"], ["documents", "Printed wording"],
            ["announcements", "Announcements"], ["roles", "Roles"],
            ["ops", "Operations"]].map(([key, label]) => {
          const a = el("a", { href: "#/admin",
            onclick: (e) => { e.preventDefault(); tab = key; message = null; render(); } },
            label);
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

    const pending = {};
    const form = el("form", {
      onsubmit: async (event) => {
        event.preventDefault();
        errors = [];
        try {
          await api.put("/admin/settings", { settings: pending });
          settings = await api.get("/admin/settings");
          message = "Saved. These values are live everywhere on the site.";
          render();
        } catch (error) {
          errors = error.errors && error.errors.length ? error.errors : [error.message];
          render();
        }
      },
    });

    for (const [group, rows] of Object.entries(groups)) {
      form.append(el("fieldset", {},
        el("legend", {}, el("h2", {}, group)),
        el("div", { class: "grid" },
          ...rows.map((row) => el("div", { class: "span-6" }, settingField(row, pending))))));
    }

    form.append(el("div", { class: "btn-row" },
      button("Save settings", { variant: "btn--primary", type: "submit" })));
    host.append(form);
  }

  function settingField(row, pending) {
    const isDate = row.value_type === "datetime";
    const isMoney = row.value_type === "cents";

    // A deadline is entered as a plain California date. The server converts it
    // to the right UTC instant, including working out whether that date is in
    // PST or PDT.
    const control = input({
      type: isDate ? "date" : "text",
      value: isDate ? toDateInput(row.value)
        : isMoney ? (Number(row.value || 0) / 100).toFixed(2)
        : row.value,
      class: isMoney ? "mono" : null,
      oninput: (event) => {
        pending[row.key] = isMoney
          ? String(Math.round(Number(event.target.value || 0) * 100))
          : event.target.value;
      },
    });

    return field({
      id: `set-${row.key}`,
      label: row.label,
      help: isDate ? "A California date. End of that day is used."
        : isMoney ? "In dollars."
        : row.key,
      control,
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
    host.append(el("p", { class: "muted" },
      "Every block of printed or displayed wording. Changing these never " +
      "requires a deploy."));

    for (const document_ of settings.documents) {
      const body = el("textarea", { style: "min-height:12rem" }, document_.body_md);
      host.append(el("section", { class: "panel", style: "margin-bottom:1.5rem" },
        el("h2", {}, document_.title),
        el("p", { class: "label" }, document_.key),
        field({ id: `doc-${document_.key}`, label: "Wording", wide: true,
                help: "Blank lines make paragraphs. **Two asterisks** make bold. " +
                      "A line starting with - makes a bullet.",
                control: body }),
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

    host.append(
      el("section", { class: "panel" },
        el("h2", {}, "Put a banner on every page"),
        el("p", { class: "muted" },
          "For a schedule change, a room change, or anything that cannot wait. " +
          "It appears at the top of every page within a minute."),
        field({ id: "ann-body", label: "What it should say", wide: true,
                required: true, control: body }),
        field({ id: "ann-level", label: "How urgent", control: level }),
        el("div", { class: "btn-row" },
          button("Publish announcement", {
            variant: "btn--primary",
            onclick: async () => {
              if (!body.value.trim()) { errors = ["Write the announcement first."]; render(); return; }
              try {
                await api.post("/admin/announcements", {
                  body_md: body.value, level: level.value, active: true });
                message = "Announcement published.";
                render();
              } catch (error) { errors = [error.message]; render(); }
            },
          }))),
      el("p", { class: "small muted", style: "margin-top:1rem" },
        "If Modal is down entirely, edit frontend/public/announcement.json in " +
        "the GitHub web interface. The static file is the second layer and needs " +
        "no server at all."));

    const existing = await api.get("/admin/announcements");
    if (existing.announcements.length) {
      host.append(el("h2", {}, "Recent announcements"),
        table([
          { key: "body_md", label: "Message" },
          { key: "level", label: "Level" },
          { key: "active", label: "Live",
            render: (row) => row.active ? "Yes" : "No" },
          { key: "created_at", label: "Created",
            render: (row) => localDate(row.created_at) },
        ], existing.announcements, { caption: "Announcements" }));
    }
  }

  /* -------------------------------------------------------------------- */

  async function renderRoles() {
    const roles = await api.get("/admin/roles");
    const key = input({ placeholder: "colloquia_chair" });
    const name = input({ placeholder: "Colloquia Chair" });
    const scopes = ["registration", "academics", "awards", "sponsor",
                    "delegate", "chapter", "*"];
    const chosen = new Set();

    host.append(
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

    host.append(
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
      document.body.append(link);
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
