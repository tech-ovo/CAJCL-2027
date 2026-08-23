# Going live for the August 29th board meeting

Modal + Turso + GitHub Pages. **Apps Script is not needed** — exports download
straight from the browser, and nothing else in the demo touches Drive.

Budget about **90 minutes** the first time, then rehearse twice.

---

## 0. Your terminal, before anything else

Use **WSL** or the VS Code terminal pointed at WSL. Either is fine; pick one.
WSL matches the Linux environment Modal runs on, and it is also the only one of
the two where the PDF tools install at all.

Modern Ubuntu will not let `pip` install into the system Python. That is a
safety feature, not a mistake. Make a virtual environment **inside the project**
so it is obvious what it belongs to:

```bash
cd ~/CAJCL-2027
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install modal
```

You must run `source .venv/bin/activate` in **every new terminal**. Your prompt
gains a `(.venv)` prefix when it has worked. If a command suddenly says a
package is missing, that is nearly always why.

`.venv/` is gitignored.

---

## 1. Turso — 15 minutes

```bash
curl -sSfL https://get.tur.so/install.sh | bash
turso auth signup
turso db create cajcl-2027
turso db show cajcl-2027 --url
turso db tokens create cajcl-2027
```

### About the region

Turso will put you in a group like `aws-us-east-1`. **Leave it there.**

The instinct is to move it near California, but nobody in California ever talks
to Turso. Only Modal does — the browser never touches the database. Modal's
default region is US East, so an East Coast database is *already* the right
choice: it puts the two things that actually talk to each other next to each
other. Moving Turso west would put a continent between Modal and its database
and make every page slower.

### The URL will not look like the example

Yours will be something like:

```
libsql://cajcl-2027-cajcl-2027.aws-us-east-1.turso.io
         └─ database ─┘ └─ org ─┘ └── region ──┘
```

The doubled name is normal — Turso names your first organisation after you. The
second half is your **organisation slug**, which you need later for
`TURSO_ORG`. Confirm it with `turso org list`.

Create a staging database too, while you are here. The free tier allows 100, and
it means you never test a migration against the database the board is about to
look at:

```bash
turso db create cajcl-2027-staging
```

---

## 2. Modal, and generating the pepper — 15 minutes

```bash
pip install modal
modal setup                              # opens a browser
```

**Generate the pepper so you can see it.** Do not pipe it straight into the
secret — you need a copy, and a value you never saw is a value you cannot put in
a password manager.

```bash
export CODE_PEPPER="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export TURSO_DATABASE_URL="libsql://cajcl-2027-<org>.aws-us-east-1.turso.io"
export TURSO_AUTH_TOKEN="<the token from step 1>"

echo "$CODE_PEPPER"        # <- put this in a password manager NOW
```

Then create the secret from those variables:

```bash
modal secret create cajcl-2027 \
  CODE_PEPPER="$CODE_PEPPER" \
  TURSO_DATABASE_URL="$TURSO_DATABASE_URL" \
  TURSO_AUTH_TOKEN="$TURSO_AUTH_TOKEN" \
  CAJCL_ENV="production"
```

**Why the pepper matters this much.** Every access code is stored scrambled with
it, and the plain codes are stored nowhere. Lose the pepper and nobody can ever
sign in again — there is no recovery, which is exactly what makes a stolen copy
of the database useless on its own.

You *can* read a Modal secret back later from the Modal dashboard under Secrets.
Do not let that be your only copy.

### Adding or changing keys afterwards

`modal secret create` refuses if the secret already exists. Use `--force`, which
**replaces the whole secret** — so you must pass every key again, not only the
new ones:

```bash
modal secret create cajcl-2027 \
  CODE_PEPPER="$CODE_PEPPER" \
  TURSO_DATABASE_URL="$TURSO_DATABASE_URL" \
  TURSO_AUTH_TOKEN="$TURSO_AUTH_TOKEN" \
  CAJCL_ENV="production" \
  TURSO_PLATFORM_TOKEN="$(turso auth api-tokens create cajcl-usage | tail -1)" \
  TURSO_ORG="<your org slug from turso org list>" \
  TURSO_DB_NAME="cajcl-2027" \
  --force
```

The last three are optional and only power the usage page. Without them it shows
a message pointing at the Turso dashboard rather than misleading zeros.

**Your Modal organisation and your Turso organisation are unrelated.** They are
separate companies; the names do not have to match and usually do not.

---

## 3. Deploy, then migrate and seed — 10 minutes

Deploy first, because the database setup runs **on Modal**:

```bash
modal deploy backend/app.py
```

Then:

```bash
modal run backend/app.py::setup --reset
```

That applies the migrations and loads the demonstration data, printing every
access code and writing them to `demo-codes.txt` on your own machine.
**Print that page.** Codes are regenerated on every seed, so a copy from an
earlier rehearsal will not work.

Later on, to update the structure without touching the data:

```bash
modal run backend/app.py::setup --no-seed
```

### Why this runs on Modal and not on your laptop

The driver that talks to hosted Turso is `libsql`. It ships ready-built for
x86_64 Linux, both kinds of Mac, and Windows — but **not for ARM64 Linux**. On
a Snapdragon laptop, WSL is ARM64 Linux, so pip tries to compile it from Rust
source, needs cmake and a full toolchain, and usually fails with:

```
is `cmake` not installed?
```

Modal's machines are x86_64, so the driver is simply there. Running the setup
on Modal sidesteps the problem entirely, and is better practice regardless: the
migration runs in the same environment as the code that will use it.

`backend/requirements.txt` already skips the driver on ARM64 Linux, so a plain
`pip install -r backend/requirements.txt` works there.

> **If you see `WSServerHandshakeError: 400`** you have the *old* driver
> installed from an earlier attempt. `libsql-client` was archived in June 2025
> and current Turso servers reject its handshake — before running any SQL, and
> while the Turso CLI connects to the same database perfectly happily.
>
> ```bash
> pip uninstall -y libsql-client
> ```

---

## 4. Check it answers — 2 minutes

```bash
curl https://<org>--cajcl-2027-web.modal.run/health
curl https://<org>--cajcl-2027-web.modal.run/public/stats
```

`/health` touches no database, so it answers even if the database is
misconfigured — which makes it the useful first test. `/public/stats` is the
one that proves the whole chain works: Modal is up, the credentials are right,
and the data is there.

The URL is printed by `modal deploy`, and is on the Modal dashboard under the
`cajcl-2027` app.

---

## 5. Point the frontend at it — 5 minutes

**Two files, and both matter.**

`frontend/public/config.js` — replace the placeholder URL:

```js
: "https://<org>--cajcl-2027-web.modal.run",
```

`backend/api.py` → `ALLOWED_ORIGINS` — add your real GitHub Pages origin:

```python
"https://<your-github-username>.github.io",
```

Until that origin is listed, every request from the published site is blocked,
and the *only* place that says so is the browser's developer console. Redeploy
Modal after changing it.

---

## 6. Publish the site — 10 minutes

```bash
python scripts/build_fonts.py            # writes the font subsets
python scripts/build_snapshot.py         # bakes the numbers into index.html
```

Repository → Settings → Pages → Source: **GitHub Actions**.

Add these repository secrets first (Settings → Secrets and variables → Actions),
or the deploy workflow fails within seconds — which is exactly what happens if
you push before setting them:

`MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`

Modal tokens come from `~/.modal.toml` after `modal setup`, or from the Modal
dashboard under Settings → API Tokens.

If the custom domain is not ready, delete `frontend/CNAME` and use the
`github.io` address — it still has to be in `ALLOWED_ORIGINS` either way.

---

## 7. Warm it — 1 minute, and do not skip this

Sign in as an admin → **Settings → Operations → Keep warm for 6 hours**, on the
morning of the meeting.

Modal sleeps when idle. The first request after a quiet spell takes several
seconds, and the first thing the board sees should not be a loading message —
even a well-designed one.

---

## 8. Rehearse — twice

Against production, start to finish, with the projector if you can get it. Time
it. Then have someone else drive while you watch, because you will click past
the thing that is broken.

---

## Pre-flight checklist

- [ ] `curl .../health` returns `{"ok": true}`
- [ ] `curl .../public/stats` returns real numbers
- [ ] The published site loads and shows statistics, not dashes
- [ ] The **Demonstration data** banner is on every page
- [ ] Every code in `demo-codes.txt` signs in
- [ ] A QR from a printed sheet scans and signs in on a **phone**
- [ ] The packet prints; the invoice prints; the exempt invoice explains itself
- [ ] Warm is set past the end of the meeting
- [ ] `demo-codes.txt` is printed on paper
- [ ] A screen recording of the full flow exists
- [ ] A local copy runs offline, in case the venue Wi-Fi fails

---

## Known gaps, so nothing surprises you live

- **PDF generation is untested end to end.** The print view works and is the
  same document. The first PDF request cold-starts a second, heavier container
  and takes 30+ seconds. **Demo the print view, not the PDF.**
- **`/admin/usage` shows a message, not numbers**, unless the three optional
  Turso platform values are set.
- **The catalog editor is read-only.** Seeded correctly; the editing screen was
  cut for time.
- **Exports download from the browser.** Writing them to Drive needs Apps
  Script, which is not set up and is not needed for this.

---

## If it breaks during the meeting

Do not debug in front of the board.

1. **Switch to the local copy.** `uvicorn backend.api:app --port 8000` plus
   `python -m http.server 8080 --directory frontend/public`, with `config.js`
   pointed at `127.0.0.1:8000`. Everything works offline against `dev.db`.
2. **Switch to the recording.**
3. Fix it afterwards. `docs/RUNBOOK.md` section 12 has the diagnosis paths.

Having the local copy already running in a second browser window costs nothing
and turns a disaster into a shrug.
