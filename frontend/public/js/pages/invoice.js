/* The sponsor's invoice.
 *
 * Every line is shown separately, INCLUDING the free-adult allowance, so the
 * arithmetic is visible rather than magic. A sponsor who cancels a delegate and
 * sees the bill fall by $65 instead of $140 can find the reason here rather than
 * sending an email.
 *
 * An exempt chapter gets an explanation in words, never a blank page.
 */

import * as api from "../api.js";
import { add, el, clear, tabula, table, money, localDate, renderMarkdown, personNumber } from "../ui.js";
import { openPrintView } from "./roster.js";

export async function invoicePage(host) {
  const invoice = await api.get("/sponsor/invoice", { statusHost: host });
  clear(host);

  const school = invoice.school;

  add(host, tabula({
    label: "Chapter",
    name: school.name,
    left: invoice.exempt ? "Nothing due" : money(invoice.balance_cents) + " outstanding",
    right: personNumber(school.id),
  }));

  if (invoice.exempt) {
    add(host, 
      el("h1", {}, "Invoice"),
      renderMarkdown(
        "This chapter is **not billed** for the state convention, so there is " +
        "nothing to pay and no check to send.\n\n" +
        "Your registration is complete once your attendees have finished their " +
        "forms and returned their signed paper waivers and medical forms."),
      el("div", { class: "btn-row" },
        el("a", { class: "btn", href: "#/roster" }, "Back to roster")));
    return;
  }

  add(host, 
    el("section", { class: "grid" },
      el("div", { class: "span-7" },
        el("h1", {}, "Invoice"),
        el("p", { class: "lede" },
          "This updates as your roster changes. Work from this page rather " +
          "than a printed copy."),

        el("div", { class: "totals" },
          ...invoice.lines
            .filter((line) => line.count || line.amount_cents)
            .map((line) => el("div", { class: "totals__row" },
              el("span", {}, line.label,
                line.note ? el("span", { class: "label" }, ` ${line.note}`) : null,
                el("span", { class: "muted mono" }, `  ×${line.count}`)),
              el("span", { class: "mono" },
                line.unit_cents ? money(line.amount_cents) : "included"))),

          invoice.discount_cents
            ? el("div", { class: "totals__row" },
                el("span", {}, "Discount",
                  invoice.discount_reason
                    ? el("span", { class: "label" }, ` ${invoice.discount_reason}`)
                    : null),
                el("span", { class: "mono" }, `−${money(invoice.discount_cents)}`))
            : null,

          el("div", { class: "totals__row" },
            el("span", {}, "Total due"),
            el("span", { class: "mono" }, money(invoice.amount_owed_cents))),
          el("div", { class: "totals__row" },
            el("span", {}, "Received"),
            el("span", { class: "mono" }, money(invoice.amount_paid_cents))),
          el("div", { class: "totals__row totals__row--final" },
            el("span", {}, "Balance"),
            el("span", { class: "mono" }, money(invoice.balance_cents)))),

        invoice.counts.delegates_cancelled_paid
          ? el("p", { class: "field__warning", style: "max-width:34rem" },
              `${invoice.counts.delegates_cancelled_paid} attendee` +
              `${invoice.counts.delegates_cancelled_paid === 1 ? "" : "s"} withdrew ` +
              "after your payment was received. There are no refunds, so they " +
              "remain on this invoice.")
          : null,

        el("div", { class: "btn-row" },
          el("button", {
            class: "btn btn--primary", type: "button",
            onclick: () => openPrintView("/sponsor/invoice.html"),
          }, "Print this invoice"),
          el("a", { class: "btn", href: "#/roster" }, "Back to roster"))),

      el("div", { class: "span-4" },
        el("h2", {}, "Where to send it"),
        el("dl", { class: "detail" },
          el("dt", {}, "Due"), el("dd", {}, invoice.due || "—"),
          el("dt", {}, "Remit to"), el("dd", {}, invoice.remit_to),
          el("dt", {}, "Address"), el("dd", {}, invoice.remit_address)),
        el("hr", { class: "hair" }),
        el("h2", {}, "Payments received"),
        invoice.payments.length
          ? table([
              { key: "received_on", label: "Date",
                render: (row) => localDate(row.received_on || row.created_at) },
              { key: "reference", label: "Reference",
                render: (row) => row.reference || row.method || "—" },
              { key: "amount_cents", label: "Amount", num: true,
                render: (row) => money(row.amount_cents) },
            ], invoice.payments, { caption: "Payments received" })
          : el("p", { class: "muted" }, "Nothing recorded yet."))));
}
