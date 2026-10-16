/* The privacy notice for students, parents and sponsors.
 *
 * PUBLIC, and linked from the footer of every page and from the join page,
 * because a parent reads it before anyone signs anything.
 *
 * THE WORDING IS docs/PRIVACY.md §9. When what the site collects, who sees it,
 * where it goes or how long it is kept changes, change both together -- this
 * page is the version families read, that one is the version we are held to.
 * The dates are the ones in §6.
 */

import { add, el, clear } from "../ui.js";

const CONTACT = "state@uhsjcl.org";

function list(...items) {
  return el("ul", {}, ...items.map((item) => el("li", {}, item)));
}

export async function privacyPage(host) {
  clear(host);
  add(host, el("article", { class: "doc" },
    el("h1", {}, "Privacy notice"),
    el("p", { class: "lede" },
      "The California Junior Classical League (CAJCL), a 501(c)(3) non-profit, "
      + "collects a small amount of student information to run the State "
      + "Convention, and deletes it afterward. This page says what, who sees "
      + "it, and when it is deleted."),
    el("p", { class: "label" }, "Effective October 1, 2026"),

    el("h2", {}, "What we collect"),
    list(
      "Student: legal name, grade (6–12), chapter, Latin level, the "
      + "activities, tests and contests chosen, meal preference, and a parent "
      + "or guardian's name and phone number. Your school's Latin teacher (the "
      + "sponsor) enters these, or the student enters their own name, grade "
      + "and Latin level with the join code on the sponsor's handout. If the "
      + "sponsor does not approve that registration, everything entered is "
      + "deleted.",
      "Adults: name, email address, mobile phone and chaperone availability.",
      "Optional: photos a student uploads to the convention photo contest, "
      + "with a caption, and sign-ups for Olympika events and activities. "
      + "Location and camera data are removed from each photo before it is "
      + "stored.",
      "To keep the site secure: a scrambled copy of each login token, and a "
      + "scrambled copy of the visitor's network address. We keep no "
      + "readable record of either."),

    el("h2", {}, "What we never collect"),
    list(
      "Student email addresses, home street addresses, dates of birth, or "
      + "Social Security numbers.",
      "Credit or debit card numbers. Fees are paid by check.",
      "Health records. Medical forms and signed waivers stay on paper; "
      + "scans are kept in a private folder that only the Convention "
      + "Presidents can open."),

    el("h2", {}, "Who can see it"),
    list(
      "A chapter's sponsor sees that chapter and no other.",
      "The Convention Presidents and registration chairs see every chapter, "
      + "in order to run registration.",
      "Other chairs see only what their job needs: the Athletics Director "
      + "sees Olympika entrants, and the Activities chair sees photos and "
      + "the names of approved activity helpers. Contest judges see entries "
      + "as “Entry N”, with no name or chapter.",
      "The public sees only totals and the convention schedule, never "
      + "names."),

    el("h2", {}, "How we protect it"),
    list(
      "Every connection is encrypted, and the database is encrypted where "
      + "it is stored.",
      "Login tokens are stored only in scrambled form, and repeated wrong "
      + "guesses lock the sign-in.",
      "Every change to a record is written to an audit log.",
      "We use these services to run the site: GitHub (the website), Modal "
      + "(the server), a hosted database service, and Google Drive "
      + "(uploaded files and scans). Write to us for the full list."),

    el("h2", {}, "We never sell or profile"),
    el("p", {},
      "We never sell student data, show advertisements, or build marketing "
      + "profiles. The site has no advertising or tracking code."),

    el("h2", {}, "When it is deleted"),
    el("p", {},
      "All names, contact details, uploaded files and photos are deleted on "
      + "April 12, 2027, 30 days after the convention. We keep only the year, "
      + "badge number, chapter, grade, Latin level and competition "
      + "placements, with no names or contact details. A sponsor can delete "
      + "a student's information sooner. Financial records are kept for the "
      + "seven years required for non-profit tax purposes."),

    el("h2", {}, "Parents and guardians"),
    el("p", {},
      "You may ask to see, correct or delete your child's information at any "
      + "time, through your child's sponsor or by writing to ",
      el("a", { href: `mailto:${CONTACT}` }, CONTACT),
      ". If we ever find that personal information has been exposed, we will "
      + "tell the affected sponsors and families in writing within 30 days."),

    el("p", {},
      el("a", { href: "#/join" }, "Join your chapter"), " · ",
      el("a", { href: "#/" }, "Back to the welcome page"))));
}
