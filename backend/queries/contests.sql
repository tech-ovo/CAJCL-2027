-- Pre-convention contests: entries, rubrics, and judges' scores.
--
-- `contests` and `contest_criteria` are a handful of rows each and are read
-- whole. Everything touching entries or scores goes through an index: by
-- person, by chapter, or by contest.

-- name: contests.all
-- Six rows, joined to the catalog for the name and to skip anything a chair
-- has switched off there.
SELECT c.item_id, c.key, i.name, c.entry_kind, c.entered_by, c.divisions,
       c.accepted_types, c.needs_title, c.min_words, c.max_words,
       c.words_penalty, c.max_chars, c.needs_translation, c.must_attend,
       c.facets, c.rules_md, c.sort_order
FROM contests c
JOIN catalog_items i ON i.id = c.item_id
WHERE i.active = 1
ORDER BY c.sort_order, i.name;

-- name: contests.criteria_all
SELECT id, item_id, label, max_points, sort_order
FROM contest_criteria
ORDER BY item_id, sort_order, id;

-- name: contests.update_rules
UPDATE contests SET rules_md = ? WHERE item_id = ?;

-- name: contests.criteria_delete
DELETE FROM contest_criteria WHERE item_id = ?;

-- name: contests.criteria_create
INSERT INTO contest_criteria (item_id, label, max_points, sort_order)
VALUES (?, ?, ?, ?);

-- name: contests.criteria_update
UPDATE contest_criteria SET label = ? WHERE id = ? AND item_id = ?;

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
       e.updated_at, p.first_name, p.last_name, p.school_seq, p.status
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
-- Replacing keeps the entry's id, and so its number with the judges. Its
-- scores are deleted separately: they were for the work being replaced.
UPDATE contest_entries
SET division = ?, title = ?, body_text = ?, translation = ?, link_url = ?,
    facets = ?, word_count = ?, word_count_source = ?, drive_file_id = ?,
    drive_folder_id = ?, original_name = ?, mime_type = ?, size_bytes = ?,
    submitted_by = ?, updated_at = ?
WHERE id = ?;

-- name: contests.entry_delete
DELETE FROM contest_entries WHERE id = ?;

-- name: contests.scores_delete_for_entry
DELETE FROM contest_scores WHERE entry_id = ?;

-- name: contests.entries_for_judging
-- WHAT A JUDGE SEES, AND NOTHING MORE: no person, no chapter, no file name.
-- Chapter entries (Publicity) are not anonymous -- a portfolio names its
-- school on every page -- but the chapter still is not sent from here.
--
-- idx_contest_entries_item, then this judge's own scores through the
-- (entry_id, judge_person_id, facet) unique index.
SELECT e.id, e.division, e.title, e.body_text, e.translation, e.link_url,
       e.facets, e.word_count, e.word_count_source, e.mime_type,
       e.size_bytes, e.drive_file_id IS NOT NULL AS has_file,
       s.facet AS score_facet, s.points_json, s.penalty, s.total,
       s.comment, s.status AS score_status
FROM contest_entries e
LEFT JOIN contest_scores s
       ON s.entry_id = e.id AND s.judge_person_id = ?
WHERE e.item_id = ?
ORDER BY e.division, e.id;

-- name: contests.judge_progress
-- The judge's front page: how many entries each contest has, and how many
-- this judge has handed in. Driven from the six contests, one indexed count
-- per contest -- never a scan of every entry.
SELECT c.item_id,
       (SELECT COUNT(*) FROM contest_entries e
         WHERE e.item_id = c.item_id)                         AS entries,
       (SELECT COUNT(DISTINCT s.entry_id)
          FROM contest_scores s
          JOIN contest_entries e ON e.id = s.entry_id
         WHERE s.judge_person_id = ? AND s.status = 'submitted'
           AND e.item_id = c.item_id)                         AS scored
FROM contests c;

-- name: contests.score_upsert
-- One row per judge, entry and facet, so saving twice updates rather than
-- adding a second score that would count double in the average.
INSERT INTO contest_scores (entry_id, judge_person_id, facet, points_json,
                            penalty, total, comment, status, created_at,
                            updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (entry_id, judge_person_id, facet) DO UPDATE SET
  points_json = excluded.points_json,
  penalty     = excluded.penalty,
  total       = excluded.total,
  comment     = excluded.comment,
  status      = excluded.status,
  updated_at  = excluded.updated_at;

-- name: contests.scored_count
-- Whether a rubric can still change. Driven from this contest's entries, then
-- the unique index on contest_scores for each.
SELECT COUNT(*) AS n
FROM contest_entries e
JOIN contest_scores s ON s.entry_id = e.id
WHERE e.item_id = ?;

-- name: contests.results_overview
-- The chairs' front page. Driven from the six contests, one indexed count
-- per contest: entries through idx_contest_entries_item, then each entry's
-- handed-in scores through the unique index on contest_scores.
SELECT c.item_id,
       (SELECT COUNT(*) FROM contest_entries e
         WHERE e.item_id = c.item_id)                         AS entries,
       (SELECT COUNT(DISTINCT s.entry_id)
          FROM contest_entries e
          JOIN contest_scores s ON s.entry_id = e.id
         WHERE e.item_id = c.item_id AND s.status = 'submitted') AS judged,
       (SELECT COUNT(*)
          FROM contest_entries e
          JOIN contest_scores s ON s.entry_id = e.id
         WHERE e.item_id = c.item_id AND s.status = 'submitted') AS scores
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

-- name: contests.results_scores
-- Every submitted score in one contest, with the judge's name so a chair can
-- chase a missing one. Entries by idx_contest_entries_item, then each entry's
-- scores through the unique index.
SELECT s.entry_id, s.facet, s.total, s.penalty, s.comment, s.status,
       s.judge_person_id, j.first_name AS judge_first, j.last_name AS judge_last
FROM contest_entries e
JOIN contest_scores s ON s.entry_id = e.id
JOIN people j ON j.id = s.judge_person_id
WHERE e.item_id = ? AND s.status = 'submitted';
