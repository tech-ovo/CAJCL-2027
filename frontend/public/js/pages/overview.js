/* The registration chair's one screen.
 *
 * Every chapter, who they are bringing, how far along they are, and what they
 * owe — plus the meal totals the caterer needs.
 *
 * ONE REQUEST, READING FIFTY ROWS. Every number here was counted inside the
 * transaction that changed it, so nothing is aggregated live. See migration
 * 012 for why that matters more than it sounds.
 *
 * The Chapters page next door is for ACTING on one chapter — recording a
 * payment, opening a roster. This one is for looking at all of them at once
 * and finding the two that need chasing.
 */

import * as api from "../api.js";
import { add, el, clear, table, money, loadingRows, emptyState } from "../ui.js";

export async function overviewPage(host) {
  let data = null;
  let onlyProblems = false;

  add(host, loadingRows(10, "Counting"));
  data = await api.get("/admin/overview", { statusHost: host });
  render();

  function render() {
    clear(host);
    const t = data.totals;

    add(host,
      el("h1", {}, "Overview"),
      el("p", { class: "lede" },
        "Where every chapter has got to. Figures come from the counters, which "
        + "move with the roster, so this is what is true now."),

      headline(t),
      meals(t),
      chapters());
  }

  function headline(t) {
    const pair = (label, value, note) => el("div", { class: "stat" },
      el("span", { class: "stat__value" }, value),
      el("span", { class: "label" }, label),
      note ? el("span", { class: "small muted" }, note) : null);

    return el("div", { class: "stats" },
      pair("Chapters", t.chapters,
           progress(t.chapters_started, t.chapters, "have started")),
      // Split, because almost every question a chair is asked about numbers
      // is really about one level: how many tests to print at each level, how
      // many rooms, which Certamen bracket.
      pair("Delegates", t.delegates.toLocaleString("en-US"),
           `${t.delegates_ms} middle · ${t.delegates_hs} high`),
      pair("Adults", t.adults.toLocaleString("en-US"),
           `${t.sponsors} sponsors · ${t.chaperones} chaperones`),
      pair("Forms complete", `${t.complete}/${t.people}`,
           t.people ? `${Math.round(100 * t.complete / t.people)}%` : null),
      pair("Still owed", money(t.outstanding_cents),
           progress(t.chapters_paid, t.chapters, "settled")));
  }

  function progress(done, total, what) {
    if (!total) return null;
    return `${done} of ${total} ${what}`;
  }

  /* Meals get their own block because they answer one specific question, asked
   * by somebody who is not a registration chair, on a deadline that is not the
   * registration deadline. The caterer wants a number; the unanswered count is
   * the part the chairs have to chase. */
  /* The meal block ends one subject and the chapter table begins another.
   * Without this they ran together, and "Total attending" read as a heading
   * for the table under it. */
  function meals(t) {
    const known = t.meal_regular + t.meal_vegetarian + t.meal_gluten_free;
    const rows = [
      ["Regular", t.meal_regular],
      ["Vegetarian", t.meal_vegetarian],
      ["Gluten free", t.meal_gluten_free],
    ];

    return el("section", { style: "margin-bottom:var(--space-7)" },
      el("h2", {}, "Meals"),
      el("p", { class: "muted" },
        `${known.toLocaleString("en-US")} answered, `
        + `${t.meal_unanswered.toLocaleString("en-US")} still to come. `
        + "This is everybody attending, chapters and SCL alike, and counts "
        + "active attendees only."),

      el("div", { class: "totals" },
        ...rows.map(([label, count]) => el("div", { class: "totals__row" },
          el("span", {}, label),
          el("span", { class: "mono" },
            `${count}`,
            known ? el("span", { class: "small muted" },
                       `  ${Math.round(100 * count / known)}%`) : null))),
        el("div", { class: "totals__row" },
          el("span", {}, "Not answered yet"),
          el("span", { class: "mono" }, t.meal_unanswered)),
        el("div", { class: "totals__row totals__row--final" },
          el("span", {}, "Total attending"),
          el("span", { class: "mono" }, known + t.meal_unanswered))));
  }

  function chapters() {
    const rows = data.chapters.filter((row) => {
      if (row.status !== "active") return false;
      if (!onlyProblems) return true;
      // "Needs attention" is deliberately narrow: something a chair can act on
      // today. A chapter with nobody in it and one that owes money are two
      // different phone calls; a chapter that is simply not finished yet is
      // neither, and burying those two in it would make the filter useless.
      const wantsSponsor = row.kind === "chapter";
      return !row.people || (wantsSponsor && !row.has_sponsor)
          || (!row.billing_exempt && row.balance_cents > 0);
    });

    return el("section", {},
      el("h2", {}, "Chapters"),
      el("div", { class: "btn-row" },
        el("label", { class: "small",
                      style: "display:inline-flex;gap:.5rem;align-items:center" },
          el("input", {
            type: "checkbox", checked: onlyProblems,
            onchange: (event) => { onlyProblems = event.target.checked; render(); },
          }),
          "Only chapters needing attention")),

      rows.length
        ? table([
            // ORGANIZATIONS ARE LISTED HERE, marked. SCL is not a chapter
            // and is not counted as one in the figures above, but a chair
            // looking for "is everybody in" wants one list, not two. The pill
            // is the same one Check-in uses, so the word means one thing.
            { key: "school_name", label: "Chapter",
              render: (row) => el("span", {},
                el("a", { href: `#/roster/${row.school_id}` }, row.school_name),
                row.kind !== "chapter"
                  ? el("span", { class: "pill", style: "margin-left:.5rem" },
                       "Not a chapter")
                  : null) },
            { key: "level", label: "Level" },
            { key: "delegates_active", label: "Delegates", num: true },
            // The pill goes BEFORE the number. After it, every flagged row's
            // figure sat a pill's width further right than every other row's,
            // and a column of numbers you cannot read down is not a column.
            { key: "adults_active", label: "Adults", num: true,
              render: (row) => el("span", {},
                row.has_sponsor ? null
                  : el("span", { class: "pill", style: "margin-right:.4rem" },
                       "No sponsor"),
                el("span", { class: "mono" }, row.adults_active)) },
            { key: "complete", label: "Complete", num: true,
              render: (row) => el("span", { class: "mono" },
                `${row.complete}/${row.people}`) },
            { key: "meal_unanswered", label: "No meal", num: true },
            { key: "balance_cents", label: "Balance", num: true,
              render: (row) => row.billing_exempt
                ? el("span", { class: "muted" }, "Not billed")
                : el("span", { class: row.balance_cents > 0 ? "mono" : "mono muted" },
                     money(row.balance_cents)) },
          ], rows, {
            rowClass: (row) =>
              (!row.people || (row.kind === "chapter" && !row.has_sponsor))
                ? "is-flagged" : null,
            caption: "Every registered chapter",
          })
        : emptyState("Nothing needs attention",
            "Every chapter has a sponsor, somebody on its roster, and nothing "
            + "outstanding."));
  }
}
