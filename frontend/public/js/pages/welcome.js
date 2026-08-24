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

  try {
    const live = await api.get("/public/stats");
    stats.classList.remove("stat--stale");
    setStat("schools_hs", live.schools_hs);
    setStat("schools_ms", live.schools_ms);
    setStat("delegates", live.delegates);
    setStat("adults", live.adults);
  } catch (ignored) {
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
