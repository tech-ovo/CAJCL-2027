# The Drive puppet

Roughly 130 lines that will essentially never change.

## Why it exists

Only Apps Script can act as Timothy's Google identity and write to his personal
Drive under his 5 TB quota. Modal cannot, absent domain-wide delegation. That is
the entire justification for this component. Nothing else belongs here.

## What it does

Four operations — `upload`, `list`, `mkdir`, `trash` — and it holds no
configuration. Folder IDs, filenames, and retention rules all travel in the
request payload from Modal. Every request carries an HMAC signature and a
timestamp, and anything older than five minutes is rejected.

## What it must never touch

The scanned **medical forms and waivers**. Those live in a separate per-school
folder that the sponsor uploads to with their own Google account and shares
manually with the Convention Presidents. The database stores nothing but a URL
string, and no code in this repository reads that folder.

Keeping the two Drive roots physically separate is deliberate: it means no
future change to this automated path can widen access to minors' medical data by
accident. **Do not merge them for convenience.**

## Keeping this file and the live script in step

The copy here is synchronised with [clasp](https://github.com/google/clasp):

```
npm install -g @google/clasp
clasp login
clasp clone <scriptId>     # once
clasp pull                 # after editing in the web UI
clasp push                 # after editing here
```

`.clasprc.json` is gitignored because it holds OAuth credentials. `.clasp.json`
holds only the script ID and is safe to commit — copy `.clasp.json.example`.

A future commissioner who never touches a terminal can edit in the Apps Script
web UI and treat this copy as documentation and disaster recovery. If the two
drift, the web UI is the one that is running.

## Setup

1. **Script Properties** — set `SHARED_KEY` to a long random string. Put the
   same value in Modal Secrets as `APPS_SCRIPT_KEY`.
2. **Deploy** → New deployment → Web app, *execute as me*, *anyone with the
   link*.
3. Put the `/exec` URL in Modal Secrets as `APPS_SCRIPT_URL`.

## The failure nobody notices

Re-deploying can mint a **new URL**, and the old one then fails silently. If
exports stop appearing in Drive, check this first. See `docs/RUNBOOK.md`.
