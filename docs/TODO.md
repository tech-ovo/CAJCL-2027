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

## Small

| | What | Hours | Notes |
| --- | --- | --- | --- |
| SOON | Catalog editing screen | 6 | The catalog is seeded correctly and read-only. Cut for the demo. |
| SOON | Restore `board.json` from the live database | 1 | If the file is lost, the names are still in the database. A `--export` flag on `add_board.py` would rebuild it. |
| LATER | Draft restore on the settings form | 1 | The activity and adult sheets keep a `localStorage` draft. Settings warns before leaving but keeps nothing. |

## The board and the chapter it lives in

The state-board pseudo-chapter should go, and its people should sit in their
real schools. Agreed in principle; not done.

| | What | Hours | Notes |
| --- | --- | --- | --- |
| SOON | Move board members into their real chapters | 3 | Yun Jen Yeh, Aurelian Shen and Mark Corrigan to Woodbridge; everyone else to University. Then delete `CAJCL State Board`. Moving a person does not change their prefix, so codes survive. |

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

## Awards and academics

Nothing here is built. This is the largest remaining piece of the convention.

| | What | Hours | Notes |
| --- | --- | --- | --- |
| BEFORE CONVENTION | Test-registration counts per chapter | 4 | "How many from each chapter sat Latin Grammar 2." One indexed query, one table. The obvious next dashboard. |
| BEFORE CONVENTION | Score entry | 12 | Per test, per delegate. Needs an offline story: the gym has no wifi. |
| BEFORE CONVENTION | Tabulation and placings | 10 | Ties, sweepstakes, per-chapter totals. Get the rules in writing from the awards chair **first**. |
| BEFORE CONVENTION | Certamen brackets | 16 | Rounds, rooms, buzzer order. Consider not building this at all in year one. |
| LATER | Printed award certificates | 4 | The print pipeline already exists; this is templates. |

**Before any of it:** create accounts for Danny Yoo and Isa Baucum as Awards
Chairs at University High School — add them to `board.json` with
`"roles": ["awards_chair"]` and re-run `modal run backend/app.py::board`. That
takes two minutes and unblocks the rest.

## Known gaps in what already exists

| | What | Hours | Notes |
| --- | --- | --- | --- |
| BEFORE CONVENTION | PDF generation, tested end to end | 3 | The print view works and is the same document. The PDF path has never been run against a real request. **Demo the print view.** |
| BEFORE CONVENTION | Check-in screen | 6 | Friday morning, fifty chapters arriving at once. Wants to work on a phone with bad wifi. |
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
