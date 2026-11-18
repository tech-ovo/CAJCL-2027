-- 014_potluck.sql -- the activities potluck.
--
-- The Activities chair posts a list of activities that need helpers (a game, a
-- craft table, a quiet room). Every attendee sees the list on their own sheet
-- and ticks the ones they would help run, the way they tick Olympika events.
--
--   * An ADULT's pick is approved at once: they speak for themselves.
--   * A DELEGATE's pick waits for their sponsor, who approves or declines it.
--     A pick a sponsor (or a chair) enters for a delegate is approved at once.
--   * The Activities chair sees only the APPROVED volunteers for each
--     activity, with name and chapter, and nothing else about them.
--
-- Activities are rows, not code: they change every year and during the
-- convention. They are NOT catalog items, because the catalog is replaced
-- whole on every save of a sheet (nothing in it can carry a decision that
-- survives that), and because these carry a time, a place and a cap.

-- ---------------------------------------------------------------------------
-- potluck_activities
-- ---------------------------------------------------------------------------
-- `starts_at` / `ends_at` are UTC instants, as everywhere (lib/clock.py); the
-- chair types a California date and time. Both are empty for an activity that
-- is not scheduled yet. An activity WITH a time is written onto the master
-- schedule by lib/potluck.sync_schedule, in the same transaction.
--
-- `capacity` is the number of helpers wanted, or empty for no limit. It counts
-- pending AND approved picks, so a full activity stops taking picks and nobody
-- is approved into a place that is not there. A declined pick frees its place.
--
-- `open` is the chair's switch: a closed activity takes no NEW picks, but the
-- ones already made stand. It has nothing to do with whether it is on the
-- schedule.
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
-- Two activities called "Face painting" would be one that splits its helpers.
CREATE UNIQUE INDEX idx_potluck_activities_name
  ON potluck_activities (name COLLATE NOCASE);

-- ---------------------------------------------------------------------------
-- potluck_signups
-- ---------------------------------------------------------------------------
-- One row per person per activity. The sheet is saved as a whole, but this
-- table is NOT replaced whole: the sponsor's decision lives here, and a save
-- that deleted and re-inserted would throw it away. lib/potluck.save_picks
-- keeps the rows a person keeps.
--
--   pending    waiting for the sponsor. Counts against the cap.
--   approved   counts against the cap; the Activities chair sees these.
--   declined   the sponsor said no. Does not count. Stays on the student's
--              sheet, so they can see it, until they pick it again (which
--              makes it pending again) or the sponsor reverses it.
--
-- `decided_by_person_id` is who made the status what it is: the sponsor, or
-- the person themselves for an adult.
CREATE TABLE potluck_signups (
  person_id            INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  activity_id          INTEGER NOT NULL REFERENCES potluck_activities(id) ON DELETE CASCADE,
  status               TEXT NOT NULL CHECK (status IN ('pending','approved','declined')),
  requested_at         TEXT NOT NULL,
  decided_at           TEXT,
  decided_by_person_id INTEGER REFERENCES people(id),
  PRIMARY KEY (person_id, activity_id)
);
-- A person's own picks read through the primary key's leading column. These
-- two are for the chair's list of one activity, and the cap count.
CREATE INDEX idx_potluck_signups_activity ON potluck_signups (activity_id, status);

-- ---------------------------------------------------------------------------
-- The master schedule learns a third owner
-- ---------------------------------------------------------------------------
-- SQLite cannot alter a CHECK constraint, so schedule_items is rebuilt, as
-- role_scopes was in 008, 012 and 013. Nothing references it. A potluck row
-- is marked source = 'potluck' with source_key 'potluck:<id>'; only
-- lib/potluck.sync_schedule changes or removes it, and the Logistics chair's
-- endpoints refuse it, exactly as they refuse Olympika's.
CREATE TABLE schedule_items_new (
  id                  INTEGER PRIMARY KEY,
  title               TEXT NOT NULL,
  description         TEXT,
  location            TEXT,
  starts_at           TEXT NOT NULL,
  ends_at             TEXT,
  published           INTEGER NOT NULL DEFAULT 1 CHECK (published IN (0, 1)),
  source              TEXT NOT NULL DEFAULT 'manual'
                        CHECK (source IN ('manual','olympika','potluck')),
  source_key          TEXT,
  olympika_event_id   INTEGER REFERENCES olympika_events(id),
  potluck_activity_id INTEGER REFERENCES potluck_activities(id),
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);
INSERT INTO schedule_items_new
  (id, title, description, location, starts_at, ends_at, published, source,
   source_key, olympika_event_id, created_at, updated_at)
SELECT id, title, description, location, starts_at, ends_at, published, source,
       source_key, olympika_event_id, created_at, updated_at
FROM schedule_items;
DROP TABLE schedule_items;
ALTER TABLE schedule_items_new RENAME TO schedule_items;
CREATE INDEX idx_schedule_items_starts ON schedule_items (starts_at, id);
CREATE INDEX idx_schedule_items_event ON schedule_items (olympika_event_id);
CREATE INDEX idx_schedule_items_potluck ON schedule_items (potluck_activity_id);
CREATE UNIQUE INDEX idx_schedule_items_key
  ON schedule_items (source_key) WHERE source_key IS NOT NULL;

-- The Activities chair now runs two things.
UPDATE roles SET description =
  'Runs the at-convention photo contest and the activities potluck: the categories, the activities, every photo, and who is helping.'
WHERE key = 'activities_chair';
