"""The at-convention photo contest: what a photo must be, and what a category is.

The endpoints in api.py do the authorization and the Drive round trip. This
module holds the rules, so the tests can reach them without HTTP:

    whether an upload is really a photo     check_photo, check_thumbnail
    what a phone hid inside it              strip_metadata
    what a category may be called           check_category
    what the files are called in Drive      drive_name

A PHONE PHOTO CARRIES WHERE IT WAS TAKEN. The browser re-encodes every photo
through a canvas before sending it, which leaves the location, the camera and
the time behind; `strip_metadata` removes whatever survives when somebody
sends a file some other way. Re-encoding also applies the phone's rotation
to the pixels, so dropping the orientation tag here turns nothing sideways.
"""

from __future__ import annotations

import struct

from .catalog import ValidationError
from .contests import MAX_FILE_BYTES

# The browser sends at most a 2400-pixel JPEG, a megabyte or two. This is the
# ceiling for somebody whose browser could not re-encode and sent the original.
MAX_PHOTO_BYTES = MAX_FILE_BYTES
# A 480-pixel JPEG is 30-80 KB. Anything near this is not a thumbnail.
MAX_THUMB_BYTES = 512 * 1024

MAX_NAME = 80
MAX_DESCRIPTION = 1000
MAX_CAPTION = 200

MIME_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
ACCEPTED = ("jpg", "jpeg", "png")


def kind_of(data: bytes) -> str | None:
    """'jpg' or 'png' from the file's first bytes, whatever it is called."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    return None


def check_photo(name: str, data: bytes) -> tuple[str, str, bytes]:
    """(extension, mime type, cleaned bytes) for an acceptable photo.

    The type comes from the bytes, never from the name or from what the
    browser said, so a renamed file is not filed in Drive as a photo.
    """
    if not data:
        raise ValidationError(["That photo is empty."])
    if len(data) > MAX_PHOTO_BYTES:
        raise ValidationError([
            f"That photo is {len(data) / 1048576:.1f} MB, and the limit is "
            f"{MAX_PHOTO_BYTES // 1048576} MB."])
    kind = kind_of(data)
    if kind is None:
        raise ValidationError([
            f"“{name}” is not a JPG or PNG photo. On an iPhone, choose it from "
            "Photos rather than Files and it is converted for you."])
    return kind, MIME_TYPES[kind], strip_metadata(kind, data)


def check_thumbnail(data: bytes) -> bytes:
    if kind_of(data) != "jpg" or len(data) > MAX_THUMB_BYTES:
        raise ValidationError(["The preview of that photo did not come out "
                               "right. Try choosing it again."])
    return strip_metadata("jpg", data)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

# APP1 is Exif and XMP -- the location, the camera, the time. APP13 is
# Photoshop's IPTC block, which can hold names and places. COM is a free-text
# comment. APP0 (JFIF), APP2 (the colour profile) and APP14 (Adobe's colour
# transform) are what the picture needs to look right, and they stay.
_JPEG_DROP = {0xE1, 0xED, 0xFE}
# Text and time chunks, and PNG's own Exif.
_PNG_DROP = {b"eXIf", b"tEXt", b"iTXt", b"zTXt", b"tIME"}


def strip_metadata(kind: str, data: bytes) -> bytes:
    """The same image without the parts that say where, when and on what.

    Anything it cannot follow is refused rather than passed through, because
    passing it through is how a location would leave this function intact.
    """
    try:
        if kind == "jpg":
            return _strip_jpeg(data)
        if kind == "png":
            return _strip_png(data)
    except (IndexError, struct.error):
        pass
    raise ValidationError(["That photo looks damaged. Take or export it "
                           "again and try once more."])


def _strip_jpeg(data: bytes) -> bytes:
    out = bytearray(data[:2])            # SOI
    i = 2
    while True:
        if data[i] != 0xFF:
            raise IndexError("not a marker")
        marker = data[i + 1]
        if marker == 0xFF:               # fill byte
            i += 1
            continue
        if marker == 0xDA:               # start of scan: the rest is the image
            out += data[i:]
            return bytes(out)
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:
            out += data[i:i + 2]         # markers with no length
            i += 2
            continue
        (length,) = struct.unpack(">H", data[i + 2:i + 4])
        if length < 2 or i + 2 + length > len(data):
            raise IndexError("segment runs past the end")
        if marker not in _JPEG_DROP:
            out += data[i:i + 2 + length]
        i += 2 + length


def _strip_png(data: bytes) -> bytes:
    out = bytearray(data[:8])
    i = 8
    while i < len(data):
        (length,) = struct.unpack(">I", data[i:i + 4])
        kind = data[i + 4:i + 8]
        end = i + 12 + length
        if end > len(data):
            raise IndexError("chunk runs past the end")
        if kind not in _PNG_DROP:
            out += data[i:end]
        i = end
        if kind == b"IEND":
            return bytes(out)
    raise IndexError("no IEND")


# ---------------------------------------------------------------------------
# Categories and captions
# ---------------------------------------------------------------------------

def check_category(payload: dict, current: dict | None = None) -> dict:
    """The columns for a new or edited category. A field left out of an edit
    keeps its current value."""
    current = current or {}
    errors = []

    def given(key):
        return key in payload or key not in current

    name = " ".join(str(payload.get("name", current.get("name")) or "").split())
    if not name:
        errors.append("Give the category a name, like “Best flower photo”.")
    elif len(name) > MAX_NAME:
        errors.append(f"Keep the name under {MAX_NAME} characters.")

    description = (str(payload.get("description") or "").strip()
                   if given("description") else current.get("description") or "")
    if len(description) > MAX_DESCRIPTION:
        errors.append(f"Keep the description under {MAX_DESCRIPTION} characters.")

    accepting = (bool(payload.get("accepting", True)) if given("accepting")
                 else bool(current.get("accepting")))

    sort_order = current.get("sort_order", 0)
    if "sort_order" in payload:
        try:
            sort_order = int(payload["sort_order"])
        except (TypeError, ValueError):
            errors.append("The order must be a whole number.")

    if errors:
        raise ValidationError(errors)
    return {"name": name, "description": description or None,
            "accepting": 1 if accepting else 0, "sort_order": sort_order}


def check_caption(payload: dict) -> str | None:
    caption = " ".join(str(payload.get("caption") or "").split())
    if len(caption) > MAX_CAPTION:
        raise ValidationError([f"Keep the caption under {MAX_CAPTION} characters."])
    return caption or None


# ---------------------------------------------------------------------------
# Names in Drive
# ---------------------------------------------------------------------------

ROOT_FOLDER = "Photo Contest"
THUMBS_FOLDER = "Thumbnails"


def drive_name(person: dict, school: dict, extension: str,
               thumbnail: bool = False) -> str:
    """The file's name in Drive, which only the chairs can open. The chapter
    number keeps one chapter's photos together when the folder is sorted."""
    number = school.get("number")
    chapter = f"{number:02d} {school['name']}" if number is not None else school["name"]
    suffix = " (thumbnail)" if thumbnail else ""
    return f"{chapter} - {person['last_name']}, {person['first_name']}{suffix}.{extension}"
