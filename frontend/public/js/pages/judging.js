/* Judging the pre-convention contests, and reading the results.
 *
 *   #/judging                     every contest, and how far this judge has got
 *   #/judging/12                  one contest: rank your top N in each division
 *   #/contest-results             every contest, for the chairs ("Results")
 *   #/contest-results/12          standings with names      (Academics, Awards)
 *   #/contest-results/12/rules    rules text and N          (Academics)
 *
 * TWO JOBS, KEPT APART. Judges rank and never see names; the chairs see
 * names and never rank. The server enforces both -- the judging endpoints
 * take scope `judge` and nothing else -- so neither page has anything to hide.
 *
 * BLIND. A judge sees "Entry 14", a division, and the work -- never a name, a
 * chapter or the file name a student chose.
 *
 * TOP N, NOT A RUBRIC. In each division (and each Publicity category) a judge
 * picks their best N entries, in order, and hands that list in. N is set per
 * contest by the Academics chairs. The server combines the judges' lists; see
 * contests.rank in backend/lib/contests.py for the points and the tie-breaks.
 *
 * A DRAFT IS NOT A RANKING. "Save draft" keeps a half-finished list for later
 * and counts for nothing; "Hand in" is what the results read.
 */

import * as api from "../api.js";
import { add, el, clear, field, select, button, errorSummary, guardUnsaved,
         localDate, emptyState, loadingRows, table, tell } from "../ui.js";

const EXTENSIONS = {
  "application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png",
  "image/gif": "gif", "image/tiff": "tiff",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
  "text/plain; charset=utf-8": "txt",
};

// Only these can be shown in the page. TIFF opens in Safari and nowhere else,
// so it is offered as a download like a Word file.
const PREVIEWABLE_IMAGES = ["image/jpeg", "image/png", "image/gif"];

/* ------------------------------------------------------------------------ */

function ordinal(n) {
  const tens = n % 100;
  if (tens >= 10 && tens <= 20) return `${n}th`;
  return n + ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th");
}

function entryLabel(entry) {
  return `Entry ${entry.id}`;
}

function groupTitle(group) {
  return group.facet ? `${group.division} · ${group.facet}` : group.division;
}

function groupKey(group) {
  return `${group.division}\u0000${group.facet}`;
}

function chairNav(itemId, current, canEdit) {
  const tabs = [["results", "Standings", `#/contest-results/${itemId}`]];
  if (canEdit) tabs.push(["rules", "Rules and places", `#/contest-results/${itemId}/rules`]);
  return el("nav", { class: "tabs", "aria-label": "Contest sections" },
    ...tabs.map(([key, label, href]) => {
      const anchor = el("a", { href,
        class: key === current ? "tabs__tab is-current" : "tabs__tab" }, label);
      if (key === current) anchor.setAttribute("aria-current", "page");
      return anchor;
    }));
}

/* ------------------------------------------------------------------------ */

export async function judgingPage(host, params = []) {
  const itemId = params[0] ? Number(params[0]) : null;

  add(host, loadingRows(6, "Loading contests"));
  const overview = await api.get("/judge/contests", { statusHost: host });

  if (!itemId) {
    renderOverview(host, overview);
    return;
  }
  const contestRow = overview.contests.find((c) => c.item_id === itemId);
  if (!contestRow) {
    clear(host);
    add(host, emptyState("No such contest",
      "That contest is not being judged.",
      el("a", { class: "btn", href: "#/judging" }, "All contests")));
    return;
  }

  await rankingView(host, itemId);
}

function renderOverview(host, overview) {
  clear(host);
  add(host,
    el("h1", {}, "Judging"),
    el("p", { class: "lede" },
      "Pre-convention contests. Open one, read its entries, and hand in your "
      + "top picks for each division. Entries are numbered, never named."),
    overview.deadline
      ? el("p", { class: "form-note" },
          overview.closed
            ? "Entries are closed, so nothing will change under you."
            : `Entries are still open until ${localDate(overview.deadline, { withTime: true })}. `
              + "A student who replaces an entry takes it off your list, which "
              + "goes back to draft for you to finish again.")
      : null,
    table([
      { key: "name", label: "Contest",
        render: (row) => el("a", { href: `#/judging/${row.item_id}` }, row.name) },
      { key: "division_label", label: "Divisions",
        render: (row) => row.division_label
          + (row.facet_count ? ` · ${row.facet_count} categories` : "") },
      { key: "places", label: "Rank", render: (row) => `Top ${row.places}` },
      { key: "entries", label: "Entries", num: true },
      { key: "handed_in", label: "Your lists handed in", num: true,
        render: (row) => (row.groups ? `${row.handed_in} of ${row.groups}` : "—") },
    ], overview.contests, { caption: "Pre-convention contests" }));
}

/* ------------------------------------------------------------------------ */
/* Ranking                                                                   */
/* ------------------------------------------------------------------------ */

/* ONE LIST PER DIVISION. Each has a place picker beside every entry; giving
 * a place that another entry already holds MOVES it, so a list can never hold
 * one place twice. Picking a place only changes the page -- "Save draft" and
 * "Hand in" are what reach the server, one division at a time. */
async function rankingView(host, itemId) {
  const data = await api.get(`/judge/contests/${itemId}`, { statusHost: host });
  const byId = new Map(data.entries.map((e) => [e.id, e]));
  const picks = new Map();       // groupKey -> { entryId: place }
  const comments = new Map();    // groupKey -> text
  const dirty = new Set();       // groupKeys with unsaved changes
  const messages = new Map();    // groupKey -> { errors, note }
  const facets = data.contest.facet_list;
  let facetShown = facets.find((f) => data.groups.some((g) => g.facet === f)) || "";
  let openId = null;
  let listScroll = 0;
  let preview = null;            // { entryId, url } or { entryId, error }

  for (const group of data.groups) {
    const key = groupKey(group);
    // A list handed in before the chairs lowered N keeps places this page
    // no longer offers. They count for nothing, so they are not shown.
    const kept = {};
    const saved = group.ballot ? group.ballot.places : {};
    for (const id of Object.keys(saved)) {
      if (saved[id] <= places()) kept[id] = saved[id];
    }
    picks.set(key, kept);
    comments.set(key, group.ballot && group.ballot.comment ? group.ballot.comment : "");
  }

  guardUnsaved(() => dirty.size > 0, "rankings you have not saved");
  render();

  function contest() { return data.contest; }
  function places() { return data.contest.places; }

  function render() {
    clear(host);
    add(host,
      el("p", { class: "small" }, el("a", { href: "#/judging" }, "← All contests")),
      el("h1", {}, contest().name));

    const open = byId.get(openId);
    if (open) {
      add(host, entryPanel(open));
      return;
    }

    if (!data.entries.length) {
      add(host, emptyState("No entries yet",
        "Nobody has entered this contest yet. Entries appear here as they arrive."));
      return;
    }

    add(host,
      el("p", { class: "lede" },
        `In each division, pick your top ${places()} in order and hand the list in. `
        + "Open an entry to read it."),
      contest().words_penalty
        ? el("p", { class: "small muted" },
            `Entries outside the length limit lose ${contest().words_penalty} points `
            + "per 100 words under the Convention Book's rule. Weigh that in your ranking.")
        : null);

    if (facets.length) {
      const shown = facets.filter((f) => data.groups.some((g) => g.facet === f));
      add(host, field({ id: "facet-shown", label: "Category",
        help: "A portfolio is ranked separately in each category it includes.",
        control: select(shown.map((f) => {
          const groups = data.groups.filter((g) => g.facet === f);
          const done = groups.every((g) => g.complete && !dirty.has(groupKey(g)));
          return [f, done ? `${f} ✓` : f, f === facetShown];
        }), { onchange: (event) => { facetShown = event.target.value; render(); } }) }));
    }

    for (const group of data.groups) {
      if (facets.length && group.facet !== facetShown) continue;
      const section = el("section", {});
      add(host, section);
      drawGroup(section, group);
    }
  }

  function statusOf(group) {
    const key = groupKey(group);
    if (dirty.has(key)) return ["part", "Not saved"];
    if (!group.ballot) return ["none", "Not started"];
    if (group.ballot.status === "draft") return ["part", "Draft saved"];
    if (!group.complete) return ["part", `Handed in · now needs ${group.needed}`];
    return ["done", "✓ Handed in"];
  }

  function pill(group) {
    const [state, text] = statusOf(group);
    return el("span", { class: state === "done" ? "pill pill--done" : "pill" }, text);
  }

  /* Give `entryId` a place (or none) in `group`, moving that place off any
   * other entry that held it. Returns the entry that lost it, if any. */
  function setPlace(group, entryId, place) {
    const key = groupKey(group);
    const chosen = picks.get(key);
    let bumped = null;
    if (place) {
      for (const [other, held] of Object.entries(chosen)) {
        if (held === place && other !== String(entryId)) {
          delete chosen[other];
          bumped = other;
        }
      }
      chosen[String(entryId)] = place;
    } else {
      delete chosen[String(entryId)];
    }
    dirty.add(key);
    messages.delete(key);
    return bumped;
  }

  function placePicker(group, entry, onchange) {
    const current = picks.get(groupKey(group))[String(entry.id)] || 0;
    const options = [["", "—", !current]];
    for (let place = 1; place <= places(); place += 1) {
      options.push([String(place), ordinal(place), place === current]);
    }
    return select(options, {
      class: "place-picker",
      "aria-label": `Place for ${entryLabel(entry)}`
                    + (group.facet ? ` in ${group.facet}` : ""),
      onchange: (event) => onchange(Number(event.target.value) || 0),
    });
  }

  function drawGroup(section, group) {
    const key = groupKey(group);
    const rows = group.entry_ids.map((id) => byId.get(id));
    const pickers = {};
    const status = el("span", {}, pill(group));
    const { errors = [], note = null } = messages.get(key) || {};

    const comment = el("textarea", { rows: 3, maxlength: 2000 }, comments.get(key));
    comment.addEventListener("input", () => {
      comments.set(key, comment.value);
      dirty.add(key);
      clear(status);
      add(status, pill(group));
    });

    const handedIn = group.ballot && group.ballot.status === "submitted";
    clear(section);
    add(section,
      el("h2", {}, groupTitle(group), " ", status),
      el("p", { class: "small muted" },
        `${rows.length} ${rows.length === 1 ? "entry" : "entries"}. `
        + (group.needed < places()
            ? `Fewer than ${places()}, so rank all ${group.needed}.`
            : `Rank your top ${group.needed}.`)),
      errorSummary(errors),
      table([
        { key: "place", label: "Your place",
          render: (row) => {
            const picker = placePicker(group, row, (place) => {
              const bumped = setPlace(group, row.id, place);
              if (bumped && pickers[bumped]) pickers[bumped].value = "";
              clear(status);
              add(status, pill(group));
            });
            pickers[String(row.id)] = picker;
            return picker;
          } },
        { key: "id", label: "Entry",
          render: (row) => el("a", { href: `#/judging/${itemId}`,
            onclick: (event) => { event.preventDefault(); openEntry(row); } },
            entryLabel(row)) },
        { key: "title", label: "Title",
          render: (row) => row.title || row.text || (row.link_url ? "Portfolio" : "—") },
      ], rows, { caption: `${contest().name}, ${groupTitle(group)}` }),
      field({ id: `comment-${data.groups.indexOf(group)}`, label: "Notes for the chairs",
              help: "Optional. Students do not see them.",
              control: comment, wide: true }),
      note ? el("p", { class: "form-note" }, note) : null,
      el("div", { class: "btn-row" },
        button(handedIn ? "Hand in again" : `Hand in top ${group.needed}`, {
          variant: "btn--primary",
          onclick: () => save(section, group, true),
        }),
        button("Save draft", { onclick: () => save(section, group, false) })));
  }

  async function save(section, group, submit) {
    const key = groupKey(group);
    try {
      const result = await api.put(`/judge/contests/${itemId}/ballot`, {
        division: group.division, facet: group.facet,
        places: picks.get(key), comment: comments.get(key), submit,
      });
      group.ballot = { status: result.status, comment: comments.get(key),
                       places: result.places };
      picks.set(key, { ...result.places });
      group.complete = submit && Object.keys(result.places).length >= group.needed;
      dirty.delete(key);
      messages.set(key, { errors: [], note: submit
        ? "Handed in. You can change it and hand it in again."
        : "Draft saved. It does not count until you hand it in." });
    } catch (error) {
      messages.set(key, {
        errors: error.errors && error.errors.length ? error.errors : [error.message],
        note: null });
    }
    drawGroup(section, group);
  }

  function openEntry(entry) {
    listScroll = window.scrollY;
    openId = entry.id;
    render();
    window.scrollTo(0, 0);
    if (entry.has_file) loadPreview(entry);
  }

  function closeEntry() {
    openId = null;
    dropPreview();
    render();
    window.scrollTo(0, listScroll);
  }

  function dropPreview() {
    if (preview) URL.revokeObjectURL(preview.url);
    preview = null;
  }

  async function loadPreview(entry) {
    dropPreview();
    try {
      const { blob } = await api.getBlob(`/judge/entries/${entry.id}/file`);
      if (openId !== entry.id) return;           // moved on while it loaded
      preview = { entryId: entry.id, url: URL.createObjectURL(blob) };
    } catch (error) {
      preview = { entryId: entry.id, error: error.message };
    }
    if (openId === entry.id) render();
  }

  function entryPanel(entry) {
    const index = data.entries.indexOf(entry);
    const next = data.entries[(index + 1) % data.entries.length];
    const groups = data.groups.filter((g) => g.division === entry.division
                                             && entry.facets.includes(g.facet));

    return el("div", { class: "grid" },
      el("div", { class: "span-7" },
        el("div", { class: "tabula" },
          el("p", { class: "label" }, `${contest().name} · ${entry.division}`),
          el("p", { class: "tabula__name" }, entryLabel(entry)),
          el("div", { class: "tabula__row" },
            el("span", { class: "tabula__code" }, entry.title || ""))),
        work(entry)),
      el("div", { class: "span-5" },
        el("div", { class: "panel" },
          el("h2", {}, "Your place"),
          ...groups.map((group) => {
            const status = el("span", {}, pill(group));
            return field({
              id: `panel-place-${data.groups.indexOf(group)}`,
              label: group.facet ? group.facet : `Among ${group.division}`,
              help: status,
              control: placePicker(group, entry, (place) => {
                setPlace(group, entry.id, place);
                clear(status);
                add(status, pill(group));
              }),
            });
          }),
          el("p", { class: "small muted" },
            "A place taken from another entry moves here. Save or hand in the "
            + "list from the division's page.")),
        el("div", { class: "btn-row" },
          button("Back to the list", { onclick: () => closeEntry() }),
          next && next !== entry ? button(`Next: ${entryLabel(next)}`, {
            variant: "btn--quiet", onclick: () => openEntry(next),
          }) : null)));
  }

  function work(entry) {
    const parts = [];
    if (entry.word_count !== null && entry.word_count !== undefined) {
      parts.push(el("p", { class: "small muted" },
        `${entry.word_count} words`
        + (entry.word_count_source === "declared" ? ", as declared by the student" : "")
        + (entry.penalty
            ? ` — outside the limit: a ${entry.penalty}-point penalty under the Convention Book's rule.`
            : ".")));
    }
    if (entry.link_url) {
      parts.push(el("p", {},
        el("a", { class: "btn btn--primary", href: entry.link_url,
                  target: "_blank", rel: "noopener noreferrer" },
          "Open the portfolio")),
        el("p", { class: "small muted" },
          "Categories in this portfolio: " + entry.facets.join(", ") + "."));
    }
    if (entry.has_file) parts.push(filePreview(entry));
    if (entry.text) {
      parts.push(el("div", { class: "entry-text" }, entry.text));
      if (entry.translation) {
        parts.push(el("p", {}, el("strong", {}, "Translation: "), entry.translation));
      }
    }
    return el("div", { class: "form-section" }, ...parts);
  }

  function filePreview(entry) {
    if (!preview || preview.entryId !== entry.id) {
      return el("p", { class: "form-note" }, "Loading the file…");
    }
    if (preview.error) {
      return el("p", { class: "form-note form-note--unsaved" }, preview.error);
    }
    const extension = EXTENSIONS[entry.mime_type] || "file";
    const download = el("a", { class: "btn btn--small", href: preview.url,
                               download: `${entryLabel(entry)}.${extension}` },
      `Download ${entryLabel(entry)}.${extension}`);

    let shown = null;
    if (PREVIEWABLE_IMAGES.includes(entry.mime_type)) {
      shown = el("img", { class: "entry-preview", src: preview.url,
                          alt: `${entryLabel(entry)}, as submitted` });
    } else if (entry.mime_type === "application/pdf") {
      shown = el("iframe", { class: "entry-preview entry-preview--document",
                             src: preview.url, title: `${entryLabel(entry)}, as submitted` });
    }
    return el("div", {},
      shown,
      el("div", { class: "btn-row" }, download,
        !shown && !entry.text
          ? el("span", { class: "form-note" },
              "This kind of file cannot be shown here. Download it to read it.")
          : null));
  }

}

/* ------------------------------------------------------------------------ */
/* The chairs                                                                */
/* ------------------------------------------------------------------------ */

export async function contestResultsPage(host, params = []) {
  const itemId = params[0] ? Number(params[0]) : null;
  const view = params[1] || "results";

  add(host, loadingRows(6, "Loading contests"));
  if (!itemId) {
    const overview = await api.get("/admin/contests", { statusHost: host });
    renderChairOverview(host, overview);
    return;
  }
  const data = await api.get(`/admin/contests/${itemId}/results`, { statusHost: host });
  const current = view === "rules" && data.can_edit ? "rules" : "results";
  clear(host);
  add(host,
    el("p", { class: "small" },
      el("a", { href: "#/contest-results" }, "← All contests")),
    el("h1", {}, data.contest.name),
    chairNav(itemId, current, data.can_edit));

  if (current === "rules") {
    renderRules(host, itemId, data);
  } else {
    renderResults(host, data);
  }
}

function renderChairOverview(host, overview) {
  clear(host);
  add(host,
    el("h1", {}, "Results"),
    el("p", { class: "lede" },
      "Standings for the pre-convention contests, with names. Judges rank "
      + "their top entries in each division without seeing whose they are; "
      + "judging is done by people holding the Contest Judge role, not by the chairs."),
    overview.deadline
      ? el("p", { class: "form-note" },
          overview.closed
            ? "Entries are closed."
            : `Entries are open until ${localDate(overview.deadline, { withTime: true })}.`)
      : null,
    table([
      { key: "name", label: "Contest",
        render: (row) => el("a", { href: `#/contest-results/${row.item_id}` }, row.name) },
      { key: "division_label", label: "Divisions",
        render: (row) => row.division_label
          + (row.facet_count ? ` · ${row.facet_count} categories` : "") },
      { key: "places", label: "Places", num: true },
      { key: "entries", label: "Entries", num: true },
      { key: "ballots", label: "Lists handed in", num: true },
      { key: "judges", label: "Judges", num: true },
      { key: "rules", label: "",
        render: (row) => (overview.can_edit
          ? el("a", { href: `#/contest-results/${row.item_id}/rules` }, "Rules and places")
          : "") },
    ], overview.contests, { caption: "Pre-convention contests" }));
}

async function openEntryFile(row) {
  try {
    const { blob } = await api.getBlob(`/admin/contests/entries/${row.entry_id}/file`);
    const url = URL.createObjectURL(blob);
    const link = el("a", { href: url, target: "_blank", rel: "noopener",
                           download: `Entry ${row.entry_id}` });
    add(document.body, link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) {
    await tell({ body: error.message });
  }
}

function renderResults(host, data) {
  const n = data.contest.places;
  add(host,
    el("p", { class: "lede" },
      `${data.entry_count} ${data.entry_count === 1 ? "entry" : "entries"}. `
      + `${n === 1 ? "One place is" : `${n} places are`} awarded in each division.`),
    el("p", { class: "small muted" },
      `Each judge ranks their top ${n}. A judge's 1st is worth ${n} `
      + `${n === 1 ? "point" : `points, their 2nd ${n - 1}`}`
      + (n > 2 ? `, and so on down to 1 for a ${ordinal(n)}` : "")
      + ". Points are added across judges. Equal points go to whoever has more "
      + "1st places, then more 2nds, and so on; entries still level share a place. "
      + "Drafts do not count."
      + (data.contest.must_attend
          ? " An entry whose delegate is no longer attending is listed but not "
            + "placed, and those below move up."
          : "")),
    el("div", { class: "btn-row" },
      button("Print results", { onclick: () => window.print() })));

  if (!data.groups.length) {
    add(host, emptyState("No entries yet",
      "Standings appear here once entries arrive and judges hand in their lists."));
    return;
  }

  for (const group of data.groups) {
    add(host,
      el("h2", {}, groupTitle(group)),
      el("p", { class: "small muted" },
        group.ballots
          ? `${group.ballots} ${group.ballots === 1 ? "judge's list" : "judges' lists"} handed in.`
          : "No judge has handed in a list yet."),
      table([
        { key: "place", label: "Place",
          render: (row) => {
            if (row.place !== null) {
              return row.awarded ? ordinal(row.place)
                : el("span", { class: "muted" }, `${ordinal(row.place)} (not awarded)`);
            }
            if (!row.eligible) return "Not placed";
            return "—";
          } },
        { key: "entry_id", label: "Entry", render: (row) => `#${row.entry_id}` },
        { key: "who", label: "Entrant",
          render: (row) => (row.person_id
            ? `${row.first_name} ${row.last_name}` : row.school_name)
            + (row.eligible ? "" : " — not attending") },
        { key: "school_name", label: "Chapter" },
        { key: "work", label: "Work",
          render: (row) => [
            row.title || row.text || (row.link_url
              ? el("a", { href: row.link_url, target: "_blank",
                          rel: "noopener noreferrer" }, "Portfolio") : "—"),
            row.has_file ? " " : null,
            row.has_file ? button("File", {
              variant: "btn--small btn--quiet",
              onclick: () => openEntryFile(row),
            }) : null,
          ] },
        { key: "points", label: "Points", num: true,
          render: (row) => (row.points
            ? [String(row.points),
               row.tie_broken ? el("span", { class: "small muted" }, " · on placings") : null]
            : "—") },
        { key: "votes", label: "Judges",
          render: (row) => (row.votes.length
            ? row.votes.map((v) => `${v.name}: ${ordinal(v.place)}`).join("; ")
            : "Not ranked") },
      ], group.entries, {
        caption: `${data.contest.name}, ${groupTitle(group)}`,
      }),
      group.comments.length
        ? el("details", {},
            el("summary", {}, `Judges' notes (${group.comments.length})`),
            ...group.comments.map((c) =>
              el("p", {}, el("strong", {}, `${c.name}: `), c.comment)))
        : null);
  }
}

function renderRules(host, itemId, data) {
  const contest = data.contest;
  let errors = [];
  let saved = false;
  const holder = el("div");
  add(host, holder);

  const rules = el("textarea", { rows: 14 }, contest.rules_md || "");
  const places = el("input", { type: "number", class: "places-input", min: 1, max: 20, step: 1,
                               inputmode: "numeric", value: contest.places });
  rules.addEventListener("input", () => { saved = false; });
  places.addEventListener("input", () => { saved = false; });

  draw();

  function draw() {
    clear(holder);
    add(holder,
      errorSummary(errors),
      saved ? el("p", { class: "form-note" }, "Saved.") : null,
      field({ id: "contest-places", label: "Places awarded in each division",
              help: "Also how many entries each judge ranks. It can change after "
                + "judges have handed in: a longer list counts only its first "
                + "places, and a shorter one is shown to its judge as needing more.",
              control: places }),
      field({ id: "contest-rules", label: "Rules",
              help: "Shown to everybody entering. **Bold** and lines starting "
                + "with a dash work as they do in the rest of the site.",
              control: rules, wide: true }),
      el("p", { class: "small muted" },
        `Divisions: ${contest.division_label}. These are set by the Convention `
        + "Book and are not changed here."),
      el("div", { class: "btn-row" },
        button("Save the contest", { variant: "btn--primary", onclick: save })));
  }

  async function save() {
    try {
      await api.put(`/admin/contests/${itemId}`, {
        rules_md: rules.value,
        places: Number(places.value),
      });
      errors = [];
      saved = true;
    } catch (error) {
      errors = error.errors && error.errors.length ? error.errors : [error.message];
      saved = false;
      if (error.kind !== "validation") await tell({ body: error.message });
    }
    draw();
  }
}
