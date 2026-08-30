/* The sponsor's roster.
 *
 * One table of thirty people, from ONE query. Compact enough that thirty rows
 * fit on a laptop without scrolling, and a labelled row-group on a phone rather
 * than a table scrolled sideways.
 */

import * as api from "../api.js";
import { add, el, clear, tabula, table, button, emptyState, loadingRows,
         fullName, personNumber, ask, check, tell,
         field, input, select } from "../ui.js";
import { state, route, hasScope, adopt } from "../main.js";

export async function rosterPage(host, params = []) {
  // Set when a chair has opened one chapter from the Chapters table. A sponsor
  // reaching their own roster leaves it null and the server uses their school.
  const schoolId = params[0] ? Number(params[0]) : null;
  const asChair = schoolId !== null;
  const path = asChair ? `/sponsor/roster?school_id=${schoolId}` : "/sponsor/roster";

  let data = null;
  let sort = { key: "last_name", direction: "asc" };
  let showCancelled = false;
  // Who is ticked for a code reissue. Empty until the sponsor turns the mode
  // on, so the roster is not covered in checkboxes for a job most days do not
  // involve.
  let selecting = false;
  const picked = new Set();

  add(host, loadingRows(8, "Loading the roster"));
  data = await api.get(path, { statusHost: host });
  render();

  async function reload() {
    data = await api.get(path);
    render();
  }

  function render() {
    clear(host);
    const school = data.school;
    const stats = data.stats || {};

    const people = data.people
      .filter((p) => showCancelled || p.status === "active")
      .sort(compare);

    const cancelledCount = data.people.filter((p) => p.status !== "active").length;

    add(host, 
      tabula({
        label: "Chapter",
        name: school.name,
        // No number. `personNumber` is the number printed beside a PERSON, and
        // putting a school's row id in the same place implied chapters are
        // numbered in a way anybody uses. Nobody has ever referred to a
        // chapter by a four-digit number.
        // No level for an organization. SCL and members at large are not a
        // middle or a high school, and `schools.level` only carries 'HS' for
        // them because the column is NOT NULL. See docs/TODO.md.
        left: [school.kind === "chapter" ? school.level : null, school.city]
          .filter(Boolean).join(" · "),
      }),

      asChair
        ? el("p", {}, el("a", { href: "#/dashboard" }, "← All chapters"))
        : null,

      // A chapter with no active sponsor is a real state -- the sponsor
      // cancelled, or the chapter was created before anyone was named -- and it
      // is worth saying out loud, because nobody can sign in to work on it.
      asChair && !sponsorOf(data.people)
        ? el("div", { class: "banner banner--info", style: "margin-bottom:1.5rem" },
            el("span", { class: "banner__label" }, "No sponsor"),
            el("span", {}, "Nobody can sign in to manage this chapter's roster "
                         + "or receive its invoice."),
            // Used to say "add one from Settings", which was wrong twice:
            // Settings is admin-only, and Settings → Roles grants a role to
            // somebody who already has an account. This makes the account.
            button("Add the sponsor", {
              variant: "btn--small btn--primary",
              onclick: () => addSponsor(school),
            }))
        : null,

      el("section", { class: "grid" },
        el("div", { class: "span-8" },
          el("h1", {}, asChair ? school.name : "Roster"),
          el("p", { class: "lede" },
            asChair
              ? "Everyone this chapter is bringing. To change a form or paste a "
                + "roster, sign in as the sponsor."
              : "Add people, correct details, and tick each paper form as it "
                + "comes back to you.")),
        el("div", { class: "span-4" },
          el("dl", { class: "detail" },
            el("dt", {}, "Delegates"), el("dd", { class: "mono" }, stats.delegates_active || 0),
            el("dt", {}, "Adults"), el("dd", { class: "mono" }, stats.adults_active || 0),
            el("dt", {}, "Complete"),
            el("dd", { class: "mono" },
              `${(stats.delegates_complete || 0) + (stats.adults_complete || 0)}`)))),

      el("div", { class: "btn-row" },
        // A chair gets this too. A sponsor whose spreadsheet will not paste is
        // a support call, and until this existed the only answer was to find a
        // president to sign in as them.
        el("a", { class: "btn btn--primary",
                  href: asChair ? `#/roster/${schoolId}/import` : "#/roster/import" },
          "Paste a roster"),
        button("Add one person", { onclick: () => addPerson(school) }),
        asChair ? null : el("a", { class: "btn", href: "#/invoice" }, "View invoice"),
        asChair && hasScope("*") && sponsorOf(data.people)
          ? button("Sign in as the sponsor", {
              variant: "btn--primary",
              onclick: () => impersonateSponsor(),
            })
          : null,
        button("Preview packet", {
          // The warning used to be a paragraph under the button row, where
          // nothing connected it to this button. Asked at the moment of
          // clicking, it is unmissable and it is about the thing being done.
          onclick: async () => {
            const ok = await check({
              title: "Preview the packet",
              body: ["This is a preview, not something to hand out.",
                     "Access codes are stored scrambled and cannot be read "
                     + "back, so the sheets will show blocks where the codes "
                     + "would be.",
                     "To give somebody a working sheet, use Issue new codes "
                     + "and print from the screen that follows."],
              confirmLabel: "Show the preview",
            });
            if (!ok) return;
            openPrintView(asChair
              ? `/sponsor/packet?school_id=${schoolId}`
              : "/sponsor/packet");
          },
        }),
        button(selecting ? "Cancel reissue" : "Issue new codes", {
          variant: selecting ? "btn--quiet" : "",
          onclick: () => {
            selecting = !selecting;
            picked.clear();
            render();
          },
        }),
        cancelledCount
          ? button(showCancelled
              ? "Hide cancelled"
              : `Show ${cancelledCount} cancelled`, {
              variant: "btn--quiet",
              onclick: () => { showCancelled = !showCancelled; render(); },
            })
          : null),

      selecting ? reissueBar(people) : null,

      people.length
        ? table(columns(), people, {
            sort,
            onSort: (key) => {
              sort = {
                key,
                direction: sort.key === key && sort.direction === "asc" ? "desc" : "asc",
              };
              render();
            },
            rowClass: (row) => [
              row.status !== "active" ? "is-inactive" : null,
              row.person_type === "adult" ? "is-adult" : null,
            ].filter(Boolean).join(" ") || null,
            caption: `Roster for ${school.name}`,
          })
        : emptyState(
            "No delegates yet",
            "Paste your roster to get started. Any format works — a spreadsheet " +
            "column, a numbered list, or one name per line.",
            el("a", { class: "btn btn--primary", href: "#/roster/import" },
              "Paste your roster")),
    );
  }

  /* Correct somebody's name.
   *
   * A pasted roster reads what it is given, and it is given whatever the
   * sponsor's spreadsheet had: a nickname, a maiden name, a typo, or a name a
   * form field mangled. The name is printed on their sheet and read out at
   * awards, so it is the field most worth being able to fix -- and until this
   * existed, nothing on the site could fix it for a delegate at all.
   *
   * Names only. Grade, Latin level and meal are the delegate's own answers on
   * their own form, and a sponsor overwriting them silently is how two people
   * end up disagreeing about which test somebody is sitting.
   */
  async function editPerson(row) {
    const first = input({ id: "edit-first", value: row.first_name || "" });
    const middle = input({ id: "edit-middle", value: row.middle_name || "" });
    const last = input({ id: "edit-last", value: row.last_name || "" });
    const suffix = input({ id: "edit-suffix", value: row.suffix || "" });

    const ok = await check({
      title: `Edit ${fullName(row)}`,
      body: [
        el("p", {}, "Their access code does not change, and neither does "
                  + "anything they have filled in themselves."),
        field({ id: "edit-first", label: "First name", control: first, wide: true }),
        field({ id: "edit-middle", label: "Middle name", control: middle, wide: true }),
        field({ id: "edit-last", label: "Last name", control: last, wide: true }),
        field({ id: "edit-suffix", label: "Suffix", control: suffix, wide: true }),
      ],
      confirmLabel: "Save",
    });
    if (!ok) return;

    if (!first.value.trim() && !last.value.trim()) {
      await tell({ title: "That needs a name",
                   body: "Leave at least a first or last name, then try again." });
      return;
    }
    try {
      await api.patch(`/sponsor/people/${row.id}`, {
        first_name: first.value.trim(),
        middle_name: middle.value.trim() || null,
        last_name: last.value.trim(),
        suffix: suffix.value.trim() || null,
      });
      await reload();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  async function setUnlocked(row, unlocked) {
    if (!unlocked) {
      const ok = await check({
        title: `Close ${fullName(row)}'s form again?`,
        body: `${fullName(row)} will no longer be able to edit their own `
            + "answers, the same as everybody else after the deadline. "
            + "Everything they have already saved is kept.",
        confirmLabel: "Close it",
      });
      if (!ok) return;
    }
    try {
      await api.post(`/admin/people/${row.id}/unlock-forms`, { unlocked });
      await reload();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  async function setWaived(row, waived) {
    const ok = await check({
      title: waived
        ? `Waive ${fullName(row)}'s activity sheet?`
        : `Require ${fullName(row)}'s activity sheet again?`,
      body: waived
        ? ["They count as complete once their waiver and medical are in. Those "
           + "are safety documents and are still required.",
           "They are entered in nothing, so they will not appear on any "
           + "proctor's sheet."]
        : "They go back to needing a submitted activity sheet before they "
          + "count as complete.",
      confirmLabel: waived ? "Waive it" : "Require it",
    });
    if (!ok) return;
    try {
      await api.post(`/admin/people/${row.id}/waive-activity-sheet`, { waived });
      await reload();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  /* Add one person to a roster.
   *
   * Pasting is how a roster is BUILT; this is how it is corrected. A chapter
   * that gains one delegate in February should not have to paste a second list
   * and reason about what the de-duplicator will make of it.
   *
   * Their code is minted here and shown once, exactly like a reissue, because
   * there is no other moment at which it can be read.
   */
  async function addPerson(school) {
    const first = input({ id: "person-first", autocomplete: "off" });
    const last = input({ id: "person-last", autocomplete: "off" });
    const kind = select([["delegate", "Delegate"],
                         ["chaperone", "Chaperone"],
                         ["sponsor", "Sponsor"]], { id: "person-kind" });

    const ok = await check({
      title: `Add one person to ${school.name}`,
      body: [
        el("p", {}, "This mints their access code, which you will see once on "
                  + "the next screen. Everything else about them — grade, "
                  + "Latin level, meal — they fill in themselves."),
        field({ id: "person-first", label: "First name", control: first,
                wide: true }),
        field({ id: "person-last", label: "Last name", control: last,
                wide: true }),
        field({ id: "person-kind", label: "They are a", control: kind,
                wide: true }),
      ],
      confirmLabel: "Add them",
    });
    if (!ok) return;

    if (!first.value.trim() && !last.value.trim()) {
      await tell({ title: "That needs a name",
                   body: "Give at least a first or last name, then try again." });
      return;
    }

    const delegate = kind.value === "delegate";
    let created;
    try {
      created = await api.post("/sponsor/people", {
        school_id: schoolId || undefined,
        first_name: first.value.trim(),
        last_name: last.value.trim(),
        person_type: delegate ? "delegate" : "adult",
        adult_type: delegate ? undefined : kind.value,
      });
    } catch (error) {
      await tell({ body: error.message });
      return;
    }

    showCode(`${created.first_name} ${created.last_name}`.trim(), created.code,
             `Give this to ${created.first_name || "them"} with their sheet.`,
             created.id);
  }

  /* One code, shown once, with nothing else on the screen to compete with it.
   * Used by everything that mints a code: a new sponsor, a new person, and a
   * reissue. */
  function showCode(name, code, note, personId = null) {
    clear(host);
    add(host, el("section", { class: "panel", role: "alertdialog",
                              "aria-label": `Access code for ${name}` },
      el("h2", {}, name),
      el("p", { class: "label" }, "Access code"),
      el("p", { class: "tabula__code mono", style: "font-size:1.5rem" }, code),
      el("p", {}, "This is the only time this code is shown, and nothing can "
                + "recover it. " + note),
      el("div", { class: "btn-row" },
        personId
          ? button("Print their sheet", {
              onclick: () => openPrintView("/sponsor/packet", {
                school_id: schoolId || undefined,
                codes: [{ person_id: personId, code }],
              }),
            })
          : null,
        button("Back to the roster", {
          variant: "btn--primary",
          onclick: () => reload(),
        }))));
  }

  /* Create a chapter's sponsor, and show their code once.
   *
   * A chair adds a chapter from the Chapters page, and until this existed the
   * chapter then sat there with nobody able to sign in to it. The code is
   * shown once and cannot be recovered, so it is displayed on its own with
   * nothing else competing for attention.
   */
  async function addSponsor(school) {
    const first = input({ id: "sponsor-first", autocomplete: "off" });
    const last = input({ id: "sponsor-last", autocomplete: "off" });
    const email = input({ id: "sponsor-email", type: "email",
                          autocomplete: "off" });

    const ok = await check({
      title: `Add the sponsor for ${school.name}`,
      body: [
        el("p", {}, "This creates their account and issues their access code. "
                  + "You will see the code once, on the next screen."),
        field({ id: "sponsor-first", label: "First name", required: true,
                control: first, wide: true }),
        field({ id: "sponsor-last", label: "Last name", required: true,
                control: last, wide: true }),
        field({ id: "sponsor-email", label: "Email", control: email, wide: true,
                help: "Where you will send their code. Optional here." }),
      ],
      confirmLabel: "Create the account",
    });
    if (!ok) return;

    if (!first.value.trim() && !last.value.trim()) {
      await tell({ title: "That needs a name",
                   body: "Give the sponsor at least a first or last name, then "
                       + "try again." });
      return;
    }

    let created;
    try {
      created = await api.post(`/admin/schools/${school.id}/people`, {
        first_name: first.value.trim(),
        last_name: last.value.trim(),
        email: email.value.trim() || null,
        adult_type: "sponsor",
      });
    } catch (error) {
      await tell({ body: error.message });
      return;
    }

    showCode(`${created.first_name} ${created.last_name}`.trim(), created.code,
             "Send it to them now, in a message addressed to them alone.",
             created.id);
  }

  function reissueBar(people) {
    const active = people.filter((p) => p.status === "active");
    const count = picked.size;

    return el("div", { class: "panel", style: "margin-bottom:1.5rem" },
      el("h2", {}, "Issue new codes"),
      el("p", { class: "muted" },
        "Tick the people whose code has been lost, or who never received a "
        + "sheet. Their old codes stop working at once and every device signed "
        + "in with one is signed out, so leave everybody else alone."),
      el("div", { class: "btn-row" },
        button(`Select all ${active.length}`, {
          variant: "btn--small btn--quiet",
          onclick: () => {
            active.forEach((p) => picked.add(p.id));
            render();
          },
        }),
        button("Clear", {
          variant: "btn--small btn--quiet",
          onclick: () => { picked.clear(); render(); },
        }),
        button(count === 1 ? "Issue 1 new code" : `Issue ${count} new codes`, {
          variant: "btn--primary",
          disabled: count === 0,
          onclick: () => reissue(),
        })));
  }

  /* Shows every new code once, with the print link for exactly those sheets.
   * The codes are not recoverable afterwards -- that is the whole reason this
   * screen exists -- so it does not go away on its own. */
  async function reissue() {
    const ids = [...picked];
    const names = data.people
      .filter((p) => picked.has(p.id))
      .map((p) => fullName(p));

    const ok = await check({
      title: `Issue new codes for ${ids.length} `
             + `${ids.length === 1 ? "person" : "people"}?`,
      // Named, not counted. Ticking the wrong row is the mistake this catches,
      // and a number cannot show it.
      body: [el("ul", {}, ...names.slice(0, 10).map((n) => el("li", {}, n))),
             names.length > 10 ? `…and ${names.length - 10} more` : null,
             "Their current codes stop working immediately."],
      confirmLabel: "Issue the codes", danger: true,
    });
    if (!ok) return;

    let result;
    try {
      result = await api.post("/sponsor/regenerate-codes", {
        person_ids: ids, school_id: schoolId || undefined });
    } catch (error) {
      await tell({ body: error.message });
      return;
    }

    clear(host);
    add(host, el("section", { class: "panel", role: "alertdialog",
                              "aria-label": "New access codes" },
      el("h2", {}, result.issued.length === 1
        ? "One new access code" : `${result.issued.length} new access codes`),
      el("p", {}, "This is the only time these are shown. Print the sheets "
                + "now — nothing can recover a code after you leave this page."),
      el("table", { class: "table" },
        el("thead", {}, el("tr", {},
          el("th", { scope: "col" }, "Name"),
          el("th", { scope: "col" }, "New code"))),
        el("tbody", {}, ...result.issued.map((row) => el("tr", {},
          el("td", {}, row.name),
          el("td", { class: "mono" }, row.code))))),
      el("div", { class: "btn-row" },
        // POSTED with the codes above. The GET version of this URL renders
        // blocks, because the stored code is an HMAC -- so the sheets it
        // produced were unusable, which is the opposite of what "print these
        // sheets" promises after a reissue.
        button("Print these sheets", {
          variant: "btn--primary",
          onclick: () => openPrintView("/sponsor/packet", {
            school_id: schoolId || undefined,
            codes: result.issued.map((row) => ({ person_id: row.person_id,
                                                 code: row.code })),
          }),
        }),
        button("Done", {
          onclick: async () => {
            selecting = false;
            picked.clear();
            await reload();
          },
        }))));
  }

  function tickColumn() {
    return {
      key: "pick", label: "Reissue",
      render: (row) => row.status !== "active"
        ? el("span", { class: "muted" }, "—")
        : el("input", {
            type: "checkbox",
            checked: picked.has(row.id),
            "aria-label": `Issue a new code for ${fullName(row)}`,
            onchange: (event) => {
              if (event.target.checked) picked.add(row.id);
              else picked.delete(row.id);
              // Only the bar's count and button state change.
              const bar = host.querySelector(".panel .btn-row");
              if (bar) render();
            },
          }),
    };
  }

  function columns() {
    /* A chair opening a chapter wants to know who is in it and to be able to
     * act. Grade and Latin level stay out: they are the sponsor's working
     * state and five extra columns push the actions off the side of a screen.
     *
     * ACTIVITIES IS IN, because a chair can now reopen a form and waive a
     * sheet. It used to be hidden on the grounds that a chair could do nothing
     * about it, which stopped being true the moment those buttons existed --
     * and a button whose effect you cannot see is worse than no button.
     *
     * The paper ticks stay out. Those really are the sponsor's, and they are
     * the one thing on this page a chair should not quietly do for them.
     *
     * "Type" becomes "Position", because for an adult we can say what they
     * actually are rather than repeating the word "Adult" down the column. */
    const tick = selecting ? [tickColumn()] : [];

    if (asChair) {
      return [
        ...tick,
        { key: "name", label: "Name", sortable: true,
          render: (row) => el("span", {},
            fullName(row),
            row.status !== "active"
              ? el("span", { class: "pill", style: "margin-left:.5rem" },
                  row.status === "cancelled_paid" ? "Cancelled · paid" : "Cancelled")
              : null,
            row.is_chapter_leader
              ? el("span", { class: "pill pill--done", style: "margin-left:.5rem" },
                  "Chapter leader")
              : null) },
        { key: "id", label: "ID", sortable: true,
          render: (row) => el("span", { class: "mono" }, personNumber(school, row)) },
        { key: "position", label: "Position", sortable: true,
          render: (row) => position(row) },
        { key: "form_status", label: "Activities", render: formState },
        { key: "actions", label: "Actions", render: (row) => actions(row) },
      ];
    }

    return [
      ...tick,
      { key: "name", label: "Name", sortable: true,
        render: (row) => el("span", {},
          fullName(row),
          row.status !== "active"
            ? el("span", { class: "pill", style: "margin-left:.5rem" },
                row.status === "cancelled_paid" ? "Cancelled · paid" : "Cancelled")
            : null,
          row.is_chapter_leader
            ? el("span", { class: "pill pill--done", style: "margin-left:.5rem" },
                "Chapter leader")
            : null) },
      // The same number printed on their sheet and shown on their account, so
      // a sponsor reading one out over the phone is reading the same thing.
      { key: "id", label: "ID", sortable: true,
        render: (row) => el("span", { class: "mono" }, personNumber(school, row)) },
      { key: "person_type", label: "Type", sortable: true,
        render: (row) => row.person_type === "delegate"
          ? "Delegate"
          : (row.adult_type || "adult").replace(/^\w/, (c) => c.toUpperCase()) },
      { key: "grade", label: "Grade", render: (row) => row.grade || "—" },
      { key: "latin_level", label: "Latin", render: (row) => row.latin_level || "—" },
      // "Form" and "Paper forms" sat next to each other and neither said which
      // was which. One is the thing they fill in on this site; the other is the
      // paper that has to reach the sponsor's hands.
      { key: "form_status", label: "Activities", render: formState },
      { key: "paper", label: "Forms",
        render: (row) => paperControls(row) },
      { key: "actions", label: "Actions", render: (row) => actions(row) },
    ];
  }

  /* Where their own form has got to.
   *
   * Three states, not two. "Waived" is not a kind of "not yet": it is a
   * decision somebody made at the desk, and showing it as unfinished sends a
   * chair chasing a delegate who has nothing left to do.
   *
   * "Reopened" is worth saying out loud as well. A form that is past the
   * deadline but open for one person is exactly the sort of thing that gets
   * forgotten, and the next person to look at the row should be able to see
   * why it is editable.
   */
  function formState(row) {
    if (row.activity_sheet_waived) {
      return el("span", { class: "pill" }, "Waived");
    }
    return el("span", {},
      row.form_status === "submitted"
        ? el("span", { class: "pill pill--done" }, "✓ Submitted")
        : el("span", { class: "pill" }, "Not yet"),
      row.forms_unlocked
        ? el("span", { class: "pill", style: "margin-left:.35rem" }, "Reopened")
        : null);
  }

  /* What this person is, in the words the convention uses. `adult_type_other`
   * holds the actual title for a board member -- "Registration Chair" beats
   * "Other" for anyone reading the list. */
  function position(row) {
    // The board title first: a convention president is a delegate, and
    // "Delegate" is true but not what a chair scanning this list needs.
    if (row.board_title) return row.board_title;
    if (row.person_type === "delegate") return "Delegate";
    if (row.adult_type_other) return row.adult_type_other;
    return {
      sponsor: "Sponsor", chaperone: "Chaperone", scl: "SCL",
    }[row.adult_type] || "Adult";
  }

  /* Impersonation needs the admin's own code typed again. That step-up is the
   * point: a walked-away laptop should not be one click from reading a
   * chapter's roster as its sponsor. */
  function sponsorOf(people) {
    return (people || []).find(
      (p) => p.person_type === "adult" && p.adult_type === "sponsor"
             && p.status === "active") || null;
  }

  const impersonateSponsor = () => {
    const sponsor = sponsorOf(data.people);
    if (sponsor) impersonate(sponsor);
  };

  /* Sign in as anybody on this roster, not only the sponsor.
   *
   * A chair debugging "my activity sheet will not save" needs to see the
   * delegate's screen, not their sponsor's. The server has always allowed
   * this; only the button was missing. */
  async function impersonate(person) {
    const code = await ask({
      title: `Sign in as ${fullName(person)}`,
      body: "You will see exactly what they see, read-only, for thirty "
          + "minutes. Both names appear in a banner on every page, and this is "
          + "recorded in the log.",
      label: "Your own access code",
      confirmLabel: "Sign in as them",
      secret: true,
    });
    if (!code) return;

    try {
      const result = await api.post("/auth/impersonate", {
        target_person_id: person.id, admin_code: code.trim() });
      // Keep the admin's own token so the banner's Stop button can restore it.
      api.adminToken.set(api.token.get());
      api.token.set(result.token);
      adopt(result.person);
      // Where they land has to be a page THEY can open. A delegate has no
      // roster, and sending them to one bounces straight to "no access".
      location.hash = person.person_type === "delegate"
        ? "#/activity-sheet"
        : "#/roster";
      await route();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  function paperControls(row) {
    const forms = row.person_type === "delegate"
      ? [["student_waiver", "Waiver", row.waiver_received],
         ["student_medical", "Medical", row.medical_received]]
      : [["adult_medical", "Medical", row.medical_received]];

    return el("span", { style: "display:flex; gap:.75rem; flex-wrap:wrap" },
      ...forms.map(([formType, label, received]) => {
        const box = el("input", {
          type: "checkbox", checked: !!received,
          // A cancelled person is not attending, so whether their waiver
          // arrived is not a question anyone needs to answer. Leaving it
          // clickable invited a sponsor to tidy up a row that no longer counts.
          disabled: row.status !== "active",
          id: `paper-${row.id}-${formType}`,
          onchange: async (event) => {
            event.target.disabled = true;
            try {
              await api.post("/sponsor/paper-forms", {
                person_id: row.id, form_type: formType,
                received: event.target.checked,
              });
              await reload();
            } catch (error) {
              event.target.checked = !event.target.checked;
              event.target.disabled = false;
              await tell({ body: error.message });
            }
          },
        });
        return el("span", { style: "display:inline-flex; gap:.35rem; align-items:center" },
          box, el("label", { for: `paper-${row.id}-${formType}`, class: "small" }, label));
      }));
  }

  function actions(row) {
    const wrap = el("span", { style: "display:flex; gap:.5rem; flex-wrap:wrap" });

    // Only scope '*' may impersonate, and only somebody who can actually sign
    // in. It is the fastest way to answer "what does this person see?".
    if (hasScope("*") && row.status === "active") {
      add(wrap, button("View as", {
        variant: "btn--small btn--quiet",
        onclick: () => impersonate(row),
      }));
    }

    if (row.status === "active") {
      add(wrap, button("New code", {
        variant: "btn--small",
        onclick: () => regenerate(row),
      }));

      /* Reopening a form is a REGISTRATION CHAIR's job, not a sponsor's.
       *
       * The deadline stops a delegate editing their own answers; it was never
       * meant to stop a chair. Until this button existed the only way through
       * was somebody with a terminal, which meant every "she picked the wrong
       * Latin level" became an email to an admin. */
      // ONLY ONCE THE DEADLINE HAS PASSED. Before it, every form is open
      // already and this button does nothing you could see — so it sat on
      // every row all season looking like a control that was broken.
      if (hasScope("registration") && (data.forms_closed || row.forms_unlocked)) {
        add(wrap, button(row.forms_unlocked ? "Close form" : "Reopen form", {
          variant: "btn--small btn--quiet",
          onclick: () => setUnlocked(row, !row.forms_unlocked),
        }));
      }

      /* Waiving the activity sheet, for somebody added at the desk on the
       * Friday. Their waiver and medical are still required -- those are
       * safety documents and nobody is exempt -- but the tests were printed
       * and the food ordered weeks ago, so there is nothing left for their
       * answers to change. Without this they sit in their chapter's completion
       * figure as permanently unfinished. */
      if (hasScope("registration") && row.person_type === "delegate") {
        add(wrap, button(row.activity_sheet_waived
              ? "Un-waive sheet" : "Waive sheet", {
          variant: "btn--small btn--quiet",
          onclick: () => setWaived(row, !row.activity_sheet_waived),
        }));
      }
      if (row.person_type === "delegate") {
        add(wrap, button(row.is_chapter_leader ? "Unset leader" : "Make leader", {
          variant: "btn--small btn--quiet",
          onclick: async () => {
            await api.post(`/sponsor/people/${row.id}/chapter-leader`,
                           { granted: !row.is_chapter_leader });
            await reload();
          },
        }));
      }
      add(wrap, button("Edit", {
        variant: "btn--small btn--quiet",
        onclick: () => editPerson(row),
      }));
      add(wrap, button("Cancel", {
        variant: "btn--small btn--danger",
        onclick: async () => {
          const ok = await check({
            title: `Cancel ${fullName(row)}?`,
            body: "They can be restored later, and the roster keeps their row.",
            confirmLabel: "Cancel them", cancelLabel: "Leave them on",
            danger: true,
          });
          if (!ok) return;
          await api.post(`/sponsor/people/${row.id}/cancel`, {});
          await reload();
        },
      }));
    } else {
      add(wrap, button("Restore", {
        variant: "btn--small",
        onclick: async () => {
          await api.post(`/sponsor/people/${row.id}/restore`, {});
          await reload();
        },
      }));
    }
    return wrap;
  }

  /* Regeneration shows the new code ONCE and immediately offers the reprint.
   * Without the reprint the sponsor is holding a packet page whose QR no longer
   * works, with no obvious way to produce a new one. */
  async function regenerate(row) {
    const name = fullName(row);
    const ok = await check({
      title: `Issue a new code for ${name}?`,
      body: "Their old code, and every device signed in with it, stop working "
            + "immediately — so you will need to give them the new sheet.",
      confirmLabel: "Issue a new code", danger: true,
    });
    if (!ok) return;

    const result = await api.post(`/sponsor/people/${row.id}/regenerate-code`, {});
    const dialog = el("div", { class: "panel", role: "alertdialog",
                               "aria-label": `New code for ${name}` },
      el("p", { class: "label" }, "New access code"),
      el("p", { class: "tabula__code mono", style: "font-size:1.5rem" }, result.code),
      el("p", {},
        "This is the only time this code is shown. Print the new sheet now and " +
        `give it to ${row.first_name}.`),
      el("div", { class: "btn-row" },
        button("Print their new sheet", {
          variant: "btn--primary",
          onclick: () => openPrintView("/sponsor/packet", {
            school_id: schoolId || undefined,
            codes: [{ person_id: row.id, code: result.code }],
          }),
        }),
        button("Done", { onclick: async () => { dialog.remove(); await reload(); } })));

    clear(host);
    add(host, dialog);
  }

  function compare(a, b) {
    const direction = sort.direction === "asc" ? 1 : -1;
    const pick = (row) => {
      if (sort.key === "name") return `${row.last_name} ${row.first_name}`.toLowerCase();
      // "Position" is computed, not stored -- row.position does not exist, so
      // sorting on it compared "" against "" and left the order untouched.
      if (sort.key === "position") return position(row).toLowerCase();
      const value = row[sort.key];
      return value === null || value === undefined ? "" : String(value).toLowerCase();
    };
    // Adults and delegates stay grouped, because a sponsor reads the roster as
    // two lists -- EXCEPT when the chosen column is the one that says which is
    // which. Grouping first there means clicking "Position" appears to do
    // nothing at all, since the grouping has already decided the order.
    const groupingWouldWin = sort.key !== "position" && sort.key !== "person_type";
    if (groupingWouldWin && a.person_type !== b.person_type) {
      return a.person_type < b.person_type ? -1 : 1;
    }
    return pick(a) < pick(b) ? -direction : pick(a) > pick(b) ? direction : 0;
  }
}

/** Open a server-rendered print view in a new tab, carrying the session token.
 *  The print views are HTML documents, not JSON, so they are fetched and
 *  written into the new window rather than linked -- a plain link would arrive
 *  without the Authorization header. */
export async function openPrintView(path, body = null) {
  /* `body` turns this into a POST, which the packet needs when it is carrying
   * codes: a query string would put them in the browser's history and in every
   * access log on the way. */
  const target = window.open("", "_blank");
  if (!target) {
    await tell({ title: "The print window was blocked",
                 body: "Your browser stopped this page opening a new tab. "
                       + "Allow pop-ups for this site, then try again." });
    return;
  }
  target.document.write("<p style=\"font:14px system-ui;padding:2rem\">Preparing…</p>");
  try {
    const html = body
      ? await api.postText(path, body)
      : await api.getText(path);
    target.document.open();
    target.document.write(html);
    target.document.close();
  } catch (error) {
    target.document.body.textContent = error.message;
  }
}
