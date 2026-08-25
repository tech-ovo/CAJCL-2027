/* The public welcome page.
 *
 * WHERE THE MARKUP LIVES
 *   In index.html, not here. A visitor arriving while Modal is cold gets a
 *   finished page from the very first byte, with no request made and nothing
 *   to wait for, and scripts/build_snapshot.py has exactly one file to write
 *   the numbers into.
 *
 *   The router clears #app before every render, so main.js lifts that markup
 *   into a fragment at boot and hands back a clone here. Nothing is duplicated
 *   in JavaScript, and nothing goes blank if this module ever fails to load --
 *   the page a visitor already has is the right one.
 */

import * as api from "../api.js";
import { add, el, clear } from "../ui.js";
import { state, snapshotMarkup, applySnapshot } from "../main.js";

export async function welcomePage(host) {
  const markup = snapshotMarkup();
  if (markup) add(host, markup);

  // The convention facts may have arrived while this page was not on screen.
  if (state.convention && Object.keys(state.convention).length) {
    applySnapshot(state.convention);
  }

  const venueAddress = state.convention && state.convention["convention.venue_address"];
  if (venueAddress) {
    document.querySelectorAll('[data-snapshot="venue"]').forEach((node) => {
      clear(node);
      add(node, state.convention["convention.venue_name"], el("br"), venueAddress);
    });
  }

  const stats = document.getElementById("stats");
  if (!stats) return;

  /* A quiet note, in the stats block, only if the request is slow.
   *
   * The page is already complete and readable — the numbers on it were baked
   * in at build time — so this must never clear anything or take the top of
   * the screen. But a visitor watching a stale figure for eight seconds with
   * no explanation concludes the site is broken, which is worse than a line
   * of small text saying what is happening.
   *
   * Nothing at all is shown for a fast response, which is the normal case
   * once the server is warm.
   */
  const note = el("p", { class: "waking waking--quiet",
                         role: "status", "aria-live": "polite",
                         style: "grid-column: 1 / -1" },
    el("span", { class: "waking__dot", "aria-hidden": "true" }),
    el("span", {}, "Waking up the server, so these numbers may be a few days old…"));

  const slow = setTimeout(() => add(stats, note), 1200);
  const done = () => { clearTimeout(slow); note.remove(); };

  try {
    const live = await api.get("/public/stats");
    done();
    stats.classList.remove("stat--stale");
    setStat("schools_hs", live.schools_hs);
    setStat("schools_ms", live.schools_ms);
    setStat("delegates", live.delegates);
    setStat("adults", live.adults);
  } catch (ignored) {
    done();
    // Keep the snapshot. Say so quietly rather than showing an error on a page
    // that is otherwise perfectly readable.
    add(stats, el("p", { class: "label", style: "grid-column: 1 / -1" },
      "Showing the most recent published figures."));
  }
}

function setStat(key, value) {
  document.querySelectorAll(`[data-snapshot="${key}"]`).forEach((node) => {
    node.textContent = Number(value || 0).toLocaleString("en-US");
  });
}
