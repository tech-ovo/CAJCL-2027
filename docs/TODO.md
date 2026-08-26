# What is not built yet

Everything known to be missing, with a rough estimate. Estimates assume someone
who has read `RUNBOOK.md` and has the project running — not a first day.

They are **working hours, not calendar time**. Halve your confidence in
anything above four hours; that is where estimates start being wishes.

Ordered by ratio of value to effort, not by importance. Where something is
blocked, the blocker is named.

Status: **NEXT** (worth doing now) · **SOON** (before registration opens,
autumn 2026) · **BEFORE CONVENTION** (March 2027) · **LATER** · **DECIDED
AGAINST**

---

## Straight after the demonstration, in this order

Both were deliberately deferred: each one breaks the deployed site until a
reset follows it, which is not a thing to do five days before showing it to a
board. `docs/DEPLOY.md`, "After the demonstration", has the reset commands.

| | What | Hours | Notes |
| --- | --- | --- | --- |
| AFTER 29 AUG | Merge `010_welcome_wording` and `011_board_title` into the migrations they correct | 1 | Then delete both files and re-run `scripts/checksum_migrations.py`. **The deploy will refuse to start until the database is reset**, because the hashes of `001` and `005` change — so do it in the same sitting as the reset, not before. The reasoning that lives in those two files belongs in `RUNBOOK.md`, not in a migration comment. |
| AFTER 29 AUG | A "no meal" option | 0.5 | For somebody bringing their own for an allergy. Last in the list, never the default. Blocked today because `people.meal` carries `CHECK (meal IN ('regular','vegetarian','gluten_free'))`, SQLite cannot alter a CHECK, and the pragmas a table rebuild needs are refused by Turso. **Trivial the moment `001_core.sql` is edited directly** — do it in the same sitting as the merge. |
| AFTER 29 AUG | Let an organization have no level | 0.5 | `schools.level` is NOT NULL with `CHECK (level IN ('MS','HS'))`, so SCL is stored as 'HS' and the frontend just hides the level for organizations. Nullable is honest; it needs a table rebuild, which is free while `001_core.sql` is being edited anyway. |
| AFTER 29 AUG | Add "At Large (MS)" and "At Large (HS)" | 0.5 | **Two rows, not one.** Members at large can be either level, and every rule that gates Latin levels, tests and grades reads `schools.level` — one row would have to be wrong for half of them. Both `kind = 'organization'`. |
| AFTER 29 AUG | A sponsor serving more than one chapter | 3 | `people.school_id` is one column, so this needs a grant table: a primary school, plus rows saying which others that person may manage. Touches `auth.require_school`, which is the most safety-critical code here — do it on its own, not alongside anything else. Has never happened; this is future-proofing. |

## Small

| | What | Hours | Notes |
| --- | --- | --- | --- |
| SOON | Catalog editing screen | 6 | The catalog is seeded correctly and read-only. Cut for the demo. |
| LATER | Draft restore on the settings form | 1 | The activity and adult sheets keep a `localStorage` draft. Settings warns before leaving but keeps nothing. |

## The board and the chapter it lives in

The state-board pseudo-chapter should go, and its people should sit in their
real schools. Agreed in principle; not done.

| | What | Hours | Notes |
| --- | --- | --- | --- |


**The prefix is fully retired.** `ADM` is gone from `VALID_PREFIXES`, so those
codes no longer sign anybody in, and `modal run backend/app.py::retire_adm_codes`
reissues for everyone who held one. A code now says what somebody *is* and never
changes when a role is granted — the same model as chapter leader.

**The bootstrap is documented**, in DEPLOY.md step 4b: the first commissioner
adds themselves through `board.json`, which is the one door that opens from
outside a signed-in session, and everybody else is added from Settings → Roles.

**Moving people between chapters is safe.** The prefix is part of the hashed
string, so changing it breaks a code — but a chapter move does not touch it.
Only a change in what somebody *is* (a sponsor becoming a chaperone) forces a
reissue and a reprinted sheet.

## Asked for, not yet built

| | What | Hours | Notes |
| --- | --- | --- | --- |
| SOON | Adding a delegate at the desk | 2 | The check-in screen is built; this half of it is not. A chapter turns up with a replacement and there is no way to enter them at the desk. The roster's **Add the sponsor** button now proves the pattern — same endpoint, `POST /admin/schools/{id}/people` — so what is left is a form inside the check-in dialog, plus `POST /admin/people/{id}/waive-activity-sheet`, which exists and is tested. The invoice does not change: the chapter paid for a head and it is bringing one. |
| SOON | Pasting a roster for another chapter | 2 | A chair cannot get a sponsor's spreadsheet in for them; today that needs a president to sign in as the sponsor. `sponsor.roster.parse` and `sponsor.roster.commit` both already accept a registration chair, so the work is a `#/roster/{id}/import` route and passing `school_id` on the two calls the import page makes. Promised to the chairs in docs/REGISTRATION.md §11 as a known gap. |
| SOON | Adding one person to a roster | 1 | `POST /sponsor/people` exists, is tested, and nothing calls it. Sponsors add people by pasting again — a second paste adds rather than replaces — which works but is not what anybody looks for. |
| SOON | Reopening a submitted form | 1 | `POST /admin/people/{id}/unlock-forms` works and has no button. A delegate who submitted their sheet with the wrong Latin level currently needs an admin with a terminal. A control on the roster row is the whole job. Promised to the chairs in docs/REGISTRATION.md §11 as a known gap. |
| SOON | Editing a chapter | 2 | `PATCH /admin/schools/{id}` sets the name, city, level, discount and billing exemption, and nothing on the site calls it. Chapters are created from the dashboard, so a typo in a name is permanent until somebody runs a script. Promised to the chairs in docs/REGISTRATION.md §11 as a known gap. |
| SOON | Quota screen | 1 | `GET /admin/usage` already returns rows read, rows written and storage, and no page shows them. During convention the quota is the number worth watching from a phone, and the alternative is a terminal. One stat block on Operations. |
| SOON | Split Entries into Academics and Activities | 2 | One page listing fifty items serves two different chairs. The category is already on every row; this is a tab, not a query. |
| SOON | Four-digit test IDs, editable by Academic Chairs | 3 | A number per test, entered on a **subset** of Settings → Values — which means a scoped settings view, since `academics` scope must not reach the fee or the deadlines. That gating is the real work; the column is trivial. |

## Awards and academics

Nothing here is built. This is the largest remaining piece of the convention.

| | What | Hours | Notes |
| --- | --- | --- | --- |
| BEFORE CONVENTION | Score entry | 12 | Per test, per delegate. Needs an offline story: the gym has no wifi. |
| BEFORE CONVENTION | Tabulation and placings | 10 | Ties, sweepstakes, per-chapter totals. Get the rules in writing from the awards chair **first**. |
| BEFORE CONVENTION | Certamen brackets | 16 | Rounds, rooms, buzzer order. Consider not building this at all in year one. |
| LATER | Printed award certificates | 4 | The print pipeline already exists; this is templates. |

Danny Yoo and Isa Baucum are in `board.json` as Awards Chairs at University
High School, so **Entries** is already open to them.

## Known gaps in what already exists

| | What | Hours | Notes |
| --- | --- | --- | --- |
| BEFORE CONVENTION | PDF generation, tested end to end | 3 | The print view works and is the same document. The PDF path has never been run against a real request. **Demo the print view.** |
| BEFORE CONVENTION | Check-in screen | 6 | Friday afternoon, fifty chapters arriving at once after school. Wants to work on a phone with bad wifi. |
| SOON | Apps Script for Drive exports | 5 | Exports currently download to the browser. Only needed for contest submissions. |
| LATER | Chapter team entries UI | 4 | The data model and endpoints exist. No screen. |

## Decided against

Recorded so nobody re-opens them without new information.

| What | Why |
| --- | --- |
| Refunds | The convention runs on pre-payment. `cancelled_paid` keeps the balance honest without a refund path. |
| Moving delegates between chapters | Has not come up. Cancel and re-add if it ever does. |
| A fee snapshot per school | The fee does not change once registration opens. If it must, a discount or a negative payment handles it, and both leave a trail. |
| Storing codes reversibly | It would make packet reprints easy and make a database dump useful to a thief. The selective reissue flow solves the same problem. |
| Deleting a board member | They are real people who are usually also a sponsor or a delegate, and the audit log refers to them. Removing every role takes away the powers and leaves the person, which is what "they have left the board" actually means. **Settings → Roles → Remove every role.** |
| An idle session timeout | Would mostly punish an honest delegate filling in a long form on a school Chromebook. Sign-out is on every page. |

---

## How to keep this file honest

Add a row when you notice something missing, not when you get round to fixing
it. A file that only records completed work is a changelog, and there is
already one of those in the git history.

When something here is done, **delete the row** — do not mark it done. What is
left undone is the only thing this file is for.
