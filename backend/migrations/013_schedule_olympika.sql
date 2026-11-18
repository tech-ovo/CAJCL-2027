-- 013_schedule_olympika.sql -- the convention schedule, and Olympika sign-ups.
--
-- Two things that meet in one table.
--
--   THE MASTER SCHEDULE (`schedule_items`) is what every delegate, sponsor and
--   chaperone reads to know where to be. The Logistics chair keeps it.
--
--   OLYMPIKA (`olympika_*`) is the athletics program: track events delegates
--   enter one by one, and team events like Ultimate Frisbee that a delegate
--   enters on behalf of a team. The Athletics Director sets up the events,
--   sees every sign-up, sets when the heats and games are, and presses a
--   button to deal the entrants into heats or draw a bracket.
--
-- Whatever the Athletics Director schedules is WRITTEN INTO schedule_items by
-- lib/olympika.sync_schedule, in the same transaction as the change, so the
-- master schedule can never disagree with the heats. Those rows are marked
-- source = 'olympika' and the Logistics chair cannot edit them.

-- ---------------------------------------------------------------------------
-- Two scopes, two roles
-- ---------------------------------------------------------------------------
-- Narrow and global, exactly like `judge` and `activities`: deliberately NOT
-- in auth.ADMIN_SCOPES, so `require_school` never treats either as reaching a
-- chapter's roster. The Athletics Director sees names and chapters of the
-- people entered in Olympika, and nothing else; the Logistics chair sees no
-- people at all.
--
-- SQLite cannot alter a CHECK constraint, so role_scopes is rebuilt, exactly
-- as 008 and 012 did.
CREATE TABLE role_scopes_new (
  role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  scope   TEXT NOT NULL CHECK (scope IN ('*','registration','academics','awards',
                                         'sponsor','delegate','chapter','judge',
                                         'activities','athletics','logistics')),
  PRIMARY KEY (role_id, scope)
);
INSERT INTO role_scopes_new (role_id, scope) SELECT role_id, scope FROM role_scopes;
DROP TABLE role_scopes;
ALTER TABLE role_scopes_new RENAME TO role_scopes;

INSERT INTO roles (key, name, description, is_system, created_at) VALUES
  ('athletics_director', 'Athletics Director',
   'Runs Olympika: its events, every sign-up, the heats and brackets, and when each is played.',
   1, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('logistics_chair', 'Logistics Chair',
   'Keeps the master convention schedule: what happens, where, and when.',
   1, strftime('%Y-%m-%dT%H:%M:%SZ','now'));
INSERT INTO role_scopes (role_id, scope)
SELECT id, 'athletics' FROM roles WHERE key = 'athletics_director';
INSERT INTO role_scopes (role_id, scope)
SELECT id, 'logistics' FROM roles WHERE key = 'logistics_chair';

-- ---------------------------------------------------------------------------
-- olympika_events
-- ---------------------------------------------------------------------------
-- An event is a row, not code: the Athletics Director adds, renames and
-- removes them, often during convention itself.
--
-- `kind` decides how people enter and what the Director does next:
--   individual  a delegate signs themself up; "Assign heats" deals the
--               entrants into the heats.
--   team        a delegate signs up a TEAM (they become its captain -- one
--               delegate per team); "Form bracket" draws a single-elimination
--               bracket of the teams.
--
-- `signup_open` is the Director's switch. Events can be set up before
-- convention and opened on the day, or closed when the heats are drawn.
--
-- `max_per_school` is entrants (individual) or teams (team) one chapter may
-- enter; NULL is no limit.
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
-- Two events called "Kickball" would be one event split in two.
CREATE UNIQUE INDEX idx_olympika_events_name
  ON olympika_events (name COLLATE NOCASE);

-- ---------------------------------------------------------------------------
-- olympika_heats
-- ---------------------------------------------------------------------------
-- The sessions an individual event is run in. `starts_at` and `ends_at` are
-- UTC instants (lib/clock.py) and may be empty while the Director is still
-- deciding; a heat with no start is not on the master schedule yet.
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
-- Also the index every "heats of this event" read goes through.
CREATE UNIQUE INDEX idx_olympika_heats_event
  ON olympika_heats (event_id, number);

-- ---------------------------------------------------------------------------
-- olympika_signups -- a delegate entering an individual event
-- ---------------------------------------------------------------------------
-- `heat_id` and `lane` are empty until "Assign heats" (or the Director moves
-- somebody by hand). One sign-up per delegate per event.
CREATE TABLE olympika_signups (
  id             INTEGER PRIMARY KEY,
  event_id       INTEGER NOT NULL REFERENCES olympika_events(id),
  person_id      INTEGER NOT NULL REFERENCES people(id),
  school_id      INTEGER NOT NULL REFERENCES schools(id),
  heat_id        INTEGER REFERENCES olympika_heats(id),
  lane           INTEGER,
  signed_up_at   TEXT NOT NULL
);
-- The Director's list for one event reads through this, by its leading column.
CREATE UNIQUE INDEX idx_olympika_signups_event
  ON olympika_signups (event_id, person_id);
-- A delegate's own sign-ups.
CREATE INDEX idx_olympika_signups_person
  ON olympika_signups (person_id);
-- Counting a chapter's entrants against `max_per_school`.
CREATE INDEX idx_olympika_signups_school
  ON olympika_signups (event_id, school_id);
-- Deleting a heat looks for the people in it.
CREATE INDEX idx_olympika_signups_heat
  ON olympika_signups (heat_id);

-- ---------------------------------------------------------------------------
-- olympika_teams -- a delegate entering a team event
-- ---------------------------------------------------------------------------
-- ONE DELEGATE SIGNS UP PER TEAM. The captain is the only person recorded;
-- the team's other players are not entered anywhere. A captain may captain
-- one team per event, and a chapter may field several if the event allows.
--
-- `captain_person_id` is emptied (never the row deleted) when the captain is
-- redacted after a bracket has been drawn, so the bracket keeps its shape.
-- `seed` is the team's place in the draw, 1 = best.
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
-- A delegate captains at most one team per event. NULL captains do not collide.
CREATE UNIQUE INDEX idx_olympika_teams_captain
  ON olympika_teams (event_id, captain_person_id);
-- Two teams called "Eagles" in one bracket cannot be told apart.
CREATE UNIQUE INDEX idx_olympika_teams_name
  ON olympika_teams (event_id, name COLLATE NOCASE);
-- A chapter's teams, for `max_per_school`.
CREATE INDEX idx_olympika_teams_school
  ON olympika_teams (event_id, school_id);
-- A delegate's own teams.
CREATE INDEX idx_olympika_teams_person
  ON olympika_teams (captain_person_id);

-- ---------------------------------------------------------------------------
-- olympika_matches -- a bracket
-- ---------------------------------------------------------------------------
-- Single elimination. `round` counts from 1 (the first round played) and
-- `slot` from 0 within the round; the winner of (round, slot) goes to
-- (round + 1, slot / 2) -- as team A when slot is even, team B when odd.
--
-- A first-round match with a team A and no team B is a BYE: its winner is set
-- when the bracket is drawn and it is never scheduled or shown as a game.
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
-- Also the index every "matches of this event" read goes through.
CREATE UNIQUE INDEX idx_olympika_matches_slot
  ON olympika_matches (event_id, round, slot);
-- A team's own games.
CREATE INDEX idx_olympika_matches_team_a ON olympika_matches (team_a_id);
CREATE INDEX idx_olympika_matches_team_b ON olympika_matches (team_b_id);
-- Deleting a team checks no game names it as the winner.
CREATE INDEX idx_olympika_matches_winner ON olympika_matches (winner_id);

-- ---------------------------------------------------------------------------
-- schedule_items -- THE MASTER SCHEDULE
-- ---------------------------------------------------------------------------
-- `starts_at` / `ends_at` are UTC instants, as everywhere (lib/clock.py); the
-- editor takes a California date and time and the server converts. `ends_at`
-- is empty for a moment rather than a span ("Lights out").
--
-- `published` lets the Logistics chair draft a block before delegates see it.
--
-- `source` says who owns the row:
--   manual    the Logistics chair's, edited freely.
--   olympika  written by lib/olympika.sync_schedule from a heat or a round of
--             a bracket. `source_key` ('heat:12', 'round:3:2') is how the sync
--             finds its own row again; `olympika_event_id` ties it to the
--             event. Only that code changes or removes these rows.
CREATE TABLE schedule_items (
  id                 INTEGER PRIMARY KEY,
  title              TEXT NOT NULL,
  description        TEXT,
  location           TEXT,
  starts_at          TEXT NOT NULL,
  ends_at            TEXT,
  published          INTEGER NOT NULL DEFAULT 1 CHECK (published IN (0, 1)),
  source             TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','olympika')),
  source_key         TEXT,
  olympika_event_id  INTEGER REFERENCES olympika_events(id),
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL
);
CREATE INDEX idx_schedule_items_starts ON schedule_items (starts_at, id);
-- The sync finds one event's rows through this, and deleting an event does.
CREATE INDEX idx_schedule_items_event ON schedule_items (olympika_event_id);
CREATE UNIQUE INDEX idx_schedule_items_key
  ON schedule_items (source_key) WHERE source_key IS NOT NULL;

-- ---------------------------------------------------------------------------
-- A first event
-- ---------------------------------------------------------------------------
-- Ultimate Frisbee, closed: nobody signs a team up until the Director opens
-- it. The rest of Olympika is the Director's to add.
INSERT INTO olympika_events (name, description, kind, location, signup_open,
                             max_per_school, sort_order, created_at, updated_at)
VALUES ('Ultimate Frisbee',
        'Teams of any size from one chapter. One delegate signs up for the team and is its captain.',
        'team', NULL, 0, NULL, 50,
        strftime('%Y-%m-%dT%H:%M:%SZ','now'), strftime('%Y-%m-%dT%H:%M:%SZ','now'));
