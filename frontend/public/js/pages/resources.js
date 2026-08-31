/* Resources — practice tools and places to find other people practising.
 *
 * Everything here is OUTSIDE this site. That is the whole reason the page
 * exists: the links were accumulating in the navigation, where a Certamen
 * practice app sat beside Registration and Check-in as though it were another
 * piece of convention paperwork. One tab, set apart at the end of the row, is
 * the honest shape — these are things to go and do, not things to complete.
 *
 * It is public. A delegate who has not signed in, or a parent looking over a
 * shoulder in October, should be able to reach practice material without a
 * code.
 */

import { add, el, clear } from "../ui.js";

/* Ordered by how likely somebody is to want it, not alphabetically. The
 * Certamen arena is the thing this page is mostly visited for.
 *
 * `internal` links stay inside this site; the rest leave it, and say so. */
const RESOURCES = [
  {
    name: "Certamen Arena",
    where: "state.uhsjcl.org/certamen",
    href: "/certamen/",
    internal: true,
    what: "Practice buzzing on real questions, alone or against the clock. "
        + "Built by the University High School JCL technology chairs, and "
        + "hosted here.",
  },
  {
    name: "Celerius",
    where: "timothychen.org",
    href: "https://timothychen.org/latin/celerius/",
    what: "Practising Latin inflections, Certamen-style. Drill endings at the "
        + "speed a match actually moves.",
  },
  {
    name: "CAJCL Certamen Scrimmages",
    where: "Discord",
    href: "https://discord.gg/cgkYcWYGYj",
    what: "Regular scrimmages against other California chapters. The fastest "
        + "way to find out what a real match feels like before March.",
  },
];

export async function resourcesPage(host) {
  clear(host);

  add(host,
    el("h1", {}, "Resources"),
    el("p", { class: "lede" },
      "Practice tools, and places to find other people practising. Everything "
      + "here is open to anybody — no code needed."),

    el("div", { class: "resources" },
      ...RESOURCES.map((item) => el("a", {
        class: "resource",
        href: item.href,
        // External links open in a new tab so a half-finished form on this
        // site is not thrown away by following one. `noopener` because the
        // opened page must not get a handle on this one.
        target: item.internal ? null : "_blank",
        rel: item.internal ? null : "noopener noreferrer",
      },
        el("span", { class: "resource__head" },
          el("span", { class: "resource__name" }, item.name),
          el("span", { class: "label" }, item.where)),
        el("span", { class: "resource__what" }, item.what)))),

    el("p", { class: "small muted" },
      "More to come. If you have made something other chapters would use, or "
      + "know of something that belongs here, write to ",
      el("a", { href: "mailto:state@uhsjcl.org" }, "state@uhsjcl.org"),
      "."));
}
