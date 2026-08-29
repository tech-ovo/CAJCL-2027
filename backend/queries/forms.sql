-- Online forms, paper-form attestation, and activity selections.

-- name: forms.get_submission
SELECT id, person_id, form_type, status, submitted_at, updated_at
FROM form_submissions WHERE person_id = ? AND form_type = ?;

-- name: forms.upsert_submission
INSERT INTO form_submissions (person_id, form_type, status, submitted_at, updated_at)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (person_id, form_type) DO UPDATE SET
  status = excluded.status,
  submitted_at = COALESCE(form_submissions.submitted_at, excluded.submitted_at),
  updated_at = excluded.updated_at;

-- name: forms.selections_for_person
SELECT s.id AS selection_id, s.item_id, i.name AS item_name,
       i.category_id, c.key AS category_key
FROM activity_selections s
JOIN catalog_items i ON i.id = s.item_id
JOIN catalog_categories c ON c.id = i.category_id
WHERE s.person_id = ?;

-- name: forms.selection_options_for_person
SELECT so.selection_id, so.option_id, o.name AS option_name, s.item_id
FROM activity_selection_options so
JOIN activity_selections s ON s.id = so.selection_id
JOIN catalog_item_options o ON o.id = so.option_id
WHERE s.person_id = ?;

-- name: forms.clear_selections
-- Editing an activity sheet replaces ALL selections in one transaction: delete
-- then insert. Do not diff -- diffing is where the bugs live and there are
-- never more than a few dozen rows.
-- activity_selection_options cascades from activity_selections.
DELETE FROM activity_selections WHERE person_id = ?;

-- name: forms.add_selection
INSERT INTO activity_selections (person_id, item_id, created_at) VALUES (?, ?, ?);

-- name: forms.add_selection_option
INSERT INTO activity_selection_options (selection_id, option_id) VALUES (?, ?);

-- name: forms.adult_roles_for_person
SELECT ars.item_id, i.name AS item_name
FROM adult_role_selections ars
JOIN catalog_items i ON i.id = ars.item_id
WHERE ars.person_id = ?;

-- name: forms.clear_adult_roles
DELETE FROM adult_role_selections WHERE person_id = ?;

-- name: forms.add_adult_role
INSERT INTO adult_role_selections (person_id, item_id, created_at) VALUES (?, ?, ?);

-- name: forms.mark_paper
-- The sponsor's attestation that a signed form was received. Records the
-- attestation ONLY -- no medical information, no file, no Drive pointer.
INSERT INTO paper_forms (person_id, form_type, received, marked_by_person_id, marked_at)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (person_id, form_type) DO UPDATE SET
  received = excluded.received,
  marked_by_person_id = excluded.marked_by_person_id,
  marked_at = excluded.marked_at;

-- name: forms.chapter_entries_for_school
SELECT ce.id, ce.item_id, ce.team_label, ce.notes, ce.created_at,
       i.name AS item_name
FROM chapter_entries ce
JOIN catalog_items i ON i.id = ce.item_id
WHERE ce.school_id = ?
ORDER BY i.sort_order, ce.team_label;

-- name: forms.chapter_entry_create
INSERT INTO chapter_entries (school_id, item_id, team_label, notes, created_by_person_id, created_at)
VALUES (?, ?, ?, ?, ?, ?);

-- name: forms.chapter_entry_delete
DELETE FROM chapter_entries WHERE id = ? AND school_id = ?;

-- name: forms.chapter_entry_get
SELECT id, school_id, item_id, team_label FROM chapter_entries WHERE id = ?;

-- name: forms.paper_for_person
-- Which of a person's paper forms have reached their sponsor. Shown on their
-- own sheet, because "am I registered?" is not answered by the online half
-- alone and a delegate has no other way to find out.
-- Indexed by the primary key on (person_id, form_type).
SELECT form_type, received FROM paper_forms WHERE person_id = ?;

-- name: forms.own_completeness
-- Is THIS person's registration finished? One row, by primary key.
--
-- Feeds the marker on their own Registration tab. Deliberately the same
-- definition the chapter counters use (see stats.count_school), so a delegate
-- and their sponsor never disagree about whether they are done.
SELECT
  CASE WHEN p.person_type = 'delegate'
       THEN (fs.status = 'submitted' OR p.activity_sheet_waived = 1)
       ELSE (fs.status = 'submitted' OR p.adult_type = 'scl') END AS form_done,
  COALESCE(pf_w.received, 0) AS waiver_received,
  COALESCE(pf_m.received, 0) AS medical_received,
  COALESCE(pf_a.received, 0) AS adult_medical_received,
  p.person_type
FROM people p
LEFT JOIN form_submissions fs
       ON fs.person_id = p.id
      AND fs.form_type = CASE WHEN p.person_type = 'delegate'
                              THEN 'student_activity' ELSE 'adult_registration' END
LEFT JOIN paper_forms pf_w ON pf_w.person_id = p.id AND pf_w.form_type = 'student_waiver'
LEFT JOIN paper_forms pf_m ON pf_m.person_id = p.id AND pf_m.form_type = 'student_medical'
LEFT JOIN paper_forms pf_a ON pf_a.person_id = p.id AND pf_a.form_type = 'adult_medical'
WHERE p.id = ?;
