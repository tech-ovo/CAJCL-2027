# **Structure**

*Carl Liu + Timothy Chen | 2027 CAJCL Convention Technology Commissioners*

This document describes the structure of the 72nd CAJCL State Convention website — University High School, Irvine, March 12–13, 2027. A demo of the registration component will be presented at the August 29th state board meeting, and includes only the functionality related to registration.

Throughout, *[Demo: …]* marks what is and is not in scope for that meeting.

# **Public**

Most of the site sits behind a login for security. The only public sections are a small set of welcome pages.

The welcome page carries the masthead, the convention theme, the dates and venue, and live statistics: the number of registered schools split into middle school and high school, and the number of registered attendees split into delegates and adults. These statistics are served from a cached single row rather than computed on request, and the page renders a build-time snapshot of the convention facts immediately so that a visitor arriving while Modal is cold sees a complete page rather than a spinner.

*[Demo: the welcome page with statistics. Later, general registration information for a public audience, relevant links, corporate sponsors, and the convention board.]*

# **Account**

Each attendee receives one secret code, generated at registration, in the format `PPP-XXXXX-XXXXX` — a three-letter prefix (`SPO` sponsor, `DEL` delegate, `VOL` adult volunteer or chaperone, `ADM` admin), nine random Crockford Base32 characters, and a check symbol. A person holds exactly one code no matter how many roles they have; additional permissions are scopes attached to the account, not additional codes.

They enter it once, or scan the QR code on their printed sheet, and `localStorage` keeps a session token so they never log in again on that device. The raw code is never stored on the device. If someone loses their code they talk to their sponsor, who regenerates it — which invalidates the old code, the old QR, and every session derived from it.

*[Demo: all of this.]*

Delegates can later see their personalized schedule with mandatory events and their own signups, links to voting and other activities, and eventually scores and point totals. Adults can see their duties, contact information for their shifts, and emergency contacts. Everyone gets the campus map, which is available only after login for security.

*[Demo: none of this.]*

# **Registration**

## Getting a school into the system

The sponsor has already registered through [the official CAJCL site](https://n344.fmphost.com/fmi/webd#CAJCL-Database), which we do not control. When we are notified by email that a new school has registered, an admin creates the school in the dashboard — name, middle school or high school — and creates one or more sponsor accounts, which generates their codes. An admin then **manually** sends each sponsor an email from the official CAJCL account containing detailed instructions and their code. Nothing about this is automated; there is no bulk mailing anywhere in this system.

A chapter that sends both middle and high school delegates registers twice, as two separate schools, since they usually have separate sponsors anyway.

*[Demo: the admin flow for creating a school and its sponsor accounts, shown live at the start of the presentation. The email itself is composed by hand outside the site.]*

## The roster

The sponsor pastes in the names of every delegate and adult in their chapter. **Accept any format.** Sponsors will paste from a spreadsheet with tabs, from a Word document with bullets and numbering, from an email with commas, with `Last, First` in some rows and `First Last` in others, with trailing whitespace and smart quotes and stray blank lines. One name per line is the only real rule, and even that should degrade gracefully.

Parsing produces first, middle, and last name. Middle is blank when there isn't one. Lowercase particles — `de`, `de la`, `van`, `van der`, `von`, `da`, `di`, `du`, `le`, `bin`, `al` — attach to the last name rather than being read as a middle name. Suffixes like `Jr.`, `III` go to a suffix field. Capitalization from the input is preserved rather than normalized, because title-casing mangles `McDonald` and `de la Cruz`; the only exception is a line that arrives entirely uppercase or entirely lowercase, which gets careful title casing with particle and `Mc`/`O'` handling.

Parsing **never writes to the database**. It returns a preview: an editable table with one row per parsed name, with warnings attached. Anything that produced more than two name tokens after particle folding is flagged for confirmation. So is any duplicate within the paste, any duplicate against the existing roster, and any line containing an unexpected character. The sponsor reviews, corrects inline, and confirms — and only then does anything get written.

The confirm request carries an **idempotency key** issued with the preview. A double-click, a flaky connection, or an impatient refresh cannot create the roster twice. This is the single most damaging thing a sponsor could accidentally do, and it must be impossible.

In the same preview table, the sponsor can prefill per-delegate details so students don't have to: grade, Latin level, meal preference, and parent/guardian name and phone. Parent name and phone also serve as the deduplication key for two delegates with the same name in one chapter. We do not collect personal emails from delegates at all — every communication goes through the sponsor — which also keeps us clear of collecting contact information from eleven-year-olds.

Each attendee gets a sequential ID, assigned in order and not tied to their school, and a code. Sponsors can add attendees, remove them, reset codes, and edit any field at any time. Delegates cannot change their own name and must ask their sponsor.

An attendee who can no longer attend is **marked cancelled rather than deleted**, and can be restored.

*[Demo: all of this. The parsing logic should be genuinely good, since it is the most impressive thing to show a board. Later: richer duplicate detection, a manual per-student edit form with more validation, and SCL and delegate-at-large registration — which is easy, just a school named SCL and a school named At Large with some ad hoc handling. SCL does not pay but still needs accounts.]*

## The printed packet

The site generates a printable packet for the sponsor. It contains one page per attendee with that person's name, ID, access code, QR code, and the instructions for finishing registration, plus a cover sheet for the chapter.

The packet also includes the paper forms that are **not** filled out online: the student waiver, the student medical form, and the adult medical form. These follow the same procedure as previous years. Attendees print them, sign them by hand with a parent or guardian signature where required, and return them to their sponsor. The sponsor collects and scans the whole packet, mails the paper along with the check, and uploads the scans to their school's Google Drive folder.

That Drive folder link is stored in the database and visible **only to the Convention Presidents**. Registration chairs never see it. Instead, the sponsor attests to completeness in the portal with two checkboxes per attendee — waiver received, medical received — as part of assembling the packet they're already mailing. Chairs see the attestation; Presidents can audit against Drive; nobody else touches minors' medical information. Legibility and signature checks happen at Friday check-in.

The printed sheet also notes that an attendee with no access to any electronic device can ask their sponsor to print physical copies of the [delegate](https://docs.google.com/document/d/1G1BEMj3XtU-W4DLDzbMDaL9iJW1q0Q4-KvWGX6APQSs/edit?usp=sharing) and [adult](https://docs.google.com/document/d/1uiMRT6wFq2TGTYWkrJiq4cD6a5gEKrSRR-9K2LoCVnI/edit?usp=sharing) forms, which the sponsor then transcribes. This is strongly discouraged, and the printed sheet says so.

Because the sheet carries a working credential, it says that too, and shows the attendee's name large enough that a sponsor cannot hand the wrong page to the wrong student.

*[Demo: the packet as an HTML print view with a real print stylesheet, which works even if PDF generation is down and is the first thing to cut if time runs short. Server-side PDF via WeasyPrint on a separate fat Modal image comes second.]*

## What delegates fill out online

The **Student Activity Sheet** becomes a single web form, submitted once rather than saving on every keystroke, and editable by the delegate until the deadline. It collects grade, Latin level, and meal preference — prefilled if the sponsor entered them — and then the delegate's event choices:

- **Academic testing.** Between one and three tests, enforced as a **hard block**. Eligibility depends on Latin level: Grammar 1 is MS-1–2 and HS-1, Grammar 2 is MS-3 and HS-2, Grammar 3 is HS-3 and above, and Reading Comprehension 1, 2, and 3 mirror them. Ineligible tests are disabled with an explanation, not hidden.
- **Academic and creative arts.** Costume, Dramatic Interpretation, English Oratory, Essay, Latin Oratory, Sight Latin Reading.
- **Graphic arts.** Fourteen categories. Drawing/Painting permits up to eight sub-categories; other categories carry their own sub-options where they have them.
- **Olympika.** Chess and Track are individual entries; Track carries sub-options for 100m, 200m, and 400m. **Kickball, Fugepilam, and Ultimate Frisbee are chapter entries**, registered by the sponsor or by a delegate the sponsor has granted chapter-leadership permission — not by individual delegates.
- ***Ludi.*** Eleven activities including Open Certamen, Pandora's Breakout Box, and Spelling Bee.

A middle school chapter's delegates see only grades 6–8 and levels MS-1 through MS-3; a high school chapter's see only grades 9–12 and HS-1 through HS-Adv.

None of these choices are binding. They exist so the Academics, Activities, and Athletics chairs can plan, and the form says so plainly.

*[Demo: all of this, including the eligibility gating, the hard block on test count, the graphic arts sub-categories, and chapter entries.]*

## What adults fill out online

The **Adult Registration Sheet** becomes a web form collecting name, email, cell phone, type (Latin teacher/sponsor, parent/chaperone, SCL, other), meal preference, and a single yes/no for whether they know Latin — replacing the original four-level scale, of which only two levels were ever used.

Adults then choose volunteer roles from the same dashboard-editable catalog: Wherever Needed, Certamen Reader, Certamen Scorer/Timer, Graphic Arts Judge, Olympika Volunteer, Ludi Volunteer, and the creative arts judging roles (Latin Oratory, Sight Latin Reading, Essay Reading, Costume, English Oratory, Dramatic Interpretation). Roles requiring Latin are marked. **There are no time blocks** — adults simply indicate which events they are willing to run — and a free-text note field captures availability constraints and anything else they need to explain.

"Please sign up for at least two roles" is a **warning, not a block**. An adult who ignores it can still submit.

**SCL adults do not complete this form.** Their type is prefilled and their roles are assigned separately, outside the website.

*[Demo: all of this.]*

## Payment and invoices

Sponsors see how much their chapter owes, how much has been received, and the remaining balance. An admin records payments in the dashboard, entering the exact amount received so it can be corrected, with the audit log preserving each individual entry.

The invoice is `$140 × active delegates`, plus `max(0, $75 × (active adults − ceil(active delegates ÷ 10)))`. A school with five delegates gets one free adult. Both fee amounts, and every other figure below, are editable in the dashboard rather than hard-coded.

The generic invoice details — payment deadline of February 13, 2027, and remit to University High School JCL c/o Mark Michalak, University High School, 4771 Campus Drive, Irvine, CA 92612 — are dashboard-editable settings. There is a [sample invoice](https://docs.google.com/spreadsheets/d/180ZfF7xyLx_PvS293pFebJZp7511rYZ2JMQz00zSAJ0/edit?usp=sharing) from two years ago to work from.

*[Demo: the invoice, the sponsor's view of amount owed and amount paid, and the admin action to record a payment. Not yet decided and left as explicit TODOs in the code: whether a cancelled attendee still counts toward the invoice, and what happens when the fee changes mid-cycle. There is probably no late registration fee.]*

## Deadlines

Delegate and adult forms lock on **February 13, 2027**, the same date as the payment deadline. The lock date is editable in the dashboard, and an admin can unlock an individual person when a legitimate exception comes up.

# **Administration**

Admin accounts carry scopes. The four scopes are `registration` (roster, payment, check-in), `academics` (test and activity registration, pre-convention contests, grading and scanning, Certamen), `awards` (score entry, test printing, tabulation), and `*`, which subsumes everything including announcements, audit log access, exports, role management, and impersonation. Scopes are global rather than per-school. If a chair can read a thing, they can generally write it — the exception is that nobody outside the Convention Presidents sees the Drive folders.

An admin with `*` can create new roles with any combination of scopes and grant them to any account, so future chairs can be provisioned without code changes.

**Viewing another account.** An admin with `*` can open a read-only view of exactly what another person sees, which is the only practical way to debug a confused sponsor. It requires re-entering the admin's own code, expires after thirty minutes, shows a permanent banner naming both identities, and never reveals the target's code. Editing while impersonating requires an explicit second toggle. Every action inside the session is logged with both the acting identity and the impersonator.

*[Demo: four admin accounts with `*` for the two convention presidents and two technology commissioners, plus the role-creation UI and impersonation.]*

## `Registration`

Registration chairs track progress and numbers: how many chapters have registered, how large each is, how many attendees have completed their forms, and what has been paid. Chairs will track logistics on the website rather than in a separate Google Sheet — fellowship room, volunteer liaison from Uni or Woodbridge — referencing the [sheet](https://docs.google.com/spreadsheets/d/1a96kLUzhJIifKt0-ab-NkzhDb9JlXXJZZwW43Aug9J0/edit?usp=sharing) used previously. On Friday a per-chapter checklist streamlines check-in. Everything is exportable at any point if things break down, but keeping it on the site is far more streamlined.

Nametag PDF generation is deferred.

*[Demo: the chair dashboard with per-school progress, totals, and completion tracking. Nametags and the Friday checklist come later.]*

## `Academics, Activities, and Athletics`

Chairs track how many students registered for each test and activity so they can prepare materials. They receive submitted pre-convention contests — **Modern Myth, Poetry, Slogan (English), and Slogan (Latin)** — along with graphic arts and other entries, and distribute them to judges. During convention they enter scores directly; academic chairs upload a scan of the bubble sheets for optical mark recognition.

*[Demo: none of this, though the activity registration counts the chairs will eventually consume are already being collected.]*

## `Awards`

Points are tabulated automatically from events. A Google Slides deck, sticker sheet, and awards script are generated from final scores. Delegates and sponsors receive a score report.

*[Demo: none of this. Set up the database infrastructure — a points column and the shape of a score record — so the schema doesn't need reworking later.]*

## Site settings

Everything a future commissioner would otherwise need code to change lives in dashboard-editable settings: convention year, ordinal, dates, venue name and address, theme text with translation and citation, contact email, fee amounts, deadlines, the warm-until timestamp, auto-export on/off with its shut-off time, and the announcement banner.

The activity and role catalogs are likewise fully editable through a web UI — categories, items, sub-options, eligibility by Latin level and school level, minimum and maximum selection counts, and whether a rule blocks or warns. Adding a new *ludus* for 2028 should require no code.

*[Demo: all of this, since it is what makes the site inheritable.]*

# **Utilities**

*[Demo: nothing in this section.]*

**Schedule.** Delegates view the events they signed up for and register for new ones like Pandora's Breakout Box. Opt-in notifications on mobile, including shift reminders for some adults.

**Map.** Interactive map of Uni with every event location marked and directions available. Attendees see what is happening now and what is happening soon. Tapping a location or event opens details — live Certamen scores, colloquia abstracts and slides — plus signup links.

**Lost and found.** Images stored in Timothy's Google Drive through the Apps Script puppet, with Drive file IDs cached in the database rather than crawled.

# **Miscellaneous**

*[Demo: nothing in this section.]*

**Certamen.** A central hub for resources, CARCER placements, brackets and scores, possibly question-by-question statistics like [what Princeton does](https://www.princetoncertamen.org/past-questions), and Open Certamen registration with teams and matchups.

**Voting.** Delegates vote on graphic arts, as was done at St. Francis, and on photos if there is a contest or gallery.

**Scavenger hunt.** Something physical with volunteers staffed around campus may well be more fun than anything digital.

**Feedback form.** Available throughout convention, possibly with prizes for the most helpful feedback.
