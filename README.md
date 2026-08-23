# CAJCL 2027

The 72nd California Junior Classical League State Convention — University High
School, Irvine, March 12–13, 2027.

**Going live?** [`docs/DEPLOY.md`](docs/DEPLOY.md) — about 90 minutes, Modal +
Turso + GitHub Pages, no Apps Script needed.

**Something broken?** [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — written for someone
who did not build this and may be panicking.

---

## Start here

```bash
pip install -r backend/requirements.txt
pip install pytest httpx esprima fonttools brotli

export CODE_PEPPER="anything-for-local-work"
python scripts/seed.py --db dev.db --reset      # 12 chapters, ~150 delegates
uvicorn backend.api:app --reload --port 8000

# in a second terminal
python -m http.server 8080 --directory frontend/public
```

Open <http://localhost:8080>. The seed prints the access codes you need.

Run the tests with `python -m pytest backend/tests -q`.

---

## What lives where

```
frontend/public      the site. Plain ES modules, no bundler, no build step.
  tokens.css         EVERY colour, font, and spacing step. The only one.
  app.css            the design system
  js/                one module per page
  fonts/             self-hosted woff2 subsets, Latin Extended-A included
backend
  api.py             every endpoint. No Modal import, so it runs anywhere.
  app.py             the thin Modal wrapper: two images, three crons
  lib/               the actual logic, one concern per file
  queries/           ALL SQL. Nothing anywhere else builds a statement.
  migrations/        numbered, forward-only
  workers/           fat-image jobs; each runs standalone in a Colab
  tests/
apps-script          the Drive puppet, mirrored with clasp
scripts              seed, exports, font build, query-plan check, usage
docs                 the specification, the risks, and the runbook
```

---

## The five rules

Everything here follows from these. If a change fights one of them, the change
is wrong.

**1. Reads are the only quota that can be blown, and only by bad queries.**
In Turso a "row read" is a row *scanned*. Exceeding the monthly quota returns
`BLOCKED` and the database stops answering — you cannot pay your way out during
convention. So: every index is declared in the migration that creates its table,
every list view is one query with a JOIN, aggregates are never computed live,
and CI runs `EXPLAIN QUERY PLAN` over every query and fails on a `SCAN` of any
table over 200 rows.

**2. Brand and layout are code. Convention operations are data.**
Next year's commissioners *will* edit the palette, the typeface, and the
masthead — that is what `tokens.css` is for. They must never have to edit code
to change a fee, a deadline, a venue, the activity catalog, or a line of printed
prose. If running a convention requires a deploy, something is in the wrong
layer.

**3. Nothing changes data without an audit entry, in the same transaction.**
Enforced in `backend/lib/db.py`, not by reviewer discipline: a transaction that
mutated and did not audit refuses to commit.

**4. Scopes reach a person only through roles.**
`person_roles → roles → role_scopes`. There is no `person_scopes` table and
there must never be one — every authorization test checks that path and only
that path.

**5. No real student data, ever.**
The repository is public and the demo is projected in a room. Every name in the
seed is invented. Delegates have no email addresses and the database refuses to
store one. Medical forms and waivers never touch this system.

---

## The things most likely to break

| | |
|---|---|
| **A sponsor commits a roster twice** | The single most damaging accident available to them. Prevented by a `UNIQUE` idempotency key, not by an application check — an application check loses to two concurrent requests. |
| **The theme's macrons vanish** | `ā ē ī ō ū` live in Latin Extended-A, which default font subsetting silently drops, and the failure is tofu boxes on the one line the design is built around. `scripts/build_fonts.py` fails the build on it. |
| **A deadline is an hour wrong** | Deadlines are UTC instants meaning "end of day in California". Always set them through the dashboard, which computes the offset — including whether the date is PST or PDT. |
| **One sponsor reads another school's roster** | The realistic attack. Every endpoint is hit by tests with a wrong-scope and a wrong-school credential, and a route added without a guard fails the suite. |

---

## Measured, not assumed

Extrapolated to 50 chapters, 1,000 delegates and 150 adults
(`python scripts/measure_usage.py --db dev.db`):

| | Projected | Free tier | Headroom |
|---|---|---|---|
| Storage | 2.2 MB | 5 GB | 2,200× |
| Reads, normal month | 434,000 | 500 M | 1,150× |
| Reads, convention month | 1.7 M | 500 M | 288× |

Every page load is an indexed lookup. The public welcome page costs **one** row
read; a thirty-person roster costs about thirty-four.

---

## Reading the code

Start with `docs/structure.md` for what the site does, then
`backend/queries/` for every question it asks the database. Both are meant to
be read straight through.

Comments explain *why*, never *what*. Where a comment sounds emphatic, it is
usually marking a place where the obvious approach is wrong and something
already went wrong once.
