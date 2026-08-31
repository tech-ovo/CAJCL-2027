# **Structure**

*Carl Liu + Timothy Chen | 2027 CAJCL Convention Technology Commissioners*

This document describes the structure of the 72nd CAJCL State Convention website — University High School, Irvine, March 12–13, 2027. Registration is built and running; the sections below describe the whole site, including the parts that are not. `docs/TODO.md` says which is which, with estimates.

Throughout,  marks what is and is not in scope for that meeting.

# **Public**

Most of the site sits behind a login for security. The only public sections are a small set of welcome pages.

The welcome page carries the masthead, the convention theme, the dates and venue, and live statistics: the number of registered schools split into middle school and high school, and the number of registered attendees split into delegates and adults. These statistics are served from a cached single row rather than computed on request, and the page renders a build-time snapshot of the convention facts immediately so that a visitor arriving while Modal is cold sees a complete page rather than a spinner.

# **Account**

Each attendee receives one secret code, generated at registration, in the format `PPP-XXXXX-XXXXX` — a three-letter prefix (`SPO` sponsor, `DEL` delegate, `VOL` adult volunteer or chaperone — the prefix says what a person *is*, never what they may do), nine random Crockford Base32 characters, and a check symbol. A person holds exactly one code no matter how many roles they have. Additional permissions come from **roles granted to the account**, and roles carry scopes; a scope is never attached to a person directly, and there is never a second code.

They enter it once, or scan the QR code on their printed sheet, and `localStorage` keeps a session token so they never log in again on that device. The raw code is never stored on the device.

**Assume shared devices.** Many delegates will use a school Chromebook or a friend's phone, so a sign-out control must be visible on every page — not buried in a menu — and signing out must revoke that session server-side rather than only clearing `localStorage`. A person's own account page lists their active sessions with device and last-seen, and lets them revoke any of them.

If someone loses their code they talk to their sponsor, who regenerates it. Regeneration invalidates the old code, the old QR, and every session derived from it, and it **must immediately offer a single-attendee reprint** — otherwise the sponsor is left holding a packet page whose QR no longer works, with no obvious way to produce a new one.

Delegates can later see their personalized schedule with mandatory events and their own signups, links to voting and other activities, and eventually scores and point totals. Adults can see their duties, contact information for their shifts, and emergency contacts. Everyone gets the campus map, which is available only after login for security.

# **Registration**

## Getting a school into the system

The sponsor has already registered through [the official CAJCL site](https://n344.fmphost.com/fmi/webd#CAJCL-Database), which we do not control. When we are notified by email that a new school has registered, an admin creates the school in the dashboard — name, middle school or high school — and creates one or more sponsor accounts, which generates their codes. An admin then **manually** sends each sponsor an email from the official CAJCL account containing detailed instructions and their code. Nothing about this is automated; there is no bulk mailing anywhere in this system.

A chapter that sends both middle and high school delegates registers twice, as two separate schools, since they usually have separate sponsors anyway.

## The roster

The sponsor pastes in the names of every delegate and adult in their chapter. **Accept any format.** Sponsors will paste from a spreadsheet with tabs, from a Word document with bullets and numbering, from an email with commas, with `Last, First` in some rows and `First Last` in others, with trailing whitespace and smart quotes and stray blank lines. One name per line is the only real rule, and even that should degrade gracefully.

Parsing produces first, middle, and last name. Middle is blank when there isn't one. Lowercase particles attach to the last name rather than being read as a middle name — the canonical particle list lives in `schema.md` and is the only copy; do not duplicate it. Suffixes like `Jr.`, `III` go to a suffix field. Capitalization from the input is preserved rather than normalized, because title-casing mangles `McDonald` and `de la Cruz`; the only exception is a line that arrives entirely uppercase or entirely lowercase, which gets careful title casing with particle and `Mc`/`O'` handling.

Parsing **never writes to the database**. It returns a preview: an editable table with one row per parsed name, with warnings attached. First-middle-last is ordinary and is *not* flagged; only four or more tokens after particle folding, or a single token, get a confirmation warning. So does any duplicate within the paste, any duplicate against the existing roster, and any line containing an unexpected character. Warnings should be rare enough that a sponsor reads them — flagging every third row trains people to click through. The sponsor reviews, corrects inline, and confirms — and only then does anything get written.

The confirm request carries an **idempotency key** issued with the preview. A double-click, a flaky connection, or an impatient refresh cannot create the roster twice. This is the single most damaging thing a sponsor could accidentally do, and it must be impossible.

In the same preview table, the sponsor can prefill per-delegate details so students don't have to: grade, Latin level, meal preference, and parent/guardian name and phone. Parent name and phone also serve as the deduplication key for two delegates with the same name in one chapter. We do not collect personal emails from delegates at all — every communication goes through the sponsor — which also keeps us clear of collecting contact information from eleven-year-olds.

Each attendee gets a sequential ID, assigned in order and not tied to their school, and a code. Sponsors can add attendees, remove them, reset codes, and edit any field at any time. Delegates cannot change their own name and must ask their sponsor.

An attendee who can no longer attend is **marked cancelled rather than deleted**, and can be restored. Because there are **no refunds**, cancellation has two forms and the site picks between them from the payment record: someone who withdraws before their chapter's check arrives stops being billed, while someone who withdraws after it arrives keeps counting toward the invoice so the balance still reads correctly. The sponsor is never asked which — they should not have to know the billing policy to remove a student.

A person is never **moved** between chapters. Chapters are completely separate, and a chapter sending both middle and high school delegates is already two schools with two sponsors. If a sponsor enters someone under the wrong chapter, they cancel that row and enter them again under the right one.

## The printed packet

The site generates a printable packet for the sponsor. It contains one page per attendee with that person's name, ID, access code, QR code, and the instructions for finishing registration, plus a cover sheet for the chapter.

The packet also includes the paper forms that are **not** filled out online: the student waiver, the student medical form, and the adult medical form. These follow the same procedure as previous years. Attendees print them, sign them by hand with a parent or guardian signature where required, and return them to their sponsor. The sponsor collects and scans the whole packet, mails the paper along with the check, and uploads the scans to their school's Google Drive folder.

That Drive folder link is stored in the database and visible **only to the Convention Presidents**. Registration chairs never see it. Instead, the sponsor attests to completeness in the portal with two checkboxes per attendee — waiver received, medical received — as part of assembling the packet they're already mailing. Chairs see the attestation; Presidents can audit against Drive; nobody else touches minors' medical information. Legibility and signature checks happen at Friday check-in.

**This folder is not managed by Apps Script and this site never reads it.** The sponsor uploads to it directly with their own Google account, sharing is granted manually to the Presidents, and the database holds nothing but a URL string. It is deliberately outside the automated path: medical data for minors should not be reachable by any code we write, and there is no feature that would benefit from it being reachable. This is entirely separate from the Apps-Script-managed Drive described under pre-convention contests and exports below — do not conflate the two.

The printed sheet also notes that an attendee with no access to any electronic device can ask their sponsor to print physical copies of the [delegate](https://docs.google.com/document/d/1G1BEMj3XtU-W4DLDzbMDaL9iJW1q0Q4-KvWGX6APQSs/edit?usp=sharing) and [adult](https://docs.google.com/document/d/1uiMRT6wFq2TGTYWkrJiq4cD6a5gEKrSRR-9K2LoCVnI/edit?usp=sharing) forms, which the sponsor then transcribes. This is strongly discouraged, and the printed sheet says so.

Because the sheet carries a working credential, it says that too, and shows the attendee's name large enough that a sponsor cannot hand the wrong page to the wrong student.

## What delegates fill out online

The **Student Activity Sheet** becomes a single web form, submitted once rather than saving on every keystroke, and editable by the delegate until the deadline. It collects grade, Latin level, and meal preference — prefilled if the sponsor entered them — and then the delegate's event choices:

- **Academic testing.** Between one and three tests, enforced as a **hard block**. Eligibility depends on Latin level: Grammar 1 is MS-1–2 and HS-1, Grammar 2 is MS-3 and HS-2, Grammar 3 is HS-3 and above, and Reading Comprehension 1, 2, and 3 mirror them. Ineligible tests are disabled with an explanation, not hidden.
- **Academic and creative arts.** Costume, Dramatic Interpretation, English Oratory, Essay, Latin Oratory, Sight Latin Reading.
- **Graphic arts.** Fourteen categories. Drawing/Painting permits up to eight sub-categories; other categories carry their own sub-options where they have them.
- **Olympika.** Chess and Track are individual entries; Track carries sub-options for 100m, 200m, and 400m. **Kickball, Fugepilam, and Ultimate Frisbee are chapter entries**, registered by the sponsor or by a delegate the sponsor has granted chapter-leadership permission — not by individual delegates.
- ***Ludi.*** Eleven activities including Open Certamen, Pandora's Breakout Box, and Spelling Bee.

A middle school chapter's delegates see only grades 6–8 and levels MS-1 through MS-3; a high school chapter's see only grades 9–12 and HS-1 through HS-Adv.

None of these choices are binding. They exist so the Academics, Activities, and Athletics chairs can plan, and the form says so plainly.

## What adults fill out online

The **Adult Registration Sheet** becomes a web form collecting name, email, cell phone, type (Latin teacher/sponsor, parent/chaperone, SCL, other), meal preference, and Latin knowledge on the original four-level scale: none, novice, intermediate, advanced. Keep all four even though every current role requires either nothing or advanced — different jobs need different familiarity with the language, and a future chair should be able to mark a role as requiring intermediate Latin without a schema change.

Adults then choose volunteer roles from the same dashboard-editable catalog: Wherever Needed, Certamen Reader, Certamen Scorer/Timer, Graphic Arts Judge, Olympika Volunteer, Ludi Volunteer, and the creative arts judging roles (Latin Oratory, Sight Latin Reading, Essay Reading, Costume, English Oratory, Dramatic Interpretation). Roles requiring Latin are marked. **There are no time blocks** — adults simply indicate which events they are willing to run — and a free-text note field captures availability constraints and anything else they need to explain.

"Please sign up for at least two roles" is a **warning, not a block**. An adult who ignores it can still submit.

**SCL adults do not complete this form.** Their type is prefilled and their roles are assigned separately, outside the website.

## Payment and invoices

Sponsors see how much their chapter owes, how much has been received, and the remaining balance. An admin records payments in the dashboard, entering the exact amount received so it can be corrected, with the audit log preserving each individual entry.

The invoice is `$140 × billable delegates`, plus `max(0, $75 × (billable adults − ceil(billable delegates ÷ 10)))`, minus the school's discount, floored at zero. A school with five delegates gets one free adult. Both fee amounts, and every other figure below, are editable in the dashboard rather than hard-coded.

**Billable** means active attendees plus anyone who cancelled after the chapter paid — see the roster section above. **The discount** is a per-school amount an admin sets by hand, with a reason shown on the invoice: a new-chapter discount, a hardship arrangement, or the way a fee change gets honoured after invoicing. There is no early-bird discount and no late fee; every chapter pays the same amount at the same time.

**Some chapters are not billed.** SCL pays nothing but still needs accounts so its members can complete forms. Members at large DO pay; they are an organization rather than a chapter, which is a separate question from billing. This is a `billing_exempt` flag on the school record, toggled in the admin dashboard — **not** a special case keyed to the name "SCL" in code. A name check would silently break the first time someone types "S.C.L." or creates a second exempt chapter. An exempt school computes an invoice total of zero, its invoice page says why in plain words rather than showing a blank, and it is excluded from the chair dashboard's outstanding-balance total so the number stays meaningful.

The generic invoice details — payment deadline of February 13, 2027, and remit to University High School JCL c/o Mark Michalak, University High School, 4771 Campus Drive, Irvine, CA 92612 — are dashboard-editable settings. There is a [sample invoice](https://docs.google.com/spreadsheets/d/180ZfF7xyLx_PvS293pFebJZp7511rYZ2JMQz00zSAJ0/edit?usp=sharing) from two years ago to work from.

There is **no refund**, for a school or an attendee, in any circumstance: an event this size runs on pre-payment. A school that withdraws after paying keeps its payment on record; a chapter is only ever marked exempt on bookkeeping grounds, like SCL, and never after money has arrived.

If a fee ever did change mid-cycle it is handled ad hoc rather than by machinery, using the discount field and — where money has to go back — a negative payment row. The payment history and the audit log carry the record.

## Deadlines

Delegate and adult forms lock on **February 13, 2027**, the same date as the payment deadline. The lock date is editable in the dashboard, and an admin can unlock an individual person when a legitimate exception comes up.

# **Administration**

Every account gets its permissions from roles, and roles carry scopes. Four scopes are **administrative**: `registration` (roster, payment, check-in), `academics` (test and activity registration, pre-convention contests, grading and scanning, Certamen), `awards` (score entry, test printing, tabulation), and `*`, which subsumes everything including announcements, audit log access, exports, role management, and impersonation. Three more are **identity** scopes carried by ordinary accounts and always school-limited: `sponsor`, `delegate`, and `chapter` (chapter team entries, held by sponsors and by any delegate a sponsor promotes to chapter leader). Administrative scopes are global rather than per-school; identity scopes never are. If a chair can read a thing, they can generally write it — the exception is that nobody outside the Convention Presidents sees the Drive folders.

An admin with `*` can create new roles with any combination of scopes and grant them to any account, so future chairs can be provisioned without code changes.

**Viewing another account.** An admin with `*` can open a read-only view of exactly what another person sees, which is the only practical way to debug a confused sponsor. It requires re-entering the admin's own code, expires after thirty minutes, shows a permanent banner naming both identities, and never reveals the target's code. Editing while impersonating requires an explicit second toggle. Every action inside the session is logged with both the acting identity and the impersonator.

## `Registration`

Registration chairs track progress and numbers: how many chapters have registered, how large each is, how many attendees have completed their forms, and what has been paid. Chairs will track logistics on the website rather than in a separate Google Sheet — fellowship room, volunteer liaison from Uni or Woodbridge — referencing the [sheet](https://docs.google.com/spreadsheets/d/1a96kLUzhJIifKt0-ab-NkzhDb9JlXXJZZwW43Aug9J0/edit?usp=sharing) used previously. On Friday a per-chapter checklist streamlines check-in. Everything is exportable at any point if things break down, but keeping it on the site is far more streamlined.

Nametag PDF generation is deferred.

## `Academics, Activities, and Athletics`

Chairs track how many students registered for each test and activity so they can prepare materials. During convention they enter scores directly; academic chairs upload a scan of the bubble sheets for optical mark recognition.

**Pre-convention contests** — Modern Myth, Poetry, Slogan (English), and Slogan (Latin) — are submitted by delegates **through the website**. The delegate uploads their file to the portal, Modal passes it to the Apps Script puppet, and the puppet files it into the Google Drive under a folder structure organized by contest and then by chapter, returning the Drive file ID for Modal to store alongside the submission record. Chairs are then simply granted access to the relevant contest folder in Drive and judge from there; they do not download anything through this site.

This is a **different Drive mechanism** from the packet folders described under Registration. Contest submissions are written by Apps Script, live in the Google Drive, are organized automatically, and are non-sensitive student creative work. Medical forms and waivers are uploaded manually by sponsors to a separate folder that no code touches and only the Presidents can open. Keep them structurally separate, with separate folder roots, so no future change can accidentally widen access to the second while working on the first.

## `Awards`

Points are tabulated automatically from events. A Google Slides deck, sticker sheet, and awards script are generated from final scores. Delegates and sponsors receive a score report.

## Site settings

Everything a future commissioner would otherwise need code to change lives in dashboard-editable settings: convention year, ordinal, dates, venue name and address, theme text with translation and citation, contact email, fee amounts, deadlines, the warm-until timestamp, auto-export on/off with its shut-off time, and the announcement banner.

The activity and role catalogs are likewise editable through a web UI — items, sub-options, eligibility by Latin level and school level, and whether an item is offered at all. Adding a new *ludus* for 2028 requires no code. **Categories and their rules** — the minimum and maximum selection counts, and whether a rule blocks or warns — stay in a migration: a wrong rule stops delegates submitting for a reason nobody can find, and that is not a thing to type into a box.

# **Utilities**

**Schedule.** Delegates view the events they signed up for and register for new ones like Pandora's Breakout Box. Opt-in notifications on mobile, including shift reminders for some adults.

**Map.** Interactive map of Uni with every event location marked and directions available. Attendees see what is happening now and what is happening soon. Tapping a location or event opens details — live Certamen scores, colloquia abstracts and slides — plus signup links.

**Lost and found.** Images stored in the Google Drive through the Apps Script puppet, with Drive file IDs cached in the database rather than crawled.

# **Miscellaneous**

**Certamen.** A central hub for resources, CARCER placements, brackets and scores, possibly question-by-question statistics like [what Princeton does](https://www.princetoncertamen.org/past-questions), and Open Certamen registration with teams and matchups.

**Voting.** Delegates vote on graphic arts, as was done at St. Francis, and on photos if there is a contest or gallery.

**Scavenger hunt.** Something physical with volunteers staffed around campus may well be more fun than anything digital.

**Feedback form.** Available throughout convention, possibly with prizes for the most helpful feedback.

---

# **Appendix A: a roster paste worth keeping**

Kept because it is the hardest input the parser has to survive, and because
every line in it is deliberate. Paste it into **Roster → Paste a roster** after
any change to `backend/lib/names.py` and read the preview against the table
below. `backend/tests/test_names.py` covers the same ground automatically; this
is for looking at it with your own eyes.

**Those are real tab characters.** Copy the block rather than retyping it, or
paste three columns out of a spreadsheet, which produces exactly this.

```
Aurelia Vance	9	HS-1
Marcus DeLuca	10	HS-2
Priya Raghunathan	11	HS-3
Chen, Wei-Lin	9	HS-1
Okonkwo, Ngozi A.	12	HS-Adv
Sofia van der Berg	10	HS-2
Jamal Washington III	11	HS-3
Elena Marie Castellanos	9	HS-1
theodore huang	10	HS-2
MIRANDA OYELARAN	12	HS-Adv
Rafael Ortiz-Mendoza	11	HS-3
Yuki Tanaka	9	HS-1
1. Amara Nwosu	10	HS-2
2. Dmitri Volkov, Jr.	12	HS-Adv
3. Isabella Rossi	11	HS-3
Aurelia Vance	9	HS-1
```

| Line | What it shows |
| --- | --- |
| `Chen, Wei-Lin` | `Last, First` read correctly — first name Wei-Lin |
| `Okonkwo, Ngozi A.` | inverted **and** a middle initial |
| `Sofia van der Berg` | `van der` stays with the surname, not the middle name |
| `Jamal Washington III` | a generational suffix in its own field |
| `theodore huang` | typed lower case, filed as Theodore Huang |
| `MIRANDA OYELARAN` | typed shouting, filed as Miranda Oyelaran |
| `1. Amara Nwosu` | numbered list, numbers discarded |
| `Dmitri Volkov, Jr.` | a comma that is **not** `Last, First` |
| `Aurelia Vance` twice | the only row flagged, as a duplicate |

The last row is the only one flagged, and it is flagged as a duplicate rather
than rejected: the sponsor decides.

---

# **Appendix B: questions sponsors ask**

**These are aimed at sponsors**, and they were written for a room — short
enough to answer out loud, and honest where the answer is "not yet". A board
or a parent asks the same things in a different order.

Some answers name specific behaviour. Check them against the site before
relying on one: a few were written when parts of this were still unbuilt.

### About the students

**"What about student privacy?"**
Delegate email addresses are never collected — several delegates are eleven.
Medical forms and waivers are paper, scanned by the sponsor into their own
Drive folder that no code here reads. The site records only that a form
arrived, never what is in it.

**"Is this real student data?"**
No. Every chapter, delegate and parent on the site is invented, and the banner
at the top of every page says so. The only real people are the board members in
this room.

**"What if a student does not have a phone or a computer?"**
Their sponsor can print a paper copy of the form and type the answers in for
them. It is slower and mistakes are harder to catch, so the packet says to
avoid it where possible — but nobody is locked out.

**"Can a student change their own name?"**
No. Names come from the sponsor's roster, and a delegate cannot edit theirs.
This is deliberate: the name on the roster is the name on the award.

**"What stops a student signing in as someone else?"**
Nothing except holding the other student's sheet, and the sheet says so in
plain words. That is the trade for having no passwords. Every sheet carries one
name in large type so a sponsor cannot hand the wrong page to the wrong
student, and a lost sheet is replaced in about ten seconds.

### About the sponsors

**"How much work is this for me?"**
Paste your roster once. Tick each paper form as it arrives. That is the whole
job. Everything else — the invoice, the packet, the codes — is generated.

**"What if my spreadsheet is a mess?"**
That is the case it was built for. You just watched it read four different
formats in one paste. Anything ambiguous is flagged rather than guessed at, and
every row is editable before anything is saved.

**"Can two of us from the same school use it?"**
Yes. A chapter can have more than one sponsor and both can edit the roster. If
you both paste a roster at the same time you will get both rosters — the site
warns about duplicates but does not stop you.

**"What if a student drops out after we have paid?"**
They are marked cancelled and stay on the invoice, so your balance still reads
zero. There are no refunds — the convention runs on pre-payment — and the site
does not pretend otherwise by showing you a credit that is never coming.

**"Does the deadline actually lock me out?"**
It locks the students out of their own forms. A chair can reopen any individual
form, and you can always ask.

### About the money

**"Who sees what we have paid?"**
You, and the registration chairs. Not other chapters. The invoice shows the
arithmetic rather than a total, so if the number is wrong you can see where.

**"What if the fee changes after we are invoiced?"**
It is not expected to once registration opens. If it has to, the site handles
it with a discount or a negative payment, and both leave a visible trail on
your invoice.

**"We are not billed. Will the site cope?"**
Yes — that is a flag on the chapter, not a name check, so it keeps working if
SCL is ever typed differently. An exempt chapter's invoice says why it is zero
instead of showing a blank page.

### About the system

**"Who pays for this?"**
Nobody. All three services are on free tiers with a large margin, and it has
been measured rather than estimated.

**"What happens if it goes down during convention?"**
There is a local copy that runs with no internet at all, and every backup is an
ordinary SQLite file that opens in free tools. The runbook is written for
somebody who did not build this and is panicking.

**"Who maintains it next year?"**
Next year's commissioners, and that is the point. Every fee, deadline, date and
block of printed wording is editable from the Settings page without touching
code. The handover documents are in the repository.

**"What is not built yet?"**
Scores, tabulation and Certamen brackets. Registration is finished; the awards
side is not. There is a list with time estimates, and it is honest.

**"Can we see the code?"**
It is public. That is deliberate — the next commissioners inherit it, and a
private repository would have to be handed over rather than simply found.
