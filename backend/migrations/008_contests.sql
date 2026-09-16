-- 008_contests.sql -- the pre-convention contest portal.
--
-- Delegates submit Digital Art/Poster, Modern Myth, Original Poetry and the two
-- Original Slogans online; a chapter submits its Publicity portfolio. Judges
-- score them here, without seeing names or chapters, and the Academics chairs
-- read the results.
--
-- Everything a future chair would want to change -- the rules text, the
-- rubric, the accepted file types, the deadline -- is a row, not code.

-- ---------------------------------------------------------------------------
-- The `judge` scope
-- ---------------------------------------------------------------------------
-- A volunteer judge needs to read contest entries and score them, and nothing
-- else: not rosters, not test counts, not the rest of `academics`. So it is a
-- scope of its own, reached through a role like every other scope.
--
-- SQLite cannot alter a CHECK constraint, so role_scopes is rebuilt. Nothing
-- references it, and it holds a few dozen rows.
CREATE TABLE role_scopes_new (
  role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  -- '*' subsumes everything. The three identity scopes (sponsor, delegate,
  -- chapter) are ALWAYS school-limited; the four administrative scopes are
  -- global. `judge` is global too, but reaches only the judging screens --
  -- it is deliberately NOT in auth.ADMIN_SCOPES, so it opens no roster.
  scope   TEXT NOT NULL CHECK (scope IN ('*','registration','academics','awards',
                                         'sponsor','delegate','chapter','judge')),
  PRIMARY KEY (role_id, scope)
);
INSERT INTO role_scopes_new (role_id, scope) SELECT role_id, scope FROM role_scopes;
DROP TABLE role_scopes;
ALTER TABLE role_scopes_new RENAME TO role_scopes;

INSERT INTO roles (key, name, description, is_system, created_at) VALUES
  ('contest_judge', 'Contest Judge',
   'Scores pre-convention contest entries. Sees the entries, never the names or chapters behind them.',
   1, strftime('%Y-%m-%dT%H:%M:%SZ','now'));
INSERT INTO role_scopes (role_id, scope)
SELECT id, 'judge' FROM roles WHERE key = 'contest_judge';

-- ---------------------------------------------------------------------------
-- The catalog
-- ---------------------------------------------------------------------------
-- The category stays INACTIVE. These are not choices on the activity sheet --
-- a delegate enters one by submitting it -- and an active category would put
-- six checkboxes on every delegate's form and six rows of zeroes on Entries.
UPDATE catalog_categories
SET description = 'Submitted online before convention, from the Contests page.'
WHERE key = 'preconvention';

UPDATE catalog_items SET name = 'Original Poetry', active = 1
WHERE name = 'Poetry'
  AND category_id = (SELECT id FROM catalog_categories WHERE key = 'preconvention');
UPDATE catalog_items SET name = 'Original Slogan (English)', active = 1
WHERE name = 'Slogan (English)'
  AND category_id = (SELECT id FROM catalog_categories WHERE key = 'preconvention');
UPDATE catalog_items SET name = 'Original Slogan (Latin)', active = 1
WHERE name = 'Slogan (Latin)'
  AND category_id = (SELECT id FROM catalog_categories WHERE key = 'preconvention');
UPDATE catalog_items SET active = 1
WHERE name = 'Modern Myth'
  AND category_id = (SELECT id FROM catalog_categories WHERE key = 'preconvention');

-- Publicity is entered by a chapter, but its registration_scope stays
-- 'individual': 'chapter' means a TEAM on the Teams page, and Publicity is
-- not a team. Who enters a contest is `contests.entered_by`.
INSERT INTO catalog_items (category_id, name, sort_order, active) VALUES
  ((SELECT id FROM catalog_categories WHERE key='preconvention'), 'Digital Art/Poster', 5,  1),
  ((SELECT id FROM catalog_categories WHERE key='preconvention'), 'Publicity',          50, 1);

-- ---------------------------------------------------------------------------
-- contests
-- ---------------------------------------------------------------------------
-- One row per pre-convention contest: how it is entered and by whom.
--
-- `divisions`
--   none         one pool                                  -> 'Open'
--   level        by chapter                                -> 'MS', 'HS'
--   level_grade  by chapter, then grade in a high school   -> 'MS', 'HS 9-10', 'HS 11-12'
--   latin_level  by the delegate's Latin level             -> 'MS-I', 'MS-II', 'MS-III',
--                'HS-I', 'HS-II', 'HS-III', 'HS-Advanced' -- and nothing else.
-- The division is worked out when an entry is submitted and STORED on it, so
-- a delegate whose grade or level is corrected later does not move pools
-- mid-judging. Divisions are the Convention Book's rule and have no screen.
--
-- `facets` is a newline-separated list of categories judged separately within
-- one entry -- Publicity's eight. NULL means the entry is judged once.
CREATE TABLE contests (
  item_id           INTEGER PRIMARY KEY REFERENCES catalog_items(id),
  key               TEXT NOT NULL UNIQUE,
  entry_kind        TEXT NOT NULL CHECK (entry_kind IN ('file','text','link')),
  entered_by        TEXT NOT NULL CHECK (entered_by IN ('delegate','chapter')),
  divisions         TEXT NOT NULL DEFAULT 'none'
                      CHECK (divisions IN ('none','level','level_grade','latin_level')),
  -- CSV of lower-case extensions, for file entries.
  accepted_types    TEXT,
  needs_title       INTEGER NOT NULL DEFAULT 0,
  min_words         INTEGER,
  max_words         INTEGER,
  -- Points lost per started hundred words outside min_words..max_words.
  words_penalty     INTEGER NOT NULL DEFAULT 0,
  max_chars         INTEGER,
  needs_translation INTEGER NOT NULL DEFAULT 0,
  -- The creator must attend to win. Publicity is the one that does not.
  must_attend       INTEGER NOT NULL DEFAULT 1,
  facets            TEXT,
  rules_md          TEXT,
  sort_order        INTEGER NOT NULL DEFAULT 0
);

INSERT INTO contests (item_id, key, entry_kind, entered_by, divisions,
                      accepted_types, needs_title, min_words, max_words,
                      words_penalty, max_chars, needs_translation, must_attend,
                      facets, rules_md, sort_order)
SELECT i.id, v.key, v.entry_kind, v.entered_by, v.divisions, v.accepted_types,
       v.needs_title, v.min_words, v.max_words, v.words_penalty, v.max_chars,
       v.needs_translation, v.must_attend, v.facets, v.rules_md, v.sort_order
FROM (
  SELECT 'Digital Art/Poster' AS name, 'digital_art' AS key, 'file' AS entry_kind,
         'delegate' AS entered_by, 'latin_level' AS divisions,
         'jpg,jpeg,tif,tiff,pdf,gif,png' AS accepted_types, 1 AS needs_title,
         NULL AS min_words, NULL AS max_words, 0 AS words_penalty,
         NULL AS max_chars, 0 AS needs_translation, 1 AS must_attend,
         NULL AS facets, 10 AS sort_order,
'Create an entirely digital piece of art on a classical theme, **or** design a digital poster to promote JCL and the Classics.

Judged by Latin level, in seven divisions: MS-I, MS-II, MS-III, HS-I, HS-II, HS-III and HS-Advanced.

- The concept and the execution must be your own. This is **not** a graphic design contest: work assembled in Canva is likely to be disqualified for using material that is not your creation.
- Any size and any medium, but submit it as a single JPG, TIFF, PDF, GIF or PNG file. Horizontal or vertical is fine.
- Use the highest resolution you can: at least 300 dpi, and 600 dpi or more is better.
- By entering you confirm that the work is entirely your own and infringes nobody''s rights. CAJCL may contact you about using a promotional poster in the future.
- You must attend convention to win.' AS rules_md
  UNION ALL
  SELECT 'Modern Myth', 'modern_myth', 'file', 'delegate', 'level_grade',
         'pdf,docx,txt', 1, 500, 1200, 3, NULL, 0, 1, NULL, 20,
'Enter **one** modern myth, in prose or poetry, written since the last state convention. Divisions: middle school, high school grades 9–10, and grades 11–12.

**Length: 500 to 1,200 words**, counting articles and prepositions. A myth outside that range loses 3 points for every 100 words it is over or under.

Choose one topic:

- An original myth explaining something in nature or modern culture. Use Greek **or** Roman mythological characters, not both; new characters with classical names are allowed.
- A classical myth in a modern setting, recognizable from its plot rather than its character names. Name the original myth in a postscript.
- A new myth using classical figures, with minor new characters — a new Hercules story, for example.

Do not contradict existing myths. New characters and adventures are fine; changing basic, traditional mythology is not.

Do not put your name or your chapter in the file. Judges read entries without knowing whose they are.'
  UNION ALL
  SELECT 'Original Poetry', 'poetry', 'file', 'delegate', 'level_grade',
         'pdf,docx,txt', 1, NULL, NULL, 0, NULL, 0, 1, NULL, 30,
'Enter **one** original poem in English, in any meter or verse, on the convention theme. Divisions: middle school, high school grades 9–10, and grades 11–12.

Do not put your name or your chapter in the file. Judges read entries without knowing whose they are.'
  UNION ALL
  SELECT 'Original Slogan (English)', 'slogan_english', 'text', 'delegate', 'level_grade',
         NULL, 0, NULL, NULL, 0, 100, 0, 1, NULL, 40,
'A slogan that publicizes Latin or JCL, short enough for a bumper sticker or a button. Divisions: middle school, high school grades 9–10, and grades 11–12.

You may enter two slogans in all: one in English and one in Latin. Once submitted, a slogan becomes the property of CAJCL and may be used for publicity.'
  UNION ALL
  SELECT 'Original Slogan (Latin)', 'slogan_latin', 'text', 'delegate', 'level_grade',
         NULL, 0, NULL, NULL, 0, 100, 1, 1, NULL, 50,
'A Latin slogan that publicizes Latin or JCL, short enough for a bumper sticker or a button. **Include an English translation.** Divisions: middle school, high school grades 9–10, and grades 11–12.

You may enter two slogans in all: one in English and one in Latin. Once submitted, a slogan becomes the property of CAJCL and may be used for publicity.'
  UNION ALL
  SELECT 'Publicity', 'publicity', 'link', 'chapter', 'level',
         NULL, 0, NULL, NULL, 0, NULL, 0, 0,
'Media
School-Affiliated Media
School-Affiliated Posters/Displays outside of school
Posters/Displays at school
Miscellaneous
Best Club Swag
Best Recruitment Presentation
Best Overall Portfolio', 60,
'Every chapter in good standing may enter, in a middle school or high school division. **Nobody needs to attend convention to win.**

Everything must be essentially about the JCL, Latin, Greek or classical studies, written or started by your club, and published or available to the public between the close of the last convention and the deadline.

Submit **one portfolio**: a shared Google document holding your best entry for each category, in the order listed, each clearly labelled. Every item needs a picture or a working link and up to 150 words saying why it was the best in the state — how many people saw it, how many were made, how it was received.

- **Media** — newspapers, radio, TV, websites, podcasts, and outside social media accounts sharing your posts. Not school media.
- **School-Affiliated Media** — school or district media, but not your chapter''s own accounts.
- **School-Affiliated Posters/Displays outside of school**
- **Posters/Displays at school**
- **Miscellaneous** — parade floats, answering-machine messages, flyers, decorated pumpkins, bookmarks.
- **Best Club Swag** — clothing, key chains, bumper stickers, made or ordered by your club. Nothing bought from others at State or Nationals.
- **Best Recruitment Presentation** — on or off campus, recruiting students or promoting Latin, Greek or JCL.
- **Best Overall Portfolio** — three places.

Portfolios submitted after the deadline are not judged. Falsifying an entry makes the school ineligible for the whole contest that year.'
) AS v
JOIN catalog_items i
  ON i.name = v.name
 AND i.category_id = (SELECT id FROM catalog_categories WHERE key = 'preconvention');

-- ---------------------------------------------------------------------------
-- contest_criteria
-- ---------------------------------------------------------------------------
-- The rubric. A judge enters points per criterion, up to max_points.
--
-- The Convention Book gives no rubric for Digital Art/Poster or the slogans,
-- so each starts with a single 100-point line for the Academics chairs to
-- replace from the Judging page before anyone scores.
CREATE TABLE contest_criteria (
  id          INTEGER PRIMARY KEY,
  item_id     INTEGER NOT NULL REFERENCES contests(item_id),
  label       TEXT NOT NULL,
  max_points  INTEGER NOT NULL CHECK (max_points > 0),
  sort_order  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_contest_criteria_item ON contest_criteria (item_id, sort_order);

INSERT INTO contest_criteria (item_id, label, max_points, sort_order)
SELECT c.item_id, v.label, v.max_points, v.sort_order
FROM (
  SELECT 'modern_myth' AS key, 'Classical Allusion/Reference' AS label, 25 AS max_points, 10 AS sort_order
  UNION ALL SELECT 'modern_myth', 'Originality/Creativity',          25, 20
  UNION ALL SELECT 'modern_myth', 'Theme/Style/Mechanics',           25, 30
  UNION ALL SELECT 'modern_myth', 'Overall Effectiveness',           25, 40
  UNION ALL SELECT 'poetry', 'Relevance to Convention Theme',        20, 10
  UNION ALL SELECT 'poetry', 'Clarity of Expression',                20, 20
  UNION ALL SELECT 'poetry', 'Choice of Vocabulary',                 15, 30
  UNION ALL SELECT 'poetry', 'Relevance to Topic',                   15, 40
  UNION ALL SELECT 'poetry', 'Mechanics (Usage, Grammar, Spelling)', 10, 50
  UNION ALL SELECT 'poetry', 'Overall Effectiveness',                20, 60
  UNION ALL SELECT 'publicity', 'Impact',                            20, 10
  UNION ALL SELECT 'publicity', 'Originality/Creativity',            20, 20
  UNION ALL SELECT 'publicity', 'Quality of Content',                20, 30
  UNION ALL SELECT 'publicity', 'Appeal',                            20, 40
  UNION ALL SELECT 'publicity', 'Effort',                            20, 50
  UNION ALL SELECT 'digital_art',    'Overall impression',          100, 10
  UNION ALL SELECT 'slogan_english', 'Overall impression',          100, 10
  UNION ALL SELECT 'slogan_latin',   'Overall impression',          100, 10
) AS v
JOIN contests c ON c.key = v.key;

-- ---------------------------------------------------------------------------
-- contest_entries (replaces contest_submissions)
-- ---------------------------------------------------------------------------
-- contest_submissions was created in 004 as a placeholder and nothing ever
-- wrote to it. It could not hold a slogan (no file) or a Publicity portfolio
-- (no person), so it is replaced rather than altered. Lost-and-found photos,
-- which it also meant to cover, will want a table of their own.
--
-- NO FILE BYTES ARE STORED HERE. A file entry is a pointer into the AUTOMATED
-- Drive root, written by the Apps Script puppet. `body_text` holds a slogan, or
-- the plain text read out of a .docx or .txt so a judge can read it without a
-- download.
--
-- This root is entirely separate from the per-school packet folders holding
-- medical forms and waivers, which no code touches. Do not merge them.
DROP TABLE contest_submissions;

CREATE TABLE contest_entries (
  id                INTEGER PRIMARY KEY,
  item_id           INTEGER NOT NULL REFERENCES contests(item_id),
  school_id         INTEGER NOT NULL REFERENCES schools(id),
  -- NULL for a chapter entry (Publicity).
  person_id         INTEGER REFERENCES people(id),
  division          TEXT NOT NULL,
  title             TEXT,
  body_text         TEXT,
  translation       TEXT,
  link_url          TEXT,
  -- Publicity: which of the contest's facets this portfolio includes.
  facets            TEXT,
  word_count        INTEGER,
  word_count_source TEXT CHECK (word_count_source IN ('counted','declared')),
  drive_file_id     TEXT,
  drive_folder_id   TEXT,
  original_name     TEXT,
  mime_type         TEXT,
  size_bytes        INTEGER,
  submitted_by      INTEGER NOT NULL REFERENCES people(id),
  submitted_at      TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);
-- One entry per delegate per contest, and one per chapter for a chapter
-- contest. Partial indexes, because SQLite treats NULLs as distinct and a
-- plain UNIQUE (item_id, person_id) would let a chapter enter twice.
CREATE UNIQUE INDEX idx_contest_entries_person
  ON contest_entries (person_id, item_id) WHERE person_id IS NOT NULL;
CREATE UNIQUE INDEX idx_contest_entries_chapter
  ON contest_entries (school_id, item_id) WHERE person_id IS NULL;
-- The judging list and the results, one contest at a time.
CREATE INDEX idx_contest_entries_item   ON contest_entries (item_id, division);
-- A sponsor's view of their chapter's entries.
CREATE INDEX idx_contest_entries_school ON contest_entries (school_id, item_id);

-- ---------------------------------------------------------------------------
-- contest_scores
-- ---------------------------------------------------------------------------
-- One judge's score for one entry, or for one facet of it. `points_json` maps
-- criterion id to points; it is read whole and never queried into.
--
-- `penalty` is stored rather than recomputed, so a length rule changed after
-- judging does not silently rewrite scores already handed in.
--
-- A draft is a judge's work in progress and is left out of the results.
-- Replacing an entry deletes its scores: they were for different work.
CREATE TABLE contest_scores (
  id               INTEGER PRIMARY KEY,
  entry_id         INTEGER NOT NULL REFERENCES contest_entries(id) ON DELETE CASCADE,
  judge_person_id  INTEGER NOT NULL REFERENCES people(id),
  facet            TEXT NOT NULL DEFAULT '',
  points_json      TEXT NOT NULL,
  penalty          INTEGER NOT NULL DEFAULT 0,
  total            REAL NOT NULL,
  comment          TEXT,
  status           TEXT NOT NULL CHECK (status IN ('draft','submitted')),
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  UNIQUE (entry_id, judge_person_id, facet)
);
CREATE INDEX idx_contest_scores_judge ON contest_scores (judge_person_id);

-- ---------------------------------------------------------------------------
-- Settings
-- ---------------------------------------------------------------------------
-- The Convention Book publishes the pre-convention deadline. It starts at the
-- forms deadline -- end of 13 February 2027 in California, which is PST -- and
-- is changed from Settings like every other deadline.
--
-- The Drive root is the AUTOMATED folder the puppet files entries under, one
-- subfolder per contest and then per chapter. Not the packet folders.
-- Its ID is not a secret -- Drive still checks sharing -- but that folder must
-- be shared only with the chairs, never "anyone with the link". Change it in
-- Settings, not here: this value is only the starting point.
INSERT INTO settings (key, value, value_type, label, group_name, sort_order, updated_at) VALUES
  ('deadline.contests',   '2027-02-14T07:59:59Z', 'datetime', 'Pre-convention contests due',
   'Deadlines', 30, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('drive.contests_root', '1Oh8odNUmX_yCxCjIl1zwuHIdqx8VWof1', 'string', 'Drive folder ID for contest entries',
   'Operations', 60, strftime('%Y-%m-%dT%H:%M:%SZ','now'));
