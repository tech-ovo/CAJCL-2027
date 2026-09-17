/* Pre-convention contests: entering them.
 *
 * THREE PAGES, ONE MODULE.
 *   #/contests            a delegate's own entries: art, myth, poetry, slogans
 *   #/chapter-contests    a chapter's Publicity portfolio, and -- for a
 *                         sponsor -- which of their delegates entered what,
 *                         with their files to download
 *   #/contest-submissions every entry from every chapter, for the
 *                         registration chairs. Names, no scores.
 *
 * ONE FORM OPEN AT A TIME. Five contests each showing an empty upload form is
 * a page nobody can read on a phone. Each contest is a short summary with a
 * button, and the button opens that contest's form in place.
 *
 * A FILE TRAVELS AS BASE64 INSIDE THE JSON BODY. It is read here, checked for
 * size before anything is sent, and the button carries the wait: a 20 MB
 * poster on school Wi-Fi takes a while, and the page must not go anywhere
 * while it does.
 */

import * as api from "../api.js";
import { add, el, clear, field, input, button, errorSummary, renderMarkdown,
         localDate, emptyState, loadingRows, table, check, tell,
         fullName, select, personNumber, chapterNumber } from "../ui.js";

const FILE_LABELS = { jpg: "JPG", png: "PNG", gif: "GIF", tiff: "TIFF",
                      pdf: "PDF", docx: "Word (.docx)", txt: "plain text (.txt)" };

/* ------------------------------------------------------------------------ */
/* Shared pieces. Top-level functions, so nothing reaches into a sibling.    */
/* ------------------------------------------------------------------------ */

function deadlineLine(data) {
  if (!data.deadline) return null;
  const when = localDate(data.deadline, { withTime: true });
  return el("p", { class: data.closed ? "form-note form-note--unsaved" : "form-note" },
    data.closed
      ? `Entries closed on ${when}. Nothing can be submitted, changed or withdrawn.`
      : `Due by ${when}, California time. You can replace or withdraw an entry until then.`);
}

function rulesBlock(contest) {
  const rubric = contest.criteria.length
    ? el("ul", {}, ...contest.criteria.map((c) =>
        el("li", {}, `${c.label} — ${c.max_points} points`)))
    : null;
  return el("details", {},
    el("summary", {}, "Rules and judging"),
    renderMarkdown(contest.rules_md || ""),
    rubric ? el("p", {}, el("strong", {}, `Judged out of ${contest.max_points}:`)) : null,
    rubric);
}

function statusPill(entry) {
  return entry
    ? el("span", { class: "pill pill--done" }, "✓ Entered")
    : el("span", { class: "pill" }, "Not entered");
}

function acceptList(contest) {
  return contest.accepted.map((t) => `.${t}`).join(",");
}

function describeTypes(contest) {
  const shown = contest.accepted.filter((t) => t !== "jpeg" && t !== "tif");
  return shown.map((t) => FILE_LABELS[t] || t.toUpperCase()).join(", ");
}

function megabytes(bytes) {
  return `${(bytes / 1048576).toFixed(bytes < 1048576 ? 2 : 1)} MB`;
}

/* Base64 without building one enormous string of char codes: a 20 MB file
 * passed to String.fromCharCode in one call overflows the argument limit. */
async function fileToBase64(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

/* Save a contest file. The session token travels in a header, which a plain
 * link cannot send, so the bytes are fetched and handed over as a Blob. The
 * name comes from the server unless the caller knows a better one. */
async function saveFile(path, name) {
  try {
    const result = await api.getBlob(path);
    const url = URL.createObjectURL(result.blob);
    const link = el("a", { href: url, download: name || result.name });
    add(document.body, link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) {
    await tell({ body: error.message });
  }
}

/* What an entry IS, in one table cell: its title, its slogan, its portfolio
 * link and categories -- whichever it has. */
function entryCell(row) {
  const parts = [];
  if (row.title) parts.push(el("strong", {}, row.title));
  if (row.text) parts.push(el("span", {}, row.text));
  if (row.translation) {
    parts.push(el("span", { class: "small muted" }, `Translation: ${row.translation}`));
  }
  if (row.link_url) {
    parts.push(el("a", { href: row.link_url, target: "_blank",
                         rel: "noopener noreferrer" }, "Open the portfolio"));
  }
  if (row.facets && row.facets.length) {
    parts.push(el("span", { class: "small muted" }, row.facets.join(", ")));
  }
  if (row.word_count !== null && row.word_count !== undefined) {
    parts.push(el("span", { class: "small muted" }, `${row.word_count} words`));
  }
  if (!parts.length) return "—";
  const cell = el("span", { style: "display:flex;flex-direction:column;gap:var(--space-1)" });
  for (const part of parts) add(cell, part);
  return cell;
}

function fileCell(row, path) {
  if (!row.has_file) return el("span", { class: "muted" }, "—");
  return button("Download", {
    variant: "btn--small",
    title: `${row.file} · ${megabytes(row.size_bytes)}`,
    onclick: () => saveFile(path),
  });
}

function extensionOf(name) {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot + 1).toLowerCase();
}

/* ------------------------------------------------------------------------ */
/* A delegate's contests                                                     */
/* ------------------------------------------------------------------------ */

export async function contestsPage(host) {
  let data = null;
  let editing = null;          // item_id whose form is open
  let errors = [];

  add(host, loadingRows(5, "Loading contests"));
  data = await api.get("/me/contests", { statusHost: host });
  render();

  function render() {
    clear(host);
    add(host,
      el("h1", {}, "Pre-convention contests"),
      el("p", { class: "lede" },
        "Digital art, a modern myth, a poem and two slogans, submitted here "
        + "before convention. Judges see your work without your name or your "
        + "chapter."),
      deadlineLine(data));

    if (!data.can_enter) {
      add(host, emptyState("These are for delegates",
        "Pre-convention contests are entered by delegates. Your chapter's "
        + "Publicity portfolio is on the chapter's Contests page."));
      return;
    }

    for (const contest of data.contests) add(host, section(contest));
  }

  function section(contest) {
    const entry = contest.entry;
    const open = editing === contest.item_id;
    const node = el("section", { class: "form-section", id: `contest-${contest.item_id}` },
      el("h2", {}, contest.name, " ", statusPill(entry)),
      el("p", { class: "small muted" },
        contest.division
          ? `Your division: ${contest.division}.`
          : contest.division_problem,
        contest.must_attend ? " You must attend convention to win." : ""),
      rulesBlock(contest));

    if (entry && !open) add(node, entrySummary(contest, entry));

    if (open) {
      add(node, entryForm(contest));
    } else if (!data.closed && contest.division) {
      add(node, el("div", { class: "btn-row" },
        button(entry ? "Replace this entry" : `Enter ${contest.name}`, {
          variant: entry ? "" : "btn--primary",
          onclick: () => { editing = contest.item_id; errors = []; render(); focusForm(contest); },
        }),
        entry ? button("Withdraw", {
          variant: "btn--quiet btn--danger",
          onclick: () => withdraw(contest),
        }) : null));
    }
    return node;
  }

  function focusForm(contest) {
    const target = document.getElementById(`contest-${contest.item_id}`);
    if (target) target.scrollIntoView({ block: "start" });
  }

  function entrySummary(contest, entry) {
    const rows = [];
    if (entry.title) rows.push(["Title", entry.title]);
    if (entry.text && contest.entry_kind === "text") rows.push(["Slogan", entry.text]);
    if (entry.translation) rows.push(["Translation", entry.translation]);
    if (entry.has_file) {
      rows.push(["File", `${entry.original_name} · ${megabytes(entry.size_bytes)}`]);
    }
    if (entry.word_count !== null && entry.word_count !== undefined) {
      rows.push(["Length", `${entry.word_count} words`
        + (entry.word_count_source === "counted" ? " (counted)" : " (as you told us)")]);
    }
    rows.push(["Division", entry.division]);
    rows.push(["Submitted", localDate(entry.updated_at, { withTime: true })]);

    return el("div", { class: "panel" },
      el("dl", { class: "detail" },
        ...rows.flatMap(([term, value]) => [el("dt", {}, term), el("dd", {}, value)])),
      entry.has_file
        ? el("div", { class: "btn-row" },
            button("Download what you sent", {
              variant: "btn--small",
              onclick: () => download(contest, entry),
            }))
        : null);
  }

  function download(contest, entry) {
    return saveFile(`/me/contests/${contest.item_id}/file`, entry.original_name);
  }

  function entryForm(contest) {
    const entry = contest.entry;
    const id = (name) => `c${contest.item_id}-${name}`;
    const form = el("div", { class: "panel" });
    add(form, errorSummary(errors));

    const controls = {};
    if (contest.needs_title) {
      controls.title = input({ value: entry ? entry.title || "" : "", maxlength: 200 });
      add(form, field({ id: id("title"), label: "Title", required: true,
                        control: controls.title, wide: true }));
    }

    if (contest.entry_kind === "text") {
      controls.text = input({ value: entry ? entry.text || "" : "",
                              maxlength: contest.max_chars || 200 });
      const counter = el("p", { class: "count-note" });
      const count = () => {
        counter.textContent =
          `${controls.text.value.length} of ${contest.max_chars} characters`;
      };
      controls.text.addEventListener("input", count);
      count();
      add(form,
        field({ id: id("text"), label: contest.needs_translation ? "Your slogan, in Latin" : "Your slogan",
                help: "Short enough for a bumper sticker or a button.",
                required: true, control: controls.text, wide: true }),
        counter);
      if (contest.needs_translation) {
        controls.translation = input({ value: entry ? entry.translation || "" : "",
                                       maxlength: 300 });
        add(form, field({ id: id("translation"), label: "English translation",
                          required: true, control: controls.translation, wide: true }));
      }
    }

    if (contest.entry_kind === "file") {
      controls.file = el("input", { type: "file", accept: acceptList(contest) });
      add(form, field({
        id: id("file"), label: entry ? "A new file (leave empty to keep yours)" : "Your file",
        help: `${describeTypes(contest)}, up to ${megabytes(data.max_file_bytes)}.`
          + (contest.key === "digital_art"
            ? " Use the highest resolution you have — 300 dpi at the least." : "")
          + (contest.accepted.includes("docx")
            ? " Leave your name and chapter out of the file itself." : ""),
        required: !entry, control: controls.file, wide: true }));

      const countsWords = contest.min_words !== null || contest.max_words !== null;
      if (countsWords) {
        const counted = entry && entry.word_count_source === "counted";
        controls.words = el("input", { type: "number", min: 1, step: 1,
          value: entry && !counted ? entry.word_count : "" });
        const wordsField = field({
          id: id("words"), label: "How many words?",
          help: `Only for a PDF, which cannot be counted automatically. A Word or `
            + `text file is counted for you. The limit is ${contest.min_words}–`
            + `${contest.max_words} words; outside it costs ${contest.words_penalty} `
            + `points per 100 words.`,
          control: controls.words });
        add(form, wordsField);
        // Shown only when it can matter: a PDF, or an entry already declared.
        const sync = () => {
          const chosen = controls.file.files[0];
          const needs = chosen
            ? extensionOf(chosen.name) === "pdf"
            : Boolean(entry && !counted);
          wordsField.hidden = !needs;
        };
        controls.file.addEventListener("change", sync);
        sync();
      }
    }

    add(form, el("div", { class: "btn-row" },
      button(entry ? "Replace my entry" : `Submit ${contest.name}`, {
        variant: "btn--primary",
        onclick: () => submit(contest, controls),
      }),
      button("Cancel", {
        variant: "btn--quiet",
        onclick: () => { editing = null; errors = []; render(); },
      })));
    return form;
  }

  async function submit(contest, controls) {
    const payload = {};
    const problems = [];
    if (controls.title) payload.title = controls.title.value;
    if (controls.text) payload.text = controls.text.value;
    if (controls.translation) payload.translation = controls.translation.value;
    if (controls.words && !controls.words.closest(".field").hidden) {
      payload.word_count = controls.words.value;
    }
    if (controls.file && controls.file.files[0]) {
      const chosen = controls.file.files[0];
      if (!contest.accepted.includes(extensionOf(chosen.name))) {
        problems.push(`${contest.name} accepts ${describeTypes(contest)} files.`);
      } else if (chosen.size > data.max_file_bytes) {
        problems.push(`That file is ${megabytes(chosen.size)}. The limit is `
          + `${megabytes(data.max_file_bytes)}; save it smaller and try again.`);
      } else {
        payload.file = { name: chosen.name, data: await fileToBase64(chosen) };
      }
    }
    if (problems.length) { errors = problems; render(); return; }

    // No statusHost: the cold-start ladder would sit over the form. The
    // button is already showing the wait.
    try {
      const result = await api.post(`/me/contests/${contest.item_id}`, payload);
      contest.entry = result.entry;
      editing = null;
      errors = [];
      render();
      focusForm(contest);
    } catch (error) {
      errors = error.errors && error.errors.length ? error.errors : [error.message];
      render();
    }
  }

  async function withdraw(contest) {
    const sure = await check({
      title: `Withdraw your ${contest.name} entry?`,
      body: "It is removed from judging. You can enter again before the deadline.",
      confirmLabel: "Withdraw entry",
      danger: true,
    });
    if (!sure) return;
    try {
      await api.del(`/me/contests/${contest.item_id}`);
      contest.entry = null;
      render();
    } catch (error) {
      await tell({ body: error.message });
    }
  }
}

/* ------------------------------------------------------------------------ */
/* A chapter's contests                                                      */
/* ------------------------------------------------------------------------ */

export async function chapterContestsPage(host, params = []) {
  const schoolId = params[0] ? Number(params[0]) : null;
  const query = schoolId ? `?school_id=${schoolId}` : "";
  let data = null;
  let editing = null;
  let errors = [];

  add(host, loadingRows(5, "Loading contests"));
  data = await api.get(`/sponsor/contests${query}`, { statusHost: host });
  render();

  function render() {
    clear(host);
    add(host,
      el("h1", {}, "Chapter contests"),
      el("p", { class: "lede" },
        `${data.school.name}'s Publicity portfolio, and the pre-convention `
        + "entries your delegates have submitted."),
      deadlineLine(data));

    for (const contest of data.contests) add(host, section(contest));

    if (data.students) add(host, studentsBlock());
  }

  function section(contest) {
    const entry = contest.entry;
    const open = editing === contest.item_id;
    const node = el("section", { class: "form-section" },
      el("h2", {}, contest.name, " ", statusPill(entry)),
      el("p", { class: "small muted" },
        contest.division ? `Division: ${contest.division}.` : contest.division_problem),
      rulesBlock(contest));

    if (entry && !open) {
      add(node, el("div", { class: "panel" },
        el("dl", { class: "detail" },
          el("dt", {}, "Portfolio"),
          el("dd", {}, el("a", { href: entry.link_url, target: "_blank",
                                 rel: "noopener noreferrer" }, entry.link_url)),
          el("dt", {}, "Categories"),
          el("dd", {}, entry.facets.join(", ")),
          el("dt", {}, "Submitted"),
          el("dd", {}, localDate(entry.updated_at, { withTime: true })))));
    }

    if (open) {
      add(node, portfolioForm(contest));
    } else if (!data.closed && contest.division) {
      add(node, el("div", { class: "btn-row" },
        button(entry ? "Change the portfolio" : "Submit your portfolio", {
          variant: entry ? "" : "btn--primary",
          onclick: () => { editing = contest.item_id; errors = []; render(); },
        }),
        entry ? button("Withdraw", {
          variant: "btn--quiet btn--danger",
          onclick: () => withdraw(contest),
        }) : null));
    }
    return node;
  }

  function portfolioForm(contest) {
    const entry = contest.entry;
    const link = input({ type: "url", value: entry ? entry.link_url : "",
                         placeholder: "https://docs.google.com/document/d/…" });
    const chosen = new Set(entry ? entry.facets : []);
    const boxes = contest.facet_list.map((facet) => {
      const box = el("input", { type: "checkbox", checked: chosen.has(facet) });
      return [facet, el("label", { class: "choice" }, box,
                        el("span", { class: "choice__name" }, facet)), box];
    });

    return el("div", { class: "panel" },
      errorSummary(errors),
      field({ id: "portfolio-link", label: "Link to the portfolio",
              help: "A Google document shared so that anyone with the link can view it.",
              required: true, control: link, wide: true }),
      el("fieldset", {},
        el("legend", { class: "label" }, "Categories your portfolio includes"),
        el("div", { class: "choices choices--two" }, ...boxes.map((b) => b[1]))),
      el("div", { class: "btn-row" },
        button(entry ? "Save the portfolio" : "Submit the portfolio", {
          variant: "btn--primary",
          onclick: async () => {
            try {
              const result = await api.post(`/sponsor/contests/${contest.item_id}`, {
                school_id: schoolId,
                link_url: link.value,
                facets: boxes.filter((b) => b[2].checked).map((b) => b[0]),
              });
              contest.entry = result.entry;
              editing = null;
              errors = [];
              render();
            } catch (error) {
              errors = error.errors && error.errors.length ? error.errors : [error.message];
              render();
            }
          },
        }),
        button("Cancel", {
          variant: "btn--quiet",
          onclick: () => { editing = null; errors = []; render(); },
        })));
  }

  async function withdraw(contest) {
    const sure = await check({
      title: `Withdraw ${data.school.name}'s ${contest.name} portfolio?`,
      body: "It is removed from judging. You can submit again before the deadline.",
      confirmLabel: "Withdraw portfolio",
      danger: true,
    });
    if (!sure) return;
    try {
      await api.del(`/sponsor/contests/${contest.item_id}${query}`);
      contest.entry = null;
      render();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  function studentsBlock() {
    const rows = data.students;
    return el("section", { class: "form-section" },
      el("h2", {}, "Your delegates' entries"),
      rows.length
        ? table([
            { key: "contest", label: "Contest" },
            { key: "name", label: "Delegate",
              render: (row) => fullName(row)
                + (row.status !== "active" ? " (not attending)" : "") },
            { key: "division", label: "Division" },
            { key: "entry", label: "Entry",
              render: (row) => entryCell(row) },
            { key: "file", label: "File",
              render: (row) => fileCell(row,
                `/sponsor/contests/entries/${row.id}/file`) },
            { key: "updated_at", label: "Submitted",
              render: (row) => localDate(row.updated_at) },
          ], rows, { caption: "Pre-convention entries from this chapter" })
        : emptyState("No entries yet",
            "When your delegates submit a contest entry from their own Contests "
            + "page, it appears here."));
  }
}

/* ------------------------------------------------------------------------ */
/* Every submission, for the registration chairs                             */
/* ------------------------------------------------------------------------ */

/* WHO HAS SENT WHAT. The question a registration chair is asked is "did my
 * student's poster arrive?", so this is a list with names and chapters and
 * the files themselves -- and no scores, which belong to Contest results.
 *
 * Filtering is local: everything is already here. Only the list under the
 * filters is redrawn, so the search box keeps its focus while typing. */
export async function contestSubmissionsPage(host) {
  let data = null;
  let contestFilter = "";
  let chapterFilter = "";
  let needle = "";

  add(host, loadingRows(8, "Loading submissions"));
  data = await api.get("/admin/contests/submissions", { statusHost: host });

  const chapters = [];
  const seen = new Set();
  for (const row of data.entries) {
    if (seen.has(row.school_id)) continue;
    seen.add(row.school_id);
    chapters.push(row);
  }
  chapters.sort((a, b) => (a.school_number || 0) - (b.school_number || 0)
                          || a.school_name.localeCompare(b.school_name));

  const results = el("div", {});
  clear(host);
  add(host,
    el("h1", {}, "Contest submissions"),
    el("p", { class: "lede" },
      "Every pre-convention entry from every chapter, with who sent it. "
      + "Scores are on Contest results."),
    deadlineLine(data),
    headline(),
    filters(),
    results);
  draw();

  function headline() {
    const people = new Set(data.entries.filter((r) => r.person_id !== null)
                                       .map((r) => r.person_id));
    const stat = (label, value) => el("div", { class: "stat" },
      el("span", { class: "stat__value" }, String(value)),
      el("span", { class: "label" }, label));
    return el("div", { class: "stats" },
      stat("Entries", data.entries.length),
      stat("Chapters", chapters.length),
      stat("Delegates", people.size),
      ...data.contests.map((c) => stat(c.name, c.entries)));
  }

  function filters() {
    const contest = select(
      [["", "All contests"], ...data.contests.map((c) => [String(c.item_id), c.name])],
      { id: "submissions-contest",
        onchange: (event) => { contestFilter = event.target.value; draw(); } });
    const chapter = select(
      [["", "All chapters"],
       ...chapters.map((c) => [String(c.school_id),
                               `${chapterNumber({ number: c.school_number })} ${c.school_name}`])],
      { id: "submissions-chapter",
        onchange: (event) => { chapterFilter = event.target.value; draw(); } });
    const search = input({
      id: "submissions-search", type: "search",
      placeholder: "Name or title",
      oninput: (event) => { needle = event.target.value.trim().toLowerCase(); draw(); },
    });
    return el("div", { class: "btn-row", style: "margin-top:var(--space-6);align-items:flex-end" },
      field({ id: "submissions-contest", label: "Contest", control: contest }),
      field({ id: "submissions-chapter", label: "Chapter", control: chapter }),
      field({ id: "submissions-search", label: "Search", control: search }));
  }

  function matches(row) {
    if (contestFilter && String(row.item_id) !== contestFilter) return false;
    if (chapterFilter && String(row.school_id) !== chapterFilter) return false;
    if (!needle) return true;
    const haystack = [row.first_name, row.last_name, row.title, row.text,
                      row.school_name].filter(Boolean).join(" ").toLowerCase();
    return haystack.includes(needle);
  }

  function draw() {
    clear(results);
    const rows = data.entries.filter(matches);
    if (!data.entries.length) {
      add(results, emptyState("No entries yet",
        "When delegates and sponsors submit pre-convention entries, they appear here."));
      return;
    }
    add(results,
      el("p", { class: "small muted" },
        `Showing ${rows.length} of ${data.entries.length}.`),
      rows.length
        ? table([
            { key: "school_name", label: "Chapter",
              render: (row) => el("a", { href: `#/chapter-contests/${row.school_id}` },
                `${chapterNumber({ number: row.school_number })} ${row.school_name}`) },
            { key: "contest", label: "Contest" },
            { key: "division", label: "Division" },
            { key: "name", label: "Entrant",
              render: (row) => row.person_id === null
                ? el("span", { class: "muted" }, "The chapter")
                : el("span", {},
                    fullName(row), " ",
                    el("span", { class: "small muted mono" },
                       personNumber({ number: row.school_number }, row)),
                    row.person_status !== "active"
                      ? el("span", { class: "pill", style: "margin-left:.5rem" },
                           "Not attending")
                      : null) },
            { key: "entry", label: "Entry", render: (row) => entryCell(row) },
            { key: "file", label: "File",
              render: (row) => fileCell(row,
                `/admin/contests/entries/${row.id}/file`) },
            { key: "updated_at", label: "Submitted",
              render: (row) => localDate(row.updated_at, { withTime: true }) },
          ], rows, { caption: "Pre-convention contest submissions" })
        : emptyState("Nothing matches", "Try a different contest, chapter or search."));
  }
}
