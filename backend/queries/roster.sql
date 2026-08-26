-- The sponsor roster.
--
-- THIS IS THE QUERY docs/stack.md NAMES AS BUG #1. The tempting shape is:
-- fetch the roster, then loop over thirty delegates issuing one form-status
-- query each. Without an index on form_submissions(person_id) each of those
-- thirty is a full scan of ~3,450 rows -- 103,500 reads per page load instead
-- of ~90. At 3,000 loads a month that is 300 million reads from one screen,
-- against a 500M/month quota, and exceeding it returns BLOCKED.
--
-- So: ONE query, four LEFT JOINs, every one of them indexed. No query inside a
-- loop, anywhere, ever.

-- name: roster.list
-- form_submissions is reached by its UNIQUE (person_id, form_type) index, and
-- each paper_forms join by its (person_id, form_type) primary key.
--
-- The form_type in the LEFT JOIN is chosen per row rather than left open,
-- because a person with both a student_activity and an adult_registration row
-- would otherwise appear twice on their own sponsor's roster.
SELECT p.id, p.first_name, p.middle_name, p.last_name, p.suffix,
       p.person_type, p.adult_type, p.adult_type_other, p.board_title,
       p.status, p.grade, p.latin_level, p.meal,
       p.cell_phone, p.email, p.latin_knowledge,
       p.guardian_name, p.guardian_phone,
       p.code_prefix, p.code_issued_at, p.forms_unlocked,
       p.activity_sheet_waived,
       fs.status       AS form_status,
       fs.submitted_at AS form_submitted_at,
       COALESCE(pf_w.received, 0) AS waiver_received,
       COALESCE(pf_m.received, 0) AS medical_received,
       EXISTS (SELECT 1 FROM person_roles pr
               JOIN roles r ON r.id = pr.role_id
               WHERE pr.person_id = p.id AND r.key = 'chapter_leader') AS is_chapter_leader
FROM people p
LEFT JOIN form_submissions fs
       ON fs.person_id = p.id
      AND fs.form_type = CASE WHEN p.person_type = 'delegate'
                              THEN 'student_activity' ELSE 'adult_registration' END
LEFT JOIN paper_forms pf_w
       ON pf_w.person_id = p.id AND pf_w.form_type = 'student_waiver'
LEFT JOIN paper_forms pf_m
       ON pf_m.person_id = p.id
      AND pf_m.form_type = CASE WHEN p.person_type = 'delegate'
                                THEN 'student_medical' ELSE 'adult_medical' END
WHERE p.school_id = ?
ORDER BY p.person_type, p.last_name, p.first_name;

-- name: roster.import_by_key
-- The idempotency check. UNIQUE on idempotency_key, so this is a single indexed
-- lookup. A repeat commit finds this row and returns the original result rather
-- than importing again -- which is what makes a double-click harmless.
SELECT id, school_id, actor_person_id, parsed_count, committed_count, created_at
FROM roster_imports WHERE idempotency_key = ?;

-- name: roster.import_create
INSERT INTO roster_imports (
  school_id, actor_person_id, idempotency_key, raw_text,
  parsed_count, committed_count, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?);

-- name: roster.people_of_import
-- Which people a given import created, so a repeated commit returns exactly
-- what the first one did rather than a plausible-looking approximation.
--
-- Keyed on roster_import_id, NOT on created_at. Matching by timestamp looked
-- fine and was wrong: two people created in the same second are
-- indistinguishable, so a re-read could return the whole roster.
SELECT id, first_name, middle_name, last_name, suffix, person_type, code_prefix
FROM people
WHERE roster_import_id = ?
ORDER BY id;
