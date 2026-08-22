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

```sql
CREATE TABLE schools (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL,
  level           TEXT NOT NULL CHECK (level IN ('MS','HS')),
  city            TEXT,
  drive_folder_id TEXT,               -- visible only to scope '*'
  status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','withdrawn')),
  notes           TEXT,               -- fellowship room, volunteer liaison, chair notes
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  UNIQUE (name, level)
);
CREATE INDEX idx_schools_status_level ON schools (status, level);
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
  knows_latin      INTEGER,               -- adults only, 0/1
  availability_note TEXT,                 -- adults only

  guardian_name    TEXT,                  -- delegates only
  guardian_phone   TEXT,                  -- delegates only

  code_hmac        TEXT NOT NULL,         -- HMAC-SHA256(pepper, normalized_code)
  code_prefix      TEXT NOT NULL CHECK (code_prefix IN ('SPO','DEL','VOL','ADM')),
  pepper_version   INTEGER NOT NULL DEFAULT 1,
  code_issued_at   TEXT NOT NULL,

  status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','cancelled')),
  cancelled_at     TEXT,
  forms_unlocked   INTEGER NOT NULL DEFAULT 0,  -- admin override past the lock date

  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,

  CHECK (person_type = 'adult'    OR adult_type IS NULL),
  CHECK (person_type = 'delegate' OR (grade IS NULL AND latin_level IS NULL)),
  CHECK (person_type = 'delegate' OR email IS NULL OR email <> '')
);

CREATE UNIQUE INDEX idx_people_code_hmac  ON people (code_hmac);
CREATE INDEX        idx_people_school     ON people (school_id, status, person_type);
CREATE INDEX        idx_people_sort       ON people (school_id, last_name, first_name);
```

`idx_people_school` is the index the sponsor roster and every chair count depend on. `idx_people_code_hmac` is what makes login O(1).

Delegates never have an email. This is enforced in application code and asserted in tests; the `CHECK` above is deliberately loose because SQLite cannot express it cleanly.

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
  scope   TEXT NOT NULL CHECK (scope IN ('*','registration','academics','awards','sponsor','delegate','chapter')),
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
CREATE TABLE login_attempts (
  id           INTEGER PRIMARY KEY,
  code_prefix  TEXT,
  ip_hash      TEXT NOT NULL,
  succeeded    INTEGER NOT NULL,
  attempted_at TEXT NOT NULL
);
CREATE INDEX idx_login_attempts_ip ON login_attempts (ip_hash, attempted_at);
```

Rate limit: 10 failures per IP per 15 minutes, 5 failures per known code per hour. Prune rows older than 7 days on a daily cron.

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
CREATE INDEX idx_form_submissions_person ON form_submissions (person_id, status);
```

The `UNIQUE (person_id, form_type)` constraint creates the index that kills the N+1. The roster view is one query:

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
  eligible_latin_levels  TEXT,   -- CSV of latin_level values; NULL means all
  eligible_school_levels TEXT,   -- CSV of 'MS','HS'; NULL means all
  registration_scope     TEXT NOT NULL DEFAULT 'individual'
                           CHECK (registration_scope IN ('individual','chapter')),
  max_sub_selections     INTEGER,
  requires_latin         INTEGER NOT NULL DEFAULT 0,  -- adult roles
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
Wherever needed!; Certamen Reader *(requires_latin)*; Certamen Scorer/Timer; Graphic Arts Judge; Olympika Volunteer; Ludi Volunteer; Latin Oratory Judge *(requires_latin)*; Sight Latin Reading Judge *(requires_latin)*; Essay Reading Judge; Costume Judge; English Oratory Judge; Dramatic Interpretation Judge *(requires_latin)*.

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
  school_id               INTEGER PRIMARY KEY REFERENCES schools(id),
  delegates_active        INTEGER NOT NULL DEFAULT 0,
  delegates_cancelled     INTEGER NOT NULL DEFAULT 0,
  adults_active           INTEGER NOT NULL DEFAULT 0,
  delegates_complete      INTEGER NOT NULL DEFAULT 0,
  adults_complete         INTEGER NOT NULL DEFAULT 0,
  amount_owed_cents       INTEGER NOT NULL DEFAULT 0,
  amount_paid_cents       INTEGER NOT NULL DEFAULT 0,
  updated_at              TEXT NOT NULL
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

Invoice: `fee.delegate_cents × delegates_active + max(0, fee.extra_adult_cents × (adults_active − ceil(delegates_active ÷ fee.adult_ratio)))`.

> **TODO (undecided):** whether cancelled delegates still count toward the invoice, and what happens when a fee changes mid-cycle. Mark both explicitly in code.

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

CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
```

Actions: `auth.login`, `auth.login_failed`, `auth.magic_link`, `auth.logout`, `impersonation.start`, `impersonation.end`, `school.create`, `school.update`, `roster.preview`, `roster.import`, `person.create`, `person.update`, `person.cancel`, `person.restore`, `person.code_regenerate`, `form.submit`, `form.update`, `form.unlock`, `paper_form.mark`, `chapter_entry.create`, `chapter_entry.delete`, `payment.record`, `catalog.update`, `settings.update`, `announcement.update`, `role.create`, `role.grant`, `role.revoke`, `export.run`, `warm.set`.

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

## Awards infrastructure (schema only, no UI in the demo)

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

This is the most visible piece of the demo and the most likely to embarrass you live. Specify it precisely.

**Input:** one blob of text from a textarea. **Output:** a preview array. **Never writes.**

1. **Split** on `\r\n`, `\n`, `\r`. Drop empty and whitespace-only lines.
2. **Strip line noise** per line: leading bullets (`-`, `–`, `*`, `•`, `·`), leading numbering (`1.`, `1)`, `(1)`, `1 -`), surrounding straight and smart quotes, trailing commas and semicolons.
3. **Delimiters.** If the line contains tabs, split on tabs. If it contains commas and splitting yields exactly two fields where both look like name fragments, treat as `Last, First [Middle]`. If splitting yields more than two fields, treat field 1 as the name and attempt to map remaining fields onto grade, Latin level, phone, and email by pattern.
4. **Extract non-name data** wherever it appears: anything matching an email pattern goes to `email` (and is discarded with a warning for delegates), anything matching a 10-digit phone pattern goes to `cell_phone`, a bare integer 6–12 goes to `grade`, and a token matching `MS-[123]`, `HS-[123]`, or `HS-Adv` (case-insensitively, with or without the hyphen) goes to `latin_level`.
5. **Suffixes.** Strip a trailing `Jr`, `Jr.`, `Sr`, `Sr.`, `II`, `III`, `IV`, `V` into `suffix`.
6. **Particles.** Scan right to left; fold lowercase particles (`de`, `del`, `de la`, `de los`, `della`, `van`, `van der`, `van den`, `von`, `da`, `di`, `dos`, `du`, `la`, `le`, `bin`, `binte`, `ibn`, `al`, `ter`, `ten`) into the last name.
7. **Assign** remaining tokens: one token → last name only, warn. Two → first, last. Three → first, middle, last, and **flag for confirmation**. Four or more → first token to first name, last token to last name, remainder to middle, and **flag for confirmation**.
8. **Casing.** Preserve the input's casing. Only if the entire line is uppercase or entirely lowercase, apply title casing with `Mc`/`Mac`/`O'`/hyphen handling and particles left lowercase.
9. **Warnings** attached per row: `multi_token_name`, `single_token_name`, `duplicate_in_paste`, `duplicate_in_roster` (matched on normalized first+last, disambiguated by guardian name/phone), `unexpected_character` (control characters or unmatched brackets), `email_discarded`, `ambiguous_delimiter`, `possible_header_row` (a first line reading `Name`, `Student`, `First`, etc.).
10. **Preview** renders an editable table: type (delegate/adult), first, middle, last, suffix, grade, Latin level, meal, guardian name, guardian phone — all editable inline, with warnings shown per row and a per-row dismiss.

**Test fixtures must include:** `de la Cruz, Mary Beth`; `MARY BETH DE LA CRUZ`; `mary beth de la cruz`; `Robert McDonald Jr.`; `O'Brien, Seán`; `Nguyễn Thị Minh Anh`; `Smith,John,9,HS-1`; a tab-separated spreadsheet paste with a header row; a list with `1.` numbering; two identical names; a line containing only whitespace; a 300-line paste; and a line with a zero-width space in it.

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
| POST | `/sponsor/people/{id}/chapter-leader` | `sponsor` | Grants/revokes the `chapter` scope |
| POST | `/sponsor/paper-forms` | `sponsor` | `{person_id, form_type, received}` |
| GET | `/sponsor/packet` | `sponsor` | HTML print view |
| GET | `/sponsor/packet.pdf` | `sponsor` | Spawns the fat-image worker |
| GET | `/sponsor/invoice` | `sponsor` | Computed from `school_stats` |
| GET/POST/DELETE | `/sponsor/chapter-entries` | `sponsor` or `chapter` | |

### Attendee
| Method | Path | Scope | Notes |
|---|---|---|---|
| GET | `/me/activity-sheet` | `delegate` | Own only |
| PUT | `/me/activity-sheet` | `delegate` | Whole-form replace in one transaction; rejects if locked |
| GET | `/me/adult-sheet` | any adult | |
| PUT | `/me/adult-sheet` | any adult | |
| GET | `/me/catalog` | any session | Filtered by person type, school level, Latin level |

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

### Internal
| Method | Path | Notes |
|---|---|---|
| POST | `/internal/worker-callback` | HMAC-signed; worker reports completion |
| — | cron `warm_reconciler` | Every 5 minutes |
| — | cron `autoexport` | Every 10 minutes, no-op unless enabled and within window |
| — | cron `prune_login_attempts` | Daily |

---

# **Demo seed data**

All fabricated. Generated programmatically and reproducible from a fixed seed.

- **12 schools** — 9 high school, 3 middle school — with realistic-sounding invented California school names, none of them real, at varying stages of registration so the chair dashboard shows a genuine spread.
- **University High School (HS)** fully populated with **30 delegates and 4 adults** (2 sponsors, 2 chaperones), realistic mixed completion: roughly 60% of activity sheets submitted, 40% of paper forms marked received, one cancelled delegate, one restored delegate, and one delegate whose name exercises the particle parser.
- **4 admin accounts** with `*` for the two convention presidents and two technology commissioners.
- **A populated audit log** covering the past several weeks, so the log page shows something real.
- **One partial payment** recorded against Uni so the invoice shows a nonzero balance.
- A **"Reset demo data"** button behind `*`, so the presentation can be rerun cleanly if something goes wrong mid-demo.
