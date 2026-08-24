-- Settings, catalog, documents, announcements, payments, roles.

-- name: settings.all
-- The whole settings table is ~22 rows and is read on nearly every request, so
-- it is cached per container and refreshed on mutation. See lib/settings.py.
SELECT key, value, value_type, label, group_name, sort_order, updated_at
FROM settings ORDER BY group_name, sort_order;

-- name: settings.update
UPDATE settings SET value = ?, updated_at = ?, updated_by = ? WHERE key = ?;

-- name: settings.get
SELECT key, value, value_type FROM settings WHERE key = ?;

-- name: documents.all
SELECT key, title, body_md, updated_at FROM documents ORDER BY key;

-- name: documents.get
SELECT key, title, body_md, updated_at FROM documents WHERE key = ?;

-- name: documents.update
UPDATE documents SET title = ?, body_md = ?, updated_at = ?, updated_by = ? WHERE key = ?;

-- name: catalog.categories
SELECT id, key, name, description, applies_to, min_selections, max_selections,
       enforcement, sort_order, active
FROM catalog_categories ORDER BY applies_to, sort_order;

-- name: catalog.items
-- The whole catalog is ~150 rows and is loaded ONCE per container into memory,
-- refreshed on mutation. It is never queried per request.
SELECT i.id, i.category_id, i.name, i.description, i.eligible_latin_levels,
       i.eligible_school_levels, i.registration_scope, i.max_sub_selections,
       i.min_latin_knowledge, i.sort_order, i.active,
       c.key AS category_key
FROM catalog_items i
JOIN catalog_categories c ON c.id = i.category_id
ORDER BY c.sort_order, i.sort_order;

-- name: catalog.options
SELECT id, item_id, name, sort_order, active
FROM catalog_item_options ORDER BY item_id, sort_order;

-- name: catalog.category_update
UPDATE catalog_categories
SET name = ?, description = ?, min_selections = ?, max_selections = ?,
    enforcement = ?, sort_order = ?, active = ?
WHERE id = ?;

-- name: catalog.item_update
UPDATE catalog_items
SET name = ?, description = ?, eligible_latin_levels = ?,
    eligible_school_levels = ?, registration_scope = ?, max_sub_selections = ?,
    min_latin_knowledge = ?, sort_order = ?, active = ?
WHERE id = ?;

-- name: catalog.item_create
INSERT INTO catalog_items (
  category_id, name, description, eligible_latin_levels, eligible_school_levels,
  registration_scope, max_sub_selections, min_latin_knowledge, sort_order, active
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- name: catalog.option_create
INSERT INTO catalog_item_options (item_id, name, sort_order, active) VALUES (?, ?, ?, ?);

-- name: catalog.option_update
UPDATE catalog_item_options SET name = ?, sort_order = ?, active = ? WHERE id = ?;

-- name: announcements.active
-- The banner. Uses idx_announcements_active.
SELECT id, body_md, level, starts_at, ends_at
FROM announcements
WHERE active = 1
  AND (starts_at IS NULL OR starts_at <= ?)
  AND (ends_at   IS NULL OR ends_at   >= ?)
ORDER BY id DESC;

-- name: announcements.all
SELECT id, body_md, level, active, starts_at, ends_at, created_at
FROM announcements ORDER BY id DESC LIMIT 50;

-- name: announcements.create
INSERT INTO announcements (body_md, level, active, starts_at, ends_at, created_by, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?);

-- name: announcements.set_active
UPDATE announcements SET active = ? WHERE id = ?;

-- name: payments.create
-- Append-only. A correction is a NEW row, possibly negative, never an edit.
INSERT INTO payments (school_id, amount_cents, method, reference, received_on, note, recorded_by_person_id, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?);

-- name: payments.for_school
-- Indexed by idx_payments_school. The history a sponsor sees, and the whole
-- answer when someone disputes a balance in March.
SELECT p.id, p.amount_cents, p.method, p.reference, p.received_on, p.note,
       p.created_at, r.first_name AS recorded_by_first, r.last_name AS recorded_by_last
FROM payments p
LEFT JOIN people r ON r.id = p.recorded_by_person_id
WHERE p.school_id = ?
ORDER BY p.created_at DESC;

-- name: roles.all
SELECT r.id, r.key, r.name, r.description, r.is_system,
       group_concat(rs.scope) AS scopes
FROM roles r
LEFT JOIN role_scopes rs ON rs.role_id = r.id
GROUP BY r.id
ORDER BY r.is_system DESC, r.key;

-- name: roles.by_key
SELECT id, key, name, is_system FROM roles WHERE key = ?;

-- name: roles.create
INSERT INTO roles (key, name, description, is_system, created_at) VALUES (?, ?, ?, 0, ?);

-- name: roles.add_scope
INSERT INTO role_scopes (role_id, scope) VALUES (?, ?)
ON CONFLICT (role_id, scope) DO NOTHING;

-- name: people.roles_of
SELECT r.id, r.key, r.name FROM person_roles pr
JOIN roles r ON r.id = pr.role_id
WHERE pr.person_id = ?;

-- name: admin.people_search
-- Impersonation target picker and the admin person lookup. Bounded by LIMIT and
-- only ever called with an explicit school filter or a name prefix, so it never
-- walks the whole table.
SELECT p.id, p.first_name, p.middle_name, p.last_name,
       p.person_type, p.adult_type, p.adult_type_other, p.status,
       p.school_id, s.name AS school_name
FROM people p JOIN schools s ON s.id = p.school_id
WHERE p.school_id = ?
ORDER BY p.last_name, p.first_name
LIMIT 200;

-- name: admin.board_members
-- Everyone holding a role that is not simply "I am a delegate" or "I am a
-- chapter leader" -- in other words, the convention's board and chairs.
--
-- DRIVEN FROM roles, NOT FROM people. There are seven roles and five of them
-- are board roles, so the plan starts with five index seeks on
-- idx_person_roles_role (added in 009) and reaches people by primary key.
-- Starting from people would scan one row per delegate at the convention to
-- find about twenty adults, and Turso bills a scan by rows scanned.
--
-- The role list is a correlated subquery rather than a second GROUP BY, so a
-- person who holds both `sponsor` and `admin` appears once, with both.
SELECT DISTINCT
       p.id, p.first_name, p.middle_name, p.last_name,
       p.adult_type, p.adult_type_other, p.status,
       p.school_id, s.name AS school_name,
       (SELECT group_concat(r2.key) FROM person_roles pr2
          JOIN roles r2 ON r2.id = pr2.role_id
         WHERE pr2.person_id = p.id)  AS role_keys,
       (SELECT group_concat(r2.name) FROM person_roles pr2
          JOIN roles r2 ON r2.id = pr2.role_id
         WHERE pr2.person_id = p.id)  AS role_names
FROM roles r
JOIN person_roles pr ON pr.role_id = r.id
JOIN people p        ON p.id = pr.person_id
JOIN schools s       ON s.id = p.school_id
WHERE r.key NOT IN ('delegate', 'chapter_leader')
ORDER BY p.last_name, p.first_name
LIMIT 200;
