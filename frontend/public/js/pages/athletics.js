/* The Athletics Director's dashboard: Olympika.
 *
 * TWO PAGES, ONE MODULE.
 *   #/athletics         every event, how many have entered, what is set up,
 *                       and adding an event
 *   #/athletics/{id}    one event, in full:
 *       a race (individual)  heats and when they run; every entrant, who can
 *                            be moved between heats; "Assign heats" deals
 *                            everyone in at once
 *       a team event         every team (one delegate signed up each); "Draw
 *                            bracket" forms a single-elimination bracket and
 *                            can time every game; results are entered here
 *
 * EVERY TIME THE DIRECTOR SETS HERE REACHES THE MASTER SCHEDULE. The server
 * writes the heats, and one entry per round of a bracket, onto the Schedule
 * page in the same request, so there is nothing to "publish" and nothing to
 * keep in step. The Logistics chair sees those entries and cannot change them.
 *
 * Times are the clock as it reads in the hall (see when.js): the Director
 * picks a date and a time and the server works out the rest.
 */

import * as api from "../api.js";
import { add, el, clear, field, input, select, button, errorSummary, emptyState,
         loadingRows, table, check, ask, tell, personNumber,
         chapterNumber } from "../ui.js";
import { whenText } from "../when.js";

/* ------------------------------------------------------------------------ */
/* Shared pieces. Top-level functions, so nothing reaches into a sibling.    */
/* ------------------------------------------------------------------------ */

function problems(error) {
  return error.errors && error.errors.length ? error.errors : [error.message];
}

function kindText(kind) {
  return kind === "team" ? "Teams" : "Individuals";
}

function openPill(event) {
  return event.signup_open
    ? el("span", { class: "pill pill--done" }, "✓ Sign-up open")
    : el("span", { class: "pill" }, "Sign-up closed");
}

function entrantName(row) {
  return `${row.first_name} ${row.last_name}`;
}

function chapterText(row) {
  return `${chapterNumber({ number: row.school_number })} ${row.school_name}`;
}

/** Whole minutes from "09:30" to "10:15", or null if either is missing. */
function minutesBetween(start, end) {
  if (!start || !end) return null;
  const [h1, m1] = start.split(":").map(Number);
  const [h2, m2] = end.split(":").map(Number);
  return (h2 * 60 + m2) - (h1 * 60 + m1);
}

function link(href, text) {
  return el("a", { href }, text);
}

/* ------------------------------------------------------------------------ */

export async function athleticsPage(host, params = []) {
  if (params[0]) return eventPage(host, Number(params[0]));
  return eventsPage(host);
}

/* ------------------------------------------------------------------------ */
/* Every event                                                               */
/* ------------------------------------------------------------------------ */

async function eventsPage(host) {
  let data = null;
  let errors = [];
  let typed = { name: "", kind: "individual", location: "", description: "",
                max_per_school: "", signup_open: false };   // survives a refused save

  add(host, loadingRows(6, "Loading Olympika"));
  data = await api.get("/admin/athletics", { statusHost: host });
  render();

  function render() {
    clear(host);
    add(host,
      el("h1", {}, "Olympika"),
      el("p", { class: "lede" },
        "Every athletic event, who has entered, and when each is played. Open "
        + "an event to set its heats or draw its bracket; whatever you "
        + "schedule appears on the convention Schedule by itself."),
      summary(),
      eventsTable(),
      addForm());
  }

  function summary() {
    const open = data.events.filter((e) => e.signup_open).length;
    const entries = data.events.reduce((sum, e) => sum + e.entries, 0);
    const pair = (label, value, note) => el("div", { class: "stat" },
      el("span", { class: "stat__value" }, String(value)),
      el("span", { class: "label" }, label),
      note ? el("span", { class: "small muted" }, note) : null);
    return el("div", { class: "stats" },
      pair("Events", data.events.length),
      pair("Open for sign-up", open),
      pair("Entries", entries, "delegates and teams, all events"));
  }

  function eventsTable() {
    if (!data.events.length) {
      return emptyState("No events",
        "Add the first one below, like “100-meter dash”.");
    }
    return table([
      { key: "name", label: "Event",
        render: (e) => el("span", {}, el("strong", {}, link(`#/athletics/${e.id}`, e.name)),
          e.location ? el("span", { class: "small muted photo-description" }, e.location) : null) },
      { key: "kind", label: "Entered by", render: (e) => kindText(e.kind) },
      { key: "open", label: "Sign-up", render: openPill },
      { key: "entries", label: "Entries", num: true,
        render: (e) => String(e.entries) },
      { key: "plan", label: "Set up",
        render: (e) => (e.kind === "team"
          ? (e.bracket ? "Bracket drawn" : "No bracket yet")
          : (e.heats ? `${e.heats} heat${e.heats === 1 ? "" : "s"}, ${e.heats_timed} timed`
                     : "No heats yet")) },
      { key: "actions", label: "",
        render: (e) => el("div", { class: "btn-row" },
          button(e.signup_open ? "Close sign-up" : "Open sign-up", {
            variant: "btn--small",
            onclick: () => toggle(e),
          }),
          el("a", { class: "btn btn--small btn--quiet", href: `#/athletics/${e.id}` }, "Manage")) },
    ], data.events, { caption: "Olympika events" });
  }

  function addForm() {
    const name = input({ maxlength: data.max_name, placeholder: "100-meter dash",
                         value: typed.name });
    const kind = select([["individual", "Individuals, one by one", typed.kind === "individual"],
                         ["team", "Teams, one delegate signs up each", typed.kind === "team"]]);
    const place = input({ maxlength: data.max_location, placeholder: "Track",
                          value: typed.location });
    const description = el("textarea", { rows: 3, maxlength: data.max_description,
      placeholder: "Rules, equipment, who may enter. Delegates see this when they sign up." },
      typed.description);
    const limit = input({ type: "number", min: 1, placeholder: "No limit",
                          value: typed.max_per_school });
    const open = el("input", { type: "checkbox", checked: typed.signup_open || null });

    return el("section", { class: "form-section" },
      el("h2", {}, "Add an event"),
      el("div", { class: "panel" },
        errorSummary(errors),
        field({ id: "event-name", label: "Name", required: true, control: name, wide: true }),
        field({ id: "event-kind", label: "How delegates enter", control: kind, wide: true }),
        field({ id: "event-place", label: "Where", control: place, wide: true }),
        field({ id: "event-description", label: "Description", control: description, wide: true }),
        field({ id: "event-limit", label: "Most per chapter",
                help: "Entrants for a race, teams for a team event. Empty is no limit.",
                control: limit }),
        el("label", { class: "choice" }, open,
          el("span", {},
            el("span", { class: "choice__name" }, "Open sign-up now"),
            el("span", { class: "choice__why" },
              "Delegates can sign up only while this is ticked. You can change it any time."))),
        el("div", { class: "btn-row" },
          button("Add event", {
            variant: "btn--primary",
            onclick: () => create({
              name: name.value, kind: kind.value, location: place.value,
              description: description.value, max_per_school: limit.value,
              signup_open: open.checked,
            }),
          }))));
  }

  async function create(payload) {
    try {
      const result = await api.post("/admin/athletics/events", payload);
      location.hash = `#/athletics/${result.event.id}`;
    } catch (error) {
      typed = payload;
      errors = problems(error);
      render();
    }
  }

  async function toggle(event) {
    try {
      const result = await api.patch(`/admin/athletics/events/${event.id}`,
                                     { signup_open: !event.signup_open });
      event.signup_open = result.event.signup_open;
      errors = [];
    } catch (error) {
      await tell({ body: error.message });
    }
    render();
  }
}

/* ------------------------------------------------------------------------ */
/* One event                                                                 */
/* ------------------------------------------------------------------------ */

async function eventPage(host, eventId) {
  let data = null;
  let errors = {};             // section name -> messages from its last action
  let editingEvent = false;
  let editingMatch = null;     // id of the game whose form is open
  let filter = "";
  let entrantsNode = null;     // redrawn as the filter is typed
  let heatInputs = new Map();  // heat id -> its row's inputs, kept across redraws of one render

  add(host, loadingRows(8, "Loading the event"));
  data = await api.get(`/admin/athletics/events/${eventId}`, { statusHost: host });
  render();

  function render() {
    heatInputs = new Map();
    clear(host);
    const event = data.event;
    add(host,
      el("p", { class: "small" }, link("#/athletics", "← All events")),
      el("h1", {}, event.name, " ", openPill(event)),
      eventPanel());
    if (event.kind === "team") {
      add(host, teamsSection(), bracketSection());
    } else {
      add(host, heatsSection(), entrantsSection());
    }
  }

  /* One request against the server. Endpoints below the event itself answer
   * with the whole event as it now stands, which replaces `data`. */
  async function run(section, call) {
    try {
      const result = await call();
      if (result && result.event && result.heats) data = result;
      errors[section] = null;
    } catch (error) {
      errors[section] = problems(error);
    }
    render();
  }

  /* -- The event itself -------------------------------------------------- */

  function eventPanel() {
    const event = data.event;
    if (editingEvent) return eventForm();
    return el("section", { class: "form-section" },
      errorSummary(errors.event),
      event.description ? el("p", { class: "photo-description" }, event.description) : null,
      el("dl", { class: "detail" },
        el("dt", {}, "Entered by"), el("dd", {}, kindText(event.kind)),
        el("dt", {}, "Where"), el("dd", {}, event.location || "Not set"),
        el("dt", {}, "Most per chapter"), el("dd", {},
          event.max_per_school ? String(event.max_per_school) : "No limit")),
      el("div", { class: "btn-row" },
        button(event.signup_open ? "Close sign-up" : "Open sign-up", {
          variant: event.signup_open ? "" : "btn--primary",
          onclick: () => changeEvent({ signup_open: !event.signup_open }),
        }),
        button("Edit details", {
          onclick: () => { editingEvent = true; errors.event = null; render(); },
        }),
        button("Delete event", {
          variant: "btn--quiet btn--danger",
          onclick: removeEvent,
        })));
  }

  function eventForm() {
    const event = data.event;
    const name = input({ value: event.name, maxlength: data.max_name });
    const place = input({ value: event.location || "", maxlength: data.max_location });
    const description = el("textarea", { rows: 3, maxlength: data.max_description },
                           event.description || "");
    const limit = input({ type: "number", min: 1, value: event.max_per_school || "",
                          placeholder: "No limit" });
    return el("section", { class: "form-section" },
      el("h2", {}, "Edit details"),
      el("div", { class: "panel" },
        errorSummary(errors.event),
        field({ id: "edit-name", label: "Name", required: true, control: name, wide: true }),
        field({ id: "edit-place", label: "Where", control: place, wide: true }),
        field({ id: "edit-description", label: "Description", control: description, wide: true }),
        field({ id: "edit-limit", label: "Most per chapter", control: limit }),
        el("div", { class: "btn-row" },
          button("Save changes", {
            variant: "btn--primary",
            onclick: () => changeEvent({
              name: name.value, location: place.value,
              description: description.value, max_per_school: limit.value,
            }),
          }),
          button("Cancel", {
            variant: "btn--quiet",
            onclick: () => { editingEvent = false; errors.event = null; render(); },
          }))));
  }

  async function changeEvent(payload) {
    try {
      const result = await api.patch(`/admin/athletics/events/${eventId}`, payload);
      data.event = result.event;
      editingEvent = false;
      errors.event = null;
      // A renamed event is renamed on the schedule too; nothing to refresh here.
    } catch (error) {
      errors.event = problems(error);
    }
    render();
  }

  async function removeEvent() {
    const entered = data.event.kind === "team" ? data.teams.length : data.signups.length;
    const sure = await check({
      title: `Delete ${data.event.name}?`,
      body: (entered
        ? `Its ${entered} ${data.event.kind === "team" ? "team" : "sign-up"}`
          + `${entered === 1 ? "" : "s"}, ${data.event.kind === "team" ? "its bracket" : "its heats"} `
          + "and its entries on the Schedule are deleted with it."
        : "Nobody has entered, and its entries on the Schedule are removed."),
      confirmLabel: "Delete event",
      danger: true,
    });
    if (!sure) return;
    try {
      await api.del(`/admin/athletics/events/${eventId}`);
      location.hash = "#/athletics";
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  /* -- A race: heats and entrants --------------------------------------- */

  function heatsSection() {
    const heats = data.heats;
    const first = heats.length ? heats[0] : null;
    const second = heats.length > 1 ? heats[1] : null;

    const count = input({ type: "number", min: 0, max: data.max_heats,
                          value: heats.length || 1 });
    const date = input({ type: "date", value: first && first.date ? first.date : "" });
    const start = input({ type: "time", value: first && first.start ? first.start : "" });
    const between = input({ type: "number", min: 0, value: (second && first
      && minutesBetween(first.start, second.start)) || 15 });
    const length = input({ type: "number", min: 1, value: (first
      && minutesBetween(first.start, first.end)) || "" });

    const entrants = data.signups.length;
    const unassigned = data.signups.filter((s) => !s.heat_id).length;

    return el("section", { class: "form-section" },
      el("h2", {}, "Heats"),
      el("p", {},
        "Say how many heats there are and when the first one starts, and the "
        + "rest follow at the interval you give. Every heat with a time is on "
        + "the convention Schedule at once."),
      errorSummary(errors.heats),
      el("div", { class: "panel" },
        el("div", { class: "grid" },
          el("div", { class: "span-3" },
            field({ id: "heat-count", label: "How many heats", control: count })),
          el("div", { class: "span-3" },
            field({ id: "heat-date", label: "Date", control: date })),
          el("div", { class: "span-3" },
            field({ id: "heat-start", label: "First heat at", control: start })),
          el("div", { class: "span-3" },
            field({ id: "heat-between", label: "Minutes between starts", control: between }))),
        el("div", { class: "grid" },
          el("div", { class: "span-3" },
            field({ id: "heat-length", label: "Minutes each heat takes",
                    help: "Optional. Shown as the end time.", control: length }))),
        el("div", { class: "btn-row" },
          button(heats.length ? "Update the heats" : "Set up the heats", {
            variant: heats.length ? "" : "btn--primary",
            onclick: () => setHeats({
              count: count.value, date: date.value, start: start.value,
              minutes_between: between.value, minutes_long: length.value,
            }),
          }))),
      heats.length ? heatsTable() : null,
      heats.length
        ? el("div", { class: "btn-row" },
            button(`Assign ${entrants} ${entrants === 1 ? "entrant" : "entrants"} to heats`, {
              variant: "btn--primary",
              onclick: assign,
            }),
            unassigned && unassigned < entrants
              ? el("span", { class: "small muted" },
                  `${unassigned} not in a heat yet. Assigning again deals everyone afresh.`)
              : null)
        : null);
  }

  /* The inputs for one heat's row, made once per render so the columns of a
   * row (which are built separately) share them. */
  function controlsFor(heat) {
    if (!heatInputs.has(heat.id)) {
      heatInputs.set(heat.id, {
        label: input({ value: heat.label || "", maxlength: data.max_label,
                       placeholder: `Heat ${heat.number}`, "aria-label": `Name of heat ${heat.number}` }),
        date: input({ type: "date", value: heat.date || "",
                      "aria-label": `Date of heat ${heat.number}` }),
        start: input({ type: "time", value: heat.start || "",
                       "aria-label": `Start of heat ${heat.number}` }),
        end: input({ type: "time", value: heat.end || "",
                     "aria-label": `End of heat ${heat.number}` }),
      });
    }
    return heatInputs.get(heat.id);
  }

  function heatsTable() {
    return table([
      { key: "number", label: "Heat", render: (h) => String(h.number) },
      { key: "label", label: "Name", render: (h) => controlsFor(h).label },
      { key: "date", label: "Date", render: (h) => controlsFor(h).date },
      { key: "start", label: "Starts", render: (h) => controlsFor(h).start },
      { key: "end", label: "Ends", render: (h) => controlsFor(h).end },
      { key: "entrants", label: "Entrants", num: true, render: (h) => String(h.entrants) },
      { key: "save", label: "",
        render: (h) => button("Save", {
          variant: "btn--small",
          onclick: () => {
            const c = controlsFor(h);
            return run("heats", () => api.patch(`/admin/athletics/heats/${h.id}`, {
              label: c.label.value, date: c.date.value, start: c.start.value,
              end: c.end.value,
            }));
          },
        }) },
    ], data.heats, { caption: "Heats" });
  }

  async function setHeats(payload) {
    const removing = Number(payload.count) < data.heats.length;
    if (removing) {
      const sure = await check({
        title: "Remove heats?",
        body: "The last heats are deleted, and anyone in them is no longer in a heat. "
              + "Their entries come off the Schedule.",
        confirmLabel: "Remove heats", danger: true,
      });
      if (!sure) return;
    }
    // A blank date or time means "keep the times I already set".
    if (!payload.date || !payload.start) {
      delete payload.date;
      delete payload.start;
    }
    await run("heats", () => api.put(`/admin/athletics/events/${eventId}/heats`, payload));
  }

  async function assign() {
    if (data.signups.some((s) => s.heat_id)) {
      const sure = await check({
        title: "Deal everyone again?",
        body: "This replaces the current heats and lanes, including anyone you moved by hand.",
        confirmLabel: "Assign heats",
      });
      if (!sure) return;
    }
    await run("heats", () => api.post(`/admin/athletics/events/${eventId}/assign`, {}));
  }

  function entrantsSection() {
    const search = input({ type: "search", value: filter,
      placeholder: "Search by name or chapter", "aria-label": "Search entrants" });
    search.addEventListener("input", () => { filter = search.value; drawEntrants(); });
    entrantsNode = el("div", {});
    drawEntrants();
    return el("section", { class: "form-section" },
      el("h2", {}, `Entrants (${data.signups.length})`),
      el("p", {}, "Everyone who has signed up, in heat order. Change a heat or "
        + "lane to move someone; it saves as you choose."),
      errorSummary(errors.entrants),
      data.signups.length ? search : null,
      entrantsNode);
  }

  function drawEntrants() {
    clear(entrantsNode);
    if (!data.signups.length) {
      add(entrantsNode, emptyState("Nobody has signed up",
        data.event.signup_open
          ? "Delegates sign up from their Olympika page."
          : "Sign-up is closed. Open it so delegates can enter."));
      return;
    }
    const needle = filter.trim().toLowerCase();
    const rows = data.signups.filter((s) => !needle
      || `${entrantName(s)} ${s.school_name}`.toLowerCase().includes(needle));
    if (!rows.length) {
      add(entrantsNode, emptyState("Nobody matches", "Clear the search to see everyone."));
      return;
    }
    const heatOptions = (current) => [["", "Not in a heat", !current]].concat(
      data.heats.map((h) => [String(h.id),
        `Heat ${h.number}${h.label ? ` (${h.label})` : ""}`, h.id === current]));

    add(entrantsNode, table([
      { key: "name", label: "Name",
        render: (s) => el("span", {}, el("strong", {}, entrantName(s)), " ",
          el("span", { class: "mono small muted" },
             personNumber({ number: s.school_number }, s))) },
      { key: "chapter", label: "Chapter", render: chapterText },
      { key: "grade", label: "Grade", render: (s) => (s.grade ? String(s.grade) : "") },
      { key: "level", label: "Latin", render: (s) => s.latin_level || "" },
      { key: "heat", label: "Heat",
        render: (s) => select(heatOptions(s.heat_id), {
          "aria-label": `Heat for ${entrantName(s)}`,
          onchange: (event) => run("entrants", () => api.patch(
            `/admin/athletics/signups/${s.id}`,
            { heat_id: event.target.value ? Number(event.target.value) : null })),
        }) },
      { key: "lane", label: "Lane",
        render: (s) => input({
          type: "number", min: 1, value: s.lane || "", disabled: !s.heat_id || null,
          "aria-label": `Lane for ${entrantName(s)}`, class: "places-input",
          onchange: (event) => run("entrants", () => api.patch(
            `/admin/athletics/signups/${s.id}`,
            { heat_id: s.heat_id, lane: event.target.value })),
        }) },
      { key: "remove", label: "",
        render: (s) => button("Remove", {
          variant: "btn--small btn--quiet btn--danger",
          onclick: () => removeEntrant(s),
        }) },
    ], rows, { caption: "Entrants" }));
  }

  async function removeEntrant(entrant) {
    const sure = await check({
      title: `Remove ${entrantName(entrant)}?`,
      body: "They are taken out of the event. They can sign up again if it is open.",
      confirmLabel: "Remove", danger: true,
    });
    if (!sure) return;
    await run("entrants", () => api.del(`/admin/athletics/signups/${entrant.id}`));
  }

  /* -- A team event: teams and bracket ---------------------------------- */

  function teamsSection() {
    const drawn = data.matches.length > 0;
    return el("section", { class: "form-section" },
      el("h2", {}, `Teams (${data.teams.length})`),
      el("p", {}, "One delegate signed up each team and is its captain; the "
        + "other players are not entered anywhere."),
      errorSummary(errors.teams),
      data.teams.length
        ? table([
            { key: "seed", label: "Seed", num: true,
              render: (t) => (t.seed ? String(t.seed) : "—") },
            { key: "name", label: "Team", render: (t) => el("strong", {}, t.name) },
            { key: "chapter", label: "Chapter", render: chapterText },
            { key: "captain", label: "Captain",
              render: (t) => (t.captain_id
                ? el("span", {}, entrantName(t), " ",
                    el("span", { class: "mono small muted" },
                       personNumber({ number: t.school_number }, t)))
                : el("span", { class: "muted" }, "Withdrawn")) },
            { key: "actions", label: "",
              render: (t) => el("div", { class: "btn-row" },
                button("Rename", { variant: "btn--small", onclick: () => renameTeam(t) }),
                button("Remove", {
                  variant: "btn--small btn--quiet btn--danger",
                  disabled: drawn || null,
                  title: drawn ? "Clear the bracket first" : null,
                  onclick: () => removeTeam(t),
                })) },
          ], data.teams, { caption: "Teams" })
        : emptyState("No teams yet",
            data.event.signup_open
              ? "Delegates sign a team up from their Olympika page."
              : "Sign-up is closed. Open it so delegates can sign teams up."));
  }

  async function renameTeam(team) {
    const name = await ask({ title: "Rename the team", label: "Team name",
                             confirmLabel: "Rename" });
    if (!name) return;
    await run("teams", () => api.patch(`/admin/athletics/teams/${team.id}`, { name }));
  }

  async function removeTeam(team) {
    const sure = await check({
      title: `Remove ${team.name}?`,
      body: "The team is taken out of the event.", confirmLabel: "Remove team", danger: true,
    });
    if (!sure) return;
    await run("teams", () => api.del(`/admin/athletics/teams/${team.id}`));
  }

  function bracketSection() {
    const drawn = data.matches.length > 0;
    const date = input({ type: "date" });
    const start = input({ type: "time" });
    const minutes = input({ type: "number", min: 5, value: 40 });
    const fields = input({ placeholder: "Field 1, Field 2", maxlength: 200 });
    const plan = () => ({ date: date.value, start: start.value,
                          minutes: minutes.value, fields: fields.value });
    const first = data.matches.find((m) => m.date);
    if (first) {
      date.value = first.date;
      start.value = first.start;
    }

    return el("section", { class: "form-section" },
      el("h2", {}, "Bracket"),
      el("p", {},
        "Drawing a bracket shuffles the teams into a single-elimination "
        + "bracket, keeps teams from one chapter apart in the first round "
        + "where it can, and gives byes to the top seeds when the number of "
        + "teams is not a power of two. Add a start time to schedule every game "
        + "at once: each round starts when the last one ends."),
      errorSummary(errors.bracket),
      el("div", { class: "panel" },
        el("div", { class: "grid" },
          el("div", { class: "span-3" },
            field({ id: "bracket-date", label: "Date", control: date })),
          el("div", { class: "span-3" },
            field({ id: "bracket-start", label: "First game at", control: start })),
          el("div", { class: "span-3" },
            field({ id: "bracket-minutes", label: "Minutes per game", control: minutes })),
          el("div", { class: "span-3" },
            field({ id: "bracket-fields", label: "Fields",
                    help: "Names, separated by commas. Games run at once, one per field.",
                    control: fields }))),
        el("div", { class: "btn-row" },
          button(drawn ? "Draw a new bracket" : "Draw bracket", {
            variant: drawn ? "" : "btn--primary",
            disabled: data.teams.length < 2 || null,
            onclick: () => draw(plan()),
          }),
          drawn ? button("Re-time the games", {
            onclick: () => run("bracket", () => api.post(
              `/admin/athletics/events/${eventId}/bracket/times`, plan())),
          }) : null,
          drawn ? button("Clear the bracket", {
            variant: "btn--quiet btn--danger",
            onclick: clearBracket,
          }) : null),
        data.teams.length < 2
          ? el("p", { class: "small muted" }, "A bracket needs at least two teams.") : null),
      drawn ? bracketView() : null);
  }

  async function draw(plan) {
    if (data.matches.length) {
      const sure = await check({
        title: "Draw a new bracket?",
        body: "The current bracket and every result in it are replaced.",
        confirmLabel: "Draw bracket", danger: true,
      });
      if (!sure) return;
    }
    // No date or time: only the draw, and no games on the Schedule.
    if (!plan.date || !plan.start) {
      plan = {};
    }
    await run("bracket", () => api.post(`/admin/athletics/events/${eventId}/bracket`, plan));
  }

  async function clearBracket() {
    const sure = await check({
      title: "Clear the bracket?",
      body: "The bracket, every result in it and its games on the Schedule are removed. "
            + "Teams stay entered.",
      confirmLabel: "Clear bracket", danger: true,
    });
    if (!sure) return;
    editingMatch = null;
    await run("bracket", () => api.del(`/admin/athletics/events/${eventId}/bracket`));
  }

  function bracketView() {
    const rounds = [];
    for (let round = 1; round <= data.rounds; round += 1) {
      rounds.push(data.matches.filter((m) => m.round === round));
    }
    const open = data.matches.find((m) => m.id === editingMatch);
    return el("div", {},
      open ? matchForm(open) : null,
      ...rounds.map((games) => el("div", {},
        el("h3", {}, games[0].round_name),
        table([
          { key: "a", label: "Team", render: (m) => teamCell(m, "a") },
          { key: "b", label: "Against", render: (m) => (m.bye
              ? el("span", { class: "muted" }, "Bye")
              : teamCell(m, "b")) },
          { key: "result", label: "Result", render: resultText },
          { key: "when", label: "When",
            render: (m) => (m.bye ? "" : m.date ? whenText(m) : "Not timed") },
          { key: "field", label: "Where", render: (m) => m.field || "" },
          { key: "edit", label: "",
            render: (m) => (m.bye ? null : button("Score or move", {
              variant: "btn--small",
              onclick: () => { editingMatch = m.id; errors.match = null; render(); },
            })) },
        ], games, { caption: games[0].round_name }))));
  }

  function teamCell(match, side) {
    const name = match[`team_${side}_name`];
    const id = match[`team_${side}_id`];
    if (!id) return el("span", { class: "muted" }, "To be decided");
    return match.winner_id === id
      ? el("strong", {}, `✓ ${name}`) : name;
  }

  function resultText(match) {
    if (match.bye) return "";
    if (!match.winner_id) return "";
    const score = match.score_a !== null && match.score_b !== null
      ? `${match.score_a}–${match.score_b}` : "";
    return el("span", { class: "mono" }, score || "Played");
  }

  function matchForm(match) {
    const winner = select([
      ["", "Not played yet", !match.winner_id],
      ...(match.team_a_id ? [[String(match.team_a_id), match.team_a_name,
                              match.winner_id === match.team_a_id]] : []),
      ...(match.team_b_id ? [[String(match.team_b_id), match.team_b_name,
                              match.winner_id === match.team_b_id]] : []),
    ]);
    const scoreA = input({ type: "number", min: 0, value: match.score_a === null ? "" : match.score_a });
    const scoreB = input({ type: "number", min: 0, value: match.score_b === null ? "" : match.score_b });
    const date = input({ type: "date", value: match.date || "" });
    const start = input({ type: "time", value: match.start || "" });
    const end = input({ type: "time", value: match.end || "" });
    const place = input({ value: match.field || "", maxlength: data.max_location });

    return el("div", { class: "panel" },
      el("h3", {}, `${match.round_name}: ${match.team_a_name || "To be decided"} `
                   + `against ${match.team_b_name || "To be decided"}`),
      errorSummary(errors.match),
      el("div", { class: "grid" },
        el("div", { class: "span-6" },
          field({ id: "match-winner", label: "Winner", control: winner })),
        el("div", { class: "span-3" },
          field({ id: "match-score-a", label: `${match.team_a_name || "First"} score`,
                  control: scoreA })),
        el("div", { class: "span-3" },
          field({ id: "match-score-b", label: `${match.team_b_name || "Second"} score`,
                  control: scoreB }))),
      el("div", { class: "grid" },
        el("div", { class: "span-3" },
          field({ id: "match-date", label: "Date", control: date })),
        el("div", { class: "span-3" },
          field({ id: "match-start", label: "Starts", control: start })),
        el("div", { class: "span-3" },
          field({ id: "match-end", label: "Ends", control: end })),
        el("div", { class: "span-3" },
          field({ id: "match-field", label: "Where", control: place }))),
      el("div", { class: "btn-row" },
        button("Save", {
          variant: "btn--primary",
          onclick: async () => {
            await run("match", () => api.patch(`/admin/athletics/matches/${match.id}`, {
              winner_id: winner.value ? Number(winner.value) : null,
              score_a: scoreA.value, score_b: scoreB.value,
              date: date.value, start: start.value, end: end.value, field: place.value,
            }));
            if (!errors.match) editingMatch = null;
            render();
          },
        }),
        button("Cancel", {
          variant: "btn--quiet",
          onclick: () => { editingMatch = null; errors.match = null; render(); },
        })));
  }
}
