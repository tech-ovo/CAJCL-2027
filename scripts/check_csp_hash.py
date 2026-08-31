"""Recompute the Content-Security-Policy hash for the inline theme script.

    python scripts/check_csp_hash.py          # report
    python scripts/check_csp_hash.py --write  # fix index.html

WHY A HASH AND NOT 'unsafe-inline'
    `script-src 'unsafe-inline'` allows ANY inline script, including one an
    attacker manages to get onto the page. A hash allows exactly one: the theme
    script, which has to run before the first paint and so cannot be moved into
    a file.

    The cost is that editing that script by one character stops it running --
    silently, because a blocked script is a console message nobody reads. Run
    this after touching it. A test fails if it is stale, which is the real
    safety net.
"""

from __future__ import annotations

import base64
import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX = ROOT / "frontend" / "public" / "index.html"
INLINE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def wanted(html: str) -> list[str]:
    """The hash of every inline script on the page, in order.

    NEWLINES ARE NORMALISED TO LF FIRST, and this is the whole trap. Git stores
    this file with LF and checks it out on Windows with CRLF, so a hash taken
    from the working copy does not match the bytes GitHub Pages serves. The
    browser would compute the LF hash, find no match, and block the script --
    silently, because a blocked script is a console line nobody reads, and the
    only symptom is a white flash on a dark-mode phone.

    Hashing the LF form means the answer is the same on any machine and is the
    one the browser will actually compute.
    """
    # COMMENTS ARE STRIPPED FIRST. This document explains its own policy in a
    # comment, and while writing that explanation the words "script tag" were
    # spelt as one -- which this pattern matched, running the "inline script"
    # from the middle of the prose to the end of the real one. The hash then
    # changed every time the comment was reworded.
    html = COMMENT.sub("", html)
    return [
        "sha256-" + base64.b64encode(
        hashlib.sha256(
            body.replace(chr(13) + chr(10), chr(10)).encode("utf-8")
        ).digest()).decode()
        for body in INLINE.findall(html)
    ]


def recorded(html: str) -> list[str]:
    policy = re.search(r'http-equiv="Content-Security-Policy" content="(.*?)"',
                       html, re.S)
    if not policy:
        return []
    return re.findall(r"'(sha256-[A-Za-z0-9+/=]+)'", policy.group(1))


def main() -> int:
    html = INDEX.read_text(encoding="utf-8")
    want, have = wanted(html), recorded(html)

    if want == have:
        print(f"the policy allows exactly the {len(want)} inline script(s) on the page")
        return 0

    print("  in the page, not allowed by the policy:")
    for value in want:
        if value not in have:
            print(f"    {value}")
    print("  allowed by the policy, not on the page:")
    for value in have:
        if value not in want:
            print(f"    {value}")

    if "--write" not in sys.argv[1:]:
        print()
        print("The inline script would be BLOCKED by the browser, silently. "
              "Run again with --write, or paste the hash in by hand.",
              file=sys.stderr)
        return 1

    fixed = html
    for old, new in zip(have + [None] * len(want), want):
        if old and old != new:
            fixed = fixed.replace(f"'{old}'", f"'{new}'")
    INDEX.write_text(fixed, encoding="utf-8")
    print("index.html updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
