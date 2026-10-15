/* The master convention schedule.
 *
 * TWO PAGES, ONE MODULE.
 *   #/schedule        what happens, where and when. Open to everyone, signed
 *                     in or not, because it is the page a parent follows from
 *                     the welcome page and a delegate opens on a phone.
 *   #/schedule/edit   the Logistics chair: add, change and delete entries, and
 *                     keep drafts back until they are ready.
 *
 * ENTRIES THE ATHLETICS DIRECTOR SCHEDULES ARE ON THIS PAGE TOO -- every heat,
 * and every round of the Ultimate Frisbee bracket. The server writes them
 * there when the Director sets a time, so nothing here joins two lists. They
 * are marked "Olympika" and the editor shows them without Edit or Delete: they
 * are changed on the Athletics page and follow here.
 *
 * TIMES ARE THE CLOCK AS IT READS IN THE HALL (see when.js). The editor sends
 * a date and a time and the server works out the zone.
 */

import * as api from "../api.js";
import { add, el, clear, field, input, button, errorSummary, emptyState,
         loadingRows, table, check, tell } from "../ui.js";
import { hasScope } from "../main.js";
import { dayText, rangeText, isHappening } from "../when.js";

/* ------------------------------------------------------------------------ */
/* Shared pieces. Top-level functions, so nothing reaches into a sibling.    */
/* ------------------------------------------------------------------------ */

/** Entries grouped by their date, in the order the server sent them. */
function byDay(items) {
  const days = [];
  for (const item of items) {
    let day = days.find((d) => d.date === item.date);
    if (!day) {
      day = { date: item.date, items: [] };
      days.push(day);
    }
    day.items.push(item);
  }
  return days;
}

function sourcePill(item) {
  return item.source === "olympika"
    ? el("span", { class: "pill" }, "Olympika") : null;
}

function titleCell(item) {
  return el("span", {},
    el("strong", {}, item.title), " ", sourcePill(item),
    item.description
      ? el("span", { class: "small muted photo-description" }, item.description)
      : null);
}

/* ------------------------------------------------------------------------ */
/* Everybody's schedule                                                      */
/* ------------------------------------------------------------------------ */

export async function schedulePage(host) {
  let data = null;
  let filter = "";
  let bodyNode = null;         // the part under the search box, redrawn as you type

  add(host, loadingRows(8, "Loading the schedule"));
  data = await api.get("/public/schedule", { statusHost: host });
  render();

  function render() {
    clear(host);
    add(host,
      el("h1", {}, "Schedule"),
      el("p", { class: "lede" },
        "What happens at convention, and where. Times are California time. "
        + "If something moves, this page is where it changes first."),
      toolbar());

    bodyNode = el("div", {});
    add(host, bodyNode);
    draw();
  }

  function toolbar() {
    const search = input({
      type: "search", placeholder: "Search, like “Frisbee” or “Auditorium”",
      value: filter, "aria-label": "Search the schedule",
    });
    search.addEventListener("input", () => {
      filter = search.value;
      draw();
    });
    return el("div", { class: "btn-row" },
      search,
      button("Refresh", { variant: "btn--quiet", onclick: refresh }),
      hasScope("logistics")
        ? el("a", { class: "btn", href: "#/schedule/edit" }, "Edit the schedule")
        : null);
  }

  async function refresh() {
    data = await api.get("/public/schedule");
    render();
  }

  function draw() {
    const body = bodyNode;
    clear(body);
    const needle = filter.trim().toLowerCase();
    const items = data.items.filter((item) => !needle
      || [item.title, item.location, item.description].join(" ")
          .toLowerCase().includes(needle));

    if (!data.items.length) {
      add(body, emptyState("Nothing is scheduled yet",
        "The schedule is posted here as it is settled. Check back closer to "
        + "convention."));
      return;
    }
    if (!items.length) {
      add(body, emptyState("Nothing matches",
        "Nothing on the schedule mentions that. Clear the search to see all of it."));
      return;
    }

    for (const day of byDay(items)) {
      add(body, el("section", { class: "form-section" },
        el("h2", {}, dayText(day.date)),
        table([
          { key: "time", label: "Time",
            render: (item) => el("span", { class: "mono" },
              rangeText(item.start, item.end),
              isHappening(item, data.now)
                ? el("span", { class: "pill pill--done" }, "Now") : null) },
          { key: "title", label: "What", render: titleCell },
          { key: "location", label: "Where", render: (item) => item.location || "" },
        ], day.items, { caption: `Schedule for ${dayText(day.date)}` })));
    }
  }
}

/* ------------------------------------------------------------------------ */
/* The Logistics chair                                                       */
/* ------------------------------------------------------------------------ */

export async function scheduleEditorPage(host) {
  let data = null;
  let editing = null;          // entry being edited, or null for a new one
  let errors = [];
  let pending = null;          // what was typed when a save was refused, so it is not lost
  let lastDate = "";           // so a run of entries on one day need not retype it

  add(host, loadingRows(8, "Loading the schedule"));
  data = await api.get("/admin/schedule", { statusHost: host });
  lastDate = data.items.length ? data.items[data.items.length - 1].date : "";
  render();

  function render() {
    clear(host);
    add(host,
      el("h1", {}, "Edit the schedule"),
      el("p", { class: "lede" },
        "Everything here is what delegates read on the Schedule page. Untick "
        + "“Show on the schedule” to keep an entry back until it is ready. "
        + "Heats and games the Athletics Director sets appear on their own; "
        + "change those on the Athletics page."),
      el("div", { class: "btn-row" },
        el("a", { class: "btn btn--quiet", href: "#/schedule" }, "See it as delegates do")),
      list(),
      form());
  }

  function list() {
    if (!data.items.length) {
      return emptyState("Nothing on the schedule",
        "Add the first entry below, like “Opening ceremony”.");
    }
    return el("div", {},
      ...byDay(data.items).map((day) => el("section", { class: "form-section" },
        el("h2", {}, dayText(day.date)),
        table([
          { key: "time", label: "Time",
            render: (item) => el("span", { class: "mono" }, rangeText(item.start, item.end)) },
          { key: "title", label: "What",
            render: (item) => el("span", {}, titleCell(item), " ",
              item.published ? null : el("span", { class: "pill" }, "Draft")) },
          { key: "location", label: "Where", render: (item) => item.location || "" },
          { key: "actions", label: "",
            render: (item) => (item.editable
              ? el("div", { class: "btn-row" },
                  button("Edit", {
                    variant: "btn--small",
                    onclick: () => begin(item),
                  }),
                  button("Delete", {
                    variant: "btn--small btn--quiet btn--danger",
                    onclick: () => remove(item),
                  }))
              : el("span", { class: "small muted" }, "Set on the Athletics page")) },
        ], day.items, { caption: `Entries for ${dayText(day.date)}` }))));
  }

  function begin(item) {
    editing = item;
    pending = null;
    errors = [];
    render();
    const target = document.getElementById("schedule-form");
    if (target) target.scrollIntoView({ block: "start" });
  }

  function form() {
    const current = editing;
    // What was typed wins over what was saved: a refused save keeps the form.
    const shown = pending || (current ? {
      title: current.title, date: current.date, start: current.start,
      end: current.end || "", location: current.location || "",
      description: current.description || "", published: current.published,
    } : { title: "", date: lastDate, start: "", end: "", location: "",
          description: "", published: true });
    const title = input({ value: shown.title,
                          maxlength: data.max_title, placeholder: "Opening ceremony" });
    const date = input({ type: "date", value: shown.date });
    const start = input({ type: "time", value: shown.start });
    const end = input({ type: "time", value: shown.end });
    const place = input({ value: shown.location,
                          maxlength: data.max_location, placeholder: "Auditorium" });
    const description = el("textarea", { rows: 3, maxlength: data.max_description,
      placeholder: "Anything delegates should know: what to bring, what to wear." },
      shown.description);
    const published = el("input", { type: "checkbox",
      checked: shown.published || null });

    return el("section", { class: "form-section", id: "schedule-form" },
      el("h2", {}, current ? `Edit “${current.title}”` : "Add an entry"),
      el("div", { class: "panel" },
        errorSummary(errors),
        field({ id: "schedule-title", label: "What", required: true,
                control: title, wide: true }),
        el("div", { class: "grid" },
          el("div", { class: "span-4" },
            field({ id: "schedule-date", label: "Date", required: true, control: date })),
          el("div", { class: "span-4" },
            field({ id: "schedule-start", label: "Starts", required: true, control: start })),
          el("div", { class: "span-4" },
            field({ id: "schedule-end", label: "Ends",
                    help: "Leave empty for a moment, like “Lights out”.",
                    control: end }))),
        field({ id: "schedule-location", label: "Where", control: place, wide: true }),
        field({ id: "schedule-description", label: "Details", control: description,
                wide: true }),
        el("label", { class: "choice" }, published,
          el("span", {},
            el("span", { class: "choice__name" }, "Show on the schedule"),
            el("span", { class: "choice__why" },
              "Untick to keep it as a draft only you can see."))),
        el("div", { class: "btn-row" },
          button(current ? "Save changes" : "Add to the schedule", {
            variant: "btn--primary",
            onclick: () => save({
              title: title.value, date: date.value, start: start.value,
              end: end.value, location: place.value,
              description: description.value, published: published.checked,
            }),
          }),
          current ? button("Cancel", {
            variant: "btn--quiet",
            onclick: () => { editing = null; pending = null; errors = []; render(); },
          }) : null)));
  }

  async function save(payload) {
    try {
      const result = editing
        ? await api.patch(`/admin/schedule/${editing.id}`, payload)
        : await api.post("/admin/schedule", payload);
      const saved = result.item;
      data.items = data.items.filter((item) => item.id !== saved.id).concat(saved);
      data.items.sort((a, b) => (a.date + a.start).localeCompare(b.date + b.start)
                                || a.id - b.id);
      lastDate = saved.date;
      editing = null;
      pending = null;
      errors = [];
      render();
    } catch (error) {
      pending = payload;
      errors = error.errors && error.errors.length ? error.errors : [error.message];
      render();
    }
  }

  async function remove(item) {
    const sure = await check({
      title: `Delete “${item.title}”?`,
      body: "It comes off the schedule at once, for everyone.",
      confirmLabel: "Delete entry",
      danger: true,
    });
    if (!sure) return;
    try {
      await api.del(`/admin/schedule/${item.id}`);
      data.items = data.items.filter((other) => other.id !== item.id);
      if (editing && editing.id === item.id) editing = null;
      render();
    } catch (error) {
      await tell({ body: error.message });
    }
  }
}
