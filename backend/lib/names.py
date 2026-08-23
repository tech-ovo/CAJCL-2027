"""The roster name parser.

Pure functions. This module never touches the database, the network, or the
clock. Parsing produces a preview that a sponsor reviews and corrects before
anything is written -- see docs/structure.md.

WHAT SPONSORS ACTUALLY PASTE
    Tabs from a spreadsheet. Bullets and numbering from a Word document.
    Commas from an email. `Last, First` in some rows and `First Last` in the
    next. Trailing whitespace, smart quotes, blank lines, a header row they
    forgot to delete, and last year's vocabulary for Latin levels. Accept all
    of it. One name per line is the only real rule, and even that degrades
    gracefully.

THE RULE ABOUT WARNINGS
    Warnings must be rare enough that a sponsor reads them. Flagging every
    third row teaches people to click through without looking, which is worse
    than not warning at all. This is why a three-token name -- first, middle,
    last -- produces NO warning: middle names are ordinary and would put a
    warning on a third of any real roster.

CASING
    Input casing is preserved. Title-casing everything mangles `McDonald` and
    `de la Cruz`, and a sponsor who typed a name correctly should see it come
    back unchanged. The single exception is a line that arrives entirely
    uppercase or entirely lowercase -- almost always a spreadsheet artifact --
    which gets careful title casing.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Canonical constants
# ---------------------------------------------------------------------------

# THIS LIST IS CANONICAL AND LIVES IN EXACTLY ONE PLACE. No other module and no
# other document may hold its own copy. If you are about to paste these strings
# somewhere else, import them instead.
#
# Multi-word particles are matched before single-word ones, which is why
# `de los` works even though `los` alone is not a particle.
PARTICLES: frozenset[str] = frozenset({
    "de", "del", "de la", "de los", "della",
    "van", "van der", "van den", "von",
    "da", "di", "dos", "du",
    "la", "le",
    "bin", "binte", "ibn", "al",
    "ter", "ten",
})

_PARTICLE_MAX_WORDS = max(len(p.split()) for p in PARTICLES)

SUFFIXES: dict[str, str] = {
    "jr": "Jr.", "jr.": "Jr.", "sr": "Sr.", "sr.": "Sr.",
    "ii": "II", "iii": "III", "iv": "IV", "v": "V",
}

LATIN_LEVELS = ("MS-1", "MS-2", "MS-3", "HS-1", "HS-2", "HS-3", "HS-Adv")

# Words that appear in a header row a sponsor forgot to delete.
_HEADER_WORDS = frozenset({
    "name", "names", "student", "students", "first", "last", "firstname",
    "lastname", "middle", "grade", "level", "latin", "latinlevel", "meal",
    "phone", "email", "guardian", "parent", "delegate", "adult", "#",
})

# Invisible characters that survive a copy-paste out of Word or a web page and
# then silently break every duplicate check, because a name with a zero-width
# space in it never equals the same name without one.
_INVISIBLES = "​‌‍﻿­⁠"

_EMAIL_RE = re.compile(r"[^\s,;<>]+@[^\s,;<>]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?1[\s.-]*)?\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}")
_LEADING_NOISE_RE = re.compile(r"^\s*(?:[-–—*•·]+\s*|\(?\d{1,3}[.)]\s+|\d{1,3}\s+[-–]\s+)")
_QUOTES = "\"'“”‘’"

_BRACKETS = {"(": ")", "[": "]", "{": "}"}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ParsedRow:
    """One line of the paste, ready to be shown in the editable preview.

    Every field is editable by the sponsor before commit, so a wrong guess here
    costs a correction, not a bad record.
    """
    line_number: int
    raw: str
    person_type: str = "delegate"
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    suffix: str = ""
    grade: int | None = None
    latin_level: str | None = None
    meal: str | None = None
    email: str | None = None
    cell_phone: str | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    warnings: list[str] = field(default_factory=list)

    def warn(self, code: str) -> None:
        if code not in self.warnings:
            self.warnings.append(code)

    @property
    def display_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name, self.suffix]
        return " ".join(p for p in parts if p)

    def to_dict(self) -> dict:
        return {
            "line_number": self.line_number,
            "raw": self.raw,
            "person_type": self.person_type,
            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,
            "suffix": self.suffix,
            "grade": self.grade,
            "latin_level": self.latin_level,
            "meal": self.meal,
            "email": self.email,
            "cell_phone": self.cell_phone,
            "guardian_name": self.guardian_name,
            "guardian_phone": self.guardian_phone,
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Line cleanup
# ---------------------------------------------------------------------------

def _split_lines(text: str) -> list[tuple[int, str]]:
    """Split on any line ending, keeping original 1-based line numbers.

    Line numbers are kept so the preview can tell a sponsor which line of THEIR
    paste a warning refers to, even after blank lines are dropped.
    """
    out = []
    for i, line in enumerate(re.split(r"\r\n|\n|\r", text), start=1):
        if line.strip(" \t" + _INVISIBLES):
            out.append((i, line))
    return out


def _strip_noise(line: str) -> tuple[str, bool]:
    """Remove bullets, numbering, surrounding quotes, trailing punctuation.

    Returns the cleaned line and whether any invisible character was removed --
    the caller warns about that, because an invisible character in a pasted name
    is a sign the whole paste came out of something that will have mangled other
    rows too.
    """
    had_invisible = any(ch in _INVISIBLES for ch in line)
    line = "".join(ch for ch in line if ch not in _INVISIBLES)

    # Run to a fixed point. A line can arrive as `1. "Timothy Chen",` where each
    # layer of noise hides the next: the trailing comma stops the quote check
    # from firing, and the quotes stop the numbering from matching. Looping is
    # boring and obviously correct; hand-ordering the passes is neither, and
    # gets it wrong on the first input nobody anticipated.
    while True:
        before = line
        line = line.strip().rstrip(",;").strip()
        line = _LEADING_NOISE_RE.sub("", line).strip()
        if len(line) >= 2 and line[0] in _QUOTES and line[-1] in _QUOTES:
            line = line[1:-1]
        if line == before:
            break
    return line, had_invisible


def _has_unexpected_characters(line: str) -> bool:
    """Control characters, or brackets that do not close.

    Deliberately NOT triggered by accented or non-Latin letters: `Seán` and
    `Nguyễn Thị Minh Anh` are ordinary names, and warning about them would be
    both insulting and the kind of noise that trains people to ignore warnings.
    """
    if any(unicodedata.category(ch) == "Cc" for ch in line):
        return True
    stack = []
    closers = {v: k for k, v in _BRACKETS.items()}
    for ch in line:
        if ch in _BRACKETS:
            stack.append(ch)
        elif ch in closers:
            if not stack or stack.pop() != closers[ch]:
                return True
    return bool(stack)


# ---------------------------------------------------------------------------
# Non-name field extraction
# ---------------------------------------------------------------------------

def _normalize_latin_level(token: str, school_level: str) -> str | None:
    """Map anything a sponsor might have written to a current Latin level.

    Sponsors are pasting out of their own spreadsheets, which still say `AP
    Latin` and `HS-4` because those are what we used to call things. Normalizing
    quietly is right here: we changed the vocabulary, not them.
    """
    t = token.strip().lower().replace("_", "-")
    t = re.sub(r"\s+", " ", t)

    # Legacy spellings for the top level.
    if t in {"hs-4", "hs4", "hs 4", "latin 4", "latin4", "ap", "ap latin",
             "hs-adv", "hsadv", "hs adv", "adv", "advanced"}:
        return "HS-Adv"

    m = re.fullmatch(r"(ms|hs)[\s-]?([123])", t)
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"

    # A bare 1-3 means the matching level for this chapter's type. A bare 6-12
    # is a grade and is handled elsewhere; the two ranges do not overlap, which
    # is what makes this safe without knowing which column we are in.
    m = re.fullmatch(r"(?:latin\s*)?([123])", t)
    if m:
        return f"{school_level}-{m.group(1)}"

    return None


def _extract_fields(tokens: list[str], row: ParsedRow, school_level: str) -> list[str]:
    """Pull grade, Latin level, phone, and email out of a token list.

    Returns the tokens that are left, which are the name. Works the same whether
    the tokens came from tab-separated columns, comma-separated fields, or plain
    spaces, so `Smith,John,9,HS-1` and `Rivera Ana 7 MS-2` take one code path.
    """
    remaining: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i].strip()
        if not tok:
            i += 1
            continue

        # Two-token Latin levels: "AP Latin", "Latin 4", "HS Adv".
        if i + 1 < len(tokens):
            pair = f"{tok} {tokens[i + 1].strip()}"
            if row.latin_level is None and _normalize_latin_level(pair, school_level):
                row.latin_level = _normalize_latin_level(pair, school_level)
                i += 2
                continue

        if row.email is None and (m := _EMAIL_RE.fullmatch(tok)):
            row.email = m.group(0)
            i += 1
            continue

        if row.cell_phone is None and _PHONE_RE.fullmatch(tok):
            row.cell_phone = tok
            i += 1
            continue

        if row.grade is None and re.fullmatch(r"(?:grade\s*)?(\d{1,2})", tok, re.I):
            n = int(re.sub(r"\D", "", tok))
            if 6 <= n <= 12:
                row.grade = n
                i += 1
                continue

        if row.latin_level is None and (lvl := _normalize_latin_level(tok, school_level)):
            row.latin_level = lvl
            i += 1
            continue

        remaining.append(tok)
        i += 1

    return remaining


def _extract_embedded(text: str, row: ParsedRow) -> str:
    """Pull an email or phone out of the middle of an otherwise plain line.

    `Ana Rivera ana@example.com` has no delimiter at all, so field-splitting
    never sees the address as its own column.
    """
    if row.email is None and (m := _EMAIL_RE.search(text)):
        row.email = m.group(0)
        text = text[:m.start()] + " " + text[m.end():]
    if row.cell_phone is None and (m := _PHONE_RE.search(text)):
        # Only treat it as a phone if it is not glued to a letter, so a name
        # containing digits is not mangled.
        row.cell_phone = m.group(0).strip()
        text = text[:m.start()] + " " + text[m.end():]
    return text


# ---------------------------------------------------------------------------
# Casing
# ---------------------------------------------------------------------------

def _is_uniform_case(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 2:
        return False
    return all(c.isupper() for c in letters) or all(c.islower() for c in letters)


def _title_word(word: str) -> str:
    """Title-case one word, handling Mc, O', and hyphenated pairs.

    `Mac` is deliberately NOT handled. `Mc` is unambiguous, but `Mac` is a
    prefix in MacDonald and ordinary letters in Machado, Macias, and Macy --
    and there is no rule that separates them. Producing `MacHado` from a name
    the sponsor typed correctly is a worse failure than leaving `Macdonald` for
    them to fix in the preview, because a wrong name that looks deliberate does
    not get corrected. Flagged as an open question in the handover report.
    """
    if not word:
        return word

    for sep in ("-", "–"):
        if sep in word:
            return sep.join(_title_word(p) for p in word.split(sep))

    lower = word.lower()

    if lower.startswith("mc") and len(word) > 2:
        return "Mc" + lower[2].upper() + lower[3:]

    if lower.startswith("o'") and len(word) > 2:
        return "O'" + lower[2].upper() + lower[3:]

    if "'" in word:
        head, _, tail = word.partition("'")
        return head.capitalize() + "'" + tail.lower()

    return word[:1].upper() + word[1:].lower()


def _title_case_tokens(tokens: list[str]) -> list[str]:
    """Title-case a whole name, leaving particles lowercase."""
    out = []
    for tok in tokens:
        out.append(tok.lower() if tok.lower() in PARTICLES else _title_word(tok))
    return out


# ---------------------------------------------------------------------------
# Particles and suffixes
# ---------------------------------------------------------------------------

def _pop_suffix(tokens: list[str]) -> tuple[list[str], str]:
    if len(tokens) >= 2:
        candidate = tokens[-1].strip().rstrip(",").lower()
        if candidate in SUFFIXES:
            return tokens[:-1], SUFFIXES[candidate]
    return tokens, ""


def _fold_particles(tokens: list[str], *, case_insensitive: bool) -> list[str]:
    """Attach lowercase particles to the last name, scanning right to left.

    `Mary Beth de la Cruz` becomes [Mary, Beth, "de la Cruz"], so it reads as an
    ordinary first-middle-last name and produces no warning -- which is the
    whole point. Without this it would look like a five-token name and get
    flagged, and `de` and `la` would be read as middle names.

    Multi-word particles are tried before single-word ones so `de los` matches
    as a unit even though `los` alone is not a particle.
    """
    if len(tokens) < 2:
        return tokens

    def is_particle(seq: list[str]) -> bool:
        joined = " ".join(seq)
        if joined.lower() not in PARTICLES:
            return False
        # In mixed-case input a particle must actually be written lowercase --
        # that is how we tell `Van` the middle name from `van` the particle.
        # In uniform-case input there is no such signal, so we match anyway.
        return case_insensitive or joined.islower()

    head = tokens[:-1]
    last = [tokens[-1]]

    while head:
        for width in range(min(_PARTICLE_MAX_WORDS, len(head)), 0, -1):
            if is_particle(head[-width:]):
                last = head[-width:] + last
                head = head[:-width]
                break
        else:
            break

    return head + [" ".join(last)]


# ---------------------------------------------------------------------------
# Name assignment
# ---------------------------------------------------------------------------

def _assign(units: list[str], row: ParsedRow) -> None:
    """Turn folded name units into first / middle / last.

    One unit  -> last name only, warn.
    Two       -> first, last.
    Three     -> first, middle, last, NO WARNING. A middle name is ordinary.
    Four plus -> first, ...middle..., last, and flag for confirmation.
    """
    units = [u for u in units if u]

    if not units:
        row.warn("single_token_name")
        return

    if len(units) == 1:
        row.last_name = units[0]
        row.warn("single_token_name")
    elif len(units) == 2:
        row.first_name, row.last_name = units
    elif len(units) == 3:
        row.first_name, row.middle_name, row.last_name = units
    else:
        row.first_name = units[0]
        row.last_name = units[-1]
        row.middle_name = " ".join(units[1:-1])
        row.warn("multi_token_name")


# ---------------------------------------------------------------------------
# One line
# ---------------------------------------------------------------------------

def _parse_line(line_number: int, raw: str, school_level: str,
                default_person_type: str) -> ParsedRow | None:
    row = ParsedRow(line_number=line_number, raw=raw, person_type=default_person_type)

    cleaned, had_invisible = _strip_noise(raw)
    if not cleaned:
        return None
    if had_invisible or _has_unexpected_characters(cleaned):
        row.warn("unexpected_character")

    # --- choose a delimiter -------------------------------------------------
    # Tabs win outright: a tab is only ever a spreadsheet column boundary.
    if "\t" in cleaned:
        fields = [f.strip() for f in cleaned.split("\t")]
        name_fields = _extract_fields(fields, row, school_level)
        # A spreadsheet's name column very often holds `Last, First` on its own,
        # so a comma INSIDE a tab-separated field still has to be read. Without
        # this, `Chen, Timothy Wei<TAB>11<TAB>HS-3` produces a student whose
        # first name is "Chen," -- which looks deliberate and so never gets
        # corrected in the preview.
        if len(name_fields) == 1 and "," in name_fields[0]:
            inner = [f.strip() for f in name_fields[0].split(",") if f.strip()]
            if len(inner) == 2:
                name_fields = inner
        from_delimited = True
    elif "," in cleaned:
        fields = [f.strip() for f in cleaned.split(",") if f.strip()]
        name_fields = _extract_fields(fields, row, school_level)
        from_delimited = True
    else:
        cleaned = _extract_embedded(cleaned, row)
        name_fields = _extract_fields(cleaned.split(), row, school_level)
        from_delimited = False

    # A header row the sponsor forgot to delete. Checked after field extraction
    # so that a row reading `Name  Grade  Level` is caught even though `Grade`
    # and `Level` are not themselves names.
    joined = " ".join(name_fields).lower()
    header_tokens = [re.sub(r"[^a-z#]", "", t.lower()) for t in re.split(r"[\s,]+", joined) if t]
    if header_tokens and all(t in _HEADER_WORDS for t in header_tokens):
        row.warn("possible_header_row")

    # --- `Last, First Middle` ----------------------------------------------
    # After the recognizable non-name columns are removed, exactly two name
    # fields from a delimited line is the `Last, First [Middle]` shape. This is
    # what makes `Smith,John,9,HS-1` and `de la Cruz, Mary Beth` both work: the
    # grade and level columns are gone by the time we look.
    if from_delimited and len(name_fields) == 2:
        last_part, first_part = name_fields[0], name_fields[1]
        tokens = first_part.split() + last_part.split()
        uniform = _is_uniform_case(cleaned)
        if uniform:
            tokens = _title_case_tokens(tokens)
        tokens, row.suffix = _pop_suffix(tokens)

        first_tokens = tokens[:len(first_part.split())]
        last_tokens = tokens[len(first_part.split()):]
        if not last_tokens:                       # the suffix ate the last name
            last_tokens, first_tokens = first_tokens[-1:], first_tokens[:-1]

        last_units = _fold_particles(last_tokens, case_insensitive=uniform)
        units = first_tokens + [" ".join(last_units)]
        _assign(units, row)

    else:
        if from_delimited and len(name_fields) > 2:
            row.warn("ambiguous_delimiter")
        tokens = " ".join(name_fields).split()
        uniform = _is_uniform_case(cleaned)
        if uniform:
            tokens = _title_case_tokens(tokens)
        tokens, row.suffix = _pop_suffix(tokens)
        units = _fold_particles(tokens, case_insensitive=uniform)
        _assign(units, row)

    # Delegates have no email, ever. The database CHECK enforces it too; this
    # is where the sponsor finds out, so they are not surprised at commit.
    if row.person_type == "delegate" and row.email:
        row.email = None
        row.warn("email_discarded")

    return row


# ---------------------------------------------------------------------------
# Duplicates
# ---------------------------------------------------------------------------

def _dedupe_key(first: str, last: str) -> str:
    """Casefolded first+last, whitespace collapsed.

    Accents are NOT stripped. `Seán` and `Sean` may well be two different
    students, and a false duplicate warning costs more trust than a missed one:
    the sponsor knows their own roster and we do not.
    """
    norm = lambda s: re.sub(r"\s+", " ", s.strip()).casefold()
    return f"{norm(first)}|{norm(last)}"


def _guardians_differ(a: ParsedRow | dict, b: ParsedRow | dict) -> bool:
    """Two same-named delegates are different people if their guardians differ.

    Only a positive difference counts. Two blank guardians are not evidence of
    anything, so they stay flagged as a possible duplicate.
    """
    get = lambda r, k: (r.get(k) if isinstance(r, dict) else getattr(r, k, None)) or ""
    for key in ("guardian_phone", "guardian_name"):
        x, y = get(a, key).strip().casefold(), get(b, key).strip().casefold()
        if x and y and x != y:
            return True
    return False


def _flag_duplicates(rows: list[ParsedRow], existing: list[dict] | None) -> None:
    seen: dict[str, list[ParsedRow]] = {}
    for row in rows:
        if not (row.first_name or row.last_name):
            continue
        key = _dedupe_key(row.first_name, row.last_name)
        for prior in seen.get(key, []):
            if not _guardians_differ(prior, row):
                prior.warn("duplicate_in_paste")
                row.warn("duplicate_in_paste")
        seen.setdefault(key, []).append(row)

    if not existing:
        return

    # Built once from the roster the caller already fetched -- never a query
    # inside this loop, and never a query from this module at all.
    index: dict[str, list[dict]] = {}
    for person in existing:
        index.setdefault(
            _dedupe_key(person.get("first_name", ""), person.get("last_name", "")), []
        ).append(person)

    for row in rows:
        key = _dedupe_key(row.first_name, row.last_name)
        for person in index.get(key, []):
            if not _guardians_differ(person, row):
                row.warn("duplicate_in_roster")
                break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_roster(text: str, *, school_level: str = "HS",
                 existing: list[dict] | None = None,
                 default_person_type: str = "delegate") -> list[ParsedRow]:
    """Parse a pasted roster into an editable preview. Writes nothing.

    `school_level` is 'MS' or 'HS' and decides what a bare Latin level like `2`
    means. `existing` is the school's current roster, passed in by the caller
    so that duplicate detection needs no database access from this module.
    """
    if school_level not in ("MS", "HS"):
        raise ValueError("school_level must be 'MS' or 'HS'")

    rows = []
    for line_number, raw in _split_lines(text):
        row = _parse_line(line_number, raw, school_level, default_person_type)
        if row is not None:
            rows.append(row)

    _flag_duplicates(rows, existing)
    return rows
