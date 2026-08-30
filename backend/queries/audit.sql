-- Audit log. Append-only, enforced by trigger in migration 003.
--
-- Written in the SAME transaction as the mutation it describes. There is no
-- code path that changes data without one -- backend/lib/db.py refuses to
-- commit a transaction that mutated and did not audit.

-- name: audit.insert
INSERT INTO audit_log (
  ts_utc, actor_person_id, actor_role_snapshot, impersonator_person_id,
  action, entity_type, entity_id, school_id, summary,
  changed_fields, value_detail, request_id, ip_hash
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- name: audit.recent
-- The admin log viewer, newest first. Uses idx_audit_ts, so this is an indexed
-- backwards walk of exactly `limit` rows rather than a sort of the whole table.
-- Paginated by keyset (id < ?) rather than OFFSET: OFFSET makes page 50 scan
-- every row before it, which is how a log viewer quietly becomes the most
-- expensive page on the site.
SELECT a.id, a.ts_utc, a.action, a.summary, a.entity_type, a.entity_id,
       a.school_id, a.changed_fields, a.value_detail,
       a.actor_person_id, a.impersonator_person_id,
       actor.first_name  AS actor_first_name,
       actor.last_name   AS actor_last_name,
       imp.first_name    AS impersonator_first_name,
       imp.last_name     AS impersonator_last_name,
       s.name            AS school_name
FROM audit_log a
LEFT JOIN people  actor ON actor.id = a.actor_person_id
LEFT JOIN people  imp   ON imp.id   = a.impersonator_person_id
LEFT JOIN schools s     ON s.id     = a.school_id
WHERE a.id < ?
ORDER BY a.id DESC
LIMIT ?;

-- name: audit.recent_by_school
-- Same, filtered. Uses idx_audit_school (school_id, ts_utc).
SELECT a.id, a.ts_utc, a.action, a.summary, a.entity_type, a.entity_id,
       a.school_id, a.changed_fields, a.value_detail,
       a.actor_person_id, a.impersonator_person_id,
       actor.first_name AS actor_first_name,
       actor.last_name  AS actor_last_name,
       imp.first_name   AS impersonator_first_name,
       imp.last_name    AS impersonator_last_name,
       s.name           AS school_name
FROM audit_log a
LEFT JOIN people  actor ON actor.id = a.actor_person_id
LEFT JOIN people  imp   ON imp.id   = a.impersonator_person_id
LEFT JOIN schools s     ON s.id     = a.school_id
WHERE a.school_id = ? AND a.id < ?
ORDER BY a.id DESC
LIMIT ?;

-- name: audit.max_id
-- The starting cursor for keyset pagination. Reads one row.
SELECT COALESCE(MAX(id), 0) + 1 AS next_cursor FROM audit_log;

-- name: audit.recent_logins
-- Who has been trying to sign in, newest first.
--
-- Reads login_attempts, which the daily prune keeps to seven days, and is
-- bounded by LIMIT. Uses idx_login_attempts_ip only incidentally; this is a
-- backwards walk of the primary key, which is what "newest first" means on a
-- table whose ids are assigned in time order.
--
-- THE IP IS A PEPPERED HMAC AND STAYS ONE. It comes back so that two attempts
-- from the same place can be seen to be from the same place -- which is the
-- entire question anybody asks of this table -- without anybody, including
-- this program, being able to say where that place is.
SELECT id, code_prefix, ip_hash, succeeded, attempted_at
FROM login_attempts
ORDER BY id DESC
LIMIT ?;
