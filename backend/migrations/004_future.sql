-- 004_future.sql -- schema only, no UI in the demo.
--
-- These tables exist now so that building contests and awards later is not a
-- migration against populated tables. Adding an index to a populated table
-- costs one row read per existing row; doing it in March is the expensive time.

-- ---------------------------------------------------------------------------
-- contest_submissions
-- ---------------------------------------------------------------------------
-- Pre-convention contests, graphic arts entries, and lost-and-found photos all
-- follow one upload path: the browser posts the file to Modal, Modal hands it to
-- the Apps Script puppet, and the puppet files it under the AUTOMATED Drive root
-- -- organized by contest, then by chapter -- and returns a Drive file ID.
--
-- No file bytes are ever stored in the database. Chairs are granted access to
-- the relevant Drive folder directly and judge there; this site stores pointers.
--
-- This root is entirely separate from the per-school packet folders holding
-- medical forms and waivers, which no code touches and only scope '*' can see
-- the link to. Keeping the two roots physically separate is what stops a future
-- change to this automated path from widening access to minors' medical data.
-- Do not merge them for convenience.
--
-- person_id is nullable because lost-and-found photos belong to no one. SQLite
-- treats NULLs as distinct in a UNIQUE index, so those rows do not collide.
CREATE TABLE contest_submissions (
  id              INTEGER PRIMARY KEY,
  person_id       INTEGER REFERENCES people(id),
  school_id       INTEGER NOT NULL REFERENCES schools(id),
  item_id         INTEGER NOT NULL REFERENCES catalog_items(id),
  drive_file_id   TEXT NOT NULL,
  drive_folder_id TEXT NOT NULL,
  original_name   TEXT NOT NULL,
  mime_type       TEXT,
  size_bytes      INTEGER,
  submitted_at    TEXT NOT NULL,
  UNIQUE (person_id, item_id)
);
CREATE INDEX idx_contest_submissions_item   ON contest_submissions (item_id);
CREATE INDEX idx_contest_submissions_school ON contest_submissions (school_id);

-- ---------------------------------------------------------------------------
-- scores
-- ---------------------------------------------------------------------------
-- Awards infrastructure. `points` is the sweepstakes contribution and is stored
-- rather than derived, because the points value of a placement is a rule that
-- changes between years and a stored number keeps old years readable.
CREATE TABLE scores (
  id         INTEGER PRIMARY KEY,
  person_id  INTEGER REFERENCES people(id),
  school_id  INTEGER REFERENCES schools(id),
  item_id    INTEGER REFERENCES catalog_items(id),
  raw_score  REAL,
  placement  INTEGER,
  points     INTEGER NOT NULL DEFAULT 0,
  entered_by INTEGER REFERENCES people(id),
  created_at TEXT NOT NULL
);
CREATE INDEX idx_scores_person ON scores (person_id);
CREATE INDEX idx_scores_school ON scores (school_id);
CREATE INDEX idx_scores_item   ON scores (item_id);
