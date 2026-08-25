/* The Friday desk.
 *
 * Chapters arrive after school, fifty of them, in about ninety minutes. This
 * is used standing up, on a phone, with a queue in front of it and the venue
 * wifi doing whatever venue wifi does.
 *
 * Everything follows from that:
 *   - ONE TAP to mark a chapter arrived, and the tap is the whole row.
 *   - Not-yet-arrived chapters first, because the desk works down what is left.
 *   - The row updates the moment it is tapped; the request goes behind it.
 *     Waiting for a round trip with somebody standing there is the failure.
 *   - Un-marking is one tap too. The commonest mistake at a desk is ticking
 *     the row above the one you meant.
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

  function row(chapter) {
    const here = !!chapter.arrived_at;

    const tick = el("button", {
      type: "button",
      class: "checkin__tick" + (here ? " is-here" : ""),
      "aria-pressed": here ? "true" : "false",
      "aria-label": here
        ? `${chapter.school_name} has arrived. Tap to undo.`
        : `Mark ${chapter.school_name} arrived`,
      onclick: () => mark(chapter, !here),
    }, here ? "✓" : "");

    const note = el("textarea", {
      class: "checkin__note",
      rows: "2",
      placeholder: NOTE_PLACEHOLDER,
      "aria-label": `Notes for ${chapter.school_name}`,
      onchange: (event) => saveNote(chapter, event.target.value),
    }, chapter.checkin_note || "");

    return el("div", { class: "checkin__row" + (here ? " is-here" : "") },
      tick,
      el("div", { class: "checkin__who" },
        el("p", { class: "checkin__name" }, chapter.school_name),
        el("p", { class: "small muted" },
          `${chapter.delegates_active} delegates · `
          + `${chapter.adults_active} adults`,
          chapter.kind !== "chapter"
            ? el("span", { class: "pill", style: "margin-left:.5rem" },
                "Not a chapter")
            : null),
        el("p", { class: "checkin__when small muted" },
          here ? `Arrived ${time(chapter.arrived_at)}` : "")),
      note);
  }

  function time(iso) {
    // Time only. Everybody at this desk knows what day it is.
    const when = localDate(iso, { withTime: true });
    const at = when.lastIndexOf(" at ");
    return at === -1 ? when : when.slice(at + 4);
  }

  /* Painted first, sent second. A desk cannot wait for a round trip, and the
   * failure mode is honest: if the request is refused the tick goes back and
   * the reason is said out loud. */
  async function mark(chapter, arrived) {
    chapter.arrived_at = arrived ? new Date().toISOString() : null;
    recount();
    render();

    try {
      const result = await api.post(`/admin/checkin/${chapter.school_id}`,
                                    { arrived });
      chapter.arrived_at = result.arrived_at;
      recount();
    } catch (error) {
      chapter.arrived_at = arrived ? null : new Date().toISOString();
      recount();
      render();
      alert(`That did not save: ${error.message}`);
    }
  }

  async function saveNote(chapter, text) {
    const before = chapter.checkin_note;
    chapter.checkin_note = text.trim() || null;
    try {
      await api.post(`/admin/checkin/${chapter.school_id}`, { note: text });
    } catch (error) {
      chapter.checkin_note = before;
      render();
      alert(`That note did not save: ${error.message}`);
    }
  }

  function recount() {
    const arrived = data.chapters.filter((c) => c.arrived_at);
    data.totals.arrived = arrived.length;
    data.totals.waiting = data.chapters.length - arrived.length;
    data.totals.people_arrived = arrived.reduce(
      (sum, c) => sum + c.delegates_active + c.adults_active, 0);
  }
}
