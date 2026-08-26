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
import { add, el, clear, button, loadingRows, localDate } from "../ui.js";

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
      el("span", { class: "checkin__state" + (here ? " is-here" : "") },
        here ? "✓" : ""),
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
                          onclick: () => dialog.close() })));

    const dialog = el("dialog", { class: "dialog" }, form);
    dialog.addEventListener("close", () => { dialog.remove(); render(); });
    add(document.body, dialog);
    dialog.showModal();
    note.focus();
  }

  function recount() {
    const arrived = data.chapters.filter((c) => c.arrived_at);
    data.totals.arrived = arrived.length;
    data.totals.waiting = data.chapters.length - arrived.length;
    data.totals.people_arrived = arrived.reduce(
      (sum, c) => sum + c.delegates_active + c.adults_active, 0);
  }
}
