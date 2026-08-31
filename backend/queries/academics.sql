-- Counts for the Academics, Activities and Athletics chairs.
--
-- The question these answer is "how many test papers do we print, and for
-- whom". Nothing here grades anything or records a score: this is registration
-- data, read by the people who have to prepare for it.

-- name: academics.item_counts
-- Every catalog item with how many delegates have chosen it.
--
-- DRIVEN FROM catalog_items, which is about fifty rows, with one indexed seek
-- per item into activity_selections via idx_activity_selections_item -- the
-- index 002 created for precisely this. Driven the other way it would scan
-- every selection at the convention, which is thousands of rows and, on Turso,
-- thousands of billed row reads for a page somebody refreshes.
--
-- Cancelled delegates are excluded: nobody prints a paper for a student who
-- withdrew. `cancelled_paid` is still billed, and still not attending.
SELECT c.name          AS category,
       c.key           AS category_key,
       c.sort_order    AS category_sort,
       i.id, i.name, i.sort_order,
       i.registration_scope,
       i.item_code,
       i.eligible_latin_levels,
       (SELECT COUNT(*)
          FROM activity_selections s
          JOIN people p ON p.id = s.person_id
         WHERE s.item_id = i.id AND p.status = 'active'
           AND p.activity_sheet_waived = 0)       AS chosen,
       (SELECT COUNT(*)
          FROM activity_selections s
          JOIN people p ON p.id = s.person_id
          JOIN schools sc ON sc.id = p.school_id
         WHERE s.item_id = i.id AND p.status = 'active'
           AND p.activity_sheet_waived = 0
           AND sc.level = 'MS')                                AS chosen_ms,
       (SELECT COUNT(*)
          FROM chapter_entries e
         WHERE e.item_id = i.id)                               AS chapter_entries
FROM catalog_items i
JOIN catalog_categories c ON c.id = i.category_id
WHERE i.active = 1 AND c.active = 1 AND c.applies_to = 'delegate'
ORDER BY c.sort_order, i.sort_order, i.name;

-- name: academics.item_by_chapter
-- One item, broken down by chapter. The drill-down from the row above.
--
-- Seeks idx_activity_selections_item for the one item, then reaches each
-- person by primary key. Bounded by the number of people who chose that item,
-- never by the size of the convention.
SELECT sc.id AS school_id, sc.name AS school_name, sc.level,
       COUNT(*) AS chosen
FROM activity_selections s
JOIN people p  ON p.id = s.person_id
JOIN schools sc ON sc.id = p.school_id
WHERE s.item_id = ? AND p.status = 'active'
  AND p.activity_sheet_waived = 0
GROUP BY sc.id
ORDER BY sc.name;

-- name: academics.item_people
-- Who, for one item. What a proctor's sign-in sheet is made of.
SELECT p.id, p.first_name, p.middle_name, p.last_name, p.suffix,
       p.grade, p.latin_level,
       sc.name AS school_name, sc.level AS school_level
FROM activity_selections s
JOIN people p   ON p.id = s.person_id
JOIN schools sc ON sc.id = p.school_id
WHERE s.item_id = ? AND p.status = 'active'
  AND p.activity_sheet_waived = 0
ORDER BY sc.name, p.last_name, p.first_name;

-- name: academics.item
-- One catalog item with the category it belongs to. A primary-key lookup.
SELECT i.id, i.name, i.description, i.registration_scope,
       i.eligible_latin_levels, i.active,
       c.name AS category, c.key AS category_key
FROM catalog_items i
JOIN catalog_categories c ON c.id = i.category_id
WHERE i.id = ?;
