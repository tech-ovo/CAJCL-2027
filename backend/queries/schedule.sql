-- The master convention schedule.
--
-- schedule_items is a few dozen rows by hand plus a row per Olympika heat and
-- per round of a bracket -- a couple of hundred at the very most -- and is
-- read whole, in time order, through idx_schedule_items_starts.

-- name: schedule.published
-- What every visitor sees. Public and cached, so nothing in it names a person.
SELECT id, title, description, location, starts_at, ends_at, source,
       olympika_event_id, updated_at
FROM schedule_items
WHERE published = 1
ORDER BY starts_at, id;

-- name: schedule.all
-- The Logistics chair's list, drafts included.
SELECT id, title, description, location, starts_at, ends_at, published, source,
       source_key, olympika_event_id, created_at, updated_at
FROM schedule_items
ORDER BY starts_at, id;

-- name: schedule.get
SELECT * FROM schedule_items WHERE id = ?;

-- name: schedule.create
INSERT INTO schedule_items (title, description, location, starts_at, ends_at,
                            published, source, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, 'manual', ?, ?);

-- name: schedule.update
UPDATE schedule_items
SET title = ?, description = ?, location = ?, starts_at = ?, ends_at = ?,
    published = ?, updated_at = ?
WHERE id = ?;

-- name: schedule.delete
DELETE FROM schedule_items WHERE id = ?;

-- name: schedule.for_event
-- The rows one Olympika event has put on the schedule, so the sync can tell
-- which to update and which to remove: idx_schedule_items_event.
SELECT id, source_key, title, location, starts_at, ends_at
FROM schedule_items
WHERE olympika_event_id = ?;

-- name: schedule.sync_insert
INSERT INTO schedule_items (title, description, location, starts_at, ends_at,
                            published, source, source_key, olympika_event_id,
                            created_at, updated_at)
VALUES (?, NULL, ?, ?, ?, 1, 'olympika', ?, ?, ?, ?);

-- name: schedule.sync_update
UPDATE schedule_items
SET title = ?, location = ?, starts_at = ?, ends_at = ?, updated_at = ?
WHERE id = ?;

-- name: schedule.delete_for_event
DELETE FROM schedule_items WHERE olympika_event_id = ?;

-- name: schedule.for_potluck
-- The one row an activities-potluck activity has on the schedule, if any:
-- idx_schedule_items_potluck.
SELECT id, title, description, location, starts_at, ends_at
FROM schedule_items
WHERE potluck_activity_id = ?;

-- name: schedule.sync_insert_potluck
INSERT INTO schedule_items (title, description, location, starts_at, ends_at,
                            published, source, source_key, potluck_activity_id,
                            created_at, updated_at)
VALUES (?, ?, ?, ?, ?, 1, 'potluck', ?, ?, ?, ?);

-- name: schedule.sync_update_potluck
UPDATE schedule_items
SET title = ?, description = ?, location = ?, starts_at = ?, ends_at = ?,
    updated_at = ?
WHERE id = ?;

-- name: schedule.delete_for_potluck
DELETE FROM schedule_items WHERE potluck_activity_id = ?;
