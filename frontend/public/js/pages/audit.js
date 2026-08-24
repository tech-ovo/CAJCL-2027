/* The audit log.
 *
 * Every entry is a complete sentence written when the change happened, so this
 * page reads without any knowledge of the code behind it. That is the whole
 * design: a future commissioner works out what happened by reading English.
 *
 * Paginated by keyset, not OFFSET. OFFSET makes page fifty scan every row
 * before it, which is how a log viewer quietly becomes the most expensive page
 * on the site.
 */

import * as api from "../api.js";
import { add, el, clear, table, button, localDate, loadingRows, emptyState } from "../ui.js";

export async function auditPage(host) {
  let entries = [];
  let cursor = null;
  let done = false;

  add(host, loadingRows(10, "Loading the log"));
  await loadMore(true);

  async function loadMore(first = false) {
    const query = cursor ? `?cursor=${cursor}` : "";
    const page = await api.get(`/admin/audit${query}`,
                               first ? { statusHost: host } : {});
    entries = entries.concat(page.entries);
    cursor = page.next_cursor;
    done = !cursor;
    render();
  }

  function render() {
    clear(host);
    add(host, 
      el("h1", {}, "Activity log"),
      el("p", { class: "lede" },
        "Everything that has changed, newest first. Entries are never edited " +
        "or deleted — the database refuses both."),

      entries.length
        ? table([
            { key: "ts_utc", label: "When",
              render: (row) => localDate(row.ts_utc, { withTime: true }) },
            { key: "summary", label: "What happened",
              render: (row) => el("span", {},
                row.summary,
                row.impersonator_person_id
                  ? el("span", { class: "choice__why" },
                      `Done by ${row.impersonator_first_name} ` +
                      `${row.impersonator_last_name}, viewing as ` +
                      `${row.actor_first_name} ${row.actor_last_name}.`)
                  : null,
                row.value_detail ? renderValueDetail(row.value_detail) : null,
                row.changed_fields ? renderChangedFields(row.changed_fields) : null) },
            { key: "school_name", label: "Chapter",
              render: (row) => row.school_name || "—" },
            { key: "action", label: "Action",
              render: (row) => el("span", { class: "pill" }, row.action) },
          ], entries, {
            rowClass: (row) => row.impersonator_person_id ? "is-flagged" : null,
            caption: "Audit log",
          })
        : emptyState("Nothing logged yet",
            "Actions appear here as soon as anyone changes something."),

      done
        ? el("p", { class: "label" }, `That is all ${entries.length} entries.`)
        : el("div", { class: "btn-row" },
            button("Load older entries", { onclick: () => loadMore() })));
  }

  /* Field NAMES only, never values -- that is what keeps minors' answers out of
   * a log many people can read. */
  function renderChangedFields(json) {
    let fields;
    try { fields = JSON.parse(json); } catch (ignored) { return null; }
    if (!fields || !fields.length) return null;
    return el("span", { class: "choice__why" },
      `Changed: ${fields.map((f) => f.replace(/_/g, " ")).join(", ")}.`);
  }

  /* Payments are the ONE action that records values, because money disputes are
   * exactly when you need them. */
  function renderValueDetail(json) {
    let detail;
    try { detail = JSON.parse(json); } catch (ignored) { return null; }
    if (!detail) return null;
    const dollars = (cents) => ((cents || 0) / 100)
      .toLocaleString("en-US", { style: "currency", currency: "USD" });
    return el("span", { class: "choice__why" },
      `${dollars(detail.amount_cents)}` +
      (detail.reference ? `, reference ${detail.reference}` : "") +
      (detail.new_total_cents !== undefined
        ? `. Chapter total is now ${dollars(detail.new_total_cents)}.` : "."));
  }
}
