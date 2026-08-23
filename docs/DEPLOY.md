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

Use **WSL** — Windows Subsystem for Linux — or the VS Code terminal with WSL
selected. Either is fine; pick one and stay with it. WSL matches the Linux
environment that Modal runs on, and it is also the only one of the two where
the PDF tools install at all.

Modern Ubuntu will not let `pip` install packages into the system copy of
Python. That is a safety feature, not a mistake. The answer is a **virtual
environment**: a private folder of installed packages belonging to one project.
Make it inside the project folder, so it is obvious what it belongs to:

```bash
cd ~/CAJCL-2027
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install modal
```

You must run `source .venv/bin/activate` in **every new terminal window**. When
it has worked, your prompt gains a `(.venv)` prefix, like this:

```
(.venv) you@yourmachine:~/CAJCL-2027$
```

If a command suddenly says a package is missing, the reason is almost always
that you opened a new terminal and forgot this step.

The `.venv` folder contains thousands of installed files and is specific to
your computer. It is listed in `.gitignore` — the file that tells Git which
things to leave out of the repository — so it is never committed and you never
need to think about it again.

---

## 1. Turso, the database — 15 minutes

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

### Generate the pepper first, and look at it

The **pepper** is a long random string used to scramble access codes before
they are stored. Generate it into a variable so you can see it, rather than
piping it straight into the secret — a value you have never seen is a value you
cannot save anywhere:

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

Rather than pasting the URL and token by hand, let the Turso command line tool
produce them. A token is several hundred characters long, and pasting one by
hand is the single most common way this step goes wrong:

```bash
export TURSO_DATABASE_URL="$(turso db show cajcl-2027 --url)"
export TURSO_AUTH_TOKEN="$(turso db tokens create cajcl-2027)"
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

Note that the verb is `mint`, not `create`, and that `--org` is now required:

```bash
export TURSO_ORG="<your organisation slug, from turso org list>"
export TURSO_DB_NAME="cajcl-2027"
export TURSO_PLATFORM_TOKEN="$(turso auth api-tokens mint cajcl-usage --org "$TURSO_ORG")"

echo "${#TURSO_PLATFORM_TOKEN} characters"   # zero means the command failed
```

Do not pipe that command through `tail` or `head`. Those discard error
messages, so a mistyped command leaves you with an empty variable and no
explanation. The token is shown once and never again, so if you lose it, mint
another under a different name.

### Create the secret

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

If you skipped the usage settings, leave off the last three lines — and
remember to remove the trailing `\` from the `CAJCL_ENV` line, which is what
joins each line to the next.

Double-check that all secrets were stored correctly.

```bash
modal shell --secret cajcl-2027 --cmd "env | grep -E '^(CODE_PEPPER|TURSO_DATABASE_URL|TURSO_AUTH_TOKEN|CAJCL_ENV|TURSO_PLATFORM_TOKEN|TURSO_ORG|TURSO_DB_NAME)='"
```

That prints every value in full, so do not run it while your screen is being
projected. Step 3 has `modal run backend/app.py::doctor`, which checks the same
settings without revealing them.

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

### If step 3 or step 4 fails

**`Hrana: http error: http::Error(InvalidHeaderValue)`**

The authentication token contains a character that cannot be sent over the
network — nearly always a line break, picked up when a long token wrapped
across two lines in the terminal and was copied along with the wrap. Set the
values using the commands in step 2, which never involve pasting, then re-create
the secret with `--force`.

**`WSServerHandshakeError: 400`**

An obsolete database driver is installed, left over from an earlier attempt.
Remove it:

```bash
pip uninstall -y libsql-client
```

**`is 'cmake' not installed?` while running `pip install`**

Your computer has an ARM processor — a Snapdragon laptop, or Linux running on
Apple silicon. The `libsql` database driver has no ready-built version for that
combination, so `pip` tries to compile it from source and fails.

Nothing is broken, and there is nothing to fix. `backend/requirements.txt`
already skips that driver on ARM machines, and none of the steps in this
document need it, because everything that touches the live database runs on
Modal. Local development uses a plain file on disk and a driver built into
Python.

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
there. Run `modal deploy backend/app.py` again after changing this file.

---

## 7. Publish the website — 10 minutes

```bash
python scripts/build_fonts.py            # writes the font files
python scripts/build_snapshot.py         # bakes the statistics into index.html
```

In the repository on GitHub: **Settings → Pages → Source: GitHub Actions**.

Add these four repository secrets first, under **Settings → Secrets and
variables → Actions**. Without them the publishing workflow fails within
seconds, which is exactly what happens if you push a change before setting
them:

`MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`

The two Modal values are in the file `~/.modal.toml` on your computer after you
ran `modal setup`, and are also on the Modal dashboard under Settings → API
Tokens. The two Turso values are the same ones you used in step 2.

If the custom domain is not ready yet, delete the file `frontend/CNAME` and use
the `github.io` address instead. Either way, whichever address you end up with
has to appear in `ALLOWED_ORIGINS` from step 6.

---

## 8. Warm it up — 1 minute, and do not skip this

On the morning of the meeting, sign in as an administrator and go to
**Settings → Operations → Keep warm for 6 hours**.

Modal shuts the backend down when nothing has used it for a while. The first
request after a quiet spell takes several seconds while it starts up again, and
the first thing the board sees should not be a loading message — however
well-designed that loading message is.

---

## 9. Rehearse — twice

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
