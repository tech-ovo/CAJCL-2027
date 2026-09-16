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
- `certamen-bot/` — Certamen practice arena, React 19 + Vite 6 (no Tailwind,
  no icon library). `npm run build` outputs to `frontend/public/certamen/`
  (committed). The built page links the site's `../tokens.css` and
  `../app.css` via a plugin in `vite.config.ts`; a dev middleware serves them
  from `frontend/public`. Components reuse site classes; `src/index.css` has
  only arena-specific rules, token-only. Sections are hash routes
  (`#/arena`, `#/stats`, `#/leaderboard`, `#/bank`, `#/settings`); the
  profile editor is a native `<dialog>`.
- `apps-script/`, `scripts/`, `docs/`.

## Checks
- `python -m pytest backend/tests -q` (on this machine the installed starlette
  lacks `StarletteDeprecationWarning`, which `pytest.ini` references; run
  single files with `-p no:warnings` until that is fixed).
- `backend/tests/test_frontend.py` fails on any hex colour outside
  `tokens.css`, including the Certamen build's CSS.
- `cd certamen-bot && npm run lint && npm run build`.

## Known loose ends
- `certamen-bot/bun.lock` is stale (still lists tailwind and lucide-react);
  npm's `package-lock.json` is current.
