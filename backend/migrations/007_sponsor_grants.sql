-- 007_sponsor_grants.sql -- one sponsor, more than one chapter.
--
-- THE PROBLEM. `people.school_id` is a single column, and it is the right
-- shape for almost everybody: a delegate belongs to one chapter, a chaperone
-- travels with one chapter, and the number printed beside their name is that
-- chapter's number and their place in it. Changing that column into a
-- relationship to serve a case that has not yet happened would rewrite the
-- meaning of every person in the system.
--
-- So a sponsor still BELONGS to one chapter -- their own, the one their number
-- comes from -- and this table records the additional chapters they may act
-- for. A teacher who moved schools mid-year, a district where one person
-- covers the middle school and the high school, a sponsor covering for a
-- colleague on leave.
--
-- WHAT THIS TABLE IS NOT. It is not a way to give somebody a scope. Scopes
-- reach a person only through roles -- person_roles, roles, role_scopes -- and
-- nothing here changes that. A grant widens WHICH CHAPTERS an existing scope
-- reaches; somebody with no sponsor role gets nothing from a row in here, and
-- the endpoint that writes one refuses a person who does not already hold the
-- sponsor role.
--
-- WHY IT IS SAFE TO READ ON EVERY REQUEST. `authenticate` only asks for grants
-- when the person already holds the sponsor role, so a delegate signing in
-- costs nothing, and a sponsor costs one lookup on the unique index below --
-- on the connection the request already has open.

CREATE TABLE sponsor_school_grants (
  id                    INTEGER PRIMARY KEY,
  person_id             INTEGER NOT NULL REFERENCES people(id),
  school_id             INTEGER NOT NULL REFERENCES schools(id),
  -- Who did this, kept here as well as in the audit log: the log is the
  -- narrative and this is the current state, and answering "why does this
  -- person have access to Pinnacle Bay" should not need a log search.
  granted_by_person_id  INTEGER REFERENCES people(id),
  granted_at            TEXT NOT NULL,
  -- "Covering while Ms Alvarez is on leave." Optional, and worth asking for:
  -- an access grant nobody can explain is one nobody dares remove.
  note                  TEXT
);

-- One row per person per school. Also the index every read uses: `person_id`
-- leads, so the per-request lookup is a seek on this index rather than a scan.
CREATE UNIQUE INDEX sponsor_school_grants_unique
  ON sponsor_school_grants(person_id, school_id);

-- The other direction: who, besides its own sponsor, can act for this chapter.
-- Asked by the chair looking at one chapter, and by the check before a chapter
-- is withdrawn.
CREATE INDEX sponsor_school_grants_by_school
  ON sponsor_school_grants(school_id);
