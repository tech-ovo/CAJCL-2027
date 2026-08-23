# Going live for the August 29th board meeting

Modal + Turso + GitHub Pages. **Apps Script is not needed** — exports download
straight from the browser, and nothing else in the demo touches Drive.

Budget about **90 minutes** the first time, then rehearse twice.

---

## 1. Turso — 15 minutes

```bash
curl -sSfL https://get.tur.so/install.sh | bash
turso auth signup
turso db create cajcl-2027
turso db show cajcl-2027 --url          # -> libsql://cajcl-2027-<org>.turso.io
turso db tokens create cajcl-2027       # -> the auth token
```

Create a second database now, while you are thinking about it:

```bash
turso db create cajcl-2027-staging
```

The free tier allows 100 databases. Having a staging one costs nothing and means
you never test a migration against the database the board is about to look at.

## 2. Modal — 10 minutes

```bash
pip install modal
modal setup                              # opens a browser
```

Create the secret. **These are the only secrets the demo needs.**

```bash
modal secret create cajcl-2027 \
  CODE_PEPPER="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  TURSO_DATABASE_URL="libsql://cajcl-2027-<org>.turso.io" \
  TURSO_AUTH_TOKEN="<the token from step 1>" \
  CAJCL_ENV="production"
```

**Save the `CODE_PEPPER` somewhere you will not lose it.** Every access code in
the database is hashed with it. Lose it and nobody can ever sign in again; there
is no recovery, by design.

Optional, for the usage page — it degrades gracefully without them:

```
TURSO_PLATFORM_TOKEN=...   TURSO_ORG=...   TURSO_DB_NAME=cajcl-2027
```

## 3. Migrate and seed — 5 minutes

```bash
export TURSO_DATABASE_URL="libsql://cajcl-2027-<org>.turso.io"
export TURSO_AUTH_TOKEN="..."
export CODE_PEPPER="<the same pepper you put in Modal>"

python -m backend.lib.migrate
python scripts/seed.py --reset
```

The seed prints every access code you need and writes them to
`demo-codes.txt`. **Print that page.** The codes are regenerated on every seed,
so a stale copy from a rehearsal will not work.

## 4. Deploy the API — 5 minutes

```bash
modal deploy backend/app.py
```

Note the URL it prints — something like
`https://<org>--cajcl-2027-web.modal.run`. Check it:

```bash
curl https://<org>--cajcl-2027-web.modal.run/health
curl https://<org>--cajcl-2027-web.modal.run/public/stats
```

## 5. Point the frontend at it — 5 minutes

**Two files, and both matter.**

`frontend/public/config.js` — replace the placeholder:

```js
: "https://<org>--cajcl-2027-web.modal.run",
```

`backend/api.py` → `ALLOWED_ORIGINS` — add your real GitHub Pages origin:

```python
"https://<your-github-username>.github.io",
```

CORS will block every request from the published site until that origin is
listed, and the browser console is the only place it says so. Redeploy Modal
after changing it.

## 6. Publish the site — 10 minutes

```bash
python scripts/build_fonts.py            # writes the woff2 subsets
python scripts/build_snapshot.py         # bakes the numbers into index.html
```

Repository → Settings → Pages → Source: **GitHub Actions**. Then push to
`main`; `.github/workflows/deploy.yml` does the rest.

Add these repository secrets first (Settings → Secrets → Actions):
`MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `TURSO_DATABASE_URL`,
`TURSO_AUTH_TOKEN`.

If the custom domain is not ready, delete `frontend/CNAME` and use the
`github.io` URL — remember it has to be in `ALLOWED_ORIGINS` either way.

## 7. Warm it — 1 minute, and do not skip this

Sign in as an admin → **Settings → Operations → Keep warm for 6 hours**, on the
morning of the meeting.

Modal scales to zero. The first request after an idle period takes several
seconds, and the very first thing the board sees should not be a loading
message — even a well-designed one.

## 8. Rehearse — twice

Against production, start to finish, with the projector if you can get it.
Time it. Then have someone else drive it while you watch, because you will
click past the thing that is broken.

---

## Pre-flight checklist

- [ ] `curl .../health` returns `{"ok": true}`
- [ ] The published site loads and shows real statistics, not dashes
- [ ] The **Demonstration data** banner is visible on every page
- [ ] Every code in `demo-codes.txt` signs in
- [ ] A QR from a printed sheet scans and signs in on a **phone**
- [ ] The roster prints; the invoice prints; the exempt invoice says why
- [ ] Warm is set past the end of the meeting
- [ ] `demo-codes.txt` is printed on paper
- [ ] A screen recording of the full flow exists as a fallback
- [ ] A local `dev.db` copy runs offline, in case the venue Wi-Fi fails

---

## Known gaps, so nothing surprises you live

- **PDF generation is untested end to end.** The print view works and is the
  same document. The first `/sponsor/packet.pdf` request cold-starts the fat
  image and takes 30+ seconds. **Demo the print view, not the PDF.**
- **`/admin/usage` shows a message, not numbers**, unless the three optional
  Turso platform variables are set.
- **The catalog editor is read-only.** Seeded correctly; the editing UI was cut.
- **Exports download from the browser.** Writing them to Drive needs Apps
  Script, which is not set up and is not needed for this.

---

## If it breaks during the meeting

Do not debug in front of the board.

1. **Switch to the local copy.** `uvicorn backend.api:app --port 8000` plus
   `python -m http.server 8080 --directory frontend/public`, with `config.js`
   pointed at `127.0.0.1:8000`. Everything works offline against `dev.db`.
2. **Switch to the recording.**
3. Fix it afterwards. `docs/RUNBOOK.md` has the diagnosis paths.

Having the local copy already running on the machine, in a second browser
window, costs nothing and turns a disaster into a shrug.
