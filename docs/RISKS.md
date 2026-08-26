# Risks

Ways this system can break, what was done about each, and what is still open.

Written continuously during the build, not at the end. **Add to it when you
notice something, not when you fix it** — an unmitigated risk that is written
down is worth more than a fixed one that nobody recorded.

Status key: **MITIGATED** (handled in code, with a test) · **PARTIAL** (handled,
with a known gap) · **ACCEPTED** (understood, deliberately not fixed) ·
**OPEN** (no mitigation yet).

---

## Data loss and duplication

### A sponsor pastes the same roster twice, or refreshes mid-commit
**MITIGATED.** The preview issues an HMAC-signed idempotency key carrying the
school id, a hash of the pasted text, a nonce, and a timestamp. Commit stores
that key in `roster_imports.idempotency_key`, which is `NOT NULL UNIQUE`. A
second commit with the same key finds the row and returns the first commit's
result instead of importing again. Preview itself writes nothing, so an
abandoned preview leaves no row to clean up.

This is the single most damaging accident available to a sponsor, so the
guarantee is a database constraint rather than an application check — an
application check loses to two concurrent requests.

### Two sponsors from one school edit the roster simultaneously
**PARTIAL.** Both hold `sponsor` scope on the same school, so both may write.
Distinct edits to distinct people are safe. Two simultaneous roster *commits*
of different pastes both succeed and produce a combined roster containing
everyone twice — the idempotency key does not help here, because the two pastes
genuinely differ.

Mitigation: the parser flags `duplicate_in_roster` against the roster as it
exists at preview time, so the second sponsor sees the warnings. That is a
warning, not a block.
**Still open:** no locking, and no "someone else changed this roster while you
were looking at it" check between preview and commit. The signed key contains a
hash of the pasted text but not of the roster state. Worth adding: reject a
commit whose preview is older than the school's `updated_at`.

### Someone pastes 5,000 lines into the roster textarea
**MITIGATED.** The parser is linear and handles 300 lines in single-digit
milliseconds, so this was never a parsing problem. It was two other things.

`roster.MAX_PASTE_LINES` caps a paste at 500 with a message naming the number
of lines sent, which covers the transaction size. That check ran *after*
FastAPI had read and parsed the whole body, though, so the body itself was
still unbounded — a middleware now refuses anything over 1 MB on the declared
`Content-Length`, before parsing. 1 MB is roughly forty times the largest
legitimate paste.

**Accepted:** a request that lies about its `Content-Length` is not caught. The
platform terminates the connection well before anything reaches this process,
and reading the stream to check would defeat the purpose.

---

## Credentials

### A delegate's code is regenerated while they have an open session
**MITIGATED.** Regeneration revokes every session derived from the old code, in
the same transaction. The delegate's next request returns 401 and the frontend
sends them to the sign-in screen with a message naming what happened, rather
than an unexplained failure.

### The sponsor is left holding a packet page whose QR no longer works
**MITIGATED.** Regeneration returns the new code once and immediately offers a
single-attendee reprint. This is required behaviour, not a convenience:
without it the sponsor has a dead sheet and no obvious path to a live one.

### A delegate signs in on a shared device and walks away
**PARTIAL.** Sign-out is visible on every page, not in a menu, and revokes the
session server-side rather than only clearing `localStorage`. A person's account
page lists their active sessions with device and last-seen and can revoke any of
them.
**Accepted:** sessions last 180 days and there is no idle timeout. An idle
timeout on a school Chromebook would mostly punish the honest delegate filling
in a long form. The shared-device risk is real but the blast radius is one
activity sheet, and the delegate cannot change their own name.

### A packet reprinted later has blocks where the codes should be
**MITIGATED, and it was a real hole.** A code is stored only as an HMAC, which
is what makes a stolen database useless — and it also means a code that was
never written down cannot be recovered. Reprinting a packet produced `███` in
place of every code and `XXXXX` in every QR, so the sheets were not credentials
at all. The failure was silent: the pages looked finished.

The way out is to mint new codes, and the safeguard is that the sponsor names
who gets one. The roster has a reissue mode: tick the people whose sheet was
lost, confirm, and every new code is shown once with a print link for exactly
those sheets. There is deliberately no "reissue for everyone" button — a
whole-chapter reissue signs out every delegate already using the site, most of
whom have their sheet and are fine.

**Still true:** the codes on that screen are shown once and are gone when the
page is left. That is the design, not a defect, and the screen says so.

### The printed sheet is a bearer credential
**ACCEPTED, with mitigations.** Anyone holding the sheet can sign in as that
person. The sheet says so in plain words, and shows the attendee's name large
enough that a sponsor cannot hand the wrong page to the wrong student. There is
no way around this: the whole point is that an eleven-year-old with no email
address can log in.

### Someone walks the code keyspace
**MITIGATED.** 45 bits of entropy, HMAC-peppered with the pepper in Modal
Secrets, plus 10 failures per IP per 15 minutes and 5 per code per hour. The
check symbol is validated in the browser, so honest typos never reach the
limiter. Failed attempts are logged with a keyed hash of the guess, which is
what makes the per-code limit possible at all.

### The pepper leaks or has to be rotated
**ACCEPTED.** Rotation invalidates every code and requires reprinting every
packet. `people.pepper_version` exists so it is possible, but it is a
break-glass procedure, not routine. See `RUNBOOK.md`.

---

## Money

### A school withdraws after paying
**RESOLVED — there are no refunds.** An event this size runs on pre-payment.
`schools.status` becomes `withdrawn`, the payment stays on record, and nothing
computes a refund because none is owed. Withdrawn schools drop out of the public
statistics; their payment history stays readable on their own page and in the
audit log.

### An attendee withdraws after their chapter paid
**RESOLVED — `cancelled_paid`.** `people.status` has three values, not two.
Someone who withdraws before their chapter's payment arrives becomes
`cancelled` and stops being billed; someone who withdraws after becomes
`cancelled_paid` and keeps counting toward the invoice, so the balance keeps
reading zero instead of turning into a credit nobody intends to refund. Which
one applies is decided from the payment record at cancellation time and never
asked of the sponsor — they should not have to know the billing policy to
remove a student. Tested in `test_money.py`.

### A school is marked exempt after paying
**RESOLVED — this does not happen.** Exemption is applied on bookkeeping
grounds only (SCL), when a chapter is created, and never after money
has arrived. Nothing enforces that in code, so an admin could still do it by
hand and produce a zero invoice against a positive payment. Judged not worth a
constraint: the recovery is obvious and visible, and it is corrected with a
negative payment row.

### The invoice fee changes in January, after some schools have paid
**RESOLVED — handled ad hoc, deliberately not modelled.** The fee is not
expected to change once registration opens, so there is no fee snapshot per
school and no effective date on the fee setting. If it has to change, the
mechanism already exists: fee **up**, give already-invoiced schools a discount
equal to the increase; fee **down** and you want to honour it, the recomputed
invoice falls by itself, and for schools that already paid the higher amount you
send the difference back and record a **negative payment**. Both paths leave a
readable trail in the payment history and the audit log. Written up in
`RUNBOOK.md`.

### A discount is entered wrong, or larger than the bill
**MITIGATED.** `discount_cents` carries `CHECK (discount_cents >= 0)` so it
cannot become a surcharge, and `invoice_cents()` floors the total at zero so an
oversized discount produces nothing owed rather than a credit. Both are tested.
The discount and its reason appear as their own line on the invoice, so a
sponsor can see why their bill is what it is.

### Billing exemption
**MITIGATED.** `schools.billing_exempt` is a flag, never a name check. A name
check breaks the first time someone types "S.C.L." or a second exempt chapter
appears. Exempt schools compute a zero total, say why in words rather than
showing a blank, and are excluded from the chair dashboard's outstanding-balance
total so that number stays meaningful.

---

## Time

### Forms lock at midnight on February 13 while someone is mid-submission
**PARTIAL.** The deadline is stored as a UTC instant computed from a wall-clock
California date, never hand-typed: `2027-02-14T07:59:59Z` for end of day on
February 13 in PST. There is a test asserting exactly this value, because
storing `2027-02-13T23:59:59Z` would lock delegates out eight hours early, in
the middle of the last afternoon anyone actually uses.
**Still open:** a submission in flight at the boundary is rejected with no grace
period, losing whatever the delegate had typed. The form submits once rather
than saving continuously, so that is a real loss. Consider accepting a
submission whose session began before the deadline, or warning at T-minus-1-hour.

### A future commissioner moves a deadline into a DST month
**MITIGATED.** The dashboard takes a wall-clock date and computes the UTC
instant using `America/Los_Angeles`, so the offset changes from −8 to −7 on its
own. Nobody hand-types the UTC string. This is the trap `schema.md` calls out
and it is handled in `backend/lib/clock.py`.

### An admin impersonates someone, walks away, and leaves the tab open
**MITIGATED.** Impersonation sessions expire after 30 minutes, are read-only
unless a second explicit toggle is set, show a permanent banner naming both
identities, and never reveal the target's code. Every action inside carries both
identities in the audit log.

---

## Infrastructure

### Turso hits a read quota on Friday afternoon
**MITIGATED by design, verified in CI.** Exceeding the quota returns `BLOCKED`
and the database stops answering; it cannot be resolved by paying. Therefore:
every index is declared in the migration that creates its table; every list view
is a single query with a JOIN; aggregates are never computed live but served
from `school_stats` and `public_stats_cache`, updated in the same transaction as
the mutation; and CI runs `EXPLAIN QUERY PLAN` over every query in
`backend/queries/` and fails on a `SCAN` of any table expected to exceed 200
rows.
An admin page shows current rows read, rows written, and storage from the Turso
platform API, so drift is visible before it becomes an outage.

### Modal redeploys during convention and silently resets the autoscaler to cold
**MITIGATED.** Deploying resets the autoscaler to whatever is written in code,
so a one-shot "keep warm" button would be undone by the first hotfix. Instead
the database is the source of truth: `ops.warm_until` holds a UTC timestamp and
a cron reconciles reality to it every five minutes. It re-applies within five
minutes of any deploy and survives the container dying with a change pending.

### The Apps Script deployment URL changes, or its quota is exhausted
**OPEN.** Re-deploying an Apps Script web app can mint a new URL, and every
export would then fail silently against the old one. Nothing currently alerts on
this.
Needed: the export path must surface a failure to the admin who triggered it
rather than logging and moving on, and the URL belongs in Modal Secrets with a
documented rotation procedure. Quota (~20k UrlFetch/day) is not a realistic
concern at a few hundred calls/day.

### The board meeting venue has no working Wi-Fi
**OPEN — operational, not code.** Warm the container beforehand, rehearse the
full flow against production at least twice, and have a recorded screen capture
as a fallback. A local `dev.db` plus the seed script also runs the whole demo
offline, which is the better fallback because it is interactive. See `RUNBOOK.md`.

### Modal is unreachable
**MITIGATED by design.** The public welcome page renders convention facts and
statistics from a build-time static snapshot immediately, then quietly replaces
them with live values. Every authenticated page shows a clear failure message
naming what to do instead — never an indefinite spinner. The announcement banner
has a second layer in `frontend/public/announcement.json`, editable from the
GitHub web UI, so a banner can be published with Modal completely down.

---

## Data quality

### A name contains a character the parser has never seen
**MITIGATED.** Accented and non-Latin names parse normally and produce **no**
warning — `Seán O'Brien` and `Nguyễn Thị Minh Anh` are ordinary names and
warning about them would be both insulting and the kind of noise that trains
sponsors to ignore warnings. Only control characters and unmatched brackets
trigger `unexpected_character`. Invisible characters (zero-width space, BOM,
soft hyphen) are stripped *and* flagged, because a name containing one looks
correct on screen and then never matches a duplicate check.

### A name is a single word, or 90 characters long
**MITIGATED.** A single token becomes the last name and warns
(`single_token_name`). Long names are stored as-is; there is no length limit in
the schema, and the print template must handle overflow — see below.

### A four-or-more-token name is guessed wrong
**ACCEPTED, by design.** `Nguyễn Thị Minh Anh` parses as first `Nguyễn`, middle
`Thị Minh`, last `Anh`, which is wrong for a Vietnamese name where the surname
comes first. It is flagged `multi_token_name` for confirmation and the preview is
editable inline. There is no rule that gets this right without knowing the name's
origin, so the design is to guess visibly and let the sponsor correct it.

### `Mac` casing
**ACCEPTED, deliberately not handled.** `Mc` is unambiguous and is handled.
`Mac` is a prefix in MacDonald and ordinary letters in Machado, Macias, and
Macy, and no rule separates them. Producing `MacHado` from a correctly typed
name is worse than leaving `Macdonald` for the sponsor to fix, because a wrong
name that looks deliberate never gets corrected. Only fires on uniform-case
lines, which are rare. **Raised as a question; unanswered.**

### A delegate is moved from a middle school chapter to a high school chapter
**RESOLVED — this operation does not exist.** Chapters are completely separate,
and a site sending both middle and high school delegates is already two schools
with two sponsors. There is deliberately **no query** for moving a person
between schools, and `people.sql` says so in place of one. If a sponsor enters
someone under the wrong chapter, they cancel that row and enter them again under
the right one. A move would have to revalidate the Latin level, every test
eligibility, and both schools' invoices — machinery for an operation that
should not happen.

### A sponsor uploads scans to the wrong school's Drive folder
**ACCEPTED — outside this system entirely.** Sponsors upload with their own
Google account to a folder shared manually with the Convention Presidents. No
code in this repository reads that folder; the database holds a URL string.
Nothing here can detect or prevent a misfiled scan, and deliberately so: medical
data for minors should not be reachable by any code we write. The Presidents
audit against Drive at check-in.

---

## Things noticed while building

### Cancelling a delegate can *raise* part of the bill
**ACCEPTED, and surfaced in the UI.** The free-adult allowance is
`ceil(delegates / 10)`, so the 1st, 11th, and 21st delegate each carry a free
adult with them. Cancelling one of those removes the allowance, and the
chapter's bill falls by $140 - $75 = $65 rather than the full $140. Correct, but
a sponsor will ask. The invoice shows the free-adult allowance as its own line
so the arithmetic is visible rather than magic. Pinned in `test_money.py`.

### The check symbol silently detected nothing
**FIXED — caught by an exhaustive test, not by review.** The check symbol is a
position-weighted sum modulo 31, but the first version kept all 32 Crockford
characters. `Z` has value 31 and `0` has value 0, which are congruent modulo 31,
so typing one for the other produced the same check symbol and passed straight
through. Dropping `Z` from the alphabet makes the values 0-30, all distinct
modulo the modulus, and the guarantee exact. `codes.py` now asserts
`len(ALPHABET) == CHECK_MODULUS` at import. Cost: 0.4 bits of entropy across the
whole code.

### Rate limiting counted nothing
**FIXED — caught by a test.** A failed redemption recorded its `login_attempts`
row and then raised; the raise rolled the transaction back, taking the row with
it. The limiter therefore counted zero failures forever while looking entirely
correct. `redeem()` now takes the Database rather than a transaction and commits
the failure in its own transaction *before* raising. Any "record the failure
then fail" path has to take this shape.

### One shared database connection
**FIXED.** The first cut held a single connection on the `Database` object.
Modal serves concurrent requests, so two of them would interleave inside one
transaction and whichever committed first would commit the other's half-finished
work; nested transactions also failed outright. Each transaction now opens its
own handle. A SQLite connection costs microseconds and the Turso client is HTTP.

### Two unclosed function calls in the frontend
**FIXED — caught by a parser, not by reading.** There is no bundler and no Node
toolchain, so nothing catches a JavaScript syntax error until a browser silently
refuses to load the module and the page renders as a blank white rectangle.
`import.js` and `admin.js` each had a `host.append(` that was never closed.
Reviewing the code by eye did not find them; running a real parser over every
module found both in seconds. `test_frontend.py` now does that on every run.

### The site needed a phone from 2021
**FIXED.** The first cut used optional catch binding (`catch {}`, Safari 11.1),
nullish coalescing (`??`, Safari 13.1) and logical assignment (`||=`, Safari
14). All are valid and all are unnecessary here. Delegates arrive on whatever
phone they own, frequently a handed-down one, and each of those features cuts
off a slice of them for no benefit. The code now stays inside what the CI
parser accepts, which doubles as the compatibility floor.

### The "anonymised" export contained a name
**FIXED — caught by testing the claim rather than trusting it.** The redaction
was column-based: it stripped names from `people` and summaries from
`audit_log`, and missed `settings`, where `invoice.remit_to` names the
treasurer. In reality the treasurer is usually also a sponsor on somebody's
roster, so this was a real leak and not a hypothetical one.

Prose is now redacted from the anonymised export as well — `settings` values of
type `string`/`markdown`, `documents.body_md`, `announcements.body_md`, and
`schools.discount_reason`, which is free text an admin types and could name a
family. The numbers survive, which is the part an analysis needs.

The docstring was also narrowed: "anonymised" means *no student, parent, or
volunteer data*, not *no proper nouns at all*. A chapter's own name is data the
export exists to carry.

### The idempotent re-read matched people by timestamp
**FIXED.** A repeated roster commit looked up the people it had created with
`WHERE school_id = ? AND created_at = ?`. Two people created in the same second
are indistinguishable that way, so a re-read could return the entire roster
rather than the eight rows the import made. `people.roster_import_id` now
records which import created each row, with a partial index. It also answers
"where did this row come from?" years later.

### `schools.list` omitted a column its own serializer read
**FIXED.** `_school_public()` reveals `drive_folder_id` to scope `*` and hides
it from everyone else, but `schools.list` never selected the column — so the
admin branch raised `KeyError` and the endpoint returned 500 for exactly the
people who were supposed to see it. Redacting in one serializer is right;
omitting the column in each query is what broke it.

### A sponsor naming another school was quietly given their own
**FIXED.** `_school_of()` originally substituted the caller's own school when a
non-admin named a different one. That is "safe" in the sense that no data
leaked, and wrong in every other sense: it serves a wrong answer as if it were
right, hides the bug or the probe behind a page that looks entirely correct, and
made the wrong-school tests pass without proving anything. It now refuses.

### The PDF renderer cannot be run on Windows
**ACCEPTED, with a workaround.** WeasyPrint needs Pango and Cairo, which do not
install on Windows without GTK — and both commissioners develop on Windows. The
PDF builds correctly on Modal's Debian image, from the same HTML.

`backend/workers/pdf.py --html` writes the HTML instead, so a layout change can
be checked locally without any of that. The build order also puts the PDF
renderer first on the list of things to cut, and the print view — which is the
same document — is what actually matters.

### `%-d` and `%-I` in date formatting
**FIXED.** They are a glibc extension: they work on Modal and raise `ValueError`
on Windows, where both commissioners develop. A formatter that works in
production and crashes on your laptop is worse than one that is slightly tedious
to read, so `render_local()` builds the string by hand.

### The roster query can double-count a person
**MITIGATED.** The roster JOIN matches medical forms with
`form_type IN ('student_medical','adult_medical')`. If a person ever held both
rows, the LEFT JOIN would return them twice and the sponsor's own roster would
show a phantom attendee. `paper_forms.form_type` is constrained so a delegate
cannot acquire an `adult_medical` row. Not in the original schema; added.

### Admin accounts have no chapter
**MITIGATED.** `people.school_id` is `NOT NULL`, so the four state-board admins
must belong to some school. Attaching them to a real chapter would inflate that
chapter's adult count, its invoice, and the public statistics. `schools.kind`
separates chapters from organizations; organizations are excluded from public
stats, the chair dashboard, and all invoicing — by flag, never by name. Not in
the original schema; added after asking.

### Dead `ON DELETE CASCADE` clauses
**ACCEPTED.** Several tables cascade from `people`, but nothing in `people` is
ever hard-deleted, so those clauses can never fire. Harmless, and worth keeping
as documentation of intent — but do not read them as permission to hard-delete.

### `argon2-cffi` is listed as a dependency and never used
**MITIGATED.** Removed from the slim image. Codes are HMAC-peppered and session
tokens are plain SHA-256; there is no password anywhere in the system. A slow
KDF would also turn login from an indexed lookup into a full scan, which on
Turso is billed per row.

### Windows console encoding breaks any script that prints Latin text
**MITIGATED.** The default Windows codepage is cp1252 and printing a macron
raises `UnicodeEncodeError`, which looks exactly like a test failure and is not
one. Both commissioners are on Windows. The test bootstrap reconfigures stdout
and stderr to UTF-8; any new standalone script must do the same.

### WeasyPrint does not support the full CSS grid
**OPEN.** `design.md` specifies a 12-column grid, and the print templates are
rendered by WeasyPrint to produce the PDF. Print layouts must therefore use
flow, tables, and simple flex rather than grid, or the PDF and the browser print
view will disagree — which defeats the entire point of having one template.
Print stylesheets are written accordingly; verify by diffing the two outputs
before convention.

### A credential pasted by hand carries an invisible line break
**MITIGATED.** A Turso auth token is several hundred characters long and wraps
across several lines in a terminal. Copying it by hand brings the wrap along,
and the token then travels in an `Authorization` header, where a newline is
illegal. The driver reports this as
`Hrana: http error: http::Error(InvalidHeaderValue)` — which names neither the
setting nor the character, arrives before any SQL runs, and looks for all the
world like a network fault. It cost an evening of the demo build.

`db.py` now trims surrounding whitespace from `TURSO_DATABASE_URL` and
`TURSO_AUTH_TOKEN` and refuses an interior control character by name, without
echoing the value into the logs. `DEPLOY.md` sets both from command
substitution rather than a paste, and `modal run backend/app.py::doctor`
reports the shape of every setting and attempts the connection. The underlying
hazard is not fixed and cannot be: a commissioner setting the secret through
the Modal web dashboard can still introduce one, and will now at least be told
which value and which character.

### A very long name overflowing the tabula on the printed sheet
**OPEN.** Not yet tested against the 90-character fixture. The credential block
uses `break-inside: avoid`, so an overflowing name would push rather than split,
but the layout has not been checked.

---

## Measured, not assumed

`docs/stack.md` projected the free-tier headroom with arithmetic done in
advance. Running `scripts/measure_usage.py` against a real seeded database and
extrapolating to 50 chapters, 1,000 delegates and 150 adults gives:

| | stack.md projected | Measured projection | Free tier |
|---|---|---|---|
| Storage | ~25 MB | **2.2 MB** | 5 GB |
| Reads, normal month | ~3 M | **434,000** | 500 M |
| Reads, convention month | ~12 M | **1.7 M** | 500 M |

The original estimate was conservative by roughly 7–11×, which is the right
direction to be wrong in. Every page load is an indexed lookup: the public
welcome page costs **one** row read, an authenticated request costs three, and a
thirty-person roster costs about thirty-four. Nothing scans.

The margin is not the reason this is safe, though — the CI plan check is. A
single unindexed list view would put a five-figure multiplier on one of those
rows, and 288× headroom disappears quickly at 100,000 reads a page.

### `node.append(x)` renders the word "null" when x is null
**MITIGATED.** The DOM's own `append` stringifies whatever it is handed, so the
ordinary way to write a conditional child —

```js
host.append(error ? errorSummary(error) : null, field({...}))
```

— puts a text node reading `null` on the page whenever there is no error. It
survives every review that reads the markup, because the markup is correct;
only the rendered page is wrong. It shipped above roughly half the headings on
the site and above the sign-in field, and was found by a person looking at the
live site rather than by any test.

`ui.js` now exports `add(node, ...children)`, which filters null, undefined and
false exactly as `el()` always did, and `test_frontend.py` fails on any
`.append(` outside `ui.js`.

### The welcome page went blank the moment JavaScript loaded
**FIXED.** Two files disagreed about who owned the markup. `index.html` carries
the welcome page so a cold visitor sees a finished page with no request made;
`welcome.js` was written on the assumption that the router left it alone, and
said so in a comment. The router cleared `#app` before every render, including
that one. `welcomePage` then found no `#stats`, returned early, and left an
empty page — while the local file:// preview, where the module never loaded at
all, looked perfect.

`main.js` now lifts those children into a fragment at boot, before anything can
clear them, and hands `welcomePage` a clone. `index.html` stays the one source
of truth.

The general lesson is the one worth keeping: a comment asserting what another
file does is not a mechanism. It was accurate when written.

### A dependency that is only present by accident
**MITIGATED.** `zoneinfo` reads the operating system's time-zone database.
Linux and macOS ship one; Windows does not. Nothing in this project declared
`tzdata`, and the whole test suite passed on a Windows machine for weeks —
because pandas, installed for something unrelated, had pulled it in. The first
clean virtual environment failed at `import clock`, before a line of the
application ran, with twenty frames of importlib naming neither cause nor fix.

`tzdata` is now declared in `backend/requirements.txt` and in both Modal
images, deliberately **without** a platform marker: a marker would leave the
Linux side depending on whatever the base image happens to ship, which is the
same bug wearing a different hat. `clock.py` raises a RuntimeError naming the
fix. A test asserts the dependency is declared and unmarked.

The general shape is worth remembering: **a green test suite proves the code
works in the environment it ran in.** Anything the environment supplies by
accident is invisible until somebody starts clean.

### The local half of a Modal entrypoint needed the whole backend
**MITIGATED.** `modal run backend/app.py::board` reads `board.json` on your own
machine and does the database work in the container. `scripts/add_board.py`
imported `backend.lib` at module level, so the local half needed a working
backend environment — time-zone data, the Turso driver — to read a JSON file.
On Windows it failed before opening it.

The backend imports now live inside the functions that use them. `load()` and
`report()` are pure text handling and import nothing, which is checked by a
test that runs a subprocess and asserts no `backend.*` module was loaded.

### A pragma the hosted database will not run
**MITIGATED.** `PRAGMA busy_timeout` was added to the remote connection to
match the local one, on the reasoning that lock contention is a hosted
database's problem rather than a laptop's. The reasoning was right and the
mechanism was wrong: Turso allows a short list of pragmas and refuses the rest
outright, and because pragmas run at CONNECTION time a refused one took down
every request rather than one query. It shipped and broke production.

The wait now happens in Python — `_run_with_retry` in `db.py` — which needs
nobody's permission. `test_source.py` asserts the remote path sends only
`foreign_keys`, and that test was verified by reintroducing the bug and
watching it fail.

The general shape: **a local file is opened, a hosted database is asked.**
Anything that configures the connection has to be checked against what the
server will actually accept, and there is no way to learn that from a local
SQLite file.

### A file no test ever loaded
**MITIGATED.** `backend/app.py` imports `modal` at module level, so nothing in
the suite ever imported it — and a broken string literal in it therefore
reached the person trying to run `modal run`, as a `SyntaxError` at import.
Every other file is imported by some test; this one and the standalone scripts
were not.

`test_source.py` now **compiles** every Python file in the repository. Parsing
needs no dependencies, no credentials and no network, so it covers exactly the
files that nothing else touches: `app.py`, `scripts/`, `workers/`. Verified by
reintroducing the bug.

**A related trap, worth naming.** The two checks above were first written
inside `test_db_drivers.py`, which opens with `pytest.importorskip("libsql")`.
That driver has no ARM wheel, so the whole module — and both new checks — was
silently skipped on precisely the machines that needed it. A test that does not
run is not a test. Source-level checks live in their own module, which imports
nothing.

### The seed file promised something that was not true
**MITIGATED.** `scripts/seed.py` opens by saying every name in it is
fabricated and that no real student, parent, teacher or school appears. Three
real people were in it — two commissioners and the host chapter's sponsor, who
narrated half the seeded audit log — and the repository is public.

They are gone, replaced with invented names, and `test_source.py` now fails if
any of them comes back. The list of names to refuse is in that test; add to it
when somebody real joins.

**Two places still carry a real name, both deliberately.** The
`invoice.remit_to` setting is whose name a chapter writes on a cheque: a
business fact printed on a real invoice, specified in `structure.md`, and
editable from Settings. `docs/TODO.md` says who is meant to do what, which is
what that file is for. Neither is demonstration data.

**Why a docstring was not enough.** It described an intention, and intentions
do not survive somebody adding themselves to a list of administrators at
eleven at night. The check that matters is the one that runs.

### Editing a migration that has already run
**MITIGATED.** `migrate.py` has always refused to start when an applied
migration's contents change — it compares each file against the sha256 recorded
in `schema_migrations` when that file ran. The check is correct and it is the
one that protects the data.

But it lives in the **deployed database**, so it fires in CI, against
production, after a push. A one-word change to an illustrative comment in
`003_money_audit.sql` — not a statement, a comment — stopped a deploy that way.

`backend/migrations/CHECKSUMS.txt` now records the same hashes in the
repository, and `test_source.py` fails if a file no longer matches. The answer
becomes `git checkout` before the commit rather than a failed deploy after it.
`scripts/checksum_migrations.py` regenerates the manifest, refuses to do so
quietly when an applied file has changed, and is run only when ADDING a
migration.

### Two sponsors from one school edit the roster simultaneously
**MITIGATED.** Previously PARTIAL, and this was the oldest open entry here.

The idempotency key bound the school, a hash of the pasted text, and a
five-minute freshness window — so nobody could review one list and commit
another. It said nothing about the roster those names were checked *against*.
Two sponsors pasting the same twenty students at the same time both previewed
against an empty roster, both saw no duplicates, and both committed. The
chapter ended up with forty.

The key now also carries a fingerprint of the roster the preview was reviewed
against, and a commit whose fingerprint no longer matches is refused with a
message saying so. Keys issued before this existed carry no fingerprint and are
accepted: a preview open across a deploy is a worse failure than a race that
needs two sponsors acting inside five minutes.

**The order of the two checks is load-bearing.** The idempotency lookup runs
first, because the first press of a double-click is itself what changes the
roster — checked the other way round, the second press is rejected as
"somebody else changed this roster", which is true, and is the same person half
a second earlier. Both directions are tested.
