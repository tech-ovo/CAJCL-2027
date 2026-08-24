-- The convention is hosted jointly by two schools, but happens on one campus.
--
-- `convention.venue_name` is the place events actually happen, and everything
-- that gives directions uses it. That is not the same fact as who is running
-- the convention, and conflating the two would either drop Woodbridge from the
-- credit or send delegates to the wrong campus. So: two settings.
--
-- Editable from Settings like every other line here, because the pair of host
-- schools changes every year and the next commissioner should not need a
-- migration to say so.

INSERT INTO settings (key, value, value_type, label, group_name, sort_order, updated_at)
VALUES
  ('convention.hosts',
   'Jointly hosted by University High School and Woodbridge High School',
   'string', 'Hosted by', 'Convention', 55,
   strftime('%Y-%m-%dT%H:%M:%SZ','now'))
ON CONFLICT (key) DO NOTHING;
