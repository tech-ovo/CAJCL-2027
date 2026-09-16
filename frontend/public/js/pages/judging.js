/* Judging the pre-convention contests, and reading the results.
 *
 *   #/judging                     every contest, and how far this judge has got
 *   #/judging/12                  one contest's entries, and the score sheet
 *   #/contest-results             every contest, for the chairs
 *   #/contest-results/12          standings with names      (Academics, Awards)
 *   #/contest-results/12/rubric   rules and rubric          (Academics)
 *
 * TWO JOBS, KEPT APART. Judges score and never see names; the chairs see
 * names and never score. The server enforces both -- the judging endpoints
 * take scope `judge` and nothing else -- so neither page has anything to hide.
 *
 * BLIND. A judge sees "Entry 14", a division, and the work -- never a name, a
 * chapter or the file name a student chose.
 *
 * A DRAFT IS NOT A SCORE. "Save draft" keeps a half-finished sheet for later
 * and counts for nothing; "Hand in score" is what the results read.
 */

import * as api from "../api.js";
import { add, el, clear, field, input, select, button, errorSummary,
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

function statusOf(entry) {
  const facets = entry.facets;
  const handed = facets.filter((f) => entry.scores[f]
                                   && entry.scores[f].status === "submitted").length;
  const drafted = facets.some((f) => entry.scores[f]
                                  && entry.scores[f].status === "draft");
  if (handed === facets.length) return ["done", "✓ Handed in"];
  if (handed || drafted) {
    return ["part", facets.length > 1
      ? `${handed} of ${facets.length} handed in` : "Draft saved"];
  }
  return ["none", "Not started"];
}

function entryLabel(entry) {
  return `Entry ${entry.id}`;
}

function chairNav(itemId, current, canEdit) {
  const tabs = [["results", "Results", `#/contest-results/${itemId}`]];
  if (canEdit) tabs.push(["rubric", "Rules and rubric", `#/contest-results/${itemId}/rubric`]);
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

  await scoringView(host, itemId);
}

function renderOverview(host, overview) {
  clear(host);
  add(host,
    el("h1", {}, "Judging"),
    el("p", { class: "lede" },
      "Pre-convention contests. Open one to read its entries and hand in your "
      + "scores. Entries are numbered, never named."),
    overview.deadline
      ? el("p", { class: "form-note" },
          overview.closed
            ? "Entries are closed, so nothing will change under you."
            : `Entries are still open until ${localDate(overview.deadline, { withTime: true })}. `
              + "A student who replaces an entry clears the scores on it.")
      : null,
    table([
      { key: "name", label: "Contest",
        render: (row) => el("a", { href: `#/judging/${row.item_id}` }, row.name) },
      { key: "division_label", label: "Divisions",
        render: (row) => row.division_label
          + (row.facet_count ? ` · ${row.facet_count} categories` : "") },
      { key: "entries", label: "Entries", num: true },
      { key: "scored", label: "You have handed in", num: true,
        render: (row) => (row.entries ? `${row.scored} of ${row.entries}` : "—") },
    ], overview.contests, { caption: "Pre-convention contests" }));
}

/* ------------------------------------------------------------------------ */
/* Scoring                                                                   */
/* ------------------------------------------------------------------------ */

async function scoringView(host, itemId) {
  const data = await api.get(`/judge/contests/${itemId}`, { statusHost: host });
  let openId = null;
  let facet = "";
  let errors = [];
  let note = null;
  let preview = null;          // { entryId, url } or { entryId, error }

  render();

  function contest() { return data.contest; }

  function render() {
    clear(host);
    add(host,
      el("p", { class: "small" }, el("a", { href: "#/judging" }, "← All contests")),
      el("h1", {}, contest().name));

    const open = data.entries.find((e) => e.id === openId);
    if (open) {
      add(host, entryPanel(open));
      return;
    }

    if (!data.entries.length) {
      add(host, emptyState("No entries yet",
        "Nobody has entered this contest yet. Entries appear here as they arrive."));
      return;
    }

    const divisions = [...new Set(data.entries.map((e) => e.division))];
    for (const division of divisions) {
      const rows = data.entries.filter((e) => e.division === division);
      add(host,
        el("h2", {}, division),
        table([
          { key: "id", label: "Entry",
            render: (row) => el("a", { href: `#/judging/${itemId}`,
              onclick: (event) => { event.preventDefault(); openEntry(row); } },
              entryLabel(row)) },
          { key: "title", label: "Title",
            render: (row) => row.title || row.text || (row.link_url ? "Portfolio" : "—") },
          { key: "status", label: "Your score",
            render: (row) => {
              const [state, text] = statusOf(row);
              return el("span", { class: state === "done" ? "pill pill--done" : "pill" }, text);
            } },
        ], rows, { caption: `${contest().name}, ${division}` }));
    }
  }

  function openEntry(entry) {
    openId = entry.id;
    const unscored = entry.facets.find((f) => !(entry.scores[f]
                                                && entry.scores[f].status === "submitted"));
    facet = unscored === undefined ? entry.facets[0] : unscored;
    errors = [];
    note = null;
    render();
    window.scrollTo(0, 0);
    if (entry.has_file) loadPreview(entry);
  }

  function closeEntry() {
    openId = null;
    dropPreview();
    render();
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
    const [, statusText] = statusOf(entry);
    const index = data.entries.indexOf(entry);
    const next = data.entries.slice(index + 1).concat(data.entries.slice(0, index))
      .find((e) => statusOf(e)[0] !== "done");

    return el("div", { class: "grid" },
      el("div", { class: "span-7" },
        el("div", { class: "tabula" },
          el("p", { class: "label" }, `${contest().name} · ${entry.division}`),
          el("p", { class: "tabula__name" }, entryLabel(entry)),
          el("div", { class: "tabula__row" },
            el("span", { class: "tabula__code" }, entry.title || ""),
            el("span", { class: "tabula__id" }, statusText))),
        work(entry)),
      el("div", { class: "span-5" },
        scoreSheet(entry),
        el("div", { class: "btn-row" },
          button("Back to the list", { onclick: () => closeEntry() }),
          next ? button(`Next: ${entryLabel(next)}`, {
            variant: "btn--quiet", onclick: () => openEntry(next),
          }) : null)));
  }

  function work(entry) {
    const parts = [];
    if (entry.word_count !== null && entry.word_count !== undefined) {
      parts.push(el("p", { class: "small muted" },
        `${entry.word_count} words`
        + (entry.word_count_source === "declared" ? ", as declared by the student" : "")
        + (entry.penalty ? ` — outside the limit, so ${entry.penalty} points come off.` : ".")));
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

  function scoreSheet(entry) {
    const saved = entry.scores[facet] || null;
    const criteria = contest().criteria;
    const inputs = {};

    const total = el("span", { class: "mono" });
    const recount = () => {
      let sum = 0;
      for (const criterion of criteria) {
        const value = Number(inputs[criterion.id].value);
        if (Number.isFinite(value)) sum += value;
      }
      total.textContent = `${Math.max(0, sum - entry.penalty)} / ${contest().max_points}`;
    };

    const rows = criteria.map((criterion) => {
      const box = el("input", {
        type: "number", min: 0, max: criterion.max_points, step: "0.5",
        inputmode: "decimal", class: "rubric__points",
        value: saved && saved.points[criterion.id] !== undefined
          ? saved.points[criterion.id] : "",
      });
      box.addEventListener("input", recount);
      inputs[criterion.id] = box;
      return field({ id: `criterion-${criterion.id}`,
                     label: `${criterion.label} (out of ${criterion.max_points})`,
                     control: box });
    });

    const comment = el("textarea", { rows: 4, maxlength: 2000 },
                       saved && saved.comment ? saved.comment : "");
    recount();

    const facetPicker = entry.facets.length > 1
      ? field({ id: "score-facet", label: "Category",
                help: "A portfolio is scored once for each category it includes.",
                control: select(entry.facets.map((f) => {
                  const done = entry.scores[f] && entry.scores[f].status === "submitted";
                  return [f, done ? `${f} ✓` : f, f === facet];
                }), { onchange: (event) => { facet = event.target.value; errors = []; note = null; render(); } }) })
      : null;

    return el("div", { class: "panel" },
      el("h2", {}, facet ? `Score: ${facet}` : "Your score"),
      facetPicker,
      errorSummary(errors),
      ...rows,
      entry.penalty
        ? el("p", { class: "small" }, `Length penalty: −${entry.penalty}`)
        : null,
      el("div", { class: "totals" },
        el("div", { class: "totals__row totals__row--final" },
          el("span", {}, "Total"), total)),
      field({ id: "score-comment", label: "Comment",
              help: "For the chairs. Students do not see it.",
              control: comment, wide: true }),
      note ? el("p", { class: "form-note" }, note) : null,
      el("div", { class: "btn-row" },
        button(saved && saved.status === "submitted" ? "Hand in again" : "Hand in score", {
          variant: "btn--primary",
          onclick: () => save(entry, inputs, comment, true),
        }),
        button("Save draft", {
          onclick: () => save(entry, inputs, comment, false),
        })));
  }

  async function save(entry, inputs, comment, submit) {
    const points = {};
    for (const [id, box] of Object.entries(inputs)) {
      if (box.value !== "") points[id] = box.value;
    }
    try {
      const result = await api.put(`/judge/entries/${entry.id}/score`, {
        facet, points, comment: comment.value, submit,
      });
      entry.scores[facet] = {
        points, penalty: result.penalty, total: result.total,
        comment: comment.value, status: result.status,
      };
      errors = [];
      note = submit
        ? `Handed in: ${result.total} points. You can change it and hand it in again.`
        : "Draft saved. It does not count until you hand it in.";
      render();
    } catch (error) {
      errors = error.errors && error.errors.length ? error.errors : [error.message];
      note = null;
      render();
    }
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
  clear(host);
  add(host,
    el("p", { class: "small" },
      el("a", { href: "#/contest-results" }, "← All contests")),
    el("h1", {}, data.contest.name),
    chairNav(itemId, view === "rubric" && data.can_edit ? "rubric" : "results",
             data.can_edit));

  if (view === "rubric" && data.can_edit) {
    renderRubric(host, itemId, data);
  } else {
    renderResults(host, data);
  }
}

function renderChairOverview(host, overview) {
  clear(host);
  add(host,
    el("h1", {}, "Contest results"),
    el("p", { class: "lede" },
      "Standings for the pre-convention contests, with names. Judges score "
      + "the entries without seeing whose they are; judging is done by people "
      + "holding the Contest Judge role, not by the chairs."),
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
      { key: "entries", label: "Entries", num: true },
      { key: "judged", label: "Judged at least once", num: true,
        render: (row) => (row.entries ? `${row.judged} of ${row.entries}` : "—") },
      { key: "scores", label: "Scores handed in", num: true },
      { key: "rubric", label: "",
        render: (row) => (overview.can_edit
          ? el("a", { href: `#/contest-results/${row.item_id}/rubric` }, "Rules and rubric")
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
  add(host,
    el("p", { class: "lede" },
      `${data.entry_count} ${data.entry_count === 1 ? "entry" : "entries"}. `
      + "A score is the mean of its judges' handed-in totals; drafts do not count."),
    data.contest.must_attend
      ? el("p", { class: "small muted" },
          "An entry whose delegate is no longer attending is listed but not placed.")
      : null,
    el("div", { class: "btn-row" },
      button("Print results", { onclick: () => window.print() })));

  if (!data.groups.length) {
    add(host, emptyState("No entries yet",
      "Standings appear here once entries arrive and judges hand in scores."));
    return;
  }

  for (const group of data.groups) {
    add(host,
      el("h2", {}, group.facet ? `${group.division} · ${group.facet}` : group.division),
      table([
        { key: "place", label: "Place", num: true,
          render: (row) => {
            if (row.place !== null) return row.place;
            return row.eligible ? "—" : "Not placed";
          } },
        { key: "entry_id", label: "Entry", render: (row) => `#${row.entry_id}` },
        { key: "who", label: "Entrant",
          render: (row) => (row.person_id
            ? `${row.first_name} ${row.last_name}` : row.school_name)
            + (row.eligible ? "" : " — not attending") },
        { key: "school_name", label: "Chapter" },
        { key: "work", label: "Entry",
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
        { key: "average", label: "Score", num: true,
          render: (row) => (row.average === null ? "—" : row.average) },
        { key: "judges", label: "Judges",
          render: (row) => (row.judges.length
            ? row.judges.map((j) => `${j.name}: ${j.total}`).join("; ")
            : "Not yet scored") },
      ], group.entries, {
        caption: `${data.contest.name}, ${group.division}${group.facet ? `, ${group.facet}` : ""}`,
      }));
  }
}

function renderRubric(host, itemId, data) {
  const contest = data.contest;
  let lines = contest.criteria.map((c) => ({ id: c.id, label: c.label,
                                             max_points: c.max_points }));
  let errors = [];
  let saved = false;
  const holder = el("div");
  add(host, holder);

  const rules = el("textarea", { rows: 14 }, contest.rules_md || "");

  draw();

  function draw() {
    clear(holder);
    const total = lines.reduce((sum, line) => sum + (Number(line.max_points) || 0), 0);
    add(holder,
      errorSummary(errors),
      saved ? el("p", { class: "form-note" }, "Saved.") : null,
      field({ id: "contest-rules", label: "Rules",
              help: "Shown to everybody entering. **Bold** and lines starting "
                + "with a dash work as they do in the rest of the site.",
              control: rules, wide: true }),
      el("p", { class: "small muted" },
        `Divisions: ${contest.division_label}. These are set by the Convention `
        + "Book and are not changed here."),
      el("h2", {}, `Rubric — ${total} points`),
      el("p", { class: "small muted" },
        data.rubric_locked
          ? "Judges have already scored this contest, so lines can be reworded "
            + "but not added, removed or re-weighted."
          : "Each line is scored out of its points."),
      ...lines.map((line, index) => el("div", { class: "rubric" },
        field({ id: `line-${index}-label`, label: `Line ${index + 1}`,
                control: bind(input({ value: line.label, maxlength: 120 }),
                              (value) => { line.label = value; }) }),
        field({ id: `line-${index}-points`, label: "Points",
                control: bind(el("input", { type: "number", min: 1, max: 1000,
                                            value: line.max_points,
                                            disabled: data.rubric_locked }),
                              (value) => { line.max_points = value; }) }),
        data.rubric_locked ? null : button("Remove", {
          variant: "btn--small btn--quiet btn--danger",
          onclick: () => { lines = lines.filter((l) => l !== line); draw(); },
        }))),
      el("div", { class: "btn-row" },
        data.rubric_locked ? null : button("Add a line", {
          onclick: () => { lines.push({ label: "", max_points: 10 }); draw(); },
        }),
        button("Save the contest", { variant: "btn--primary", onclick: save })));
  }

  function bind(control, write) {
    control.addEventListener("input", () => { write(control.value); saved = false; });
    return control;
  }

  async function save() {
    try {
      await api.put(`/admin/contests/${itemId}`, {
        rules_md: rules.value,
        criteria: lines.map((l) => ({ id: l.id, label: l.label,
                                      max_points: Number(l.max_points) })),
      });
      const fresh = await api.get(`/admin/contests/${itemId}/results`);
      lines = fresh.contest.criteria.map((c) => ({ id: c.id, label: c.label,
                                                   max_points: c.max_points }));
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
