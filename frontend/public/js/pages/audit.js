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
  let logins = [];
  let cursor = null;
  let done = false;

  add(host, loadingRows(10, "Loading the log"));
  await loadMore(true);
  // Fetched after the log, not with it: the log is what the page is for, and a
  // second request should not hold it back. A failure here leaves the list
  // empty rather than taking the page down.
  try {
    logins = (await api.get("/admin/logins")).logins || [];
    render();
  } catch (error) { /* the log above is still worth showing */ }

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
                // The summary is prose written when the entry was made, so
                // the names in it are text. What IS linkable is the person the
                // entry is about and the person who did it — both carry an id.
                row.summary,
                who(row),
                row.impersonator_person_id
                  ? el("span", { class: "choice__why" },
                      `Done by ${row.impersonator_first_name} ` +
                      `${row.impersonator_last_name}, viewing as ` +
                      `${row.actor_first_name} ${row.actor_last_name}.`)
                  : null,
                row.value_detail ? renderValueDetail(row.value_detail) : null,
                row.changed_fields ? renderChangedFields(row.changed_fields) : null) },
            { key: "school_name", label: "Chapter",
              render: (row) => row.school_id
                ? el("a", { href: `#/roster/${row.school_id}` },
                     row.school_name || `Chapter ${row.school_id}`)
                : "—" },
            { key: "action", label: "Action",
              render: (row) => el("span", { class: "pill" }, row.action) },
          ], entries, {
            rowClass: (row) => row.impersonator_person_id ? "is-flagged" : null,
            caption: "Audit log",
          })
        : emptyState("Nothing logged yet",
            "Actions appear here as soon as anyone changes something."),

      /* WHO HAS BEEN TRYING TO SIGN IN.
       *
       * A separate list because it answers a different question from the log
       * above: not "what changed" but "is somebody grinding at this". The
       * answer is repetition — the same place failing over and over, or one
       * prefix tried from many places — and both are visible without knowing
       * whose place it is.
       */
      el("details", { class: "panel", style: "margin:1.5rem 0" },
        el("summary", {}, el("span", { class: "label label--ink" },
                             "Recent sign-in attempts")),
        el("p", { class: "small muted" },
          "Kept for seven days, then deleted. Addresses are stored as a "
          + "one-way hash, keyed with a secret that is not in the database, "
          + "and shown here as the first twelve characters of it — enough to "
          + "tell two places apart, and not enough to say where either is. "
          + "Nothing here, including this site, can turn one back into an "
          + "address."),
        logins.length
          ? table([
              { key: "attempted_at", label: "When",
                render: (row) => localDate(row.attempted_at, { withTime: true }) },
              { key: "succeeded", label: "Result",
                render: (row) => row.succeeded
                  ? el("span", { class: "pill pill--done" }, "Signed in")
                  : el("span", { class: "pill" }, "Refused") },
              { key: "code_prefix", label: "Kind",
                render: (row) => row.code_prefix || "—" },
              { key: "ip_hash", label: "From",
                render: (row) => el("span", { class: "mono small" }, row.ip_hash) },
            ], logins, { caption: "Recent sign-in attempts" })
          : el("p", { class: "muted" }, "Nothing in the last seven days.")),

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
  /* Who this entry is about, and who did it — as links into the chapter where
   * that person can actually be seen.
   *
   * The roster is the page that answers "who is this and what have they got",
   * so an id in the log becomes a click rather than a number to go and look
   * up. An entry with no school -- a settings change, say -- has nowhere to
   * send anybody and shows nothing.
   */
  function who(row) {
    if (!row.school_id) return null;
    const links = [];

    if (row.entity_type === "person" && row.entity_id) {
      links.push(["About", row.entity_id]);
    }
    if (row.actor_person_id && row.actor_person_id !== row.entity_id) {
      links.push(["By", row.actor_person_id]);
    }
    if (!links.length) return null;

    return el("span", { class: "choice__why" },
      ...links.flatMap(([label, personId], index) => [
        index ? " · " : null,
        `${label} `,
        el("a", { href: `#/roster/${row.school_id}#person-${personId}` },
           `#${personId}`),
      ]).filter((part) => part !== null));
  }

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
