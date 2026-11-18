-- 015_site_pages.sql -- long text pages written in Google Docs.
--
-- A hotel list, the white book, registration instructions: text a board member
-- already keeps in a Google Doc. An administrator pastes the Doc's link once.
-- Apps Script turns the Doc into a cleaned HTML file in Drive (same file every
-- time, so its link never changes); the database remembers that link; and the
-- site build (scripts/build_pages.py) downloads each one and writes it out as a
-- static page, /p/<slug>.html, inside the site's own frame.
--
-- Nothing here holds the page's TEXT. The Doc is the source and Drive holds the
-- converted copy; losing this table loses the list of pages, not the writing.
--
--   slug          the address: /p/<slug>.html. Lower-case letters, digits and
--                 hyphens. Unique ignoring case.
--   title         the page's heading and its <title>.
--   nav_label     the shorter name used in the navigation, or empty to use
--                 the title.
--   show_in_nav   0 = reachable by its address and from the Resources page
--                 only; 1 = also a link in the navigation bar.
--   doc_url       what the administrator pasted, kept so it can be shown and
--                 corrected. doc_id is the part Apps Script needs.
--   html_file_id  the converted file in Drive, or empty before the first
--                 successful conversion. html_url is its public download link,
--                 which is what the build fetches.
--   synced_at     when the last conversion SUCCEEDED. sync_error is what went
--                 wrong the last time one did not (empty after a success).
--                 A page with no html_url is not published at all.
CREATE TABLE site_pages (
  id           INTEGER PRIMARY KEY,
  slug         TEXT NOT NULL,
  title        TEXT NOT NULL,
  nav_label    TEXT NOT NULL DEFAULT '',
  show_in_nav  INTEGER NOT NULL DEFAULT 1 CHECK (show_in_nav IN (0, 1)),
  sort_order   INTEGER NOT NULL DEFAULT 0,
  doc_url      TEXT NOT NULL,
  doc_id       TEXT NOT NULL,
  html_file_id TEXT NOT NULL DEFAULT '',
  html_url     TEXT NOT NULL DEFAULT '',
  synced_at    TEXT,
  sync_error   TEXT NOT NULL DEFAULT '',
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_site_pages_slug ON site_pages (slug COLLATE NOCASE);
