-- The number printed beside a name becomes 07014: chapter 07, their 14th person.
--
-- It used to be `people.id` padded to four digits, which is a database row id
-- and reads like one. Nobody could tell from #0042 which chapter that person
-- belonged to, and two chapters' sheets shuffled together could not be sorted
-- back apart without opening the site.
--
-- TWO NEW COLUMNS, BOTH ASSIGNED ONCE AND NEVER REUSED. A cancelled delegate
-- keeps their number; the next person added gets the one after it. Reusing a
-- number would make two different people share an identifier on two pieces of
-- paper printed a month apart, which is exactly the confusion this is meant to
-- remove.
--
-- THIS IS NOT A SECRET AND MUST NEVER BECOME ONE. It is printed beside the
-- access code and is deliberately guessable -- it is an index, like a seat
-- number. The access code stays nine random characters plus a check symbol,
-- and nothing about a person's identity is encoded in it.

-- 01..99. Two digits, so ninety-nine chapters; the convention runs about
-- fifty. A hundredth chapter is a real problem and should fail loudly rather
-- than silently wrap, which the UNIQUE constraint arranges.
ALTER TABLE schools ADD COLUMN number INTEGER;
CREATE UNIQUE INDEX idx_schools_number ON schools (number);

-- 001..999 within a chapter. The largest chapter here brings about sixty.
ALTER TABLE people ADD COLUMN school_seq INTEGER;
CREATE UNIQUE INDEX idx_people_school_seq ON people (school_id, school_seq);

-- Backfill in creation order, so existing sheets and the numbers on them keep
-- a sensible relationship to when people were added.
UPDATE schools SET number = (
  SELECT COUNT(*) FROM schools AS earlier
  WHERE earlier.id <= schools.id
) WHERE number IS NULL;

UPDATE people SET school_seq = (
  SELECT COUNT(*) FROM people AS earlier
  WHERE earlier.school_id = people.school_id AND earlier.id <= people.id
) WHERE school_seq IS NULL;
