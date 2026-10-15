"""Long text pages written in Google Docs (migration 015).

The endpoints in api.py do the authorization and the database; this module
holds the rules, so the tests can reach them without HTTP:

    what a page may be                      check_page
    which Doc a pasted link points at       doc_id_from
    converting a Doc into the Drive copy    convert
    asking GitHub to rebuild the site       request_rebuild
    a page as the admin page / site build   view, public_view

THE FLOW
    1. A board member writes the page in Google Docs.
    2. An administrator pastes its link on the Site pages screen (once).
    3. "Publish" asks the Drive puppet (apps-script/Code.gs, op `convert`) to
       turn each Doc into a cleaned HTML file in Drive, pictures embedded, and
       share it with anyone who has the link. The screen sends ONE request per
       page, so none runs past the web function's 60 seconds however many
       pages or pictures there are. The file is rewritten in place, so its
       link is stable; the database stores that link and nothing else about
       the text.
    4. When every page has been tried, the screen asks GitHub to rebuild the
       site. The build (scripts/build_pages.py) reads /public/pages, downloads
       each file, cleans it AGAIN with htmlclean, saves its pictures as files,
       and writes /p/<slug>.html.

A conversion that fails leaves the previous Drive copy and link in place: the
page keeps showing the last good version.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from . import drive
from .catalog import ValidationError

MAX_TITLE = 120
MAX_NAME = 40
MAX_SLUG = 60
FOLDER_NAME = "Site Pages"

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# /document/d/<id>/edit, /document/u/1/d/<id>/..., and the id= form of an
# older share link. Docs ids are 25+ characters of letters, digits, - and _.
DOC_LINK = re.compile(
    r"^https://docs\.google\.com/document/(?:u/\d+/)?d/([A-Za-z0-9_-]{20,})(?:[/?#].*)?$")
OLD_LINK = re.compile(r"^https://docs\.google\.com/open\?id=([A-Za-z0-9_-]{20,})(?:[&#].*)?$")

# Pages the site already has or might: an address here would shadow them.
RESERVED = {"index", "404", "new"}


def doc_id_from(link: str) -> str | None:
    link = (link or "").strip()
    for pattern in (DOC_LINK, OLD_LINK):
        match = pattern.match(link)
        if match:
            return match.group(1)
    return None


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:MAX_SLUG].strip("-")


def check_page(payload: dict, current: dict | None = None) -> dict:
    """The columns for a new or edited page. A field left out of an edit keeps
    its current value; a new page's address defaults to its title."""
    current = current or {}
    errors = []

    title = " ".join(str(payload.get("title", current.get("title")) or "").split())
    if not title:
        errors.append("Give the page a title, like “Hotel list”.")
    elif len(title) > MAX_TITLE:
        errors.append(f"Keep the title under {MAX_TITLE} characters.")

    slug = str(payload.get("slug", current.get("slug")) or "").strip().lower()
    if not slug and title:
        slug = slugify(title)
    if not slug:
        errors.append("Give the page an address, like “hotel-list”.")
    elif len(slug) > MAX_SLUG or not SLUG.match(slug):
        errors.append("The address can only use lower-case letters, numbers "
                      "and single hyphens, like “hotel-list”.")
    elif slug in RESERVED:
        errors.append(f"“{slug}” is reserved. Choose a different address.")

    nav_label = " ".join(str(payload.get("nav_label", current.get("nav_label")) or "").split())
    if len(nav_label) > MAX_NAME:
        errors.append(f"Keep the menu name under {MAX_NAME} characters.")

    show = payload.get("show_in_nav", current.get("show_in_nav", True))
    show_in_nav = 1 if (show in (True, 1, "1", "true")) else 0

    sort_order = current.get("sort_order", 0)
    if "sort_order" in payload:
        try:
            sort_order = int(payload["sort_order"])
        except (TypeError, ValueError):
            errors.append("The order must be a whole number.")

    doc_url = str(payload.get("doc_url", current.get("doc_url")) or "").strip()
    doc_id = current.get("doc_id", "")
    if not doc_url:
        errors.append("Paste the link to the Google Doc.")
    elif doc_url != current.get("doc_url"):
        doc_id = doc_id_from(doc_url) or ""
        if not doc_id:
            errors.append(
                "That does not look like a link to a Google Doc. Open the Doc, "
                "click Share, and copy the link. It starts with "
                "https://docs.google.com/document/d/ — a Sheet, a Slide deck or "
                "a plain Drive file will not work.")

    if errors:
        raise ValidationError(errors)
    return {"slug": slug, "title": title, "nav_label": nav_label,
            "show_in_nav": show_in_nav, "sort_order": sort_order,
            "doc_url": doc_url, "doc_id": doc_id}


def drive_name(page: dict) -> str:
    """Named by id, not slug, so changing the address does not leave an
    orphaned file behind and start a second one."""
    return f"page-{page['id']}.html"


def view(row) -> dict:
    """A page as the Site pages screen receives it."""
    return {"id": row["id"], "slug": row["slug"], "title": row["title"],
            "nav_label": row["nav_label"], "show_in_nav": bool(row["show_in_nav"]),
            "sort_order": row["sort_order"], "doc_url": row["doc_url"],
            "converted": bool(row["html_url"]), "synced_at": row["synced_at"],
            "sync_error": row["sync_error"],
            "path": f"/p/{row['slug']}.html"}


def public_view(row) -> dict:
    """What the site build needs, and nothing it does not."""
    return {"slug": row["slug"], "title": row["title"],
            "nav_label": row["nav_label"] or row["title"],
            "show_in_nav": bool(row["show_in_nav"]), "html_url": row["html_url"],
            "synced_at": row["synced_at"]}


# ---------------------------------------------------------------------------
# Converting a Doc
# ---------------------------------------------------------------------------

def convert(page: dict, folder_id: str) -> tuple[str, str]:
    """(Drive file id, public download URL). Raises drive.DriveUnavailable with
    a sentence the administrator can read."""
    return drive.client("Page publishing").convert(
        folder_id, drive_name(page), page["doc_id"])


def convert_one(page: dict, folder_id: str) -> dict:
    """Convert one page. {"ok", "file_id", "url", "error"}; never raises, so one
    bad Doc is a message on its row, not a failed request."""
    try:
        file_id, url = convert(page, folder_id)
        return {"ok": True, "file_id": file_id, "url": url, "error": ""}
    except drive.DriveUnavailable as error:
        return {"ok": False, "file_id": "", "url": "", "error": str(error)}
    except Exception as error:      # a bug must not look like a Drive outage
        return {"ok": False, "file_id": "", "url": "",
                "error": f"Unexpected error: {error}"}


def folder_for_pages(store: drive.Drive, configured: str) -> str:
    """The "Site Pages" folder under the automated Drive root."""
    root = drive.root_folder(configured, "Page publishing")
    return store.mkdir(root, FOLDER_NAME)


# ---------------------------------------------------------------------------
# Rebuilding the site
# ---------------------------------------------------------------------------

class RebuildUnavailable(Exception):
    """GitHub could not be asked, or is not configured. Nothing was started."""


def _github_settings() -> dict:
    return {
        "token": os.environ.get("GITHUB_DISPATCH_TOKEN", ""),
        "repo": os.environ.get("GITHUB_REPO", "tech-ovo/CAJCL-2027"),
        "workflow": os.environ.get("GITHUB_WORKFLOW", "deploy.yml"),
        "ref": os.environ.get("GITHUB_REF_NAME", "main"),
    }


def actions_url() -> str:
    cfg = _github_settings()
    return f"https://github.com/{cfg['repo']}/actions/workflows/{cfg['workflow']}"


def _post_dispatch() -> None:
    cfg = _github_settings()
    if not cfg["token"]:
        raise RebuildUnavailable(
            "The site rebuild is not switched on yet: no GitHub token is set. "
            "Your pages were converted, but the site has not changed. Please "
            "tell state@uhsjcl.org.")
    url = (f"https://api.github.com/repos/{cfg['repo']}/actions/workflows/"
           f"{cfg['workflow']}/dispatches")
    # site_only: rebuild and publish the site; skip the API redeploy.
    body = json.dumps({"ref": cfg["ref"], "inputs": {"site_only": "true"}}).encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {cfg['token']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "cajcl-2027",
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status not in (200, 201, 204):
                raise RebuildUnavailable(f"GitHub answered {response.status}.")
    except urllib.error.HTTPError as error:
        raise RebuildUnavailable(
            f"GitHub refused to start the rebuild ({error.code}). Check that the "
            "token is still valid and may run workflows.") from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise RebuildUnavailable(f"GitHub did not answer ({error}).") from None


_dispatcher = None


def use_dispatcher(fn) -> None:
    """Install a stand-in for the GitHub call (tests), or None for the real one."""
    global _dispatcher
    _dispatcher = fn


def request_rebuild() -> str:
    """Start the site rebuild. Returns the URL where its progress can be seen."""
    (_dispatcher or _post_dispatch)()
    return actions_url()
