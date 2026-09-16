"""Pre-convention contests: what an entry must be, and what its scores add up to.

The endpoints in api.py do the authorization and the Drive round trip. This
module holds the rules, so the tests can reach them without HTTP:

    which division an entry belongs to     division_for
    whether a file is what it claims       check_file
    how long a piece of writing is         read_text, count_words
    what a length rule costs               penalty_for
    whether a judge's score is complete    check_score
    who is winning                         rank

BLIND JUDGING IS A RULE, NOT A COURTESY. Nothing a judge is sent carries a name,
a chapter, or the file name the student uploaded ("Jane Doe myth FINAL.docx").
`judge_view` is the one place that shapes an entry for a judge.
"""

from __future__ import annotations

import io
import json
import math
import re
import zipfile
from xml.etree import ElementTree

from .catalog import ValidationError

# Apps Script accepts a request of about 50 MB, and base64 adds a third.
MAX_FILE_BYTES = 20 * 1024 * 1024

MIME_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain; charset=utf-8",
}

DIVISION_LABELS = {"none": "Open", "level": "MS or HS",
                   "level_grade": "MS, HS 9–10, HS 11–12",
                   "latin_level": "MS-I to MS-III, HS-I to HS-III, HS-Advanced"}

# By Latin level, these seven and no others.
LATIN_DIVISIONS = {
    "MS-1": "MS-I", "MS-2": "MS-II", "MS-3": "MS-III",
    "HS-1": "HS-I", "HS-2": "HS-II", "HS-3": "HS-III", "HS-Adv": "HS-Advanced",
}

# Youngest first, the order the awards are read in.
DIVISION_ORDER = {
    "MS": 0, "HS 9–10": 1, "HS 11–12": 2, "HS": 3,
    "MS-I": 10, "MS-II": 11, "MS-III": 12,
    "HS-I": 13, "HS-II": 14, "HS-III": 15, "HS-Advanced": 16,
    "Open": 20,
}

MAX_TITLE = 200
MAX_TRANSLATION = 300
MAX_TEXT_KEPT = 200_000        # characters of extracted writing kept for judges


# ---------------------------------------------------------------------------
# The catalog of contests
# ---------------------------------------------------------------------------

def load(tx) -> list[dict]:
    """Every active contest with its rubric attached. About thirty rows in all."""
    criteria: dict[int, list[dict]] = {}
    for row in tx.all("contests.criteria_all"):
        criteria.setdefault(row["item_id"], []).append(dict(row))

    contests = []
    for row in tx.all("contests.all"):
        contest = dict(row)
        contest["criteria"] = criteria.get(contest["item_id"], [])
        contest["facet_list"] = split_lines(contest["facets"])
        contest["accepted"] = [t for t in (contest["accepted_types"] or "").split(",") if t]
        contest["max_points"] = sum(c["max_points"] for c in contest["criteria"])
        contest["division_label"] = DIVISION_LABELS[contest["divisions"]]
        contests.append(contest)
    return contests


def by_item(tx, item_id: int) -> dict:
    for contest in load(tx):
        if contest["item_id"] == item_id:
            return contest
    raise ValidationError(["There is no such contest."])


def split_lines(text: str | None) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def public_view(contest: dict) -> dict:
    """What anybody entering a contest may see about it."""
    keep = ("item_id", "key", "name", "entry_kind", "entered_by", "divisions",
            "division_label", "accepted", "needs_title", "min_words",
            "max_words", "words_penalty", "max_chars", "needs_translation",
            "must_attend", "facet_list", "rules_md", "criteria", "max_points")
    return {k: contest[k] for k in keep}


# ---------------------------------------------------------------------------
# Divisions
# ---------------------------------------------------------------------------

def division_for(contest: dict, school: dict, person: dict | None) -> str:
    """Which pool this entry is judged in, fixed at the moment it is submitted."""
    scheme = contest["divisions"]
    if scheme == "none":
        return "Open"

    if scheme == "latin_level":
        level = (person or {}).get("latin_level")
        if level not in LATIN_DIVISIONS:
            raise ValidationError([
                "Add your Latin level on your registration form first. This "
                "contest is judged by Latin level, so it needs to know yours."])
        return LATIN_DIVISIONS[level]

    level = school.get("level")
    if level not in ("MS", "HS"):
        raise ValidationError([
            f"{school['name']} is not marked as a middle or high school chapter, "
            "so this entry has no division. Ask the Registration chairs to fix it."])
    if scheme == "level" or level == "MS":
        return level

    grade = (person or {}).get("grade")
    if not grade:
        raise ValidationError([
            "Add your grade on your registration form first. This contest is "
            "judged in grade divisions, so it needs to know yours."])
    return "HS 9–10" if int(grade) <= 10 else "HS 11–12"


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def extension_of(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def check_file(contest: dict, name: str, data: bytes) -> tuple[str, str]:
    """(extension, mime type) for an acceptable file, or a ValidationError.

    The extension is checked against the file's first bytes, so a renamed
    executable is not handed to a judge as "Entry 14.pdf". The mime type
    stored is the one this module derives, never the one the browser sent.
    """
    extension = extension_of(name)
    accepted = contest["accepted"]
    listed = ", ".join(t.upper() for t in accepted if t not in ("jpeg", "tif"))
    if extension not in accepted:
        raise ValidationError([
            f"{contest['name']} accepts {listed} files. "
            f"“{name}” is not one of those."])
    if not data:
        raise ValidationError(["That file is empty."])
    if len(data) > MAX_FILE_BYTES:
        raise ValidationError([
            f"That file is {len(data) / 1048576:.1f} MB, and the limit is "
            f"{MAX_FILE_BYTES // 1048576} MB. Save it at a smaller size and try again."])

    if not _looks_like(extension, data):
        raise ValidationError([
            f"“{name}” does not look like a real {extension.upper()} file. "
            "Export it again from the program you made it in."])
    return extension, MIME_TYPES[extension]


def _looks_like(extension: str, data: bytes) -> bool:
    if extension == "pdf":
        return data[:1024].lstrip().startswith(b"%PDF-")
    if extension in ("jpg", "jpeg"):
        return data.startswith(b"\xff\xd8\xff")
    if extension == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == "gif":
        return data[:6] in (b"GIF87a", b"GIF89a")
    if extension in ("tif", "tiff"):
        return data[:4] in (b"II*\x00", b"MM\x00*")
    if extension == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                return "word/document.xml" in archive.namelist()
        except zipfile.BadZipFile:
            return False
    if extension == "txt":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return False
        return "\x00" not in text
    return False


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_text(extension: str, data: bytes) -> str | None:
    """The words in a .docx or .txt, for counting and for judges to read.

    None for anything else. A PDF's text cannot be read reliably without a
    heavy library, so a PDF's length is declared by the student instead.
    """
    if extension == "txt":
        return data.decode("utf-8-sig").replace("\r\n", "\n")
    if extension != "docx":
        return None

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo("word/document.xml")
        # A zip bomb unpacks to far more than it weighs. A real essay's XML is
        # a few hundred kilobytes.
        if info.file_size > MAX_FILE_BYTES:
            raise ValidationError(["That document is too large to read."])
        root = ElementTree.fromstring(archive.read(info))

    paragraphs = []
    for paragraph in root.iter(f"{_W}p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == f"{_W}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{_W}tab":
                parts.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                parts.append("\n")
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


_WORD = re.compile(r"\w+(?:['’\-]\w+)*")


def count_words(text: str) -> int:
    """Words as a reader counts them: "don't" and "well-known" are one each."""
    return len(_WORD.findall(text))


def penalty_for(contest: dict, word_count: int | None) -> int:
    """Points lost for length: `words_penalty` per started hundred words out of range.

    1,210 words against a 1,200 limit is ten words over, which is into the
    first hundred, so it costs one penalty. An unknown length costs nothing
    here; the judge sees that it is unknown.
    """
    per = contest["words_penalty"] or 0
    if not per or word_count is None:
        return 0
    low, high = contest["min_words"], contest["max_words"]
    if low is not None and word_count < low:
        return math.ceil((low - word_count) / 100) * per
    if high is not None and word_count > high:
        return math.ceil((word_count - high) / 100) * per
    return 0


def drive_name(person: dict | None, school: dict, extension: str) -> str:
    """The file's name in Drive, which only the chairs can open."""
    if person:
        who = f"{person['last_name']}, {person['first_name']}"
    else:
        who = school["name"]
    return f"{who}.{extension}"


def chapter_folder_name(school: dict) -> str:
    number = school.get("number")
    return f"{number:02d} {school['name']}" if number is not None else school["name"]


def anonymous_name(entry: dict, extension: str) -> str:
    return f"Entry {entry['id']}.{extension}"


# ---------------------------------------------------------------------------
# Entries that are not files
# ---------------------------------------------------------------------------

def check_text_entry(contest: dict, payload: dict) -> tuple[str, str | None]:
    text = " ".join(str(payload.get("text") or "").split())
    translation = " ".join(str(payload.get("translation") or "").split()) or None
    errors = []
    if not text:
        errors.append("Write your slogan.")
    elif contest["max_chars"] and len(text) > contest["max_chars"]:
        errors.append(
            f"A slogan has to fit on a bumper sticker: {contest['max_chars']} "
            f"characters at most. Yours is {len(text)}.")
    if contest["needs_translation"]:
        if not translation:
            errors.append("A Latin slogan needs an English translation.")
        elif len(translation) > MAX_TRANSLATION:
            errors.append(f"Keep the translation under {MAX_TRANSLATION} characters.")
    else:
        translation = None
    if errors:
        raise ValidationError(errors)
    return text, translation


GOOGLE_HOSTS = ("https://docs.google.com/", "https://drive.google.com/")


def check_link_entry(contest: dict, payload: dict) -> tuple[str, str]:
    link = str(payload.get("link_url") or "").strip()
    chosen = [f for f in (payload.get("facets") or []) if isinstance(f, str)]
    errors = []
    if not link.startswith(GOOGLE_HOSTS) or len(link) > 500 or any(c.isspace() for c in link):
        errors.append(
            "Paste the link to your portfolio's Google document. It starts with "
            "https://docs.google.com/.")
    facets = [f for f in contest["facet_list"] if f in chosen]
    if not facets:
        errors.append("Tick at least one category your portfolio includes.")
    if errors:
        raise ValidationError(errors)
    return link, "\n".join(facets)


def check_title(contest: dict, payload: dict) -> str | None:
    title = " ".join(str(payload.get("title") or "").split())
    if contest["needs_title"] and not title:
        raise ValidationError(["Give your entry a title."])
    if len(title) > MAX_TITLE:
        raise ValidationError([f"Keep the title under {MAX_TITLE} characters."])
    return title or None


def declared_words(payload: dict) -> int:
    try:
        words = int(payload.get("word_count"))
    except (TypeError, ValueError):
        words = 0
    if words <= 0 or words > 100_000:
        raise ValidationError([
            "Say how many words your myth has. A PDF cannot be counted "
            "automatically — or upload it as a .docx and it will be."])
    return words


# ---------------------------------------------------------------------------
# Judging
# ---------------------------------------------------------------------------

def judge_view(contest: dict, rows: list) -> list[dict]:
    """Entries as a judge sees them: numbered, never named.

    `rows` is contests.entries_for_judging, one row per entry per score this
    judge has saved, so an entry judged in three facets arrives three times.
    """
    entries: dict[int, dict] = {}
    for row in rows:
        entry = entries.get(row["id"])
        if entry is None:
            entry = {
                "id": row["id"],
                "division": row["division"],
                "title": row["title"],
                "text": row["body_text"],
                "translation": row["translation"],
                "link_url": row["link_url"],
                "facets": split_lines(row["facets"]) if contest["facet_list"] else [""],
                "word_count": row["word_count"],
                "word_count_source": row["word_count_source"],
                "penalty": penalty_for(contest, row["word_count"]),
                "has_file": bool(row["has_file"]),
                "mime_type": row["mime_type"],
                "size_bytes": row["size_bytes"],
                "scores": {},
            }
            entries[row["id"]] = entry
        if row["score_status"] is not None:
            entry["scores"][row["score_facet"]] = {
                "points": json.loads(row["points_json"]),
                "penalty": row["penalty"],
                "total": row["total"],
                "comment": row["comment"],
                "status": row["score_status"],
            }
    return sorted(entries.values(),
                  key=lambda e: (DIVISION_ORDER.get(e["division"], 99), e["id"]))


def check_score(contest: dict, entry: dict, payload: dict) -> dict:
    """A judge's score, validated against the rubric. Returns what to store."""
    facet = str(payload.get("facet") or "")
    allowed = split_lines(entry["facets"]) if contest["facet_list"] else [""]
    if facet not in allowed:
        raise ValidationError(["That entry is not judged in that category."])

    submit = bool(payload.get("submit"))
    given = payload.get("points") or {}
    if not isinstance(given, dict):
        raise ValidationError(["Scores arrived in a shape this cannot read."])

    points: dict[str, float] = {}
    errors = []
    for criterion in contest["criteria"]:
        raw = given.get(str(criterion["id"]))
        if raw in (None, ""):
            if submit:
                errors.append(f"Score {criterion['label']} before handing this in.")
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            errors.append(f"{criterion['label']} needs a number.")
            continue
        if not math.isfinite(value) or value < 0 or value > criterion["max_points"]:
            errors.append(
                f"{criterion['label']} is out of {criterion['max_points']}; "
                f"{raw} is not between 0 and {criterion['max_points']}.")
            continue
        points[str(criterion["id"])] = round(value, 2)
    if not contest["criteria"]:
        errors.append("This contest has no rubric yet. Ask the Academics chairs.")
    if errors:
        raise ValidationError(errors)

    comment = str(payload.get("comment") or "").strip()[:2000] or None
    penalty = penalty_for(contest, entry["word_count"])
    total = max(0.0, round(sum(points.values()) - penalty, 2))
    return {"facet": facet, "points_json": json.dumps(points, sort_keys=True),
            "penalty": penalty, "total": total, "comment": comment,
            "status": "submitted" if submit else "draft"}


def rank(contest: dict, entries: list, scores: list) -> list[dict]:
    """Standings per division and facet, from submitted scores only.

    An entry's score is the mean of its judges' totals. Ties share a place
    (1, 2, 2, 4). An entry whose creator is no longer attending is listed but
    not placed when the contest requires attendance -- the Convention Book's
    rule, applied here so nobody has to remember it at the awards table.
    """
    by_entry: dict[tuple[int, str], list] = {}
    for score in scores:
        by_entry.setdefault((score["entry_id"], score["facet"]), []).append(score)

    groups: dict[tuple[str, str], list] = {}
    for row in entries:
        facets = split_lines(row["facets"]) if contest["facet_list"] else [""]
        for facet in facets:
            judged = by_entry.get((row["id"], facet), [])
            totals = [s["total"] for s in judged]
            eligible = not (contest["must_attend"] and row["person_id"]
                            and row["person_status"] != "active")
            groups.setdefault((row["division"], facet), []).append({
                "entry_id": row["id"],
                "title": row["title"],
                "text": row["body_text"],
                "translation": row["translation"],
                "link_url": row["link_url"],
                "has_file": bool(row["has_file"]),
                "word_count": row["word_count"],
                "person_id": row["person_id"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "school_id": row["school_id"],
                "school_name": row["school_name"],
                "school_number": row["school_number"],
                "school_seq": row["school_seq"],
                "eligible": eligible,
                "judges": [{"name": f"{s['judge_first']} {s['judge_last']}".strip(),
                            "total": s["total"], "comment": s["comment"]}
                           for s in judged],
                "average": round(sum(totals) / len(totals), 2) if totals else None,
                "place": None,
            })

    facet_order = {f: i for i, f in enumerate(contest["facet_list"])}

    def order(key):
        division, facet = key
        return (DIVISION_ORDER.get(division, 99), division, facet_order.get(facet, 0))

    out = []
    for (division, facet) in sorted(groups, key=order):
        rows = groups[(division, facet)]
        placed = sorted((r for r in rows if r["eligible"] and r["average"] is not None),
                        key=lambda r: -r["average"])
        previous, place = None, 0
        for index, row in enumerate(placed, 1):
            if row["average"] != previous:
                place, previous = index, row["average"]
            row["place"] = place
        rest = [r for r in rows if r["place"] is None]
        out.append({"division": division, "facet": facet,
                    "entries": placed + rest})
    return out
