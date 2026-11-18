"""Pre-convention contests: what an entry must be, and who the judges placed.

The endpoints in api.py do the authorization and the Drive round trip. This
module holds the rules, so the tests can reach them without HTTP:

    which division an entry belongs to     division_for
    whether a file is what it claims       check_file
    how long a piece of writing is         read_text, count_words
    what a length rule costs               penalty_for
    whether a judge's ranking is complete  check_ballot
    who is winning                         rank

BLIND JUDGING IS A RULE, NOT A COURTESY. Nothing a judge is sent carries a name,
a chapter, or the file name the student uploaded ("Jane Doe myth FINAL.docx").
`judge_view` is the one place that shapes an entry for a judge.
"""

from __future__ import annotations

import io
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
    """Every active contest. Six rows."""
    contests = []
    for row in tx.all("contests.all"):
        contest = dict(row)
        contest["facet_list"] = split_lines(contest["facets"])
        contest["accepted"] = [t for t in (contest["accepted_types"] or "").split(",") if t]
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
            "must_attend", "facet_list", "rules_md", "places")
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

def facets_of(contest: dict, row) -> list[str]:
    """The categories an entry is judged in: its Publicity facets, or [""]."""
    return split_lines(row["facets"]) if contest["facet_list"] else [""]


def groups_of(contest: dict, rows) -> list[tuple[str, str]]:
    """Every (division, facet) the entries fall into, in display order. Each is
    judged separately, and each judge hands in one ballot for each."""
    facet_order = {f: i for i, f in enumerate(contest["facet_list"])}
    seen = {(row["division"], facet) for row in rows for facet in facets_of(contest, row)}
    return sorted(seen, key=lambda g: (DIVISION_ORDER.get(g[0], 99), g[0],
                                       facet_order.get(g[1], 0)))


def places_needed(contest: dict, group_size: int) -> int:
    """How many entries a complete ballot ranks: N, or every entry if fewer."""
    return min(contest["places"], group_size)


def judge_view(contest: dict, rows: list, ballot_rows: list) -> dict:
    """Entries as a judge sees them, numbered and never named, and the judge's
    own ballots, one per division (and Publicity category).

    `ballot_rows` is contests.ballots_for_judge: one row per place, or one row
    with no place for an empty draft.
    """
    entries = [{
        "id": row["id"],
        "division": row["division"],
        "title": row["title"],
        "text": row["body_text"],
        "translation": row["translation"],
        "link_url": row["link_url"],
        "facets": facets_of(contest, row),
        "word_count": row["word_count"],
        "word_count_source": row["word_count_source"],
        "penalty": penalty_for(contest, row["word_count"]),
        "has_file": bool(row["has_file"]),
        "mime_type": row["mime_type"],
        "size_bytes": row["size_bytes"],
    } for row in rows]
    entries.sort(key=lambda e: (DIVISION_ORDER.get(e["division"], 99), e["id"]))

    ballots: dict[tuple[str, str], dict] = {}
    for row in ballot_rows:
        ballot = ballots.setdefault((row["division"], row["facet"]), {
            "status": row["status"], "comment": row["comment"],
            "updated_at": row["updated_at"], "places": {}})
        if row["place"] is not None:
            ballot["places"][str(row["entry_id"])] = row["place"]

    groups = []
    for division, facet in groups_of(contest, rows):
        ids = [e["id"] for e in entries
               if e["division"] == division and facet in e["facets"]]
        ballot = ballots.get((division, facet))
        needed = places_needed(contest, len(ids))
        groups.append({
            "division": division, "facet": facet, "entry_ids": ids,
            "needed": needed, "ballot": ballot,
            # Handed in, and still as long as N asks for -- N may have been
            # raised since.
            "complete": bool(ballot and ballot["status"] == "submitted"
                             and len(ballot["places"]) >= needed),
        })
    return {"entries": entries, "groups": groups}


def check_ballot(contest: dict, rows: list, payload: dict) -> dict:
    """A judge's ranking of one division, validated. Returns what to store.

    `places` maps entry id to place. A draft may leave places empty; a ballot
    handed in ranks exactly places 1..k, where k is N or the number of
    entries in the division if that is fewer.
    """
    division = str(payload.get("division") or "")
    facet = str(payload.get("facet") or "")
    if (division, facet) not in groups_of(contest, rows):
        raise ValidationError(["There are no entries to rank there."])
    in_group = {row["id"] for row in rows
                if row["division"] == division and facet in facets_of(contest, row)}

    given = payload.get("places") or {}
    if not isinstance(given, dict):
        raise ValidationError(["The ranking arrived in a shape this cannot read."])

    limit = contest["places"]
    by_place: dict[int, int] = {}
    seen: set[int] = set()
    errors = []
    for key, raw in given.items():
        if raw in (None, ""):
            continue
        try:
            entry_id = int(key)
            place = int(raw)
        except (TypeError, ValueError):
            errors.append("Every place must be a whole number.")
            continue
        if entry_id in seen:
            errors.append(f"Entry {entry_id} is listed twice.")
        elif entry_id not in in_group:
            errors.append(f"Entry {key} is not in {division}"
                          + (f", {facet}" if facet else "") + ".")
        elif not 1 <= place <= limit:
            errors.append(f"Entry {entry_id}: places run from 1 to {limit}.")
        elif place in by_place:
            errors.append(f"Entries {by_place[place]} and {entry_id} are both "
                          f"placed {ordinal(place)}. Give each place to one entry.")
        else:
            by_place[place] = entry_id
        seen.add(entry_id)
    if errors:
        raise ValidationError(errors)

    submit = bool(payload.get("submit"))
    needed = places_needed(contest, len(in_group))
    if submit:
        missing = [p for p in range(1, needed + 1) if p not in by_place]
        if missing:
            raise ValidationError([
                "Before handing this in, choose an entry for "
                + ", ".join(ordinal(p) for p in missing) + " place."])

    comment = str(payload.get("comment") or "").strip()[:2000] or None
    return {"division": division, "facet": facet, "comment": comment,
            "places": sorted(by_place.items()),
            "status": "submitted" if submit else "draft"}


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def rank(contest: dict, entries: list, ballots: list) -> list[dict]:
    """Standings per division and facet, from handed-in ballots only.

    HOW JUDGES' LISTS COMBINE. With N places, a judge's 1st is worth N points,
    their 2nd N-1, and so on down to 1 for their Nth; places beyond N (from a
    ballot handed in before N was lowered) are worth nothing. An entry's
    points are the sum over judges. One judge's list therefore comes out
    exactly as they ranked it.

    TIES. Equal points are broken by who has more 1st places, then more 2nds,
    and so on down to Nth. Entries still level after that share a place and
    the next place is skipped (1, 2, 2, 4).

    An entry whose creator is no longer attending is listed but not placed
    when the contest requires attendance -- the Convention Book's rule,
    applied here so nobody has to remember it at the awards table. Entries
    below move up.
    """
    n = contest["places"]
    votes: dict[tuple[int, str], list] = {}
    comments: dict[tuple[str, str], list] = {}
    counted: dict[tuple[str, str], set] = {}
    for row in ballots:
        key = (row["division"], row["facet"])
        name = f"{row['judge_first']} {row['judge_last']}".strip()
        if row["id"] not in counted.setdefault(key, set()):
            counted[key].add(row["id"])
            if row["comment"]:
                comments.setdefault(key, []).append({"name": name,
                                                     "comment": row["comment"]})
        if row["place"] is not None:
            votes.setdefault((row["entry_id"], row["facet"]), []).append(
                {"name": name, "place": row["place"]})

    groups: dict[tuple[str, str], list] = {}
    for row in entries:
        for facet in facets_of(contest, row):
            judged = sorted(votes.get((row["id"], facet), []),
                            key=lambda v: (v["place"], v["name"]))
            counts = [sum(1 for v in judged if v["place"] == p) for p in range(1, n + 1)]
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
                "votes": judged,
                "points": sum(max(0, n + 1 - v["place"]) for v in judged),
                "_counts": counts,
                "place": None,
                "awarded": False,
                "tie_broken": False,
            })

    out = []
    for key in groups_of(contest, entries):
        rows = groups[key]
        order = lambda r: (-r["points"], [-c for c in r["_counts"]])
        placed = sorted((r for r in rows if r["eligible"] and r["points"] > 0), key=order)
        previous, place = None, 0
        for index, row in enumerate(placed, 1):
            if order(row) != previous:
                place, previous = index, order(row)
            row["place"] = place
            row["awarded"] = place <= n
        # Placed and level on points only because of the tie-break: say so,
        # so the chairs can explain it at the awards table.
        for row in placed:
            row["tie_broken"] = any(o is not row and o["points"] == row["points"]
                                    and o["place"] != row["place"] for o in placed)
        rest = sorted((r for r in rows if r["place"] is None),
                      key=lambda r: (not r["eligible"], -r["points"], r["entry_id"]))
        for row in rows:
            del row["_counts"]
        division, facet = key
        out.append({"division": division, "facet": facet,
                    "ballots": len(counted.get(key, ())),
                    "comments": comments.get(key, []),
                    "entries": placed + rest})
    return out
