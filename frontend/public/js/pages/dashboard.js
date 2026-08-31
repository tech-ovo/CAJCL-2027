/* The registration chair dashboard.
 *
 * Fifty schools in one table, served from `school_stats` -- never a COUNT and
 * never a query per row. Sortable, with a visible affordance and aria-sort.
 *
 * Exempt chapters are excluded from the outstanding-balance total so that
 * number stays meaningful: a chair looking at "still owed" wants the figure
 * they can actually chase.
 */

import * as api from "../api.js";
import { add, el, clear, table, button, money, field, input, select, errorSummary, loadingRows, localDate } from "../ui.js";
import { openPrintView } from "./roster.js";

export async function dashboardPage(host) {
  let data = null;
  let sort = { key: "name", direction: "asc" };
  let panel = null;      // the open side panel: payment, or a new chapter

  add(host, loadingRows(10, "Loading chapters"));
  data = await api.get("/admin/registration", { statusHost: host });
  render();

  async function reload() {
    data = await api.get("/admin/registration");
    render();
  }

  function render() {
    clear(host);
    const totals = data.totals;
    const rows = [...data.schools].sort(compare);

    add(host, 
      el("section", { class: "grid" },
        el("div", { class: "span-8" },
          el("h1", {}, "Chapters"),
          el("p", { class: "lede" },
            "How large each chapter is, how far along its attendees are, and " +
            "what it has paid.")),
        el("div", { class: "span-4" },
          el("div", { class: "totals" },
            el("div", { class: "totals__row" },
              el("span", {}, "Chapters"),
              el("span", { class: "mono" }, totals.chapters)),
            el("div", { class: "totals__row" },
              el("span", {}, "Delegates"),
              el("span", { class: "mono" }, totals.delegates)),
            el("div", { class: "totals__row" },
              el("span", {}, "Adults"),
              el("span", { class: "mono" }, totals.adults)),
            el("div", { class: "totals__row" },
              el("span", {}, "Collected"),
              el("span", { class: "mono" }, money(totals.collected_cents))),
            el("div", { class: "totals__row totals__row--final" },
              el("span", {}, "Still owed"),
              el("span", { class: "mono" }, money(totals.outstanding_cents)))))),

      el("div", { class: "btn-row" },
        button("Add a chapter", {
          variant: "btn--primary",
          onclick: () => { panel = { kind: "school" }; render(); },
        })),

      panel ? renderPanel() : null,

      table(columns(), rows, {
        sort,
        onSort: (key) => {
          sort = { key, direction: sort.key === key && sort.direction === "asc"
            ? "desc" : "asc" };
          render();
        },
        rowClass: (row) => row.status === "withdrawn" ? "is-inactive" : null,
        caption: "Registered chapters",
      }));
  }

  function columns() {
    return [
      { key: "name", label: "Chapter", sortable: true,
        render: (row) => el("span", {},
          row.name,
          row.billing_exempt
            ? el("span", { class: "pill", style: "margin-left:.5rem" }, "Not billed")
            : null,
          row.status === "withdrawn"
            ? el("span", { class: "pill", style: "margin-left:.5rem" }, "Withdrawn")
            : null) },
      { key: "level", label: "Level", sortable: true },
      { key: "delegates_active", label: "Delegates", num: true, sortable: true },
      { key: "adults_active", label: "Adults", num: true, sortable: true },
      { key: "delegates_complete", label: "Complete", num: true, sortable: true,
        render: (row) => {
          const done = row.delegates_complete || 0;
          const total = row.delegates_active || 0;
          return el("span", {}, `${done}/${total}`,
            total && done === total
              ? el("span", { class: "pill pill--done", style: "margin-left:.4rem" }, "✓")
              : null);
        } },
      { key: "amount_owed_cents", label: "Owed", num: true, sortable: true,
        render: (row) => money(row.amount_owed_cents) },
      { key: "amount_paid_cents", label: "Paid", num: true, sortable: true,
        render: (row) => money(row.amount_paid_cents) },
      { key: "balance", label: "Balance", num: true, sortable: true,
        render: (row) => row.billing_exempt
          ? el("span", { class: "muted" }, "—")
          : money((row.amount_owed_cents || 0) - (row.amount_paid_cents || 0)) },
      { key: "actions", label: "Actions",
        render: (row) => el("span", { style: "display:flex;gap:.5rem;flex-wrap:wrap" },
          button("Payment", {
            variant: "btn--small",
            onclick: () => { panel = { kind: "payment", school: row }; render(); },
          }),
          // What has already been recorded. A chair about to enter a cheque
          // needs to know whether somebody else entered it this morning, and
          // the balance alone does not say.
          button("Records", {
            variant: "btn--small btn--quiet",
            onclick: () => { panel = { kind: "records", school: row }; render(); },
          }),
          // "Roster" used to open the printable packet, which is not a roster
          // and cannot be edited. It now opens the chapter's actual roster;
          // the packet is its own button, named after what it produces.
          el("a", { class: "btn btn--small", href: `#/roster/${row.id}` },
            "Roster"),
          // A chapter's own details -- its name above all. Created from this
          // page in a hurry, so a typo in one is normal and used to be
          // permanent.
          button("Edit", {
            variant: "btn--small btn--quiet",
            onclick: () => { panel = { kind: "school", school: row }; render(); },
          }),
          button("Packet", {
            variant: "btn--small btn--quiet",
            onclick: () => openPrintView(`/sponsor/packet?school_id=${row.id}`),
          })) },
    ];
  }

  /* ------------------------------------------------------------------ */

  function renderPanel() {
    if (panel.kind === "payment") return paymentPanel(panel.school);
    if (panel.kind === "records") return recordsPanel(panel.school);
    return schoolPanel(panel.school || null);
  }

  function paymentPanel(school) {
    let errors = [];
    // The `$` sits in the field rather than in help text underneath, the same
    // way Settings → Values renders a fee. Help text under a label pushes the
    // input out of line with its neighbours in the grid.
    const amount = input({ inputmode: "decimal", placeholder: "e.g., 2500.00" });
    const reference = input({ placeholder: "Check number" });
    const received = el("input", { type: "date" });
    const note = input({ placeholder: "Anything worth remembering" });

    const wrap = el("div", { class: "panel" });

    function draw() {
      clear(wrap);
      add(wrap, 
        el("h2", {}, `Record a payment from ${school.name}`),
        el("p", { class: "muted" },
          "Enter the exact amount received. Payments are never edited — a " +
          "correction is a new entry, and a refund is a negative one."),
        errors.length ? errorSummary(errors) : null,
        el("div", { class: "grid" },
          el("div", { class: "span-3" },
            field({ id: "amount", label: "Amount", required: true,
                    control: el("span", { class: "input-prefix" },
                                el("span", {}, "$"), amount) })),
          el("div", { class: "span-3" },
            field({ id: "reference", label: "Check number", control: reference })),
          el("div", { class: "span-3" },
            field({ id: "received", label: "Date received", control: received })),
          el("div", { class: "span-3" },
            field({ id: "note", label: "Note", control: note }))),
        el("div", { class: "btn-row" },
          button("Record payment", {
            variant: "btn--primary",
            onclick: async () => {
              errors = [];
              const dollars = Number(String(amount.value).replace(/[$,\s]/g, ""));
              if (!Number.isFinite(dollars) || dollars === 0) {
                errors = ["Enter the amount received, in dollars. " +
                          "A refund is entered as a negative number."];
                draw();
                return;
              }
              try {
                await api.post("/admin/payments", {
                  school_id: school.id,
                  amount_cents: Math.round(dollars * 100),
                  method: "check",
                  reference: reference.value || null,
                  received_on: received.value || null,
                  note: note.value || null,
                });
                panel = null;
                await reload();
              } catch (error) {
                errors = error.errors && error.errors.length
                  ? error.errors : [error.message];
                draw();
              }
            },
          }),
          button("Cancel", { onclick: () => { panel = null; render(); } })));
    }

    draw();
    return wrap;
  }

  /* Every payment recorded against one chapter, and its discount.
   *
   * Payments are APPEND-ONLY: a correction is another row, and a refund is a
   * negative one. That makes this list the answer to "why is the balance
   * that?", which is a question asked in March with somebody's cheque stub in
   * hand, and it is the reason the rows carry who entered each one and when.
   */
  function recordsPanel(school) {
    const wrap = el("div", { class: "panel" });
    add(wrap, el("h2", {}, `Records for ${school.name}`),
              loadingRows(3, "Loading records"));

    api.get(`/admin/payments?school_id=${school.id}`).then((data) => {
      const rows = data.payments || [];
      const paid = rows.reduce((sum, row) => sum + row.amount_cents, 0);

      clear(wrap);
      add(wrap,
        el("h2", {}, `Records for ${school.name}`),

        el("dl", { class: "detail", style: "margin-bottom:var(--space-6)" },
          el("dt", {}, "Owed"),
          el("dd", { class: "mono" }, school.billing_exempt
            ? "Not billed" : money(school.amount_owed_cents)),
          el("dt", {}, "Paid"),
          el("dd", { class: "mono" }, money(paid)),
          el("dt", {}, "Balance"),
          el("dd", { class: "mono" }, school.billing_exempt
            ? "—" : money((school.amount_owed_cents || 0) - paid)),
          ...(school.discount_cents
            ? [el("dt", {}, "Discount"),
               el("dd", {}, el("span", { class: "mono" },
                              money(school.discount_cents)),
                 school.discount_reason
                   ? el("span", { class: "small muted" },
                        ` — ${school.discount_reason}`)
                   : null)]
            : [])),

        rows.length
          ? table([
              { key: "received_on", label: "Received",
                render: (row) => row.received_on
                  ? localDate(row.received_on) : "—" },
              { key: "amount_cents", label: "Amount", num: true,
                render: (row) => el("span", { class: "mono" },
                                    money(row.amount_cents)) },
              { key: "reference", label: "Check", render: (row) => row.reference || "—" },
              { key: "note", label: "Note", render: (row) => row.note || "—" },
              { key: "recorded_by", label: "Recorded by",
                render: (row) => el("span", {},
                  [row.recorded_by_first, row.recorded_by_last]
                    .filter(Boolean).join(" ") || "—",
                  // Two different dates, and a dispute needs both: the day
                  // written on the cheque, and the moment somebody entered it.
                  row.created_at
                    ? el("span", { class: "small muted" },
                        `, ${localDate(row.created_at, { withTime: true })}`)
                    : null) },
            ], rows, { caption: `Payments from ${school.name}` })
          : el("p", { class: "muted" },
               "Nothing recorded yet. A payment entered here would appear in "
               + "this list, and the balance above would move with it."),

        /* WHY THE BALANCE MOVED, not just what arrived.
         *
         * The payments above say what came in. This says what changed the
         * amount OWED — a delegate added, somebody cancelled, a discount
         * applied — which is the half of the argument that was missing when a
         * sponsor rings up in March disagreeing with a figure. Both halves in
         * one place, because the dispute is about the difference between them.
         */
        el("h3", { class: "label label--ink", style: "margin-top:var(--space-6)" },
           "What changed this chapter"),
        historyBlock(school),

        el("div", { class: "btn-row" },
          button("Record a payment", {
            variant: "btn--primary",
            onclick: () => { panel = { kind: "payment", school }; render(); },
          }),
          button("Close", { variant: "btn--quiet",
                            onclick: () => { panel = null; render(); } })));
    }).catch((error) => {
      clear(wrap);
      add(wrap, el("h2", {}, `Records for ${school.name}`),
                errorSummary([error.message]),
                el("div", { class: "btn-row" },
                  button("Close", { variant: "btn--quiet",
                                    onclick: () => { panel = null; render(); } })));
    });

    return wrap;
  }

  /* Fetched separately and drawn where it lands, so a slow second request
   * cannot hold up the payments the panel is mostly opened for. */
  function historyBlock(school) {
    const host_ = el("div", {}, el("p", { class: "muted" }, "Loading…"));

    api.get(`/admin/schools/${school.id}/history`).then((data) => {
      const history = data.history || [];
      clear(host_);
      if (!history.length) {
        add(host_, el("p", { class: "muted" },
          "Nothing recorded yet. Adding people, cancelling them, and changing "
          + "a discount all appear here."));
        return;
      }
      add(host_, el("ul", { class: "history" },
        ...history.map((entry) => el("li", {},
          el("span", { class: "history__when small muted" },
             localDate(entry.ts_utc, { withTime: true })),
          el("span", {}, entry.summary)))));
    }).catch((error) => {
      clear(host_);
      add(host_, el("p", { class: "small muted" },
                    `Could not load the history: ${error.message}`));
    });

    return host_;
  }

  /* Adding a chapter and correcting one are the same six fields.
   *
   * Written as two panels they drift: the create form gains a field, the edit
   * form does not, and the difference is invisible until somebody cannot fix
   * the thing they just typed wrong. `existing` is null when adding.
   */
  function schoolPanel(existing) {
    const editing = existing !== null;
    let errors = [];
    const name = input({ placeholder: "Chapter name",
                         value: editing ? existing.name : "" });
    const city = input({ placeholder: "City", value: editing ? existing.city || "" : "" });
    const level = select([["HS", "High school"], ["MS", "Middle school"]]);
    if (editing) level.value = existing.level;
    const exempt = el("input", { type: "checkbox" });
    if (editing && existing.billing_exempt) exempt.checked = true;
    const discount = input({
      inputmode: "decimal", placeholder: "0.00",
      value: editing && existing.discount_cents
        ? (existing.discount_cents / 100).toFixed(2) : "",
    });
    const reason = input({ value: editing ? existing.discount_reason || "" : "" });

    const wrap = el("div", { class: "panel" });

    function draw() {
      clear(wrap);
      add(wrap, 
        el("h2", {}, editing ? `Edit ${existing.name}` : "Add a chapter"),
        el("p", { class: "muted" },
          editing
            ? "Changing the name changes it everywhere, including on sheets "
              + "printed from now on. Nobody's access code is affected."
            : "A chapter sending both middle and high school delegates "
              + "registers twice, as two chapters with two sponsors."),
        errors.length ? errorSummary(errors) : null,
        el("div", { class: "grid" },
          el("div", { class: "span-5" },
            field({ id: "school-name", label: "Name", required: true, control: name })),
          el("div", { class: "span-4" },
            field({ id: "school-city", label: "City", required: true,
                    control: city })),
          el("div", { class: "span-3" },
            field({ id: "school-level", label: "Level", required: true, control: level })),
          el("div", { class: "span-4" },
            field({ id: "discount", label: "Discount",
                    control: el("span", { class: "input-prefix" },
                                el("span", {}, "$"), discount) })),
          el("div", { class: "span-8" },
            field({ id: "reason", label: "Discount reason", control: reason }))),
        el("label", { class: "choice" }, exempt,
          el("span", {},
            el("span", { class: "choice__name" }, "This chapter is not billed"),
            el("span", { class: "choice__why" },
              "SCL only. Members at large pay like everybody else. An exempt "
              + "chapter still needs accounts and forms."))),
        el("div", { class: "btn-row" },
          button(editing ? "Save changes" : "Add chapter", {
            variant: "btn--primary",
            onclick: async () => {
              errors = [];
              if (!name.value.trim()) { errors = ["Give the chapter a name."]; draw(); return; }
              try {
                const dollars = Number(String(discount.value || 0)
                  .replace(/[$,\s]/g, "")) || 0;
                const body = {
                  name: name.value.trim(), city: city.value.trim(),
                  level: level.value,
                  billing_exempt: exempt.checked,
                  discount_cents: Math.round(dollars * 100),
                  discount_reason: reason.value.trim() || null,
                };
                if (editing) await api.patch(`/admin/schools/${existing.id}`, body);
                else await api.post("/admin/schools", body);
                panel = null;
                await reload();
              } catch (error) {
                errors = error.errors && error.errors.length
                  ? error.errors : [error.message];
                draw();
              }
            },
          }),
          button("Cancel", { onclick: () => { panel = null; render(); } })));
    }

    draw();
    return wrap;
  }

  function compare(a, b) {
    const direction = sort.direction === "asc" ? 1 : -1;
    const pick = (row) => {
      if (sort.key === "balance") {
        return (row.amount_owed_cents || 0) - (row.amount_paid_cents || 0);
      }
      const value = row[sort.key];
      return typeof value === "number" ? value
        : String(value === null || value === undefined ? "" : value).toLowerCase();
    };
    const left = pick(a); const right = pick(b);
    return left < right ? -direction : left > right ? direction : 0;
  }
}
