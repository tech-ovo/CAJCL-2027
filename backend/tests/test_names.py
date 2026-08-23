"""The name parser, against every fixture in docs/schema.md.

This is the most visible part of the demo and the most likely to embarrass us
live, so these tests are specific about exact output rather than checking that
something plausible came back.
"""

from __future__ import annotations

import pathlib

import pytest

from backend.lib.names import PARTICLES, parse_roster


def one(text: str, **kw):
    rows = parse_roster(text, **kw)
    assert len(rows) == 1, f"expected 1 row, got {[r.display_name for r in rows]}"
    return rows[0]


def names_of(row):
    return (row.first_name, row.middle_name, row.last_name, row.suffix)


# ---------------------------------------------------------------------------
# The fixture set from docs/schema.md
# ---------------------------------------------------------------------------

def test_last_comma_first_middle_with_a_particle():
    r = one("de la Cruz, Mary Beth")
    assert names_of(r) == ("Mary", "Beth", "de la Cruz", "")
    # Three units after folding is an ordinary name. It must not warn.
    assert r.warnings == []


def test_all_uppercase_is_title_cased_with_particles_left_lowercase():
    r = one("MARY BETH DE LA CRUZ")
    assert names_of(r) == ("Mary", "Beth", "de la Cruz", "")
    assert r.warnings == []


def test_all_lowercase_is_title_cased():
    r = one("mary beth de la cruz")
    assert names_of(r) == ("Mary", "Beth", "de la Cruz", "")
    assert r.warnings == []


def test_suffix_is_split_off_and_mc_casing_is_preserved():
    r = one("Robert McDonald Jr.")
    assert names_of(r) == ("Robert", "", "McDonald", "Jr.")
    assert r.warnings == []


def test_apostrophe_and_accent_survive_untouched():
    r = one("O'Brien, Seán")
    assert names_of(r) == ("Seán", "", "O'Brien", "")
    # An accented name is an ordinary name. Warning about it would be both
    # wrong and the kind of noise that trains sponsors to ignore warnings.
    assert r.warnings == []


def test_four_token_name_is_flagged_for_confirmation():
    r = one("Nguyễn Thị Minh Anh")
    assert names_of(r) == ("Nguyễn", "Thị Minh", "Anh", "")
    assert r.warnings == ["multi_token_name"]


def test_comma_separated_with_grade_and_level():
    r = one("Smith,John,9,HS-1")
    assert names_of(r) == ("John", "", "Smith", "")
    assert (r.grade, r.latin_level) == (9, "HS-1")
    assert r.warnings == []


def test_three_token_name_produces_no_warning():
    """The single most important fixture in this file.

    A middle name is ordinary. Flagging it would put a warning on a third of any
    real roster, which teaches sponsors to dismiss warnings without reading
    them -- and then they miss the duplicate that actually mattered.
    """
    r = one("Chen, Timothy Wei")
    assert names_of(r) == ("Timothy", "Wei", "Chen", "")
    assert r.warnings == []


def test_legacy_ap_latin_normalizes_silently():
    """We changed the vocabulary, not the sponsor. Their spreadsheet still says
    AP Latin and it should just work."""
    r = one("Liu,Carl,12,AP Latin")
    assert names_of(r) == ("Carl", "", "Liu", "")
    assert (r.grade, r.latin_level) == (12, "HS-Adv")
    assert r.warnings == []


def test_space_separated_with_grade_and_level():
    r = one("Rivera Ana 7 MS-2", school_level="MS")
    assert (r.first_name, r.last_name) == ("Rivera", "Ana")
    assert (r.grade, r.latin_level) == (7, "MS-2")


def test_tab_separated_paste_with_a_header_row():
    text = "Name\tGrade\tLatin Level\nChen, Timothy Wei\t11\tHS-3\nRivera, Ana\t9\tHS-1"
    rows = parse_roster(text)
    assert len(rows) == 3
    assert "possible_header_row" in rows[0].warnings
    assert names_of(rows[1]) == ("Timothy", "Wei", "Chen", "")
    assert (rows[1].grade, rows[1].latin_level) == (11, "HS-3")
    assert names_of(rows[2]) == ("Ana", "", "Rivera", "")


def test_numbered_list_has_its_numbering_stripped():
    text = "1. Timothy Chen\n2. Carl Liu\n3) Ana Rivera\n(4) Mary de la Cruz"
    rows = parse_roster(text)
    assert [r.display_name for r in rows] == [
        "Timothy Chen", "Carl Liu", "Ana Rivera", "Mary de la Cruz",
    ]
    assert all(r.warnings == [] for r in rows)


def test_identical_names_disambiguated_only_by_guardian_phone():
    rows = parse_roster("Ana Rivera\nAna Rivera")
    assert all("duplicate_in_paste" in r.warnings for r in rows)

    # Once the sponsor fills in different guardian phones in the preview, they
    # are two different students and the warning must clear.
    rows[0].guardian_phone = "555-0101"
    rows[1].guardian_phone = "555-0202"
    from backend.lib.names import _flag_duplicates
    for r in rows:
        r.warnings.clear()
    _flag_duplicates(rows, None)
    assert all(r.warnings == [] for r in rows)


def test_whitespace_only_lines_are_dropped():
    rows = parse_roster("Timothy Chen\n   \n\t\n\nCarl Liu")
    assert [r.display_name for r in rows] == ["Timothy Chen", "Carl Liu"]


def test_three_hundred_line_paste():
    text = "\n".join(f"Student{i} Testname{i}" for i in range(300))
    rows = parse_roster(text)
    assert len(rows) == 300
    assert not any(r.warnings for r in rows)


def test_zero_width_space_is_removed_and_flagged():
    """A name with an invisible character in it looks correct on screen and
    then never matches anything, so the sponsor has to be told."""
    r = one("Timothy​ Chen")
    assert names_of(r) == ("Timothy", "", "Chen", "")
    assert "unexpected_character" in r.warnings


# ---------------------------------------------------------------------------
# Warnings stay rare
# ---------------------------------------------------------------------------

def test_an_ordinary_roster_produces_no_warnings_at_all():
    """If this ever fails, sponsors will start clicking through warnings."""
    text = """Timothy Chen
Carl Liu
Mary Beth de la Cruz
Robert McDonald Jr.
Seán O'Brien
Ana Rivera
Priya Raghunathan
Jean-Luc Barthélemy
Kwame Osei-Bonsu
Yuki Tanaka"""
    rows = parse_roster(text)
    assert len(rows) == 10
    offenders = {r.display_name: r.warnings for r in rows if r.warnings}
    assert offenders == {}


def test_single_token_name_warns():
    r = one("Madonna")
    assert names_of(r) == ("", "", "Madonna", "")
    assert r.warnings == ["single_token_name"]


def test_ninety_character_name_is_accepted():
    long_last = "Wolfeschlegelsteinhausenbergerdorff" * 2
    r = one(f"Hubert {long_last}")
    assert r.last_name == long_last
    assert len(r.display_name) >= 70


# ---------------------------------------------------------------------------
# Particles
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("line,expected_last", [
    ("Ana de los Santos", "de los Santos"),
    ("Piet van der Berg", "van der Berg"),
    ("Klaus von Habsburg", "von Habsburg"),
    ("Marco della Rovere", "della Rovere"),
    ("Sofia da Silva", "da Silva"),
    ("Luca di Angelo", "di Angelo"),
    ("Omar ibn Rashid", "ibn Rashid"),
    ("Nur binte Hassan", "binte Hassan"),
    ("Jan ten Boom", "ten Boom"),
    ("Willem ter Horst", "ter Horst"),
])
def test_lowercase_particles_fold_into_the_last_name(line, expected_last):
    r = one(line)
    assert r.last_name == expected_last
    assert r.middle_name == ""
    assert r.warnings == []


def test_capitalised_particle_is_treated_as_a_middle_name():
    """`Van` written with a capital is a middle name, not a particle. That
    distinction is the only signal the input gives us."""
    r = one("Robert Van Houten")
    assert names_of(r) == ("Robert", "Van", "Houten", "")
    assert r.warnings == []


def test_the_particle_list_has_exactly_one_copy():
    """docs/schema.md says this list is canonical and lives in one constant.
    If a second copy appears, the two will drift and names will parse
    differently depending on which code path ran."""
    root = pathlib.Path(__file__).resolve().parents[2]
    holders = []
    for path in list(root.glob("backend/**/*.py")) + list(root.glob("frontend/**/*.js")):
        if path.name in ("names.py", "test_names.py"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        # "de los" and "binte" are distinctive enough that finding them
        # anywhere else means someone pasted the list.
        if '"de los"' in text or "'de los'" in text or "binte" in text:
            holders.append(str(path.relative_to(root)))
    assert holders == [], f"particle list duplicated in {holders}"


# ---------------------------------------------------------------------------
# Latin level normalisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("written,expected", [
    ("HS-4", "HS-Adv"), ("HS4", "HS-Adv"), ("Latin 4", "HS-Adv"),
    ("AP", "HS-Adv"), ("AP Latin", "HS-Adv"), ("hs-adv", "HS-Adv"),
    ("HS1", "HS-1"), ("hs 2", "HS-2"), ("HS-3", "HS-3"),
])
def test_high_school_latin_levels(written, expected):
    assert one(f"Carl Liu,{written}").latin_level == expected


@pytest.mark.parametrize("written,expected", [
    ("MS-1", "MS-1"), ("ms2", "MS-2"), ("MS 3", "MS-3"),
])
def test_middle_school_latin_levels(written, expected):
    assert one(f"Ana Rivera,{written}", school_level="MS").latin_level == expected


def test_bare_level_number_follows_the_chapter_type():
    """A bare 1-3 in a Latin column means MS-2 at a middle school and HS-2 at a
    high school. Grades are 6-12, so the two ranges never collide."""
    assert one("Ana Rivera,2", school_level="MS").latin_level == "MS-2"
    assert one("Carl Liu,2", school_level="HS").latin_level == "HS-2"


def test_grade_and_bare_level_coexist():
    r = one("Ana Rivera,7,2", school_level="MS")
    assert (r.grade, r.latin_level) == (7, "MS-2")


# ---------------------------------------------------------------------------
# Emails and phones
# ---------------------------------------------------------------------------

def test_delegate_email_is_discarded_with_a_warning():
    """Several delegates are eleven years old. We collect no contact
    information from them at all."""
    r = one("Timothy Chen,tim@example.com")
    assert r.email is None
    assert "email_discarded" in r.warnings


def test_adult_email_is_kept():
    r = one("Mark Michalak,mark@example.edu", default_person_type="adult")
    assert r.email == "mark@example.edu"
    assert "email_discarded" not in r.warnings


@pytest.mark.parametrize("phone", [
    "555-123-4567", "(555) 123-4567", "5551234567", "555.123.4567",
])
def test_phone_formats(phone):
    r = one(f"Mark Michalak,{phone}", default_person_type="adult")
    assert r.cell_phone is not None
    assert names_of(r)[0] == "Mark"


def test_embedded_email_without_a_delimiter():
    r = one("Mark Michalak mark@example.edu", default_person_type="adult")
    assert r.email == "mark@example.edu"
    assert names_of(r) == ("Mark", "", "Michalak", "")


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

def test_smart_quotes_and_trailing_punctuation_are_stripped():
    assert one("“Timothy Chen”,").display_name == "Timothy Chen"
    assert one("'Carl Liu';").display_name == "Carl Liu"


def test_mixed_delimiters_across_lines():
    text = "Chen, Timothy\nCarl Liu\nRivera\tAna\t9\tHS-1"
    rows = parse_roster(text)
    assert [r.display_name for r in rows] == ["Timothy Chen", "Carl Liu", "Ana Rivera"]


def test_all_line_ending_styles():
    for sep in ("\n", "\r\n", "\r"):
        rows = parse_roster(f"Timothy Chen{sep}Carl Liu")
        assert [r.display_name for r in rows] == ["Timothy Chen", "Carl Liu"]


def test_control_characters_are_flagged():
    assert "unexpected_character" in one("Timothy\x07 Chen").warnings


def test_unmatched_bracket_is_flagged():
    assert "unexpected_character" in one("Timothy Chen (11").warnings


def test_empty_input_yields_nothing():
    assert parse_roster("") == []
    assert parse_roster("   \n\t\n  ") == []


def test_duplicate_against_the_existing_roster():
    existing = [{"first_name": "Timothy", "last_name": "Chen", "guardian_phone": ""}]
    r = one("Timothy Chen", existing=existing)
    assert "duplicate_in_roster" in r.warnings


def test_existing_roster_duplicate_clears_when_guardians_differ():
    existing = [{"first_name": "Ana", "last_name": "Rivera", "guardian_phone": "555-0101"}]
    rows = parse_roster("Ana Rivera", existing=existing)
    rows[0].guardian_phone = "555-0202"
    from backend.lib.names import _flag_duplicates
    rows[0].warnings.clear()
    _flag_duplicates(rows, existing)
    assert rows[0].warnings == []


def test_parser_never_needs_a_database():
    """Stated as a hard rule in docs/structure.md: parsing never writes, and it
    should not read either. This module imports nothing that could."""
    import backend.lib.names as m
    source = pathlib.Path(m.__file__).read_text(encoding="utf-8")
    for forbidden in ("sqlite3", "libsql", "import requests", "httpx", "execute("):
        assert forbidden not in source, f"names.py references {forbidden}"


def test_school_level_must_be_valid():
    with pytest.raises(ValueError):
        parse_roster("Timothy Chen", school_level="ELEMENTARY")


def test_particles_constant_is_frozen():
    assert isinstance(PARTICLES, frozenset)
    assert "de la" in PARTICLES and "de los" in PARTICLES
