-- Somewhere to put "Convention President" that is not an adult-only column.
--
-- WHY THIS IS NEEDED
--     Almost everybody on the convention board is a STUDENT. They are
--     delegates at their own chapter who also hold a convention role, in
--     exactly the way a chapter leader is a delegate who also manages team
--     entries. One person, one account, one code; the role is granted on top.
--
--     Their title was being stored in `adult_type_other`, which is the free
--     text that goes with `adult_type = 'other'` and is meaningless for a
--     delegate. Worse, filing them as adults to make that column available
--     gave them the Adult Registration Form instead of the Student Activity
--     Sheet -- so a convention president could not complete the form every
--     other delegate completes, and their roster row read "Not yet" forever.
--
-- WHY A COLUMN RATHER THAN THE ROLE NAME
--     Roles are permissions: `admin`, `registration_chair`. Titles are what
--     somebody is called: "WHS Operations", "Logistics Coordinator". Two
--     people can hold `admin` and have different titles, and a title can
--     change without any permission changing. Deriving one from the other
--     would be wrong in both directions.
--
-- Nullable, and null for everyone who is not on the board -- which is almost
-- everyone. Nothing reads it except the places that show who somebody is.

ALTER TABLE people ADD COLUMN board_title TEXT;

-- Carry across anything already filed the old way, so nobody has to be
-- re-entered. `adult_type = 'other'` with free text was only ever used for
-- board members; a sponsor or a chaperone has a real adult_type and no free
-- text, so this touches nothing else.
UPDATE people
SET board_title = adult_type_other
WHERE person_type = 'adult'
  AND adult_type = 'other'
  AND adult_type_other IS NOT NULL
  AND board_title IS NULL;
