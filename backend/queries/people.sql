-- People, the roster, and codes.

-- name: people.get
SELECT p.*, s.name AS school_name, s.level AS school_level, s.kind AS school_kind
FROM people p JOIN schools s ON s.id = p.school_id
WHERE p.id = ?;

-- name: people.create
INSERT INTO people (
  school_id, person_type, adult_type, adult_type_other,
  first_name, middle_name, last_name, suffix, raw_name_input,
  grade, latin_level, meal, cell_phone,
  email, latin_knowledge, availability_note,
  guardian_name, guardian_phone,
  code_hmac, code_prefix, pepper_version, code_issued_at,
  created_at, updated_at, roster_import_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- name: people.update_details
-- The sponsor's inline roster edit. Delegates cannot change their own name --
-- they ask their sponsor -- which is enforced at the endpoint, not here.
UPDATE people
SET first_name = ?, middle_name = ?, last_name = ?, suffix = ?,
    grade = ?, latin_level = ?, meal = ?, cell_phone = ?,
    guardian_name = ?, guardian_phone = ?, updated_at = ?
WHERE id = ?;

-- name: people.update_adult_details
UPDATE people
SET first_name = ?, middle_name = ?, last_name = ?, suffix = ?,
    adult_type = ?, adult_type_other = ?, meal = ?, cell_phone = ?,
    email = ?, latin_knowledge = ?, availability_note = ?, updated_at = ?
WHERE id = ?;

-- name: people.update_self_delegate
-- What a delegate may change about themselves on their own activity sheet.
-- Their NAME is deliberately absent from this list.
UPDATE people
SET grade = ?, latin_level = ?, meal = ?, updated_at = ?
WHERE id = ?;

-- name: people.update_self_adult
UPDATE people
SET meal = ?, cell_phone = ?, email = ?, latin_knowledge = ?,
    availability_note = ?, adult_type = ?, adult_type_other = ?, updated_at = ?
WHERE id = ?;

-- name: people.cancel
-- Soft delete. Nothing in `people` is ever hard-deleted: an attendee who can no
-- longer come is marked cancelled and can be restored.
--
-- The status is chosen by the CALLER, not fixed here, because which of the two
-- cancelled states applies depends on whether the chapter has already paid --
-- and there are no refunds. See backend/lib/roster.py.
UPDATE people SET status = ?, cancelled_at = ?, updated_at = ? WHERE id = ?;

-- name: people.restore
UPDATE people SET status = 'active', cancelled_at = NULL, updated_at = ? WHERE id = ?;

-- name: people.set_code
-- Regeneration. The caller MUST revoke this person's sessions in the same
-- transaction, or the old QR keeps working.
UPDATE people
SET code_hmac = ?, code_prefix = ?, pepper_version = ?, code_issued_at = ?, updated_at = ?
WHERE id = ?;

-- name: people.set_forms_unlocked
UPDATE people SET forms_unlocked = ?, updated_at = ? WHERE id = ?;

-- There is deliberately NO query for moving a person between schools.
-- Chapters are completely separate: a middle school and a high school from the
-- same site register as two schools with two sponsors. In the rare case a
-- sponsor enters someone under the wrong chapter, the fix is to cancel that row
-- and enter them again under the right one. A move would have to revalidate the
-- Latin level, every test eligibility, and both schools' invoices -- machinery
-- for an operation that should not happen.

-- name: people.school_of
-- The school-scoping check. Every sponsor endpoint compares this to the
-- caller's own school before touching anything.
SELECT school_id, person_type, status FROM people WHERE id = ?;

-- name: people.existing_names_for_dedupe
-- Feeds the parser's duplicate-in-roster check. Fetched ONCE and passed in, so
-- duplicate detection never issues a query per pasted line.
SELECT id, first_name, last_name, guardian_name, guardian_phone
FROM people
WHERE school_id = ? AND status = 'active';

-- name: people.grant_role
INSERT INTO person_roles (person_id, role_id, granted_by, granted_at)
VALUES (?, ?, ?, ?)
ON CONFLICT (person_id, role_id) DO NOTHING;

-- name: people.revoke_role
DELETE FROM person_roles WHERE person_id = ? AND role_id = ?;
