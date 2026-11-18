/* The activities potluck, for the Activities chair.
 *
 *   #/potluck    the activities that need helpers, who is helping with each,
 *                and the form to add or change one
 *
 * An activity is a name, a blurb, and optionally a place, a time and how many
 * helpers are wanted. Attendees tick the ones they would help run on their own
 * sheet; an adult's pick counts at once, a delegate's counts once their
 * sponsor approves it. This page shows only the approved ones, with a name and
 * a chapter, and how many are still waiting on a sponsor.
 *
 * An activity with a time appears on the master schedule by itself.
 */

import * as api from "../api.js";
import { add, el, clear, table, field, input, button, errorSummary,
         emptyState, loadingRows, check, tell } from "../ui.js";
import { whenText } from "../when.js";

function errorsOf(error) {
  return error.errors && error.errors.length ? error.errors : [error.message];
}

function helpersText(activity) {
  const wanted = activity.capacity === null ? "" : ` of ${activity.capacity}`;
  const waiting = activity.waiting
    ? ` (${activity.waiting} waiting on a sponsor)` : "";
  return `${activity.approved}${wanted}${waiting}`;
}

export async function potluckPage(host) {
  add(host, loadingRows(6, "Loading the potluck"));
  const data = await api.get("/admin/potluck", { statusHost: host });
  clear(host);

  let editing = null;      // activity id being edited
  let pending = null;      // what was typed into a form that was refused
  let errors = [];
  let expanded = new Set();

  add(host,
    el("h1", {}, "Activities potluck"),
    el("p", { class: "lede" },
      "Activities that need helpers at convention. Attendees tick the ones "
      + "they would help run on their sheet; delegates need their sponsor's "
      + "approval first. Give an activity a time and it is added to the "
      + "schedule for you."));
  const body = el("div", {});
  add(host, body);
  draw();

  function draw() {
    clear(body);
    if (data.activities.length) {
      add(body, table([
        { key: "name", label: "Activity",
          render: (row) => el("span", {}, el("strong", {}, row.name),
            row.description
              ? el("span", { class: "small muted photo-description" }, row.description)
              : null) },
        { key: "when", label: "When and where",
          render: (row) => el("span", {},
            row.date ? whenText(row) : el("span", { class: "muted" }, "Not scheduled"),
            row.location
              ? el("span", { class: "small muted", style: "display:block" }, row.location)
              : null) },
        { key: "helpers", label: "Helpers", render: (row) => helpersText(row) },
        { key: "open", label: "Picking",
          render: (row) => row.open
            ? el("span", { class: "pill pill--done" }, "✓ Open")
            : el("span", { class: "pill" }, "Closed") },
        { key: "actions", label: "",
          render: (row) => el("div", { class: "btn-row" },
            button(expanded.has(row.id) ? "Hide helpers" : "Helpers", {
              variant: "btn--small",
              onclick: () => {
                if (expanded.has(row.id)) expanded.delete(row.id);
                else expanded.add(row.id);
                draw();
              },
            }),
            button(row.open ? "Close" : "Open", {
              variant: "btn--small btn--quiet",
              onclick: () => save(row, { open: !row.open }),
            }),
            button("Edit", {
              variant: "btn--small btn--quiet",
              onclick: () => { editing = row.id; pending = null; errors = []; draw();
                               scrollToForm(); },
            }),
            button("Delete", {
              variant: "btn--small btn--quiet btn--danger",
              onclick: () => remove(row),
            })) },
      ], data.activities, { caption: "Potluck activities" }));

      for (const activity of data.activities.filter((a) => expanded.has(a.id))) {
        add(body, helpersPanel(activity));
      }
    } else {
      add(body, emptyState("No activities yet",
        "Add the first one below. Attendees see it on their sheets as soon as "
        + "it is added."));
    }

    const current = data.activities.find((a) => a.id === editing) || null;
    add(body, form(current));
  }

  function helpersPanel(activity) {
    const rows = activity.volunteers;
    return el("section", { class: "panel", style: "margin-top:1rem" },
      el("h2", {}, `Helping with ${activity.name} (${rows.length})`),
      rows.length
        ? table([
            { key: "name", label: "Name",
              render: (row) => row.name },
            { key: "chapter", label: "Chapter",
              render: (row) => row.adult
                ? el("span", {}, row.school_name, " ",
                     el("span", { class: "pill" }, "Adult"))
                : row.school_name },
          ], rows, { caption: `Approved helpers for ${activity.name}` })
        : el("p", { class: "muted" },
            activity.waiting
              ? `Nobody is approved yet. ${activity.waiting} waiting on a sponsor.`
              : "Nobody has signed up yet."));
  }

  function scrollToForm() {
    const target = document.getElementById("potluck-form");
    if (target) target.scrollIntoView({ block: "start" });
  }

  function form(current) {
    const shown = pending || (current ? {
      name: current.name, description: current.description || "",
      location: current.location || "", date: current.date || "",
      start: current.start || "", end: current.end || "",
      capacity: current.capacity === null ? "" : String(current.capacity),
      open: current.open,
    } : { name: "", description: "", location: "", date: "", start: "", end: "",
          capacity: "", open: true });

    const name = input({ value: shown.name, maxlength: data.max_name,
                         placeholder: "Face painting" });
    const description = el("textarea", { rows: 3, maxlength: data.max_description,
      placeholder: "What helpers will be doing, what to bring, who it suits." },
      shown.description);
    const place = input({ value: shown.location, maxlength: data.max_location,
                          placeholder: "Quad" });
    const date = input({ type: "date", value: shown.date });
    const start = input({ type: "time", value: shown.start });
    const end = input({ type: "time", value: shown.end });
    const capacity = input({ type: "number", min: "1", max: String(data.max_capacity),
                             value: shown.capacity, inputmode: "numeric" });
    const open = el("input", { type: "checkbox", checked: shown.open || null });

    const values = () => ({
      name: name.value, description: description.value, location: place.value,
      date: date.value, start: start.value, end: end.value,
      capacity: capacity.value, open: open.checked,
    });

    return el("section", { class: "form-section", id: "potluck-form" },
      el("h2", {}, current ? `Edit “${current.name}”` : "Add an activity"),
      el("div", { class: "panel" },
        errorSummary(errors),
        field({ id: "potluck-name", label: "Name", required: true,
                control: name, wide: true }),
        field({ id: "potluck-description", label: "Blurb",
                help: "Shown to everyone choosing activities.",
                control: description, wide: true }),
        field({ id: "potluck-location", label: "Where", control: place, wide: true }),
        el("div", { class: "grid" },
          el("div", { class: "span-4" },
            field({ id: "potluck-date", label: "Date",
                    help: "Leave the date and times empty if it is not scheduled yet.",
                    control: date })),
          el("div", { class: "span-4" },
            field({ id: "potluck-start", label: "Starts", control: start })),
          el("div", { class: "span-4" },
            field({ id: "potluck-end", label: "Ends", control: end }))),
        field({ id: "potluck-capacity", label: "Helpers wanted",
                help: "Leave empty for no limit. A full activity stops taking picks.",
                control: capacity }),
        el("label", { class: "choice" }, open,
          el("span", {},
            el("span", { class: "choice__name" }, "Taking helpers"),
            el("span", { class: "choice__why" },
              "Untick to stop new picks. People who already picked it stay."))),
        el("div", { class: "btn-row" },
          button(current ? "Save changes" : "Add activity", {
            variant: "btn--primary",
            onclick: () => (current ? save(current, values(), true) : create(values())),
          }),
          current ? button("Cancel", {
            variant: "btn--quiet",
            onclick: () => { editing = null; pending = null; errors = []; draw(); },
          }) : null)));
  }

  async function create(values) {
    try {
      const result = await api.post("/admin/potluck", values);
      data.activities.push(result.activity);
      data.activities.sort(compare);
      pending = null;
      errors = [];
      draw();
    } catch (error) {
      pending = values;
      errors = errorsOf(error);
      draw();
    }
  }

  async function save(row, payload, fromForm = false) {
    try {
      const result = await api.patch(`/admin/potluck/${row.id}`, payload);
      // Keep the helper list: the server's reply is the activity alone.
      Object.assign(row, result.activity);
      data.activities.sort(compare);
      editing = null;
      pending = null;
      errors = [];
      draw();
    } catch (error) {
      if (fromForm) {
        pending = payload;
        errors = errorsOf(error);
        draw();
      } else {
        await tell({ body: error.message });
      }
    }
  }

  async function remove(row) {
    const sure = await check({
      title: `Delete “${row.name}”?`,
      body: row.approved || row.waiting
        ? `Everyone who picked it is taken off it, and it comes off the schedule. `
          + `${row.approved + row.waiting} `
          + `${row.approved + row.waiting === 1 ? "person has" : "people have"} picked it.`
        : "Nobody has picked it. It comes off the schedule if it was on it.",
      confirmLabel: "Delete activity",
      danger: true,
    });
    if (!sure) return;
    try {
      await api.del(`/admin/potluck/${row.id}`);
      data.activities = data.activities.filter((a) => a.id !== row.id);
      if (editing === row.id) editing = null;
      draw();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  /* The server's order: the chair's sort order, then name. A new or changed
   * activity is placed the same way so the table does not jump on reload. */
  function compare(a, b) {
    return (a.sort_order - b.sort_order)
      || String(a.name).toLowerCase().localeCompare(String(b.name).toLowerCase());
  }
}
