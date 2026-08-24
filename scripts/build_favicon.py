"""Make the favicon out of the CAJCL mark.

    python scripts/build_favicon.py

WHY A SCRIPT AND NOT A ONE-OFF
    Because the mark will be replaced. When a future commissioner drops a new
    logo.webp into frontend/public/img/, running this regenerates every size
    correctly, and nobody has to remember what was done by hand three years ago
    in an image editor that is no longer installed.

WHY IT PADS RATHER THAN CROPS
    The mark is very nearly square already -- 640x674 -- so cropping to a square
    would take a slice off the top and bottom of the artwork. Padding keeps the
    whole mark and centres it, which is what a favicon wants: the browser scales
    the square down to 16px and any crop shows as a clipped edge.

    The transparent margin is trimmed first, so the mark fills as much of those
    16 pixels as it can. At favicon size that is the difference between a
    recognisable shape and a smudge.

OUTPUT
    favicon.ico   16 / 32 / 48, for the address bar and older browsers
    favicon.png   512, for everything modern
    apple-touch-icon.png   180, on an opaque background because iOS ignores
                           transparency and would otherwise composite onto black
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
IMG = ROOT / "frontend" / "public" / "img"
SOURCE = IMG / "logo.webp"

# --parchment from tokens.css. iOS composites an icon onto whatever is behind
# it, and black is the default; the mark is dark gold and would disappear.
APPLE_BACKGROUND = (250, 248, 243, 255)


def squared(image: Image.Image) -> Image.Image:
    """Trim the transparent margin, then centre the mark on a square canvas."""
    image = image.convert("RGBA")

    box = image.getchannel("A").getbbox()
    if box:
        image = image.crop(box)

    side = max(image.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image,
                 ((side - image.width) // 2, (side - image.height) // 2),
                 image)
    return canvas


def main() -> int:
    if not SOURCE.exists():
        print(f"no source mark at {SOURCE.relative_to(ROOT)}", file=sys.stderr)
        print("put the logo there as logo.webp, or edit SOURCE in this script.",
              file=sys.stderr)
        return 1

    mark = squared(Image.open(SOURCE))
    print(f"source {SOURCE.name}  {Image.open(SOURCE).size}"
          f"  ->  squared {mark.size}")

    # 192 is the size Android asks for, and it is the largest any of this is
    # ever displayed at. A 512 version was four times the file for no visible
    # difference on a browser tab.
    png = mark.resize((192, 192), Image.LANCZOS)
    png.save(IMG / "favicon.png", optimize=True)

    # Pillow writes every requested size into the one .ico file.
    mark.save(IMG / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

    apple = Image.new("RGBA", mark.size, APPLE_BACKGROUND)
    apple.paste(mark, (0, 0), mark)
    apple.convert("RGB").resize((180, 180), Image.LANCZOS).save(
        IMG / "apple-touch-icon.png", optimize=True)

    for name in ("favicon.ico", "favicon.png", "apple-touch-icon.png"):
        size = (IMG / name).stat().st_size
        print(f"  wrote img/{name:<22} {size:>7,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
