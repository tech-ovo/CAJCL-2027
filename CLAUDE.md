# CAJCL 2027 — notes for Claude

The 72nd CAJCL State Convention site. Read `README.md` first (layout, the five
rules), then `docs/design.md` for the visual rules.

## Layout
- `frontend/public/` — the site. Plain ES modules, no build step.
  `tokens.css` is the ONLY place colours/fonts/spacing are defined; `app.css`
  is the design system (`.masthead`, `.nav`, `.btn`, `.field`, `.table`,
  `.tabula`, `.stats`, `.dialog`, `.empty`, `.waking`, …). Light/dark via
  `data-theme` on `<html>` + `localStorage["theme"]`.
- `backend/` — FastAPI (`api.py`), Modal wrapper (`app.py`), SQL in `queries/`.
  `app.py` attaches two Modal secrets: `cajcl-2027` (database, pepper, …) and
  `apps-script` (only `APPS_SCRIPT_URL`/`APPS_SCRIPT_KEY`); a missing one fails
  the deploy. `modal run backend/app.py::doctor` shows what the container sees.
  Every route needs a `guard(...)` AND a row in `tests/test_endpoints.py`
  `ROUTES`; every named query needs a Python caller; a new migration needs
  `python scripts/checksum_migrations.py`; a new table needs a block in
  `docs/schema.md` and a size entry in `scripts/check_query_plans.py`.
- Pre-convention contests (migration 008): `lib/contests.py` (rules, divisions,
  word counts, scoring, ranking), `lib/drive.py` (Apps Script puppet client, or
  `DRIVE_LOCAL_DIR` folder stand-in locally/tests), `queries/contests.sql`,
  endpoints under `/me/contests`, `/sponsor/contests`, `/judge/...`,
  `/admin/contests/...`. Pages: `js/pages/contests.js` (`#/contests`,
  `#/chapter-contests`, `#/contest-submissions`) and `js/pages/judging.js` (`#/judging[/id]` for
  judges, `#/contest-results[/id[/rubric]]` for Academics/Awards chairs).
  `#/contest-submissions` (nav "Submissions" for registration chairs) lists
  every entry with names and chapters, no scores, from
  `GET /admin/contests/submissions`. Sponsors see their delegates' entries on
  `#/chapter-contests` and download files from
  `GET /sponsor/contests/entries/{id}/file` (entry's own school checked).
  Scope `judge` (role `contest_judge`) is global but NOT in
  `auth.ADMIN_SCOPES`; judging endpoints take `judge` only and
  `_judge_only()` refuses anyone holding `academics`. Digital Art divisions
  are by Latin level (MS-I..MS-III, HS-I..HS-III, HS-Advanced);
  divisions have no editing screen. Judges never receive names, chapters or original file
  names; files come back through the API as `Entry {id}.ext`. File bytes
  travel base64 in JSON (20 MB cap; the body-size middleware exempts only
  `POST /me/contests/{id}`). Settings: `deadline.contests`,
  `drive.contests_root`.
- `certamen-bot/` — Certamen practice arena, React 19 + Vite 6 (no Tailwind,
  no icon library). `npm run build` outputs to `frontend/public/certamen/`
  (committed). Connected to a separate Turso database via Modal endpoints (`/certamen/...`)
  and `src/services/tursoService.ts` (no Google Sheets); credentials live in Modal secrets
  (`TURSO_CERTAMEN_DATABASE_URL`, `TURSO_CERTAMEN_AUTH_TOKEN`) with fallback to local `certamen.db`.
  Questions are flattened to tossup format. The built page links the
  site's `../tokens.css` and `../app.css` via a plugin in `vite.config.ts`; a dev middleware
  serves them from `frontend/public`. Components reuse site classes; `src/index.css` has
  only arena-specific rules, token-only. Sections are hash routes
  (`#/arena`, `#/stats`, `#/leaderboard`, `#/bank`, `#/settings`); the
  profile editor is a native `<dialog>`.
- `apps-script/`, `scripts/`, `docs/`. Bulk question import: `python scripts/import_certamen_questions.py --file <path.json|path.csv>`.

## Checks
- `python -m pytest backend/tests -q` (on this machine the installed starlette
  lacks `StarletteDeprecationWarning`, which `pytest.ini` references; run
  single files with `-p no:warnings` until that is fixed).
- `pip install esprima` or ~24 frontend tests skip silently. esprima 4 cannot
  parse `??` or `?.`, so the site's JS avoids them.
- `python scripts/check_query_plans.py`.
- `backend/tests/test_frontend.py` fails on any hex colour outside
  `tokens.css`, including the Certamen build's CSS.
- `cd certamen-bot && npm run lint && npm run build`.

## Known loose ends
- Contest file uploads wait on deploying `apps-script/Code.gs` (now with a
  `fetch` op; the HMAC string is `ts.op.folderId.name.fileId`) — see
  `docs/TODO.md` §2.
- `certamen-bot/bun.lock` is stale (still lists tailwind and lucide-react);
  npm's `package-lock.json` is current.
