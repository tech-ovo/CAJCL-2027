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
         check, tell, field, input } from "../ui.js";

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

  /* One dialog per chapter. Both buttons are IDEMPOTENT -- "Registration
   * complete" sets arrived, "Unregister" clears it -- rather than one control
   * that toggles. A toggle double-clicked at a desk sends two opposite
   * requests and lands wherever the network decides; two buttons that each
   * assert a state cannot. */
  function open_(chapter) {
    // Built by hand rather than with `check()` from ui.js, and deliberately.
    // Those helpers ask one question, resolve, and close. This dialog STAYS
    // OPEN and reports back into itself: mark arrived, see the time appear,
    // change the note, mark arrived again, all without the row underneath
    // moving. At a desk with a queue, closing after every action is the wrong
    // shape.
    const note = el("textarea", {
      id: "checkin-note", rows: "5", class: "checkin__note",
      placeholder: NOTE_PLACEHOLDER,
    }, chapter.checkin_note || "");

    const status = el("p", { class: "form-note", "aria-live": "polite" },
      chapter.arrived_at
        ? `Registered ${time(chapter.arrived_at)}`
        : "Not yet registered");

    let busy = false;
    const send = async (body, buttons) => {
      if (busy) return;                 // a second click while the first is out
      busy = true;
      buttons.forEach((b) => { b.disabled = true; });
      try {
        const result = await api.post(`/admin/checkin/${chapter.school_id}`, body);
        chapter.arrived_at = result.arrived_at;
        chapter.checkin_note = result.note;
        clear(status);
        add(status, chapter.arrived_at
          ? `Registered ${time(chapter.arrived_at)}` : "Not yet registered");
        recount();
      } catch (error) {
        clear(status);
        status.className = "form-note form-note--unsaved";
        add(status, `Not saved: ${error.message}`);
      } finally {
        busy = false;
        buttons.forEach((b) => { b.disabled = false; });
      }
    };

    const done = button("Registration complete", { variant: "btn--primary" });
    const undo = button("Unregister", { variant: "btn--quiet btn--danger" });
    const buttons = [done, undo];
    done.onclick = () => send({ arrived: true, note: note.value }, buttons);
    undo.onclick = () => send({ arrived: false, note: note.value }, buttons);

    const form = el("form", { method: "dialog" },
      el("h2", {}, chapter.school_name),
      el("p", { class: "muted" },
        `${chapter.delegates_active} delegates · ${chapter.adults_active} adults`),
      status,
      el("label", { class: "label", for: "checkin-note" }, "Notes"),
      note,
      el("div", { class: "btn-row" },
        done, undo,
        button("Close", { variant: "btn--quiet",
                          onclick: () => dialog.close() })),

      /* The two things a desk does besides ticking a chapter off.
       *
       * A chapter turns up with a replacement for somebody who could not come.
       * The replacement needs a code in their hand within the minute, and the
       * person they replaced should stop being counted for meals. Both used to
       * mean finding somebody with a terminal.
       *
       * Kept below the close button, in quieter type, because they are the
       * exception: forty-nine chapters in fifty just arrive. */
      el("div", { class: "checkin__extras" },
        button("Add a delegate", {
          variant: "btn--small btn--quiet",
          onclick: () => addLate(chapter, dialog),
        }),
        el("a", { class: "btn btn--small btn--quiet",
                  href: `#/roster/${chapter.school_id}` },
          "Open the roster")));

    const dialog = el("dialog", { class: "dialog" }, form);
    dialog.addEventListener("close", () => { dialog.remove(); render(); });
    add(document.body, dialog);
    dialog.showModal();
    note.focus();
  }

  /* A delegate added at the desk on the Friday.
   *
   * Two calls, and the second is the point: their ACTIVITY SHEET IS WAIVED.
   * The tests were printed and the food ordered weeks ago, so there is nothing
   * left for their answers to change -- and without the waiver they would sit
   * in their chapter's completion figure as permanently unfinished, sending
   * somebody to chase a delegate who cannot act.
   *
   * Their waiver and medical are NOT waived. Those are safety documents and
   * nobody is exempt; the desk checks the paper as it always has.
   */
  async function addLate(chapter, dialog) {
    const first = input({ id: "late-first", autocomplete: "off" });
    const last = input({ id: "late-last", autocomplete: "off" });

    const ok = await check({
      title: `Add a delegate to ${chapter.school_name}`,
      body: [
        el("p", {}, "For somebody arriving in place of a delegate who could "
                  + "not come. Their activity sheet is waived — the tests are "
                  + "already printed — but their waiver and medical form are "
                  + "still required, on paper, today."),
        field({ id: "late-first", label: "First name", control: first, wide: true }),
        field({ id: "late-last", label: "Last name", control: last, wide: true }),
      ],
      confirmLabel: "Add them",
    });
    if (!ok) return;

    if (!first.value.trim() && !last.value.trim()) {
      await tell({ title: "That needs a name",
                   body: "Give at least a first or last name, then try again." });
      return;
    }

    let created;
    try {
      created = await api.post("/sponsor/people", {
        school_id: chapter.school_id,
        first_name: first.value.trim(),
        last_name: last.value.trim(),
        person_type: "delegate",
      });
      await api.post(`/admin/people/${created.id}/waive-activity-sheet`,
                     { waived: true });
    } catch (error) {
      await tell({ body: error.message });
      return;
    }

    chapter.delegates_active += 1;
    dialog.close();
    await tell({
      title: `${created.first_name} ${created.last_name}`.trim(),
      body: [
        el("p", { class: "label" }, "Access code"),
        el("p", { class: "tabula__code mono", style: "font-size:1.5rem" },
          created.code),
        el("p", {}, "Write this down or photograph it now. It is not shown "
                  + "again and nothing can recover it."),
      ],
    });
    data = await api.get("/admin/checkin");
    render();
  }

  function recount() {
    const arrived = data.chapters.filter((c) => c.arrived_at);
    data.totals.arrived = arrived.length;
    data.totals.waiting = data.chapters.length - arrived.length;
    data.totals.people_arrived = arrived.reduce(
      (sum, c) => sum + c.delegates_active + c.adults_active, 0);
  }
}
