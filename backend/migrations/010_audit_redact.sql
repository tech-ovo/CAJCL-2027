-- Migration 010: Allow per-person redaction on audit_log summaries while preserving append-only invariant.
--
-- Deletion requests and California pupil privacy (SOPIPA, AB 1584) require
-- redacting a person's details everywhere, including within audit sentences.
-- The original trigger rejected every UPDATE. We drop it and recreate it with
-- an exception strictly limited to redactions: only `summary` may change, every
-- other column must remain identical, and the new summary must contain 'REDACTED'.
-- Any other update is rejected with 'audit_log is append-only'.

DROP TRIGGER audit_log_no_update;

CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
WHEN NOT (
    OLD.id = NEW.id
    AND OLD.ts_utc = NEW.ts_utc
    AND (OLD.actor_person_id IS NEW.actor_person_id)
    AND (OLD.actor_role_snapshot IS NEW.actor_role_snapshot)
    AND (OLD.impersonator_person_id IS NEW.impersonator_person_id)
    AND OLD.action = NEW.action
    AND (OLD.entity_type IS NEW.entity_type)
    AND (OLD.entity_id IS NEW.entity_id)
    AND (OLD.school_id IS NEW.school_id)
    AND (OLD.changed_fields IS NEW.changed_fields)
    AND (OLD.value_detail IS NEW.value_detail)
    AND (OLD.request_id IS NEW.request_id)
    AND (OLD.ip_hash IS NEW.ip_hash)
    AND NEW.summary LIKE '%REDACTED%'
)
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;
