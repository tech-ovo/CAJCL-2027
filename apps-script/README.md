# The Drive puppet

Roughly 160 lines that will essentially never change.

## Why it exists

Only Apps Script can act as Timothy's Google identity and write to his personal
Drive under his 5 TB quota. Modal cannot, absent domain-wide delegation. That is
the entire justification for this component. Nothing else belongs here.

## What it does

Five operations — `upload`, `fetch`, `list`, `mkdir`, `trash` — and it holds no
configuration. Folder IDs, filenames, and retention rules all travel in the
request payload from Modal. Every request carries an HMAC signature and a
timestamp, and anything older than five minutes is rejected. The signed string
is `ts.op.folderId.name.fileId`; `backend/lib/drive.py` builds the same one.

`upload` files pre-convention contest entries under the automated contest
root (Settings → *Drive folder ID for contest entries*), one folder per
contest and then per chapter. `fetch` reads one back so a judge can see an
entry through the site without being shared the folder, whose chapter
subfolders would say whose it is. Apps Script caps a request at about 50 MB,
which is why the site caps an upload at 20 MB (base64 adds a third).

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

## Setup, start to finish

About an hour the first time. Do every step signed in as **the Google account
that owns the Drive** the entries should live in (the convention Workspace
account). The script runs *as that account*, so the folder and the script must
belong to the same one.

### 1. Make the contest folder

1. In Google Drive, create a folder, e.g. **CAJCL 2027 — Contest entries**.
   Nothing else goes in it, and it is **not** one of the per-school packet
   folders.
2. Open it. The address is `https://drive.google.com/drive/folders/<FOLDER ID>`.
   Copy the ID; it is needed in step 6.
3. Share it (Viewer) with the Academics and Awards chairs if they want to
   browse it directly. **Never share it with judges**: the subfolders are named
   after chapters and the files after students. The site creates the
   subfolders itself — one per contest, then one per chapter.

### 2. Create the script project

1. Go to <https://script.google.com> → **New project**. Rename it
   *CAJCL Drive puppet*.
2. Replace the contents of `Code.gs` with this repository's
   `apps-script/Code.gs`, exactly.
3. Project Settings (gear icon) → tick **Show "appsscript.json" manifest file
   in editor**. Back in the editor, replace `appsscript.json` with this
   repository's copy. It asks for the Drive scope only, runs as the deploying
   user, and allows anonymous callers — the HMAC signature is what keeps
   strangers out.
4. Project Settings → **Script Properties** → *Add script property*:
   - Property `SHARED_KEY`
   - Value: a long random string. Make one with
     `python -c "import secrets; print(secrets.token_hex(32))"`.
     Keep it; the same value goes into Modal in step 5. No spaces, no quotes.

(Or push with clasp instead of pasting — see *Keeping this file and the live
script in step* above. `.clasp.json` needs the script ID from Project
Settings → IDs, and clasp needs the Apps Script API turned on at
<https://script.google.com/home/usersettings>.)

### 3. Deploy it as a web app

1. **Deploy → New deployment**. Gear beside *Select type* → **Web app**.
2. Description: *v1*. **Execute as: Me**. **Who has access: Anyone**.
   If *Anyone* is not offered, the Workspace admin console forbids sharing
   outside the organisation; an admin has to allow it for this account
   (Admin console → Apps → Google Workspace → Drive and Docs → Sharing
   settings). *Anyone within cajcl.org* will not work — Modal is not signed in.
3. **Deploy**, then **Authorize access**, choose the account. Google warns the
   app is unverified: **Advanced → Go to CAJCL Drive puppet (unsafe) → Allow**.
   It is your own script asking for your own Drive.
4. Copy the **Web app URL**. It ends in `/exec` (on Workspace it may look like
   `https://script.google.com/a/macros/cajcl.org/s/…/exec`; that is fine).

### 4. Check it from your laptop, before Modal is involved

From the repository root, with the URL, the key and the folder ID from above:

```bash
APPS_SCRIPT_URL="https://script.google.com/macros/s/…/exec" \
APPS_SCRIPT_KEY="the-shared-key" \
python -c "
from backend.lib.drive import client
d = client()
folder = d.mkdir('<FOLDER ID>', '_connection test')
f = d.upload(folder, 'hello.txt', 'text/plain', b'hello')
assert d.fetch(f) == b'hello'
d.trash(f)
print('puppet OK')
"
```

A `_connection test` folder appears in Drive with `hello.txt` in its trash.
Delete the folder. If it fails, see *When it does not work* below.

### 5. Give the two values to Modal

The site reads `APPS_SCRIPT_URL` and `APPS_SCRIPT_KEY` from the Modal secret
`cajcl-2027`, beside the database settings.

- **Easiest:** modal.com → *Secrets* → `cajcl-2027` → *Edit* → add both keys →
  save.
- **Or from a terminal:** `modal secret create cajcl-2027 … --force` replaces
  the **whole** secret, so repeat every existing value from
  `docs/DEPLOY.md` step 2 and add the two new ones.

A running container keeps the secret it started with, so **deploy again**
(push to `main`, or `modal deploy backend/app.py`). Then
`modal run backend/app.py::doctor` should list both with their lengths.

### 6. Tell the site where the folder is

Migration 008 already sets **Drive folder ID for contest entries** to
`1Oh8odNUmX_yCxCjIl1zwuHIdqx8VWof1`. If the folder from step 1 is a different
one, sign in with an administrator code → **Settings → Values** → under
*Operations*, replace the ID → **Save settings**. That value, not the one in
the migration, is what the site uses once the database exists. While you are
there, set **Deadlines → Pre-convention contests due** to the date in the
Convention Book.

### 7. Try it for real

1. Sign in as a delegate → **Contests** → Digital Art/Poster → upload a small
   PNG. It should say *Entered*, and Drive should now hold
   `Digital Art/Poster / 07 <Chapter> / <Last>, <First>.png`.
2. Settings → Roles → give an adult the **Contest Judge** role. Sign in as them
   → **Judging** → the entry shows as *Entry N* with the picture. Hand in a
   score.
3. As an Academics chair → **Contest results** → the entry is ranked, with the
   delegate's name.
4. Back as the delegate, **Withdraw**. The file moves to Drive's trash (a
   30-day undo; nothing here ever deletes permanently).

### Changing the script later

**Deploy → Manage deployments → pencil → Version: New version → Deploy.** This
keeps the URL. **Deploy → New deployment** makes a *new* URL, and Modal keeps
calling the old one — see below. After any change, run step 4 again.

### Limits worth knowing

- One request can carry about 50 MB. The site caps a file at 20 MB because
  base64 adds a third.
- Apps Script runs about 30 requests at once per account. On the evening of
  the deadline a burst beyond that fails with "Drive refused the request";
  nothing is saved and the student simply tries again.
- A signed request is good for five minutes, so a clock far out on the
  calling machine is refused.

### When it does not work

| The site or step 4 says | It means |
|---|---|
| "not switched on yet: the Drive connection is not configured" | `APPS_SCRIPT_URL` or `APPS_SCRIPT_KEY` is missing from the container. Step 5, then deploy. |
| "not switched on yet: no Drive folder is set" | Step 6. |
| "Drive refused the request: signature rejected" | The two keys differ — often a trailing space or newline in one of them. Or the calling clock is more than five minutes out. |
| "Drive refused the request: unknown op: fetch" | An older `Code.gs` is deployed. Paste the current one and publish a **new version**. |
| "Drive refused the request: … No item with the given ID" / "Access denied" | The folder ID is wrong, or the folder belongs to a different account from the one the script runs as. |
| "SHARED_KEY is not set" | Step 2.4 was skipped, or done in a different project. |
| "Drive did not answer (HTTP Error 401/403)" or "(Expecting value …)" | Google answered with a sign-in page instead of JSON: access is not *Anyone*, or the script needs authorising again (open the editor, run any function, accept). |
| Uploads worked yesterday and fail today | Someone used *New deployment*. Put the new URL in the Modal secret and deploy, or go back to the old deployment. |

## The failure nobody notices

Re-deploying can mint a **new URL**, and the old one then fails silently. If
exports stop appearing in Drive, check this first. See `docs/RUNBOOK.md`.
