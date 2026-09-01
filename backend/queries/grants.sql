-- A sponsor's access to chapters other than their own.
--
-- See backend/migrations/007_sponsor_grants.sql for why this is a table rather
-- than a second column on `people`. In short: a person still belongs to one
-- chapter, and this records the others they may act for.
--
-- NONE OF THESE GRANT A SCOPE. Scopes reach a person only through roles. Every
-- statement here answers "which chapters", never "what may they do".

-- name: grants.for_person
-- ON THE AUTHENTICATED PATH, so it is a seek and not a scan: person_id leads
-- the unique index. Asked only for people who already hold the sponsor role,
-- so a delegate signing in never runs it at all.
SELECT school_id FROM sponsor_school_grants WHERE person_id = ?;

-- name: grants.list_for_person
-- The chapters one sponsor may act for, named, for the chair reviewing them.
-- One indexed seek plus one join on the schools primary key.
SELECT g.id, g.school_id, g.granted_at, g.note,
       s.name AS school_name, s.level AS school_level, s.number AS school_number
FROM sponsor_school_grants g
JOIN schools s ON s.id = g.school_id
WHERE g.person_id = ?
ORDER BY s.name;

-- name: grants.list_for_school
-- Who, besides its own sponsor, may act for this chapter. Uses
-- sponsor_school_grants_by_school.
SELECT g.id, g.person_id, g.granted_at, g.note,
       p.first_name, p.last_name, p.school_id AS home_school_id,
       s.name AS home_school_name
FROM sponsor_school_grants g
JOIN people p ON p.id = g.person_id
JOIN schools s ON s.id = p.school_id
WHERE g.school_id = ?
ORDER BY p.last_name, p.first_name;

-- name: grants.get
SELECT id, person_id, school_id FROM sponsor_school_grants
WHERE person_id = ? AND school_id = ?;

-- name: grants.create
INSERT INTO sponsor_school_grants
  (person_id, school_id, granted_by_person_id, granted_at, note)
VALUES (?, ?, ?, ?, ?);

-- name: grants.delete
DELETE FROM sponsor_school_grants WHERE person_id = ? AND school_id = ?;

-- name: grants.sponsors_available
-- Adults holding the sponsor role, for the chair choosing somebody to give a
-- second chapter to. The role join is what keeps this list to people a grant
-- would actually mean something for -- a grant to anybody else is refused.
SELECT p.id, p.first_name, p.last_name, p.email,
       p.school_id, s.name AS school_name
FROM people p
JOIN schools s ON s.id = p.school_id
JOIN person_roles pr ON pr.person_id = p.id
JOIN roles r ON r.id = pr.role_id AND r.key = 'sponsor'
WHERE p.status = 'active' AND p.school_id <> ?
ORDER BY p.last_name, p.first_name;
