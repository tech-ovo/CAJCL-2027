/* What the Academics, Activities and Athletics chairs need before convention.
 *
 * ONE QUESTION: how many papers do we print, and how many rooms do we need.
 *
 * This is REGISTRATION data. Nothing here grades anything or records a score;
 * those are not built. What is built is the count that has to be right weeks
 * before anybody sits anything, and the list of names a proctor carries.
 *
 * The summary is one request. Opening an item is one more, and it is bounded
 * by the people who chose that item rather than by the size of the convention.
 */

import * as api from "../api.js";
import { add, el, clear, table, button, loadingRows, fullName,
         emptyState, localDate, tell } from "../ui.js";
import { openPrintView } from "./roster.js";

/* TWO CHAIRS, TWO JOBS, ONE PAGE OF FIFTY ROWS.
 *
 * The Academics chair prints and proctors tests. The Activities and Athletics
 * chairs run arts entries, ludi and olympika. They work at different times, on
 * different things, and neither one wants to scroll past the other's
 * categories to find their own.
 *
 * The split is a filter over data already in hand -- one request still, and
 * `category_key` was always on every row. Which key belongs to which tab is
 * the only thing this adds, and it is here rather than in the database
 * because it is a question about who does what job, not about the catalog.
 */
/* ACADEMICS IS THE NAMED LIST; ACTIVITIES IS EVERYTHING ELSE.
 *
 * Written as two lists, a category added later -- and the catalog editor is
 * meant to make that a five-minute job -- would have belonged to neither and
 * disappeared from this page entirely, with no error and nothing missing that
 * anybody could see. A catch-all cannot lose a row. If a new category belongs
 * on the Academics side, add its key here. */
const ACADEMIC_CATEGORIES = ["academic_testing", "creative_arts",
                             "preconvention"];

const TABS = [
  ["academics", "Academics",
   (row) => ACADEMIC_CATEGORIES.includes(row.category_key)],
  ["activities", "Activities",
   (row) => !ACADEMIC_CATEGORIES.includes(row.category_key)],
];

export async function academicsPage(host) {
  let data = null;
  let open = null;          // the item being looked at, or null
  let filter = "";
  // Whichever tab this chair is most likely to want. Somebody holding only
  // `academics` opens on Academics; everybody else opens on the first tab.
  let tab = TABS[0][0];

  add(host, loadingRows(8, "Counting entries"));
  data = await api.get("/admin/academics/counts", { statusHost: host });
  render();

  function render() {
    clear(host);
    const totals = data.totals;

    add(host,
      el("section", { class: "grid" },
        el("div", { class: "span-8" },
          el("h1", {}, "Entries"),
          el("p", { class: "lede" },
            "Open a row to see which chapters, and who.")),
        el("div", { class: "span-4" },
          el("div", { class: "totals" },
            el("div", { class: "totals__row" },
              el("span", {}, "Items offered"),
              el("span", { class: "mono" }, totals.items_offered)),
            el("div", { class: "totals__row" },
              el("span", {}, "Chapter entries"),
              el("span", { class: "mono" }, totals.chapter_entries)),
            el("div", { class: "totals__row totals__row--final" },
              el("span", {}, "Individual entries"),
              el("span", { class: "mono" }, totals.entries))))),

      el("p", { class: "small muted" }, deadlineNote()),

      tabs(),
      searchBox());

    if (open) {
      add(host, itemPanel());
      return;
    }

    const rows = data.items.filter(inTab).filter(matches);
    if (!rows.length) {
      add(host, emptyState("Nothing matches",
        "No test or activity has a name like that."));
      return;
    }

    // Grouped by category, because a chair works on one category at a time —
    // and a flat list of fifty items sorted by count tells nobody which of
    // them are their problem.
    let lastCategory = null;
    let group = [];
    const flush = () => {
      if (!group.length) return;
      add(host,
        el("h2", {}, lastCategory),
        table(columns(), group, { caption: `Entries for ${lastCategory}` }));
      group = [];
    };

    for (const row of rows) {
      if (row.category !== lastCategory) { flush(); lastCategory = row.category; }
      group.push(row);
    }
    flush();
  }

  /* The two chairs' halves. A search still looks across BOTH, because
   * somebody who types "Certamen" wants it found rather than told it is on the
   * other tab. */
  function tabs() {
    return el("div", { class: "tabs" },
      ...TABS.map(([key, label, belongs]) => {
        const count = data.items.filter(belongs).length;
        const anchor = el("a", {
          href: "#/entries",
          class: key === tab ? "tabs__tab is-current" : "tabs__tab",
          onclick: (event) => {
            event.preventDefault();
            tab = key;
            open = null;
            render();
          },
        }, label, el("span", { class: "small muted" }, `  ${count}`));
        if (key === tab) anchor.setAttribute("aria-current", "page");
        return anchor;
      }));
  }

  function inTab(row) {
    // A search reaches across both halves. Somebody typing a name wants it
    // found, not told that it lives on the tab they are not looking at.
    if (filter.trim()) return true;
    return TABS.find(([key]) => key === tab)[2](row);
  }

  function deadlineNote() {
    const parts = ["Counts exclude cancelled delegates."];
    if (data.deadline) {
      const when = localDate(data.deadline);
      if (when) parts.push(`Sheets close ${when}.`);
    }
    return parts.join(" ");
  }

  function searchBox() {
    const box = el("input", {
      type: "search",
      placeholder: "Find a test or activity",
      value: filter,
      oninput: (event) => {
        filter = event.target.value;
        // Filtering is local: everything is already here, and a keystroke
        // should not cost a request.
        render();
        const again = host.querySelector('input[type="search"]');
        if (again) { again.focus(); again.setSelectionRange(again.value.length,
                                                            again.value.length); }
      },
    });
    return el("div", { class: "field", style: "max-width:24rem" }, box);
  }

  function matches(row) {
    if (!filter.trim()) return true;
    const needle = filter.trim().toLowerCase();
    return row.name.toLowerCase().includes(needle)
        || row.category.toLowerCase().includes(needle);
  }

  function columns() {
    return [
      // The name IS the link, the way a chapter's name is on every other page.
      // A trailing "Who" button made a second target for the same thing and
      // put it at the far end of the row, so the eye crossed five columns to
      // reach it.
      { key: "name", label: "Item",
        render: (row) => el("span", {},
          el("a", {
            href: "#/entries",
            onclick: (event) => { event.preventDefault(); openItem(row.id); },
          }, row.name),
          row.registration_scope === "chapter"
            ? el("span", { class: "pill", style: "margin-left:.5rem" },
                "Per chapter")
            : null) },
      /* THE NUMBER ON THE ANSWER SHEET, editable in place.
       *
       * The Academics chairs hold `academics`, not `*`, so the catalog editor
       * next door is closed to them — and rightly: renaming a test or changing
       * who may enter it is not theirs. This one field is, and it has its own
       * endpoint that can write nothing else.
       *
       * Blank until somebody sets it. A test with no number is not an error,
       * it is a test whose sheets have not been laid out yet. */
      { key: "item_code", label: "No.",
        render: (row) => el("input", {
          type: "text", value: row.item_code || "", size: 4, maxlength: 4,
          inputmode: "numeric", class: "mono",
          "aria-label": `Test number for ${row.name}`,
          placeholder: "····",
          onchange: async (event) => {
            const box = event.target;
            box.disabled = true;
            try {
              const result = await api.patch(
                `/admin/academics/item/${row.id}/code`,
                { item_code: box.value.trim() });
              row.item_code = result.item_code;
              box.value = result.item_code || "";
            } catch (error) {
              box.value = row.item_code || "";
              await tell({ body: error.message });
            } finally {
              box.disabled = false;
            }
          },
        }) },
      { key: "eligible_latin_levels", label: "Open to",
        render: (row) => row.eligible_latin_levels
          ? row.eligible_latin_levels.split(",").join(", ")
          : "Any level" },
      { key: "chosen_ms", label: "MS", num: true },
      { key: "chosen_hs", label: "HS", num: true },
      { key: "chosen", label: "Total", num: true,
        render: (row) => row.registration_scope === "chapter"
          ? el("span", { class: "mono" }, `${row.chapter_entries} teams`)
          : el("strong", { class: "mono" }, row.chosen) },
    ];
  }

  async function openItem(itemId) {
    clear(host);
    add(host, loadingRows(6, "Loading entries"));
    try {
      open = await api.get(`/admin/academics/item/${itemId}`);
    } catch (error) {
      open = null;
      clear(host);
      add(host, el("p", {}, error.message));
      return;
    }
    render();
  }

  function itemPanel() {
    const item = open.item;

    return el("div", {},
      el("p", {}, button("← All entries", {
        variant: "btn--quiet",
        onclick: () => { open = null; render(); },
      })),

      el("h2", {}, item.name),
      el("p", { class: "muted" },
        `${item.category} · `,
        item.eligible_latin_levels
          ? `open to ${item.eligible_latin_levels.split(",").join(", ")}`
          : "open to any Latin level"),

      el("div", { class: "btn-row" },
        button("Print the sign-in sheet", {
          variant: "btn--primary",
          onclick: () => openPrintView(
            `/admin/academics/item/${item.id}/sheet`),
        })),

      open.chapters.length
        ? el("div", {},
            el("h3", {}, `${open.total} `
              + (open.total === 1 ? "delegate" : "delegates")
              + ` from ${open.chapters.length} `
              + (open.chapters.length === 1 ? "chapter" : "chapters")),
            table([
              { key: "school_name", label: "Chapter" },
              { key: "level", label: "Level" },
              { key: "chosen", label: "Delegates", num: true },
            ], open.chapters, { caption: `Chapters entering ${item.name}` }),

            el("h3", {}, "Everyone entered"),
            table([
              { key: "name", label: "Name", render: (row) => fullName(row) },
              { key: "school_name", label: "Chapter" },
              { key: "grade", label: "Grade", render: (row) => row.grade || "—" },
              { key: "latin_level", label: "Latin",
                render: (row) => row.latin_level || "—" },
            ], open.people, { caption: `Delegates entered in ${item.name}` }))
        : emptyState("Nobody yet",
            "An item nobody enters needs no room — and one nobody can find "
            + "may be gated to the wrong Latin level."));
  }
}
