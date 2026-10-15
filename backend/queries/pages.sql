-- Long text pages written in Google Docs (migration 015).
--
-- site_pages is a dozen rows and is read whole.

-- name: pages.all
SELECT id, slug, title, nav_label, show_in_nav, sort_order, doc_url, doc_id,
       html_file_id, html_url, synced_at, sync_error, created_at, updated_at
FROM site_pages
ORDER BY sort_order, title COLLATE NOCASE;

-- name: pages.published
-- What the site build reads: only pages that have been converted at least once.
SELECT slug, title, nav_label, show_in_nav, sort_order, html_url, synced_at
FROM site_pages
WHERE html_url <> ''
ORDER BY sort_order, title COLLATE NOCASE;

-- name: pages.get
SELECT * FROM site_pages WHERE id = ?;

-- name: pages.create
INSERT INTO site_pages (slug, title, nav_label, show_in_nav, sort_order,
                        doc_url, doc_id, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);

-- name: pages.update
UPDATE site_pages
SET slug = ?, title = ?, nav_label = ?, show_in_nav = ?, sort_order = ?,
    doc_url = ?, doc_id = ?, updated_at = ?
WHERE id = ?;

-- name: pages.reset_conversion
-- The Doc changed, so the converted copy belongs to something else.
UPDATE site_pages
SET html_file_id = '', html_url = '', synced_at = NULL, sync_error = ''
WHERE id = ?;

-- name: pages.synced
UPDATE site_pages
SET html_file_id = ?, html_url = ?, synced_at = ?, sync_error = ''
WHERE id = ?;

-- name: pages.sync_failed
UPDATE site_pages SET sync_error = ? WHERE id = ?;

-- name: pages.delete
DELETE FROM site_pages WHERE id = ?;
