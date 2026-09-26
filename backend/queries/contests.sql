-- Pre-convention contests: entries, and judges' ranked ballots.
--
-- `contests` is a handful of rows and is read whole. Everything touching
-- entries or ballots goes through an index: by person, by chapter, by
-- contest, or by ballot.

-- name: contests.all
-- Six rows, joined to the catalog for the name and to skip anything a chair
-- has switched off there.
SELECT c.item_id, c.key, i.name, c.entry_kind, c.entered_by, c.divisions,
       c.accepted_types, c.needs_title, c.min_words, c.max_words,
       c.words_penalty, c.max_chars, c.needs_translation, c.must_attend,
       c.facets, c.rules_md, c.places, c.sort_order
FROM contests c
JOIN catalog_items i ON i.id = c.item_id
WHERE i.active = 1
ORDER BY c.sort_order, i.name;

-- name: contests.update_rules
UPDATE contests SET rules_md = ? WHERE item_id = ?;

-- name: contests.update_places
UPDATE contests SET places = ? WHERE item_id = ?;

-- name: contests.entries_for_person
-- A delegate's own entries: idx_contest_entries_person.
SELECT id, item_id, division, title, body_text, translation, word_count,
       word_count_source, original_name, mime_type, size_bytes, submitted_at,
       updated_at, drive_file_id
FROM contest_entries
WHERE person_id = ?;

-- name: contests.entry_for_person
SELECT * FROM contest_entries WHERE person_id = ? AND item_id = ?;

-- name: contests.entry_for_chapter
-- `person_id IS NULL` is what lets the planner use the partial unique index
-- idx_contest_entries_chapter.
SELECT * FROM contest_entries
WHERE school_id = ? AND item_id = ? AND person_id IS NULL;

-- name: contests.entry_get
SELECT * FROM contest_entries WHERE id = ?;

-- name: contests.entries_for_school
-- A sponsor's view of their chapter: every entry, with who made it.
-- idx_contest_entries_school, then one primary-key lookup per entry.
SELECT e.id, e.item_id, e.person_id, e.division, e.title, e.body_text,
       e.translation, e.link_url, e.facets, e.original_name, e.submitted_at,
       e.updated_at, e.word_count, e.size_bytes,
       e.drive_file_id IS NOT NULL AS has_file,
       p.first_name, p.last_name, p.school_seq, p.status
FROM contest_entries e
LEFT JOIN people p ON p.id = e.person_id
WHERE e.school_id = ?
ORDER BY e.item_id, p.last_name, p.first_name;

-- name: contests.entry_create
INSERT INTO contest_entries (
  item_id, school_id, person_id, division, title, body_text, translation,
  link_url, facets, word_count, word_count_source, drive_file_id,
  drive_folder_id, original_name, mime_type, size_bytes, submitted_by,
  submitted_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- name: contests.entry_replace
-- Replacing keeps the entry's id, and so its number with the judges. It is
-- taken off judges' ballots separately: they ranked the work being replaced.
UPDATE contest_entries
SET division = ?, title = ?, body_text = ?, translation = ?, link_url = ?,
    facets = ?, word_count = ?, word_count_source = ?, drive_file_id = ?,
    drive_folder_id = ?, original_name = ?, mime_type = ?, size_bytes = ?,
    submitted_by = ?, updated_at = ?
WHERE id = ?;

-- name: contests.entry_delete
DELETE FROM contest_entries WHERE id = ?;

-- name: contests.ballots_reopen_for_entry
-- Every ballot this entry is on goes back to draft, before the entry is
-- taken off them: the judge's list now has a gap to fill.
-- idx_contest_ballot_places_entry, then primary-key updates.
UPDATE contest_ballots SET status = 'draft', updated_at = ?
WHERE id IN (SELECT ballot_id FROM contest_ballot_places WHERE entry_id = ?);

-- name: contests.ballot_places_delete_for_entry
DELETE FROM contest_ballot_places WHERE entry_id = ?;

-- name: contests.entries_for_judging
-- WHAT A JUDGE SEES, AND NOTHING MORE: no person, no chapter, no file name.
-- Chapter entries (Publicity) are not anonymous -- a portfolio names its
-- school on every page -- but the chapter still is not sent from here.
-- idx_contest_entries_item.
SELECT e.id, e.division, e.title, e.body_text, e.translation, e.link_url,
       e.facets, e.word_count, e.word_count_source, e.mime_type,
       e.size_bytes, e.drive_file_id IS NOT NULL AS has_file
FROM contest_entries e
WHERE e.item_id = ?
ORDER BY e.division, e.id;

-- name: contests.entry_groups
-- Which divisions (and Publicity categories) a contest has entries in, for
-- counting the ballots a judge owes. idx_contest_entries_item.
SELECT division, facets FROM contest_entries WHERE item_id = ?;

-- name: contests.ballots_for_judge
-- One judge's ballots in one contest, with their places in order. The
-- (item_id, judge_person_id, division, facet) unique index, then each
-- ballot's places by primary key.
SELECT b.id, b.division, b.facet, b.comment, b.status, b.updated_at,
       p.place, p.entry_id
FROM contest_ballots b
LEFT JOIN contest_ballot_places p ON p.ballot_id = b.id
WHERE b.item_id = ? AND b.judge_person_id = ?
ORDER BY b.id, p.place;

-- name: contests.judge_progress
-- The judge's front page: how many ballots this judge has handed in, per
-- contest. Driven from the six contests, one indexed count per contest.
SELECT c.item_id,
       (SELECT COUNT(*) FROM contest_entries e
         WHERE e.item_id = c.item_id)                         AS entries,
       (SELECT COUNT(*) FROM contest_ballots b
         WHERE b.item_id = c.item_id AND b.judge_person_id = ?
           AND b.status = 'submitted')                        AS handed_in
FROM contests c;

-- name: contests.ballot_upsert
-- One ballot per judge, contest, division and category, so saving twice
-- updates rather than adding a second list that would count double.
INSERT INTO contest_ballots (item_id, division, facet, judge_person_id,
                             comment, status, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (item_id, judge_person_id, division, facet) DO UPDATE SET
  comment    = excluded.comment,
  status     = excluded.status,
  updated_at = excluded.updated_at;

-- name: contests.ballot_get
SELECT id FROM contest_ballots
WHERE item_id = ? AND judge_person_id = ? AND division = ? AND facet = ?;

-- name: contests.ballot_places_delete
DELETE FROM contest_ballot_places WHERE ballot_id = ?;

-- name: contests.ballot_place_create
INSERT INTO contest_ballot_places (ballot_id, place, entry_id) VALUES (?, ?, ?);

-- name: contests.results_overview
-- The chairs' front page. Driven from the six contests, one indexed count
-- per contest: entries through idx_contest_entries_item, ballots through
-- idx_contest_ballots_item.
SELECT c.item_id,
       (SELECT COUNT(*) FROM contest_entries e
         WHERE e.item_id = c.item_id)                         AS entries,
       (SELECT COUNT(*) FROM contest_ballots b
         WHERE b.item_id = c.item_id AND b.status = 'submitted') AS ballots,
       (SELECT COUNT(DISTINCT b.judge_person_id) FROM contest_ballots b
         WHERE b.item_id = c.item_id AND b.status = 'submitted') AS judges
FROM contests c;

-- name: contests.results_entries
-- The chairs' view of one contest: every entry WITH its person and chapter.
-- idx_contest_entries_item, then primary-key lookups.
SELECT e.id, e.division, e.title, e.body_text, e.translation, e.link_url,
       e.facets, e.word_count, e.word_count_source, e.submitted_at,
       e.drive_file_id IS NOT NULL AS has_file,
       e.person_id, p.first_name, p.last_name, p.status AS person_status,
       p.grade, sc.id AS school_id, sc.name AS school_name, sc.number AS school_number,
       p.school_seq
FROM contest_entries e
JOIN schools sc ON sc.id = e.school_id
LEFT JOIN people p ON p.id = e.person_id
WHERE e.item_id = ?
ORDER BY e.division, e.id;

-- name: contests.submissions_for_item
-- The registration chairs' list of every submission: who, which chapter, and
-- what they sent. No scores. Called once per contest, so each call is
-- idx_contest_entries_item and then primary-key lookups -- never a scan of
-- every entry.
SELECT e.id, e.item_id, e.division, e.title, e.body_text, e.translation,
       e.link_url, e.facets, e.word_count, e.word_count_source,
       e.original_name, e.size_bytes, e.submitted_at, e.updated_at,
       e.drive_file_id IS NOT NULL AS has_file,
       e.person_id, p.first_name, p.last_name, p.status AS person_status,
       p.school_seq, sc.id AS school_id, sc.name AS school_name,
       sc.number AS school_number
FROM contest_entries e
JOIN schools sc ON sc.id = e.school_id
LEFT JOIN people p ON p.id = e.person_id
WHERE e.item_id = ?
ORDER BY sc.number, sc.name, p.last_name, p.first_name;

-- name: contests.results_ballots
-- Every handed-in ballot in one contest, with its places and the judge's
-- name so a chair can chase a missing one. idx_contest_ballots_item, then
-- each ballot's places by primary key.
SELECT b.id, b.division, b.facet, b.comment, b.judge_person_id,
       j.first_name AS judge_first, j.last_name AS judge_last,
       p.place, p.entry_id
FROM contest_ballots b
JOIN people j ON j.id = b.judge_person_id
LEFT JOIN contest_ballot_places p ON p.ballot_id = b.id
WHERE b.item_id = ? AND b.status = 'submitted'
ORDER BY b.id, p.place;

-- name: contests.redact_for_person
-- Blank out personal text and file links on a redacted person's contest entries.
-- CASE WHEN is used to redact translation only when present.
-- Uses idx_contest_entries_person.
UPDATE contest_entries
SET title = 'REDACTED',
    body_text = 'REDACTED',
    translation = CASE WHEN translation IS NOT NULL THEN 'REDACTED' ELSE NULL END,
    original_name = 'REDACTED',
    link_url = NULL,
    drive_file_id = NULL,
    drive_folder_id = NULL,
    updated_at = ?
WHERE person_id = ?;

