# Database Schema, Natural Language Parser & API Reference Specification

**Platform:** 72nd Annual CAJCL State Convention Platform (`state.uhsjcl.org`)  
**Target Engine:** Turso / libSQL (SQLite-compatible)  
**Document Classification:** Technical Data Architecture, Parser Logic & API Specification  
**Audience:** Software Engineers, Database Administrators, System Integrators  

---

## 1. Database Architecture & Design Standards

- **Engine:** libSQL (distributed SQLite) hosted on Turso in `aws-us-east-1`.
- **Integrity Enforcements:** `PRAGMA foreign_keys = ON` executed on every connection.
- **Temporal Precision:** All timestamps stored in ISO-8601 UTC string format (`YYYY-MM-DDTHH:MM:SSZ`). Wall-clock conversions default to `America/Los_Angeles`.
- **Monetary Representation:** Stored strictly as signed 64-bit `INTEGER` cents ($140.00 = `14000`). Floating-point currency representation is forbidden.
- **Boolean Encoding:** Stored as `INTEGER` 0 or 1.
- **Lifecycle Immutability:** Identity records (`people`, `schools`) employ soft-deletion (`status = 'cancelled'`). Audit and financial ledger tables are strictly append-only.
- **Index Migration Rule:** Every index must be declared in the migration that creates its host table. Adding indexes to populated production tables is barred to prevent full table scans.

---

## 2. Core Relational Schema (DDL)

### 2.1 Configuration & Institutional Entities

```sql
CREATE TABLE settings (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  value_type  TEXT NOT NULL CHECK (value_type IN ('string','int','cents','bool','datetime','markdown')),
  label       TEXT NOT NULL,
  group_name  TEXT NOT NULL,
  sort_order  INTEGER NOT NULL DEFAULT 0,
  updated_at  TEXT NOT NULL,
  updated_by  INTEGER REFERENCES people(id)
);

CREATE TABLE schools (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL,
  level           TEXT NOT NULL CHECK (level IN ('MS','HS')),
  kind            TEXT NOT NULL DEFAULT 'chapter' CHECK (kind IN ('chapter','organization')),
  city            TEXT,
  drive_folder_id TEXT,
  billing_exempt  INTEGER NOT NULL DEFAULT 0,
  discount_cents  INTEGER NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
  discount_reason TEXT,
  status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','withdrawn')),
  notes           TEXT,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  checkin_note    TEXT,
  number          INTEGER,
  join_code       TEXT,
  join_open       INTEGER NOT NULL DEFAULT 1 CHECK (join_open IN (0, 1)),
  UNIQUE (name, level)
);
CREATE INDEX idx_schools_kind_status_level ON schools (kind, status, level);
CREATE UNIQUE INDEX idx_schools_join_code ON schools (join_code) WHERE join_code IS NOT NULL;
```

---

### 2.2 Identity & Access Control

```sql
CREATE TABLE people (
  id                    INTEGER PRIMARY KEY,
  school_id             INTEGER NOT NULL REFERENCES schools(id),
  person_type           TEXT NOT NULL CHECK (person_type IN ('delegate','adult')),
  adult_type            TEXT CHECK (adult_type IN ('sponsor','chaperone','scl','other')),
  adult_type_other      TEXT,
  first_name            TEXT NOT NULL,
  middle_name           TEXT,
  last_name             TEXT NOT NULL,
  suffix                TEXT,
  raw_name_input        TEXT,
  grade                 INTEGER CHECK (grade BETWEEN 6 AND 12),
  latin_level           TEXT CHECK (latin_level IN ('MS-1','MS-2','MS-3','HS-1','HS-2','HS-3','HS-Adv')),
  meal                  TEXT CHECK (meal IN ('regular','vegetarian','gluten_free')),
  cell_phone            TEXT,
  email                 TEXT,
  latin_knowledge       TEXT CHECK (latin_knowledge IN ('none','novice','intermediate','advanced')),
  availability_note     TEXT,
  guardian_name         TEXT,
  guardian_phone        TEXT,
  code_hmac             TEXT NOT NULL,
  code_prefix           TEXT NOT NULL CHECK (code_prefix IN ('SPO','DEL','VOL','ADM')),
  pepper_version        INTEGER NOT NULL DEFAULT 1,
  code_issued_at        TEXT NOT NULL,
  status                TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','cancelled','cancelled_paid')),
  cancelled_at          TEXT,
  forms_unlocked        INTEGER NOT NULL DEFAULT 0,
  created_at            TEXT NOT NULL,
  updated_at            TEXT NOT NULL,
  roster_import_id      INTEGER,
  board_title           TEXT,
  activity_sheet_waived INTEGER NOT NULL DEFAULT 0,
  school_seq            INTEGER,
  approval              TEXT NOT NULL DEFAULT 'approved' CHECK (approval IN ('approved','pending','denied')),
  CHECK (person_type = 'adult'    OR adult_type IS NULL),
  CHECK (person_type = 'delegate' OR (grade IS NULL AND latin_level IS NULL)),
  CHECK (person_type = 'adult'    OR (email IS NULL AND latin_knowledge IS NULL AND availability_note IS NULL)),
  CHECK (person_type = 'delegate' OR (guardian_name IS NULL AND guardian_phone IS NULL))
);
CREATE UNIQUE INDEX idx_people_code_hmac ON people (code_hmac);
CREATE INDEX        idx_people_school    ON people (school_id, status, person_type);
CREATE INDEX        idx_people_sort      ON people (school_id, last_name, first_name);

CREATE TABLE sessions (
  id                      INTEGER PRIMARY KEY,
  person_id               INTEGER NOT NULL REFERENCES people(id),
  token_hash              TEXT NOT NULL,
  impersonator_person_id  INTEGER REFERENCES people(id),
  impersonation_can_write INTEGER NOT NULL DEFAULT 0,
  created_at              TEXT NOT NULL,
  last_seen_at            TEXT NOT NULL,
  expires_at              TEXT NOT NULL,
  revoked_at              TEXT,
  user_agent              TEXT,
  ip_hash                 TEXT
);
CREATE UNIQUE INDEX idx_sessions_token  ON sessions (token_hash);
CREATE INDEX        idx_sessions_person ON sessions (person_id, revoked_at);

CREATE TABLE roles (
  id          INTEGER PRIMARY KEY,
  key         TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  description TEXT,
  is_system   INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL
);

CREATE TABLE role_scopes (
  role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  scope   TEXT NOT NULL CHECK (scope IN ('*','registration','academics','awards','sponsor','delegate','chapter','judge','activities')),
  PRIMARY KEY (role_id, scope)
);

CREATE TABLE person_roles (
  person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  role_id    INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  granted_by INTEGER REFERENCES people(id),
  granted_at TEXT NOT NULL,
  PRIMARY KEY (person_id, role_id)
);

CREATE TABLE sponsor_school_grants (
  id                   INTEGER PRIMARY KEY,
  person_id            INTEGER NOT NULL REFERENCES people(id),
  school_id            INTEGER NOT NULL REFERENCES schools(id),
  granted_by_person_id INTEGER REFERENCES people(id),
  granted_at           TEXT NOT NULL,
  note                 TEXT,
  UNIQUE (person_id, school_id)
);
CREATE INDEX idx_sponsor_grants_school ON sponsor_school_grants (school_id);

CREATE TABLE login_attempts (
  id                  INTEGER PRIMARY KEY,
  attempted_code_hmac TEXT NOT NULL,
  code_prefix         TEXT,
  ip_hash             TEXT NOT NULL,
  succeeded           INTEGER NOT NULL,
  attempted_at        TEXT NOT NULL
);
CREATE INDEX idx_login_attempts_ip   ON login_attempts (ip_hash, attempted_at);
CREATE INDEX idx_login_attempts_code ON login_attempts (attempted_code_hmac, attempted_at);
```

---

### 2.3 Registration, Forms & Competition Catalogs

```sql
CREATE TABLE form_submissions (
  id           INTEGER PRIMARY KEY,
  person_id    INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  form_type    TEXT NOT NULL CHECK (form_type IN ('student_activity','adult_registration')),
  status       TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','submitted')),
  submitted_at TEXT,
  updated_at   TEXT NOT NULL,
  UNIQUE (person_id, form_type)
);

CREATE TABLE paper_forms (
  person_id            INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  form_type            TEXT NOT NULL CHECK (form_type IN ('student_waiver','student_medical','adult_medical')),
  received             INTEGER NOT NULL DEFAULT 0,
  marked_by_person_id  INTEGER REFERENCES people(id),
  marked_at            TEXT,
  PRIMARY KEY (person_id, form_type)
);

CREATE TABLE catalog_categories (
  id             INTEGER PRIMARY KEY,
  key            TEXT NOT NULL UNIQUE,
  name           TEXT NOT NULL,
  description    TEXT,
  applies_to     TEXT NOT NULL CHECK (applies_to IN ('delegate','adult')),
  min_selections INTEGER,
  max_selections INTEGER,
  enforcement    TEXT NOT NULL DEFAULT 'none' CHECK (enforcement IN ('block','warn','none')),
  sort_order     INTEGER NOT NULL DEFAULT 0,
  active         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE catalog_items (
  id                     INTEGER PRIMARY KEY,
  category_id            INTEGER NOT NULL REFERENCES catalog_categories(id),
  name                   TEXT NOT NULL,
  description            TEXT,
  item_code              TEXT UNIQUE,
  eligible_latin_levels  TEXT,
  registration_scope     TEXT NOT NULL DEFAULT 'individual' CHECK (registration_scope IN ('individual','chapter')),
  max_sub_selections     INTEGER,
  min_latin_knowledge    TEXT CHECK (min_latin_knowledge IN ('none','novice','intermediate','advanced')),
  sort_order             INTEGER NOT NULL DEFAULT 0,
  active                 INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_catalog_items_cat ON catalog_items (category_id, active, sort_order);

CREATE TABLE catalog_item_options (
  id         INTEGER PRIMARY KEY,
  item_id    INTEGER NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  active     INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_catalog_options_item ON catalog_item_options (item_id, active);

CREATE TABLE activity_selections (
  id         INTEGER PRIMARY KEY,
  person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  item_id    INTEGER NOT NULL REFERENCES catalog_items(id),
  created_at TEXT NOT NULL,
  UNIQUE (person_id, item_id)
);
CREATE INDEX idx_act_sel_person ON activity_selections (person_id);
CREATE INDEX idx_act_sel_item   ON activity_selections (item_id);

CREATE TABLE activity_selection_options (
  selection_id INTEGER NOT NULL REFERENCES activity_selections(id) ON DELETE CASCADE,
  option_id    INTEGER NOT NULL REFERENCES catalog_item_options(id),
  PRIMARY KEY (selection_id, option_id)
);

CREATE TABLE chapter_entries (
  id                   INTEGER PRIMARY KEY,
  school_id            INTEGER NOT NULL REFERENCES schools(id),
  item_id              INTEGER NOT NULL REFERENCES catalog_items(id),
  team_label           TEXT NOT NULL DEFAULT 'A',
  notes                TEXT,
  created_by_person_id INTEGER REFERENCES people(id),
  created_at           TEXT NOT NULL,
  UNIQUE (school_id, item_id, team_label)
);
CREATE INDEX idx_chapter_entries_school ON chapter_entries (school_id);

CREATE TABLE adult_role_selections (
  person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  item_id    INTEGER NOT NULL REFERENCES catalog_items(id),
  created_at TEXT NOT NULL,
  PRIMARY KEY (person_id, item_id)
);
CREATE INDEX idx_adult_roles_item ON adult_role_selections (item_id);
```

---

### 2.4 Financial Ledgers, Counters & Audit Logging

```sql
CREATE TABLE payments (
  id                    INTEGER PRIMARY KEY,
  school_id             INTEGER NOT NULL REFERENCES schools(id),
  amount_cents          INTEGER NOT NULL,
  method                TEXT CHECK (method IN ('check','other')),
  reference             TEXT,
  received_on           TEXT,
  note                  TEXT,
  recorded_by_person_id INTEGER NOT NULL REFERENCES people(id),
  created_at            TEXT NOT NULL
);
CREATE INDEX idx_payments_school ON payments (school_id, created_at);

CREATE TABLE school_stats (
  school_id                INTEGER PRIMARY KEY REFERENCES schools(id),
  delegates_active         INTEGER NOT NULL DEFAULT 0,
  delegates_cancelled      INTEGER NOT NULL DEFAULT 0,
  delegates_cancelled_paid INTEGER NOT NULL DEFAULT 0,
  adults_active            INTEGER NOT NULL DEFAULT 0,
  adults_cancelled         INTEGER NOT NULL DEFAULT 0,
  adults_cancelled_paid    INTEGER NOT NULL DEFAULT 0,
  delegates_complete       INTEGER NOT NULL DEFAULT 0,
  adults_complete          INTEGER NOT NULL DEFAULT 0,
  discount_cents           INTEGER NOT NULL DEFAULT 0,
  amount_owed_cents        INTEGER NOT NULL DEFAULT 0,
  amount_paid_cents        INTEGER NOT NULL DEFAULT 0,
  updated_at               TEXT NOT NULL,
  meal_regular             INTEGER NOT NULL DEFAULT 0,
  meal_vegetarian          INTEGER NOT NULL DEFAULT 0,
  meal_gluten_free         INTEGER NOT NULL DEFAULT 0,
  meal_unanswered          INTEGER NOT NULL DEFAULT 0,
  meal_none                INTEGER NOT NULL DEFAULT 0,
  adults_sponsors          INTEGER NOT NULL DEFAULT 0,
  adults_chaperones        INTEGER NOT NULL DEFAULT 0,
  arrived_at               TEXT,
  delegates_pending        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE public_stats_cache (
  id            INTEGER PRIMARY KEY CHECK (id = 1),
  schools_ms    INTEGER NOT NULL,
  schools_hs    INTEGER NOT NULL,
  delegates     INTEGER NOT NULL,
  adults        INTEGER NOT NULL,
  updated_at    TEXT NOT NULL
);

CREATE TABLE audit_log (
  id                     INTEGER PRIMARY KEY,
  ts_utc                 TEXT NOT NULL,
  actor_person_id        INTEGER REFERENCES people(id),
  actor_role_snapshot    TEXT,
  impersonator_person_id INTEGER REFERENCES people(id),
  action                 TEXT NOT NULL,
  entity_type            TEXT,
  entity_id              INTEGER,
  school_id              INTEGER REFERENCES schools(id),
  summary                TEXT NOT NULL,
  changed_fields         TEXT,
  value_detail           TEXT,
  request_id             TEXT,
  ip_hash                TEXT
);
CREATE INDEX idx_audit_ts     ON audit_log (ts_utc);
CREATE INDEX idx_audit_school ON audit_log (school_id, ts_utc);
CREATE INDEX idx_audit_actor  ON audit_log (actor_person_id, ts_utc);

-- Enforce append-only integrity on audit_log
CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
WHEN NOT (
    OLD.id = NEW.id AND OLD.ts_utc = NEW.ts_utc
    AND (OLD.actor_person_id IS NEW.actor_person_id)
    AND (OLD.actor_role_snapshot IS NEW.actor_role_snapshot)
    AND (OLD.impersonator_person_id IS NEW.impersonator_person_id)
    AND OLD.action = NEW.action
    AND (OLD.entity_type IS NEW.entity_type)
    AND (OLD.entity_id IS NEW.entity_id)
    AND (OLD.school_id IS NEW.school_id)
    AND (OLD.changed_fields IS NEW.changed_fields)
    AND (OLD.value_detail IS NEW.value_detail)
    AND (OLD.request_id IS NEW.request_id)
    AND (OLD.ip_hash IS NEW.ip_hash)
    AND NEW.summary LIKE '%REDACTED%'
)
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;

CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;

CREATE TABLE roster_imports (
  id              INTEGER PRIMARY KEY,
  school_id       INTEGER NOT NULL REFERENCES schools(id),
  actor_person_id INTEGER NOT NULL REFERENCES people(id),
  idempotency_key TEXT NOT NULL UNIQUE,
  raw_text        TEXT NOT NULL,
  parsed_count    INTEGER NOT NULL,
  committed_count INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT NOT NULL
);

CREATE TABLE announcements (
  id         INTEGER PRIMARY KEY,
  body_md    TEXT NOT NULL,
  level      TEXT NOT NULL CHECK (level IN ('info','warning','critical')),
  active     INTEGER NOT NULL DEFAULT 0,
  starts_at  TEXT,
  ends_at    TEXT,
  created_by INTEGER REFERENCES people(id),
  created_at TEXT NOT NULL
);
CREATE INDEX idx_announcements_active ON announcements (active, starts_at);

CREATE TABLE documents (
  id          INTEGER PRIMARY KEY,
  key         TEXT NOT NULL UNIQUE,
  title       TEXT NOT NULL,
  body_md     TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  updated_by  INTEGER REFERENCES people(id)
);
```

---

### 2.5 Pre-Convention Contests & Double-Blind Judging

```sql
CREATE TABLE contests (
  item_id           INTEGER PRIMARY KEY REFERENCES catalog_items(id),
  key               TEXT NOT NULL UNIQUE,
  entry_kind        TEXT NOT NULL CHECK (entry_kind IN ('file','text','link')),
  entered_by        TEXT NOT NULL CHECK (entered_by IN ('delegate','chapter')),
  divisions         TEXT NOT NULL DEFAULT 'none' CHECK (divisions IN ('none','level','level_grade','latin_level')),
  accepted_types    TEXT,
  needs_title       INTEGER NOT NULL DEFAULT 0,
  min_words         INTEGER,
  max_words         INTEGER,
  words_penalty     INTEGER NOT NULL DEFAULT 0,
  max_chars         INTEGER,
  needs_translation INTEGER NOT NULL DEFAULT 0,
  must_attend       INTEGER NOT NULL DEFAULT 1,
  facets            TEXT,
  rules_md          TEXT,
  sort_order        INTEGER NOT NULL DEFAULT 0,
  places            INTEGER NOT NULL DEFAULT 3 CHECK (places BETWEEN 1 AND 20)
);

CREATE TABLE contest_entries (
  id                INTEGER PRIMARY KEY,
  item_id           INTEGER NOT NULL REFERENCES contests(item_id),
  school_id         INTEGER NOT NULL REFERENCES schools(id),
  person_id         INTEGER REFERENCES people(id),
  division          TEXT NOT NULL,
  title             TEXT,
  body_text         TEXT,
  translation       TEXT,
  link_url          TEXT,
  facets            TEXT,
  word_count        INTEGER,
  word_count_source TEXT CHECK (word_count_source IN ('counted','declared')),
  drive_file_id     TEXT,
  drive_folder_id   TEXT,
  original_name     TEXT,
  mime_type         TEXT,
  size_bytes        INTEGER,
  submitted_by      INTEGER NOT NULL REFERENCES people(id),
  submitted_at      TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_contest_entries_person  ON contest_entries (person_id, item_id) WHERE person_id IS NOT NULL;
CREATE UNIQUE INDEX idx_contest_entries_chapter ON contest_entries (school_id, item_id) WHERE person_id IS NULL;
CREATE INDEX        idx_contest_entries_item    ON contest_entries (item_id, division);

CREATE TABLE contest_ballots (
  id               INTEGER PRIMARY KEY,
  item_id          INTEGER NOT NULL REFERENCES contests(item_id),
  division         TEXT NOT NULL,
  facet            TEXT NOT NULL DEFAULT '',
  judge_person_id  INTEGER NOT NULL REFERENCES people(id),
  comment          TEXT,
  status           TEXT NOT NULL CHECK (status IN ('draft','submitted')),
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  UNIQUE (item_id, judge_person_id, division, facet)
);

CREATE TABLE contest_ballot_places (
  ballot_id  INTEGER NOT NULL REFERENCES contest_ballots(id) ON DELETE CASCADE,
  place      INTEGER NOT NULL CHECK (place > 0),
  entry_id   INTEGER NOT NULL REFERENCES contest_entries(id) ON DELETE CASCADE,
  PRIMARY KEY (ballot_id, place),
  UNIQUE (ballot_id, entry_id)
);

CREATE TABLE scores (
  id          INTEGER PRIMARY KEY,
  person_id   INTEGER REFERENCES people(id),
  school_id   INTEGER REFERENCES schools(id),
  item_id     INTEGER REFERENCES catalog_items(id),
  raw_score   REAL,
  placement   INTEGER,
  points      INTEGER NOT NULL DEFAULT 0,
  entered_by  INTEGER REFERENCES people(id),
  created_at  TEXT NOT NULL
);
CREATE INDEX idx_scores_person ON scores (person_id);
CREATE INDEX idx_scores_school ON scores (school_id);
CREATE INDEX idx_scores_item   ON scores (item_id);
```

### 2.6 At-Convention Photo Contest

Delegates upload one photo per category from their phones during convention;
the Activities chair (role `activities_chair`, scope `activities` — global but
narrow, NOT in `auth.ADMIN_SCOPES`) adds, edits, opens/closes and deletes
categories and sees every photo with its delegate and chapter (migration 012).
No image bytes are stored: the photo and a browser-made 480 px thumbnail live
in Drive under `drive.contests_root` → `Photo Contest/<category>` (thumbnails
in a `Thumbnails` subfolder), through the same Apps Script puppet as contest
entries. The browser re-encodes each photo (dropping location/camera
metadata); `lib/photos.py` strips any Exif/XMP/IPTC that survives. The two
folder ids are cached on the category after its first photo.

```sql
CREATE TABLE photo_categories (
  id               INTEGER PRIMARY KEY,
  name             TEXT NOT NULL,
  description      TEXT,
  accepting        INTEGER NOT NULL DEFAULT 1 CHECK (accepting IN (0, 1)),
  sort_order       INTEGER NOT NULL DEFAULT 0,
  drive_folder_id  TEXT,
  drive_thumbs_id  TEXT,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_photo_categories_name ON photo_categories (name COLLATE NOCASE);

CREATE TABLE photo_entries (
  id               INTEGER PRIMARY KEY,
  category_id      INTEGER NOT NULL REFERENCES photo_categories(id),
  person_id        INTEGER NOT NULL REFERENCES people(id),
  school_id        INTEGER NOT NULL REFERENCES schools(id),
  caption          TEXT,
  drive_file_id    TEXT NOT NULL,
  drive_thumb_id   TEXT,
  original_name    TEXT NOT NULL,
  mime_type        TEXT NOT NULL,
  size_bytes       INTEGER NOT NULL,
  submitted_at     TEXT NOT NULL,
  updated_at       TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_photo_entries_person   ON photo_entries (person_id, category_id);
CREATE INDEX        idx_photo_entries_category ON photo_entries (category_id, submitted_at);
```

---

### 2.7 The Convention Schedule and Olympika

Two things that meet in one table (migration 013). The **master schedule**
(`schedule_items`) is what everybody reads to know where to be; the Logistics
chair (role `logistics_chair`, scope `logistics`) adds, edits and deletes its
entries. **Olympika** is the athletics program; the Athletics Director (role
`athletics_director`, scope `athletics`) keeps its events, sees every sign-up,
and sets when heats and games are played. Both scopes are global but narrow
and NOT in `auth.ADMIN_SCOPES`: neither opens a roster.

Times are UTC instants like everywhere else (`lib/clock.py`); the editors send
a California date and `HH:MM` and the server converts, and every entry comes
back out as the same pieces (`date`, `start`, `end`), so no browser does
time-zone arithmetic.

**What the Director schedules is written onto the master schedule** by
`lib/olympika.sync_schedule`, in the same transaction as the change: one entry
per heat, and one entry per ROUND of a bracket ("Ultimate Frisbee —
Quarterfinals") spanning that round's games. Those rows are `source =
'olympika'`, keyed by `source_key` (`heat:12`, `round:3:2`), and the Logistics
chair cannot edit or delete them.

An event is `individual` (each delegate signs themself up; "Assign heats" deals
the entrants into the heats: sizes within one, a chapter's entrants spread over
different heats, lanes shuffled) or `team` (**one delegate signs up per team**
and is its captain, the only person recorded; "Form bracket" draws a
single-elimination bracket, byes to the top seeds, shuffled until the fewest
first-round games are between teams of one chapter). Only delegates who are
`active` and `approved` count in any list.

```sql
CREATE TABLE olympika_events (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL,
  description     TEXT,
  kind            TEXT NOT NULL CHECK (kind IN ('individual','team')),
  location        TEXT,
  signup_open     INTEGER NOT NULL DEFAULT 0 CHECK (signup_open IN (0, 1)),
  max_per_school  INTEGER CHECK (max_per_school IS NULL OR max_per_school >= 1),
  sort_order      INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_olympika_events_name ON olympika_events (name COLLATE NOCASE);

CREATE TABLE olympika_heats (
  id          INTEGER PRIMARY KEY,
  event_id    INTEGER NOT NULL REFERENCES olympika_events(id),
  number      INTEGER NOT NULL,
  label       TEXT,
  starts_at   TEXT,
  ends_at     TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_olympika_heats_event ON olympika_heats (event_id, number);

CREATE TABLE olympika_signups (
  id             INTEGER PRIMARY KEY,
  event_id       INTEGER NOT NULL REFERENCES olympika_events(id),
  person_id      INTEGER NOT NULL REFERENCES people(id),
  school_id      INTEGER NOT NULL REFERENCES schools(id),
  heat_id        INTEGER REFERENCES olympika_heats(id),
  lane           INTEGER,
  signed_up_at   TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_olympika_signups_event  ON olympika_signups (event_id, person_id);
CREATE INDEX        idx_olympika_signups_person ON olympika_signups (person_id);
CREATE INDEX        idx_olympika_signups_school ON olympika_signups (event_id, school_id);
CREATE INDEX        idx_olympika_signups_heat   ON olympika_signups (heat_id);

CREATE TABLE olympika_teams (
  id                 INTEGER PRIMARY KEY,
  event_id           INTEGER NOT NULL REFERENCES olympika_events(id),
  school_id          INTEGER NOT NULL REFERENCES schools(id),
  captain_person_id  INTEGER REFERENCES people(id),
  name               TEXT NOT NULL,
  seed               INTEGER,
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_olympika_teams_captain ON olympika_teams (event_id, captain_person_id);
CREATE UNIQUE INDEX idx_olympika_teams_name    ON olympika_teams (event_id, name COLLATE NOCASE);
CREATE INDEX        idx_olympika_teams_school  ON olympika_teams (event_id, school_id);
CREATE INDEX        idx_olympika_teams_person  ON olympika_teams (captain_person_id);

CREATE TABLE olympika_matches (
  id          INTEGER PRIMARY KEY,
  event_id    INTEGER NOT NULL REFERENCES olympika_events(id),
  round       INTEGER NOT NULL,
  slot        INTEGER NOT NULL,
  team_a_id   INTEGER REFERENCES olympika_teams(id),
  team_b_id   INTEGER REFERENCES olympika_teams(id),
  winner_id   INTEGER REFERENCES olympika_teams(id),
  score_a     INTEGER,
  score_b     INTEGER,
  starts_at   TEXT,
  ends_at     TEXT,
  field       TEXT,
  updated_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_olympika_matches_slot   ON olympika_matches (event_id, round, slot);
CREATE INDEX        idx_olympika_matches_team_a ON olympika_matches (team_a_id);
CREATE INDEX        idx_olympika_matches_team_b ON olympika_matches (team_b_id);
CREATE INDEX        idx_olympika_matches_winner ON olympika_matches (winner_id);

CREATE TABLE schedule_items (
  id                 INTEGER PRIMARY KEY,
  title              TEXT NOT NULL,
  description        TEXT,
  location           TEXT,
  starts_at          TEXT NOT NULL,
  ends_at            TEXT,
  published          INTEGER NOT NULL DEFAULT 1 CHECK (published IN (0, 1)),
  source             TEXT NOT NULL DEFAULT 'manual'
                       CHECK (source IN ('manual','olympika','potluck')),
  source_key         TEXT,
  olympika_event_id  INTEGER REFERENCES olympika_events(id),
  potluck_activity_id INTEGER REFERENCES potluck_activities(id),  -- migration 014
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL
);
CREATE INDEX idx_schedule_items_starts ON schedule_items (starts_at, id);
CREATE INDEX idx_schedule_items_event  ON schedule_items (olympika_event_id);
CREATE INDEX idx_schedule_items_potluck ON schedule_items (potluck_activity_id);
CREATE UNIQUE INDEX idx_schedule_items_key ON schedule_items (source_key) WHERE source_key IS NOT NULL;
```

In a bracket, `round` counts from 1 and `slot` from 0; the winner of (round,
slot) goes to (round + 1, slot / 2), as team A when slot is even and team B
when odd. A first-round game with one team is a **bye**: its winner is set when
the bracket is drawn and it is never timed or shown as a game. A redacted
captain's sign-ups are deleted, and so is their team unless a bracket has been
drawn, when the team stays nameless so the bracket keeps its shape.

---

### 2.8 The Activities Potluck

The Activities chair posts activities that need helpers; attendees tick the
ones they would help run on their own activity sheet (migration 014,
`lib/potluck.py`). An **adult's** pick is approved at once. A **delegate's**
pick is `pending` until their sponsor approves or declines it; a pick a
sponsor or chair enters for a delegate is approved at once. The Activities
chair sees only **approved** helpers per activity, by name and chapter.

`capacity` counts `pending` + `approved`, so a full activity stops taking picks
and a sponsor is never asked to approve a place that is not there; a declined
pick frees its place, and reversing a decline is refused if the activity has
filled. `open` stops NEW picks only. The signup table is not replaced whole on
a sheet save (the sponsor's decision lives in it); a declined pick stays on the
student's sheet until they pick it again (which makes it `pending`). Two picks
at the same time are a warning, never a block. An activity with a time is
written onto `schedule_items` (`source = 'potluck'`, `source_key` =
`potluck:<id>`) by `potluck.sync_schedule` in the same transaction; the
Logistics chair cannot edit it, and no person is named there.

```sql
CREATE TABLE potluck_activities (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL,
  description TEXT,
  location    TEXT,
  starts_at   TEXT,
  ends_at     TEXT,
  capacity    INTEGER CHECK (capacity IS NULL OR capacity > 0),
  open        INTEGER NOT NULL DEFAULT 1 CHECK (open IN (0, 1)),
  sort_order  INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_potluck_activities_name ON potluck_activities (name COLLATE NOCASE);

CREATE TABLE potluck_signups (
  person_id            INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  activity_id          INTEGER NOT NULL REFERENCES potluck_activities(id) ON DELETE CASCADE,
  status               TEXT NOT NULL CHECK (status IN ('pending','approved','declined')),
  requested_at         TEXT NOT NULL,
  decided_at           TEXT,
  decided_by_person_id INTEGER REFERENCES people(id),
  PRIMARY KEY (person_id, activity_id)
);
CREATE INDEX idx_potluck_signups_activity ON potluck_signups (activity_id, status);
```

Redaction deletes the person's signups (`potluck.forget_person`).

---

### 2.9 Site Pages (Google Docs)

Long text pages (hotel list, white book, registration instructions, …) are
written in Google Docs and published as static pages (migration 015,
`lib/pages.py`, `lib/htmlclean.py`, `scripts/build_pages.py`). The table holds
only the list of pages and where each one's converted HTML lives; the text is
in the Doc and in Drive. `POST /admin/pages/{id}/convert` (one page per request, so none runs past the 60 s web-function limit; the screen walks the list) has the Drive puppet
(`convert` op) turn each Doc into a cleaned HTML file named `page-<id>.html`
under `<drive.contests_root>/Site Pages/`, rewritten in place so its public
download link (`html_url`) never changes, then `POST /admin/pages/rebuild` asks GitHub to rebuild the site
(`workflow_dispatch` on `deploy.yml` with `site_only=true`). The build fetches
`GET /public/pages`, downloads each `html_url`, cleans it again with
`htmlclean`, saves its embedded pictures as files in `/p/img/`, and writes
`/p/<slug>.html` plus `/pages.json` (the navigation).
A failed conversion keeps the previous copy and records `sync_error`. Changing
`doc_url` to a different Doc clears `html_file_id`, `html_url` and `synced_at`.
Removing a page trashes its Drive copy and never touches the Doc.

```sql
CREATE TABLE site_pages (
  id           INTEGER PRIMARY KEY,
  slug         TEXT NOT NULL,           -- /p/<slug>.html
  title        TEXT NOT NULL,
  nav_label    TEXT NOT NULL DEFAULT '',
  show_in_nav  INTEGER NOT NULL DEFAULT 1 CHECK (show_in_nav IN (0, 1)),
  sort_order   INTEGER NOT NULL DEFAULT 0,
  doc_url      TEXT NOT NULL,
  doc_id       TEXT NOT NULL,
  html_file_id TEXT NOT NULL DEFAULT '',
  html_url     TEXT NOT NULL DEFAULT '',
  synced_at    TEXT,
  sync_error   TEXT NOT NULL DEFAULT '',
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_site_pages_slug ON site_pages (slug COLLATE NOCASE);
```

---

## 3. Natural Language Name Parser Specification

The ingestion engine processes raw unstructured text from chapter sponsors via `backend/lib/names.py`.

### Execution Pipeline (In-Memory Preview Only)
1. **Line Segmentation:** Split payload on line breaks (`\r\n`, `\n`). Strip leading/trailing empty lines.
2. **Noise Scrubbing:** Remove numbering markers (`1.`, `1)`, `(1)`), bullet symbols (`-`, `*`, `•`), surrounding quotation marks, and trailing semicolons/commas.
3. **Delimiter Detection:** Evaluate presence of tabs (`\t`) or commas. Lines matching `Last, First [Middle]` are extracted into discrete name components.
4. **Metadata Extraction:** Extract telephone strings, emails (discarded for delegates), standalone numbers (grades 6–12), and Latin levels (`MS-1..3`, `HS-1..Adv`).
5. **Generational Suffix Extraction:** Extract terminal generational designations (`Jr.`, `Sr.`, `II`, `III`, `IV`, `V`) to `suffix`.
6. **Compound Particle Folding:** Scan right-to-left. Lowercase surname particles are folded into the family name.  
   *Canonical Particle Constant:* `de`, `del`, `de la`, `de los`, `della`, `van`, `van der`, `van den`, `von`, `da`, `di`, `dos`, `du`, `la`, `le`, `bin`, `binte`, `ibn`, `al`, `ter`, `ten`.
7. **Token Allocation:**
   - 1 Token: Assigned to `last_name` with warning `single_token_name`.
   - 2 Tokens: Assigned to `first_name` and `last_name`.
   - 3 Tokens: Assigned to `first_name`, `middle_name`, `last_name` (**no warning**).
   - $\ge$ 4 Tokens: First token to `first_name`, terminal token to `last_name`, interior tokens to `middle_name`, flagged `multi_token_name` for review.
8. **Casing Normalization:** Retains mixed-case input. Re-cases via Title Casing only if input is uniformly all-uppercase or all-lowercase.

---

## 4. API Endpoint Reference

### 4.1 Authentication & Sessions
| Method | Route | Required Scope | Summary |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/redeem` | *Public* | Validates login token; returns session token and persona profile. Rate limited. |
| `POST` | `/auth/join` | *Public* | Chapter join code + name, grade, Latin level. Creates a **pending** delegate, signs them in, returns their login token once. Wrong codes rate limited apart from sign-in failures. |
| `GET` | `/auth/me` | *Any Session* | Returns active identity, assigned roles, scopes, and chapter metadata. |
| `POST` | `/auth/logout` | *Any Session* | Revokes current session token server-side. |
| `POST` | `/auth/impersonate`| `*` | Step-up authentication creating a 30-minute read-only support session. |

### 4.2 Sponsor & Chapter Operations
| Method | Route | Required Scope | Summary |
| :--- | :--- | :--- | :--- |
| `GET` | `/sponsor/roster` | `sponsor` | Retrieves single-query consolidated chapter roster and form completion statuses. |
| `POST` | `/sponsor/roster/parse`| `sponsor` | Executes in-memory parsing; returns preview array and signed idempotency token. |
| `POST` | `/sponsor/roster/commit`| `sponsor` | Commits previewed roster to database within an audited transaction. |
| `POST` | `/sponsor/people` | `sponsor` | Provisions single attendee and outputs initial login token. |
| `PATCH` | `/sponsor/people/{id}`| `sponsor` | Updates attendee directory fields (name, phone, grade). |
| `POST` | `/sponsor/people/{id}/cancel` | `sponsor` | Executes soft-cancellation; recalculates invoice and statistics. |
| `POST` | `/sponsor/people/{id}/regenerate-code` | `sponsor` | Reissues login token and revokes existing sessions. |
| `POST` | `/sponsor/people/{id}/approve` | `sponsor` | Approves a pending (join-code) student; they move into the invoice, public count and meal totals. |
| `POST` | `/sponsor/people/{id}/deny` | `sponsor` | Denies a pending student: runs the full redaction and leaves an anonymous `denied` row. |
| `POST` | `/sponsor/approve-all` | `sponsor` | Approves everyone currently pending in the chapter. |
| `POST` | `/sponsor/people/{id}/potluck/{activity}/approve` | `sponsor` | Approves a delegate's offer to help with a potluck activity. Reversing a decline is refused if the activity has filled. |
| `POST` | `/sponsor/people/{id}/potluck/{activity}/decline` | `sponsor` | Declines it; the delegate sees that on their sheet and may pick again. |
| `POST` | `/sponsor/potluck/approve-all` | `sponsor` | Approves every pick waiting in the chapter. |
| `POST` | `/sponsor/join/code` | `sponsor` | Replaces the chapter's join code; the old one stops working at once. |
| `POST` | `/sponsor/join/open` | `sponsor` | Closes or reopens joining without changing the code. |
| `GET` | `/sponsor/join-sheet` | `sponsor` | One-page printable handout: join code, QR, instructions. |
| `GET` | `/sponsor/packet` | `sponsor` | Generates HTML printable credential packet. |
| `GET` | `/sponsor/packet.pdf` | `sponsor` | Spawns asynchronous worker to generate WeasyPrint PDF packet. |
| `GET` | `/sponsor/invoice` | `sponsor` | Computes itemized invoice breakdown from `school_stats`. |

### 4.3 Attendee Forms & Contest Uploads
| Method | Route | Required Scope | Summary |
| :--- | :--- | :--- | :--- |
| `GET` | `/me/activity-sheet` | `delegate` | Retrieves personal exam and activity selections. |
| `PUT` | `/me/activity-sheet` | `delegate` | Replaces exam and event selections atomically; rejects post-deadline. |
| `GET/PUT`| `/me/adult-sheet` | `delegate` (adult)| Manages adult contact details, Latin knowledge, and volunteer roles. |
| `POST` | `/me/contests/{id}` | `delegate` | Ingests creative contest submission (file, text, or link); passes to Drive. |
| `GET` | `/me/photos` | `delegate` | Lists photo contest categories with the caller's own photo in each. |
| `POST/DELETE` | `/me/photos/{category_id}` | `delegate` | Uploads (or replaces, or re-captions) / withdraws the caller's photo; only while the category is accepting. Body carries the photo and thumbnail base64. |
| `GET` | `/me/photos/{category_id}/file?size=thumb` | `delegate` | Streams the caller's own photo or thumbnail. |
| `GET` | `/me/olympika` | `delegate` | Every Olympika event with the caller's own entry: their heat, lane and time, or their team's games. |
| `POST/PATCH/DELETE` | `/me/olympika/{event_id}` | `delegate` | Signs up for an individual event, or signs up a team (`team_name`; the caller is its captain); renames the caller's team; withdraws. Entering only while sign-up is open; a team cannot leave a drawn bracket. |

### 4.4 Double-Blind Judging
| Method | Route | Required Scope | Summary |
| :--- | :--- | :--- | :--- |
| `GET` | `/judge/contests` | `judge` | Summarizes contest groups, entry counts, and ballot completion statuses. |
| `GET` | `/judge/contests/{id}` | `judge` | Retrieves blinded contest entries (`Entry N`) stripped of student/school metadata. |
| `GET` | `/judge/entries/{id}/file`| `judge` | Streams contest creative file anonymized as `Entry {id}.ext`. |
| `PUT` | `/judge/contests/{id}/ballot` | `judge` | Submits ranked placement ballot for an event division. |

### 4.5 Administrative & Financial Governance
| Method | Route | Required Scope | Summary |
| :--- | :--- | :--- | :--- |
| `GET/POST`| `/admin/schools` | `registration` | Provisions or audits registered chapter institutions. |
| `GET` | `/admin/registration`| `registration` | Retrieves executive KPI overview (delegates, completion, balances). |
| `POST` | `/admin/payments` | `registration` | Ingests immutable financial payment transactions. |
| `POST` | `/admin/people/{id}/unlock-forms` | `registration` | Grants temporary post-deadline form modification access. |
| `GET/PUT`| `/admin/settings` | `*` | Updates global convention parameters (fees, deadlines, venue). |
| `GET` | `/admin/audit` | `*` | Queries paginated, filterable immutable system audit trail. |
| `GET` | `/admin/photos` | `activities` | Every photo category with its count, and every photo with delegate and chapter. |
| `POST` | `/admin/photos/categories` | `activities` | Adds a photo category (name, description, accepting). |
| `PATCH/DELETE` | `/admin/photos/categories/{id}` | `activities` | Edits / opens / closes a category; deletes it with all its photos (files trashed in Drive). |
| `GET/DELETE` | `/admin/photos/entries/{id}[/file?size=thumb]` | `activities` | Streams a photo or its thumbnail; takes a photo down. |
| `GET` | `/admin/potluck` | `activities` | Every potluck activity with its approved helpers (name and chapter) and a count still waiting on a sponsor. |
| `POST` | `/admin/potluck` | `activities` | Adds an activity (name, blurb, place, date/start/end, helpers wanted, open). |
| `PATCH/DELETE` | `/admin/potluck/{id}` | `activities` | Edits / opens / closes an activity; deletes it with every pick and its schedule row. |
| `GET` | `/public/pages` | none | Every site page converted at least once: slug, title, menu name, `html_url`. Read by the site build. Cached 10 s. |
| `GET/POST` | `/admin/pages` | `registration` / `academics` | The site pages list; adds a page (title, address, Google Doc link, menu name, show in menu, order). |
| `PATCH/DELETE` | `/admin/pages/{id}` | same | Edits a page (a different Doc forgets the converted copy); removes it and trashes the copy. |
| `POST` | `/admin/pages/{id}/convert` | same | Re-reads one Doc through the Drive puppet and rewrites its Drive copy (pictures embedded). A failed Doc keeps its last good copy and returns the reason. |
| `POST` | `/admin/pages/rebuild` | same | Asks GitHub to rebuild the site. Reports whether it started. |
| `GET` | `/public/schedule` | none | Every published master-schedule entry, in time order, with the convention's clock. Cached 20 s. |
| `GET/POST` | `/admin/schedule` | `logistics` | The master schedule with drafts; adds an entry. |
| `PATCH/DELETE` | `/admin/schedule/{id}` | `logistics` | Edits / deletes a manual entry. Entries the Athletics Director's heats and brackets wrote (`source = 'olympika'`) are refused. |
| `GET` | `/admin/athletics` | `athletics` | Every Olympika event with its entry count, heats and whether a bracket is drawn. |
| `POST` | `/admin/athletics/events` | `athletics` | Adds an event. |
| `GET/PATCH/DELETE` | `/admin/athletics/events/{id}` | `athletics` | One event with every sign-up, heat, team and game; edits it (including opening and closing sign-up); deletes it with everything under it. |
| `PUT` | `/admin/athletics/events/{id}/heats` | `athletics` | Sets the number of heats and, with a date and start, times them all. |
| `PATCH` | `/admin/athletics/heats/{id}` | `athletics` | Renames a heat or changes when it runs. |
| `POST` | `/admin/athletics/events/{id}/assign` | `athletics` | Deals every entrant into the heats. |
| `PATCH/DELETE` | `/admin/athletics/signups/{id}` | `athletics` | Moves an entrant to another heat or lane; removes the sign-up. |
| `POST/DELETE` | `/admin/athletics/events/{id}/bracket` | `athletics` | Draws a single-elimination bracket (optionally timing the games); clears it. |
| `POST` | `/admin/athletics/events/{id}/bracket/times` | `athletics` | Re-times the games of the bracket as drawn. |
| `PATCH` | `/admin/athletics/matches/{id}` | `athletics` | Records a result (the winner moves on) and/or changes a game's time and field. |
| `PATCH/DELETE` | `/admin/athletics/teams/{id}` | `athletics` | Renames a team; removes one (only before a bracket is drawn). |
| `POST` | `/admin/export` | `*` | Generates full or anonymized SQL/Excel system backups. |
