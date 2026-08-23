-- 002_forms_catalog.sql -- online forms, paper-form attestation, the activity
-- and role catalog, and everything a person selects from it.

-- ---------------------------------------------------------------------------
-- form_submissions
-- ---------------------------------------------------------------------------
-- One row per person per form. The form is submitted once, not saved on every
-- keystroke, and stays editable by its owner until the lock date.
--
-- The UNIQUE constraint below creates the index that kills the roster N+1. Do
-- NOT add a second index on person_id alone: the unique index already covers
-- that prefix, and a duplicate would cost storage and slow every write for
-- nothing.
CREATE TABLE form_submissions (
  id           INTEGER PRIMARY KEY,
  person_id    INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  form_type    TEXT NOT NULL CHECK (form_type IN ('student_activity','adult_registration')),
  status       TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','submitted')),
  submitted_at TEXT,
  updated_at   TEXT NOT NULL,
  UNIQUE (person_id, form_type)
);

-- ---------------------------------------------------------------------------
-- paper_forms
-- ---------------------------------------------------------------------------
-- Waivers and medical forms are paper. They are signed by hand, mailed with the
-- check, and scanned by the sponsor into that school's own Drive folder. This
-- table records only the sponsor's attestation that a form was received -- it
-- holds no medical information and points at no file.
--
-- Chairs see the attestation. Only scope '*' sees the Drive link. Nobody else
-- touches minors' medical information, and no code in this repository reads it.
--
-- The CHECK ties form_type to the person's type. Without it a delegate could
-- acquire an 'adult_medical' row, and the roster query -- which matches medical
-- forms with IN ('student_medical','adult_medical') -- would return that person
-- twice, silently double-counting them on the sponsor's own screen.
CREATE TABLE paper_forms (
  person_id           INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  form_type           TEXT NOT NULL CHECK (form_type IN ('student_waiver','student_medical','adult_medical')),
  received            INTEGER NOT NULL DEFAULT 0,
  marked_by_person_id INTEGER REFERENCES people(id),
  marked_at           TEXT,
  PRIMARY KEY (person_id, form_type)
);

-- ---------------------------------------------------------------------------
-- catalog
-- ---------------------------------------------------------------------------
-- Adding a new ludus for 2028 must require no code. Categories, items,
-- sub-options, eligibility by Latin level and school level, selection minimums
-- and maximums, and whether a rule blocks or warns are all rows, all editable
-- from the admin dashboard.
--
-- The whole catalog is roughly 150 rows and is read on nearly every form load,
-- so it is loaded once per container into memory and refreshed on mutation.
-- It is never queried per request. See backend/lib/catalog.py.
CREATE TABLE catalog_categories (
  id             INTEGER PRIMARY KEY,
  key            TEXT NOT NULL UNIQUE,
  name           TEXT NOT NULL,
  description    TEXT,
  applies_to     TEXT NOT NULL CHECK (applies_to IN ('delegate','adult')),
  min_selections INTEGER,
  max_selections INTEGER,
  -- 'block' refuses the submission. 'warn' shows a message the person can
  -- submit past. Academic testing blocks at 1-3; adult roles warn at 2.
  enforcement    TEXT NOT NULL DEFAULT 'none' CHECK (enforcement IN ('block','warn','none')),
  sort_order     INTEGER NOT NULL DEFAULT 0,
  active         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE catalog_items (
  id                     INTEGER PRIMARY KEY,
  category_id            INTEGER NOT NULL REFERENCES catalog_categories(id),
  name                   TEXT NOT NULL,
  description            TEXT,
  -- CSV of latin_level values; NULL means all levels. CSV rather than a join
  -- table because this is read into memory whole and never queried against.
  eligible_latin_levels  TEXT,
  eligible_school_levels TEXT,   -- CSV of 'MS','HS'; NULL means all
  -- 'chapter' items are registered once per school by a sponsor or a delegate
  -- the sponsor has promoted to chapter leader -- never by an individual
  -- delegate on their own activity sheet. Kickball, Fugepilam, Ultimate.
  registration_scope     TEXT NOT NULL DEFAULT 'individual'
                           CHECK (registration_scope IN ('individual','chapter')),
  max_sub_selections     INTEGER,
  -- Every current adult role needs either nothing or advanced Latin, but all
  -- four levels are here so a future chair can mark a role as needing
  -- intermediate Latin from the dashboard without a migration.
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

-- ---------------------------------------------------------------------------
-- selections
-- ---------------------------------------------------------------------------
-- Editing an activity sheet replaces ALL selections for that person inside a
-- single transaction: delete then insert. Do not diff. Diffing is where the
-- bugs live and there are never more than a few dozen rows.
CREATE TABLE activity_selections (
  id         INTEGER PRIMARY KEY,
  person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  item_id    INTEGER NOT NULL REFERENCES catalog_items(id),
  created_at TEXT NOT NULL,
  UNIQUE (person_id, item_id)
);
CREATE INDEX idx_activity_selections_person ON activity_selections (person_id);
-- Exists for the Academics/Activities/Athletics chairs' "how many are taking
-- Mythology" counts, which would otherwise scan every selection row.
CREATE INDEX idx_activity_selections_item   ON activity_selections (item_id);

CREATE TABLE activity_selection_options (
  selection_id INTEGER NOT NULL REFERENCES activity_selections(id) ON DELETE CASCADE,
  option_id    INTEGER NOT NULL REFERENCES catalog_item_options(id),
  PRIMARY KEY (selection_id, option_id)
);

-- Team entries belong to the school, not to a person, which is why they survive
-- a delegate cancelling. created_by_person_id records who entered them.
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
CREATE INDEX idx_chapter_entries_item   ON chapter_entries (item_id);

CREATE TABLE adult_role_selections (
  person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  item_id    INTEGER NOT NULL REFERENCES catalog_items(id),
  created_at TEXT NOT NULL,
  PRIMARY KEY (person_id, item_id)
);
CREATE INDEX idx_adult_roles_item ON adult_role_selections (item_id);
