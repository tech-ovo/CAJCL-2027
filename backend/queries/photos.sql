-- The at-convention photo contest: categories, and the photos in them.
--
-- `photo_categories` is a handful of rows and is read whole. Everything
-- touching photos goes through an index: by person, or by category.

-- name: photos.categories
SELECT id, name, description, accepting, sort_order, drive_folder_id,
       drive_thumbs_id, created_at, updated_at
FROM photo_categories
ORDER BY sort_order, name COLLATE NOCASE;

-- name: photos.category_get
SELECT * FROM photo_categories WHERE id = ?;

-- name: photos.category_create
INSERT INTO photo_categories (name, description, accepting, sort_order,
                              created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?);

-- name: photos.category_update
UPDATE photo_categories
SET name = ?, description = ?, accepting = ?, sort_order = ?, updated_at = ?
WHERE id = ?;

-- name: photos.category_set_folders
UPDATE photo_categories SET drive_folder_id = ?, drive_thumbs_id = ? WHERE id = ?;

-- name: photos.category_delete
DELETE FROM photo_categories WHERE id = ?;

-- name: photos.entries_for_person
-- A delegate's own photos: idx_photo_entries_person.
SELECT id, category_id, caption, original_name, size_bytes, drive_file_id,
       drive_thumb_id, submitted_at, updated_at
FROM photo_entries
WHERE person_id = ?;

-- name: photos.entry_for_person
SELECT * FROM photo_entries WHERE person_id = ? AND category_id = ?;

-- name: photos.entry_get
SELECT * FROM photo_entries WHERE id = ?;

-- name: photos.entries_for_category
-- The chair's page, one category at a time: idx_photo_entries_category, then
-- a primary-key lookup each for the person and the chapter. Called once per
-- category so no call ever reads every photo at once.
SELECT e.id, e.category_id, e.caption, e.original_name, e.size_bytes,
       e.drive_file_id, e.drive_thumb_id,
       e.submitted_at, e.updated_at,
       e.person_id, p.first_name, p.last_name, p.school_seq,
       p.status AS person_status, p.approval,
       sc.id AS school_id, sc.name AS school_name, sc.number AS school_number
FROM photo_entries e
JOIN people p ON p.id = e.person_id
JOIN schools sc ON sc.id = e.school_id
WHERE e.category_id = ?
ORDER BY e.submitted_at DESC;

-- name: photos.entry_create
INSERT INTO photo_entries (category_id, person_id, school_id, caption,
                           drive_file_id, drive_thumb_id, original_name,
                           mime_type, size_bytes, submitted_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- name: photos.entry_replace
UPDATE photo_entries
SET caption = ?, drive_file_id = ?, drive_thumb_id = ?, original_name = ?,
    mime_type = ?, size_bytes = ?, updated_at = ?
WHERE id = ?;

-- name: photos.entry_delete
DELETE FROM photo_entries WHERE id = ?;

-- name: photos.entries_delete_for_category
DELETE FROM photo_entries WHERE category_id = ?;

-- name: photos.entries_delete_for_person
-- Redaction. A photo carries a face and a name in Drive; neither stays.
DELETE FROM photo_entries WHERE person_id = ?;
