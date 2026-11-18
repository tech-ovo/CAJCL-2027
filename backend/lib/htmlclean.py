"""Reduce HTML from a Google Doc to a handful of safe, plain tags.

Used twice, on purpose:

  * in the tests and the local Drive stand-in, as the reference for what the
    Apps Script cleaner (apps-script/Code.gs, `cleanDocHtml`) should produce;
  * by scripts/build_pages.py on every page it downloads, because that page
    goes onto the public site and Drive is not a source to trust. Whatever the
    Apps Script did or did not manage to strip, nothing outside this list
    reaches the site.

An ALLOWLIST. Anything not named here is removed: a tag is unwrapped (its text
stays), and the few that can carry code or load something (script, style,
iframe, ...) are removed with everything inside them. Attributes are dropped
except `href` on a link and `colspan`/`rowspan` on a cell. Links may only go
to http(s), mailto, tel, or somewhere on the same page.

IMAGES. The only images kept are ones embedded in the HTML as
`data:image/{png,jpeg,gif};base64,...` (Apps Script puts them there; an image
linked from anywhere else is dropped, so nothing on a page can load from
another site). `extract_images` then turns each into a real file on the site,
checking its type by its first bytes and removing location/camera metadata.

Output is always well-formed: every tag opened is closed, in order.
"""

from __future__ import annotations

import base64
import hashlib
import html
import pathlib
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

# The page's TEXT, with its images taken out, may not exceed this...
MAX_BYTES = 2 * 1024 * 1024
# ...and the file as downloaded, images included, may not exceed this.
MAX_SOURCE_BYTES = 24 * 1024 * 1024
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_IMAGES = 40
MAX_ALT = 300

DATA_IMAGE = re.compile(r"^data:image/(png|jpeg|gif);base64,([A-Za-z0-9+/]+={0,2})$")
IMG_TAG = re.compile(r'<img src="(data:image/[^"]*)" alt="([^"]*)">')

# Kept as they are.
KEEP = {"p", "br", "hr", "ul", "ol", "li", "strong", "em", "u", "sub", "sup",
        "a", "table", "thead", "tbody", "tr", "th", "td", "blockquote",
        "code", "pre", "h2", "h3", "h4"}
VOID = {"br", "hr", "img"}

# Written as another tag. The page's own title is the <h1>, so a Doc's
# "Heading 1" becomes <h2>, and so on down, bottoming out at <h4>.
RENAME = {"h1": "h2", "h2": "h3", "h3": "h4", "h4": "h4", "h5": "h4", "h6": "h4",
          "b": "strong", "i": "em", "ins": "u"}

# Removed along with everything inside.
DISCARD = {"script", "style", "iframe", "object", "embed", "head", "title",
           "svg", "math", "form", "button", "textarea", "select", "noscript",
           "template", "canvas", "audio", "video", "picture", "map",
           "frameset", "frame", "applet"}
# Removed, but they have no end tag, so there is no "inside" to skip.
DISCARD_VOID = {"link", "meta", "base", "source", "track", "input"}

# Opening the key closes an open tag in the value, if it is the innermost.
IMPLIED_END = {"li": ("li",), "p": ("p",), "td": ("td", "th"), "th": ("td", "th"),
               "tr": ("td", "th", "tr")}

SAFE_SCHEMES = {"http", "https", "mailto", "tel"}


def clean_href(value: str) -> str:
    """The link's address if it is safe to keep, otherwise an empty string.

    Google wraps every link in a redirect through google.com/url?q=...; the
    real destination is inside it.
    """
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if (parsed.scheme in ("http", "https")
            and parsed.netloc.lower().endswith("google.com")
            and parsed.path == "/url"):
        target = parse_qs(parsed.query).get("q", [""])[0]
        return clean_href(target) if target != value else ""
    if value.startswith("#") and len(value) > 1:
        return value
    if parsed.scheme.lower() in SAFE_SCHEMES and (parsed.netloc or parsed.path):
        return value
    return ""


class _Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []      # tags we emitted and have yet to close
        self.skip = 0                   # inside a discarded element
        self.skip_tag = ""

    # -- opening ------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if self.skip:
            if tag == self.skip_tag:
                self.skip += 1
            return
        if tag in DISCARD_VOID:
            return
        if tag in DISCARD:
            self.skip, self.skip_tag = 1, tag
            return
        tag = RENAME.get(tag, tag)
        if tag == "img":
            attributes = dict(attrs)
            source = (attributes.get("src") or "").strip()
            if DATA_IMAGE.match(source):
                alt = " ".join((attributes.get("alt") or "").split())[:MAX_ALT]
                self.out.append(f'<img src="{source}" alt="{html.escape(alt, quote=True)}">')
            return
        if tag not in KEEP:
            return                       # unwrapped: its text still arrives
        # HTML lets these end tags be left off; the next sibling closes them.
        for closes in IMPLIED_END.get(tag, ()):
            if self.stack and self.stack[-1] == closes:
                self.out.append(f"</{self.stack.pop()}>")
        attributes = dict(attrs)
        if tag == "a":
            href = clean_href(attributes.get("href", ""))
            if not href:
                return                   # an anchor with nowhere to go
            self.out.append(f'<a href="{html.escape(href, quote=True)}">')
            self.stack.append("a")
            return
        if tag in ("td", "th"):
            extra = ""
            for name in ("colspan", "rowspan"):
                value = (attributes.get(name) or "").strip()
                if value.isdigit() and 1 < int(value) <= 50:
                    extra += f' {name}="{int(value)}"'
            self.out.append(f"<{tag}{extra}>")
            self.stack.append(tag)
            return
        if tag in VOID:
            self.out.append(f"<{tag}>")
            return
        self.out.append(f"<{tag}>")
        self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        # <br/> and <hr/>; for anything else a self-closing form opens nothing.
        if tag in VOID:
            self.handle_starttag(tag, attrs)

    # -- closing ------------------------------------------------------------
    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip_tag:
                self.skip -= 1
            return
        tag = RENAME.get(tag, tag)
        if tag in VOID or tag not in self.stack:
            return
        while self.stack:
            top = self.stack.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(html.escape(data, quote=False))

    def finish(self) -> str:
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


_EMPTY = re.compile(
    r"<(p|li|strong|em|u|sub|sup|a|blockquote|h[2-4])>(?:\s|<br>|&nbsp;| )*</\1>")
_BLANKS = re.compile(r"(?:<br>\s*){3,}")


def clean(source: str) -> str:
    """Plain, safe HTML for the body of a page. Raises ValueError if too big."""
    if len(source) > MAX_SOURCE_BYTES:
        raise ValueError("That document is too large to publish as one page.")
    body = re.search(r"<body\b[^>]*>(.*)</body>", source, re.I | re.S)
    parser = _Cleaner()
    parser.feed(body.group(1) if body else source)
    parser.close()
    result = parser.finish()
    # Removing an empty element can leave its parent empty.
    for _ in range(3):
        tidied = _EMPTY.sub("", result)
        if tidied == result:
            break
        result = tidied
    result = _BLANKS.sub("<br><br>", result).strip()
    if len(IMG_TAG.sub("", result).encode("utf-8", "ignore")) > MAX_BYTES:
        raise ValueError("That document is too long to publish as one page.")
    return result


def drop_leading_title(body: str, title: str) -> str:
    """Remove the Doc's own first heading when it just repeats the page title,
    because the page already shows the title as its heading."""
    match = re.match(r"\s*<h2>(.*?)</h2>", body, re.S)
    if match:
        text = html.unescape(re.sub(r"<[^>]+>", "", match.group(1)))
        if " ".join(text.split()).lower() == " ".join(title.split()).lower():
            return body[match.end():].lstrip()
    return body


def extract_images(body: str, folder: pathlib.Path, url_prefix: str) -> str:
    """Write each embedded image to `folder` and point the page at the file.

    Files are named by a hash of their (cleaned) bytes, so the same picture on
    two pages is one file. Raises ValueError for a picture that is not what it
    says it is, is too large, or when the page has too many.
    """
    from . import photos
    from .catalog import ValidationError

    found = IMG_TAG.findall(body)
    if len(found) > MAX_IMAGES:
        raise ValueError(f"That page has {len(found)} pictures; the most is {MAX_IMAGES}.")

    def replace(match: re.Match) -> str:
        uri, alt = match.group(1), match.group(2)
        parsed = DATA_IMAGE.match(uri)
        if not parsed:
            return ""
        try:
            data = base64.b64decode(parsed.group(2), validate=True)
        except ValueError:
            raise ValueError("A picture in the document is damaged.") from None
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(
                f"A picture is {len(data) // 1024 // 1024} MB; the most is "
                f"{MAX_IMAGE_BYTES // 1024 // 1024} MB. Shrink it in the Doc.")
        kind = photos.kind_of(data) or ("gif" if data[:6] in (b"GIF87a", b"GIF89a") else None)
        if kind is None:
            raise ValueError("A picture in the document is not a PNG, JPEG or GIF.")
        if kind in ("jpg", "png"):
            try:
                data = photos.strip_metadata(kind, data)
            except ValidationError as error:
                raise ValueError(f"A picture in the document is damaged ({error.errors[0]})") from None
        name = hashlib.sha256(data).hexdigest()[:20] + "." + kind
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
        return f'<img src="{url_prefix}/{name}" alt="{alt}">'

    return IMG_TAG.sub(replace, body)
