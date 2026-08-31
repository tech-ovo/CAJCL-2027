# What is left

Everything between here and **March 12–13, 2027**, worked out from
`docs/structure.md` and from what is actually in the repository.

Read the first two sections and you know what to do next. The rest is reference.

**Hours are one person's working hours**, not calendar time, and they assume
somebody who already knows this codebase. Double them for somebody who does
not.

---

## How to read the columns

| | |
| --- | --- |
| **NOW** | Nothing blocks it. It can start today. |
| **NEEDS YOU** | Blocked on a decision, an account, or a document only you can get. The blocker is named. |
| **NOT DOING** | Ruled out. Left here so nobody reopens it without new information. |

The **Who** column says whether it needs you at all:

| | |
| --- | --- |
| **auto** | Buildable start to finish with no input. |
| **ask** | One question, then buildable. |
| **you** | Genuinely yours: an account, a policy, a document. |

---

## 1. Before registration opens

**This is the critical path.** Codes go out to fifty chapters once, and
anything that changes how somebody signs in, or what their sheet says, is far
cheaper before that than after.

| | What | Hrs | Who | Notes |
| --- | --- | --- | --- | --- |
| NEEDS YOU | Two-factor for adults and the board | 8 | you | Deliberately on hold until the `conventionpresidents@cajcl.org` Workspace account exists. Design and reasoning are in `docs/SECURITY.md` §7. **Do it before codes are sent**, or fifty sponsors have to be told sign-in changed. |
| NEEDS YOU | The opening email | 1 | you | Drafted in `docs/REGISTRATION.md` §4. Check every figure against Settings → Values, then send one message per chapter. |
| NEEDS YOU | Click **Save as PDF** once, on Modal | 0.2 | you | Everything either side of WeasyPrint is built and tested. WeasyPrint itself needs Pango and Cairo and cannot run on Windows, so the render has never executed. One click after the next deploy settles it. **Print is unaffected either way** — it is the same document, built by the same code, and it works. |
| NEEDS YOU | Real chapters and sponsors | 2 | you | Chapters → Add a chapter, then Add the sponsor on each. About fifty. Nothing technical; it is the data the whole year runs on. |

**"At Large" is two chapters, not one** — one MS, one HS — because every rule
that gates Latin levels, tests and grades reads `schools.level`. Neither is
billing-exempt; only SCL is. Make them the same way as any other chapter.

---

## 2. Before the forms deadline — 13 February 2027

Registration is running by now. These make the months in between bearable.

| | What | Hrs | Who | Notes |
| --- | --- | --- | --- | --- |
| NOW | Reuse database connections | 4 | auto | **Measured.** An authenticated request opens two connections and each costs a TLS handshake to Turso: one ≈ 350 ms, three ≈ 3 s. The session touch was the third and is now daily, which took most of it. What is left is the remaining doubling. Attempted twice and reverted twice — see §6. |
| NOW | Four-digit test IDs | 3 | auto | A number per test, entered on a **subset** of Settings → Values. The scoped settings view is the real work: `academics` must not reach the fee or the deadlines. |
| NEEDS YOU | Apps Script for Drive exports | 5 | you | Needs the Workspace account and its Drive root. Exports download to the browser today, which works; this is for contest submissions. |
| NOW | Pre-convention contest uploads | 8 | auto | Modern Myth, Poetry, Slogan. Depends on Apps Script above. Schema exists (`docs/schema.md`, "Contest submissions"). |
| NOW | A sponsor serving more than one chapter | 3 | auto | `people.school_id` is one column, so this needs a grant table. Touches `auth.require_school`, the most safety-critical code here — do it alone. Has never happened; this is future-proofing. |

---

## 3. Before convention — March 2027

**The awards side is the largest unbuilt piece**, and the one with the most
unknowns.

| | What | Hrs | Who | Notes |
| --- | --- | --- | --- | --- |
| NEEDS YOU | Tabulation rules, in writing | — | you | **Get these from the awards chair before anything below is built.** Ties, sweepstakes, per-chapter totals, what counts toward what. Building against a guess and rewriting it is the expensive path. |
| NEEDS YOU | Score entry | 12 | ask | Needs an offline story: the gym has no wifi. One question first — do scores go in on paper and get typed after, or on a laptop in the room? |
| NEEDS YOU | Tabulation and placings | 10 | you | Blocked on the rules above. |
| NOT DOING | Certamen brackets | 16 | — | You have said not to build grading infrastructure. Rounds, rooms and buzzer order are a scheduling problem wearing a scoring hat. |
| NOW | Nametag PDFs | 3 | auto | The print pipeline exists; this is a template and a page size. |
| NOW | Printed award certificates | 4 | auto | Same pipeline, same shape. |
| NOW | A quota check the week before | 0.5 | auto | Settings → Operations shows it. Look at it in February, not in March. |

---

## 4. Ruled out for this year

You have said not to build these. Recorded so the reasoning survives.

| What | Why |
| --- | --- |
| **The map** | Your call. An interactive campus map with live event locations. |
| **The schedule** | Your call. Per-delegate schedules, signups, mobile notifications. |
| **Grading infrastructure** | Your call. Score entry, tabulation, Certamen brackets — §3 keeps the pieces that are not grading. |
| Refunds | The convention runs on pre-payment. `cancelled_paid` keeps the balance honest without a refund path. |
| Moving delegates between chapters | Has not come up. Cancel and re-add if it ever does. |
| A fee snapshot per school | The fee does not change once registration opens. If it must, a discount or a negative payment handles it, and both leave a trail. |
| Storing codes reversibly | It would make packet reprints easy and make a database dump useful to a thief. Selective reissue solves the same problem. |
| Deleting a board member | They are real people, usually also a sponsor or a delegate, and the audit log refers to them. **Settings → Roles → Remove every role** is what "they have left the board" actually means. |
| An idle session timeout | Would mostly punish an honest delegate filling in a long form on a school Chromebook. Sign-out is on every page. |
| Voting, scavenger hunt, feedback form | In `structure.md` under Miscellaneous. None is on the critical path; all are cheap to add later if somebody wants one. |

---

## 5. What I need from you, in one list

Everything above marked **you** or **ask**, gathered:

1. **The Workspace account** (`conventionpresidents@cajcl.org`). Unblocks
   two-factor and Apps Script — two of the five remaining large items.
2. **Tabulation rules from the awards chair**, in writing. Blocks all of §3.
3. **How scores are entered at convention** — paper then typed, or live on a
   laptop in a room with no wifi. One sentence unblocks 12 hours of work.
4. **The real chapter list**, with sponsors' names and emails.
5. **Whether "At Large" exists this year**, and whether both levels are needed.

---

## 6. Things that were tried and abandoned

Kept because the next person will otherwise try them again.

**Per-request connection reuse.** Middleware runs on the event loop while
handlers run on a threadpool thread, so a connection opened in middleware is
used cross-thread and `sqlite3` refuses outright. A per-thread pool works and
then leaks: connections on threadpool threads that nothing can close, because
`sqlite3` also refuses `close()` from another thread. A correct version needs a
real pool with an owning thread per connection and a shutdown hook. **Do not
attempt without a way to soak-test it against Turso.**

---

## 7. Known-good, and worth not breaking

Short list of things that took a while to get right and look ordinary now.

- **The roster parser.** `docs/structure.md` Appendix A is the reference paste;
  `backend/tests/test_names.py` covers the same ground automatically.
- **Idempotent roster commit.** A double-click cannot create two rosters. The
  key covers the pasted text and the roster as it stood, not the rows, which is
  why removing a row before committing still works.
- **Counters in the same transaction as the change.** No aggregate is ever
  computed live. `backend/queries/stats.sql` explains the arithmetic.
- **Scopes only through roles.** There is no table attaching a scope to a
  person and there must never be one.
- **Every endpoint declares its scope**, and the test suite walks all of them.

---

## How to keep this file honest

Add a row when you notice something missing, not when you get round to fixing
it. A file that only records completed work is a changelog, and there is
already one of those in the commit history.

When something ships, delete its row. When something is ruled out, move it to
§4 with the reason — a row that quietly disappears teaches the next person
nothing.
