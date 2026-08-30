-- Schools and chapters.
--
-- `kind` separates chapters (who send delegates and get invoiced) from
-- organizations (the state board). `billing_exempt` is the separate idea that a
-- real chapter owes nothing. Never key either off a school's name.

-- name: schools.get
SELECT id, name, level, kind, city, drive_folder_id, billing_exempt,
       discount_cents, discount_reason, status, notes, number,
       created_at, updated_at
FROM schools WHERE id = ?;

-- name: schools.all_ids
SELECT id FROM schools;

-- name: schools.list
-- Chapters only, for the admin school list. Uses idx_schools_kind_status_level.
--
-- drive_folder_id IS selected here, and stripped by _school_public() in api.py
-- for anyone without scope '*'. Redacting in one serializer beats redacting in
-- every query: the previous version simply omitted the column, and the admin
-- branch then raised KeyError trying to read it back.
SELECT id, name, level, city, billing_exempt, discount_cents, discount_reason,
       drive_folder_id, status, notes
FROM schools
WHERE kind = 'chapter'
ORDER BY name;

-- name: schools.create
-- `number` is the two-digit half of every printed person number, assigned here
-- rather than in Python so that the single writer settles it: two chapters
-- created in the same second cannot take the same one, and the UNIQUE index
-- would refuse them anyway.
--
-- MAX + 1, never COUNT. A chapter that is deleted must not hand its number to
-- the next one created -- two chapters would then share an identifier on two
-- stacks of paper printed a month apart.
INSERT INTO schools (name, level, kind, city, billing_exempt,
                     discount_cents, discount_reason, notes, created_at, updated_at,
                     number)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
        (SELECT COALESCE(MAX(number), 0) + 1 FROM schools));

-- name: schools.update
UPDATE schools
SET name = ?, level = ?, city = ?, billing_exempt = ?,
    discount_cents = ?, discount_reason = ?, status = ?,
    notes = ?, drive_folder_id = ?, updated_at = ?
WHERE id = ?;

-- name: schools.stats_init
-- Every school gets a school_stats row at creation, so no page has to cope with
-- a missing counter row and no LEFT JOIN has to guess at zero.
INSERT INTO school_stats (school_id, updated_at) VALUES (?, ?)
ON CONFLICT (school_id) DO NOTHING;

-- name: schools.all_including_organizations
-- Every school row, chapters AND organizations. `schools.list` deliberately
-- excludes organizations so the state board never appears as a delegation on
-- the chair dashboard; this is for the places that need to look a school up by
-- name regardless of kind -- board provisioning, mainly.
--
-- Fifty rows at most, and it is not on any request path.
SELECT id, name, level, kind, city, billing_exempt, discount_cents,
       discount_reason, drive_folder_id, status, notes
FROM schools
ORDER BY name;

-- name: schools.set_checkin_note
-- What a chapter brought, written at the desk. One note per chapter.
UPDATE schools SET checkin_note = ?, updated_at = ? WHERE id = ?;
