-- 011_join_codes.sql -- a chapter join code, and a pending/approved state for
-- the delegates who arrive by it.
--
-- WHY
--   A sponsor does not know which of their Latin students are coming until the
--   paper packets are in hand. Pasting a roster first made them collect names
--   twice. Instead each chapter has a JOIN CODE: a student types it, gives
--   their name, and receives an ordinary access code. They are "pending" until
--   their sponsor approves them, but a pending student is not blocked -- they
--   fill in their activity sheet straight away.
--
-- THE JOIN CODE IS NOT A SECRET IN THE WAY AN ACCESS CODE IS. It is printed on
-- every packet and shown on the sponsor's screen, so it is stored as-is (a
-- hash would have to be reversible for the sponsor to read it). What stops it
-- being abused is that it can create nothing but a PENDING delegate in that one
-- chapter, that a sponsor can close or replace it at any time, and that a
-- chapter can only hold so many pending students at once.

ALTER TABLE schools ADD COLUMN join_code TEXT;
ALTER TABLE schools ADD COLUMN join_open INTEGER NOT NULL DEFAULT 1
  CHECK (join_open IN (0, 1));

-- Every existing chapter gets one now, from the same 31-character alphabet
-- codes.py uses (Crockford Base32 minus Z). Eight characters, so about 39 bits.
-- Organizations never take joiners.
UPDATE schools SET join_code =
     substr('0123456789ABCDEFGHJKMNPQRSTVWXY', 1 + abs(random()) % 31, 1)
  || substr('0123456789ABCDEFGHJKMNPQRSTVWXY', 1 + abs(random()) % 31, 1)
  || substr('0123456789ABCDEFGHJKMNPQRSTVWXY', 1 + abs(random()) % 31, 1)
  || substr('0123456789ABCDEFGHJKMNPQRSTVWXY', 1 + abs(random()) % 31, 1)
  || substr('0123456789ABCDEFGHJKMNPQRSTVWXY', 1 + abs(random()) % 31, 1)
  || substr('0123456789ABCDEFGHJKMNPQRSTVWXY', 1 + abs(random()) % 31, 1)
  || substr('0123456789ABCDEFGHJKMNPQRSTVWXY', 1 + abs(random()) % 31, 1)
  || substr('0123456789ABCDEFGHJKMNPQRSTVWXY', 1 + abs(random()) % 31, 1)
WHERE kind = 'chapter';

-- The join lookup is a single indexed equality on this column.
CREATE UNIQUE INDEX idx_schools_join_code ON schools (join_code)
  WHERE join_code IS NOT NULL;

-- 'approved'  an ordinary registered person. Everything created before this
--             migration, every pasted roster, every adult.
-- 'pending'   joined with the chapter's join code and not yet approved by a
--             sponsor. Can sign in and fill in forms; counted nowhere that
--             costs money or feeds the caterer. Shown as PRELIMINARY.
-- 'denied'    a pending student the sponsor turned down. The row is the
--             anonymous tombstone left by roster.redact and nothing else.
ALTER TABLE people ADD COLUMN approval TEXT NOT NULL DEFAULT 'approved'
  CHECK (approval IN ('approved', 'pending', 'denied'));

-- Partial: nearly every row is 'approved', and only the exceptions are ever
-- looked up this way (the sponsor's pending list, the per-chapter cap).
CREATE INDEX idx_people_approval ON people (school_id, approval)
  WHERE approval <> 'approved';

-- Counted in the same transaction as every other figure on this table.
ALTER TABLE school_stats ADD COLUMN delegates_pending INTEGER NOT NULL DEFAULT 0;

-- The sheet a sponsor prints for the join code. Prose, so it can be reworded
-- without a deploy.
INSERT INTO documents (key, title, body_md, updated_at) VALUES
  ('join_instructions', 'How to join your chapter',
   '1. Go to **state.uhsjcl.org** and choose **Join your chapter**, or scan the square code.

2. Type the **join code** above, then your name, grade and Latin level.

3. The site shows you an **access code** once. Write it down or take a screenshot: it is the only way back in, and your sponsor can issue a new one if you lose it.

4. Finish your Student Activity Sheet. You do not have to wait for your sponsor to approve you; until they do, your registration is marked **preliminary** and does not count toward your chapter''s total.

5. Print, sign and return the paper forms in this packet to your sponsor: the student waiver and the student medical form. Both need a parent or guardian''s signature.',
   strftime('%Y-%m-%dT%H:%M:%SZ','now'));
