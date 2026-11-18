# Certamen Arena

Certamen practice for the CAJCL convention site, served at `/certamen/`.
React + Vite; questions, user profiles, and the leaderboard live in a separate
Turso database (see `src/services/tursoService.ts`).

```bash
npm install
npm run dev      # http://localhost:3000
npm run lint     # tsc --noEmit
npm run build    # writes ../frontend/public/certamen/ — commit the result
```

## Styling

The arena has no design system of its own. `vite.config.ts` injects links to
the convention site's `../tokens.css` and `../app.css` (and its fonts and
favicon) into the built page, and serves those files from `frontend/public`
during `npm run dev`. Components use the site's classes — `.masthead`, `.nav`,
`.btn`, `.field`, `.table`, `.tabula`, `.stats`, `.dialog` — and
`src/index.css` holds only the arena-specific pieces, written against the same
tokens. Never put a colour literal in it; `backend/tests/test_frontend.py`
checks the built CSS.

The theme toggle shares the site's `localStorage` key, so light/dark carries
across both.
