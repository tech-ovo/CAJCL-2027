-- Meal preferences and adult kinds, counted where every other count lives.
--
-- WHY NOT JUST QUERY `people`
--     Because "aggregates are never computed live" is one of this system's
--     two standing rules, and the reason is Turso's billing: a row read is a
--     row SCANNED. `SELECT meal, COUNT(*) FROM people GROUP BY meal` reads
--     every person at the convention every time somebody opens the page, and
--     no index helps a full aggregate.
--
--     The registration dashboard is opened by a handful of chairs, so the
--     absolute cost would have been survivable. The rule is not about this
--     page; it is about the next one, written in a hurry in March by somebody
--     who saw this page do it.
--
-- WHY THIS IS FREE
--     `stats.count_school` already reads exactly these rows -- it is how
--     delegates_active is computed -- and it runs inside the transaction that
--     changed them. Six more SUM(CASE ...) columns over rows already being
--     read cost nothing measurable, and the dashboard then reads fifty rows
--     instead of twelve hundred.
--
-- The four meal columns count ACTIVE people only. Somebody who withdrew is not
-- eating, whether or not their chapter already paid for them -- which is the
-- one place `cancelled_paid` behaves differently from the billing columns.

ALTER TABLE school_stats ADD COLUMN meal_regular      INTEGER NOT NULL DEFAULT 0;
ALTER TABLE school_stats ADD COLUMN meal_vegetarian   INTEGER NOT NULL DEFAULT 0;
ALTER TABLE school_stats ADD COLUMN meal_gluten_free  INTEGER NOT NULL DEFAULT 0;
ALTER TABLE school_stats ADD COLUMN meal_unanswered   INTEGER NOT NULL DEFAULT 0;

-- Sponsors and chaperones separately, so the dashboard can say who the adults
-- are. Everything else is `adults_active - sponsors - chaperones`, which needs
-- no column of its own.
ALTER TABLE school_stats ADD COLUMN adults_sponsors   INTEGER NOT NULL DEFAULT 0;
ALTER TABLE school_stats ADD COLUMN adults_chaperones INTEGER NOT NULL DEFAULT 0;
