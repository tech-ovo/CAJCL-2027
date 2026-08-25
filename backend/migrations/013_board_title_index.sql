-- Find the board without reading everybody.
--
-- Settings > Roles lists the convention's board. It was defined as "everybody
-- holding a role other than delegate or chapter leader", which is driven from
-- person_roles and is a cheap index seek -- but it is also the wrong
-- definition. Somebody can have a title and no permissions: an awards chair,
-- before the awards pages exist. Granting them a role that reaches nothing so
-- the list looks right is exactly how a permission ends up granted for no
-- reason and never taken away.
--
-- `board_title IS NOT NULL` is the honest definition, and this partial index
-- makes it a seek rather than a scan of every delegate at the convention. It
-- indexes about a dozen rows, and costs a write only when a title is set --
-- which happens when somebody joins the board and never again.
CREATE INDEX IF NOT EXISTS idx_people_board_title
    ON people (board_title)
    WHERE board_title IS NOT NULL;
