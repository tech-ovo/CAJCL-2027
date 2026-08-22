# **Stack**

**GitHub Pages** serves the static site from a public repository. Everything on the page is populated by API calls to **Modal**, which holds all business logic and is the only thing that talks to the database. The database is **Turso** (hosted libSQL, which is SQLite). **Google Apps Script** is a narrow puppet that writes to and lists Timothy's personal Google Drive, because it is the only thing that can act as his Google identity. All code lives in a single GitHub repository, including a mirrored copy of the Apps Script source.

Every request routes through Modal, including basic reads, because Modal is where authentication and authorization happen. The frontend never holds a database credential and never talks to Turso.

## Why Turso instead of SQLite on a Modal Volume

Modal Volumes are explicitly not built for live database files: they require an explicit commit for changes to become visible, they apply last-write-wins on concurrent modification, and they do not support distributed file locking. Even pinned to a single container, a redeploy or a preemption mid-commit can leave the `.db` and `-wal` files snapshotted at inconsistent moments. The failure mode is not an outage — it is silent corruption discovered later, which is the one failure the emergency plan below cannot absorb.

Turso removes that entire class of bug while keeping everything that matters. libSQL *is* SQLite, so the `.sql` and `.db` exports remain real SQLite files that open in DB Browser, load into a Google Colab, and work with every fallback described under **Emergencies**. Local development runs against a plain file. Nothing about the mental model changes.

The cost is that "one platform" becomes "one repository," which is the property that actually matters for maintainability. Turso adds exactly one connection string to Modal Secrets.

## Free-tier budget

Everything must stay free. Sized against an upper bound of 50 schools, 1,000 delegates, and roughly 150 adults (1,150 people), all data stored as text with no files in the database:

| Quota | Free limit | Projected peak | Headroom |
|---|---|---|---|
| Turso storage | 5 GB | ~25 MB including indexes | ~200× |
| Turso rows written | 10 M/month | ~120,000 across the entire Sept–Mar cycle | ~80× |
| Turso rows read | 500 M/month | ~3 M/month normal, ~12 M in the convention month | ~40× |
| Turso databases | 100 | 3 (production, staging, prior-year archive) | — |
| Modal credits | $30/month | ~$1.50 for a warm convention weekend, near zero otherwise | large |
| Modal seats | 3 | 2 commissioners | — |
| GitHub Pages | 1 GB site, 100 GB/mo bandwidth | a few MB, negligible traffic | large |
| GitHub Actions | free on public repos | trivial | — |
| Apps Script | ~20k UrlFetch/day, 90 min/day runtime | a few hundred calls/day at peak | large |
| Google Drive | 5 TB | scanned packets only | large |

Storage is dominated by the audit log (~8 MB) and medical-adjacent free text (~1 MB); the rest is rounding error. Writes are trivial because registration is a months-long trickle, not a firehose.

**Reads are the only quota that can realistically be blown, and only by bad queries.** In Turso a "row read" is a row *scanned*, not a row returned. A query consulting multiple tables incurs one read per row considered from each table. Aggregate functions incur one read per row considered. Any query that cannot use an index incurs one read per row in the table. An `UPDATE` incurs one read in addition to one write per row changed. Adding an index to a table that already has rows triggers a full table scan and one read per existing row.

Two realistic bugs erase the entire 40× margin:

1. **An N+1 in the sponsor roster view.** Fetch the roster, then loop over thirty delegates issuing one form-status query each. Without an index on `form_submissions(person_id)`, each of those thirty is a full scan of ~3,450 rows: 103,500 reads per page load instead of ~90. At 3,000 loads a month that is 300 M reads from one screen.
2. **An uncached public statistics endpoint.** `COUNT(*)` over `people` costs 1,150 reads per hit. The welcome page is unauthenticated and reachable by crawlers; 100,000 hits is 115 M reads.

Exceeding a quota does not produce an overage charge — it produces a `BLOCKED` error and the database stops answering. During convention that is an outage you cannot buy your way out of. Therefore the following are requirements, not suggestions:

- **Every index is declared in the same migration that creates its table.** Never add an index to a populated table without accounting for the scan.
- **Every list view is a single query with a JOIN.** No query inside a loop, anywhere, ever.
- **Aggregates are never computed live.** `school_stats` holds per-school counters and `public_stats_cache` holds a single row of site-wide totals; both are updated inside the same transaction as the mutation that changes them, which is Turso's own recommended pattern.
- **CI runs `EXPLAIN QUERY PLAN` on every query in the codebase** and fails the build if a plan contains `SCAN` against any table expected to exceed 200 rows.
- **An admin page displays current Turso usage** (rows read, rows written, storage) pulled from the Turso platform API, so quota drift is visible before it becomes an outage.

## Modal: two images, one writer

The web server is a FastAPI app on a **slim image**: `fastapi`, `libsql-client`, `argon2-cffi`, `segno`, `openpyxl`. It must cold-start in a couple of seconds.

Anything CPU-heavy or dependency-heavy runs as a **separate function with its own fat image** — PDF generation with WeasyPrint needs Pango and Cairo apt-installed, and later work (optical mark recognition, awards generation) will need more. The web container `.spawn()`s these and the worker reports completion back to the web endpoint over the network. The fat image only ever cold-starts when someone actually asks for a PDF, so the interactive path never pays for it.

Because Turso handles durability, the web function no longer needs to be pinned to a single container. Leave `target_concurrency` unset and do not set `max_containers=1` — Modal notes that pinning to one container prevents it from bringing up a replacement to gracefully shift traffic during a rolling redeployment, which would turn every hotfix into an outage.

Workers must be written so that each one is **a single self-contained script that runs anywhere**. Given a `.db` file and arguments, it must run unmodified in a Google Colab. This is a hard architectural rule and the foundation of the fallback plans below. Do not keep a copy in Colab beforehand — it would drift — but do keep the entry point trivially copy-pasteable.

## Warm and cold

Modal scales to zero by default, which is what keeps the bill near zero. Convention weekend and live demos need warmth.

**The database is the source of truth for desired warmth, not the Modal API.** A `settings` row holds `warm_until` as a UTC timestamp. The admin dashboard sets it — "keep warm for N hours" — and a Modal cron running every five minutes reconciles reality to it: if `now < warm_until`, ensure `min_containers=1` via `Function.update_autoscaler()`; otherwise ensure `min_containers=0`.

This shape is required because deploying the app **resets the autoscaler to the static configuration in code**. A one-shot button press would be silently undone by the first hotfix during convention. The reconciler re-applies within five minutes of any deploy and also survives the container dying with a revert pending.

## Authentication

Each person receives one code, and only one, regardless of how many roles they hold. Format is a three-letter prefix, nine random Crockford Base32 characters, and a Crockford check symbol, displayed as `PPP-XXXXX-XXXXX`. Prefixes are `SPO` sponsor, `DEL` delegate, `VOL` adult volunteer or chaperone, `ADM` admin. The prefix is display and disambiguation only; it is not a namespace, and codes are globally unique across prefixes.

The check symbol is validated in the browser before any request is sent, so a mistyped code produces an immediate "check that code again" rather than a failed login attempt against the rate limiter.

Codes are stored as `HMAC-SHA256(pepper, normalized_code)` in a unique-indexed column, with the pepper held in **Modal Secrets and never in the database or repository**. This gives an O(1) indexed lookup while ensuring that a database leak alone cannot brute-force forty-five bits of entropy. Store a `pepper_version` column so rotation is possible; rotating requires reissuing every code, so it is a break-glass procedure, not routine.

Redeeming a code returns a **session token**: 32 random bytes, stored server-side as a plain SHA-256 hash (no pepper needed at 256 bits of entropy), kept in `localStorage` on the client. The raw code is never stored on the device. Sessions are individually revocable, carry a 180-day expiry, and are invalidated when a sponsor regenerates the person's code.

**Magic links.** The printed instruction sheet carries a QR code so a delegate can scan and be logged in without typing. The code travels in the **URL fragment**, never the query string — `https://state.uhsjcl.org/#/enter/DEL-K7M2N-9PQ4Z` — so it is never sent to a server, never lands in an access log, and never leaks through a `Referer` header. The frontend reads `location.hash`, exchanges it for a session token, and immediately calls `history.replaceState()` to strip it. QR codes are generated with `segno` as SVG for both screen and print.

Because the printed sheet is now a bearer credential, it says so, it shows the delegate's name and ID large enough that a sponsor cannot hand out the wrong page, and sponsors have a working "regenerate code" action that invalidates the old QR and all sessions derived from it.

**Rate limiting** is per-IP and per-code with lockout after repeated failures. Failed redemptions are logged.

**Authorization is separate from authentication and is where the real work is.** The repository is public, so every endpoint is documented to anyone curious. The realistic threat is not a database dump; it is a sponsor at one school reading another school's roster because an endpoint checked identity but not scope. Every endpoint declares its required scope and its school-scoping rule in code, and the test suite hits every endpoint with a wrong-role and wrong-school credential.

**Impersonation** exists because admins need to reproduce what a confused sponsor is seeing. It requires the `*` scope, a step-up re-entry of the admin's own code, and produces a distinct session carrying `impersonator_person_id`. It is read-only unless explicitly toggled, expires after 30 minutes, shows a permanent banner naming both identities, and never reveals the target's code. `impersonation.start`, `impersonation.end`, and every action taken inside carry both identities in the audit log.

## Google Apps Script

Apps Script is a puppet with exactly one reason to exist: only it can act as Timothy's Google identity and write to his personal Drive under his 5 TB quota. Modal cannot, absent domain-wide delegation.

It exposes four operations — `upload`, `list`, `mkdir`, `trash` — and holds no configuration. Folder IDs, filenames, and retention rules all travel in the request payload from Modal. The **one** secret that must live in Script Properties is a shared HMAC key, because the web app is deployed as "execute as me / anyone with the link" and needs some way to verify the caller is actually your backend. Requests carry an HMAC signature and a timestamp; the script rejects anything older than five minutes.

The Drive folder for each school is writable **only** through this script, and `list` lets Modal cache the folder's structure and file IDs in the database — so later features (art voting galleries, lost and found) resolve Drive IDs from the database rather than crawling Drive.

The result is roughly 80 lines that will essentially never change. The repository copy under `apps-script/` is synchronized with `clasp`: `clasp clone` once, `clasp pull` after editing in the web UI, `clasp push` after editing locally. `.clasprc.json` is gitignored because it holds OAuth credentials; `.clasp.json` holds only the script ID and is safe to commit. A future commissioner who never touches a terminal can edit in the web UI and treat the repository copy as documentation and disaster recovery.

## Repository layout and deployment

One public repository. Secrets live only in Modal Secrets and GitHub Actions secrets — never in the repository, never in the frontend.

```
/frontend          static site served by GitHub Pages
  /public          index.html, tokens.css, fonts/, convention-snapshot.json
  CNAME            custom domain (state.uhsjcl.org)
  config.js        API base URL — not a secret
/backend           Modal app
  app.py           slim web image, FastAPI endpoints
  workers/         fat-image functions, each runnable standalone in Colab
  migrations/      numbered .sql files, forward-only
  queries/         all SQL, one place, so EXPLAIN QUERY PLAN can scan it
/apps-script       clasp-managed mirror of the Drive puppet
/docs              these documents
/scripts           seed data, exports, warm toggle, local dev helpers
```

`CNAME` in the repository is how GitHub Pages tracks the custom domain, so no separate domain-tracking file is needed. GitHub Actions deploys Modal on push to `main` using a Modal token stored as a repository secret. The repository must stay public: GitHub Pages from a private repository requires a paid plan, and while the Student Developer Pack grants Pro, the site 404s when student status lapses — a landmine for future commissioners.

Because the repository is public, the demo database contains **only fabricated data**. No real student names, ever.

# **Emergencies**

Because this is a new system, assume it will fail in a way nobody predicted, and make sure the convention runs anyway.

**Exports.** Four files per export: Excel and SQL, each in a full version with personal information and an anonymized version showing only user IDs. The anonymized versions exist so they can be handed to an AI or an outside helper without exposing minors' data. During the demo and normal operation there is a **manual export button** only. An admin can later enable **auto-export on a 10-minute interval**, setting both the start and the automatic shut-off time from the dashboard; this matters most during live grading, when losing ten minutes of scores is the difference between a smooth awards ceremony and a disaster. Exports write to Drive through the Apps Script puppet.

If Modal fails, the ten-minute-old SQL file is the *last* resort, not the first. First reboot the Modal endpoint and fix forward, then generate a current export. The old file is for the case where the database itself is destroyed — a bad migration, a deletion, an attack — in which case restore from the most recent export and scrape what remains from the audit log, which is append-only and therefore reconstructs the sequence of changes even when the current-state tables are gone.

**Graceful failure.** If Modal is unreachable, the static site says so plainly and tells the person what to do instead. It never loads indefinitely. This is a minor inconvenience for registration and a serious problem for live events, so live events get named fallbacks: Open Certamen participants and organizers switch to a Google Sheets bracket, with a script that fills it from registration data; live grading switches to a backup grading spreadsheet.

**Everything runs elsewhere.** Every worker is a standalone script that takes a `.db` file and arguments. Exporting, grading, invoice generation, and awards tabulation must all be runnable in a Google Colab within minutes by someone who has never seen the codebase. Test this by actually doing it once before convention, not by assuming it.

**Drift.** Once you fall back to spreadsheets, the database and the spreadsheet diverge, and reconciling them is the hard part. Build a converter that reads an exported Excel file and produces either a SQL import or, better, a **diff against the current database** so a human decides what to apply. Colloquia time is the natural window to reconcile. Write the detailed reconciliation procedure before convention; do not plan to figure it out on the day.

**Announcements.** For real emergencies — a schedule change, a room change, a pig on campus — an admin must be able to put a banner on every page in under a minute without touching code. The banner lives in the `announcements` table and is editable from the dashboard. As a second layer, `frontend/public/announcement.json` is committed to the repository and editable from the GitHub web UI, so a banner can be published even with Modal completely down; the live value overrides the static one when the API is reachable.

**Quota.** Watch the Turso usage page during convention. A `BLOCKED` error stops the database and cannot be resolved by paying, so a query regression is an outage. Anything that changes a query goes through the `EXPLAIN QUERY PLAN` check in CI.

**Demo day.** Warm the container before the board meeting. Rehearse the full flow against production at least twice, and have a recorded screen capture as a fallback if the venue's network fails.

# **Continual paranoia**

Write the code so that a future commissioner, dropped into a fresh context with no history, can read the repository and understand the whole system. Comment the *why*, not the *what*. Keep all SQL in one place. Keep the schema documented alongside the migrations. Prefer boring, obvious code to clever code, because the next person to touch this will be a high school student in a hurry.

While building, continually brainstorm ways this can go wrong, and write those down as they occur rather than at the end. What happens when a sponsor pastes the same roster twice? When two sponsors from one school edit simultaneously? When a delegate's code is regenerated while they have an open session? When a school withdraws after paying? When the invoice fee changes mid-cycle? When a name contains a character the parser has never seen? Assume every one of these will actually happen.
