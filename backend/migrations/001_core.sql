-- 001_core.sql -- schools, people, settings, sessions, roles, login attempts.
--
-- Forward-only. Never edit a migration that has run anywhere; add a new one.
--
-- Every index this file needs is declared here, in the same migration that
-- creates its table. Turso bills one row read per row *scanned*, and adding an
-- index to a table that already holds rows triggers a full scan billed at one
-- read per existing row. Retrofitting an index onto `people` in March would
-- cost more reads than every login of the season combined.

-- ---------------------------------------------------------------------------
-- schools
-- ---------------------------------------------------------------------------
-- `kind` separates chapters (who send delegates and get invoiced) from
-- organizations (the state board itself). Admin accounts must hang off some
-- school because people.school_id is NOT NULL, but the state board is not a
-- chapter: it must never appear in the public school count, never appear on the
-- chair dashboard, and never generate an invoice. Keying that off `kind` rather
-- than off a name means adding a second organization in 2028 needs no code
-- change -- the same reason billing_exempt is a flag and not a name check.
--
-- billing_exempt is the *separate* idea that a real chapter owes nothing. SCL
-- and At Large send real people who need real accounts and real forms; they
-- simply are not billed. Do not collapse these two columns into one.
CREATE TABLE schools (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL,
  level           TEXT NOT NULL CHECK (level IN ('MS','HS')),
  kind            TEXT NOT NULL DEFAULT 'chapter' CHECK (kind IN ('chapter','organization')),
  city            TEXT,
  -- Packet scans: waivers and medical forms. A URL string and nothing else.
  -- No code in this repository ever reads this folder. See docs/structure.md.
  drive_folder_id TEXT,
  billing_exempt  INTEGER NOT NULL DEFAULT 0,
  -- An ad-hoc reduction an admin applies by hand: a new-chapter discount, a
  -- hardship arrangement, or the mechanism for honouring a fee change that has
  -- already been invoiced. Subtracted from the computed total, floored at zero.
  --
  -- This is the pressure valve that keeps everything else simple. There is no
  -- fee snapshot per school and no effective date on the fee, because a fee
  -- change is handled by discounting the affected schools and, where money has
  -- already arrived, recording a negative payment. See docs/RUNBOOK.md.
  discount_cents  INTEGER NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
  discount_reason TEXT,                  -- shown on the invoice; say why in words
  status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','withdrawn')),
  notes           TEXT,                  -- fellowship room, volunteer liaison, chair notes
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  -- A chapter sending both middle and high school delegates registers twice, as
  -- two schools, so name alone is not unique but (name, level) is.
  UNIQUE (name, level)
);

-- Serves the chair dashboard and the public MS/HS split. `kind` leads because
-- every one of those queries filters organizations out first.
CREATE INDEX idx_schools_kind_status_level ON schools (kind, status, level);

-- ---------------------------------------------------------------------------
-- people
-- ---------------------------------------------------------------------------
-- One row per human. One code per human, no matter how many roles they hold.
-- `id` is the public-facing badge number printed on the packet sheet, assigned
-- sequentially across all schools, so it is stable and never reused. Nothing
-- here is ever hard-deleted; cancellation is a status change.
CREATE TABLE people (
  id               INTEGER PRIMARY KEY,
  school_id        INTEGER NOT NULL REFERENCES schools(id),
  person_type      TEXT NOT NULL CHECK (person_type IN ('delegate','adult')),
  adult_type       TEXT CHECK (adult_type IN ('sponsor','chaperone','scl','other')),
  adult_type_other TEXT,

  first_name       TEXT NOT NULL,
  middle_name      TEXT,
  last_name        TEXT NOT NULL,
  suffix           TEXT,
  -- Exactly what the sponsor pasted for this row, before parsing. When a
  -- sponsor says "the site got my student's name wrong", this is the evidence.
  raw_name_input   TEXT,

  grade            INTEGER CHECK (grade BETWEEN 6 AND 12),
  latin_level      TEXT CHECK (latin_level IN ('MS-1','MS-2','MS-3','HS-1','HS-2','HS-3','HS-Adv')),
  meal             TEXT CHECK (meal IN ('regular','vegetarian','gluten_free')),
  cell_phone       TEXT,

  -- Adults only. Delegates are as young as eleven; we collect no contact
  -- information from them at all and everything routes through the sponsor.
  -- The CHECK at the bottom of this table is what enforces that, not app code.
  email             TEXT,
  latin_knowledge   TEXT CHECK (latin_knowledge IN ('none','novice','intermediate','advanced')),
  availability_note TEXT,

  -- Delegates only. Also the tiebreaker for two delegates with the same name in
  -- one chapter, which is why the parser asks the sponsor to fill it in.
  guardian_name    TEXT,
  guardian_phone   TEXT,

  -- HMAC-SHA256(pepper, normalized_code). The pepper lives in Modal Secrets and
  -- never in this database, so a dump of this table alone cannot brute-force
  -- the 45 bits of entropy in a code.
  code_hmac        TEXT NOT NULL,
  code_prefix      TEXT NOT NULL CHECK (code_prefix IN ('SPO','DEL','VOL','ADM')),
  -- Rotating the pepper means reissuing and reprinting every code. It is a
  -- break-glass procedure, not routine; this column exists so it is possible.
  pepper_version   INTEGER NOT NULL DEFAULT 1,
  code_issued_at   TEXT NOT NULL,

  -- THERE ARE NO REFUNDS. An event this size runs on pre-payment, so the two
  -- cancelled states are not cosmetic -- they are the whole billing rule:
  --
  --   'active'         attending, billable.
  --   'cancelled'      withdrew before their chapter's payment arrived.
  --                    Not attending, NOT billable. The invoice falls.
  --   'cancelled_paid' withdrew after payment. Not attending, STILL billable,
  --                    so the balance continues to read correctly instead of
  --                    showing a credit nobody intends to refund.
  --
  -- Which one applies is decided by whether the school has recorded any payment
  -- at the moment of cancellation -- see backend/lib/roster.py. Both states
  -- block sign-in; neither is ever hard-deleted, and both can be restored.
  status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','cancelled','cancelled_paid')),
  cancelled_at     TEXT,
  forms_unlocked   INTEGER NOT NULL DEFAULT 0,   -- admin override past the lock date

  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,

  -- Which roster import created this person, when one did. NULL for people
  -- added one at a time. This is what a repeated commit reads back to return
  -- the first commit's result, and it answers "where did this row come from?"
  -- years later. Declared without a REFERENCES clause because roster_imports is
  -- created in a later migration; the link is by convention and by the index.
  roster_import_id INTEGER,

  -- The person-type split is enforced here rather than trusted to application
  -- code, because some future endpoint written in a hurry will forget. Assert
  -- these in tests too: a later migration could quietly drop them.
  CHECK (person_type = 'adult'    OR adult_type IS NULL),
  CHECK (person_type = 'delegate' OR (grade IS NULL AND latin_level IS NULL)),
  CHECK (person_type = 'adult'    OR (email IS NULL AND latin_knowledge IS NULL AND availability_note IS NULL)),
  CHECK (person_type = 'delegate' OR (guardian_name IS NULL AND guardian_phone IS NULL))
);

-- Login is a single indexed equality lookup on this column and nothing else.
CREATE UNIQUE INDEX idx_people_code_hmac ON people (code_hmac);
-- The index the sponsor roster and every chair count depend on. Without it, one
-- roster page load scans every person in the database.
CREATE INDEX idx_people_school ON people (school_id, status, person_type);
CREATE INDEX idx_people_sort   ON people (school_id, last_name, first_name);
-- Partial: almost every row is NULL here, and only imported rows are ever
-- looked up this way.
CREATE INDEX idx_people_import ON people (roster_import_id)
  WHERE roster_import_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- settings
-- ---------------------------------------------------------------------------
-- Everything a future commissioner would otherwise need a deploy to change.
-- Brand and layout are code and are expected to change; convention operations
-- are data and must never be code. If running a convention requires a deploy,
-- something is in the wrong layer.
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

-- ---------------------------------------------------------------------------
-- sessions
-- ---------------------------------------------------------------------------
-- A session token is 32 random bytes stored as a plain SHA-256 hash. No pepper
-- is needed: at 256 bits there is nothing to brute-force. The raw code is never
-- stored on the device -- only this token is.
--
-- Assume shared devices. A school Chromebook will hold sessions for a dozen
-- delegates over a weekend, so revocation has to be real and server-side.
CREATE TABLE sessions (
  id                      INTEGER PRIMARY KEY,
  person_id               INTEGER NOT NULL REFERENCES people(id),
  token_hash              TEXT NOT NULL,
  -- Set only on impersonation sessions. Its presence is what makes a session
  -- read-only by default and what puts both names in the audit log.
  impersonator_person_id  INTEGER REFERENCES people(id),
  impersonation_can_write INTEGER NOT NULL DEFAULT 0,
  created_at              TEXT NOT NULL,
  last_seen_at            TEXT NOT NULL,
  expires_at              TEXT NOT NULL,
  revoked_at              TEXT,
  user_agent              TEXT,
  -- Hashed, never raw. Most subjects here are minors and an IP is personal data.
  ip_hash                 TEXT
);
CREATE UNIQUE INDEX idx_sessions_token  ON sessions (token_hash);
CREATE INDEX        idx_sessions_person ON sessions (person_id, revoked_at);

-- ---------------------------------------------------------------------------
-- roles and scopes
-- ---------------------------------------------------------------------------
-- The ONLY path from a person to a scope is person_roles -> roles ->
-- role_scopes. There is deliberately no person_scopes table and there must
-- never be one: a single direct grant would make every authorization test in
-- the suite a lie, because the tests check this path and only this path.
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
  -- '*' subsumes everything: announcements, audit, exports, role management,
  -- impersonation, and the Drive folder links. The three identity scopes
  -- (sponsor, delegate, chapter) are ALWAYS school-limited; the four
  -- administrative scopes are global rather than per-school.
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

-- ---------------------------------------------------------------------------
-- login_attempts
-- ---------------------------------------------------------------------------
-- attempted_code_hmac is the HMAC of whatever was typed, valid or not, under
-- the same pepper. Without it there is nothing to rate-limit against: a failed
-- attempt matches no row in `people` by definition. Storing it is safe -- it is
-- a keyed hash of a guess, and it is what distinguishes one delegate fumbling
-- their own code from someone walking the keyspace. Never store the raw guess.
CREATE TABLE login_attempts (
  id                  INTEGER PRIMARY KEY,
  attempted_code_hmac TEXT NOT NULL,
  code_prefix         TEXT,
  ip_hash             TEXT NOT NULL,
  succeeded           INTEGER NOT NULL,
  attempted_at        TEXT NOT NULL
);
-- Both rate limits are counted with an indexed range scan over a handful of
-- rows. An unindexed COUNT(*) here would be paid by every login at convention.
CREATE INDEX idx_login_attempts_ip   ON login_attempts (ip_hash, attempted_at);
CREATE INDEX idx_login_attempts_code ON login_attempts (attempted_code_hmac, attempted_at);
