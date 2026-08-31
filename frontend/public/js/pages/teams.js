/* Chapter team entries — Kickball, Fugepilam, Ultimate Frisbee.
 *
 * A CHAPTER ENTERS THESE, NOT A DELEGATE. That distinction is the whole reason
 * this page exists separately from the activity sheet. A delegate ticking
 * "Kickball" on their own form would tell the Athletics chair that one person
 * wants to play, which is not a team and cannot be scheduled against anything.
 * What the chair needs is "Pinnacle Bay is bringing two kickball teams", and
 * only somebody who speaks for the chapter can say that.
 *
 * So: the sponsor, or a delegate the sponsor has made chapter leader. Both
 * carry the `chapter` scope, and a registration chair can do it for them.
 *
 * The activity sheet already SHOWED these entries and could not create them —
 * `POST /sponsor/chapter-entries` existed, was tested, and had no caller.
 */

import * as api from "../api.js";
import { add, el, clear, button, table, field, input, select, loadingRows,
         emptyState, check, tell } from "../ui.js";
import { hasScope } from "../main.js";

export async function teamsPage(host, params = []) {
  // A chair opening one chapter's teams. A sponsor leaves it null and the
  // server uses their own school, exactly as the roster does.
  const schoolId = params[0] ? Number(params[0]) : null;
  const query = schoolId ? `?school_id=${schoolId}` : "";

  let data = null;

  add(host, loadingRows(5, "Loading team entries"));
  data = await api.get(`/sponsor/chapter-entries${query}`, { statusHost: host });
  render();

  async function reload() {
    data = await api.get(`/sponsor/chapter-entries${query}`);
    render();
  }

  function render() {
    clear(host);
    const entries = data.entries || [];
    const available = data.available || [];

    add(host,
      el("h1", {}, "Chapter teams"),
      el("p", { class: "lede" },
        "Kickball, Fugepilam and Ultimate Frisbee are entered by the chapter, "
        + "not by individual delegates. Say how many teams you are bringing "
        + "and the Athletics chair can build a bracket."),

      el("p", { class: "small muted" },
        "Everything else — Chess, Track, tests, arts — each delegate enters on "
        + "their own form."),

      el("div", { class: "btn-row" },
        available.length
          ? button("Enter a team", {
              variant: "btn--primary",
              onclick: () => addEntry(available),
            })
          : null,
        schoolId
          ? el("a", { class: "btn", href: `#/roster/${schoolId}` }, "Back to roster")
          : el("a", { class: "btn", href: "#/roster" }, "Back to roster")),

      entries.length
        ? table([
            { key: "item_name", label: "Event" },
            // A chapter bringing two kickball teams needs to tell them apart
            // on a bracket, and "A" and "B" is what everybody already writes
            // on the sheet.
            { key: "team_label", label: "Team",
              render: (row) => el("span", { class: "mono" }, row.team_label) },
            { key: "notes", label: "Notes",
              render: (row) => row.notes || "—" },
            { key: "actions", label: "",
              render: (row) => button("Remove", {
                variant: "btn--small btn--quiet btn--danger",
                onclick: () => removeEntry(row),
              }) },
          ], entries, { caption: "Team entries for this chapter" })
        : emptyState("No teams entered",
            available.length
              ? "If your chapter is bringing a kickball, Fugepilam or Ultimate "
                + "Frisbee team, enter it here so it can be scheduled."
              : "There are no chapter team events open at the moment."));
  }

  async function addEntry(available) {
    const event = select(
      available.map((item) => [String(item.id), item.name]), { id: "team-item" });
    // "A" for the first, "B" for the second. Eight characters is enough for
    // anything anybody actually writes and short enough to fit a bracket.
    const label = input({ id: "team-label", value: "A", maxlength: "8" });
    const notes = input({ id: "team-notes" });

    const ok = await check({
      title: "Enter a chapter team",
      body: [
        el("p", {}, "One entry per team. A chapter bringing two kickball "
                  + "teams enters Kickball twice, as A and B."),
        field({ id: "team-item", label: "Event", control: event, wide: true }),
        field({ id: "team-label", label: "Team", control: label, wide: true,
                help: "A, B, and so on. Shown on the bracket." }),
        field({ id: "team-notes", label: "Notes", control: notes, wide: true,
                help: "Anything the chair should know. Optional." }),
      ],
      confirmLabel: "Enter the team",
    });
    if (!ok) return;

    try {
      await api.post("/sponsor/chapter-entries", {
        school_id: schoolId || undefined,
        item_id: Number(event.value),
        team_label: label.value.trim() || "A",
        notes: notes.value.trim() || null,
      });
      await reload();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  async function removeEntry(row) {
    const ok = await check({
      title: `Remove ${row.item_name} team ${row.team_label}?`,
      body: "The chapter will not be scheduled for it. You can enter it again "
          + "at any time before the deadline.",
      confirmLabel: "Remove it", danger: true,
    });
    if (!ok) return;
    try {
      await api.del(`/sponsor/chapter-entries/${row.id}`);
      await reload();
    } catch (error) {
      await tell({ body: error.message });
    }
  }
}
