# Text Pages from Google Docs — Operating Guide

Long, mostly-text pages (hotel list, academic resources, registration
instructions, the white book, the convention book, …) are written in **Google
Docs** and published as ordinary pages on the site. Nobody uploads HTML or
Markdown: an administrator pastes a Doc's link **once**; after that, editing the
Doc and pressing **Publish** is all it takes.

Who may use it: the **registration** and **academics** chairs, and the admin (nav **Site pages**, `#/site-pages`).
Everyone, signed in or not, can read the published pages.

## For the person adding or updating a page

1. Write the page in a Google Doc. Use real headings (Heading 1/2/3), lists,
   links, tables and pictures. Fonts, colours and sizes are **not** carried
   over: the site supplies the look. Pictures are (see *Pictures* below). Do not
   repeat the page title as the first line; the page already shows it.
2. Share the Doc with the CAJCL Drive account (the address is shown in the
   error if you forget). **Viewer** is enough.
3. **Site pages → Add a page:** a title and the Doc's link. Leave *Address*
   empty to make it from the title (`Hotel list` → `/p/hotel-list.html`).
   *Show in the menu* puts a link in the nav bar; every page is also listed on
   **Resources**.
4. Press **Publish the site.** It reads the Docs one at a time (the screen shows
   which), reports each one that failed, then says the site is rebuilding. Watch the build (link on the
   screen); a green tick means it is live, usually within a few minutes.
5. To change the text later: edit the Doc, press **Publish** again. The link
   never changes.

Removing a page takes it off the site at the next Publish and moves the Drive
copy to the Drive trash. The Google Doc is never touched.

## How it works

```
Doc ──► Publish: one request per page ──► Apps Script `convert` ──► page-<id>.html in Drive
          (Modal stores the link in site_pages)          (pictures embedded; public link,
                │                                         same file every time)
                └──► then /admin/pages/rebuild ──► GitHub Actions workflow_dispatch (deploy.yml, site_only=true)
                          └─ scripts/build_pages.py:  GET /public/pages
                                download each link ► htmlclean ► /p/<slug>.html + /p/img/* + pages.json
                                └─► GitHub Pages
```

* **Apps Script** (`apps-script/Code.gs`, op `convert`) exports the Doc as a zip
  (HTML plus its `images/`), turns bold/italic/underline/super/subscript into
  plain tags, drops every style and attribute (only a link's `href`, a cell's
  `colspan`/`rowspan` and a picture's `alt` stay), embeds each picture in the
  HTML as a `data:` image, unwraps Google's `google.com/url?q=` link redirects, and
  rewrites **one file per page** in `<drive.contests_root>/Site Pages/`, shared
  "anyone with the link". Because the same file is rewritten, its link is stable.
* **Modal** stores only that link (`site_pages.html_url`), not the text.
* **The build** downloads each link and cleans it **again** with the same
  allowlist in Python (`backend/lib/htmlclean.py`): the Drive copy is not
  trusted, so nothing outside the allowlist can reach the public site. It then
  saves each picture as a file under `/p/img/` (named by a hash of its content,
  so a repeated picture is one file) after checking it really is a PNG, JPEG or
  GIF and removing any location/camera data. A parity
  test keeps the two cleaners in step.
* **The frame** (masthead, menu, footer, theme script) comes from
  `frontend/page.template.html` and the built `index.html`, so these pages
  cannot drift from the rest of the site. Generated files (`frontend/public/p/`,
  `pages.json`) are not committed.

## When something goes wrong

| Symptom | Cause / fix |
| :--- | :--- |
| Status "Failed", message "Share the Doc with …@gmail.com" | The Doc is not shared with the Drive account. Share it (Viewer) and Publish. |
| "Drive did not answer" on a page with many pictures | Reading it took longer than 55 seconds. Shrink the pictures in the Doc and Publish again. |
| Status "Out of date" | The last conversion failed; the previous copy is still on the site. The message says why. |
| "That link is not a Google Doc" | A Sheet, Slides or ordinary Drive file was pasted. Only Docs work. |
| "The site rebuild is not switched on yet" | `GITHUB_DISPATCH_TOKEN` is missing from the Modal secret. Docs were converted; run **Actions → Deploy → Run workflow** (tick *site only*) by hand. See `DEPLOY.md` Phase 5b. |
| "GitHub refused to start the rebuild (401/403/404)" | The token expired or lacks *Actions: read and write* on this repository. Make a new one. |
| The Deploy run fails in *Build the text pages* | A page could not be fetched or came back empty (the log names it). A failed build keeps the previous site up. Usually the Drive file is not shared with "anyone with the link", or the Doc is empty. |
| Every deploy (even code pushes) fails at *Build the text pages* | The API is down or the Drive copy was deleted. Fix it, or remove the page on **Site pages**. |

## Limits and decisions

* The site menu links to these pages are plain links to separate documents. A
  signed-in person reading `/p/…` sees the public menu (Welcome, Schedule, the
  pages, Resources, Sign in); their own menu returns on the main site.
## Pictures

Insert them in the Doc as normal; give each one **alt text** (right-click →
*Alt text*) so it can be described to a screen reader. PNG, JPEG and GIF work.
Limits: 4 MB per picture, 40 per page, 16 MB of pictures per page (extra ones
are left out; a picture that is not really an image, or is over 4 MB, fails the
build with the page's name). Keep photos modest: they are shown at the page's
width, and big ones make the page slow on a phone. Drawings, text boxes and
Google Charts are not pictures and do not come across.
* Pages are public. Never put names, phone numbers or other registrant data in
  one (`PRIVACY.md` §3).
* Menu order is the page's *Order* number (smaller first; new pages go last).
  There is no drag-and-drop.
