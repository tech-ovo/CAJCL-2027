/* The public welcome page.
 *
 * The static snapshot in index.html is ALREADY on screen when this runs. This
 * only replaces the numbers once the API answers, so a visitor arriving at a
 * cold site sees a complete page rather than a loading screen -- and if the API
 * never answers, they keep the snapshot instead of a spinner.
 */

import * as api from "../api.js";
import { el, clear } from "../ui.js";
import { state } from "../main.js";

export async function welcomePage(host) {
  // Nothing is cleared here on purpose: index.html's markup IS the snapshot,
  // and the router leaves it in place for this route.
  const stats = document.getElementById("stats");
  if (!stats) return;

  const venue = state.convention && state.convention["convention.venue_address"];
  if (venue) {
    document.querySelectorAll('[data-snapshot="venue"]').forEach((node) => {
      clear(node);
      node.append(state.convention["convention.venue_name"], el("br"), venue);
    });
  }

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
    stats.append(el("p", { class: "label", style: "grid-column: 1 / -1" },
      "Showing the most recent published figures."));
  }
}

function setStat(key, value) {
  document.querySelectorAll(`[data-snapshot="${key}"]`).forEach((node) => {
    node.textContent = Number(value || 0).toLocaleString("en-US");
  });
}
