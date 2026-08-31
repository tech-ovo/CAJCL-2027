-- 006_seed_catalog.sql -- the activity and adult-role catalog.
--
-- This is a SEED, not a definition. Everything here is editable from the admin
-- dashboard: categories, items, sub-options, eligibility by Latin level and
-- school level, selection minimums and maximums, and whether a rule blocks or
-- warns. Adding a ludus for 2028 must require no code and no migration.
--
-- NULL in eligible_latin_levels or eligible_school_levels means "no
-- restriction". NULL in min_latin_knowledge means "no Latin required".

-- ---------------------------------------------------------------------------
-- Categories
-- ---------------------------------------------------------------------------
INSERT INTO catalog_categories (key, name, description, applies_to, min_selections, max_selections, enforcement, sort_order, active) VALUES
  -- The one hard block on the delegate form. Between one and three tests.
  ('academic_testing', 'Academic Testing', 'Choose between one and three tests. Which tests you may take depends on your Latin level.', 'delegate', 1, 3, 'block', 10, 1),
  ('creative_arts',    'Academic and Creative Arts', NULL, 'delegate', NULL, NULL, 'none', 20, 1),
  ('graphic_arts',     'Graphic Arts',      'Entries are brought to convention. Some categories have sub-categories.', 'delegate', NULL, NULL, 'none', 30, 1),
  ('olympika',         'Olympika',          'Chess and Track are entered by individual delegates. Kickball, Fugepilam, and Ultimate Frisbee are chapter teams, entered by your sponsor or chapter leader.', 'delegate', NULL, NULL, 'none', 40, 1),
  ('ludi',             'Ludi',              NULL, 'delegate', NULL, NULL, 'none', 50, 1),
  -- Seeded inactive. The upload path is built but has no UI in the demo.
  ('preconvention',    'Pre-Convention Contests', 'Submitted online before convention.', 'delegate', NULL, NULL, 'none', 60, 0),
  -- A warning, not a block. An adult who ignores it can still submit.
  ('adult_roles',      'Volunteer Roles',   'Please sign up for at least two. There are no time blocks — tell us which events you are willing to run.', 'adult', 2, NULL, 'warn', 10, 1);

-- ---------------------------------------------------------------------------
-- Academic testing
-- ---------------------------------------------------------------------------
-- Grammar and Reading Comprehension mirror each other: 1 is MS-1/MS-2/HS-1,
-- 2 is MS-3/HS-2, 3 is HS-3 and above. Ineligible tests are shown DISABLED with
-- the requirement stated, never hidden -- a delegate who cannot find Grammar 2
-- assumes the site is broken.
INSERT INTO catalog_items (category_id, name, eligible_latin_levels, sort_order) VALUES
  -- OPEN TO EVERY LATIN LEVEL, because it does not test Latin. A first-year
  -- Latin student and a fourth-year one start Greek in the same place, so
  -- gating it by Latin level would exclude people for a reason that has
  -- nothing to do with the test. NULL is how "any level" is stored.
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Elementary Greek',             NULL,               5),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Classical Art',                NULL,              10),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Daily Life',                   NULL,              20),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Derivatives',                  NULL,              30),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Geography',                    NULL,              40),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Grammar 1',                    'MS-1,MS-2,HS-1',  50),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Grammar 2',                    'MS-3,HS-2',       60),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Grammar 3',                    'HS-3,HS-Adv',     70),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'History',                      NULL,              80),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Mottos/Quotes/Abbreviations',  NULL,              90),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Mythology',                    NULL,             100),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Pentathlon',                   NULL,             110),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Reading Comprehension 1',      'MS-1,MS-2,HS-1', 120),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Reading Comprehension 2',      'MS-3,HS-2',      130),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Reading Comprehension 3',      'HS-3,HS-Adv',    140),
  ((SELECT id FROM catalog_categories WHERE key='academic_testing'), 'Vocabulary',                   NULL,             150);

-- ---------------------------------------------------------------------------
-- Academic and creative arts
-- ---------------------------------------------------------------------------
INSERT INTO catalog_items (category_id, name, sort_order) VALUES
  ((SELECT id FROM catalog_categories WHERE key='creative_arts'), 'Costume',                 10),
  ((SELECT id FROM catalog_categories WHERE key='creative_arts'), 'Dramatic Interpretation', 20),
  ((SELECT id FROM catalog_categories WHERE key='creative_arts'), 'English Oratory',         30),
  ((SELECT id FROM catalog_categories WHERE key='creative_arts'), 'Essay',                   40),
  ((SELECT id FROM catalog_categories WHERE key='creative_arts'), 'Latin Oratory',           50),
  ((SELECT id FROM catalog_categories WHERE key='creative_arts'), 'Sight Latin Reading',     60);

-- ---------------------------------------------------------------------------
-- Graphic arts
-- ---------------------------------------------------------------------------
-- Thirteen items here, but FOURTEEN competition categories: Models is judged as
-- two separate categories, Large and Small, which is why it carries sub-options
-- rather than being one entry. docs/structure.md counts the categories a
-- delegate competes in (14); this table counts the things they tick (13). Both
-- are right. Do not "fix" one to match the other.
INSERT INTO catalog_items (category_id, name, max_sub_selections, sort_order) VALUES
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Cartoons',                        NULL,  10),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Charts/Maps',                     NULL,  20),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Drawing/Painting',                   8,  30),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Greeting Cards',                  NULL,  40),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Illustrated Quotes',              NULL,  50),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Impromptu Art',                   NULL,  60),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Jewelry',                         NULL,  70),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Models (Large & Small)',          NULL,  80),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Mosaics',                         NULL,  90),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Photography (Computer Enhanced)', NULL, 100),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Photography (Traditional)',       NULL, 110),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Pottery/Sculpture',               NULL, 120),
  ((SELECT id FROM catalog_categories WHERE key='graphic_arts'), 'Textile Arts',                    NULL, 130);

-- The eight Drawing/Painting media, alphabetical as they appear on the entry
-- form. max_sub_selections is 8, so a delegate may enter every medium -- the
-- limit is not a restriction, it is the count of what exists.
--
-- "Mixed Media" is defined as any combination of the other seven and NOTHING
-- else, however minor the addition. That rule is judged at convention, not
-- validated here: a delegate ticking Mixed Media plus others is making a
-- legitimate statement about their piece, and this form is not binding anyway.
INSERT INTO catalog_item_options (item_id, name, sort_order) VALUES
  ((SELECT id FROM catalog_items WHERE name='Drawing/Painting'), 'Acrylic or Oil',                                        10),
  ((SELECT id FROM catalog_items WHERE name='Drawing/Painting'), 'Black Pencil',                                          20),
  ((SELECT id FROM catalog_items WHERE name='Drawing/Painting'), 'Chalk or Pastel',                                       30),
  ((SELECT id FROM catalog_items WHERE name='Drawing/Painting'), 'Charcoal',                                              40),
  ((SELECT id FROM catalog_items WHERE name='Drawing/Painting'), 'Colored Pencil',                                        50),
  ((SELECT id FROM catalog_items WHERE name='Drawing/Painting'), 'Ink (colored or black, including block printing)',      60),
  ((SELECT id FROM catalog_items WHERE name='Drawing/Painting'), 'Watercolor (including water markers done with a brush)', 70),
  ((SELECT id FROM catalog_items WHERE name='Drawing/Painting'), 'Mixed Media (any combination of the other seven)',      80);

INSERT INTO catalog_item_options (item_id, name, sort_order) VALUES
  ((SELECT id FROM catalog_items WHERE name='Models (Large & Small)'), 'Large', 10),
  ((SELECT id FROM catalog_items WHERE name='Models (Large & Small)'), 'Small', 20);

-- ---------------------------------------------------------------------------
-- Olympika
-- ---------------------------------------------------------------------------
-- registration_scope='chapter' items never appear on an individual delegate's
-- activity sheet. They are entered once per school by a sponsor or by a
-- delegate the sponsor has promoted to chapter leader.
INSERT INTO catalog_items (category_id, name, registration_scope, sort_order) VALUES
  ((SELECT id FROM catalog_categories WHERE key='olympika'), 'Chess',                   'individual', 10),
  ((SELECT id FROM catalog_categories WHERE key='olympika'), 'Track',                   'individual', 20),
  ((SELECT id FROM catalog_categories WHERE key='olympika'), 'Fugepilam (Dodgeball)',   'chapter',    30),
  ((SELECT id FROM catalog_categories WHERE key='olympika'), 'Kickball',                'chapter',    40),
  ((SELECT id FROM catalog_categories WHERE key='olympika'), 'Ultimate Frisbee',        'chapter',    50);

INSERT INTO catalog_item_options (item_id, name, sort_order) VALUES
  ((SELECT id FROM catalog_items WHERE name='Track'), '100m', 10),
  ((SELECT id FROM catalog_items WHERE name='Track'), '200m', 20),
  ((SELECT id FROM catalog_items WHERE name='Track'), '400m', 30);

-- ---------------------------------------------------------------------------
-- Ludi
-- ---------------------------------------------------------------------------
INSERT INTO catalog_items (category_id, name, sort_order) VALUES
  ((SELECT id FROM catalog_categories WHERE key='ludi'), 'Edible Mosaics',                 10),
  ((SELECT id FROM catalog_categories WHERE key='ludi'), 'Open Certamen',                  20),
  ((SELECT id FROM catalog_categories WHERE key='ludi'), 'Pandora''s Breakout Box',        30),
  ((SELECT id FROM catalog_categories WHERE key='ludi'), 'Percy Jackson Kahoot',           40),
  ((SELECT id FROM catalog_categories WHERE key='ludi'), 'Project Runway',                 50),
  ((SELECT id FROM catalog_categories WHERE key='ludi'), 'Roman Rap Battle',               60),
  ((SELECT id FROM catalog_categories WHERE key='ludi'), 'Roman Speed Dating',             70),
  ((SELECT id FROM catalog_categories WHERE key='ludi'), 'Scavenger Hunt (Goose Chase)',   80),
  ((SELECT id FROM catalog_categories WHERE key='ludi'), 'Spelling Bee',                   90),
  ((SELECT id FROM catalog_categories WHERE key='ludi'), 'STEM Challenge',                100),
  ((SELECT id FROM catalog_categories WHERE key='ludi'), 'That''s Entertainment',         110);

-- Watching it and being in it are different answers, and the Activities chair
-- needs both: auditions are a schedule with slots, the audience is a room with
-- seats. One tick answered neither. Two sub-choices, and somebody auditioning
-- is in the audience for everyone else, so both may be picked.
UPDATE catalog_items SET max_sub_selections = 2
WHERE name = 'That''s Entertainment';

INSERT INTO catalog_item_options (item_id, name, sort_order)
SELECT id, 'Auditioning', 10 FROM catalog_items WHERE name = 'That''s Entertainment';
INSERT INTO catalog_item_options (item_id, name, sort_order)
SELECT id, 'Watching',    20 FROM catalog_items WHERE name = 'That''s Entertainment';

-- ---------------------------------------------------------------------------
-- Pre-convention contests (seeded, inactive, no UI in the demo)
-- ---------------------------------------------------------------------------
INSERT INTO catalog_items (category_id, name, sort_order, active) VALUES
  ((SELECT id FROM catalog_categories WHERE key='preconvention'), 'Modern Myth',      10, 0),
  ((SELECT id FROM catalog_categories WHERE key='preconvention'), 'Poetry',           20, 0),
  ((SELECT id FROM catalog_categories WHERE key='preconvention'), 'Slogan (English)', 30, 0),
  ((SELECT id FROM catalog_categories WHERE key='preconvention'), 'Slogan (Latin)',   40, 0);

-- ---------------------------------------------------------------------------
-- Adult volunteer roles
-- ---------------------------------------------------------------------------
-- Every role below needs either nothing or advanced Latin, but the column
-- carries all four levels so a future chair can mark a role as needing
-- intermediate Latin from the dashboard without a migration. An adult below a
-- role's minimum sees it disabled with the requirement stated -- the same
-- treatment as an ineligible test, for the same reason.
INSERT INTO catalog_items (category_id, name, min_latin_knowledge, sort_order) VALUES
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'Wherever needed!',              NULL,        10),
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'Certamen Reader',               'advanced',  20),
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'Certamen Scorer/Timer',         NULL,        30),
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'Graphic Arts Judge',            NULL,        40),
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'Olympika Volunteer',            NULL,        50),
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'Ludi Volunteer',                NULL,        60),
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'Latin Oratory Judge',           'advanced',  70),
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'Sight Latin Reading Judge',     'advanced',  80),
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'Essay Reading Judge',           NULL,        90),
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'Costume Judge',                 NULL,       100),
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'English Oratory Judge',         NULL,       110),
  ((SELECT id FROM catalog_categories WHERE key='adult_roles'), 'Dramatic Interpretation Judge', 'advanced', 120);
