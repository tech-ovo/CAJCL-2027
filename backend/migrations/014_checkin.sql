-- Friday afternoon at the desk.
--
-- Chapters arrive after school, fifty of them, in about ninety minutes. What
-- the desk records is small and it has to be recordable one-handed on a phone
-- with bad wifi: this chapter arrived, at this time, and here is what they
-- brought.
--
-- ARRIVAL IS PER CHAPTER, NOT PER PERSON. A chapter arrives together, in a
-- bus. Ticking sixty individual boxes at a desk with a queue behind it is not
-- a thing anybody would do, and the per-person question that DOES matter --
-- did their waiver and medical arrive -- is already answered weeks earlier in
-- the roster, because the paper is mailed with the check.

ALTER TABLE school_stats ADD COLUMN arrived_at TEXT;

-- One note per chapter, written at the desk. Not per person: a note about one
-- delegate is a note about the chapter that brought them, and splitting it
-- would mean deciding whose row a catapult goes in.
ALTER TABLE schools ADD COLUMN checkin_note TEXT;

-- A delegate added at the desk to replace somebody who could not come.
--
-- They still need a waiver and a medical form -- those are safety documents
-- and nobody is exempt -- but their activity sheet is waived: the tests were
-- printed and the food was ordered weeks ago, so there is nothing for their
-- answers to change. Without this they would sit in every chapter's completion
-- figure as permanently unfinished, and a chair chasing that number would
-- chase somebody who cannot act.
--
-- Waived delegates are excluded from the academic counts entirely. They are
-- not entered in anything, so a proctor's sheet must not carry their name.
ALTER TABLE people ADD COLUMN activity_sheet_waived INTEGER NOT NULL DEFAULT 0;
