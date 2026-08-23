/* The sponsor's roster.
 *
 * One table of thirty people, from ONE query. Compact enough that thirty rows
 * fit on a laptop without scrolling, and a labelled row-group on a phone rather
 * than a table scrolled sideways.
 */

import * as api from "../api.js";
import {
  el, clear, tabula, table, button, emptyState, loadingRows, fullName,
} from "../ui.js";

export async function rosterPage(host) {
  let data = null;
  let sort = { key: "last_name", direction: "asc" };
  let showCancelled = false;

  host.append(loadingRows(8, "Loading your roster"));
  data = await api.get("/sponsor/roster", { statusHost: host });
  render();

  async function reload() {
    data = await api.get("/sponsor/roster");
    render();
  }

  function render() {
    clear(host);
    const school = data.school;
    const stats = data.stats || {};

    const people = data.people
      .filter((p) => showCancelled || p.status === "active")
      .sort(compare);

    const cancelledCount = data.people.filter((p) => p.status !== "active").length;

    host.append(
      tabula({
        label: "Chapter",
        name: school.name,
        left: `${school.level} · ${school.city || ""}`,
        right: `№  ${String(school.id).padStart(4, "0")}`,
      }),

      el("section", { class: "grid" },
        el("div", { class: "span-8" },
          el("h1", {}, "Roster"),
          el("p", { class: "lede" },
            "Everyone your chapter is bringing. Add people, correct details, " +
            "and mark their paper forms as they come back to you.")),
        el("div", { class: "span-4" },
          el("dl", { class: "detail" },
            el("dt", {}, "Delegates"), el("dd", { class: "mono" }, stats.delegates_active || 0),
            el("dt", {}, "Adults"), el("dd", { class: "mono" }, stats.adults_active || 0),
            el("dt", {}, "Complete"),
            el("dd", { class: "mono" },
              `${(stats.delegates_complete || 0) + (stats.adults_complete || 0)}`)))),

      el("div", { class: "btn-row" },
        el("a", { class: "btn btn--primary", href: "#/roster/import" },
          "Paste a roster"),
        el("a", { class: "btn", href: "#/invoice" }, "View invoice"),
        button("Print packet", { onclick: () => openPrintView("/sponsor/packet") }),
        cancelledCount
          ? button(showCancelled
              ? "Hide cancelled"
              : `Show ${cancelledCount} cancelled`, {
              variant: "btn--quiet",
              onclick: () => { showCancelled = !showCancelled; render(); },
            })
          : null),

      people.length
        ? table(columns(), people, {
            sort,
            onSort: (key) => {
              sort = {
                key,
                direction: sort.key === key && sort.direction === "asc" ? "desc" : "asc",
              };
              render();
            },
            rowClass: (row) => row.status !== "active" ? "is-inactive" : null,
            caption: `Roster for ${school.name}`,
          })
        : emptyState(
            "No delegates yet",
            "Paste your roster to get started. Any format works — a spreadsheet " +
            "column, a numbered list, or one name per line.",
            el("a", { class: "btn btn--primary", href: "#/roster/import" },
              "Paste your roster")),
    );
  }

  function columns() {
    return [
      { key: "name", label: "Name", sortable: true,
        render: (row) => el("span", {},
          fullName(row),
          row.status !== "active"
            ? el("span", { class: "pill", style: "margin-left:.5rem" },
                row.status === "cancelled_paid" ? "Cancelled · paid" : "Cancelled")
            : null,
          row.is_chapter_leader
            ? el("span", { class: "pill pill--done", style: "margin-left:.5rem" },
                "Chapter leader")
            : null) },
      { key: "person_type", label: "Type", sortable: true,
        render: (row) => row.person_type === "delegate"
          ? "Delegate"
          : (row.adult_type || "adult").replace(/^\w/, (c) => c.toUpperCase()) },
      { key: "grade", label: "Grade", num: true,
        render: (row) => row.grade || "—" },
      { key: "latin_level", label: "Latin", render: (row) => row.latin_level || "—" },
      { key: "form_status", label: "Form",
        render: (row) => row.form_status === "submitted"
          ? el("span", { class: "pill pill--done" }, "✓ Submitted")
          : el("span", { class: "pill" }, "Not yet") },
      { key: "paper", label: "Paper forms",
        render: (row) => paperControls(row) },
      { key: "actions", label: "Actions", render: (row) => actions(row) },
    ];
  }

  function paperControls(row) {
    const forms = row.person_type === "delegate"
      ? [["student_waiver", "Waiver", row.waiver_received],
         ["student_medical", "Medical", row.medical_received]]
      : [["adult_medical", "Medical", row.medical_received]];

    return el("span", { style: "display:flex; gap:.75rem; flex-wrap:wrap" },
      ...forms.map(([formType, label, received]) => {
        const box = el("input", {
          type: "checkbox", checked: !!received,
          id: `paper-${row.id}-${formType}`,
          onchange: async (event) => {
            event.target.disabled = true;
            try {
              await api.post("/sponsor/paper-forms", {
                person_id: row.id, form_type: formType,
                received: event.target.checked,
              });
              await reload();
            } catch (error) {
              event.target.checked = !event.target.checked;
              event.target.disabled = false;
              alert(error.message);
            }
          },
        });
        return el("span", { style: "display:inline-flex; gap:.35rem; align-items:center" },
          box, el("label", { for: `paper-${row.id}-${formType}`, class: "small" }, label));
      }));
  }

  function actions(row) {
    const wrap = el("span", { style: "display:flex; gap:.5rem; flex-wrap:wrap" });

    if (row.status === "active") {
      wrap.append(button("New code", {
        variant: "btn--small",
        onclick: () => regenerate(row),
      }));
      if (row.person_type === "delegate") {
        wrap.append(button(row.is_chapter_leader ? "Unset leader" : "Make leader", {
          variant: "btn--small btn--quiet",
          onclick: async () => {
            await api.post(`/sponsor/people/${row.id}/chapter-leader`,
                           { granted: !row.is_chapter_leader });
            await reload();
          },
        }));
      }
      wrap.append(button("Cancel", {
        variant: "btn--small btn--quiet",
        onclick: async () => {
          if (!confirm(`Cancel ${fullName(row)}? They can be restored later.`)) return;
          await api.post(`/sponsor/people/${row.id}/cancel`, {});
          await reload();
        },
      }));
    } else {
      wrap.append(button("Restore", {
        variant: "btn--small",
        onclick: async () => {
          await api.post(`/sponsor/people/${row.id}/restore`, {});
          await reload();
        },
      }));
    }
    return wrap;
  }

  /* Regeneration shows the new code ONCE and immediately offers the reprint.
   * Without the reprint the sponsor is holding a packet page whose QR no longer
   * works, with no obvious way to produce a new one. */
  async function regenerate(row) {
    const name = fullName(row);
    if (!confirm(
      `Issue a new code for ${name}?\n\n` +
      "Their old code and every device signed in with it stop working " +
      "immediately, so you will need to give them the new sheet."
    )) return;

    const result = await api.post(`/sponsor/people/${row.id}/regenerate-code`, {});
    const dialog = el("div", { class: "panel", role: "alertdialog",
                               "aria-label": `New code for ${name}` },
      el("p", { class: "label" }, "New access code"),
      el("p", { class: "tabula__code mono", style: "font-size:1.5rem" }, result.code),
      el("p", {},
        "This is the only time this code is shown. Print the new sheet now and " +
        `give it to ${row.first_name}.`),
      el("div", { class: "btn-row" },
        button("Print their new sheet", {
          variant: "btn--primary",
          onclick: () => openPrintView(`/sponsor/packet?person_id=${row.id}`),
        }),
        button("Done", { onclick: async () => { dialog.remove(); await reload(); } })));

    clear(host);
    host.append(dialog);
  }

  function compare(a, b) {
    const direction = sort.direction === "asc" ? 1 : -1;
    const pick = (row) => {
      if (sort.key === "name") return `${row.last_name} ${row.first_name}`.toLowerCase();
      const value = row[sort.key];
      return value === null || value === undefined ? "" : String(value).toLowerCase();
    };
    // Adults and delegates stay grouped whichever column is sorted, because a
    // sponsor reads the roster as two lists.
    if (a.person_type !== b.person_type) return a.person_type < b.person_type ? -1 : 1;
    return pick(a) < pick(b) ? -direction : pick(a) > pick(b) ? direction : 0;
  }
}

/** Open a server-rendered print view in a new tab, carrying the session token.
 *  The print views are HTML documents, not JSON, so they are fetched and
 *  written into the new window rather than linked -- a plain link would arrive
 *  without the Authorization header. */
export async function openPrintView(path) {
  const target = window.open("", "_blank");
  if (!target) {
    alert("Your browser blocked the print window. Allow pop-ups for this site.");
    return;
  }
  target.document.write("<p style=\"font:14px system-ui;padding:2rem\">Preparing…</p>");
  try {
    const html = await api.getText(path);
    target.document.open();
    target.document.write(html);
    target.document.close();
  } catch (error) {
    target.document.body.textContent = error.message;
  }
}
