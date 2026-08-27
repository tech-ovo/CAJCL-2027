-- "is hosted by University and Woodbridge High School".
--
-- 007_hosts.sql seeded "Jointly hosted by University High School and Woodbridge
-- High School", which sat in the rail under a "Hosted by" label and said
-- "hosted" twice. The label is gone from the welcome page -- three labelled
-- lines wrapped out of step on a phone, and this was the one that was a
-- sentence rather than an answer to a question -- so the value has to read as
-- a sentence on its own.
--
-- A NEW MIGRATION RATHER THAN AN EDIT TO 007. That one has been applied, and an
-- applied migration is never edited: the checksum guard exists to make that
-- impossible to do by accident. See docs/RUNBOOK.md 5b.
--
-- This is also editable from Settings -> Values like everything else here, so a
-- future commissioner changing the host schools needs no migration at all.

UPDATE settings
SET value = 'is hosted by University and Woodbridge High School',
    label = 'Hosts',
    updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
WHERE key = 'convention.hosts';
