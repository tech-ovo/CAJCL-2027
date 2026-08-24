# Running the demonstration

For the CAJCL board, August 29th 2026. About **twelve minutes** of driving, and
it is built around one moment: pasting a messy roster and watching it come out
right.

Read this once the day before, then follow the numbered steps live. Nothing
here needs improvisation.

---

## The morning of

Three things, in this order. None takes more than a minute.

**1. Wake it up.** Sign in as an administrator → **Settings → Operations →
Keep warm for 6 hours**. Modal sleeps when idle, and the first thing the board
sees should not be a loading message however well designed it is.

**2. Load fresh demonstration data.** This wipes and rebuilds everything:

```powershell
modal run backend/app.py::setup --reset
```

**3. Put the board back.** The reset in step 2 **deletes every real board
account**, because it rebuilds the database from the seed. This puts them back:

```powershell
modal run backend/app.py::board --create-schools
```

> **The order matters and the reason is worth knowing.** `setup --reset` drops
> the tables. Anyone added by `::board` is gone, and their codes with them —
> codes are stored scrambled and cannot be recovered, so everyone gets a new
> one. Run these two together, in this order, or not at all.
>
> If the board have already been given codes and you do not want to change
> them, **do not run `--reset`.** Demonstrate against the data that is there.

**4. Open two browser windows.** One signed in as a sponsor, one signed in as
an administrator. Switching accounts live is the slowest thing you can do in
front of an audience.

**5. Print `demo-codes.txt`** on paper, and have the QR sheet for one delegate
ready to scan with a phone.

---

## The script

### 1. The welcome page — 30 seconds

Start signed out. Point out the theme, the dates, the venue, and the four live
numbers.

> "These numbers come from the live database. The page you are looking at was
> built with them already in it, so it loads instantly even when the server is
> asleep."

Do not dwell. The board is here for registration.

### 2. Sign in as a sponsor — 1 minute

Type a sponsor code from `demo-codes.txt`. Then, on your phone, **scan a
delegate's QR** from the printed sheet and hold it up.

> "Delegates are eleven and up, and many have no email address. There are no
> passwords and no accounts to create. The sponsor hands them a sheet, and
> scanning it signs them in."

### 3. The roster paste — 4 minutes, and this is the demonstration

Go to **Roster → Paste a roster**. Paste this in:

```
Aurelia Vance	9	HS-1
Marcus DeLuca	10	HS-2
Priya Raghunathan	11	HS-3
Chen, Wei-Lin	9	HS-1
Okonkwo, Ngozi A.	12	HS-Adv
Sofia van der Berg	10	HS-2
Jamal Washington III	11	HS-3
Elena Marie Castellanos	9	HS-1
theodore huang	10	HS-2
MIRANDA OYELARAN	12	HS-Adv
Rafael Ortiz-Mendoza	11	HS-3
Yuki Tanaka	9	HS-1
1. Amara Nwosu	10	HS-2
2. Dmitri Volkov, Jr.	12	HS-Adv
3. Isabella Rossi	11	HS-3
Aurelia Vance	9	HS-1
```

**Those are real tab characters.** Copy the block from this file rather than
retyping it, or paste the same thing out of a spreadsheet — it is exactly what
three columns of Excel produce.

Then walk the preview, slowly. Every one of these is deliberate:

| Line | What it shows |
| --- | --- |
| `Chen, Wei-Lin` | `Last, First` read correctly — first name Wei-Lin |
| `Okonkwo, Ngozi A.` | inverted **and** a middle initial |
| `Sofia van der Berg` | `van der` stays with the surname, not the middle name |
| `Jamal Washington III` | a generational suffix in its own field |
| `theodore huang` | typed lower case, filed as Theodore Huang |
| `MIRANDA OYELARAN` | typed shouting, filed as Miranda Oyelaran |
| `1. Amara Nwosu` | numbered list, numbers discarded |
| `Dmitri Volkov, Jr.` | a comma that is **not** `Last, First` |
| `Aurelia Vance` twice | the only row flagged, as a duplicate |

> "Fifteen students, four formats, one paste. The only thing it complains about
> is the genuine mistake — the same student entered twice. Nobody had to clean
> the spreadsheet first, because nobody ever does."

Fix the duplicate by unticking it, then commit. Land on the roster.

**If somebody asks whether it is just guessing:** it is not, and the failure
mode is deliberate. Anything ambiguous is flagged for the sponsor rather than
guessed at, and every row is editable before it is committed. Nothing is
written until they press the button.

### 4. Double-click the commit — 20 seconds

Press the commit button twice, fast.

> "One roster. The commit carries a signed key, and the second press finds the
> first one's result instead of importing again. A sponsor on hotel wifi
> double-clicking is the most likely accident there is."

### 5. A delegate's activity sheet — 2 minutes

Switch to the delegate window. Open **Activities**.

- Change **Latin level** and watch the tests re-gate instantly, with no page
  load. *"The rules came down with the page. This works on a phone in a car
  park."*
- Point at a **disabled** test with its reason. *"It says why. A delegate who
  cannot find Grammar 2 assumes the site is broken and emails their sponsor."*
- Tick something and show **"Unsaved changes"** in red. Save.

### 6. The invoice — 1 minute

**Invoice.** Point at the free-adult line and the arithmetic.

> "One adult free per ten delegates, and the sum is on the page. A sponsor who
> cancels a student and sees the bill move by the wrong amount can find out why
> here, instead of emailing the registration chair."

Then show the **exempt** chapter's invoice, which explains itself in words
rather than showing a blank.

### 7. The chair's view — 2 minutes

Switch to the admin window. **Chapters.**

- Every chapter, its size, how far along it is, what it owes — *"one query, no
  matter how many chapters."*
- Click a chapter's **Roster**, then **Sign in as the sponsor**. Show the
  banner naming both people. *"Read-only, thirty minutes, and it is in the
  log."*
- **Log.** Scroll it. *"Every change, in a full sentence, with who did it. The
  log cannot be edited — the database refuses."*

### 8. Settings — 1 minute, the closing argument

**Settings → Values**, then **Printed wording**.

> "The fees, the deadlines, the theme, the venue, and the words on the printed
> packet are all in here. Next year's commissioners change them from this page.
> They do not touch the code, and they do not need us."

That is the note to end on. This site is meant to be inherited.

---

## Questions you should expect

**"What about student privacy?"**
Delegate emails are never collected. Medical forms and waivers are paper,
scanned by the sponsor into their own Drive folder that no code here reads. The
site records only that a form arrived, never what is in it.

**"Is this real student data?"**
No. Every chapter, delegate and parent on the site is invented — the banner at
the top says so on every page. The only real people are the board members in
the room.

**"What happens if it goes down at convention?"**
There is a local copy that runs with no internet, and every export is an
ordinary SQLite file that opens in free tools. `docs/RUNBOOK.md`.

**"Who pays for it?"**
Nobody. All three services are on free tiers with a large margin — measured,
not guessed: `docs/RISKS.md` has the numbers.

**"Can we have a feature X?"**
`docs/TODO.md` has what is not built yet, with estimates. Write it down rather
than promising it live.

---

## If it breaks

**Do not debug in front of the board.**

1. Switch to the **local copy** already running in a second window.
2. Switch to the **screen recording**.
3. Fix it afterwards.

Have both ready before you start. It costs nothing and turns a disaster into a
shrug.
