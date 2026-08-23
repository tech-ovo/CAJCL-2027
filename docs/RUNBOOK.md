# Runbook

How to operate this system without reading any source code.

**If the site is down during convention, go straight to [When it is broken](#when-it-is-broken).** Everything else can wait.

Written on the assumption that the person reading it is a high school student who did not build this, and may be panicking.

---

## The one-minute version

| I need to… | Do this |
|---|---|
| Change a fee, a deadline, the theme, an address | Sign in → **Settings**. No deploy. |
| Change printed wording | Settings → **Printed wording**. No deploy. |
| Put a banner on every page | Settings → **Announcements**. Under a minute. |
| Add a chapter or a sponsor | **Chapters** → Add a chapter → Add sponsor. Email the code by hand. |
| Record a payment | **Chapters** → Payment on that row. |
| Keep the site fast for an event | Settings → **Operations** → Keep warm for N hours. |
| Find out what happened | **Log**. Every entry is a full sentence. |
| Deploy code | `git push` to `main`. |

---

## What this system is made of

Four pieces, and only one of them holds anything important.

- **GitHub Pages** serves the static site. Free, and it cannot really break.
- **Modal** runs the API. All the business logic; the only thing that talks to the database.
- **Turso** is the database. Hosted libSQL, which *is* SQLite — every export is a real `.db` that opens in DB Browser.
- **Google Apps Script** is a ~130-line puppet that writes to Timothy's Drive, because only it can act as his Google identity.

The frontend never holds a database credential and never talks to Turso. Everything routes through Modal, including basic reads, because Modal is where authentication happens.

---

## Deploying

Push to `main`. GitHub Actions runs migrations against Turso, deploys Modal, then rebuilds and publishes the site.

To deploy by hand:

```bash
pip install modal
modal token new                    # once per machine
modal deploy backend/app.py
```

**Deploying resets the Modal autoscaler** to whatever is written in `backend/app.py`. That is why warmth is reconciled from the database every five minutes instead of being set once — see [Keeping it warm](#keeping-it-warm). A hotfix during convention will *not* silently put the site back to sleep.

### Running migrations

```bash
python -m backend.lib.migrate --db dev.db          # local
TURSO_DATABASE_URL=... python -m backend.lib.migrate   # production
```

Migrations are **forward-only**. There are no down-migrations, deliberately: a down-migration is a script you write once, never test, and then run for the first time at the worst possible moment. If a migration is wrong, write another one that corrects it.

The runner refuses to re-apply a migration whose contents have changed since it ran. If you see that error, someone edited history — the database and the repository no longer agree, and you need to work out which is right before doing anything else.

---

## Local development

```bash
pip install -r backend/requirements.txt
pip install pytest httpx esprima fonttools brotli

export CODE_PEPPER="anything-for-local-work"
python scripts/seed.py --db dev.db --reset      # 12 chapters, ~150 delegates
uvicorn backend.api:app --reload --port 8000

# in another terminal, for the site:
python -m http.server 8080 --directory frontend/public
# then open http://localhost:8080
```

The seed prints the access codes you need and writes them to `demo-codes.txt`, which is gitignored. They are freshly generated every run, because a reproducible credential is not a credential.

**On Windows:** every script forces UTF-8 output. If you write a new one that prints Latin text, do the same — the default console codepage is cp1252 and printing a macron raises `UnicodeEncodeError`, which looks exactly like a crash and is not one.

**WeasyPrint does not install on Windows** without GTK. Use `python backend/workers/pdf.py --db dev.db --document packet --school 2 --html` to check the layout; the PDF itself builds fine on Modal, from the same HTML.

---

## Secrets

Every secret lives in **Modal Secrets** (named `cajcl-2027`) and **GitHub Actions secrets**. Never in the repository. Never in the frontend.

| Secret | What it is | What breaks if you rotate it |
|---|---|---|
| `CODE_PEPPER` | Keys the HMAC of every access code | **Everything.** See below. |
| `TURSO_DATABASE_URL` | Which database to talk to | Nothing, if the new one has the same data |
| `TURSO_AUTH_TOKEN` | Permission to talk to it | API returns errors until updated |
| `APPS_SCRIPT_URL` | The Drive puppet's `/exec` URL | Exports stop reaching Drive, **silently** |
| `APPS_SCRIPT_KEY` | Shared HMAC key with the puppet | Puppet rejects every request |
| `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` | CI's permission to deploy | Deploys fail |

### Rotating `CODE_PEPPER` — break glass only

Every access code in the database is `HMAC-SHA256(pepper, code)`. Change the pepper and **nobody can sign in, ever again**, because the stored hashes no longer match anything anyone holds.

There is no way to re-derive the old codes: that is the entire point of peppering. Rotating it means:

1. Set the new pepper.
2. Regenerate every person's code (`people.pepper_version` exists to track this).
3. **Reprint and redistribute every packet.**

Do this only if the pepper has actually leaked. If it has, do it immediately — the codes are the only thing standing between a stranger and every roster.

### If `CODE_PEPPER` is missing in production

The app refuses to start rather than silently accepting a development default. That is deliberate: a container running with the wrong pepper would reject every real login while looking perfectly healthy.

---

## Keeping it warm

Modal scales to zero, which is what keeps the bill near zero. The first request after an idle period takes several seconds.

**Settings → Operations → Keep warm for N hours.**

The database is the source of truth for warmth, not the Modal API. A cron reconciles reality to `ops.warm_until` every five minutes, so it survives a deploy, a container dying, and someone forgetting.

**Before the board meeting or convention:** set it for the whole event plus a couple of hours. It costs a few cents.

---

## Exports and restoring

**Settings → Operations → Export**, or from a terminal:

```bash
python backend/workers/export.py --db cajcl.db --out ./exports
```

Four files: Excel and SQL, each in a **full** version and an **anonymised** one.

The anonymised versions have every attendee's name, guardian, email, phone, and free-text note removed — dropped, not masked. They are the ones you can hand to an AI or an outside helper. They still contain chapter names and the convention's own configuration, which are public by construction.

### Restoring

```bash
sqlite3 restored.db < exports/cajcl-YYYYMMDD-HHMM-full.sql
```

That produces a working database. To put it back into Turso, point `TURSO_DATABASE_URL` at a fresh database and import.

**The export is the *last* resort, not the first.** If Modal fails, reboot the endpoint and fix forward. The export is for the case where the database itself is destroyed — a bad migration, a deletion, an attack. In that case restore from the most recent export and reconstruct the gap from the **audit log**, which is append-only and therefore records the sequence of changes even when the current-state tables are gone.

### Running a worker in a Google Colab

Every worker is a self-contained script that takes a `.db` file and arguments. This is a hard architectural rule and the foundation of every fallback here.

```python
!pip install openpyxl
# upload cajcl.db and export.py, then:
!python export.py --db cajcl.db --out ./exports
```

**Test this once before convention, by actually doing it.** Not by assuming it.

---

## Adding a chair and granting scopes

1. **Chapters → Add a chapter** if they belong to one; otherwise they go on the state board row.
2. **Settings → Roles** → create a role with the scopes they need, if none fits.
3. Grant it to their account.

Scopes reach a person **only** through roles: `person_roles → roles → role_scopes`. There is no way to attach a scope directly and there must never be one — every authorization test in the suite checks that path and only that path.

| Scope | What it opens |
|---|---|
| `*` | Everything: audit log, exports, roles, impersonation, Drive links |
| `registration` | Rosters, chapters, payments, check-in |
| `academics` | Tests and activities, contests, grading, Certamen |
| `awards` | Score entry, test printing, tabulation |
| `sponsor` | One chapter's roster — always their own |
| `delegate` | Their own activity sheet |
| `chapter` | Chapter team entries for their own school |

The first four are **global**. The last three are **always school-limited**, and no amount of role juggling changes that.

Granting or revoking a role **signs that person out of every device**, because their existing sessions carry the old scope set.

---

## Checking Turso usage

**Settings → Operations** shows rows read, rows written, and storage, pulled from the Turso platform API.

Measured from a real seeded database and extrapolated to 50 chapters and 1,000 delegates:

| | Projected | Free tier | Headroom |
|---|---|---|---|
| Storage | 2.2 MB | 5 GB | 2,200× |
| Reads, normal month | 434,000 | 500 M | 1,150× |
| Reads, convention month | 1.7 M | 500 M | 288× |

Run `python scripts/measure_usage.py --db dev.db` to redo this against current data.

**Exceeding a read quota returns `BLOCKED` and the database stops answering.** You cannot pay your way out of it. That is why CI runs `EXPLAIN QUERY PLAN` over every query and fails the build on a `SCAN` of any table over 200 rows, and why aggregates are never computed live.

If usage suddenly climbs, something introduced a scan. Run `python scripts/check_query_plans.py` and look at what changed.

---

## When it is broken

### The site loads but says the server is not responding

Modal is cold or down.

1. Open the Modal dashboard. Look at the `cajcl-2027` app.
2. If it is erroring, check the logs for the failing function.
3. Redeploy: `modal deploy backend/app.py`.
4. Set **Keep warm** so it does not go back to sleep while you work.

The public welcome page keeps working throughout — it renders from a snapshot baked into the HTML.

### Everything returns a database error

Check Turso. If it says `BLOCKED`, a read quota is exhausted — see above. If the database is unreachable, check `TURSO_AUTH_TOKEN` has not expired.

### Nobody can sign in

Almost certainly `CODE_PEPPER`. Check the Modal secret is set and unchanged. Every stored code hash depends on it.

### One person cannot sign in

- Their code was regenerated — they need the new sheet.
- Their registration was cancelled.
- They are rate-limited: 10 failures per IP per 15 minutes, 5 per code per hour. Wait it out.

### Exports stop appearing in Drive

**Check the Apps Script deployment URL first.** Re-deploying the script can mint a new `/exec` URL, and the old one fails silently. Update `APPS_SCRIPT_URL` in Modal Secrets.

### I need a banner up right now and Modal is down

Edit `frontend/public/announcement.json` in the GitHub web interface. Set `active` to `true` and write `body_md`. It appears on every page within a minute of Pages rebuilding, with no server involved.

### The venue has no Wi-Fi

Run the whole thing locally: `python scripts/seed.py --db dev.db --reset`, then uvicorn and the static server as under [Local development](#local-development). The demo is fully interactive offline. Have a screen recording as a second fallback.

---

## Changing a fee mid-cycle

Do not. The fee is not expected to change once registration opens, and nothing models it.

If it must:

- **Fee goes up:** give every already-invoiced chapter a **discount** equal to the increase, so their bill does not move.
- **Fee goes down, and you want to honour it:** the recomputed invoice falls on its own. For chapters that already paid the higher amount, send the difference back and record a **negative payment** for it.

Both leave a readable trail in the payment history and the audit log, which is worth more than machinery that would run once a decade.

---

## Things that will bite you

- **Deadlines are stored as UTC but mean "end of day in California."** Always set them through the dashboard, which takes a plain date and works out the offset — including whether that date is in PST or PDT. Never hand-type a UTC string.
- **Payments are append-only.** A correction is a new row, possibly negative. Never edit one.
- **Nothing in `people`, `schools`, or `audit_log` is ever hard-deleted.** Cancellation is a status change, and cancellations can be restored.
- **There are no refunds.** Someone who cancels after their chapter paid keeps counting toward the invoice, so the balance stays correct. That is the `cancelled_paid` status, and it is chosen automatically.
- **The medical/waiver Drive folder is not managed by this system.** No code reads it. Only Convention Presidents can see the link. Keep it that way.
- **Delegates have no email addresses.** The database refuses to store one. Everything goes through the sponsor.

---

## The demo

```bash
python scripts/seed.py --db dev.db --reset
```

Rebuilds 12 chapters, ~150 delegates, a populated audit log, one partial payment, and a zero-invoice exempt chapter — reproducibly, from a fixed seed. Access codes are printed and written to `demo-codes.txt`.

In production the same thing is behind **Settings → Operations → Reset demo data**, and it refuses to run unless the database is flagged as demonstration data. That flag is what stands between a mis-click and an erased convention.

Whenever the flag is on, every page carries a **"Demonstration data"** banner. The demo is projected in a room full of teachers; nobody should have to wonder whether the names on screen belong to real children.
