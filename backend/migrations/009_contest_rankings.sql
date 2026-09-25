-- 009_contest_rankings.sql -- judges rank their top N; the rubric goes.
--
-- 008 had each judge score every entry against a rubric. In practice a judge
-- reads a division and picks the best few, so that is what is recorded now:
-- per division (and per Publicity category), each judge hands in an ordered
-- list of their top N entries. The results combine the judges' lists.
--
-- N is per contest, `contests.places`, and the Academics chairs change it on
-- the Results page. It may change after judges have handed in: a list longer
-- than N counts only its first N, and a shorter one counts as it stands and
-- shows the judge that it needs more.

-- ---------------------------------------------------------------------------
-- The rubric and per-entry scores are gone
-- ---------------------------------------------------------------------------
-- Nothing else references either table. Any scores already handed in were
-- against a rubric that no longer exists, so they are not carried over.
DROP TABLE contest_scores;
DROP TABLE contest_criteria;

-- How many places each contest awards, and so how many entries a judge ranks.
ALTER TABLE contests ADD COLUMN places INTEGER NOT NULL DEFAULT 3
  CHECK (places BETWEEN 1 AND 20);

-- ---------------------------------------------------------------------------
-- contest_ballots
-- ---------------------------------------------------------------------------
-- One judge's ranking of one division (and, for Publicity, one category) of
-- one contest. A draft is work in progress and is left out of the results.
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
-- The judge's own page reads through the unique index; the results read one
-- contest's ballots through this one.
CREATE INDEX idx_contest_ballots_item ON contest_ballots (item_id, status);

-- ---------------------------------------------------------------------------
-- contest_ballot_places
-- ---------------------------------------------------------------------------
-- The entries on a ballot, in order: place 1 is the judge's best. Places on a
-- ballot are 1..k with no gaps, and an entry appears on a ballot once.
--
-- Replacing or withdrawing an entry deletes it from every ballot and puts
-- those ballots back to draft: the judge ranked different work, and their
-- list now has a gap to fill.
CREATE TABLE contest_ballot_places (
  ballot_id  INTEGER NOT NULL REFERENCES contest_ballots(id) ON DELETE CASCADE,
  place      INTEGER NOT NULL CHECK (place > 0),
  entry_id   INTEGER NOT NULL REFERENCES contest_entries(id) ON DELETE CASCADE,
  PRIMARY KEY (ballot_id, place),
  UNIQUE (ballot_id, entry_id)
);
CREATE INDEX idx_contest_ballot_places_entry ON contest_ballot_places (entry_id);
