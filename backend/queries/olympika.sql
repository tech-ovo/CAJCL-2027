-- Olympika: events, heats, sign-ups, teams and brackets.
--
-- olympika_events is a handful of rows and is read whole. EVERYTHING ELSE is
-- read one event at a time, through the index that begins with event_id (or
-- person_id, for a delegate's own entries), so no call ever reads the sign-ups
-- of every event at once.
--
-- "Counts" below are people who are actually attending: status 'active' and
-- approval 'approved', the same rule every other figure in the system uses.

-- ---------------------------------------------------------------------------
-- Events
-- ---------------------------------------------------------------------------

-- name: olympika.events
SELECT id, name, description, kind, location, signup_open, max_per_school,
       sort_order, created_at, updated_at
FROM olympika_events
ORDER BY sort_order, name COLLATE NOCASE;

-- name: olympika.event_get
SELECT * FROM olympika_events WHERE id = ?;

-- name: olympika.event_create
INSERT INTO olympika_events (name, description, kind, location, signup_open,
                             max_per_school, sort_order, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);

-- name: olympika.event_update
UPDATE olympika_events
SET name = ?, description = ?, kind = ?, location = ?, signup_open = ?,
    max_per_school = ?, sort_order = ?, updated_at = ?
WHERE id = ?;

-- name: olympika.event_delete
DELETE FROM olympika_events WHERE id = ?;

-- ---------------------------------------------------------------------------
-- Heats
-- ---------------------------------------------------------------------------

-- name: olympika.heats
-- idx_olympika_heats_event.
SELECT id, event_id, number, label, starts_at, ends_at
FROM olympika_heats
WHERE event_id = ?
ORDER BY number;

-- name: olympika.heat_get
SELECT * FROM olympika_heats WHERE id = ?;

-- name: olympika.heat_create
INSERT INTO olympika_heats (event_id, number, label, starts_at, ends_at,
                            created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?);

-- name: olympika.heat_update
UPDATE olympika_heats
SET label = ?, starts_at = ?, ends_at = ?, updated_at = ?
WHERE id = ?;

-- name: olympika.heat_delete
DELETE FROM olympika_heats WHERE id = ?;

-- name: olympika.heats_delete_for_event
DELETE FROM olympika_heats WHERE event_id = ?;

-- ---------------------------------------------------------------------------
-- Sign-ups for individual events
-- ---------------------------------------------------------------------------

-- name: olympika.signups_for_event
-- The Director's list: idx_olympika_signups_event, then a primary-key lookup
-- each for the person, the chapter and the heat. In heat and lane order, with
-- everybody not yet in a heat at the end.
SELECT s.id, s.person_id, s.school_id, s.heat_id, s.lane, s.signed_up_at,
       p.first_name, p.last_name, p.school_seq, p.grade, p.latin_level,
       sc.name AS school_name, sc.number AS school_number,
       h.number AS heat_number, h.label AS heat_label
FROM olympika_signups s
JOIN people p ON p.id = s.person_id
JOIN schools sc ON sc.id = s.school_id
LEFT JOIN olympika_heats h ON h.id = s.heat_id
WHERE s.event_id = ? AND p.status = 'active' AND p.approval = 'approved'
ORDER BY h.number IS NULL, h.number, s.lane, sc.name COLLATE NOCASE,
         p.last_name COLLATE NOCASE, p.first_name COLLATE NOCASE;

-- name: olympika.signup_count_for_event
SELECT COUNT(*)
FROM olympika_signups s
JOIN people p ON p.id = s.person_id
WHERE s.event_id = ? AND p.status = 'active' AND p.approval = 'approved';

-- name: olympika.signups_for_person
-- A delegate's own sign-ups: idx_olympika_signups_person.
SELECT s.id, s.event_id, s.heat_id, s.lane, s.signed_up_at,
       h.number AS heat_number, h.label AS heat_label,
       h.starts_at AS heat_starts_at, h.ends_at AS heat_ends_at
FROM olympika_signups s
LEFT JOIN olympika_heats h ON h.id = s.heat_id
WHERE s.person_id = ?;

-- name: olympika.signup_get
SELECT * FROM olympika_signups WHERE id = ?;

-- name: olympika.signup_for_person
SELECT * FROM olympika_signups WHERE event_id = ? AND person_id = ?;

-- name: olympika.signup_count_for_school
-- Against max_per_school: idx_olympika_signups_school.
SELECT COUNT(*) FROM olympika_signups WHERE event_id = ? AND school_id = ?;

-- name: olympika.signup_create
INSERT INTO olympika_signups (event_id, person_id, school_id, signed_up_at)
VALUES (?, ?, ?, ?);

-- name: olympika.signup_set_heat
UPDATE olympika_signups SET heat_id = ?, lane = ? WHERE id = ?;

-- name: olympika.signups_unassign_heat
-- A heat that is being deleted. idx_olympika_signups_heat.
UPDATE olympika_signups SET heat_id = NULL, lane = NULL WHERE heat_id = ?;

-- name: olympika.signup_delete
DELETE FROM olympika_signups WHERE id = ?;

-- name: olympika.signups_delete_for_event
DELETE FROM olympika_signups WHERE event_id = ?;

-- name: olympika.signups_delete_for_person
-- Redaction.
DELETE FROM olympika_signups WHERE person_id = ?;

-- ---------------------------------------------------------------------------
-- Teams
-- ---------------------------------------------------------------------------

-- name: olympika.teams_for_event
-- idx_olympika_teams_name (leading column event_id), then primary-key lookups.
-- Teams whose captain has withdrawn from the convention are still listed:
-- the bracket needs them.
SELECT t.id, t.event_id, t.school_id, t.captain_person_id, t.name, t.seed,
       t.created_at, t.updated_at,
       p.first_name, p.last_name, p.school_seq, p.grade, p.latin_level,
       p.status AS person_status, p.approval,
       sc.name AS school_name, sc.number AS school_number
FROM olympika_teams t
JOIN schools sc ON sc.id = t.school_id
LEFT JOIN people p ON p.id = t.captain_person_id
WHERE t.event_id = ?
ORDER BY t.seed IS NULL, t.seed, t.created_at, t.id;

-- name: olympika.teams_for_captain
-- A delegate's own teams: idx_olympika_teams_person.
SELECT id, event_id, school_id, name, seed, created_at, updated_at
FROM olympika_teams
WHERE captain_person_id = ?;

-- name: olympika.team_get
SELECT * FROM olympika_teams WHERE id = ?;

-- name: olympika.team_for_captain
SELECT * FROM olympika_teams WHERE event_id = ? AND captain_person_id = ?;

-- name: olympika.team_count_for_school
-- idx_olympika_teams_school.
SELECT COUNT(*) FROM olympika_teams WHERE event_id = ? AND school_id = ?;

-- name: olympika.team_names_for_school
-- To give an unnamed team the chapter's name, with a number if it is taken.
SELECT name FROM olympika_teams WHERE event_id = ? AND school_id = ?;

-- name: olympika.team_count_for_event
SELECT COUNT(*) FROM olympika_teams WHERE event_id = ?;

-- name: olympika.team_create
INSERT INTO olympika_teams (event_id, school_id, captain_person_id, name,
                            created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?);

-- name: olympika.team_rename
UPDATE olympika_teams SET name = ?, updated_at = ? WHERE id = ?;

-- name: olympika.team_set_seed
UPDATE olympika_teams SET seed = ?, updated_at = ? WHERE id = ?;

-- name: olympika.teams_clear_seeds
UPDATE olympika_teams SET seed = NULL, updated_at = ? WHERE event_id = ?;

-- name: olympika.team_orphan
-- Redaction of a captain after the bracket was drawn: the team stays so the
-- bracket keeps its shape, but nothing about the person does.
UPDATE olympika_teams
SET captain_person_id = NULL, name = ?, updated_at = ?
WHERE id = ?;

-- name: olympika.team_delete
DELETE FROM olympika_teams WHERE id = ?;

-- name: olympika.teams_delete_for_event
DELETE FROM olympika_teams WHERE event_id = ?;

-- ---------------------------------------------------------------------------
-- Brackets
-- ---------------------------------------------------------------------------

-- name: olympika.matches_for_event
-- idx_olympika_matches_slot, in play order, with both teams' names.
SELECT m.id, m.event_id, m.round, m.slot, m.team_a_id, m.team_b_id,
       m.winner_id, m.score_a, m.score_b, m.starts_at, m.ends_at, m.field,
       ta.name AS team_a_name, ta.school_id AS team_a_school_id,
       tb.name AS team_b_name, tb.school_id AS team_b_school_id
FROM olympika_matches m
LEFT JOIN olympika_teams ta ON ta.id = m.team_a_id
LEFT JOIN olympika_teams tb ON tb.id = m.team_b_id
WHERE m.event_id = ?
ORDER BY m.round, m.slot;

-- name: olympika.matches_for_team
-- One team's games, through the two team indexes.
SELECT m.id, m.event_id, m.round, m.slot, m.team_a_id, m.team_b_id,
       m.winner_id, m.score_a, m.score_b, m.starts_at, m.ends_at, m.field,
       ta.name AS team_a_name, tb.name AS team_b_name
FROM olympika_matches m
LEFT JOIN olympika_teams ta ON ta.id = m.team_a_id
LEFT JOIN olympika_teams tb ON tb.id = m.team_b_id
WHERE m.team_a_id = ? OR m.team_b_id = ?
ORDER BY m.round;

-- name: olympika.match_get
SELECT * FROM olympika_matches WHERE id = ?;

-- name: olympika.match_at
SELECT * FROM olympika_matches WHERE event_id = ? AND round = ? AND slot = ?;

-- name: olympika.match_create
INSERT INTO olympika_matches (event_id, round, slot, team_a_id, team_b_id,
                              winner_id, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?);

-- name: olympika.match_update
UPDATE olympika_matches
SET team_a_id = ?, team_b_id = ?, winner_id = ?, score_a = ?, score_b = ?,
    starts_at = ?, ends_at = ?, field = ?, updated_at = ?
WHERE id = ?;

-- name: olympika.matches_delete_for_event
DELETE FROM olympika_matches WHERE event_id = ?;

-- name: olympika.match_count_for_event
-- Whether a bracket has been drawn: idx_olympika_matches_slot.
SELECT COUNT(*) FROM olympika_matches WHERE event_id = ?;
