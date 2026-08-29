-- "That's Entertainment": watching it and being in it are different answers.
--
-- The item was seeded with no options, so a delegate ticking it told the
-- Activities chair only that they were interested. The chair needs to know how
-- many are auditioning, because that is a schedule with slots in it, and how
-- many are coming to watch, because that is a room with seats in it. One tick
-- answered neither.
--
-- `max_sub_selections` is 2: somebody auditioning is also in the audience for
-- everyone else, and there is no reason to make them choose.

UPDATE catalog_items
SET max_sub_selections = 2
WHERE name = 'That''s Entertainment';

INSERT INTO catalog_item_options (item_id, name, sort_order)
SELECT id, 'Auditioning', 10 FROM catalog_items
WHERE name = 'That''s Entertainment'
  AND NOT EXISTS (SELECT 1 FROM catalog_item_options o
                  WHERE o.item_id = catalog_items.id AND o.name = 'Auditioning');

INSERT INTO catalog_item_options (item_id, name, sort_order)
SELECT id, 'Watching', 20 FROM catalog_items
WHERE name = 'That''s Entertainment'
  AND NOT EXISTS (SELECT 1 FROM catalog_item_options o
                  WHERE o.item_id = catalog_items.id AND o.name = 'Watching');
