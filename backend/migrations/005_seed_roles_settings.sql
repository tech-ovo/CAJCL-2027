-- 005_seed_roles_settings.sql -- system roles, their scopes, the settings a
-- convention is operated from, and the prose an admin can reword.
--
-- Nothing in this file is a fact about the 72nd convention that a future
-- commissioner cannot change from the dashboard. If you find yourself wanting
-- to edit this file to run the 73rd convention, that is a bug in the dashboard.

-- ---------------------------------------------------------------------------
-- System roles
-- ---------------------------------------------------------------------------
-- is_system = 1 means the role cannot be deleted from the dashboard. An admin
-- with '*' may still create additional roles with any combination of scopes,
-- which is how a future chair gets provisioned without a deploy.
INSERT INTO roles (key, name, description, is_system, created_at) VALUES
  ('admin',              'Administrator',      'Everything: announcements, audit log, exports, roles, impersonation, Drive links.', 1, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('registration_chair', 'Registration Chair', 'Rosters, schools, payments, check-in.',                                              1, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('academics_chair',    'Academics Chair',    'Tests and activity registration, contests, grading, Certamen.',                      1, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('awards_chair',       'Awards Chair',       'Score entry, test printing, tabulation.',                                            1, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('sponsor',            'Sponsor',            'Manages one chapter''s roster, packet, and invoice.',                                1, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('delegate',           'Delegate',           'Completes their own activity sheet.',                                                1, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('chapter_leader',     'Chapter Leader',     'A delegate a sponsor has promoted to manage chapter team entries.',                  1, strftime('%Y-%m-%dT%H:%M:%SZ','now'));

-- The only path from a person to a scope runs through here.
INSERT INTO role_scopes (role_id, scope)
SELECT id, '*'            FROM roles WHERE key = 'admin';
INSERT INTO role_scopes (role_id, scope)
SELECT id, 'registration' FROM roles WHERE key = 'registration_chair';
INSERT INTO role_scopes (role_id, scope)
SELECT id, 'academics'    FROM roles WHERE key = 'academics_chair';
INSERT INTO role_scopes (role_id, scope)
SELECT id, 'awards'       FROM roles WHERE key = 'awards_chair';
INSERT INTO role_scopes (role_id, scope)
SELECT id, 'sponsor'      FROM roles WHERE key = 'sponsor';
INSERT INTO role_scopes (role_id, scope)
SELECT id, 'delegate'     FROM roles WHERE key = 'delegate';
INSERT INTO role_scopes (role_id, scope)
SELECT id, 'chapter'      FROM roles WHERE key = 'chapter_leader';

-- A sponsor manages chapter team entries too, so the sponsor role carries the
-- chapter scope directly. chapter_leader exists to give that same scope to a
-- student -- as a role on their existing account, never as a second code.
INSERT INTO role_scopes (role_id, scope)
SELECT id, 'chapter'      FROM roles WHERE key = 'sponsor';

-- ---------------------------------------------------------------------------
-- Settings
-- ---------------------------------------------------------------------------
-- DEADLINE STORAGE IS A TRAP. These two are stored as UTC but mean "end of day
-- in California". February 13, 2027 falls in PST (UTC-8), so end of that day is
-- 2027-02-14T07:59:59Z. If a future commissioner moves a deadline into a DST
-- month the offset becomes -7 and a hand-typed string will be an hour wrong in
-- the direction that locks people out early. The dashboard takes a wall-clock
-- date and computes this; nobody hand-types the UTC string. See
-- backend/lib/clock.py.
INSERT INTO settings (key, value, value_type, label, group_name, sort_order, updated_at) VALUES
  ('convention.year',          '2027',                        'string',   'Convention year',            'Convention',  10, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('convention.ordinal',       '72nd',                        'string',   'Ordinal',                    'Convention',  20, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('convention.start_date',    '2027-03-12',                  'string',   'First day',                  'Convention',  30, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('convention.end_date',      '2027-03-13',                  'string',   'Last day',                   'Convention',  40, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('convention.venue_name',    'University High School',      'string',   'Host school',                'Convention',  50, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('convention.venue_address', '4771 Campus Drive, Irvine, CA 92612', 'string', 'Venue address',         'Convention',  60, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  -- Macrons here are Latin Extended-A. The font subset must include that block
  -- or this line renders as tofu boxes in the masthead. scripts/check_fonts.py
  -- fails the build on exactly this string.
  ('convention.theme_latin',   'aequam mementō rēbus in arduīs servāre mentem', 'string', 'Theme (Latin)',       'Convention',  70, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('convention.theme_english', 'Remember to keep an even mind in adversity',    'string', 'Theme (translation)', 'Convention',  80, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('convention.theme_citation','Horace, Odes II.3.1–2',       'string',   'Theme (citation)',           'Convention',  90, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('convention.contact_email', 'state@uhsjcl.org',            'string',   'Contact address',            'Convention', 100, strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  ('fee.delegate_cents',       '14000',                       'cents',    'Fee per delegate',           'Fees',        10, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('fee.extra_adult_cents',    '7500',                        'cents',    'Fee per chargeable adult',   'Fees',        20, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('fee.adult_ratio',          '10',                          'int',      'Delegates per free adult',   'Fees',        30, strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  ('deadline.forms_lock',      '2027-02-14T07:59:59Z',        'datetime', 'Forms lock',                 'Deadlines',   10, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('deadline.payment',         '2027-02-14T07:59:59Z',        'datetime', 'Payment due',                'Deadlines',   20, strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  ('invoice.remit_to',         'University High School JCL c/o Mark Michalak', 'string', 'Remit to',     'Invoice',     10, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('invoice.remit_address',    'University High School, 4771 Campus Drive, Irvine, CA 92612', 'string', 'Remit address', 'Invoice', 20, strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  -- The database is the source of truth for desired warmth, not the Modal API.
  -- A cron reconciles reality to this every five minutes, because DEPLOYING THE
  -- APP RESETS THE AUTOSCALER to whatever is written in code -- so a one-shot
  -- button press would be silently undone by the first hotfix at convention.
  ('ops.warm_until',                  '',      'datetime', 'Keep containers warm until', 'Operations', 10, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('ops.autoexport_enabled',          '0',     'bool',     'Automatic export enabled',   'Operations', 20, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('ops.autoexport_until',            '',      'datetime', 'Automatic export shuts off',  'Operations', 30, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  ('ops.autoexport_interval_minutes', '10',    'int',      'Automatic export interval',   'Operations', 40, strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  -- Drives the "Demonstration data" marker in the site header. The demo is
  -- projected in a room full of teachers; nobody should have to wonder whether
  -- the names on screen belong to real children. Seeding sets this to 1.
  ('ops.demo_mode',                   '0',     'bool',     'Demonstration data marker',   'Operations', 50, strftime('%Y-%m-%dT%H:%M:%SZ','now'));

-- ---------------------------------------------------------------------------
-- Documents
-- ---------------------------------------------------------------------------
-- Prose that gets printed or displayed, kept out of templates so rewording it
-- never requires a deploy. The packet instructions above all: they are what a
-- confused delegate reads at a kitchen table in February.
INSERT INTO documents (key, title, body_md, updated_at) VALUES
  ('packet_instructions', 'How to finish your registration',
   'Your access code is printed above. Scan the square code with your phone camera, or type the code into **state.uhsjcl.org**.

**Keep this sheet.** Anyone holding it can sign in as you. If you lose it, ask your sponsor for a new code — the old one stops working immediately.

Once you are signed in, complete your Student Activity Sheet. It asks for your grade, your Latin level, your meal preference, and the events you would like to enter. None of your event choices are binding; they let the Academics, Activities, and Athletics chairs plan.

Three forms are **not** online and must be signed on paper: the student waiver, the student medical form, and — for adults — the adult medical form. Sign them by hand, with a parent or guardian signature where the form asks for one, and give them to your sponsor.

If you have no access to a phone or computer at all, your sponsor can print a paper copy of this form and type your answers in for you. Please avoid this if you can: it is slow, and mistakes are harder to catch.',
   strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  ('packet_cover', 'Sponsor packet cover',
   'This packet contains one sheet per attendee. Each sheet carries that person''s access code, so hand each sheet only to the person named on it.

To finish your chapter''s registration:

1. Give every attendee their sheet.
2. Collect the signed waivers and medical forms.
3. Mark each form received in your roster on the site.
4. Scan the whole packet into your chapter''s Drive folder.
5. Mail the paper and your check to the address on the invoice.',
   strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  -- The last page of the packet. The three paper forms themselves are printed
  -- from the files the convention has always used and are not generated here --
  -- this page tells a sponsor which ones to expect, who signs each, and where
  -- they go. Medical documents never touch this system, by design.
  ('packet_paper_forms', 'Required paper forms',
   'These three forms are **not** completed online. Print them, sign them by hand, and return them to your sponsor.

- **Student Waiver** — every delegate. Requires a parent or guardian signature.
- **Student Medical Form** — every delegate. Requires a parent or guardian signature.
- **Adult Medical Form** — every adult attending, including sponsors and chaperones.

Your sponsor collects all three, marks them received in the roster, scans the packet into your chapter''s Drive folder, and mails the paper with the chapter''s check.

Legibility and signatures are checked at Friday check-in, so write clearly and do not leave a field blank.',
   strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  ('invoice_terms', 'Invoice terms',
   'Please make checks payable to **University High School JCL**. Write your chapter name on the memo line so we can match the payment to your invoice.

If your delegate or adult count changes before the deadline, the amount due changes with it — sign in to the site for the current figure rather than working from a printed copy.',
   strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  ('invoice_exempt_note', 'Invoice note for non-billed chapters',
   'This chapter is not billed for the state convention, so there is nothing to pay and no check to send. Your registration is complete once your attendees have finished their forms and returned their paper waivers and medical forms.',
   strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  ('welcome_body', 'Welcome page body',
   'The California Junior Classical League gathers each spring for two days of Certamen, competition, and ceremony. The 72nd State Convention will be held at University High School in Irvine.

Registration runs through your chapter''s sponsor. If you are a delegate, your sponsor will give you a sheet with your access code on it.',
   strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  ('activity_sheet_intro', 'Activity sheet introduction',
   'Choose the events you would like to enter. **None of these choices are binding** — they exist so the Academics, Activities, and Athletics chairs know how many students to prepare materials for. You can change your answers until the deadline.',
   strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  ('adult_sheet_intro', 'Adult sheet introduction',
   'Tell us which events you are willing to help run. There are no time blocks to choose — chairs build the schedule around who is available, and the notes field below is where to explain anything they should know.',
   strftime('%Y-%m-%dT%H:%M:%SZ','now'));
