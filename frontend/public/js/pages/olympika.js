/* Olympika, for a delegate: sign up, and see where and when you play.
 *
 * #/olympika
 *
 * TWO KINDS OF EVENT, TWO WAYS IN.
 *   A race or a tournament (the 100 m dash, Chess) is entered by yourself.
 *   Once the Athletics Director has dealt the entrants into heats, this page
 *   shows YOUR heat, lane and time.
 *
 *   A team event (Ultimate Frisbee) is entered by ONE person for the whole
 *   team, who becomes its captain. Nobody else on the team signs up. Once
 *   the bracket is drawn, this page shows the captain each of the team's games.
 *
 * The Director opens and closes sign-up. A closed event is listed, so a
 * delegate knows it exists, but has no button.
 */

import * as api from "../api.js";
import { add, el, clear, field, input, button, errorSummary, emptyState,
         loadingRows, table, check } from "../ui.js";
import { whenText, rangeText, dayText } from "../when.js";

/* ------------------------------------------------------------------------ */
/* Shared pieces. Top-level functions, so nothing reaches into a sibling.    */
/* ------------------------------------------------------------------------ */

function statusPill(event) {
  if (event.entry) return el("span", { class: "pill pill--done" }, "✓ Signed up");
  return el("span", { class: "pill" },
    event.signup_open ? "Sign-up open" : "Sign-up closed");
}

function placeLine(event) {
  return event.location
    ? el("p", { class: "small muted" }, `Where: ${event.location}`) : null;
}

/** Where and when a delegate runs: their heat, lane and time. */
function heatSummary(entry) {
  if (!entry.heat_number) {
    return el("p", {}, "You are signed up. Your heat and lane are set by the "
      + "Athletics Director once sign-up closes; they will appear here.");
  }
  return el("dl", { class: "detail" },
    el("dt", {}, "Heat"), el("dd", {}, `Heat ${entry.heat_number}`
      + (entry.heat_label ? ` (${entry.heat_label})` : "")),
    el("dt", {}, "Lane"), el("dd", {}, entry.lane ? String(entry.lane) : "—"),
    el("dt", {}, "When"), el("dd", {}, entry.date ? whenText(entry) : "Time not set yet"));
}

function heatTimes(event) {
  if (!event.heats || !event.heats.length) return null;
  return el("p", { class: "small muted" },
    "Heats: " + event.heats.map((heat) =>
      `${dayText(heat.date)}, ${rangeText(heat.start, heat.end)}`).join(" · "));
}

function gamesTable(games) {
  if (!games.length) {
    return el("p", {}, "The bracket has not been drawn yet. Your team's games "
      + "will appear here when it is.");
  }
  return table([
    { key: "round", label: "Round", render: (g) => g.round_name },
    { key: "opponent", label: "Against",
      render: (g) => g.opponent || "Winner of an earlier game" },
    { key: "when", label: "When",
      render: (g) => (g.date ? whenText(g) : "Time not set yet") },
    { key: "field", label: "Where", render: (g) => g.field || "" },
    { key: "result", label: "Result",
      render: (g) => (g.result
        ? `${g.result === "won" ? "Won" : "Lost"}`
          + (g.score_for !== null && g.score_against !== null
             ? ` ${g.score_for}–${g.score_against}` : "")
        : "") },
  ], games, { caption: "Your team's games" });
}

/* ------------------------------------------------------------------------ */

export async function olympikaPage(host) {
  let data = null;
  let errors = {};             // event id -> messages from its last action
  let renaming = null;         // event id whose rename form is open

  add(host, loadingRows(4, "Loading Olympika"));
  data = await api.get("/me/olympika", { statusHost: host });
  render();

  function render() {
    clear(host);
    add(host,
      el("h1", {}, "Olympika"),
      el("p", { class: "lede" },
        "The athletic events. Sign up for the ones you want to take part in; "
        + "once the heats are set, your time and place appear here. The full "
        + "program is on the Schedule page."),
      el("p", { class: "form-note" },
        "Signing up is not binding. If you change your mind, withdraw here "
        + "so someone else can have your place."));

    if (!data.can_enter) {
      add(host, el("div", { class: "banner banner--warning", role: "status" },
        el("p", {}, data.reason)));
    }
    if (!data.events.length) {
      add(host, emptyState("No events yet",
        "The Athletics Director has not set up Olympika. Check back at convention."));
      return;
    }
    for (const event of data.events) add(host, section(event));
  }

  function section(event) {
    const node = el("section", { class: "form-section", id: `olympika-${event.id}` },
      el("h2", {}, event.name, " ", statusPill(event)),
      event.description ? el("p", { class: "photo-description" }, event.description) : null,
      placeLine(event),
      event.max_per_school
        ? el("p", { class: "small muted" },
            `Each chapter can enter ${event.max_per_school} `
            + (event.kind === "team" ? "team" : "delegate")
            + (event.max_per_school === 1 ? "." : "s."))
        : null,
      errorSummary(errors[event.id]));

    if (event.kind === "team") {
      add(node, teamBody(event));
    } else {
      add(node, individualBody(event));
    }
    return node;
  }

  function individualBody(event) {
    if (event.entry) {
      return el("div", {},
        heatSummary(event.entry),
        el("div", { class: "btn-row" },
          button("Withdraw", {
            variant: "btn--quiet btn--danger",
            onclick: () => withdraw(event, "Withdraw from " + event.name + "?",
                                    "Your place is given up. You can sign up again "
                                    + "while sign-up is open."),
          })));
    }
    return el("div", {},
      heatTimes(event),
      data.can_enter && event.signup_open
        ? el("div", { class: "btn-row" },
            button("Sign up", {
              variant: "btn--primary",
              onclick: () => act(event, () => api.post(`/me/olympika/${event.id}`, {})),
            }))
        : null);
  }

  function teamBody(event) {
    if (event.entry) {
      return el("div", {},
        el("p", {}, "You are the captain of ", el("strong", {}, event.entry.team),
          event.entry.seed ? ` (seed ${event.entry.seed})` : "", "."),
        gamesTable(event.entry.games),
        renaming === event.id ? renameForm(event) : el("div", { class: "btn-row" },
          button("Rename the team", {
            onclick: () => { renaming = event.id; errors[event.id] = null; render(); },
          }),
          button("Withdraw the team", {
            variant: "btn--quiet btn--danger",
            onclick: () => withdraw(event, "Withdraw your team?",
                                    "The team leaves " + event.name + ". Once the bracket "
                                    + "is drawn, only the Athletics Director can do this."),
          })));
    }
    if (!data.can_enter || !event.signup_open) return null;

    const name = input({ maxlength: data.max_team_name,
                         placeholder: "Leave empty to use your chapter's name" });
    return el("div", { class: "panel" },
      el("p", {}, "One person signs up for the whole team, and that is you: "
        + "you become its captain. Your teammates do not need to sign up."),
      field({ id: `team-name-${event.id}`, label: "Team name", control: name, wide: true }),
      el("div", { class: "btn-row" },
        button("Sign up a team", {
          variant: "btn--primary",
          onclick: () => act(event, () => api.post(`/me/olympika/${event.id}`,
                                                   { team_name: name.value })),
        })));
  }

  function renameForm(event) {
    const name = input({ value: event.entry.team, maxlength: data.max_team_name });
    return el("div", { class: "panel" },
      field({ id: `team-rename-${event.id}`, label: "Team name", control: name, wide: true }),
      el("div", { class: "btn-row" },
        button("Save name", {
          variant: "btn--primary",
          onclick: async () => {
            await act(event, () => api.patch(`/me/olympika/${event.id}`,
                                             { team_name: name.value }));
            if (!errors[event.id]) renaming = null;
            render();
          },
        }),
        button("Cancel", {
          variant: "btn--quiet",
          onclick: () => { renaming = null; render(); },
        })));
  }

  /* One action against the server, then the page as it now stands. A refusal
   * is shown under its own event, in the server's words. */
  async function act(event, run) {
    try {
      await run();
      errors[event.id] = null;
    } catch (error) {
      errors[event.id] = error.errors && error.errors.length ? error.errors : [error.message];
    }
    try {
      data = await api.get("/me/olympika");
    } catch (ignored) { /* the page stays as it was */ }
    render();
  }

  async function withdraw(event, title, body) {
    const sure = await check({ title, body, confirmLabel: "Withdraw", danger: true });
    if (!sure) return;
    await act(event, () => api.del(`/me/olympika/${event.id}`));
  }
}
