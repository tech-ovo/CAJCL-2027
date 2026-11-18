-- The activities potluck: activities that need helpers, and who offered.
--
-- potluck_activities is a dozen or two rows and is read whole. Everything
-- touching potluck_signups goes through an index: by person (the primary
-- key's leading column) or by activity (idx_potluck_signups_activity).

-- name: potluck.activities
-- Every activity with how many places are taken (pending + approved: what the
-- cap counts) and how many are approved.
SELECT a.id, a.name, a.description, a.location, a.starts_at, a.ends_at,
       a.capacity, a.open, a.sort_order,
       (SELECT COUNT(*) FROM potluck_signups s
         WHERE s.activity_id = a.id AND s.status IN ('pending','approved')) AS taken,
       (SELECT COUNT(*) FROM potluck_signups s
         WHERE s.activity_id = a.id AND s.status = 'approved') AS approved
FROM potluck_activities a
ORDER BY a.sort_order, a.name COLLATE NOCASE;

-- name: potluck.activity_get
SELECT * FROM potluck_activities WHERE id = ?;

-- name: potluck.activity_create
INSERT INTO potluck_activities (name, description, location, starts_at, ends_at,
                                capacity, open, sort_order, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- name: potluck.activity_update
UPDATE potluck_activities
SET name = ?, description = ?, location = ?, starts_at = ?, ends_at = ?,
    capacity = ?, open = ?, sort_order = ?, updated_at = ?
WHERE id = ?;

-- name: potluck.activity_delete
DELETE FROM potluck_activities WHERE id = ?;

-- name: potluck.taken
-- Places taken in one activity, not counting one person (who is re-saving).
SELECT COUNT(*) AS n FROM potluck_signups
WHERE activity_id = ? AND status IN ('pending','approved') AND person_id <> ?;

-- name: potluck.signups_for_person
SELECT person_id, activity_id, status, requested_at, decided_at,
       decided_by_person_id
FROM potluck_signups WHERE person_id = ?;

-- name: potluck.signup_get
SELECT person_id, activity_id, status, requested_at, decided_at,
       decided_by_person_id
FROM potluck_signups WHERE person_id = ? AND activity_id = ?;

-- name: potluck.signup_add
INSERT INTO potluck_signups (person_id, activity_id, status, requested_at,
                             decided_at, decided_by_person_id)
VALUES (?, ?, ?, ?, ?, ?);

-- name: potluck.signup_set
UPDATE potluck_signups
SET status = ?, requested_at = ?, decided_at = ?, decided_by_person_id = ?
WHERE person_id = ? AND activity_id = ?;

-- name: potluck.signup_delete
DELETE FROM potluck_signups WHERE person_id = ? AND activity_id = ?;

-- name: potluck.signups_delete_for_person
DELETE FROM potluck_signups WHERE person_id = ?;

-- name: potluck.requests_for_school
-- What a sponsor has to decide: pending picks by active, approved people of one
-- chapter, oldest first. Reads people through idx_people_school, then signups by primary key.
SELECT s.person_id, s.activity_id, s.requested_at,
       p.first_name, p.last_name, p.grade, p.school_seq,
       a.name AS activity_name, a.location, a.starts_at, a.ends_at,
       a.capacity
FROM potluck_signups s
JOIN people p ON p.id = s.person_id
JOIN potluck_activities a ON a.id = s.activity_id
WHERE p.school_id = ? AND p.status = 'active' AND p.approval = 'approved'
  AND p.person_type = 'delegate' AND s.status = 'pending'
ORDER BY s.requested_at, s.person_id;

-- name: potluck.volunteers_for_activity
-- The chair's list for one activity: approved picks by active, approved
-- people, with a name and a chapter and nothing else.
SELECT s.person_id, p.first_name, p.last_name, p.person_type,
       sc.id AS school_id, sc.name AS school_name
FROM potluck_signups s
JOIN people p ON p.id = s.person_id
JOIN schools sc ON sc.id = p.school_id
WHERE s.activity_id = ? AND s.status = 'approved'
  AND p.status = 'active' AND p.approval = 'approved'
ORDER BY sc.name COLLATE NOCASE, p.last_name COLLATE NOCASE, p.first_name COLLATE NOCASE;

-- name: potluck.signups_delete_for_activity
-- Deleting an activity removes the picks for it: idx_potluck_signups_activity.
DELETE FROM potluck_signups WHERE activity_id = ?;
