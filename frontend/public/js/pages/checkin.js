/* The Friday desk.
 *
 * Chapters arrive after school, fifty of them, in about ninety minutes. This
 * is used standing up, on a phone, with a queue in front of it and the venue
 * wifi doing whatever venue wifi does.
 *
 * Everything follows from that:
 *   - THE WHOLE ROW is the target, and it opens a dialog. A tick box beside a
 *     note box gave the note a slot two inches wide, at a desk where somebody
 *     is trying to write "three Certamen machines, one chariot".
 *   - Not-yet-arrived chapters first, because the desk works down what is left.
 *   - Two IDEMPOTENT buttons, not one toggle. "Registration complete" sets
 *     arrived; "Unregister" clears it. A toggle double-clicked sends two
 *     opposite requests and lands wherever the network decides — which is
 *     exactly how this produced SQLITE_BUSY and a failed save.
 *
 * Arrival is per CHAPTER, not per person. They arrive together in a bus, and
 * the per-person question that matters — did their waiver and medical come —
 * was answered weeks earlier, because the paper is mailed with the check.
 */

import * as api from "../api.js";
import { add, el, clear, button, loadingRows, localDate,
         field, input, select, errorSummary } from "../ui.js";

/* What a delegate added at the desk can be. Both are required, and both are
 * questions only the person standing there can answer. */
const GRADES = [6, 7, 8, 9, 10, 11, 12];
const LEVELS = ["MS-1", "MS-2", "MS-3", "HS-1", "HS-2", "HS-3", "HS-Adv"];

const NOTE_PLACEHOLDER =
  "Did they bring a catapult? A chariot? How many Certamen machines?";

export async function checkinPage(host) {
  let data = null;
  let filter = "";

  add(host, loadingRows(10, "Loading the desk"));
  data = await api.get("/admin/checkin", { statusHost: host });
  render();

  function render() {
    clear(host);
    const t = data.totals;

    add(host,
      el("h1", {}, "Check-in"),
      el("p", { class: "lede" },
        `${t.arrived} of ${t.chapters} arrived · `
        + `${t.people_arrived} people on site`),

      search(),
      el("div", { class: "checkin" }, ...rows().map(row)),
    );
  }

  function search() {
    const box = el("input", {
      type: "search", value: filter,
      placeholder: "Find a chapter",
      // Filtering is local — everything is already here, and a keystroke at a
      // desk must not wait on a network.
      oninput: (event) => {
        filter = event.target.value;
        render();
        const again = host.querySelector('input[type="search"]');
        if (again) {
          again.focus();
          again.setSelectionRange(again.value.length, again.value.length);
        }
      },
    });
    return el("div", { class: "field", style: "max-width:22rem" }, box);
  }

  function rows() {
    const needle = filter.trim().toLowerCase();
    return data.chapters.filter(
      (row) => !needle || row.school_name.toLowerCase().includes(needle));
  }

  /* The whole row is the target, and it opens a dialog.
   *
   * A tick box beside a note box meant the note was a slot two inches wide at
   * a desk where somebody is trying to write "three Certamen machines, one
   * chariot". The dialog has room, and the row underneath stays a single
   * glance: who, how many, and whether they are here.
   */
  function row(chapter) {
    const here = !!chapter.arrived_at;

    return el("button", {
      type: "button",
      class: "checkin__row" + (here ? " is-here" : ""),
      onclick: () => open_(chapter),
    },
      // NO TICK BOX. There used to be a bordered square here showing arrival,
      // which read as a checkbox, was not one -- the whole row is the button --
      // and so collected clicks that did nothing. The row already says
      // "Registered 3:42 PM" in words, and turns green when it is.
      el("span", { class: "checkin__who" },
        el("span", { class: "checkin__name" }, chapter.school_name),
        el("span", { class: "small muted" },
          `${chapter.delegates_active} delegates · `
          + `${chapter.adults_active} adults`,
          chapter.kind !== "chapter"
            ? el("span", { class: "pill", style: "margin-left:.5rem" },
                "Not a chapter")
            : null),
        el("span", { class: "checkin__when small muted" },
          here ? `Registered ${time(chapter.arrived_at)}` : "Not yet registered"),
        chapter.checkin_note
          ? el("span", { class: "checkin__note-preview small" },
              chapter.checkin_note)
          : null));
  }

  function time(iso) {
    // Time only. Everybody at this desk knows what day it is.
    const when = localDate(iso, { withTime: true });
    const at = when.lastIndexOf(" at ");
    return at === -1 ? when : when.slice(at + 4);
  }

  /* ONE DIALOG PER CHAPTER, AND IT NEVER CLOSES WITHOUT SAVING.
   *
   * Both actions are IDEMPOTENT -- "Registration complete" sets arrived,
   * "Unregister" clears it -- rather than one control that toggles. A toggle
   * double-clicked at a desk sends two opposite requests and lands wherever
   * the network decides; two buttons that each assert a state cannot.
   *
   * THERE IS NO CLOSE BUTTON UNTIL SOMETHING HAS BEEN SAVED. Somebody who
   * typed a note about a missing waiver, closed the panel and walked away had
   * every reason to believe they had registered that chapter. The panel now
   * holds until an action lands, then collapses to what it recorded, and only
   * then offers a way out.
   *
   * Adding a delegate happens INSIDE this dialog rather than in a second one
   * stacked on top of it. Two dialogs meant two backdrops and two boxes of
   * different heights, with the one underneath sticking out around the edges.
   */
  function open_(chapter) {
    const dialog = el("dialog", { class: "dialog" });
    const body = el("div");
    add(dialog, body);

    // Everyone added at this desk on this visit, with the code each was given.
    // A running list, because a code is readable exactly once and a desk adds
    // two or three in a row.
    const added = [];
    let settled = !!chapter.arrived_at;

    // Escape and the backdrop dismiss a <dialog> for free. That is right once
    // something is saved and wrong before it, which is the whole point.
    dialog.addEventListener("cancel", (event) => {
      if (!settled) event.preventDefault();
    });
    dialog.addEventListener("close", () => { dialog.remove(); render(); });

    function show(node) { clear(body); add(body, node); }

    /* -- the desk itself ------------------------------------------------- */

    function deskView() {
      const note = el("textarea", {
        id: "checkin-note", rows: "5", class: "checkin__note",
        placeholder: NOTE_PLACEHOLDER,
      }, chapter.checkin_note || "");

      const status = el("p", { class: "form-note", "aria-live": "polite" },
        chapter.arrived_at
          ? `Registered ${time(chapter.arrived_at)}`
          : "Nothing saved for this chapter yet.");

      let busy = false;
      const act = async (arrived, pair) => {
        if (busy) return;
        busy = true;
        pair.forEach((one) => { one.disabled = true; });
        try {
          const result = await api.post(`/admin/checkin/${chapter.school_id}`,
                                        { arrived, note: note.value });
          chapter.arrived_at = result.arrived_at;
          chapter.checkin_note = result.note;
          settled = true;
          recount();
          show(settledView());
        } catch (error) {
          clear(status);
          status.className = "form-note form-note--unsaved";
          add(status, `Not saved: ${error.message}`);
          busy = false;
          pair.forEach((one) => { one.disabled = false; });
        }
      };

      const done = button("Registration complete", { variant: "btn--primary" });
      const undo = button("Unregister", { variant: "btn--quiet btn--danger" });
      const pair = [done, undo];
      done.onclick = () => act(true, pair);
      undo.onclick = () => act(false, pair);

      return el("div", {},
        el("h2", {}, chapter.school_name),
        el("p", { class: "muted" },
          `${chapter.delegates_active} delegates · ${chapter.adults_active} adults`),
        status,
        el("label", { class: "label", for: "checkin-note" }, "Notes"),
        note,
        // No Close. Nothing has been recorded, and the note in that box is not
        // saved until one of these is pressed.
        el("div", { class: "btn-row" }, done, undo),
        added.length ? codeList() : null,
        el("div", { class: "checkin__extras" },
          button("Add a delegate", {
            variant: "btn--small btn--quiet",
            onclick: () => show(addView()),
          })));
    }

    /* -- once something has been saved ----------------------------------- */

    function settledView() {
      return el("div", {},
        el("h2", {}, chapter.school_name),
        el("p", { class: "form-note" }, chapter.arrived_at
          ? `Registered ${time(chapter.arrived_at)}`
          : "Unregistered. This chapter is not marked as arrived."),
        chapter.checkin_note
          ? el("div", {},
              el("p", { class: "label" }, "Notes"),
              el("p", { class: "small" }, chapter.checkin_note))
          : null,
        added.length ? codeList() : null,
        el("div", { class: "btn-row" },
          button("Close", { variant: "btn--primary",
                            onclick: () => dialog.close() }),
          button("Change something", {
            variant: "btn--quiet",
            onclick: () => show(deskView()),
          })),
        el("div", { class: "checkin__extras" },
          button("Add a delegate", {
            variant: "btn--small btn--quiet",
            onclick: () => show(addView()),
          }),
          // Closes FIRST, then navigates. Left open, the dialog kept its modal
          // backdrop over the roster underneath, which rendered perfectly and
          // could not be touched.
          button("Open the roster", {
            variant: "btn--small btn--quiet",
            onclick: () => {
              dialog.close();
              location.hash = `#/roster/${chapter.school_id}`;
            },
          })));
    }

    /* -- the codes handed out here, this visit --------------------------- */

    function codeList() {
      return el("div", { class: "checkin__added" },
        el("p", { class: "label label--ink" }, added.length === 1
          ? "Added just now" : `Added just now (${added.length})`),
        el("p", { class: "small muted" },
          "Write these down or photograph them before you close this. They "
          + "cannot be shown again."),
        el("table", { class: "table" },
          el("thead", {}, el("tr", {},
            el("th", { scope: "col" }, "Name"),
            el("th", { scope: "col" }, "Code"))),
          el("tbody", {}, ...added.map((person) => el("tr", {},
            el("td", {}, person.name),
            el("td", { class: "mono" }, person.code))))));
    }

    /* -- adding a delegate, without leaving this dialog ------------------- */

    function addView() {
      const first = input({ id: "late-first", autocomplete: "off" });
      const last = input({ id: "late-last", autocomplete: "off" });
      const grade = select(
        [["", "—"], ...GRADES.map((one) => [String(one), String(one)])],
        { id: "late-grade" });
      const level = select([["", "—"], ...LEVELS.map((one) => [one, one])],
                           { id: "late-level" });
      const problems = el("div");

      return el("div", {},
        el("h2", {}, "Add a delegate"),
        el("p", { class: "muted" },
          `To ${chapter.school_name}, for somebody arriving in place of a `
          + "delegate who could not come."),
        el("p", { class: "small muted" },
          "Their activity sheet is waived — the tests are already printed "
          + "— but their waiver and medical form are still required, on "
          + "paper, today."),
        problems,
        el("div", { class: "grid" },
          el("div", { class: "span-6" },
            field({ id: "late-first", label: "First name", required: true,
                    control: first })),
          el("div", { class: "span-6" },
            field({ id: "late-last", label: "Last name", required: true,
                    control: last })),
          el("div", { class: "span-6" },
            field({ id: "late-grade", label: "Grade", required: true,
                    control: grade })),
          el("div", { class: "span-6" },
            field({ id: "late-level", label: "Latin level", required: true,
                    control: level }))),
        el("div", { class: "btn-row" },
          button("Add them", {
            variant: "btn--primary",
            onclick: async () => {
              // ALL FOUR ARE REQUIRED. A delegate entered with no grade and no
              // Latin level is a row somebody has to chase later, and the one
              // person who can answer both is standing at the desk right now.
              const missing = [];
              if (!first.value.trim()) missing.push("a first name");
              if (!last.value.trim()) missing.push("a last name");
              if (!grade.value) missing.push("a grade");
              if (!level.value) missing.push("a Latin level");
              clear(problems);
              if (missing.length) {
                add(problems,
                    errorSummary([`Still needed: ${missing.join(", ")}.`]));
                return;
              }

              let created;
              try {
                created = await api.post("/sponsor/people", {
                  school_id: chapter.school_id,
                  first_name: first.value.trim(),
                  last_name: last.value.trim(),
                  person_type: "delegate",
                  grade: Number(grade.value),
                  latin_level: level.value,
                });
                await api.post(
                  `/admin/people/${created.id}/waive-activity-sheet`,
                  { waived: true });
              } catch (error) {
                add(problems, errorSummary([error.message]));
                return;
              }

              added.push({
                name: `${created.first_name} ${created.last_name}`.trim(),
                code: created.code,
              });
              settled = true;
              data = await api.get("/admin/checkin");
              const fresh = data.chapters.find(
                (row) => row.school_id === chapter.school_id);
              if (fresh) Object.assign(chapter, fresh);
              show(chapter.arrived_at ? settledView() : deskView());
            },
          }),
          button("Back", {
            variant: "btn--quiet",
            onclick: () => show(chapter.arrived_at ? settledView() : deskView()),
          })));
    }

    show(chapter.arrived_at ? settledView() : deskView());
    add(document.body, dialog);
    dialog.showModal();
  }

  function recount() {
    const arrived = data.chapters.filter((c) => c.arrived_at);
    data.totals.arrived = arrived.length;
    data.totals.waiting = data.chapters.length - arrived.length;
    data.totals.people_arrived = arrived.reduce(
      (sum, c) => sum + c.delegates_active + c.adults_active, 0);
  }
}
