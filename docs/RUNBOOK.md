# Runbook

How to run and repair this system.

This is written for someone who did not build it. You do not need to have seen
the code before, and you do not need to be an experienced programmer. Where
something is genuinely hard, it says so.

**If the site is broken right now, skip to [When something is broken](#when-something-is-broken).** Everything else can wait.

---

## Contents

1. [What this system is, in plain terms](#1-what-this-system-is-in-plain-terms)
2. [How the repository is laid out](#2-how-the-repository-is-laid-out)
3. [Setting up your computer](#3-setting-up-your-computer)
   - [Working with the real database from an ARM machine](#working-with-the-real-database-from-an-arm-machine)
4. [Running it on your own machine](#4-running-it-on-your-own-machine)
5. [The everyday jobs](#5-the-everyday-jobs)
6. [Deploying a change](#6-deploying-a-change)
7. [Secrets, and what breaks if you change one](#7-secrets-and-what-breaks-if-you-change-one)
8. [Keeping the site fast for an event](#8-keeping-the-site-fast-for-an-event)
9. [Backups, exports, and restoring](#9-backups-exports-and-restoring)
10. [Adding a chair and giving them access](#10-adding-a-chair-and-giving-them-access)
11. [Watching the database quota](#11-watching-the-database-quota)
12. [When something is broken](#12-when-something-is-broken)
13. [Things that will catch you out](#13-things-that-will-catch-you-out)

---

## 1. What this system is, in plain terms

Four separate services. Only one of them holds anything you would be sad to
lose.

**GitHub Pages** serves the website itself — the HTML, the CSS, the JavaScript,
the fonts. It is free, it is just files, and it essentially cannot break. If
someone visits the site and sees *anything at all*, this part is working.

**Modal** runs the program that does the thinking. Every question the website
asks — who is this person, what is on their roster, how much do they owe — goes
to Modal. Modal is the only thing allowed to talk to the database.

Modal *sleeps when nobody is using it*, which is what keeps it free. Waking up
takes a few seconds. That is normal and the site is designed to say so politely
rather than appearing frozen.

**Turso** is the database. It stores every school, person, form, and payment.
Turso is a hosted version of SQLite, which matters more than it sounds: every
backup this system produces is an ordinary SQLite file that you can open in a
free program called DB Browser, or load into a Google Colab notebook, without
any special tools.

**Google Apps Script** is a small helper that writes files into the Google
Drive. It exists only because nothing else can act as his Google identity. It is
**not needed to run registration** and can be ignored until pre-convention contests are
built.

### How a single click travels

Someone clicks "Roster" on the website.

1. Their browser already has the page (from GitHub Pages) and runs a little
   JavaScript.
2. That JavaScript sends a request to Modal, carrying a session token that says
   who they are.
3. Modal checks the token, works out what that person is allowed to see, and
   asks Turso one question.
4. Turso answers. Modal turns it into JSON and sends it back.
5. The browser draws the table.

The browser never talks to Turso and never holds a database password. That is
deliberate: the website's code is public, so anything the browser knows is
public too.

---

## 2. How the repository is laid out

Six top-level folders. Here is what each is for and when you would open it.

```
frontend/     the website people see
backend/      the program that does the thinking
scripts/      one-off tools you run by hand
docs/         these documents
apps-script/  the Google Drive helper (not needed yet)
.github/      instructions for the robots that deploy things
```

### `frontend/` — the website

Plain HTML, CSS and JavaScript. There is **no build step**: the files in
`frontend/public/` are exactly what a browser downloads. You can edit one, save
it, and refresh. Nothing to compile, nothing to install.

| File | What it is |
|---|---|
| `index.html` | The page shell. Everything else is drawn into it. |
| `tokens.css` | **Every colour, font and spacing size in the entire site.** |
| `app.css` | How things look — buttons, tables, forms. |
| `js/main.js` | Decides which page to show, handles signing in and out. |
| `js/api.js` | Every request to Modal, and the "waking up the server" message. |
| `js/ui.js` | Small helpers for building the page. |
| `js/pages/` | One file per screen: `roster.js`, `invoice.js`, and so on. |
| `fonts/` | The three typefaces, stored here so no outside service is needed. |

**If you want to change how the site looks, start with `tokens.css`.** Change
the colours there and the whole site changes. That file exists so the next
commissioners can re-skin the site for their own school in an afternoon.

### `backend/` — the program

| Path | What it is |
|---|---|
| `api.py` | Every web address the site can call, and who is allowed to call it. |
| `app.py` | The small file that tells Modal how to run everything else. |
| `lib/` | The actual logic, one file per topic. |
| `queries/` | **Every database question this system asks**, as plain `.sql` files. |
| `migrations/` | The database's structure, as numbered steps. |
| `workers/` | Slow jobs (PDFs, exports) that run separately. |
| `tests/` | Around 420 automated checks. |

Inside `lib/`, the files are named after what they handle:

| File | What it handles |
|---|---|
| `db.py` | Talking to the database, and transactions. |
| `auth.py` | Signing in, sessions, and who may do what. |
| `codes.py` | Making and checking access codes. |
| `names.py` | Reading a pasted roster into first/middle/last names. |
| `roster.py` | Adding, cancelling, and restoring people. |
| `forms.py` | The activity sheet and the adult sheet. |
| `catalog.py` | The list of tests and activities, and who may enter each. |
| `stats.py` | The counters, and the invoice arithmetic. |
| `printing.py` | The printed packet and invoice. |
| `settings.py` | The values an admin can change from the dashboard. |
| `clock.py` | Dates and times, and the deadline rules. |
| `queries.py` | Loading the `.sql` files. |
| `migrate.py` | Running the migrations. |

**Two folders are worth knowing about even if you never open `lib/`.**

`backend/queries/` holds every single question this system asks the database, in
readable SQL, each one with a comment explaining why it is written that way. If
you want to understand what the system actually does, this folder is the
shortest path. Nothing anywhere else builds a database query — that rule exists
so an automated check can inspect all of them.

`backend/migrations/` holds the database structure as numbered steps
(`001_core.sql`, `002_forms_catalog.sql`, and so on). They run in order, once
each. **Never edit one that has already run** — write a new one instead. The
system refuses to start if it notices an old migration has changed, because at
that point the database and the code no longer agree and guessing which is right
would be worse than stopping.

### `scripts/` — tools you run by hand

| Script | What it does |
|---|---|
| `seed.py` | Fills the database with invented sample data. |
| `build_fonts.py` | Downloads and trims the fonts; fails if the theme cannot render. |
| `build_snapshot.py` | Bakes the current numbers into the welcome page. |
| `check_query_plans.py` | Checks no database question is accidentally slow. |
| `measure_usage.py` | Estimates how much of the free tier is being used. |
| `build_favicon.py` | Rebuilds the browser-tab icons from `img/logo.webp`. Run it when the logo changes. Needs Pillow. |
| `add_board.py` | Gives real board members accounts. Reads `board.json`, which is gitignored so no real name reaches the repository. |

---

## 3. Setting up your computer

### Which terminal?

**Whichever one you already use, and only one copy of the repository.** On
Windows that is PowerShell or the VS Code terminal; on macOS or Linux, your
usual terminal. Everything in this project runs natively on all three.

The tempting mistake on Windows is to keep a second copy of the repository
inside WSL — the Linux environment that ships with Windows — on the grounds
that Modal runs on Linux. It costs more than it gives. Two copies drift apart
within a day: you edit one, run a script in the other, and lose an afternoon
working out why the two disagree.

Nothing here needs Linux:

- The test suite passes on Windows.
- `scripts/build_fonts.py` and `scripts/build_snapshot.py` are plain Python.
- The Modal command line tool has a Windows version.
- WeasyPrint, which is the awkward one to install, is never installed locally.
  It lives in `backend/requirements-worker.txt` and runs only inside Modal's
  own image. See section 2 for what that image is.

The single exception is Turso's command line tool, which is published for macOS
and Linux only. On Windows, run those few commands in WSL — they ask Turso
about your account and never touch your files, so it does not matter which
folder you are in. Turso's website can do the same jobs if you would rather not
use WSL at all.

**If you have ended up with two copies**, keep the one your editor opens, and
delete the other. Nothing is stored in the working folder that is not either in
Git or recoverable: `.venv` is rebuilt with one command, and `~/.modal.toml` is
recreated by `modal setup`.

### Python and the virtual environment

A **virtual environment** is a private folder of Python packages belonging to
this project alone, so that installing something here cannot break something
else on your computer. Some systems — Ubuntu among them — refuse to let `pip`
install anything without one, which is a deliberate safety feature rather than
a mistake on your part.

Keep it *inside the project*, not in your home folder, so it is obvious what it
belongs to.

Windows, in PowerShell:

```powershell
cd path\to\CAJCL-2027
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
pip install pytest httpx esprima fonttools brotli modal
```

macOS or Linux:

```bash
cd path/to/CAJCL-2027
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install pytest httpx esprima fonttools brotli modal
```

You must run the activate line **each time you open a new terminal**. You will
know it worked because your prompt gains a `(.venv)` prefix. If a command
suddenly reports that a package is missing, that is almost always the reason.

If PowerShell refuses to run the activate script and mentions an execution
policy, allow local scripts once, for your account only. It changes nothing for
other users and turns off no other protection:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

On a school-managed machine you may not be allowed to. You do not need to be:
skip activation and call the environment's Python by path instead, which needs
no permission at all.

```powershell
.venv\Scripts\python.exe -m pytest backend/tests
```

Watch the folder in your prompt, too. A `.venv` created before you `cd` into
the project lands in your home folder and belongs to nothing.

`.venv` is already in `.gitignore`, so it will not be committed.

### Working with the real database from an ARM machine

Skip this unless `pip install` fails with a wall of Rust output ending in
**`is cmake not installed?`**

The driver that talks to hosted Turso is called `libsql`. It ships ready-built
for x86_64 Linux, both kinds of Mac, and x86_64 Windows — but for **no ARM
platform except Apple silicon**. If your laptop has a Snapdragon or similar ARM
chip, that rules out both Windows itself and WSL on it, so pip tries to compile
the driver from Rust source instead. That needs cmake and a full toolchain,
takes about ten minutes, and often fails anyway.

To find out which you have:

```bash
python -c "import platform, sys; print(platform.machine(), sys.platform)"
```

`ARM64 win32` or `aarch64 linux` means this section applies to you.

**You almost certainly do not need it.** Local work uses a plain file and the
`sqlite3` module that comes with Python. The driver is only needed to reach the
*hosted* database, and there is a better way to do that:

```bash
modal run backend/app.py::doctor           # check the settings and connect
modal run backend/app.py::setup            # migrate, then seed
modal run backend/app.py::setup --reset    # wipe first, then rebuild
modal run backend/app.py::setup --no-seed  # migrate only, leave data alone
```

That runs on Modal, whose machines are x86_64, so the driver is simply there.
The access codes come back to your terminal and are written to
`codes.txt` on your own machine, exactly as if you had run it locally.

This is better practice anyway: the migration runs in the same environment as
the code that will use it.

`backend/requirements.txt` already skips the driver on both ARM platforms that
lack a wheel, so a plain `pip install -r backend/requirements.txt` works there.
If you genuinely want direct access from an ARM machine, install cmake and a
Rust toolchain — on WSL, `sudo apt install cmake build-essential` — then
`pip install libsql`. Try the Modal route first.

---

## 4. Running it on your own machine

Two terminals, both with the virtual environment active.

**Terminal one — the program:**

```bash
export CODE_PEPPER="anything-at-all-for-local-work"
python scripts/seed.py --db dev.db --reset
uvicorn backend.api:app --reload --port 8000
```

**Terminal two — the website:**

```bash
python -m http.server 8080 --directory frontend/public
```

Open <http://localhost:8080>.

The seed prints the access codes you need and writes them to `codes.txt`.
They are freshly generated every time you seed, so an old copy will not work.

Run the automated checks with:

```bash
python -m pytest backend/tests -q
```

They take about a minute. If they all pass, the system is behaving.

---

## 5. The everyday jobs

None of these require touching code or deploying anything.

| I need to… | Where |
|---|---|
| Change a fee, deadline, address, or the theme | Settings → Values |
| Reword something that gets printed | Settings → Printed wording |
| Put a notice on every page | Settings → Announcements |
| Add a chapter | Chapters → Add a chapter |
| Create a sponsor account | Chapters → the chapter → Add sponsor |
| Record a payment | Chapters → Payment, on that row |
| Download a backup | Settings → Operations → Export |
| Keep the site awake for an event | Settings → Operations → Keep warm |
| See what happened and who did it | Log |

That list is the point of the whole design. Running a convention should never
require a programmer.

---

## 5b. Making a change stick

**Start here before changing anything.** Most of what people want to change is
not code, and the ones that are code have one rule that matters.

### Which kind of change is this?

| You want to change | Where | Deploy? |
| --- | --- | --- |
| Fees, deadlines, convention dates, venue, theme, ordinal | **Settings → Values** | No |
| Any printed or displayed wording | **Settings → Printed wording** | No |
| A banner on every page | **Settings → Announcements** | No |
| Who holds which role | **Settings → Roles** | No |
| Whether the site stays warm | **Settings → Operations** | No |
| A new person on the board | `board.json`, then `modal run backend/app.py::board` | No |
| Colours, fonts, page layout | `frontend/public/tokens.css` and `app.css` | Yes |
| What a page says or does | the code | Yes |
| A new table, column or index | a **new** migration | Yes |
| The default data a future convention starts from | a **new** migration | Yes |

The first six rows are the point of this system. If you find yourself editing
code to change a fee or a sentence, stop — that is a bug in the dashboard, and
worth fixing there instead.

### The one rule about migrations

**Never edit a migration that has already run. Not a statement, not a comment,
not a space.**

A migration is a record of what was done to a database that exists. Changing
the file makes that record a lie, and the deploy will refuse to start:

```
005_seed_roles_settings.sql has already been applied but its contents
have changed.
```

The hash covers the whole file, so correcting a typo in a comment breaks it
exactly as thoroughly as rewriting a table would. This has happened twice here,
both times over wording.

**What to do instead**, whether you are fixing a typo or adding a column:

1. `git checkout backend/migrations/00N_whatever.sql` — put it back.
2. Write a new file: `011_says_what_it_does.sql`. The number is the next one up.
3. Express the change as something that runs against a database that already
   exists — `ALTER TABLE`, `CREATE INDEX IF NOT EXISTS`, an `UPDATE` with a
   `WHERE` narrow enough not to clobber anybody's edits.
4. `python scripts/checksum_migrations.py` and commit the manifest with it.
5. `python -m pytest backend/tests` — this is caught locally now, not in CI.

### The exception, and it is one exception

**Between conventions, when the database is going to be rebuilt anyway, the
migrations can be rewritten.** Corrections were accumulating as new files — a
comment here, a wording change there — until seventeen migrations described a
schema that six could have. Folding them back in is the right move at that
moment and nowhere else.

```
python scripts/checksum_migrations.py --accept
modal run backend/app.py::setup --reset
```

The first refuses without `--accept` and tells you the flag exists. The second
**wipes before it migrates**, which is what makes this recoverable: a database
holding migrations that no longer exist cannot be migrated at all, so the reset
has to drop the tables before the hash check ever runs.

**Both commands, in that order, or the site is down.** After `--accept` the
deployed database has run files that are gone; until it is reset, every deploy
refuses to start with:

```
001_core.sql has already been applied but its contents have changed.
```

If you see that after a consolidation, you have not run the reset yet. That is
the whole diagnosis.

### Why the checksum exists at all

Because the alternative is silent. Two databases that ran different versions of
"the same" migration have different schemas and no way to tell. Refusing to
start is the only safe response, and the deploy log says which file and why.

`backend/migrations/CHECKSUMS.txt` brings the same check to your laptop, so the
answer is `git checkout` before the commit rather than a failed deploy after
it. `scripts/checksum_migrations.py` maintains it and refuses to record a file
that has drifted since git first saw it.

---

## 6. Deploying a change

Push to `main`. A robot (GitHub Actions) runs the tests, updates the database
structure, deploys Modal, and republishes the website.

To do it by hand:

```bash
source .venv/bin/activate
modal deploy backend/app.py
```

### Updating the database structure

```bash
python -m backend.lib.migrate --db dev.db     # your own machine

export TURSO_DATABASE_URL="libsql://..."      # the real one
export TURSO_AUTH_TOKEN="..."
python -m backend.lib.migrate
```

Migrations only ever go forwards. There is no "undo migration", on purpose: an
undo script is something you write once, never test, and then run for the first
time at the worst possible moment. If a migration was wrong, write another one
that fixes it.

### One thing to know about deploying

Deploying **resets the "keep awake" setting** to whatever is written in the code.
That is why the awake-setting lives in the database and a background job
re-applies it every five minutes. A quick fix during convention will not
accidentally put the site back to sleep.

---

## 7. Secrets, and what breaks if you change one

Secrets live in **Modal Secrets** and in **GitHub Actions secrets**. Never in
the repository, never in the website's files.

| Secret | What it is | If you change it |
|---|---|---|
| `CODE_PEPPER` | Scrambles every access code | **Nobody can sign in, ever again.** See below. |
| `TURSO_DATABASE_URL` | Which database to use | Nothing, if the new one has the same data |
| `TURSO_AUTH_TOKEN` | Permission to use it | The site errors until you update it |
| `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` | Lets the robot deploy | Deploys fail |
| `APPS_SCRIPT_URL` / `APPS_SCRIPT_KEY` | The Drive helper | Not used yet |

### Viewing and updating a secret

You **can** read a Modal secret back — open the Modal dashboard, go to Secrets,
and click into `cajcl-2027`. But do not rely on that as your only copy.

To change one after it already exists, `modal secret create` will refuse. Use:

```bash
modal secret create cajcl-2027 KEY="value" ... --force
```

`--force` replaces the whole secret, so you must pass **every** key again, not
just the one you are changing. Have them all in front of you first.

### `CODE_PEPPER` — read this before touching it

Every access code is stored scrambled, using this value as the scrambling key.
The plain codes are never stored anywhere.

Change the pepper and every stored code becomes unreadable. Nobody can sign in.
There is no recovery — that is the entire point of doing it this way, because it
means a stolen copy of the database is useless on its own.

If you ever genuinely have to change it, you must also regenerate every person's
code and **reprint and redistribute every packet**.

**Keep a copy in a password manager the day you create it.**

---

## 8. Keeping the site fast for an event

**Settings → Operations → Keep warm for N hours.**

Modal sleeps when idle. The first visitor after a quiet period waits a few
seconds. Before a board meeting or convention, set this for the length of the
event plus a couple of hours. It costs a few cents.

The setting lives in the database, and a background job checks it every five
minutes, so it survives deploys and restarts.

---

## 9. Backups, exports, and restoring

**Settings → Operations → Export**, or from a terminal:

```bash
python backend/workers/export.py --db cajcl.db --out ./exports
```

You get four files: a spreadsheet and a database dump, each in a **full** version
and an **anonymised** version.

The anonymised files have every attendee's name, guardian, email, phone and
free-text note removed — genuinely removed, not hidden. Those are the ones you
can safely send to someone helping out, or paste into an AI tool. They still
contain chapter names and the convention's own settings, which are public
anyway.

### Restoring

```bash
sqlite3 restored.db < exports/cajcl-20270312-1430-full.sql
```

That gives you a working database file. Both the full and anonymised dumps
restore; there is an automated test that proves it.

**A backup is the last resort, not the first.** If Modal breaks, restart it and
fix the problem. Backups are for the case where the *database itself* was
destroyed. Then: restore the most recent export, and reconstruct what happened
since from the activity log, which can never be edited or deleted and therefore
records the whole sequence.

### Running a backup tool without this project

Every tool in `workers/` is a standalone file. Given a `.db` file it runs
anywhere — including a free Google Colab notebook, with no setup:

```python
!pip install openpyxl
# upload cajcl.db and export.py, then:
!python export.py --db cajcl.db --out ./exports
```

**Try this once before convention, for real.** Do not assume it works.

`--db` can also be given as the `EXPORT_DB_PATH` environment variable, which is
what you want when the file is somewhere long and awkward, or when you are
running the exporter repeatedly. With neither, the exporter copies the live
Turso database to a local file first and works on that — which is what happens
on Modal, and the reason the Colab run and the production run take exactly the
same path through the code.

---

## 10. Adding a chair and giving them access

1. Create their account. If they belong to a chapter, add them there; otherwise
   they go on the state board row.
2. **Settings → Roles.** If no existing role fits, create one.
3. Grant it to their account.

Permissions only ever arrive through a role. There is no way to give one person
a special permission directly, and there should never be one — every security
check in the system assumes this.

| Permission | What it opens |
|---|---|
| `*` | Everything: the log, exports, roles, viewing-as, Drive links |
| `registration` | Rosters, chapters, payments, check-in |
| `academics` | Tests and activities, contests, grading, Certamen |
| `awards` | Scores, test printing, tabulation |
| `sponsor` | One chapter's roster — always their own |
| `delegate` | Their own activity sheet |
| `chapter` | Team entries for their own chapter |

The first four work across every chapter. The last three are **always** limited
to the person's own chapter, and nothing can change that.

Granting or removing a role signs that person out everywhere, because their
open sessions still carry their old permissions.

---

## 11. Watching the database quota

**Settings → Operations** shows how much of Turso's free tier is used. (It shows
a message instead of numbers unless the three optional Turso platform values are
configured; the Turso dashboard always works.)

Measured and projected to a full-size convention — 50 chapters, 1,000 delegates:

| | Projected | Free limit | Room to spare |
|---|---|---|---|
| Storage | 2.2 MB | 5 GB | 2,200× |
| Reads, ordinary month | 434,000 | 500,000,000 | 1,150× |
| Reads, convention month | 1.7 M | 500,000,000 | 288× |

**Why this matters more than it looks.** Turso counts every row it has to *look
at*, not every row it returns. Go over the monthly limit and the database stops
answering entirely — and you cannot pay to fix it. One badly-written question
asked on a busy page could use the whole month's allowance in a week.

That is why an automated check inspects every question in `backend/queries/` and
fails the build if any of them would have to scan a large table. If usage
suddenly climbs, run:

```bash
python scripts/check_query_plans.py
```

### Can we just rotate to a new database to reset the counter?

**No, and it is worth understanding why not** — because it is the obvious move
and it does not work.

A new database is an EMPTY database. Pointing the site at one does not carry
the registration across; it throws it away. Getting the data over means an
export and an import, during which the site is answering from neither. That is
a disaster-recovery procedure, not a way to buy quota.

**And the read limit is a plan limit, not a per-database one.** Creating a
second database under the same organisation divides the same allowance rather
than doubling it. If you ever need to confirm the current figure, the Turso
dashboard states it per plan.

**What actually protects the allowance** is that nothing here can scan. Every
question lives in `backend/queries/`, every one has its plan checked by CI, and
the public welcome page costs a single row read because its numbers are baked
into the page at build time. A flood of anonymous traffic hits Modal's compute,
not Turso's read counter.

If you are genuinely under attack: take the site off the internet by removing
the custom domain from GitHub Pages, or set `min_containers=0` and let Modal's
own limits absorb it. Neither loses data.

### What the staging database is for

`docs/DEPLOY.md` step 1 has you create `cajcl-2027-staging` and then never
mentions it again. Here is where it goes.

It is for trying something that could destroy data — a migration you are unsure
of, a bulk edit, a script written at midnight — against a copy, so that finding
out you were wrong costs nothing:

```bash
turso db shell cajcl-2027 ".dump" > snapshot.sql       # from WSL
turso db shell cajcl-2027-staging < snapshot.sql
```

Then point a **local** run at it and do the dangerous thing:

```powershell
$env:TURSO_DATABASE_URL = "libsql://cajcl-2027-staging-<org>.turso.io"
$env:TURSO_AUTH_TOKEN   = "<a token for the staging database>"
python -m backend.lib.migrate
```

**Never point the deployed app at staging.** The Modal secret holds the
production URL and should keep holding it; staging is reached by setting those
two variables in one terminal, for one command, and then closing it.

Empty it and re-dump whenever you need it. It costs nothing, and a stale copy
is worse than none because it invites conclusions about data that has moved on.

---

## 12. When something is broken

### The page loads but says the server is not responding

Modal is asleep, or crashed.

1. Open the Modal dashboard and look at the `cajcl-2027` app.
2. If a function is erroring, read its logs — the error is usually the last line.
3. Redeploy: `modal deploy backend/app.py`.
4. Set **Keep warm** so it does not sleep again while you work.

The public welcome page keeps working the whole time, because its numbers are
baked into the page itself.

### Every page shows a database error

Start here, which reports the shape of every setting in the Modal secret
without printing any of them in full, and then tries the connection for real:

```bash
modal run backend/app.py::doctor
```

If the settings look right, look at Turso.

- If it says **BLOCKED**, a monthly limit is exhausted. See section 11.
- If it cannot connect, `TURSO_AUTH_TOKEN` may have expired. Make a new one.

### `Hrana: http error: http::Error(InvalidHeaderValue)`

The authentication token contains a character that cannot be sent over the
network. The token travels in an HTTP header, and a header may hold only
ordinary printable characters — so a single line break inside the token makes
the request impossible to build, which is why this appears before any SQL runs
and looks nothing like a configuration problem.

It happens when a token several hundred characters long wraps across two lines
in the terminal and the wrap is copied along with it. Set the values without
pasting anything, then replace the whole secret:

```bash
export TURSO_DATABASE_URL="$(turso db show cajcl-2027 --url)"
export TURSO_AUTH_TOKEN="$(turso db tokens create cajcl-2027)"
```

Then re-create the Modal secret with `--force`, as in `docs/DEPLOY.md` step 2,
and confirm with `modal run backend/app.py::doctor`.

A newline at the *end* of a value is trimmed automatically and causes no
trouble. Only one in the middle is fatal.

### `WSServerHandshakeError: 400` when connecting to Turso

The wrong database driver is installed. The correct one is **`libsql`**. An
older package called `libsql-client` was abandoned in June 2025 and current
Turso servers reject it — confusingly, *before* running any SQL, and while the
Turso command-line tool connects to the same database perfectly happily.

```bash
pip uninstall libsql-client
pip install libsql
```

### `ZoneInfoNotFoundError: No time zone found with key America/Los_Angeles`

The time-zone database is missing. `zoneinfo` reads the operating system's
copy; Linux and macOS ship one and **Windows does not**.

```powershell
pip install -r backend/requirements.txt
```

`tzdata` is declared there, so a correct install fixes it. If it persists, you
are running a different Python from the one you installed into — check that
your prompt shows `(.venv)`.

Every deadline in this system means "end of day in California", so this is not
a cosmetic dependency: it is loaded at import time and nothing runs without it.

### `is cmake not installed?` while running `pip install`

Your machine is ARM and the Turso driver has no ready-built version for it.
Nothing is broken and there is nothing to fix — see *Working with the real
database from an ARM machine* in section 3.

### The published site shows *There isn't a GitHub Pages site here*

Nothing has ever been published. This is not a misconfiguration of the site
itself; it is the message GitHub shows for an address with no site behind it.

The publishing workflow has two jobs and the second waits for the first, so a
failure in the Modal half means the site half never runs. Open the **Actions**
tab and look at the most recent run. The usual cause is a missing repository
secret — see `docs/DEPLOY.md` step 7 for the four of them. Fix the cause, then
use **Re-run failed jobs** on that run; there is no need to make a commit
purely to trigger it.

If the workflow has succeeded and the site is still missing, check whether a
custom domain is set. GitHub then serves the site only at that domain and
redirects the `github.io` address to it, so a domain whose DNS is not ready
yet makes a perfectly good deployment look like a broken one.

### Nobody can sign in

Almost certainly `CODE_PEPPER`. Check the Modal secret exists and has not
changed. Every stored code depends on it.

### One person cannot sign in

- Their code was regenerated — they need the new sheet.
- Their registration was cancelled.
- They are locked out temporarily: ten wrong attempts from one place in fifteen
  minutes, or five wrong attempts at one code in an hour. It clears on its own.

### I need a notice on the site right now and Modal is down

Edit `frontend/public/announcement.json` in the GitHub website. Set `active` to
`true` and write your message. It appears within a minute, with no server
involved at all.

### The venue has no Wi-Fi

Run everything locally — section 4. The whole site works offline. Have a screen
recording as a second fallback.

---

## 13. Things that will catch you out

**Deadlines are stored in UTC but mean "end of day in California."** Always set
them through the dashboard, which does the conversion — including working out
whether that date falls in daylight saving. Never type a UTC time by hand.

**Payments are never edited.** A correction is a new entry, and a refund is a
negative one. The history is the record.

**Nothing is ever really deleted.** Cancelling a person hides them and can be
undone. The activity log physically cannot be changed or deleted.

**There are no refunds.** Someone who cancels after their chapter has paid still
counts toward the invoice, so the balance stays correct. The system chooses this
automatically; nobody has to remember it.

**Delegates have no email addresses.** The database refuses to store one. Every
message goes through the sponsor. Several delegates are eleven years old.

**The medical forms folder is not part of this system.** No code here reads it.
Only Convention Presidents can see the link. Keep it that way.

**Access codes are shown exactly once.** When you create an account or
regenerate a code, that screen is the only time it is ever displayed. Print it
or write it down before navigating away.

---

## Rebuilding the sample data

```bash
python scripts/seed.py --db dev.db --reset
```

Twelve chapters, about 150 delegates, a filled-in activity log, one partial
payment, and a chapter that is not billed — the same every time.

In production the same thing is at **Settings → Operations → Rebuild sample
data**, and it refuses to run unless the database is marked as sample data. That
mark is the only thing standing between a mis-click and an erased convention.

Whenever it is set, every page carries a **"Sample data"** banner. The
site is sometimes shown to a room full of teachers, and nobody should have to wonder
whether the names on the screen belong to real children.
