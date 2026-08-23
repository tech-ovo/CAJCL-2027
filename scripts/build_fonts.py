"""Download, subset, and verify the three self-hosted typefaces.

WHY SELF-HOSTED
    Literata, IBM Plex Sans, and IBM Plex Mono are all OFL-licensed and are
    committed to this repository as subset woff2 files. No Google Fonts CDN, no
    third-party request, no external point of failure -- the site has to work
    from a school network that blocks half the internet, and a webfont request
    that hangs is a masthead that never renders.

THE CHECK THAT MATTERS
    The subset MUST include Latin Extended-A. The convention theme is

        aequam mementō rēbus in arduīs servāre mentem

    and the macrons -- ā ē ī ō ū -- live in that block, which default
    Latin-basic subsetting silently drops. The result is tofu boxes in the
    masthead, on the one line of text the whole design is built around.

    So this script does not merely subset. It renders every character of the
    theme string against the finished font and FAILS THE BUILD if any glyph is
    missing. docs/design.md calls this the most likely way the site ships
    broken, and it is right.

    python scripts/build_fonts.py          # download, subset, verify
    python scripts/build_fonts.py --check  # verify what is committed, no network
"""

from __future__ import annotations

import argparse
import io
import pathlib
import re
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

FONTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "public" / "fonts"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# What we ask Google Fonts for, and what each file is called locally.
FACES = [
    ("Literata",       "wght@400",        "literata-400"),
    ("Literata",       "wght@600",        "literata-600"),
    ("Literata",       "ital,wght@1,400", "literata-italic-400"),
    ("IBM+Plex+Sans",  "wght@400",        "plex-sans-400"),
    ("IBM+Plex+Sans",  "wght@600",        "plex-sans-600"),
    ("IBM+Plex+Mono",  "wght@400",        "plex-mono-400"),
    ("IBM+Plex+Mono",  "wght@500",        "plex-mono-500"),
]

# The subset. Basic Latin, Latin-1 Supplement, and -- the whole point --
# Latin Extended-A, plus the punctuation the design actually uses.
UNICODE_RANGES = [
    (0x0020, 0x007E),   # Basic Latin
    (0x00A0, 0x00FF),   # Latin-1 Supplement: accented names like Seán
    (0x0100, 0x017F),   # LATIN EXTENDED-A: the macrons. Do not remove.
    (0x2010, 0x2027),   # dashes, quotes, ellipsis
    (0x20A0, 0x20BF),   # currency, for the invoice
    (0x2116, 0x2116),   # numero sign, used in the tabula
    (0x2190, 0x2193),   # arrows
    (0x2713, 0x2717),   # check and cross, for form status
]

# Every character that must render, or the build fails. The theme is the reason
# this file exists; the rest are strings the site cannot do without.
REQUIRED_TEXT = (
    "aequam mementō rēbus in arduīs servāre mentem"
    "Remember to keep an even mind in adversity"
    "Horace, Odes II.3.1–2"
    "salvē bonam fortūnam"
    "XII–XIII MARTII MMXXVII"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "$€£№#%&@*+-=/\\|()[]{}<>.,;:!?'\"“”‘’…–—"
    "Seán O'Brien · de la Cruz · Nguyễn"
)


def codepoints() -> set[int]:
    wanted = set()
    for low, high in UNICODE_RANGES:
        wanted.update(range(low, high + 1))
    wanted.update(ord(ch) for ch in REQUIRED_TEXT)
    return wanted


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def source_url(family: str, axis: str) -> str:
    """The TTF behind a Google Fonts face.

    A modern User-Agent gets woff2 back, which fontTools can read, but the
    static TTF is what subsets cleanly -- so we ask with an ancient UA.
    """
    css = urllib.request.Request(
        f"https://fonts.googleapis.com/css2?family={family}:{axis}",
        headers={"User-Agent": "Mozilla/4.0"})
    with urllib.request.urlopen(css, timeout=30) as response:
        body = response.read().decode("utf-8")
    urls = re.findall(r"url\((https://[^)]+)\)", body)
    if not urls:
        raise SystemExit(f"no font file found for {family} {axis}")
    return urls[0]


def subset_one(family: str, axis: str, name: str) -> pathlib.Path:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    print(f"  {name:22s} downloading", end="", flush=True)
    raw = fetch(source_url(family, axis))

    font = TTFont(io.BytesIO(raw))
    options = subset.Options()
    options.layout_features = ["kern", "liga", "tnum", "onum", "calt", "ccmp"]
    options.drop_tables += ["DSIG"]
    options.notdef_outline = True
    options.recalc_bounds = True
    options.name_IDs = ["*"]
    options.name_legacy = True

    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=codepoints())
    subsetter.subset(font)

    font.flavor = "woff2"
    out = FONTS_DIR / f"{name}.woff2"
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    font.save(out)
    font.close()
    print(f"  -> {out.name} ({out.stat().st_size / 1024:.0f} KB)")
    return out


def verify(path: pathlib.Path) -> list[str]:
    """Every character of REQUIRED_TEXT must have a glyph. Returns what is missing."""
    from fontTools.ttLib import TTFont

    font = TTFont(path)
    covered = set()
    for table in font["cmap"].tables:
        covered.update(table.cmap.keys())
    font.close()

    missing = sorted({ch for ch in REQUIRED_TEXT
                      if ord(ch) not in covered and not ch.isspace()})
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="verify the committed fonts without downloading")
    args = ap.parse_args()

    if not args.check:
        print("building font subsets")
        for family, axis, name in FACES:
            subset_one(family, axis, name)
        print()

    print("verifying every required glyph renders")
    failures = []
    for _, _, name in FACES:
        path = FONTS_DIR / f"{name}.woff2"
        if not path.exists():
            failures.append(f"{name}.woff2 is missing")
            continue
        missing = verify(path)
        if missing:
            shown = " ".join(f"{ch!r} (U+{ord(ch):04X})" for ch in missing[:12])
            failures.append(f"{name}.woff2 is missing {len(missing)} glyph(s): {shown}")
        else:
            print(f"  {name:22s} ok")

    if failures:
        print()
        print("FONT BUILD FAILED")
        for failure in failures:
            print(f"  - {failure}")
        print()
        print("The convention theme needs Latin Extended-A (U+0100-U+017F) for its")
        print("macrons. Without those glyphs the masthead renders as tofu boxes on")
        print("the one line the whole design is built around. See docs/design.md.")
        return 1

    print()
    print("all faces carry every required glyph, macrons included")
    return 0


if __name__ == "__main__":
    sys.exit(main())
