# **Schema and API**

Target: Turso (libSQL). All SQL lives in `/backend/queries/` so CI can run `EXPLAIN QUERY PLAN` over every statement. Migrations are numbered, forward-only, in `/backend/migrations/`.

**Every index below is declared in the migration that creates its table.** Adding an index to a populated table triggers a full table scan billed at one read per existing row.

## Conventions

- All timestamps are `TEXT` in ISO-8601 UTC (`2027-02-13T23:59:59Z`). Render in `America/Los_Angeles`. Never store local time.
- All money is `INTEGER` cents. Never a float, anywhere, for any reason.
- All booleans are `INTEGER` 0/1.
- `PRAGMA foreign_keys = ON` on every connection.
- Soft delete via a `status` column. Nothing in `people`, `schools`, or `audit_log` is ever hard-deleted.
- Enumerations are enforced with `CHECK` constraints, not application logic.

---

## Core tables

```sql
CREATE TABLE settings (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  value_type  TEXT NOT NULL CHECK (value_type IN ('string','int','cents','bool','datetime','markdown')),
  label       TEXT NOT NULL,          -- human label shown in the dashboard
  group_name  TEXT NOT NULL,          -- dashboard section
  sort_order  INTEGER NOT NULL DEFAULT 0,
  updated_at  TEXT NOT NULL,
  updated_by  INTEGER REFERENCES people(id)
);
```

Seeded keys: `convention.year`, `convention.ordinal`, `convention.start_date`, `convention.end_date`, `convention.venue_name`, `convention.venue_address`, `convention.theme_latin`, `convention.theme_english`, `convention.theme_citation`, `convention.contact_email`, `fee.delegate_cents` (14000), `fee.extra_adult_cents` (7500), `fee.adult_ratio` (10), `deadline.forms_lock`, `deadline.payment`, `invoice.remit_to`, `invoice.remit_address`, `ops.warm_until`, `ops.autoexport_enabled`, `ops.autoexport_until`, `ops.autoexport_interval_minutes`.

**Only SCL is exempt. Members at large pay.** Being an *organization* is about not being a chapter; being *exempt* is about not being billed, and they are two columns because only one school is both. The comment above `billing_exempt` in `001_core.sql` still pairs SCL with At Large — that migration has been applied and is never edited, so this line is the one to trust.

```sql
CREATE TABLE schools (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL,
  level           TEXT NOT NULL CHECK (level IN ('MS','HS')),
  kind            TEXT NOT NULL DEFAULT 'chapter' CHECK (kind IN ('chapter','organization')),
  city            TEXT,
  drive_folder_id TEXT,               -- packet scans; URL string only, visible only to scope '*'
  billing_exempt  INTEGER NOT NULL DEFAULT 0,   -- SCL only: invoice computes to zero
  discount_cents  INTEGER NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
  discount_reason TEXT,               -- shown on the invoice in words
  status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','withdrawn')),
  notes           TEXT,               -- what the CHAPTER said: machines, arrival, when the bus leaves
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  checkin_note    TEXT,               -- what the DESK wrote on the Friday about what turned up
  number          INTEGER,            -- 01..99; the chapter half of a printed person number
  UNIQUE (name, level)
);
CREATE INDEX idx_schools_kind_status_level ON schools (kind, status, level);
```

```sql
CREATE TABLE people (
  id               INTEGER PRIMARY KEY,   -- sequential, public-facing badge number
  school_id        INTEGER NOT NULL REFERENCES schools(id),
  person_type      TEXT NOT NULL CHECK (person_type IN ('delegate','adult')),
  adult_type       TEXT CHECK (adult_type IN ('sponsor','chaperone','scl','other')),
  adult_type_other TEXT,

  first_name       TEXT NOT NULL,
  middle_name      TEXT,
  last_name        TEXT NOT NULL,
  suffix           TEXT,
  raw_name_input   TEXT,                  -- exactly what the sponsor pasted, for audit

  grade            INTEGER CHECK (grade BETWEEN 6 AND 12),
  latin_level      TEXT CHECK (latin_level IN ('MS-1','MS-2','MS-3','HS-1','HS-2','HS-3','HS-Adv')),
  meal             TEXT CHECK (meal IN ('regular','vegetarian','gluten_free')),
  cell_phone       TEXT,

  email            TEXT,                  -- adults only; never collected for delegates
  latin_knowledge  TEXT CHECK (latin_knowledge IN ('none','novice','intermediate','advanced')),
  availability_note TEXT,                 -- adults only

  guardian_name    TEXT,                  -- delegates only
  guardian_phone   TEXT,                  -- delegates only

  code_hmac        TEXT NOT NULL,         -- HMAC-SHA256(pepper, normalized_code)
  code_prefix      TEXT NOT NULL CHECK (code_prefix IN ('SPO','DEL','VOL','ADM')),
                   -- 'ADM' is retired and no longer minted or accepted at
                   -- sign-in; see backend/lib/codes.py. It stays in the CHECK
                   -- because a constraint cannot be narrowed while rows still
                   -- hold the old value. The application is the narrower gate.
  pepper_version   INTEGER NOT NULL DEFAULT 1,
  code_issued_at   TEXT NOT NULL,

  status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','cancelled','cancelled_paid')),
  cancelled_at     TEXT,
  forms_unlocked   INTEGER NOT NULL DEFAULT 0,  -- admin override past the lock date

  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  roster_import_id INTEGER,           -- which paste created them, if one did
  board_title      TEXT,              -- "Convention President"; a delegate may hold one
  activity_sheet_waived INTEGER NOT NULL DEFAULT 0,  -- added at the desk on the Friday
  school_seq       INTEGER,           -- 001..999; the person half of a printed number

  CHECK (person_type = 'adult'    OR adult_type IS NULL),
  CHECK (person_type = 'delegate' OR (grade IS NULL AND latin_level IS NULL)),
  CHECK (person_type = 'adult'    OR (email IS NULL AND latin_knowledge IS NULL AND availability_note IS NULL)),
  CHECK (person_type = 'delegate' OR (guardian_name IS NULL AND guardian_phone IS NULL))
);

CREATE UNIQUE INDEX idx_people_code_hmac  ON people (code_hmac);
CREATE INDEX        idx_people_school     ON people (school_id, status, person_type);
CREATE INDEX        idx_people_sort       ON people (school_id, last_name, first_name);
```

`idx_people_school` is the index the sponsor roster and every chair count depend on. `idx_people_code_hmac` is what makes login O(1).

`schools.kind` separates chapters — who send delegates and get invoiced — from organizations. The state board is an organization: admin accounts must hang off some school because `people.school_id` is `NOT NULL`, but the board is not a chapter and must never appear in the public school count, on the chair dashboard, or in any invoice. This is a flag, never a name check, for the same reason `billing_exempt` is.

`people.status` has **three** values, not two, because **there are no refunds** — an event this size runs on pre-payment:

- `active` — attending, billable.
- `cancelled` — withdrew *before* the chapter's payment arrived. Not billable; the invoice falls.
- `cancelled_paid` — withdrew *after* payment. Not attending and absent from every public statistic and completion count, but **still billable**, so the balance keeps reading zero instead of showing a credit nobody intends to refund.

Which one applies is decided from the payment record at the moment of cancellation, not asked of the sponsor — a sponsor should not have to know the billing policy to remove a student.

The last two `CHECK` constraints enforce the person-type split at the database level rather than trusting application code: delegates cannot acquire an email, and adults cannot acquire guardian fields. Assert both in tests as well, since a future migration could quietly drop them.

---

## Sessions and access

```sql
CREATE TABLE sessions (
  id                     INTEGER PRIMARY KEY,
  person_id              INTEGER NOT NULL REFERENCES people(id),
  token_hash             TEXT NOT NULL,         -- SHA-256 of 32 random bytes
  impersonator_person_id INTEGER REFERENCES people(id),
  impersonation_can_write INTEGER NOT NULL DEFAULT 0,
  created_at             TEXT NOT NULL,
  last_seen_at           TEXT NOT NULL,
  expires_at             TEXT NOT NULL,
  revoked_at             TEXT,
  user_agent             TEXT,
  ip_hash                TEXT                   -- hashed, never raw; most subjects are minors
);
CREATE UNIQUE INDEX idx_sessions_token ON sessions (token_hash);
CREATE INDEX        idx_sessions_person ON sessions (person_id, revoked_at);
```

Normal sessions expire in 180 days; impersonation sessions in 30 minutes.

```sql
CREATE TABLE roles (
  id          INTEGER PRIMARY KEY,
  key         TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  description TEXT,
  is_system   INTEGER NOT NULL DEFAULT 0,   -- system roles cannot be deleted
  created_at  TEXT NOT NULL
);

CREATE TABLE role_scopes (
  role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  -- 'judge' arrived in 008: global like an administrative scope, but it
  -- reaches only the judging screens and never a roster.
  scope   TEXT NOT NULL CHECK (scope IN ('*','registration','academics','awards',
                                         'sponsor','delegate','chapter','judge')),
  PRIMARY KEY (role_id, scope)
);

CREATE TABLE person_roles (
  person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  role_id    INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  granted_by INTEGER REFERENCES people(id),
  granted_at TEXT NOT NULL,
  PRIMARY KEY (person_id, role_id)
);
CREATE INDEX idx_person_roles_person ON person_roles (person_id);
```

System roles seeded: `admin` (`*`), `registration_chair` (`registration`), `academics_chair` (`academics`), `awards_chair` (`awards`), `sponsor` (`sponsor`), `delegate` (`delegate`), `chapter_leader` (`chapter`).

`chapter_leader` is granted by a sponsor to a delegate so that student leadership can manage chapter team entries. It is a scope on the delegate's existing account — **never a second code**.

```sql
CREATE TABLE sponsor_school_grants (
  id                   INTEGER PRIMARY KEY,
  person_id            INTEGER NOT NULL REFERENCES people(id),
  school_id            INTEGER NOT NULL REFERENCES schools(id),
  granted_by_person_id INTEGER REFERENCES people(id),
  granted_at           TEXT NOT NULL,
  note                 TEXT              -- "Covering while Ms Alvarez is on leave."
);
CREATE UNIQUE INDEX sponsor_school_grants_unique    ON sponsor_school_grants (person_id, school_id);
CREATE INDEX        sponsor_school_grants_by_school ON sponsor_school_grants (school_id);
```

One sponsor, more than one chapter: a teacher who moved schools mid-year, a district where one person covers the middle school and the high school, somebody covering for a colleague on leave.

`people.school_id` still says which chapter a person **belongs** to — it is where their number comes from, and changing it into a relationship would rewrite the meaning of every person in the system. This table records the additional chapters a sponsor may **act for**.

**A grant widens reach, never permission.** Scopes reach a person only through roles, and nothing here changes that: a row for somebody without the sponsor role does nothing at all, which is why the endpoint that writes one refuses it. `authenticate` asks for grants only when the person already holds the sponsor role, so a delegate signing in never runs the query.

```sql
CREATE TABLE login_attempts (
  id                  INTEGER PRIMARY KEY,
  attempted_code_hmac TEXT NOT NULL,   -- HMAC of whatever was typed, valid or not
  code_prefix         TEXT,
  ip_hash             TEXT NOT NULL,
  succeeded           INTEGER NOT NULL,
  attempted_at        TEXT NOT NULL
);
CREATE INDEX idx_login_attempts_ip   ON login_attempts (ip_hash, attempted_at);
CREATE INDEX idx_login_attempts_code ON login_attempts (attempted_code_hmac, attempted_at);
```

Rate limit: 10 failures per IP per 15 minutes, **5 failures per code per hour**.

The per-code limit requires `attempted_code_hmac`, which is the HMAC of the string the person actually typed — computed with the same pepper, whether or not that code exists. Without it there is nothing to count against, since a failed attempt by definition matches no row in `people`. Storing it is safe: it is a keyed hash of a guess, it reveals nothing an attacker with database access does not already hold, and it lets you distinguish one person fumbling their own code from someone walking the keyspace. Never store the raw attempted code.

Prune rows older than 7 days on a daily cron.

---

## Forms

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
```

The `UNIQUE (person_id, form_type)` constraint creates the index that kills the N+1. Do not add a second index on `person_id` alone — the unique index already covers that prefix, and a duplicate would cost storage and slow every write for nothing. The roster view is one query:

```sql
SELECT p.id, p.first_name, p.last_name, p.person_type, p.status,
       fs.status AS form_status,
       pf_w.received AS waiver_received,
       pf_m.received AS medical_received
FROM people p
LEFT JOIN form_submissions fs
       ON fs.person_id = p.id
LEFT JOIN paper_forms pf_w
       ON pf_w.person_id = p.id AND pf_w.form_type = 'student_waiver'
LEFT JOIN paper_forms pf_m
       ON pf_m.person_id = p.id AND pf_m.form_type IN ('student_medical','adult_medical')
WHERE p.school_id = ? AND p.status = 'active'
ORDER BY p.person_type, p.last_name, p.first_name;
```

```sql
CREATE TABLE paper_forms (
  person_id            INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  form_type            TEXT NOT NULL CHECK (form_type IN ('student_waiver','student_medical','adult_medical')),
  received             INTEGER NOT NULL DEFAULT 0,
  marked_by_person_id  INTEGER REFERENCES people(id),
  marked_at            TEXT,
  PRIMARY KEY (person_id, form_type)
);
```

**Completion is defined as:**
- Delegate: `student_activity` submitted, plus `student_waiver` and `student_medical` received.
- Adult: `adult_registration` submitted, plus `adult_medical` received. SCL adults skip `adult_registration`.

---

## Catalog — fully dashboard-editable

```sql
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
  item_code              TEXT UNIQUE,  -- four digits, on the answer sheet; NULL until set
  eligible_latin_levels  TEXT,   -- CSV of latin_level values; NULL means all
  registration_scope     TEXT NOT NULL DEFAULT 'individual'
                           CHECK (registration_scope IN ('individual','chapter')),
  max_sub_selections     INTEGER,
  min_latin_knowledge    TEXT CHECK (min_latin_knowledge IN ('none','novice','intermediate','advanced')),
  sort_order             INTEGER NOT NULL DEFAULT 0,
  active                 INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_catalog_items_category ON catalog_items (category_id, active, sort_order);

CREATE TABLE catalog_item_options (
  id         INTEGER PRIMARY KEY,
  item_id    INTEGER NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  active     INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_catalog_options_item ON catalog_item_options (item_id, active);
```

The whole catalog is small (~150 rows) and read on nearly every form load, so **load it once per container into memory and refresh on mutation**. It should not be queried per request.

### Seed catalog

**`academic_testing`** — applies to delegate, min 1, max 3, enforcement `block`:
Classical Art; Daily Life; Derivatives; Geography; Grammar 1 *(MS-1, MS-2, HS-1)*; Grammar 2 *(MS-3, HS-2)*; Grammar 3 *(HS-3, HS-Adv)*; History; Mottos/Quotes/Abbreviations; Mythology; Pentathlon; Reading Comprehension 1 *(MS-1, MS-2, HS-1)*; Reading Comprehension 2 *(MS-3, HS-2)*; Reading Comprehension 3 *(HS-3, HS-Adv)*; Vocabulary.

**`creative_arts`** — delegate, no limits:
Costume; Dramatic Interpretation; English Oratory; Essay; Latin Oratory; Sight Latin Reading.

**`graphic_arts`** — delegate, no limits:
Cartoons; Charts/Maps; Drawing/Painting *(max_sub_selections 8)*; Greeting Cards; Illustrated Quotes; Impromptu Art; Jewelry; Models (Large & Small) *(options: Large, Small)*; Mosaics; Photography (Computer Enhanced); Photography (Traditional); Pottery/Sculpture; Textile Arts.

**`olympika`** — delegate, no limits:
Chess *(individual)*; Track *(individual; options 100m, 200m, 400m)*; Fugepilam (Dodgeball) *(chapter)*; Kickball *(chapter)*; Ultimate Frisbee *(chapter)*.

**`ludi`** — delegate, no limits:
Edible Mosaics; Open Certamen; Pandora's Breakout Box; Percy Jackson Kahoot; Project Runway; Roman Rap Battle; Roman Speed Dating; Scavenger Hunt (Goose Chase); Spelling Bee; STEM Challenge; That's Entertainment.

**`adult_roles`** — applies to adult, min 2, enforcement `warn`:
Wherever needed!; Certamen Reader *(advanced)*; Certamen Scorer/Timer; Graphic Arts Judge; Olympika Volunteer; Ludi Volunteer; Latin Oratory Judge *(advanced)*; Sight Latin Reading Judge *(advanced)*; Essay Reading Judge; Costume Judge; English Oratory Judge; Dramatic Interpretation Judge *(advanced)*.

Every current role needs either nothing or advanced Latin, but `min_latin_knowledge` carries all four levels so a future chair can mark a role as needing intermediate Latin from the dashboard without a migration. An adult below a role's minimum sees the role disabled with the requirement stated, not hidden — the same treatment as an ineligible test.

**`preconvention`** — delegate, deferred, seeded inactive:
Modern Myth; Poetry; Slogan (English); Slogan (Latin).

---

## Selections

```sql
CREATE TABLE activity_selections (
  id         INTEGER PRIMARY KEY,
  person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  item_id    INTEGER NOT NULL REFERENCES catalog_items(id),
  created_at TEXT NOT NULL,
  UNIQUE (person_id, item_id)
);
CREATE INDEX idx_activity_selections_person ON activity_selections (person_id);
CREATE INDEX idx_activity_selections_item   ON activity_selections (item_id);

CREATE TABLE activity_selection_options (
  selection_id INTEGER NOT NULL REFERENCES activity_selections(id) ON DELETE CASCADE,
  option_id    INTEGER NOT NULL REFERENCES catalog_item_options(id),
  PRIMARY KEY (selection_id, option_id)
);

CREATE TABLE chapter_entries (
  id                  INTEGER PRIMARY KEY,
  school_id           INTEGER NOT NULL REFERENCES schools(id),
  item_id             INTEGER NOT NULL REFERENCES catalog_items(id),
  team_label          TEXT NOT NULL DEFAULT 'A',
  notes               TEXT,
  created_by_person_id INTEGER REFERENCES people(id),
  created_at          TEXT NOT NULL,
  UNIQUE (school_id, item_id, team_label)
);
CREATE INDEX idx_chapter_entries_school ON chapter_entries (school_id);
CREATE INDEX idx_chapter_entries_item   ON chapter_entries (item_id);
```

`idx_activity_selections_item` and `idx_chapter_entries_item` exist for the A/A/A chairs' "how many are taking Mythology" counts, which would otherwise scan 12,000 rows.

Editing an activity sheet replaces all selections for that person inside a single transaction: delete then insert. Do not diff.

```sql
CREATE TABLE adult_role_selections (
  person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  item_id    INTEGER NOT NULL REFERENCES catalog_items(id),
  created_at TEXT NOT NULL,
  PRIMARY KEY (person_id, item_id)
);
CREATE INDEX idx_adult_roles_item ON adult_role_selections (item_id);
```

---

## Payments and counters

```sql
CREATE TABLE payments (
  id                   INTEGER PRIMARY KEY,
  school_id            INTEGER NOT NULL REFERENCES schools(id),
  amount_cents         INTEGER NOT NULL,
  method               TEXT CHECK (method IN ('check','other')),
  reference            TEXT,          -- check number
  received_on          TEXT,          -- date, not timestamp
  note                 TEXT,
  recorded_by_person_id INTEGER NOT NULL REFERENCES people(id),
  created_at           TEXT NOT NULL
);
CREATE INDEX idx_payments_school ON payments (school_id, created_at);
```

Payments are append-only. A correction is a new row, possibly negative, never an edit. The audit log and the payment history together are the record.

```sql
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
  -- Meals for the caterer, adult kinds for the chairs. Counted in the same
  -- transaction as anything that changes them, like every column above.
  meal_regular             INTEGER NOT NULL DEFAULT 0,
  meal_vegetarian          INTEGER NOT NULL DEFAULT 0,
  meal_gluten_free         INTEGER NOT NULL DEFAULT 0,
  meal_unanswered          INTEGER NOT NULL DEFAULT 0,  -- still to be chased
  meal_none                INTEGER NOT NULL DEFAULT 0,  -- bringing their own
  adults_sponsors          INTEGER NOT NULL DEFAULT 0,
  adults_chaperones        INTEGER NOT NULL DEFAULT 0,
  arrived_at               TEXT      -- the Friday desk; per CHAPTER, not per person
);

CREATE TABLE public_stats_cache (
  id            INTEGER PRIMARY KEY CHECK (id = 1),
  schools_ms    INTEGER NOT NULL,
  schools_hs    INTEGER NOT NULL,
  delegates     INTEGER NOT NULL,
  adults        INTEGER NOT NULL,
  updated_at    TEXT NOT NULL
);
```

Both are recomputed **inside the same transaction** as any mutation that could change them. Never `COUNT(*)` over `people` to serve a page. A single recompute costs ~1,150 reads; serving from cache costs 1.

Invoice, when `schools.billing_exempt = 0`:

```
max(0,
    fee.delegate_cents × delegates_billable
      + max(0, fee.extra_adult_cents × (adults_billable − ceil(delegates_billable ÷ fee.adult_ratio)))
      − schools.discount_cents)
```

where `delegates_billable = delegates_active + delegates_cancelled_paid` and likewise for adults. **Billable, not active** — see the three-valued `people.status` above.

`discount_cents` is an ad-hoc reduction an admin sets by hand: a new-chapter discount, a hardship arrangement, or the way a fee change gets honoured after invoices have gone out. It is floored at zero — a discount larger than the bill produces nothing owed, **never a credit**.

Note a consequence of the free-adult allowance that surprises people: because the allowance is `ceil(delegates ÷ 10)`, the 1st, 11th, and 21st delegate each carry a free adult with them. Cancelling one of those delegates removes that allowance, so the chapter's bill drops by $140 − $75 = $65 rather than by the full $140. The invoice page shows the free-adult line so the arithmetic is visible rather than magic.

When `billing_exempt = 1` the total is zero and the invoice page says so in words. Exempt schools are excluded from the chair dashboard's outstanding-balance total. Never key exemption off a school's name.

**Deadline storage is a trap.** `deadline.forms_lock` and `deadline.payment` are stored as UTC but mean "end of day in California." February 13, 2027 is during PST (UTC−8), so the correct stored value is `2027-02-14T07:59:59Z`. If a future commissioner moves a deadline into a DST month the offset changes to −7. Store a UTC instant, compute it from a wall-clock date entered in the dashboard plus `America/Los_Angeles`, and never let anyone hand-type the UTC string.

**Both former TODOs are now decided.**

*Cancelled delegates and the invoice* — resolved by the three-valued `people.status` above. There are no refunds; a cancellation after payment stays billable.

*A fee changing mid-cycle* — deliberately **not** modelled. There is no fee snapshot per school and no effective date on the fee setting, because the fee is not expected to change once registration opens. If it has to, it is handled by hand with machinery that already exists: if the fee goes **up**, give already-invoiced schools a discount equal to the increase; if it goes **down** and you want to honour it, the recomputed invoice falls on its own, and for schools that already paid the higher amount you send the difference back and record a **negative payment** for it. Both paths leave a readable trail in the payment history and the audit log, which is worth more than machinery that runs once a decade.

There is also **no operation to move a person between schools**, and deliberately no query for one. Chapters are completely separate — a middle school and a high school at the same site register as two schools with two sponsors. If a sponsor enters someone under the wrong chapter, the fix is to cancel that row and enter them again under the right one. A move would have to revalidate the Latin level, every test eligibility, and both schools' invoices: machinery for an operation that should not happen.

---

## Audit log

```sql
CREATE TABLE audit_log (
  id                     INTEGER PRIMARY KEY,
  ts_utc                 TEXT NOT NULL,
  actor_person_id        INTEGER REFERENCES people(id),   -- NULL for system actions
  actor_role_snapshot    TEXT,
  impersonator_person_id INTEGER REFERENCES people(id),
  action                 TEXT NOT NULL,
  entity_type            TEXT,
  entity_id              INTEGER,
  school_id              INTEGER REFERENCES schools(id),  -- denormalized for filtering
  summary                TEXT NOT NULL,                   -- rendered at write time
  changed_fields         TEXT,                            -- JSON array of field NAMES
  value_detail           TEXT,                            -- JSON, payments only
  request_id             TEXT,
  ip_hash                TEXT
);
CREATE INDEX idx_audit_ts       ON audit_log (ts_utc);
CREATE INDEX idx_audit_school   ON audit_log (school_id, ts_utc);
CREATE INDEX idx_audit_actor    ON audit_log (actor_person_id, ts_utc);
CREATE INDEX idx_audit_entity   ON audit_log (entity_type, entity_id);

-- Migration 010 updated audit_log_no_update to allow redaction while preserving append-only:
-- UPDATE is rejected unless all metadata remains identical and NEW.summary LIKE '%REDACTED%'.
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
```

Actions: `auth.login`, `auth.login_failed`, `auth.magic_link`, `auth.logout`, `impersonation.start`, `impersonation.end`, `school.create`, `school.update`, `roster.preview`, `roster.import`, `person.create`, `person.update`, `person.cancel`, `person.restore`, `person.redact`, `person.code_regenerate`, `form.submit`, `form.update`, `form.unlock`, `paper_form.mark`, `chapter_entry.create`, `chapter_entry.delete`, `payment.record`, `catalog.update`, `settings.update`, `announcement.update`, `role.create`, `role.grant`, `role.revoke`, `export.run`, `warm.set`, `contest.submit`, `session.revoke`.


`changed_fields` records field **names only**, never values — this keeps PII out of the log and matches the requirement that the log show "Bob updated their forms" rather than what Bob wrote. `value_detail` carries before/after values for `payment.record` only, because money disputes are exactly when you need them.

`summary` is a complete human-readable sentence written at insert time: *"Mark Michalak added 28 delegates to University High School."* A future commissioner reads the log with no code.

The log is written **in the same transaction** as the mutation. If the mutation rolls back, so does the log entry. There is no path that changes data without writing an entry.

---

## Roster import

```sql
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
```

`idempotency_key` is issued with the preview and returned with the commit. A repeat commit with a key already present returns the original result rather than importing again. This is what makes a double-click harmless.

---

## Announcements and documents

```sql
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
  key         TEXT NOT NULL UNIQUE,   -- 'packet_instructions', 'invoice_terms', 'welcome_body'
  title       TEXT NOT NULL,
  body_md     TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  updated_by  INTEGER REFERENCES people(id)
);
```

`documents` holds every block of printed or displayed prose an admin might want to reword — the packet instructions above all — so changing the wording never requires a deploy.

---

## Pre-convention contests

Delegates submit Digital Art/Poster, Modern Myth, Original Poetry, Original Slogan (English) and Original Slogan (Latin); a chapter submits its Publicity portfolio. Judges rank their top N in each division on the site, without seeing names or chapters, and the Academics chairs read the results. Created in `008_contests.sql`, which replaced the unused `contest_submissions` placeholder from 004; `009_contest_rankings.sql` replaced 008's rubric scoring with ranked ballots.

Each contest is a `catalog_items` row in the `preconvention` category — which stays **inactive**, because these are not choices on the activity sheet — plus one row here saying how it is entered.

```sql
CREATE TABLE contests (
  item_id           INTEGER PRIMARY KEY REFERENCES catalog_items(id),
  key               TEXT NOT NULL UNIQUE,
  entry_kind        TEXT NOT NULL CHECK (entry_kind IN ('file','text','link')),
  entered_by        TEXT NOT NULL CHECK (entered_by IN ('delegate','chapter')),
  divisions         TEXT NOT NULL DEFAULT 'none'
                      CHECK (divisions IN ('none','level','level_grade','latin_level')),
  accepted_types    TEXT,             -- CSV of extensions, file entries
  needs_title       INTEGER NOT NULL DEFAULT 0,
  min_words         INTEGER,
  max_words         INTEGER,
  words_penalty     INTEGER NOT NULL DEFAULT 0,   -- per started 100 words out of range
  max_chars         INTEGER,
  needs_translation INTEGER NOT NULL DEFAULT 0,
  must_attend       INTEGER NOT NULL DEFAULT 1,   -- 0 for Publicity only
  facets            TEXT,             -- newline-separated; Publicity's eight categories
  rules_md          TEXT,
  sort_order        INTEGER NOT NULL DEFAULT 0,
  places            INTEGER NOT NULL DEFAULT 3    -- N: places awarded, entries each judge ranks (009)
                      CHECK (places BETWEEN 1 AND 20)
);
```

`divisions`: `none` → `Open`; `level` → `MS`/`HS` from the chapter (Publicity); `level_grade` → `MS`, `HS 9–10`, `HS 11–12` (Myth, Poetry, slogans); `latin_level` → exactly `MS-I`, `MS-II`, `MS-III`, `HS-I`, `HS-II`, `HS-III`, `HS-Advanced` from the delegate's Latin level (Digital Art/Poster). The division is computed when an entry is submitted and **stored on it**. Divisions are the Convention Book's rule and have no editing screen. `places` is the one number the Academics chairs set per contest (with `rules_md`); it may change after judges have handed in, and everything that reads it reads it fresh. There is no rubric: 008 had one (`contest_criteria`, with per-entry `contest_scores`), and 009 dropped both without carrying scores over.

```sql
CREATE TABLE contest_entries (
  id                INTEGER PRIMARY KEY,
  item_id           INTEGER NOT NULL REFERENCES contests(item_id),
  school_id         INTEGER NOT NULL REFERENCES schools(id),
  person_id         INTEGER REFERENCES people(id),   -- NULL for a chapter entry
  division          TEXT NOT NULL,
  title             TEXT,
  body_text         TEXT,     -- a slogan, or the text read out of a .docx/.txt
  translation       TEXT,     -- Latin slogan
  link_url          TEXT,     -- Publicity portfolio (a Google document)
  facets            TEXT,     -- which Publicity categories the portfolio includes
  word_count        INTEGER,
  word_count_source TEXT CHECK (word_count_source IN ('counted','declared')),
  drive_file_id     TEXT,
  drive_folder_id   TEXT,
  original_name     TEXT,     -- never sent to a judge
  mime_type         TEXT,     -- derived from the checked extension, not the browser
  size_bytes        INTEGER,
  submitted_by      INTEGER NOT NULL REFERENCES people(id),
  submitted_at      TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_contest_entries_person
  ON contest_entries (person_id, item_id) WHERE person_id IS NOT NULL;
CREATE UNIQUE INDEX idx_contest_entries_chapter
  ON contest_entries (school_id, item_id) WHERE person_id IS NULL;
CREATE INDEX idx_contest_entries_item   ON contest_entries (item_id, division);
CREATE INDEX idx_contest_entries_school ON contest_entries (school_id, item_id);

-- One judge's ranking of one division (and, for Publicity, one category).
CREATE TABLE contest_ballots (
  id               INTEGER PRIMARY KEY,
  item_id          INTEGER NOT NULL REFERENCES contests(item_id),
  division         TEXT NOT NULL,
  facet            TEXT NOT NULL DEFAULT '',   -- '' except for Publicity
  judge_person_id  INTEGER NOT NULL REFERENCES people(id),
  comment          TEXT,
  status           TEXT NOT NULL CHECK (status IN ('draft','submitted')),
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  UNIQUE (item_id, judge_person_id, division, facet)
);
CREATE INDEX idx_contest_ballots_item ON contest_ballots (item_id, status);

-- The entries on a ballot, in order: place 1 is the judge's best.
CREATE TABLE contest_ballot_places (
  ballot_id  INTEGER NOT NULL REFERENCES contest_ballots(id) ON DELETE CASCADE,
  place      INTEGER NOT NULL CHECK (place > 0),
  entry_id   INTEGER NOT NULL REFERENCES contest_entries(id) ON DELETE CASCADE,
  PRIMARY KEY (ballot_id, place),
  UNIQUE (ballot_id, entry_id)
);
CREATE INDEX idx_contest_ballot_places_entry ON contest_ballot_places (entry_id);
```

A judge owes one ballot per (division, facet) that has entries. A draft may be partial; a ballot handed in ranks exactly places 1..k, where k is N or the number of entries in the group if fewer. Saving replaces the ballot's whole list. If N is raised after a ballot was handed in, it counts as it stands and the judge's page shows it as incomplete; if N is lowered, places beyond N count for nothing but still show.

**No file bytes are ever stored in the database.** A file entry goes browser → Modal → the Apps Script puppet, which files it under the **automated Drive root** (setting `drive.contests_root`), one folder per contest and then per chapter, and returns the Drive file ID. Judges never get the folder: they read a file back through `GET /judge/entries/{id}/file`, which names it `Entry 14.pdf`. Replacing an entry keeps its id, takes it off every ballot and puts those ballots back to draft (the judge ranked different work and now has a gap to fill), and trashes the old file; withdrawing does the same to the ballots, deletes the row and trashes the file. Drafts are left out of the results. **Points:** a judge's 1st is worth N, their 2nd N−1, … their Nth 1; an entry's points are the sum over submitted ballots, so one judge's list comes out exactly as ranked. Equal points are broken by more 1sts, then more 2nds, down to Nth; entries still level share a place and the next is skipped (1, 2, 2, 4). Places 1..N are awarded. An entry whose creator is no longer attending is listed but not placed (except Publicity), and those below move up. The deadline is the setting `deadline.contests`.

This root is entirely separate from the per-school packet folders holding medical forms and waivers, which no code touches — see `structure.md`.

## Awards infrastructure (schema only, no UI yet)

```sql
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

---

# **The name parser**

This is the most visible piece of the site and the most likely to go wrong in front of a sponsor. Specify it precisely.

**Input:** one blob of text from a textarea. **Output:** a preview array. **Never writes.**

1. **Split** on `\r\n`, `\n`, `\r`. Drop empty and whitespace-only lines.
2. **Strip line noise** per line: leading bullets (`-`, `–`, `*`, `•`, `·`), leading numbering (`1.`, `1)`, `(1)`, `1 -`), surrounding straight and smart quotes, trailing commas and semicolons.
3. **Delimiters.** If the line contains tabs, split on tabs. If it contains commas and splitting yields exactly two fields where both look like name fragments, treat as `Last, First [Middle]`. If splitting yields more than two fields, treat field 1 as the name and attempt to map remaining fields onto grade, Latin level, phone, and email by pattern.
4. **Extract non-name data** wherever it appears: anything matching an email pattern goes to `email` (and is discarded with a warning for delegates), anything matching a 10-digit phone pattern goes to `cell_phone`, a bare integer 6–12 goes to `grade`, and a token matching `MS-[123]`, `HS-[123]`, or `HS-Adv` (case-insensitively, with or without the hyphen) goes to `latin_level`. Accept the legacy spellings sponsors still have in their own spreadsheets and normalize them silently: `HS-4`, `HS4`, `Latin 4`, `AP`, and `AP Latin` all map to `HS-Adv`; a bare `1`–`3` in a Latin-level column maps to the matching level for that school's type. Normalizing quietly is right here — a sponsor pasting last year's spreadsheet should not be made to fix vocabulary we changed.
5. **Suffixes.** Strip a trailing `Jr`, `Jr.`, `Sr`, `Sr.`, `II`, `III`, `IV`, `V` into `suffix`.
6. **Particles.** Scan right to left; fold lowercase particles into the last name. **This list is canonical and lives in exactly one constant in the codebase** — no other document or module may hold its own copy: `de`, `del`, `de la`, `de los`, `della`, `van`, `van der`, `van den`, `von`, `da`, `di`, `dos`, `du`, `la`, `le`, `bin`, `binte`, `ibn`, `al`, `ter`, `ten`.
7. **Assign** remaining tokens: one token → last name only, warn. Two → first, last. Three → first, middle, last, **no warning** — a middle name is ordinary and flagging it would put a warning on a third of any real roster, which teaches sponsors to dismiss warnings without reading them. Four or more → first token to first name, last token to last name, remainder to middle, and **flag for confirmation**.
8. **Casing.** Preserve the input's casing. Only if the entire line is uppercase or entirely lowercase, apply title casing with `Mc`/`Mac`/`O'`/hyphen handling and particles left lowercase.
9. **Warnings** attached per row: `multi_token_name`, `single_token_name`, `duplicate_in_paste`, `duplicate_in_roster` (matched on normalized first+last, disambiguated by guardian name/phone), `unexpected_character` (control characters or unmatched brackets), `email_discarded`, `ambiguous_delimiter`, `possible_header_row` (a first line reading `Name`, `Student`, `First`, etc.).
10. **Preview** renders an editable table: type (delegate/adult), first, middle, last, suffix, grade, Latin level, meal, guardian name, guardian phone — all editable inline, with warnings shown per row and a per-row dismiss.

**Test fixtures must include:** `de la Cruz, Mary Beth`; `MARY BETH DE LA CRUZ`; `mary beth de la cruz`; `Robert McDonald Jr.`; `O'Brien, Seán`; `Nguyễn Thị Minh Anh`; `Smith,John,9,HS-1`; `Chen, Timothy Wei` (three tokens, must produce **no** warning); `Liu,Carl,12,AP Latin`; `Rivera Ana 7 MS-2`; a tab-separated spreadsheet paste with a header row; a list with `1.` numbering; two identical names disambiguated only by guardian phone; a line containing only whitespace; a 300-line paste; and a line with a zero-width space in it.

---

# **API**

All endpoints are under one Modal FastAPI app. Every endpoint declares a required scope and a school-scoping rule. Responses are JSON. CORS allows only the GitHub Pages origin and `state.uhsjcl.org`.

### Auth
| Method | Path | Scope | Notes |
|---|---|---|---|
| POST | `/auth/redeem` | — | `{code}` → session token + person summary. Rate limited. |
| GET | `/auth/me` | any session | Person, roles, scopes, school, impersonation state |
| POST | `/auth/logout` | any session | Revokes the current session |
| POST | `/auth/impersonate` | `*` | `{target_person_id, admin_code}`; step-up required |
| POST | `/auth/impersonate/end` | impersonation session | Returns to the admin session |

### Public (unauthenticated, cached)
| Method | Path | Notes |
|---|---|---|
| GET | `/public/stats` | Served from `public_stats_cache`, 60s HTTP cache header |
| GET | `/public/convention` | Settings subset; 300s cache |
| GET | `/public/announcements` | Active banners only |

### Sponsor
| Method | Path | Scope | Notes |
|---|---|---|---|
| GET | `/sponsor/roster` | `sponsor` | Single JOIN query, own school only |
| POST | `/sponsor/roster/parse` | `sponsor` | Returns preview + `idempotency_key`. No writes. |
| POST | `/sponsor/roster/commit` | `sponsor` | Idempotent |
| POST | `/sponsor/people` | `sponsor` | Add one attendee |
| PATCH | `/sponsor/people/{id}` | `sponsor` | Own school only |
| POST | `/sponsor/people/{id}/cancel` | `sponsor` | Soft; recompute stats |
| POST | `/sponsor/people/{id}/restore` | `sponsor` | |
| POST | `/sponsor/people/{id}/regenerate-code` | `sponsor` | Revokes sessions; returns the new code once |
| POST | `/sponsor/people/{id}/chapter-leader` | `sponsor` | Inserts or deletes a `person_roles` row for the system role `chapter_leader`. Scopes are never attached to a person directly — the only path from person to scope is `person_roles` → `roles` → `role_scopes`. |
| POST | `/sponsor/paper-forms` | `sponsor` | `{person_id, form_type, received}` |
| GET | `/sponsor/packet` | `sponsor` | HTML print view |
| GET | `/sponsor/packet.pdf` | `sponsor` | Spawns the fat-image worker |
| GET | `/sponsor/invoice` | `sponsor` | Computed from `school_stats` |
| GET/POST/DELETE | `/sponsor/chapter-entries` | `sponsor` or `chapter` | |
| GET | `/sponsor/contests` | `chapter`, `registration` or `academics` | The Publicity portfolio; the chapter's delegate entries only for a sponsor or chair |
| POST/DELETE | `/sponsor/contests/{item_id}` | `chapter` or `registration` | Publicity portfolio link and categories; refused after `deadline.contests` |
| GET | `/sponsor/contests/entries/{id}/file` | `sponsor`, `registration` or `academics` | A delegate's file, for their own chapter's sponsor; named `Contest - Last, First.ext` |

### Attendee
| Method | Path | Scope | Notes |
|---|---|---|---|
| GET | `/me/activity-sheet` | `delegate` | Own only |
| PUT | `/me/activity-sheet` | `delegate` | Whole-form replace in one transaction; rejects if locked |
| GET | `/me/adult-sheet` | any adult | |
| PUT | `/me/adult-sheet` | any adult | |
| GET | `/me/contests` | `delegate` | Contests, rules, places awarded, the caller's division and entries |
| POST/DELETE | `/me/contests/{item_id}` | `delegate` | Enter, replace or withdraw; a file travels base64 in the JSON body (20 MB cap, the one exception to the 1 MB body limit). Delegates only, not chaperones. |
| GET | `/me/contests/{item_id}/file` | `delegate` | The caller's own uploaded file |

### Judging
Scope `judge` only, and refused to anybody who also holds `academics`: the chairs read results with names and do not rank.

| Method | Path | Scope | Notes |
|---|---|---|---|
| GET | `/judge/contests` | `judge` | Per contest: places (N), entries, groups (divisions × categories) and how many ballots the caller has handed in |
| GET | `/judge/contests/{item_id}` | `judge` | Entries **without** names, chapters or file names, and one group per division (and category): its entry ids, places needed, the caller's own ballot and whether it is complete |
| GET | `/judge/entries/{id}/file` | `judge` | The file, as `Entry {id}.ext`, fetched through the puppet |
| PUT | `/judge/contests/{item_id}/ballot` | `judge` | `{division, facet, places: {entry_id: place}, comment, submit}`; replaces the caller's list for that group. A draft may be partial; handing in needs exactly places 1..min(N, entries). Duplicate places, places outside 1..N and entries from another group are 422 |

### Admin
| Method | Path | Scope | Notes |
|---|---|---|---|
| GET/POST | `/admin/schools` | `registration` | `drive_folder_id` redacted unless `*` |
| PATCH | `/admin/schools/{id}` | `registration` | |
| POST | `/admin/schools/{id}/people` | `registration` | Create sponsor accounts; returns codes once |
| GET | `/admin/registration` | `registration` | Chair dashboard, served from `school_stats` |
| POST | `/admin/payments` | `registration` | |
| POST | `/admin/people/{id}/unlock-forms` | `registration` | Per-person deadline override |
| GET/PUT | `/admin/catalog/**` | `*` | Categories, items, options |
| GET/PUT | `/admin/settings` | `*` | |
| GET/POST | `/admin/announcements` | `*` | |
| GET | `/admin/audit` | `*` | Paginated, indexed, 50/page, filterable |
| POST | `/admin/export` | `*` | `{format: xlsx\|sql, anonymized: bool}`; spawns worker |
| GET/PUT | `/admin/warm` | `*` | Sets `ops.warm_until` |
| GET/POST | `/admin/roles` | `*` | |
| POST | `/admin/people/{id}/roles` | `*` | |
| GET | `/admin/usage` | `*` | Turso rows read/written/storage |
| GET | `/admin/contests` | `academics` or `awards` | Every contest with places, entries, handed-in ballots and judges who handed any in |
| GET | `/admin/contests/{item_id}/results` | `academics` or `awards` | Standings per division and category, with names, points, each judge's place for the entry, whether the tie-break decided it, and judges' comments |
| GET | `/admin/contests/submissions` | `registration`, `academics` or `awards` | Every entry from every chapter, with names and chapters, no scores |
| GET | `/admin/contests/entries/{id}/file` | `registration`, `academics` or `awards` | An entry's file, for the chairs |
| PUT | `/admin/contests/{item_id}` | `academics` | `{rules_md, places}`; places a whole number 1–20, else 422. Divisions are not editable |

### Internal
| Method | Path | Notes |
|---|---|---|
| POST | `/internal/worker-callback` | HMAC-signed; worker reports completion |
| — | cron `warm_reconciler` | Every 5 minutes |
| — | cron `autoexport` | Every 10 minutes, no-op unless enabled and within window |
| — | cron `prune_login_attempts` | Daily |

---

# **Seed data**

All fabricated. Generated programmatically and reproducible from a fixed seed.

- **12 schools** — 9 high school, 3 middle school — with plausible-sounding **invented** California school names, none of them real, at varying stages of registration so the chair dashboard shows a genuine spread.
- **One `billing_exempt` organization** named SCL, with a couple of adults, so the zero-invoice path is exercised rather than untested.
- A **persistent "Sample data — not real attendees" marker** in the site header whenever the database is seeded. The site is sometimes shown to a room full of teachers; nobody should have to wonder.
- **University High School (HS)** fully populated with **30 delegates and 4 adults** (2 sponsors, 2 chaperones), realistic mixed completion: roughly 60% of activity sheets submitted, 40% of paper forms marked received, one cancelled delegate, one restored delegate, and one delegate whose name exercises the particle parser.
- **4 admin accounts** with `*` for the two convention presidents and two technology commissioners.
- **A populated audit log** covering the past several weeks, so the log page shows something real.
- **One partial payment** recorded against Uni so the invoice shows a nonzero balance.
- A **"Rebuild sample data"** button behind `*`, so a database of invented people can be put back exactly as it started after somebody tries something out.
