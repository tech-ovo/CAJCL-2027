/* The sponsor's roster.
 *
 * One table of thirty people, from ONE query. Compact enough that thirty rows
 * fit on a laptop without scrolling, and a labelled row-group on a phone rather
 * than a table scrolled sideways.
 */

import * as api from "../api.js";
import { add, el, clear, tabula, table, button, emptyState, loadingRows,
         fullName, personNumber, ask } from "../ui.js";
import { state, route, hasScope } from "../main.js";

export async function rosterPage(host, params = []) {
  // Set when a chair has opened one chapter from the Chapters table. A sponsor
  // reaching their own roster leaves it null and the server uses their school.
  const schoolId = params[0] ? Number(params[0]) : null;
  const asChair = schoolId !== null;
  const path = asChair ? `/sponsor/roster?school_id=${schoolId}` : "/sponsor/roster";

  let data = null;
  let sort = { key: "last_name", direction: "asc" };
  let showCancelled = false;
  // Who is ticked for a code reissue. Empty until the sponsor turns the mode
  // on, so the roster is not covered in checkboxes for a job most days do not
  // involve.
  let selecting = false;
  const picked = new Set();

  add(host, loadingRows(8, "Loading the roster"));
  data = await api.get(path, { statusHost: host });
  render();

  async function reload() {
    data = await api.get(path);
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

    add(host, 
      tabula({
        label: "Chapter",
        name: school.name,
        left: `${school.level} · ${school.city || ""}`,
        right: personNumber(school.id),
      }),

      asChair
        ? el("p", {}, el("a", { href: "#/dashboard" }, "← All chapters"))
        : null,

      // A chapter with no active sponsor is a real state -- the sponsor
      // cancelled, or the chapter was created before anyone was named -- and it
      // is worth saying out loud, because nobody can sign in to work on it.
      asChair && !sponsorOf(data.people)
        ? el("div", { class: "banner banner--info", style: "margin-bottom:1.5rem" },
            el("span", { class: "banner__label" }, "No sponsor"),
            el("span", {}, "This chapter has no active sponsor, so nobody can "
                         + "manage its roster or receive its invoice. Add one "
                         + "from Settings, or ask the chapter who it should be."))
        : null,

      el("section", { class: "grid" },
        el("div", { class: "span-8" },
          el("h1", {}, asChair ? school.name : "Roster"),
          el("p", { class: "lede" },
            asChair
              ? "Everyone this chapter is bringing. To change a form or paste a "
                + "roster, sign in as the sponsor."
              : "Add people, correct details, and tick each paper form as it "
                + "comes back to you.")),
        el("div", { class: "span-4" },
          el("dl", { class: "detail" },
            el("dt", {}, "Delegates"), el("dd", { class: "mono" }, stats.delegates_active || 0),
            el("dt", {}, "Adults"), el("dd", { class: "mono" }, stats.adults_active || 0),
            el("dt", {}, "Complete"),
            el("dd", { class: "mono" },
              `${(stats.delegates_complete || 0) + (stats.adults_complete || 0)}`)))),

      el("div", { class: "btn-row" },
        asChair ? null : el("a", { class: "btn btn--primary", href: "#/roster/import" },
          "Paste a roster"),
        asChair ? null : el("a", { class: "btn", href: "#/invoice" }, "View invoice"),
        asChair && hasScope("*") && sponsorOf(data.people)
          ? button("Sign in as the sponsor", {
              variant: "btn--primary",
              onclick: () => impersonateSponsor(),
            })
          : null,
        button("Print packet", {
          onclick: () => openPrintView(asChair
            ? `/sponsor/packet?school_id=${schoolId}`
            : "/sponsor/packet"),
        }),
        button(selecting ? "Cancel reissue" : "Issue new codes", {
          variant: selecting ? "btn--quiet" : "",
          onclick: () => {
            selecting = !selecting;
            picked.clear();
            render();
          },
        }),
        cancelledCount
          ? button(showCancelled
              ? "Hide cancelled"
              : `Show ${cancelledCount} cancelled`, {
              variant: "btn--quiet",
              onclick: () => { showCancelled = !showCancelled; render(); },
            })
          : null),

      selecting ? reissueBar(people) : null,

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
            rowClass: (row) => [
              row.status !== "active" ? "is-inactive" : null,
              row.person_type === "adult" ? "is-adult" : null,
            ].filter(Boolean).join(" ") || null,
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

  function reissueBar(people) {
    const active = people.filter((p) => p.status === "active");
    const count = picked.size;

    return el("div", { class: "panel", style: "margin-bottom:1.5rem" },
      el("h2", {}, "Issue new codes"),
      el("p", { class: "muted" },
        "Tick the people whose code has been lost, or who never received a "
        + "sheet. Their old codes stop working at once and every device signed "
        + "in with one is signed out, so leave everybody else alone."),
      el("div", { class: "btn-row" },
        button(`Select all ${active.length}`, {
          variant: "btn--small btn--quiet",
          onclick: () => {
            active.forEach((p) => picked.add(p.id));
            render();
          },
        }),
        button("Clear", {
          variant: "btn--small btn--quiet",
          onclick: () => { picked.clear(); render(); },
        }),
        button(count === 1 ? "Issue 1 new code" : `Issue ${count} new codes`, {
          variant: "btn--primary",
          disabled: count === 0,
          onclick: () => reissue(),
        })));
  }

  /* Shows every new code once, with the print link for exactly those sheets.
   * The codes are not recoverable afterwards -- that is the whole reason this
   * screen exists -- so it does not go away on its own. */
  async function reissue() {
    const ids = [...picked];
    const names = data.people
      .filter((p) => picked.has(p.id))
      .map((p) => fullName(p));

    if (!confirm(
      `Issue new codes for ${ids.length} ${ids.length === 1 ? "person" : "people"}?\n\n`
      + names.slice(0, 10).join("\n")
      + (names.length > 10 ? `\n...and ${names.length - 10} more` : "")
      + "\n\nTheir current codes stop working immediately."
    )) return;

    let result;
    try {
      result = await api.post("/sponsor/regenerate-codes", {
        person_ids: ids, school_id: schoolId || undefined });
    } catch (error) {
      alert(error.message);
      return;
    }

    clear(host);
    add(host, el("section", { class: "panel", role: "alertdialog",
                              "aria-label": "New access codes" },
      el("h2", {}, result.issued.length === 1
        ? "One new access code" : `${result.issued.length} new access codes`),
      el("p", {}, "This is the only time these are shown. Print the sheets "
                + "now — nothing can recover a code after you leave this page."),
      el("table", { class: "table" },
        el("thead", {}, el("tr", {},
          el("th", { scope: "col" }, "Name"),
          el("th", { scope: "col" }, "New code"))),
        el("tbody", {}, ...result.issued.map((row) => el("tr", {},
          el("td", {}, row.name),
          el("td", { class: "mono" }, row.code))))),
      el("div", { class: "btn-row" },
        button("Print these sheets", {
          variant: "btn--primary",
          onclick: () => openPrintView(result.print_url
            + (schoolId ? `&school_id=${schoolId}` : "")),
        }),
        button("Done", {
          onclick: async () => {
            selecting = false;
            picked.clear();
            await reload();
          },
        }))));
  }

  function tickColumn() {
    return {
      key: "pick", label: "Reissue",
      render: (row) => row.status !== "active"
        ? el("span", { class: "muted" }, "—")
        : el("input", {
            type: "checkbox",
            checked: picked.has(row.id),
            "aria-label": `Issue a new code for ${fullName(row)}`,
            onchange: (event) => {
              if (event.target.checked) picked.add(row.id);
              else picked.delete(row.id);
              // Only the bar's count and button state change.
              const bar = host.querySelector(".panel .btn-row");
              if (bar) render();
            },
          }),
    };
  }

  function columns() {
    /* A chair opening a chapter wants to know who is in it and to be able to
     * act. Grade, Latin level, and the two form columns are the sponsor's
     * working state -- a chair reading them can do nothing about any of it, and
     * five extra columns push the actions off the side of the screen.
     *
     * "Type" becomes "Position", because for an adult we can say what they
     * actually are rather than repeating the word "Adult" down the column. */
    const tick = selecting ? [tickColumn()] : [];

    if (asChair) {
      return [
        ...tick,
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
        { key: "position", label: "Position", sortable: true,
          render: (row) => position(row) },
        { key: "actions", label: "Actions", render: (row) => actions(row) },
      ];
    }

    return [
      ...tick,
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
      { key: "grade", label: "Grade", render: (row) => row.grade || "—" },
      { key: "latin_level", label: "Latin", render: (row) => row.latin_level || "—" },
      // "Form" and "Paper forms" sat next to each other and neither said which
      // was which. One is the thing they fill in on this site; the other is the
      // paper that has to reach the sponsor's hands.
      { key: "form_status", label: "Activities",
        render: (row) => row.form_status === "submitted"
          ? el("span", { class: "pill pill--done" }, "✓ Submitted")
          : el("span", { class: "pill" }, "Not yet") },
      { key: "paper", label: "Forms",
        render: (row) => paperControls(row) },
      { key: "actions", label: "Actions", render: (row) => actions(row) },
    ];
  }

  /* What this person is, in the words the convention uses. `adult_type_other`
   * holds the actual title for a board member -- "Registration Chair" beats
   * "Other" for anyone reading the list. */
  function position(row) {
    if (row.person_type === "delegate") return "Delegate";
    if (row.adult_type_other) return row.adult_type_other;
    return {
      sponsor: "Sponsor", chaperone: "Chaperone", scl: "SCL",
    }[row.adult_type] || "Adult";
  }

  /* Impersonation needs the admin's own code typed again. That step-up is the
   * point: a walked-away laptop should not be one click from reading a
   * chapter's roster as its sponsor. */
  function sponsorOf(people) {
    return (people || []).find(
      (p) => p.person_type === "adult" && p.adult_type === "sponsor"
             && p.status === "active") || null;
  }

  async function impersonateSponsor() {
    const sponsor = sponsorOf(data.people);
    if (!sponsor) return;

    const code = await ask({
      title: `Sign in as ${fullName(sponsor)}`,
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
        target_person_id: sponsor.id, admin_code: code.trim() });
      // Keep the admin's own token so the banner's Stop button can restore it.
      api.adminToken.set(api.token.get());
      api.token.set(result.token);
      state.me = null;
      location.hash = "#/roster";
      await route();
    } catch (error) {
      alert(error.message);
    }
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
      add(wrap, button("New code", {
        variant: "btn--small",
        onclick: () => regenerate(row),
      }));
      if (row.person_type === "delegate") {
        add(wrap, button(row.is_chapter_leader ? "Unset leader" : "Make leader", {
          variant: "btn--small btn--quiet",
          onclick: async () => {
            await api.post(`/sponsor/people/${row.id}/chapter-leader`,
                           { granted: !row.is_chapter_leader });
            await reload();
          },
        }));
      }
      add(wrap, button("Cancel", {
        variant: "btn--small btn--danger",
        onclick: async () => {
          if (!confirm(`Cancel ${fullName(row)}? They can be restored later.`)) return;
          await api.post(`/sponsor/people/${row.id}/cancel`, {});
          await reload();
        },
      }));
    } else {
      add(wrap, button("Restore", {
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
    add(host, dialog);
  }

  function compare(a, b) {
    const direction = sort.direction === "asc" ? 1 : -1;
    const pick = (row) => {
      if (sort.key === "name") return `${row.last_name} ${row.first_name}`.toLowerCase();
      // "Position" is computed, not stored -- row.position does not exist, so
      // sorting on it compared "" against "" and left the order untouched.
      if (sort.key === "position") return position(row).toLowerCase();
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
