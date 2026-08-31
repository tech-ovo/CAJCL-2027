-- The counter caches.
--
-- Aggregates are NEVER computed live for a page view. These queries run inside
-- the same transaction as any mutation that changes them, and pages read the
-- cached row.
--
-- The arithmetic that makes this non-negotiable: COUNT(*) over `people` at full
-- size costs ~1,150 row reads. The welcome page is unauthenticated and reachable
-- by crawlers; 100,000 hits computed live is 115 million reads against a
-- 500M/month quota, and exceeding it returns BLOCKED -- an outage you cannot buy
-- your way out of during convention.

-- name: stats.count_school
-- Counts for ONE school. Indexed by idx_people_school, so this reads that
-- school's ~35 rows, not the whole table. Safe to run on every mutation.
--
-- Completion is defined in docs/schema.md:
--   Delegate: student_activity submitted + student_waiver + student_medical.
--   Adult:    adult_registration submitted + adult_medical.
--             SCL adults skip adult_registration entirely.
-- `cancelled_paid` is counted separately from `cancelled` because there are no
-- refunds: someone who withdrew after their chapter paid still counts toward
-- the invoice, while someone who withdrew before payment does not.
SELECT
  SUM(CASE WHEN p.person_type = 'delegate' AND p.status = 'active'         THEN 1 ELSE 0 END) AS delegates_active,
  SUM(CASE WHEN p.person_type = 'delegate' AND p.status = 'cancelled'      THEN 1 ELSE 0 END) AS delegates_cancelled,
  SUM(CASE WHEN p.person_type = 'delegate' AND p.status = 'cancelled_paid' THEN 1 ELSE 0 END) AS delegates_cancelled_paid,
  SUM(CASE WHEN p.person_type = 'adult'    AND p.status = 'active'         THEN 1 ELSE 0 END) AS adults_active,
  SUM(CASE WHEN p.person_type = 'adult'    AND p.status = 'cancelled'      THEN 1 ELSE 0 END) AS adults_cancelled,
  SUM(CASE WHEN p.person_type = 'adult'    AND p.status = 'cancelled_paid' THEN 1 ELSE 0 END) AS adults_cancelled_paid,

  -- A delegate whose activity sheet is WAIVED counts as complete once their
  -- paper is in. They were added at the desk on the Friday; there is no sheet
  -- for them to submit, and leaving them permanently unfinished would send a
  -- chair chasing somebody who cannot act. The paper is still required.
  SUM(CASE WHEN p.person_type = 'delegate' AND p.status = 'active'
            AND (fs.status = 'submitted' OR p.activity_sheet_waived = 1)
            AND pf_w.received = 1
            AND pf_m.received = 1
           THEN 1 ELSE 0 END) AS delegates_complete,

  SUM(CASE WHEN p.person_type = 'adult' AND p.status = 'active'
            AND (fs.status = 'submitted' OR p.adult_type = 'scl')
            AND pf_a.received = 1
           THEN 1 ELSE 0 END) AS adults_complete,

  -- Meals, for the caterer, and adult kinds, for the chairs. Counted here
  -- because these rows are already being read; see migration 012 for why they
  -- are not a live GROUP BY.
  --
  -- ACTIVE ONLY. Somebody who withdrew is not eating, whether or not their
  -- chapter paid for them -- the one place cancelled_paid parts company with
  -- the billing columns above.
  SUM(CASE WHEN p.status = 'active' AND p.meal = 'regular'     THEN 1 ELSE 0 END) AS meal_regular,
  SUM(CASE WHEN p.status = 'active' AND p.meal = 'vegetarian'  THEN 1 ELSE 0 END) AS meal_vegetarian,
  SUM(CASE WHEN p.status = 'active' AND p.meal = 'gluten_free' THEN 1 ELSE 0 END) AS meal_gluten_free,
  -- NOT ANSWERED is not the same as NO MEAL. Somebody who has not decided is
  -- still to be chased; somebody bringing their own has answered and is not
  -- eating. Folding them together would have the caterer cook for one and
  -- the chairs chase the other.
  SUM(CASE WHEN p.status = 'active' AND (p.meal IS NULL OR p.meal = '')
           THEN 1 ELSE 0 END) AS meal_unanswered,
  SUM(CASE WHEN p.status = 'active' AND p.meal = 'none'
           THEN 1 ELSE 0 END) AS meal_none,

  SUM(CASE WHEN p.status = 'active' AND p.adult_type = 'sponsor'   THEN 1 ELSE 0 END) AS adults_sponsors,
  SUM(CASE WHEN p.status = 'active' AND p.adult_type = 'chaperone' THEN 1 ELSE 0 END) AS adults_chaperones
FROM people p
LEFT JOIN form_submissions fs
       ON fs.person_id = p.id
      AND fs.form_type = CASE WHEN p.person_type = 'delegate'
                              THEN 'student_activity' ELSE 'adult_registration' END
LEFT JOIN paper_forms pf_w ON pf_w.person_id = p.id AND pf_w.form_type = 'student_waiver'
LEFT JOIN paper_forms pf_m ON pf_m.person_id = p.id AND pf_m.form_type = 'student_medical'
LEFT JOIN paper_forms pf_a ON pf_a.person_id = p.id AND pf_a.form_type = 'adult_medical'
WHERE p.school_id = ?;

-- name: stats.paid_for_school
-- Payments are append-only and a correction is a new row, possibly negative,
-- so the balance is always the sum. Indexed by idx_payments_school.
SELECT COALESCE(SUM(amount_cents), 0) AS amount_paid_cents
FROM payments WHERE school_id = ?;

-- name: stats.upsert_school
-- The money is computed in Python (backend/lib/stats.py) rather than here,
-- because the invoice rule -- billable counts, the free-adult ratio, and the
-- discount floor -- is the piece a future commissioner is most likely to have
-- to read and check by hand.
INSERT INTO school_stats (
  school_id, delegates_active, delegates_cancelled, delegates_cancelled_paid,
  adults_active, adults_cancelled, adults_cancelled_paid,
  delegates_complete, adults_complete,
  meal_regular, meal_vegetarian, meal_gluten_free, meal_unanswered, meal_none,
  adults_sponsors, adults_chaperones,
  discount_cents, amount_owed_cents, amount_paid_cents, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (school_id) DO UPDATE SET
  delegates_active         = excluded.delegates_active,
  delegates_cancelled      = excluded.delegates_cancelled,
  delegates_cancelled_paid = excluded.delegates_cancelled_paid,
  adults_active            = excluded.adults_active,
  adults_cancelled         = excluded.adults_cancelled,
  adults_cancelled_paid    = excluded.adults_cancelled_paid,
  delegates_complete       = excluded.delegates_complete,
  adults_complete          = excluded.adults_complete,
  meal_regular             = excluded.meal_regular,
  meal_vegetarian          = excluded.meal_vegetarian,
  meal_gluten_free         = excluded.meal_gluten_free,
  meal_unanswered          = excluded.meal_unanswered,
  meal_none                = excluded.meal_none,
  adults_sponsors          = excluded.adults_sponsors,
  adults_chaperones        = excluded.adults_chaperones,
  discount_cents           = excluded.discount_cents,
  amount_owed_cents        = excluded.amount_owed_cents,
  amount_paid_cents        = excluded.amount_paid_cents,
  updated_at               = excluded.updated_at;

-- name: stats.recompute_public
-- Site-wide totals for the welcome page, derived from school_stats rather than
-- from `people`. This scans school_stats -- at most ~50 rows, well under the
-- 200-row threshold the CI plan check enforces.
--
-- kind = 'chapter' excludes the state board, which is a school row only because
-- people.school_id is NOT NULL. It is not a chapter and must never appear in a
-- number shown to the public.
INSERT INTO public_stats_cache (id, schools_ms, schools_hs, delegates, adults, updated_at)
SELECT 1,
       -- CHAPTERS are counted, and a chapter is a school. A school sending
       -- both a middle and a high school delegation sends two. SCL and
       -- members at large are neither, so they are organizations -- and
       -- counting them here made the chapter figure wrong and listed SCL as
       -- a high school.
       COALESCE(SUM(CASE WHEN s.kind = 'chapter' AND s.level = 'MS'
                         THEN 1 ELSE 0 END), 0),
       COALESCE(SUM(CASE WHEN s.kind = 'chapter' AND s.level = 'HS'
                         THEN 1 ELSE 0 END), 0),
       -- PEOPLE are counted wherever they come from. Somebody attending
       -- without a chapter behind them is still attending, and leaving them
       -- out understated the convention.
       COALESCE(SUM(ss.delegates_active), 0),
       COALESCE(SUM(ss.adults_active), 0),
       ?
FROM schools s
JOIN school_stats ss ON ss.school_id = s.id
WHERE s.status = 'active'
ON CONFLICT (id) DO UPDATE SET
  schools_ms = excluded.schools_ms,
  schools_hs = excluded.schools_hs,
  delegates  = excluded.delegates,
  adults     = excluded.adults,
  updated_at = excluded.updated_at;

-- name: stats.public
-- What the welcome page actually serves. ONE row read per request.
SELECT schools_ms, schools_hs, delegates, adults, updated_at
FROM public_stats_cache WHERE id = 1;

-- name: stats.for_school
SELECT * FROM school_stats WHERE school_id = ?;

-- name: stats.dashboard
-- The registration chair dashboard: fifty schools, one query, no loop.
-- Scans school_stats (~50 rows) joined to schools by primary key. Organizations
-- are excluded -- the state board is not a chapter and has no roster to track.
SELECT s.id, s.name, s.level, s.city, s.status, s.billing_exempt,
       s.discount_cents, s.discount_reason, s.notes,
       ss.delegates_active, ss.delegates_cancelled, ss.delegates_cancelled_paid,
       ss.adults_active, ss.adults_cancelled, ss.adults_cancelled_paid,
       ss.delegates_complete, ss.adults_complete,
       ss.amount_owed_cents, ss.amount_paid_cents, ss.updated_at
FROM schools s
LEFT JOIN school_stats ss ON ss.school_id = s.id
WHERE s.kind = 'chapter'
ORDER BY s.name;


-- name: stats.registration_overview
-- The registration dashboard: everyone coming, how far along they are, and
-- what they owe. Reads school_stats -- about fifty rows -- never `people`.
-- Everything here was counted inside the transaction that changed it.
--
-- ORGANIZATIONS ARE INCLUDED, and `kind` comes back so the caller can tell
-- them apart. This used to filter to kind = 'chapter', which was right for the
-- table of chapters and wrong for every total above it: SCL's attendees eat,
-- and the meal figures on that page are what the caterer is given. Two people
-- today, more once "At Large" exists.
SELECT s.id AS school_id, s.name AS school_name, s.level, s.city, s.kind,
       s.billing_exempt, s.status,
       ss.delegates_active, ss.adults_active,
       ss.adults_sponsors, ss.adults_chaperones,
       ss.delegates_complete, ss.adults_complete,
       ss.meal_regular, ss.meal_vegetarian, ss.meal_gluten_free,
       ss.meal_unanswered, ss.meal_none,
       ss.discount_cents, ss.amount_owed_cents, ss.amount_paid_cents
FROM schools s
JOIN school_stats ss ON ss.school_id = s.id
ORDER BY s.name;

-- name: stats.checkin_board
-- The Friday desk. Every chapter, whether it has arrived, and its note.
--
-- Reads school_stats and schools -- about fifty rows -- so it can be refreshed
-- as often as somebody wants without thinking about it. Organizations are
-- included: SCL and members at large arrive too, and turning them away because
-- they are not a chapter would be absurd.
SELECT s.id AS school_id, s.name AS school_name, s.level, s.kind,
       s.checkin_note,
       -- What the sponsor said in advance: machines, arrival, when the bus
       -- has to leave. Different from checkin_note, which the desk writes
       -- about what actually turned up.
       s.notes AS chapter_note,
       ss.arrived_at,
       ss.delegates_active, ss.adults_active,
       ss.delegates_complete, ss.adults_complete
FROM schools s
JOIN school_stats ss ON ss.school_id = s.id
WHERE s.status = 'active'
ORDER BY ss.arrived_at IS NOT NULL, s.name;

-- name: stats.set_arrived
UPDATE school_stats SET arrived_at = ?, updated_at = ? WHERE school_id = ?;
