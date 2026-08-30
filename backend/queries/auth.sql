-- Authentication and sessions.
--
-- Login is ONE indexed equality lookup on people.code_hmac. That is what
-- idx_people_code_hmac is for, and why codes are HMAC'd rather than run through
-- a slow KDF -- a KDF would make login a full table scan, billed per row.

-- name: auth.person_by_code_hmac
-- The login lookup. SEARCH people USING INDEX idx_people_code_hmac.
SELECT p.id, p.school_id, p.person_type, p.adult_type, p.first_name,
       p.middle_name, p.last_name, p.suffix, p.status, p.code_prefix,
       p.pepper_version, p.forms_unlocked, p.latin_level, p.grade,
       p.latin_knowledge, p.meal, p.email, p.cell_phone,
       s.name AS school_name, s.level AS school_level, s.kind AS school_kind,
       s.number AS school_number, p.school_seq,
       s.billing_exempt, s.status AS school_status
FROM people p
JOIN schools s ON s.id = p.school_id
WHERE p.code_hmac = ?;

-- name: auth.scopes_for_person
-- The ONLY path from a person to a scope: person_roles -> roles -> role_scopes.
-- A scope is never attached to a person directly, anywhere, for any reason.
-- Uses idx_person_roles_person, then two primary-key lookups.
SELECT DISTINCT rs.scope
FROM person_roles pr
JOIN roles r        ON r.id = pr.role_id
JOIN role_scopes rs ON rs.role_id = r.id
WHERE pr.person_id = ?;

-- name: auth.roles_for_person
SELECT r.key, r.name
FROM person_roles pr
JOIN roles r ON r.id = pr.role_id
WHERE pr.person_id = ?
ORDER BY r.key;

-- name: auth.session_create
INSERT INTO sessions (
  person_id, token_hash, impersonator_person_id, impersonation_can_write,
  created_at, last_seen_at, expires_at, user_agent, ip_hash
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);

-- name: auth.session_by_token
-- Every authenticated request starts here. SEARCH sessions USING INDEX
-- idx_sessions_token, then primary-key joins -- three rows read, not a scan.
SELECT sess.id AS session_id, sess.person_id, sess.impersonator_person_id,
       sess.impersonation_can_write, sess.expires_at, sess.revoked_at,
       sess.created_at AS session_created_at,
       -- Read so that authenticate() can decide IN PYTHON whether this session
       -- needs touching, and skip taking the write lock when it does not.
       sess.last_seen_at,
       p.school_id, p.person_type, p.adult_type, p.first_name, p.middle_name,
       p.last_name, p.suffix, p.status, p.code_prefix, p.forms_unlocked,
       p.latin_level, p.grade, p.latin_knowledge, p.meal, p.email, p.cell_phone,
       s.name AS school_name, s.level AS school_level, s.kind AS school_kind,
       s.number AS school_number, p.school_seq,
       s.billing_exempt, s.status AS school_status,
       imp.first_name AS impersonator_first_name,
       imp.last_name  AS impersonator_last_name
FROM sessions sess
JOIN people p    ON p.id = sess.person_id
JOIN schools s   ON s.id = p.school_id
LEFT JOIN people imp ON imp.id = sess.impersonator_person_id
WHERE sess.token_hash = ?;

-- name: auth.session_touch
-- Bumps last_seen_at so a person can recognise their own sessions on the
-- account page. Deliberately NOT audited -- see SILENT_ACTIONS in db.py.
--
-- THE `last_seen_at <` CLAUSE IS LOAD-BEARING, NOT AN OPTIMISATION.
--     Without it this is a WRITE ON EVERY AUTHENTICATED REQUEST. libSQL has a
--     single writer, so a sponsor loading a thirty-person roster while two
--     delegates save their forms produced three transactions all wanting the
--     write lock for a column nobody reads in real time -- and one of them came
--     back SQLITE_BUSY, which surfaced to the delegate as a 500.
--
--     The caller passes a cutoff a few minutes in the past. A session already
--     touched since then matches nothing and the statement takes no lock at
--     all, which turns the common case from a write into a no-op.
--
--     The account page shows this to the minute at best, so a few minutes of
--     staleness costs nothing a person would notice.
UPDATE sessions SET last_seen_at = ?
WHERE id = ? AND (last_seen_at IS NULL OR last_seen_at < ?);

-- name: auth.session_revoke
UPDATE sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL;

-- name: auth.session_revoke_all_for_person
-- Every session derived from a code dies with that code. Called by
-- regenerate-code, which is the whole reason a lost sheet is recoverable.
UPDATE sessions
SET revoked_at = ?
WHERE person_id = ? AND revoked_at IS NULL;

-- name: auth.sessions_for_person
-- The account page's "your active sessions" list. Assume shared devices: a
-- school Chromebook accumulates a dozen of these over a weekend.
SELECT id, created_at, last_seen_at, expires_at, user_agent,
       impersonator_person_id
FROM sessions
WHERE person_id = ? AND revoked_at IS NULL
ORDER BY last_seen_at DESC;

-- name: auth.session_owned_by
-- Guards session revocation: a person may revoke only their own sessions.
SELECT person_id FROM sessions WHERE id = ?;

-- name: auth.attempt_record
-- Rate-limit bookkeeping. attempted_code_hmac is the HMAC of whatever was
-- typed, valid or not -- without it there is nothing to count, since a failed
-- attempt matches no row in `people` by definition.
INSERT INTO login_attempts (attempted_code_hmac, code_prefix, ip_hash, succeeded, attempted_at)
VALUES (?, ?, ?, ?, ?);

-- name: auth.attempts_by_ip
-- 10 failures per IP per 15 minutes. Indexed range scan over a handful of rows
-- via idx_login_attempts_ip.
SELECT COUNT(*) AS failures
FROM login_attempts
WHERE ip_hash = ? AND succeeded = 0 AND attempted_at > ?;

-- name: auth.attempts_by_code
-- 5 failures per code per hour, via idx_login_attempts_code. This is what
-- separates one delegate fumbling their own code from someone walking the
-- keyspace from many addresses.
SELECT COUNT(*) AS failures
FROM login_attempts
WHERE attempted_code_hmac = ? AND succeeded = 0 AND attempted_at > ?;

-- name: auth.attempts_prune
-- Daily cron. Keeps the table small enough that the rate-limit ranges stay tiny.
DELETE FROM login_attempts WHERE attempted_at < ?;
