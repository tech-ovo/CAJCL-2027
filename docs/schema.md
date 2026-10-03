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
| `POST` | `/admin/export` | `*` | Generates full or anonymized SQL/Excel system backups. |
