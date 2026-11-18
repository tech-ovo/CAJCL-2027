-- 012_photo_contest.sql -- the at-convention photo contest.
--
-- During convention, delegates take photos for categories the Activities chair
-- sets up ("Best flower photo", "Best stuffed animal photo") and upload them
-- from their phones. The chair sees every photo, with whose it is, on one
-- page, and adds, renames, opens, closes and deletes categories there.
--
-- Categories are rows, not code: they change from year to year and often
-- during the convention itself.

-- ---------------------------------------------------------------------------
-- The `activities` scope
-- ---------------------------------------------------------------------------
-- The Activities chair needs every photo with a name and a chapter on it, and
-- nothing else: not rosters, not money, not test counts. So, like `judge`,
-- `activities` is global but narrow -- deliberately NOT in auth.ADMIN_SCOPES,
-- so `require_school` never treats it as reaching any chapter's roster.
--
-- SQLite cannot alter a CHECK constraint, so role_scopes is rebuilt, exactly
-- as 008 did. Nothing references it, and it holds a few dozen rows.
CREATE TABLE role_scopes_new (
  role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  scope   TEXT NOT NULL CHECK (scope IN ('*','registration','academics','awards',
                                         'sponsor','delegate','chapter','judge',
                                         'activities')),
  PRIMARY KEY (role_id, scope)
);
INSERT INTO role_scopes_new (role_id, scope) SELECT role_id, scope FROM role_scopes;
DROP TABLE role_scopes;
ALTER TABLE role_scopes_new RENAME TO role_scopes;

INSERT INTO roles (key, name, description, is_system, created_at) VALUES
  ('activities_chair', 'Activities Chair',
   'Runs the at-convention photo contest: its categories, and every photo submitted.',
   1, strftime('%Y-%m-%dT%H:%M:%SZ','now'));
INSERT INTO role_scopes (role_id, scope)
SELECT id, 'activities' FROM roles WHERE key = 'activities_chair';

-- ---------------------------------------------------------------------------
-- photo_categories
-- ---------------------------------------------------------------------------
-- `accepting` is the chair's switch: a category takes photos only while it is
-- on, so one can be set up before convention and opened on the day, or closed
-- before the awards assembly.
--
-- The Drive folders are found or made on the first photo and remembered here,
-- so later uploads skip two round trips to Apps Script -- at convention, many
-- phones upload at once and the puppet runs only so many requests together.
-- Renaming a category does not rename its folder.
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
-- Two categories called "Best flower photo" would be one contest split in two.
CREATE UNIQUE INDEX idx_photo_categories_name
  ON photo_categories (name COLLATE NOCASE);

-- ---------------------------------------------------------------------------
-- photo_entries
-- ---------------------------------------------------------------------------
-- One photo per delegate per category; a second upload replaces the first.
--
-- NO IMAGE BYTES ARE STORED HERE. Both the photo and its small thumbnail live
-- in the same AUTOMATED Drive root as contest entries (drive.contests_root),
-- under "Photo Contest/<category>". Never the per-school packet folders.
--
-- The browser re-encodes every photo before sending it, which drops the
-- location and camera details a phone writes into the file; the server strips
-- any that survive (lib/photos.py). The thumbnail is made by the browser too.
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
-- A delegate's own photos read through this, by its leading column.
CREATE UNIQUE INDEX idx_photo_entries_person
  ON photo_entries (person_id, category_id);
-- The chair's page, and deleting a category, read one category at a time.
CREATE INDEX idx_photo_entries_category
  ON photo_entries (category_id, submitted_at);

-- A first category, so the page is not empty when the chair first opens it.
-- Closed: nobody uploads until the chair opens it at convention.
INSERT INTO photo_categories (name, description, accepting, sort_order,
                              created_at, updated_at) VALUES
  ('Best flower photo',
   'A flower you found at convention. Taken by you, during convention.',
   0, 10, strftime('%Y-%m-%dT%H:%M:%SZ','now'), strftime('%Y-%m-%dT%H:%M:%SZ','now'));
