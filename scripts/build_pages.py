"""Build the long text pages written in Google Docs into static HTML.

    python scripts/build_pages.py                      # the Modal API in config.js
    python scripts/build_pages.py --api http://127.0.0.1:8000

WHAT IT DOES
    1. Asks the API for the published pages (GET /public/pages): slug, title,
       and the public Drive link of each one's converted HTML.
    2. Downloads each file, cleans it AGAIN with backend/lib/htmlclean.py (the
       Drive copy is not trusted: whatever Apps Script did or did not strip,
       only the allowlist reaches the site), and puts it in the site's frame
       (frontend/page.template.html).
    3. Writes frontend/public/p/<slug>.html for each page, and
       frontend/public/pages.json -- the list the site's navigation and the
       Resources page read.

    Run it AFTER scripts/build_snapshot.py, because the masthead, footer and
    theme script are copied from the built index.html.

WHEN IT FAILS, THE BUILD FAILS. A page that cannot be fetched is not quietly
left out: that would delete a live page from the site. The previous deployment
stays up and the log says which page and why. Retried three times first.

Both outputs are generated, never committed (.gitignore).
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import check_csp_hash  # noqa: E402
from backend.lib import htmlclean  # noqa: E402

PUBLIC = ROOT / "frontend" / "public"
TEMPLATE = ROOT / "frontend" / "page.template.html"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RETRIES = 3


class BuildError(Exception):
    pass


def http_get(url: str) -> str:
    """The body of a URL as text, retried; raises BuildError after the last try."""
    last = None
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(2 * attempt)
        request = urllib.request.Request(url, headers={"User-Agent": "cajcl-2027-build"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            last = error
    raise BuildError(f"{url} did not answer after {RETRIES} tries ({last})")


def api_base() -> str:
    config = (PUBLIC / "config.js").read_text(encoding="utf-8")
    match = re.search(r'"(https://[^"]+\.modal\.run)"', config)
    if not match:
        raise BuildError("could not find the API address in frontend/public/config.js; "
                         "pass --api")
    return match.group(1)


def snapshot(index_html: str, key: str, default: str) -> str:
    match = re.search(rf'data-snapshot="{key}"[^>]*>(.*?)</', index_html, re.S)
    return match.group(1).strip() if match and match.group(1).strip() else default


def frame_parts(index_html: str) -> dict:
    """What the pages share with the welcome page, taken from the built file."""
    stripped = check_csp_hash.COMMENT.sub("", index_html)
    scripts = check_csp_hash.INLINE.findall(stripped)
    hashes = check_csp_hash.wanted(index_html)
    if not scripts or not hashes:
        raise BuildError("index.html has no inline theme script to copy")
    return {
        "THEME_SCRIPT": "<script>" + scripts[0] + "</script>",
        "THEME_HASH": hashes[0],
        "MASTHEAD_LINE": snapshot(index_html, "masthead_line",
                                  "72nd State Convention"),
        "DATES": snapshot(index_html, "dates", ""),
        "FOOTER": snapshot(index_html, "footer", "California Junior Classical League"),
    }


def nav_html(entries: list[dict], current: str | None) -> str:
    def link(href: str, text: str, here: bool = False) -> str:
        mark = ' aria-current="page"' if here else ""
        return f'    <a href="{html.escape(href, quote=True)}"{mark}>{html.escape(text)}</a>'

    lines = [link("/", "Welcome"), link("/#/schedule", "Schedule")]
    for entry in entries:
        if entry["show_in_nav"]:
            lines.append(link(entry["path"], entry["nav_label"],
                              entry["slug"] == current))
    lines.append('    <span class="nav__you">')
    lines.append("  " + link("/#/resources", "Resources"))
    lines.append("  " + link("/#/sign-in", "Sign in"))
    lines.append("    </span>")
    return "\n".join(lines)


def render(template: str, parts: dict, page: dict, body: str, entries: list[dict]) -> str:
    fields = {**parts, "TITLE": html.escape(page["title"]), "BODY": body,
              "NAV": nav_html(entries, page["slug"])}
    # One pass over the template, so a placeholder-looking string inside a
    # page's own text is never substituted.
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: fields[m.group(1)], template)


def build(pages: list[dict], fetch, out: pathlib.Path, *, index_html: str,
          template: str) -> list[dict]:
    """Write every page and pages.json under `out`. `fetch(url)` returns text."""
    parts = frame_parts(index_html)
    seen = set()
    entries = []
    for page in pages:
        slug = str(page.get("slug", ""))
        if not SLUG.match(slug) or slug in seen:
            raise BuildError(f"the API returned a bad or repeated address: {slug!r}")
        seen.add(slug)
        title = " ".join(str(page.get("title", "")).split())
        entries.append({
            "slug": slug, "title": title,
            "nav_label": " ".join(str(page.get("nav_label") or title).split()),
            "show_in_nav": bool(page.get("show_in_nav")), "path": f"/p/{slug}.html"})

    folder = out / "p"
    folder.mkdir(parents=True, exist_ok=True)
    for stale in folder.glob("*.html"):
        stale.unlink()

    for page, entry in zip(pages, entries):
        try:
            raw = fetch(page["html_url"])
            body = htmlclean.drop_leading_title(htmlclean.clean(raw), entry["title"])
        except (BuildError, ValueError) as error:
            raise BuildError(f"page “{entry['title']}” ({entry['slug']}): {error}") from None
        if not re.sub(r"<[^>]+>|\s", "", body):
            raise BuildError(
                f"page “{entry['title']}” ({entry['slug']}) came back empty. Is the "
                "Drive file shared with anyone who has the link, and is the Doc "
                "more than a title?")
        (folder / f"{entry['slug']}.html").write_text(
            render(template, parts, entry, body, entries), encoding="utf-8")
        print(f"  /p/{entry['slug']}.html  ({len(body):,} characters)")

    (out / "pages.json").write_text(
        json.dumps(entries, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", help="API base URL (default: the one in config.js)")
    parser.add_argument("--out", default=str(PUBLIC), help="the site folder")
    args = parser.parse_args()

    out = pathlib.Path(args.out)
    try:
        base = (args.api or api_base()).rstrip("/")
        listing = json.loads(http_get(f"{base}/public/pages"))["pages"]
        print(f"{len(listing)} page(s) from {base}")
        entries = build(listing, http_get, out,
                        index_html=(out / "index.html").read_text(encoding="utf-8"),
                        template=TEMPLATE.read_text(encoding="utf-8"))
    except (BuildError, ValueError, KeyError) as error:
        print(f"build_pages: {error}", file=sys.stderr)
        return 1
    print(f"wrote {len(entries)} page(s) and pages.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
