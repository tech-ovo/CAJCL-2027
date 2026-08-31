"""The schema's own guarantees.

These tests exist because docs/schema.md asks for them explicitly: the
person-type CHECK constraints are the database-level enforcement of rules that
application code will eventually forget, and a future migration could quietly
drop them. If one of these tests fails, the protection is gone even though every
endpoint still looks correct.
"""

from __future__ import annotations

import pathlib
import sqlite3

import pytest

from .conftest import make_person


# ---------------------------------------------------------------------------
# The person-type split
# ---------------------------------------------------------------------------

def test_delegate_cannot_have_an_email(db, school):
    """Several delegates are eleven years old. We collect no contact
    information from them at all -- everything routes through the sponsor."""
    with pytest.raises(sqlite3.IntegrityError):
        make_person(db, school, person_type="delegate", email="kid@example.com")


def test_delegate_cannot_have_latin_knowledge_or_availability(db, school):
    with pytest.raises(sqlite3.IntegrityError):
        make_person(db, school, person_type="delegate", latin_knowledge="advanced")
    with pytest.raises(sqlite3.IntegrityError):
        make_person(db, school, person_type="delegate", availability_note="Fridays only")


def test_adult_cannot_have_guardian_fields(db, school):
    with pytest.raises(sqlite3.IntegrityError):
        make_person(db, school, person_type="adult", adult_type="chaperone",
                    code_prefix="VOL", guardian_name="Someone")
    with pytest.raises(sqlite3.IntegrityError):
        make_person(db, school, person_type="adult", adult_type="chaperone",
                    code_prefix="VOL", guardian_phone="555-0100")


def test_adult_cannot_have_grade_or_latin_level(db, school):
    with pytest.raises(sqlite3.IntegrityError):
        make_person(db, school, person_type="adult", adult_type="sponsor",
                    code_prefix="SPO", grade=11)
    with pytest.raises(sqlite3.IntegrityError):
        make_person(db, school, person_type="adult", adult_type="sponsor",
                    code_prefix="SPO", latin_level="HS-2")


def test_delegate_cannot_have_an_adult_type(db, school):
    with pytest.raises(sqlite3.IntegrityError):
        make_person(db, school, person_type="delegate", adult_type="sponsor")


def test_the_legitimate_shapes_are_accepted(db, school):
    """The constraints must not be so tight that real people cannot be stored."""
    make_person(db, school, _hmac_seed="d", person_type="delegate", grade=9,
                latin_level="HS-1", meal="vegetarian",
                guardian_name="A Guardian", guardian_phone="555-0101")
    make_person(db, school, _hmac_seed="a", person_type="adult",
                adult_type="sponsor", code_prefix="SPO",
                email="teacher@example.edu", latin_knowledge="advanced",
                availability_note="Saturday morning only", meal="regular",
                cell_phone="555-0102")
    assert db.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 2


# ---------------------------------------------------------------------------
# Codes
# ---------------------------------------------------------------------------

def test_code_hmac_is_globally_unique(db, school):
    """Two people sharing a code hash would make login ambiguous. The unique
    index is also what makes login an O(1) lookup rather than a scan."""
    make_person(db, school, _hmac_seed="same")
    with pytest.raises(sqlite3.IntegrityError):
        make_person(db, school, _hmac_seed="same")


def test_code_prefix_is_constrained(db, school):
    with pytest.raises(sqlite3.IntegrityError):
        make_person(db, school, code_prefix="XXX")


# ---------------------------------------------------------------------------
# The audit log is append-only
# ---------------------------------------------------------------------------

def _one_audit_row(db):
    db.execute(
        "INSERT INTO audit_log (ts_utc, action, summary) "
        "VALUES ('2026-09-01T00:00:00Z', 'school.create', 'Someone created a school.')"
    )


def test_audit_log_rejects_update(db):
    _one_audit_row(db)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("UPDATE audit_log SET summary = 'rewritten'")


def test_audit_log_rejects_delete(db):
    _one_audit_row(db)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("DELETE FROM audit_log")


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------

def test_public_stats_cache_holds_exactly_one_row(db):
    db.execute(
        "INSERT INTO public_stats_cache (id, schools_ms, schools_hs, delegates, adults, updated_at) "
        "VALUES (1, 0, 0, 0, 0, '2026-09-01T00:00:00Z')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO public_stats_cache (id, schools_ms, schools_hs, delegates, adults, updated_at) "
            "VALUES (2, 0, 0, 0, 0, '2026-09-01T00:00:00Z')"
        )


def test_there_is_no_way_to_attach_a_scope_to_a_person_directly(db):
    """Scopes reach a person only through person_roles -> roles -> role_scopes.

    Every authorization test in this suite assumes that path is the only one. A
    person_scopes table appearing here would make all of them a lie.
    """
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "person_scopes" not in tables
    columns = {r[1] for r in db.execute("PRAGMA table_info(people)")}
    assert not any("scope" in c for c in columns)


def test_paper_form_type_is_constrained(db, school):
    """A delegate acquiring an 'adult_medical' row would make the roster query
    return that person twice, silently double-counting them."""
    pid = make_person(db, school)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO paper_forms (person_id, form_type) VALUES (?, 'nonsense')", (pid,)
        )


# ---------------------------------------------------------------------------
# Seeds
# ---------------------------------------------------------------------------

def test_system_roles_and_their_scopes(db):
    got = {
        row["key"]: set((row["scopes"] or "").split(","))
        for row in db.execute(
            "SELECT r.key, group_concat(rs.scope) AS scopes FROM roles r "
            "LEFT JOIN role_scopes rs ON rs.role_id = r.id GROUP BY r.id"
        )
    }
    assert got == {
        "admin": {"*"},
        "registration_chair": {"registration"},
        "academics_chair": {"academics"},
        "awards_chair": {"awards"},
        # A sponsor manages chapter team entries too.
        "sponsor": {"sponsor", "chapter"},
        "delegate": {"delegate"},
        "chapter_leader": {"chapter"},
    }


def test_system_roles_are_marked_undeletable(db):
    assert db.execute("SELECT COUNT(*) FROM roles WHERE is_system = 0").fetchone()[0] == 0


def test_academic_testing_blocks_at_one_to_three(db):
    row = db.execute(
        "SELECT min_selections, max_selections, enforcement FROM catalog_categories "
        "WHERE key = 'academic_testing'"
    ).fetchone()
    assert (row[0], row[1], row[2]) == (1, 3, "block")


def test_adult_roles_warn_at_two(db):
    row = db.execute(
        "SELECT min_selections, enforcement FROM catalog_categories WHERE key = 'adult_roles'"
    ).fetchone()
    assert (row[0], row[1]) == (2, "warn")


def test_chapter_events_are_not_individually_registrable(db):
    """Kickball, Fugepilam, and Ultimate Frisbee are chapter entries. If one of
    these ever became 'individual' it would appear on every delegate's activity
    sheet and the athletics chair would get 400 kickball signups."""
    got = {
        r[0] for r in db.execute(
            "SELECT name FROM catalog_items WHERE registration_scope = 'chapter'"
        )
    }
    assert got == {"Kickball", "Fugepilam (Dodgeball)", "Ultimate Frisbee"}


def test_the_forms_deadline_is_end_of_day_in_california(db):
    """February 13, 2027 is in PST (UTC-8), so end of day is 07:59:59Z on the
    14th. Storing '2027-02-13T23:59:59Z' would lock delegates out eight hours
    early, in the middle of the last afternoon anyone actually uses."""
    value = db.execute(
        "SELECT value FROM settings WHERE key = 'deadline.forms_lock'"
    ).fetchone()[0]
    assert value == "2027-02-14T07:59:59Z"


def test_the_theme_needs_latin_extended_a(db):
    """The macrons are the reason the font subset must include Latin
    Extended-A. scripts/check_fonts.py fails the build on this exact string."""
    theme = db.execute(
        "SELECT value FROM settings WHERE key = 'convention.theme_latin'"
    ).fetchone()[0]
    assert theme == "aequam mementō rēbus in arduīs servāre mentem"
    assert any(ord(ch) > 0x7F for ch in theme)


def test_a_reset_wipes_before_it_migrates(tmp_path):
    """`setup --reset` has to work on the one database that cannot migrate.

    Migrating compares each file against the hash recorded when it first ran,
    so a database holding migrations that no longer exist -- after a deliberate
    consolidation -- refuses to migrate at all. That is exactly the database
    somebody reaches for `--reset` to fix.

    The wipe used to live inside `seed_database`, which `setup` called AFTER
    `migrate_database`. So the reset failed on the migrate step and never
    reached the wipe that was the whole point of asking for it, and the only
    way out was a console.
    """
    import sqlite3

    from backend.lib import migrate
    from backend.lib.db import connect
    import scripts.seed as seed_script

    path = str(tmp_path / "reset.db")
    database = connect(path)
    migrate.run(database)
    database.close()

    # A recorded hash that no longer matches the file on disk.
    raw = sqlite3.connect(path)
    raw.execute("UPDATE schema_migrations SET sha256 = 'stale' WHERE filename = ?",
                ("001_core.sql",))
    raw.commit()
    raw.close()

    database = connect(path)
    try:
        with pytest.raises(SystemExit):
            migrate.run(database)          # the state the user was stuck in

        seed_script.wipe(database)
        assert migrate.run(database) > 0, "a wiped database must migrate cleanly"
    finally:
        database.close()


def test_setup_passes_the_reset_through_to_the_migrate_step():
    """The ordering above only holds if `setup` actually asks for it."""
    source = (pathlib.Path(__file__).resolve().parents[2]
              / "backend" / "app.py").read_text(encoding="utf-8")
    body = source[source.index("def setup("):source.index("# ---", source.index("def setup("))]

    assert "migrate_database.remote(reset=reset)" in body, (
        "setup must hand the reset to the migrate step, which is the only "
        "place that can wipe before the hash check runs")
    assert "seed_database.remote(reset=False)" in body, (
        "the wipe has already happened by then; doing it twice would drop the "
        "schema that was just built")


def test_schema_md_documents_every_column_that_exists(tmp_path):
    """`docs/schema.md` is the authority on data, so it has to be true.

    It had drifted on four tables: eight counter columns added by one
    migration, the printed person number added by another, a column that was
    deliberately dropped and left documented. Nothing failed, because a
    document cannot fail -- which is exactly why this check exists.

    Comments and constraints are not checked, only that every column in the
    database appears in the block that claims to describe it, and that no
    column is described which does not exist.
    """
    import re
    import sqlite3

    from backend.lib import migrate
    from backend.lib.db import connect

    path = str(tmp_path / "documented.db")
    database = connect(path)
    migrate.run(database)
    database.close()

    doc = (pathlib.Path(__file__).resolve().parents[2]
           / "docs" / "schema.md").read_text(encoding="utf-8")
    raw = sqlite3.connect(path)

    problems = []
    for match in re.finditer(r"CREATE TABLE (\w+) \((.*?)\n\);", doc, re.S):
        table, block = match.group(1), match.group(2)
        try:
            real = [r[1] for r in raw.execute(f'PRAGMA table_info("{table}")')]
        except sqlite3.Error:
            continue
        if not real:
            problems.append(f"{table} is documented and does not exist")
            continue
        documented = set(re.findall(r"^\s{2}(\w+)\s", block, re.M))
        for column in real:
            if column not in documented:
                problems.append(f"{table}.{column} exists and is not documented")
        for column in documented - set(real):
            if column in ("UNIQUE", "CHECK", "PRIMARY", "FOREIGN"):
                continue
            problems.append(f"{table}.{column} is documented and does not exist")
    raw.close()

    assert problems == [], (
        "docs/schema.md has drifted from the migrations:\n  "
        + "\n  ".join(problems))
