# Putting the site online

This document takes you from a fresh checkout of the repository to a working
public website. It was written for the demonstration given to the CAJCL board
on August 29th, 2026, and it is the same procedure every year afterwards.

Three services are involved, and each does one job:

| Service | What it holds | What it costs |
| --- | --- | --- |
| **Turso** | the database — every school, person, and payment | free tier |
| **Modal** | the backend — all the code that reads and writes the database | free tier |
| **GitHub Pages** | the frontend — the pages a browser downloads | free |

Google Apps Script appears elsewhere in these documents. It is **not needed**
for the demonstration and is not set up here. Exports download straight to
your computer instead.

Budget about **90 minutes** the first time you do this, then rehearse twice.

---

## 0. Your terminal, before anything else

**Keep exactly one copy of this repository, and work in it from your ordinary
terminal.** On Windows that means PowerShell or the VS Code terminal; on macOS
or Linux, the terminal you already use. Every command in this document runs
there.

The temptation, on Windows, is to keep a second copy inside WSL — the Linux
environment that ships with Windows — because Modal runs on Linux. Resist it.
Two copies drift apart within a day: you edit one, run a script in the other,
and spend an afternoon working out why the results disagree. Nothing here needs
Linux. The tests, the build scripts, and the Modal command line tool all run
natively on Windows, and the PDF renderer only ever runs on Modal, never on
your own machine.

The one exception is in step 1. Turso's command line tool has no Windows
version, so those few commands need either WSL or Turso's website, and the
step says so where it comes up. Nothing about it touches the repository.

### The virtual environment

A **virtual environment** is a private folder of installed Python packages
belonging to one project, so that this project's packages cannot collide with
another's. Make it inside the project folder, where it is obvious what it
belongs to.

Windows, in PowerShell. **The `cd` is part of the recipe** — run it in the same
window, or the virtual environment is created in whatever folder you happened
to be in, which is usually your home folder:

```powershell
cd $HOME\OneDrive\Desktop\CAJCL-2027
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
pip install modal
```

macOS or Linux:

```bash
cd path/to/CAJCL-2027
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install modal
```

You must run the activate line in **every new terminal window**. When it has
worked, your prompt gains a `(.venv)` prefix **and shows the project folder**:

```
(.venv) PS C:\Users\you\OneDrive\Desktop\CAJCL-2027>
```

Check both halves. A prompt still reading `PS C:\Users\you>` means the `cd` did
not happen, and any `.venv` created there belongs to nothing. Remove it with
`Remove-Item -Recurse -Force $HOME\.venv` and start again from the `cd`.

If a command suddenly says a package is missing, the reason is almost always
that you opened a new terminal and forgot to activate.

### If PowerShell refuses to run the activate script

```
Activate.ps1 cannot be loaded because running scripts is disabled on this system.
```

Windows blocks all PowerShell scripts by default. Allow them for your own
account only — this changes nothing for other users and turns off no other
protection:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then run the activate line again.

**On a school-managed machine you may not be permitted to change that,** and
you do not need to. Skip activation entirely and call the environment's own
Python by its path. Every command works identically; it is only longer to type:

```powershell
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.venv\Scripts\python.exe -m pip install modal
.venv\Scripts\python.exe -m pytest backend/tests
.venv\Scripts\python.exe -m modal deploy backend/app.py
```

The `.venv` folder contains thousands of installed files and is specific to
your computer. It is listed in `.gitignore` — the file that tells Git which
things to leave out of the repository — so it is never committed, and you never
need to think about it again.

---

## After the demonstration: turning it into the real thing

The database the board saw on August 29th is full of invented chapters. This is
how it becomes the one registration actually runs on. Half an hour, and there
is nothing subtle in it.

### 1. Decide whether to start from scratch

Two honest options, and the second is more interesting than it sounds.

**Wipe and re-provision** is the ordinary path:

```powershell
modal run backend/app.py::setup --reset      # empty, then the tables
modal run backend/app.py::board              # the board, with new codes
```

`--reset` drops everything, so **the demonstration chapters, delegates and
codes all go**, which is the point. The board's codes go with them and are
reissued.

**Or run it the way a chapter will.** Reduce `board.json` to one person —
yourself, as the host chapter's sponsor with `admin` — reset, provision, and
then add everybody else from **Settings → Roles** in the browser. That is
exactly the path next year's commissioners take, and doing it once now is the
cheapest possible test of whether it works. Half an hour, and you find out in
August rather than next August.

Either way, **print the codes and hand them out the same day.** They are shown
once.

### 2. Turn the demonstration banner off

**Settings → Values → `ops.demo_mode`**, set to `0`. The "Demonstration data"
banner disappears from every page. Do this only after the reset — a database
still full of invented students should say so.

### 3. Check the convention facts

**Settings → Values.** Year, ordinal, dates, venue, hosts, theme, contact
address, fees, both deadlines. Nothing here needs a deploy, and everything here
is wrong by default the moment a detail changes.

### 4. Then open registration

`docs/SPONSOR-EMAIL.md` is the message, and the checklist at the bottom of it
is the last thing to read before sending.

### What about the migrations?

**Leave them exactly as they are.** It is tempting to fold `010_welcome_wording`
and `011_board_title` back into the files they correct, now that "nothing real
depends on them" — but something does, from the moment the first reset runs.
More importantly the habit is the thing being protected: a migration is never
edited, and a year from now nobody will remember which ones were safe to
squash.

They cost nothing. Eleven small files run in a few milliseconds against an
empty database, and each one is a readable record of a decision.

---

## Reading this a year later

This document says `cajcl-2027` a lot, and the 73rd convention is not 2027.

**Almost none of that is a problem.** The convention year, ordinal, dates,
venue, theme, fees, deadlines and every block of printed wording are settings,
changed from **Settings → Values** in a browser without touching code. That is
the whole design: a commissioner who has never opened an editor can run a
different convention from the same deployment.

`cajcl-2027` is a **name**, and it appears in exactly four places:

| Where | What it is | Change it? |
| --- | --- | --- |
| `backend/app.py`, four lines | the Modal app and its secret | Yes — one find-and-replace |
| Turso database | `turso db create cajcl-2027` | Yes — make your own |
| `backend/api.py`, `/health` | a label in a JSON response | Cosmetic |
| The repository folder | just a folder name | Only if you want to |

### Starting a new convention year

Work through steps 1 to 7 as written, substituting your own name for
`cajcl-2027` throughout. The order that matters:

1. **Fork or clone the repository.** Do not start from an empty one — the
   migrations and the catalog are years of accumulated decisions.
2. **Make a new Turso database.** Never reuse last year's: a convention's data
   is a record, and next year's registration does not belong in the same table
   as last year's. Old databases cost nothing to keep.
3. **Find and replace the app name** in `backend/app.py`. Four lines.
4. **Make a new Modal secret** under the matching name, with a **new pepper**.
   Do not carry the old one across — every code from last year would still
   work, against a database those people are no longer in.
5. **Deploy, migrate, seed** — steps 3 and 4.
6. **Add yourself** through `board.json` — step 4b, "The first person".
7. **Change the convention facts** from Settings. Year, ordinal, dates, venue,
   theme, fees, deadlines. None of these needs a deploy, and none of them is in
   the code.

### What never to change

**The migrations.** `backend/migrations/` is a record of what has been done to
databases that exist. Files are added, never edited, and never deleted — see
`backend/migrations/CHECKSUMS.txt`. A new convention runs all of them from
scratch and arrives at the same schema.

**And you do not need the demonstration.** `docs/DEMO.md` exists to convince a
board that this is worth adopting. That argument was made in August 2026. What
you need is this document and `docs/RUNBOOK.md`.

---

## 1. Turso, the database — 15 minutes

**On Windows, this is the one step that needs WSL.** Turso publishes its
command line tool for macOS and Linux only. Open a WSL terminal — `wsl` from
PowerShell — and run these there. They ask Turso about your account, not about
your files, so it does not matter which folder you are in and there is no
reason to copy the repository into WSL.

If you would rather not use WSL at all, everything below can be done at
[app.turso.tech](https://app.turso.tech) instead: create the database, then
read the URL and create a token from the database's page.

```bash
curl -sSfL https://get.tur.so/install.sh | bash
turso auth signup
turso db create cajcl-2027
turso db show cajcl-2027 --url
turso db tokens create cajcl-2027
```

The last two commands print the two pieces of information you need in step 2:
the **database URL**, and an **authentication token** that grants access to it.
Keep that terminal window open — you will copy from it shortly.

### About the region

Turso will place the database in a region such as `aws-us-east-1`. **Leave it
there.** Nobody in California ever talks to Turso directly; only Modal does,
and Modal is also on the East Coast. Moving the database closer to California
would put a continent between Modal and the database, and make every page
slower.

### The URL will not look exactly like the example

Yours will resemble:

```
libsql://cajcl-2027-cajcl-2027.aws-us-east-1.turso.io
         └── db ──┘ └─ org ──┘ └── region ─┘
```

The doubled name is normal. Turso names your first organisation after you, so
the database name and the organisation name often match. The second half is
your **organisation slug**, which step 2 refers to as `TURSO_ORG`. You can
confirm it with `turso org list`.

While you are here, create a second, separate database for testing. The free
tier allows 100 of them, and having one means you can try a risky change
without touching the database the board is about to look at:

```bash
turso db create cajcl-2027-staging
```

---

## 2. Modal, and the four settings it needs — 15 minutes

```bash
modal setup                              # opens a browser to log you in
```

Modal keeps configuration in something it calls a **secret**: a named bundle of
settings that the deployed code can read, and that is never written down in the
repository. This project uses one secret, named `cajcl-2027`.

### Running `modal setup` twice is fine

It mints a **new** token each time and writes it to `~/.modal.toml` — on
Windows, `C:\Users\you\.modal.toml`. The old one is not deleted or replaced; it
stays valid until you revoke it.

That is not a conflict, and nothing needs undoing. A Modal token is a
credential for **your account**, not for an app. Every token you hold reaches
the same workspace and deploys the same `cajcl-2027` app, so it does not matter
which one a particular machine uses. Deploy from your laptop, deploy from
GitHub Actions, deploy from a different computer — the last deploy wins,
exactly as it would with one token.

**Your laptop's token differing from the one in GitHub Actions is the better
arrangement, not a mistake.** If a laptop is lost, revoke that one token and CI
keeps working. If the repository's secrets are exposed, revoke that one and
your laptop keeps working.

See and revoke them at **modal.com → Settings → API Tokens**. Keep one per
machine plus one for CI, and delete any you cannot account for.

None of this touches the repository, so it has no bearing on whether it is safe
to commit. No Modal token has ever been in these files.

### Generate the pepper first, and look at it

The **pepper** is a long random string used to scramble access codes before
they are stored. Generate it into a variable so you can see it, rather than
piping it straight into the secret — a value you have never seen is a value you
cannot save anywhere:

In PowerShell:

```powershell
$env:CODE_PEPPER = (python -c "import secrets; print(secrets.token_urlsafe(48))")
$env:CODE_PEPPER           # put this in a password manager NOW
```

In bash:

```bash
export CODE_PEPPER="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
echo "$CODE_PEPPER"        # put this in a password manager NOW
```

**Why the pepper matters so much.** Every access code is stored scrambled with
it, and the plain codes are stored nowhere at all. If the pepper is lost,
nobody can ever sign in again, and there is no way to recover it. That is
precisely what makes a stolen copy of the database useless on its own.

You *can* read the pepper back later from the Modal dashboard, under Secrets.
Do not let that be your only copy.

### Then the two values that point at the database

**Never select these with the mouse.** A Turso token is several hundred
characters long and wraps across several lines in a terminal; selecting it
takes the wrap along, and a line break inside a token makes it unusable in a
way that reports itself as a network fault. Let the machine move the value
instead.

On macOS or Linux, where Turso and Modal share one terminal, that means
capturing the output directly:

```bash
export TURSO_DATABASE_URL="$(turso db show cajcl-2027 --url)"
export TURSO_AUTH_TOKEN="$(turso db tokens create cajcl-2027)"
```

On Windows the two commands live in different shells, so send each value
through the clipboard. In **WSL**, where `clip.exe` writes to the Windows
clipboard and `tr -d '\n'` guarantees no line break survives:

```bash
turso db show cajcl-2027 --url | tr -d '\n' | clip.exe
```

Then, in **PowerShell**, without touching the keyboard in between:

```powershell
$env:TURSO_DATABASE_URL = Get-Clipboard
```

Repeat for the token:

```bash
turso db tokens create cajcl-2027 | tr -d '\n' | clip.exe    # WSL
```

```powershell
$env:TURSO_AUTH_TOKEN = Get-Clipboard                        # PowerShell
```

### The optional usage settings

Turso issues **two** unrelated kinds of token, and the difference matters
because the commands look alike:

| Token | Made by | Lets you |
| --- | --- | --- |
| **Database token** | `turso db tokens create <database>` | read and write the data in one database |
| **Platform token** | `turso auth api-tokens mint <name> --org <org>` | ask Turso about your account, such as how much of the free tier is left |

The database token is `TURSO_AUTH_TOKEN`, and the site does not work without
it. The platform token is `TURSO_PLATFORM_TOKEN`, and it powers only the usage
page in the admin area. **If this part gives you trouble, skip it** — the usage
page then shows a message pointing at the Turso dashboard rather than
misleading zeros, and nothing else is affected.

Note that the verb is `mint`, not `create`, and that `--org` is now required.
Run this wherever the Turso tool lives — WSL on Windows:

```bash
turso auth api-tokens mint cajcl-usage --org "<your organisation slug>" \
  | tr -d '\n' | clip.exe            # drop the clip.exe on macOS and Linux
```

Do not pipe it through `tail` or `head`. Those discard error messages, so a
mistyped command leaves you with an empty value and no explanation. The token
is shown once and never again, so if you lose it, mint another under a
different name.

Your organisation slug comes from `turso org list`. Then set the last three
values, in the shell where you have been building the secret:

```powershell
$env:TURSO_PLATFORM_TOKEN = Get-Clipboard
$env:TURSO_ORG = "<your organisation slug>"
$env:TURSO_DB_NAME = "cajcl-2027"
```

### Create the secret

In PowerShell, where a backtick at the end of a line continues it:

```powershell
modal secret create cajcl-2027 `
  CODE_PEPPER="$env:CODE_PEPPER" `
  TURSO_DATABASE_URL="$env:TURSO_DATABASE_URL" `
  TURSO_AUTH_TOKEN="$env:TURSO_AUTH_TOKEN" `
  CAJCL_ENV="production" `
  TURSO_PLATFORM_TOKEN="$env:TURSO_PLATFORM_TOKEN" `
  TURSO_ORG="$env:TURSO_ORG" `
  TURSO_DB_NAME="$env:TURSO_DB_NAME"
```

In bash, where a backslash does the same job:

```bash
modal secret create cajcl-2027 \
  CODE_PEPPER="$CODE_PEPPER" \
  TURSO_DATABASE_URL="$TURSO_DATABASE_URL" \
  TURSO_AUTH_TOKEN="$TURSO_AUTH_TOKEN" \
  CAJCL_ENV="production" \
  TURSO_PLATFORM_TOKEN="$TURSO_PLATFORM_TOKEN" \
  TURSO_ORG="$TURSO_ORG" \
  TURSO_DB_NAME="$TURSO_DB_NAME"
```

If you skipped the usage settings, leave off the last three lines — and remove
the continuation character from the end of the `CAJCL_ENV` line, since that is
what joins each line to the next.

Step 3 checks that all of this arrived intact.

### Adding or changing settings afterwards

`modal secret create` refuses to run if a secret of that name already exists.
Add `--force` to overwrite it. Note that `--force` **replaces the entire
secret**, so you must list every setting again, not only the ones you are
adding.

---

## 3. Deploy the backend — 10 minutes

Deploying uploads the code in this repository to Modal and starts it running.
Do this before setting up the database, because the database setup runs on
Modal too:

```bash
modal deploy backend/app.py
```

Before going further, confirm that Modal can actually reach the database:

```bash
modal run backend/app.py::doctor
```

That prints the length and the first and last few characters of each setting in
the secret — enough to spot a truncated or empty one, without printing any
secret in full — and then tries the connection for real. On a database that
exists but has no tables in it yet, the last line reads:

```
connection OK - database is empty, so run `modal run backend/app.py::setup` next
```

That is the expected result at this point.

---

## 4. Create the tables and load the demonstration data — 5 minutes

```bash
modal run backend/app.py::setup --reset
```

This does three things: it deletes anything already in the database
(`--reset`), it creates all the tables, and it loads the fabricated
demonstration data. It finishes by printing every access code and writing them
to a file called `demo-codes.txt` on your own computer.

**Print that file on paper.** New codes are generated every time the
demonstration data is loaded, so a printout from an earlier rehearsal will not
work.

Two variations, for later:

```bash
# Load fresh demonstration data, keeping the existing tables.
modal run backend/app.py::setup

# Apply a change to the tables and columns, without touching the data.
modal run backend/app.py::setup --no-seed
```

The second one matters once there is real registration data in the database.
The tables and columns are defined by the numbered files in
`backend/migrations/`, and when someone adds a new one, `--no-seed` applies it
and leaves every school, person, and payment exactly where it was.

If step 3 or step 4 fails, `docs/RUNBOOK.md` section 12 lists the errors that
have actually happened here and what each one means.

---

## 4b. Give the real board their accounts — 5 minutes

The demonstration data is entirely invented, so nobody real can sign in to it.
Board members and chapter sponsors get accounts from a separate file that is
**never committed**, because this repository is public.

Create `board.json` in the project folder. Each entry needs a name, a title, a
school, and the roles that name carries.

**Almost everybody on the board is a delegate**, so `"type"` defaults to
`delegate` and only a sponsor or a chaperone needs `"type": "adult"`. A
convention president is a student at their own chapter who also holds a
convention role — one person, one account, one code, exactly like a chapter
leader. Filing them as adults would give them the Adult Registration Form
instead of the Student Activity Sheet every other delegate completes.

```json
[
  {
    "first": "Ada", "last": "Lovelace", "type": "adult", "title": "Sponsor",
    "school": "University High School", "city": "Irvine",
    "roles": ["sponsor", "admin"]
  },
  {
    "first": "Grace", "last": "Hopper", "title": "Convention President",
    "school": "University High School", "city": "Irvine",
    "roles": ["admin"]
  },
  {
    "first": "Katherine", "last": "Johnson", "title": "Awards Chair",
    "school": "Woodbridge High School", "city": "Irvine",
    "roles": ["awards_chair"]
  }
]
```

`title` is what somebody is *called* — "Logistics Coordinator", "WHS
Operations". `roles` is what they may *do*. Two people can hold `admin` and
have different titles, and a title changes without any permission changing.

The role keys are `admin`, `registration_chair`, `academics_chair`,
`awards_chair`, and `sponsor`. `admin` is everything; the rest are what their
names say. Settings → Roles lists them all, with what each one reaches.

Then:

```powershell
modal run backend/app.py::board --create-schools
```

`--create-schools` adds any chapter named in the file that does not exist yet.
Leave it off once every chapter is in place, and a misspelt school name becomes
an error naming the chapters it does know — rather than a second chapter that
looks right in a list and holds nobody.

Every new person's code is printed and written to `board-codes.txt`, which is
gitignored. **Codes are shown once.** Hand each person theirs directly.

### If anyone is still holding an `ADM-` code

`ADM` was a fourth prefix, given to anyone with full powers. It was retired,
because a prefix should say what somebody **is** — a delegate, a sponsor, a
volunteer — and never what they are allowed to do. Two sponsors doing the same
job for their two chapters were getting different prefixes because one of them
also sat on the board.

Those codes no longer work, and they cannot be converted: the prefix is part of
the string that gets hashed, so there is no way to rewrite one in place. Anyone
who held an `ADM-` code needs a new one:

```powershell
modal run backend/app.py::retire_adm_codes
```

It reissues, revokes the old sessions, prints each new code once, and writes
them to `board-codes.txt`. **Everyone in that list needs a new sheet.** If it
says nobody is holding one, there is nothing to do.

`setup --reset` followed by `::board` also clears this, because everything is
minted fresh under the current rule.

### The first person, and the chicken-and-egg

Roles are granted by somebody who already holds `admin`. In a brand new
database nobody does, so there is nobody to grant the first one.

`board.json` is how that knot is cut. It is read by a command you run from your
own machine with the Modal credentials, so it does not need anybody to be
signed in — and it is the ONLY way into the system that does not.

**Next year's commissioners should start with one entry**: themselves, as the
sponsor of the host chapter, holding `admin`.

```json
[
  {
    "first": "Your", "last": "Name", "title": "Technology Commissioner",
    "school": "Your High School", "city": "Your City",
    "roles": ["sponsor", "admin"]
  }
]
```

```powershell
modal run backend/app.py::board --create-schools
```

That prints one code. Sign in with it, and everybody else can be added from
**Settings → Roles** in the browser — which is the intended path, and the one
that leaves an audit entry naming who granted what.

Add the rest to `board.json` too if you would rather do it in one pass. Both
work; the file is simply the door that opens from outside.

**Nobody ever gets a second account for their powers.** A sponsor who joins the
board keeps the code they already had; they gain a role, not a login. This is
the same mechanism that promotes a delegate to chapter leader, and it is why
an access code says what somebody *is* rather than what they may do.

### If board.json is lost

The names are in the database. The file is what goes missing, and it is the
only route into provisioning — so recover it rather than retyping it:

```powershell
modal run backend/app.py::recover_board
```

It refuses to overwrite an existing `board.json`, so move any partial one aside
first.

**Codes are not recovered and cannot be.** Only their HMAC is stored, which is
the property that makes a stolen database useless. Anyone who needs a code gets
a new one.

### Running it again

Safe, and expected — this is how you add someone in October. A person already
in the database keeps their account, their id, and their existing code; only
their roles are brought into line with the file. Nobody gets a second account
and nobody is signed out.

```powershell
modal run backend/app.py::board                    # add anyone new, fix roles
modal run backend/app.py::board --new-codes        # reissue for EVERYONE listed
```

`--new-codes` signs out every device using an old code, so use it only when you
mean to. To reissue for one person, use the roster's **Issue new codes** button
instead.

**Each person is its own transaction.** If the run stops halfway — a misspelt
chapter, a role that does not exist — the people before it are already saved.
Fix the file and run it again; the ones already done are left alone.

---

## 5. Check that it answers — 2 minutes

```bash
curl https://<org>--cajcl-2027-web.modal.run/health
curl https://<org>--cajcl-2027-web.modal.run/public/stats
```

Replace `<org>` with your Modal organisation name. The full address is printed
by `modal deploy`, and also appears on the Modal dashboard under the
`cajcl-2027` app.

**Your Modal organisation and your Turso organisation are unrelated.** They are
two different companies. The names do not have to match, and usually do not.

`/health` reaches no database at all, so it answers even when the database is
misconfigured — which is what makes it a useful first test. `/public/stats`
is the one that proves the whole chain works: Modal is running, the settings
are correct, and the data is there.

---

## 6. Point the website at the backend — 5 minutes

**Two files, and both matter.**

First, `frontend/public/config.js`. Replace the placeholder address with the
one Modal printed:

```js
: "https://<org>--cajcl-2027-web.modal.run",
```

Second, `backend/api.py`, in the list called `ALLOWED_ORIGINS`. Add the address
your site will be published at:

```python
"https://<your-github-username>.github.io",
```

Browsers refuse to let a page at one address call a backend at another unless
the backend explicitly says that address is allowed. Until your address is in
that list, every request from the published site is blocked, and the only place
that says so is the browser's developer console — the page itself just sits
there.

### Then deploy again

```bash
modal deploy backend/app.py
```

`ALLOWED_ORIGINS` is a few lines of `backend/api.py`, and `backend/api.py` runs
**on Modal**, not on your computer. Editing the file changes only the copy on
your disk. Deploying is what uploads it, so until you deploy, the running
backend is still refusing your site.

The other file, `config.js`, belongs to the website rather than the backend, and
reaches its destination in step 7 when GitHub Pages publishes it.

Once the repository is on GitHub, pushing to `main` deploys Modal for you — the
workflow in `.github/workflows/deploy.yml` does it on every push. This manual
deploy is for the first time round, and for whenever you want to see a change
without committing it.

---

## 7. Publish the website — 10 minutes

The site is published by a GitHub Actions workflow, `.github/workflows/deploy.yml`,
which runs on every push to `main`. Doing it in that order matters: **add the
secrets before you push**, because a push without them fails within seconds and
publishes nothing at all.

### First, the four repository secrets

Under **Settings → Secrets and variables → Actions**, add:

`MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`

The two Modal values are in the file `~/.modal.toml` on your computer after you
ran `modal setup`, and are also on the Modal dashboard under Settings → API
Tokens. The two Turso values are the same ones you used in step 2.

### Then turn Pages on

**Settings → Pages → Source: GitHub Actions.** Not "Deploy from a branch" —
this repository builds the site rather than serving files straight out of it.

### Then push

```bash
git push
```

The workflow has two jobs and the second one **waits for the first**. It
deploys Modal and runs the migrations, and only then builds and publishes the
site. So a failure in the Modal half means the site is never published, and
GitHub shows the plain 404 page reading *There isn't a GitHub Pages site here.*
That message means nothing has ever been published, not that something is
misconfigured about the site itself.

You do not need to make an empty commit to try again. Open the **Actions** tab,
pick the failed run, and use **Re-run failed jobs**. The workflow also has a
**Run workflow** button, from the `workflow_dispatch` line in its configuration.

### About the custom domain

`frontend/CNAME` currently contains `state.uhsjcl.org`, and the workflow copies
it into the published site. Setting a custom domain has consequences worth
knowing:

- The site is served at that domain, and the `github.io` address redirects to
  it. If DNS is not set up yet, both addresses appear broken even though the
  publish succeeded.
- DNS needs a `CNAME` record for `state` under `uhsjcl.org`, pointing at
  `<your-github-username>.github.io`. That is set up wherever `uhsjcl.org` is
  registered, not on GitHub, and takes anywhere from minutes to a day to take
  effect.
- The domain must appear in `ALLOWED_ORIGINS` in `backend/api.py`, or the
  pages will load but no data will.

**If the domain is not ready, delete `frontend/CNAME` and clear the custom
domain box in Settings → Pages.** The site then publishes at
`https://<your-github-username>.github.io/<repository>/` and works immediately.
You can add the domain later. Whichever address you end up using has to be in
`ALLOWED_ORIGINS`.

### The two build scripts

The workflow runs these itself, so you do not have to. Run them by hand only
when you want to see the result locally before pushing:

```bash
python scripts/build_fonts.py            # writes the font files
python scripts/build_snapshot.py         # bakes the statistics into index.html
```

---

## 8. Warm it up — 1 minute, and do not skip this

On the morning of the meeting, sign in as an administrator and go to
**Settings → Operations → Keep warm for 6 hours**.

Modal shuts the backend down when nothing has used it for a while. The first
request after a quiet spell takes several seconds while it starts up again, and
the first thing the board sees should not be a loading message — however
well-designed that loading message is.

---

## 9. What this costs, and the one thing worth switching off

Modal bills for the time a container is actually running. The other two
services are free at this scale — Turso's free tier is measured in hundreds of
millions of row reads a month and this convention uses single-digit millions,
and GitHub Pages is free outright.

So Modal's number is the only one worth watching, and three things spend it:

| What | When | Roughly |
| --- | --- | --- |
| Answering requests | While somebody is using the site | Tiny — a request is milliseconds |
| Keeping a container warm | Only while you have switched it on | The largest item, by far |
| The scheduled jobs | Continuously, used or not | Small, but never zero |

**The idle cost is the one that surprises people,** because it accrues while
nobody is looking. Leave the app deployed for a week, read the figure on the
Modal dashboard, and multiply by four. That is a far better estimate than
anything written here, because it measures your app rather than a guess about
it.

### Auto-export is off outside convention

`LIVE_GRADING` at the top of `backend/app.py` is `False`, which means the
auto-export job carries no schedule at all. With it on, a container starts 144
times a day to read one setting, find auto-export switched off, and stop.

**Turn it on for convention weekend, and off afterwards.** There are two
switches on purpose: this one decides whether the alarm clock rings and needs a
deploy, and Settings → Operations decides what happens when it does and changes
in a second. A test fails while the flag is left on, so CI will remind you.

### The warm reconciler stays

It runs every five minutes all year and that is not negotiable: deploying
resets Modal's autoscaler to whatever is written in the code, so a hotfix
during convention would silently un-warm the site. Five minutes is how long
that window can stay open. It is also the cheapest of the three — it reads one
setting and stops.

### Keeping warm is the expensive one

A warm container is billed for every minute it is warm, whether anyone visits
or not. That is the trade: several seconds off the first request, in exchange
for paying while nothing happens. Use it for the hours that matter — the board
meeting, Friday check-in, the awards ceremony — and let it sleep the rest of
the time. **Keep warm for 6 hours** is shaped that way deliberately, and
expires on its own so nobody has to remember.

---

## 10. Rehearse — twice

Against the real deployed site, start to finish, with the projector if you can
get hold of one. Time it. Then have somebody else drive while you watch,
because you will click straight past the thing that is broken.

---

## Pre-flight checklist

- [ ] `curl .../health` returns `{"ok": true}`
- [ ] `curl .../public/stats` returns real numbers
- [ ] The published site loads and shows statistics, not dashes
- [ ] The **Demonstration data** banner appears on every page
- [ ] Every code in `demo-codes.txt` signs in
- [ ] A QR code from a printed sheet scans and signs in on a **phone**
- [ ] The packet prints; the invoice prints; the exempt invoice explains itself
- [ ] Warm is set to last past the end of the meeting
- [ ] `LIVE_GRADING` in `backend/app.py` is still `False` — it is for
      convention weekend only
- [ ] Every board member in `board.json` has signed in once with their code
- [ ] `demo-codes.txt` is printed on paper
- [ ] A screen recording of the full flow exists
- [ ] A local copy runs offline, in case the venue Wi-Fi fails

---

## Known gaps, so that nothing surprises you live

- **PDF generation has not been tested end to end.** The print view works, and
  it is the same document. The first PDF request has to start a second, heavier
  container and takes 30 seconds or more. **Demonstrate the print view, not the
  PDF.**
- **The usage page shows a message rather than numbers**, unless the three
  optional Turso settings from step 2 are present.
- **The catalog editor is read-only.** The catalog itself is correct; the
  screen for editing it was cut for time.
- **Exports download to your computer.** Writing them to Google Drive requires
  Apps Script, which is not set up and is not needed here.

---

## If it breaks during the meeting

Do not debug in front of the board.

1. **Switch to the local copy.** Run `uvicorn backend.api:app --port 8000` and
   `python -m http.server 8080 --directory frontend/public`, with `config.js`
   pointing at `127.0.0.1:8000`. Everything works offline against the local
   `dev.db` file.
2. **Switch to the screen recording.**
3. Fix it afterwards. `docs/RUNBOOK.md`, section 12, has the diagnosis paths.

Having the local copy already running in a second browser window costs nothing
and turns a disaster into a shrug.
