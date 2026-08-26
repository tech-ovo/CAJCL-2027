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
