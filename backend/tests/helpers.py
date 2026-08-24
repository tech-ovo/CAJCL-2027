"""A small, real world for tests: two chapters, a state board, and one of each
kind of person.

TWO schools, always. A single-school fixture cannot catch the bug this system
most needs to avoid -- a sponsor at one school reading another school's roster --
because there is no other school to read.
"""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

# Set before anything imports auth, so the pepper is deterministic across a run.
os.environ.setdefault("CODE_PEPPER", "test-pepper")

from backend.lib import auth, clock, settings, stats  # noqa: E402
from backend.lib.db import connect  # noqa: E402
from backend.lib.migrate import migration_files  # noqa: E402


class Fixture:
    """A migrated, seeded database plus a handful of people and their codes."""

    def __init__(self, tmp_path):
        self.path = str(pathlib.Path(tmp_path) / "test.db")
        self.codes: dict[str, str] = {}
        self._principals: dict[str, int] = {}

    def __enter__(self) -> "Fixture":
        import sqlite3

        raw = sqlite3.connect(self.path)
        raw.execute("PRAGMA foreign_keys = ON")
        for path in migration_files():
            raw.executescript(path.read_text(encoding="utf-8"))
        raw.close()

        settings.invalidate()
        self.db = connect(self.path)
        self._build()
        return self

    def __exit__(self, *exc) -> None:
        settings.invalidate()
        self.db.close()

    # -- construction -------------------------------------------------------

    def _school(self, tx, name, level, *, kind="chapter", exempt=0,
                discount_cents=0, discount_reason=None) -> int:
        school_id = tx.insert("schools.create", (
            name, level, kind, "Irvine", exempt,
            discount_cents, discount_reason, None,
            clock.now_iso(), clock.now_iso()))
        tx.run("schools.stats_init", (school_id, clock.now_iso()))
        return school_id

    def _person(self, tx, key, school_id, *, person_type="delegate",
                adult_type=None, first="Test", last="Person", role=None,
                **extra) -> int:
        person_id = tx.insert("people.create", (
            school_id, person_type, adult_type, None,
            first, extra.get("middle"), last, None, None,
            extra.get("grade"), extra.get("latin_level"), extra.get("meal"), None,
            extra.get("email"), extra.get("latin_knowledge"), None,
            extra.get("guardian_name"), extra.get("guardian_phone"),
            f"placeholder-{key}", "DEL", 1, clock.now_iso(),
            clock.now_iso(), clock.now_iso(), None))

        if role:
            role_row = tx.one("roles.by_key", (role,))
            tx.run("people.grant_role",
                   (person_id, role_row["id"], None, clock.now_iso()))

        prefix = auth.code_prefix_for(person_type, adult_type)
        self.codes[key] = auth.issue_code(tx, person_id, prefix)
        self._principals[key] = person_id
        return person_id

    def _build(self) -> None:
        with self.db.tx() as tx:
            self.board_id = self._school(tx, "CAJCL State Board", "HS", kind="organization")
            self.uni_id = self._school(tx, "University High School", "HS")
            self.other_id = self._school(tx, "Rival High School", "HS")
            self.exempt_id = self._school(tx, "SCL", "HS", exempt=1)

            self.admin_id = self._person(
                tx, "admin", self.board_id, person_type="adult", adult_type="other",
                first="Ada", last="Admin", role="admin",
                email="admin@example.org", latin_knowledge="advanced")
            self.chair_id = self._person(
                tx, "chair", self.board_id, person_type="adult", adult_type="other",
                first="Cleo", last="Chair", role="registration_chair",
                email="chair@example.org")

            self.uni_sponsor_id = self._person(
                tx, "uni_sponsor", self.uni_id, person_type="adult",
                adult_type="sponsor", first="Sam", last="Sponsor", role="sponsor",
                email="sponsor@example.edu", latin_knowledge="advanced")
            self.other_sponsor_id = self._person(
                tx, "other_sponsor", self.other_id, person_type="adult",
                adult_type="sponsor", first="Robin", last="Rival", role="sponsor",
                email="rival@example.edu")

            self.delegate_id = self._person(
                tx, "delegate", self.uni_id, first="Dana", last="Delegate",
                role="delegate", grade=10, latin_level="HS-2", meal="regular",
                guardian_name="Guardian One", guardian_phone="555-0101")
            self.other_delegate_id = self._person(
                tx, "other_delegate", self.other_id, first="Rory", last="Rival",
                role="delegate", grade=9, latin_level="HS-1")
            self.chaperone_id = self._person(
                tx, "chaperone", self.uni_id, person_type="adult",
                adult_type="chaperone", first="Chris", last="Chaperone",
                role="delegate", email="chap@example.edu", latin_knowledge="none")

            tx.audit("school.create", "Test fixture built four schools and seven people.")

        with self.db.tx() as tx:
            fees = settings.fee_settings(tx)
            stats.recompute_all(tx, settings=fees)
            tx.mark_silent("stats.recompute")

    # -- convenience --------------------------------------------------------

    def principal(self, key: str) -> auth.Principal:
        """A Principal for one of the fixture people, without a live session."""
        with self.db.read() as tx:
            person = tx.one("people.get", (self._principals[key],))
            return auth._principal_from_person(tx, person)

    def sign_in(self, key: str) -> str:
        """Redeem that person's code and return a live session token."""
        token, _ = auth.redeem(self.db, self.codes[key], ip="127.0.0.1")
        return token

    def expire_session(self, session_id: int) -> None:
        """Age a session out, so expiry can be tested without waiting 180 days.

        Reaches past the query registry deliberately: this is a test-only
        manipulation and giving it a named query would put an "expire any
        session" statement in the production registry.
        """
        import sqlite3

        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE sessions SET expires_at = ? WHERE id = ?",
                     ("2020-01-01T00:00:00Z", session_id))
        conn.commit()
        conn.close()

    def audit_actions(self) -> list[str]:
        with self.db.read() as tx:
            return [r["action"] for r in tx.all("audit.recent", (10 ** 9, 200))]

    def stats_for(self, school_id: int) -> dict:
        with self.db.read() as tx:
            return dict(tx.one("stats.for_school", (school_id,)))

    def public_stats(self) -> dict:
        with self.db.read() as tx:
            return dict(tx.one("stats.public"))
