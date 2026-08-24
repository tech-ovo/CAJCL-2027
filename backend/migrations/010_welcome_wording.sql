-- Reword the welcome page.
--
-- WHY THIS IS A MIGRATION AND NOT AN EDIT TO 005
--     The change itself is two words: "certamen" becomes "Certamen", and "is
--     hosted by" becomes "will be held at". It was originally made by editing
--     005_seed_roles_settings.sql directly, which had already run against the
--     live database -- so the next deploy refused to start, correctly, with
--
--         005_seed_roles_settings.sql has already been applied but its
--         contents have changed.
--
--     Migrations are forward-only. A file that has run is a historical record
--     of what was done to a database that exists; changing it makes that
--     record a lie, and the checksum is what stops the lie from being quiet.
--     Even a comment counts.
--
--     So 005 is back to exactly what it was, and the new wording arrives here.
--
-- THIS IS ALSO NOT THE USUAL WAY TO CHANGE WORDING
--     Every document in this table is editable from Settings > Printed wording
--     without a deploy, and that is how a commissioner should reword anything.
--     A migration is right only when the change should also apply to a database
--     that has not been created yet -- which is the case here, because it fixes
--     the DEFAULT text a future convention starts from.
--
--     `WHERE body_md LIKE` keeps it honest: if somebody has already reworded
--     this from the dashboard, their text is theirs and this leaves it alone.

UPDATE documents
SET body_md = 'The California Junior Classical League gathers each spring for two days of Certamen, competition, and ceremony. The 72nd State Convention will be held at University High School in Irvine.

Registration runs through your chapter''s sponsor. If you are a delegate, your sponsor will give you a sheet with your access code on it.',
    updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
WHERE key = 'welcome_body'
  AND body_md LIKE 'The California Junior Classical League gathers each spring for two days of certamen%';
