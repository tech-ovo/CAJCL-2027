"""Generate the demonstration database.

EVERY DELEGATE, PARENT AND CHAPTER IN HERE IS FABRICATED. The repository is
public and the demonstration is projected in a room full of teachers; nobody
should have to wonder whether the names on screen belong to real children.

The exceptions are named, few, and adults who have agreed to it: the two
technology commissioners, the host chapter's sponsor, and University High
School itself, which is the host site and a matter of public record. They
appear because the seeded audit log reads as a narrative of a real convention
and, being illustrative, is understood as one. `scripts/add_board.py` finds
these people rather than duplicating them.

No student. No parent. No guardian. Not one.

The whole thing is reproducible from a fixed seed, so re-running it produces the
same schools, the same rosters, and the same spread of completion. Access codes
are the deliberate exception: they come from `secrets`, never from the seeded
generator, because a reproducible credential is not a credential. The script
prints the ones a presenter needs and writes them to demo-codes.txt, which is
gitignored.

    python scripts/seed.py --db dev.db          # seed a fresh database
    python scripts/seed.py --db dev.db --reset  # wipe and seed again

`--reset` is what the "Reset demo data" button behind scope `*` calls, so a
presentation can be rerun cleanly if something goes wrong mid-demo.
"""

from __future__ import annotations

import argparse
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from backend.lib import auth, clock, settings, stats  # noqa: E402
from backend.lib.db import connect  # noqa: E402
from backend.lib import migrate as migrate_runner  # noqa: E402

SEED = 20270312   # the first day of convention, for no reason but memorability

# --- Fabricated schools ----------------------------------------------------
# Invented names. Any resemblance to a real California school is accidental and
# unintended; if one of these turns out to exist, rename it.
HIGH_SCHOOLS = [
    ("Alta Mesa High School", "Fresno"),
    ("Cordova Canyon High School", "Riverside"),
    ("Espero Valley High School", "Bakersfield"),
    ("Kestrel Ridge High School", "Santa Rosa"),
    ("Las Palomas High School", "Chula Vista"),
    ("Pinnacle Bay High School", "Alameda"),
    ("Sandpiper Cove High School", "Ventura"),
]
# Seven invented high schools, plus University High School (the host) and SCL,
# makes the nine high-school chapters docs/schema.md asks for. Three middle
# schools brings the total to twelve.
MIDDLE_SCHOOLS = [
    ("Arroyo Verde Middle School", "Modesto"),
    ("Higuera Middle School", "Salinas"),
    ("Tulare Bluffs Middle School", "Visalia"),
]

FIRST_NAMES = [
    "Amara", "Beatriz", "Callum", "Dara", "Elena", "Farid", "Gemma", "Hana",
    "Idris", "Jonah", "Kiran", "Lucia", "Mateo", "Nadia", "Omar", "Priya",
    "Quentin", "Rosa", "Sana", "Tobias", "Ursula", "Vikram", "Wren", "Ximena",
    "Yusuf", "Zara", "Anders", "Brigid", "Cyrus", "Delphine", "Emeka", "Freya",
    "Gustavo", "Halima", "Ines", "Joaquin", "Kofi", "Leila", "Marisol", "Nikolai",
]
LAST_NAMES = [
    "Abara", "Bellweather", "Castellanos", "Dunmore", "Ekstrom", "Fairbanks",
    "Ghioni", "Halvorsen", "Ibarra", "Jandali", "Kowalczyk", "Lindqvist",
    "Marchetti", "Nakagawa", "Okonjo", "Pryce", "Quintero", "Rasmussen",
    "Sandoval", "Thibault", "Ueda", "Vasquez", "Whitfield", "Xiang",
    "Yarborough", "Zeleny", "Ashcombe", "Brennan", "Calloway", "Duarte",
]
MIDDLE_NAMES = ["Rae", "Jun", "Alexis", "Marie", "Kai", "Noor", "Reese", "Sol"]

# One delegate whose name exercises the particle folding, so the parser's real
# behaviour is visible in the roster rather than only in the test suite.
PARTICLE_DELEGATE = ("Ximena", "", "de la Rosa")

MEALS = ["regular", "regular", "regular", "vegetarian", "gluten_free"]
HS_LEVELS = ["HS-1", "HS-1", "HS-2", "HS-2", "HS-3", "HS-Adv"]
MS_LEVELS = ["MS-1", "MS-2", "MS-2", "MS-3"]


def wipe(db) -> None:
    """Drop every table so migrations can rebuild from nothing.

    A plain DELETE will not do: audit_log carries an append-only trigger that
    refuses DELETE by design, and that trigger is doing its job. Dropping the
    table takes the trigger with it, which is the only honest way to reset.

    Tables are dropped in REVERSE creation order. sqlite_master lists them in
    the order they were created, and a table can only reference one that
    already exists -- so creation order is dependency order, and reversing it
    drops every child before its parent. Dropping `schools` while `people` still
    points at it fails the foreign key, and `defer_foreign_keys` does not help
    because DROP TABLE performs an implicit DELETE that is checked immediately.
    """
    with db.tx() as tx:
        for row in tx._backend.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                "AND name NOT LIKE 'sqlite_%'", ()):
            tx._backend.execute(f'DROP TRIGGER IF EXISTS "{row["name"]}"', ())
        tables = [
            row["name"] for row in tx._backend.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'", ())
        ]
        for name in reversed(tables):
            tx._backend.execute(f'DROP TABLE IF EXISTS "{name}"', ())
        tx.mark_silent("stats.recompute")


def migrate(db) -> None:
    """Apply the migrations through the one runner that knows how."""
    migrate_runner.run(db, verbose=False)


class Seeder:
    def __init__(self, db):
        self.db = db
        self.rng = random.Random(SEED)
        self.codes: dict[str, str] = {}
        # Set while the host chapter's sponsors are created, and used as the
        # actor on every audit entry after that. Declared here so a failure to
        # set it is an obvious None rather than an AttributeError forty lines
        # further down.
        self.uni_sponsor_id: int | None = None

    # -- small helpers ------------------------------------------------------

    def _school(self, tx, name, level, city, *, kind="chapter", exempt=0,
                discount=0, discount_reason=None, created: str = "") -> int:
        school_id = tx.insert("schools.create", (
            name, level, kind, city, exempt, discount, discount_reason, None,
            created, created))
        tx.run("schools.stats_init", (school_id, created))
        return school_id

    def _person(self, tx, school_id, first, middle, last, *,
                person_type="delegate", adult_type=None, role=None,
                created="", **extra) -> int:
        person_id = tx.insert("people.create", (
            school_id, person_type, adult_type, None,
            first, middle or None, last, extra.get("suffix"),
            extra.get("raw"),
            extra.get("grade"), extra.get("latin_level"), extra.get("meal"),
            extra.get("cell_phone"),
            extra.get("email"), extra.get("latin_knowledge"),
            extra.get("availability_note"),
            extra.get("guardian_name"), extra.get("guardian_phone"),
            f"seed-placeholder-{school_id}-{first}-{last}-{self.rng.random()}",
            "DEL", 1, created, created, created, None))

        if role:
            role_row = tx.one("roles.by_key", (role,))
            tx.run("people.grant_role", (person_id, role_row["id"], None, created))

        prefix = auth.code_prefix_for(person_type, adult_type)
        code = auth.issue_code(tx, person_id, prefix)
        return person_id, code

    def _guardian(self) -> tuple[str, str]:
        name = f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}"
        phone = f"555-{self.rng.randint(100, 999)}-{self.rng.randint(1000, 9999)}"
        return name, phone

    def _delegate_names(self, count: int) -> list[tuple[str, str, str]]:
        """Distinct fabricated names, with a middle name on roughly a third."""
        out, seen = [], set()
        while len(out) < count:
            first = self.rng.choice(FIRST_NAMES)
            last = self.rng.choice(LAST_NAMES)
            if (first, last) in seen:
                continue
            seen.add((first, last))
            middle = self.rng.choice(MIDDLE_NAMES) if self.rng.random() < 0.3 else ""
            out.append((first, middle, last))
        return out

    # -- the seed ----------------------------------------------------------

    def run(self) -> dict:
        days_ago = lambda n: clock.plus_days(-n)

        # Printed as it goes, because against a hosted database this is one to
        # two minutes of network round trips and silence for that long looks
        # exactly like a hang. Modal captures stdout, so these lines are also
        # what `modal app logs` shows after a detached run.
        def step(message: str) -> None:
            print(f"  seed: {message}", flush=True)

        # THERE IS NO STATE BOARD CHAPTER ANY MORE.
        #
        # It existed because `people.school_id` is NOT NULL and the board had
        # to go somewhere. But almost everybody on the board is a STUDENT --
        # a delegate at their own chapter who also holds a convention role,
        # the same model as a chapter leader. Filing them in a pseudo-chapter
        # separated them from the chapter they actually attend with, and gave
        # them the adult form instead of their own activity sheet.
        #
        # The real board arrives from board.json, at their real schools. See
        # scripts/add_board.py and docs/DEPLOY.md step 4b.
        #
        # The host chapter's sponsor below carries `admin`, so a freshly seeded
        # database still has somebody who can open Settings without anything
        # else having to be run first.

        step("the host chapter")
        # --- the host chapter ---------------------------------------------
        with self.db.tx() as tx:
            uni = self._school(tx, "University High School", "HS", "Irvine",
                               created=days_ago(56))
            tx.audit("school.create",
                     "Mark Michalak added University High School to the convention.",
                     school_id=uni, entity_type="school", entity_id=uni,
                     ts=days_ago(56))

            sponsors = [("Mark", "", "Michalak"), ("Diane", "", "Whitfield")]
            for first, middle, last in sponsors:
                pid, code = self._person(
                    tx, uni, first, middle, last, person_type="adult",
                    adult_type="sponsor", role="sponsor", created=days_ago(69),
                    email=f"{first.lower()}.{last.lower()}@example.edu",
                    latin_knowledge="advanced", meal="regular",
                    cell_phone="555-0100")
                self.codes[f"Sponsor: {first} {last} (University High School)"] = code

                # The FIRST sponsor also holds `admin`, so a freshly seeded
                # database has somebody who can open Settings without anything
                # else having to be run. `_person` grants one role, and this
                # person needs two -- granting it here rather than widening
                # that helper for a single case.
                #
                # board.json says the same thing about this person, so running
                # it afterwards finds them and changes nothing.
                if self.uni_sponsor_id is None:
                    admin_role = tx.one("roles.by_key", ("admin",))
                    tx.run("people.grant_role",
                           (pid, admin_role["id"], None, days_ago(69)))
                    # NOT a second entry under "Administrator". It is one
                    # person with one code, and listing them twice made the
                    # printed sheet look as though two people shared a code.
                    self.codes.pop(
                        f"Sponsor: {first} {last} (University High School)", None)
                    self.codes[
                        f"Sponsor and administrator: {first} {last} "
                        f"(University High School)"] = code

                # The FIRST sponsor is the one the rest of the seed acts as.
                # This used to test `first == "Mark"`, which broke silently the
                # moment the name changed -- the attribute simply never got
                # set, forty lines before anything read it.
                if self.uni_sponsor_id is None:
                    self.uni_sponsor_id = pid

            for first, middle, last in [("Alan", "", "Pryce"), ("Nadia", "", "Ibarra")]:
                self._person(
                    tx, uni, first, middle, last, person_type="adult",
                    adult_type="chaperone", role="delegate", created=days_ago(52),
                    email=f"{first.lower()}@example.com", latin_knowledge="none",
                    meal=self.rng.choice(MEALS), cell_phone="555-0101")

            tx.audit("roster.import",
                     "Mark Michalak added 2 adults to University High School.",
                     actor_person_id=self.uni_sponsor_id, school_id=uni,
                     entity_type="school", entity_id=uni, ts=days_ago(52))

        self.uni_id = uni
        step("University High School delegates")
        self._seed_uni_delegates(uni, days_ago)
        step("the other chapters")
        self._seed_other_chapters(days_ago)
        step("SCL, the chapter that is not billed")
        self._seed_scl(days_ago)
        step("payments")
        self._seed_payment(uni, days_ago)
        step("done")
        self._finish()
        return self.codes

    def _seed_uni_delegates(self, uni: int, days_ago) -> None:
        """30 delegates, with a realistic spread of completion."""
        names = self._delegate_names(29)
        names.insert(7, PARTICLE_DELEGATE)   # the particle-parser example

        with self.db.tx() as tx:
            created = days_ago(50)
            ids = []
            for first, middle, last in names:
                guardian_name, guardian_phone = self._guardian()
                pid, code = self._person(
                    tx, uni, first, middle, last, role="delegate", created=created,
                    grade=self.rng.randint(9, 12),
                    latin_level=self.rng.choice(HS_LEVELS),
                    # NO MEAL at creation. It is asked for on the activity
                    # sheet, so a delegate who has not submitted one has not
                    # answered -- and the dashboard's "still to come" figure is
                    # only meaningful if the data can actually produce it.
                    guardian_name=guardian_name, guardian_phone=guardian_phone,
                    raw=f"{last}, {first} {middle}".strip())
                ids.append(pid)
                if len(ids) == 8:
                    self.codes[f"Delegate: {first} {last} (particle parser example)"] = code
                elif len(ids) == 1:
                    self.codes[f"Delegate: {first} {last} (University High School)"] = code

            tx.audit("roster.import",
                     f"Mark Michalak added {len(ids)} delegates to University High School.",
                     actor_person_id=self.uni_sponsor_id, school_id=uni,
                     entity_type="school", entity_id=uni, ts=created)
            self.uni_delegate_ids = ids

        # Activity sheets: 60% submitted. Paper forms: 40% marked received.
        #
        # EXACT proportions, not coin flips. These numbers get read aloud at a
        # board meeting -- "about 60% of Uni's sheets are in" should be true of
        # what is on the screen, and a run of bad luck making it 40% is a
        # distraction nobody needs mid-presentation. Which delegates fall in
        # each set is still drawn from the seeded generator, so the two sets
        # overlap naturally rather than one containing the other.
        with self.db.tx() as tx:
            items = tx.all("catalog.items")
            tests = [i for i in items if i["category_key"] == "academic_testing"]
            other = [i for i in items
                     if i["category_key"] in ("creative_arts", "ludi", "graphic_arts")
                     and i["registration_scope"] == "individual"]

            total = len(self.uni_delegate_ids)
            submits = set(self.rng.sample(range(total), round(total * 0.60)))
            papers = set(self.rng.sample(range(total), round(total * 0.40)))

            submitted = 0
            for index, pid in enumerate(self.uni_delegate_ids):
                person = tx.one("people.get", (pid,))
                when = days_ago(self.rng.randint(5, 40))

                if index in submits:
                    submitted += 1
                    eligible = [
                        t for t in tests
                        if not t["eligible_latin_levels"]
                        or person["latin_level"] in t["eligible_latin_levels"].split(",")
                    ]
                    for item in self.rng.sample(eligible, self.rng.randint(1, 3)):
                        tx.insert("forms.add_selection", (pid, item["id"], when))
                    for item in self.rng.sample(other, self.rng.randint(0, 4)):
                        tx.insert("forms.add_selection", (pid, item["id"], when))
                    tx.run("people.set_meal",
                           (self.rng.choice(MEALS), when, pid))
                    tx.run("forms.upsert_submission",
                           (pid, "student_activity", "submitted", when, when))
                    tx.audit("form.submit",
                             f"{person['first_name']} {person['last_name']} submitted "
                             f"their Student Activity Sheet.",
                             actor_person_id=pid, school_id=uni,
                             entity_type="form", entity_id=pid, ts=when)

                if index in papers:
                    for form_type in ("student_waiver", "student_medical"):
                        tx.run("forms.mark_paper",
                               (pid, form_type, 1, self.uni_sponsor_id, when))
                    tx.audit("paper_form.mark",
                             f"Mark Michalak marked {person['first_name']} "
                             f"{person['last_name']}'s paper forms as received.",
                             actor_person_id=self.uni_sponsor_id, school_id=uni,
                             entity_type="person", entity_id=pid, ts=when)

            self.uni_submitted = submitted

        # One cancelled delegate and one cancelled-then-restored, so both states
        # are visible on the roster during the demo.
        with self.db.tx() as tx:
            school = dict(tx.one("schools.get", (uni,)))
            for pid, restore_after in ((self.uni_delegate_ids[-1], False),
                                       (self.uni_delegate_ids[-2], True)):
                person = dict(tx.one("people.get", (pid,)))
                name = f"{person['first_name']} {person['last_name']}"
                when = days_ago(16)
                tx.run("people.cancel", ("cancelled", when, when, pid))
                tx.audit("person.cancel",
                         f"Mark Michalak cancelled {name} at University High School.",
                         actor_person_id=self.uni_sponsor_id, school_id=uni,
                         entity_type="person", entity_id=pid,
                         changed_fields=["status"], ts=when)
                if restore_after:
                    tx.run("people.restore", (days_ago(14), pid))
                    tx.audit("person.restore",
                             f"Mark Michalak restored {name} to the roster at "
                             f"University High School.",
                             actor_person_id=self.uni_sponsor_id, school_id=uni,
                             entity_type="person", entity_id=pid,
                             changed_fields=["status"], ts=days_ago(14))

    def _seed_other_chapters(self, days_ago) -> None:
        """Eleven more chapters at varying stages, so the dashboard has a spread."""
        plan = [(name, city, "HS") for name, city in HIGH_SCHOOLS]
        plan += [(name, city, "MS") for name, city in MIDDLE_SCHOOLS]

        for index, (name, city, level) in enumerate(plan):
            # A deliberate range: some chapters are barely started, some are
            # nearly done. A dashboard where every row looks the same proves
            # nothing to a registration chair.
            size = [4, 8, 12, 16, 22, 28, 6, 10, 5, 9, 14][index % 11]
            progress = [0.0, 0.15, 0.35, 0.55, 0.8, 1.0][index % 6]
            discount = 5000 if index == 3 else 0
            reason = "New chapter, first year at state" if index == 3 else None

            with self.db.tx() as tx:
                created = days_ago(68 - index * 4)
                school = self._school(tx, name, level, city,
                                      discount=discount, discount_reason=reason,
                                      created=created)
                tx.audit("school.create",
                         f"Mark Michalak added {name} to the convention.",
                         school_id=school, entity_type="school", entity_id=school,
                         ts=created)

                first, middle, last = (self.rng.choice(FIRST_NAMES), "",
                                       self.rng.choice(LAST_NAMES))
                sponsor_id, code = self._person(
                    tx, school, first, middle, last, person_type="adult",
                    adult_type="sponsor", role="sponsor", created=created,
                    email=f"{first.lower()}@example.edu",
                    latin_knowledge="advanced", meal="regular")
                if index < 2:
                    self.codes[f"Sponsor: {first} {last} ({name})"] = code

                levels = HS_LEVELS if level == "HS" else MS_LEVELS
                grades = (9, 12) if level == "HS" else (6, 8)
                roster_ids = []
                for dfirst, dmiddle, dlast in self._delegate_names(size):
                    guardian_name, guardian_phone = self._guardian()
                    pid, _ = self._person(
                        tx, school, dfirst, dmiddle, dlast, role="delegate",
                        created=created, grade=self.rng.randint(*grades),
                        latin_level=self.rng.choice(levels),
                        guardian_name=guardian_name, guardian_phone=guardian_phone)
                    roster_ids.append(pid)

                for _ in range(max(1, size // 10 + 1)):
                    afirst, alast = self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)
                    self._person(tx, school, afirst, "", alast, person_type="adult",
                                 adult_type="chaperone", role="delegate",
                                 created=created, email=f"{afirst.lower()}@example.com",
                                 latin_knowledge="none", meal=self.rng.choice(MEALS))

                tx.audit("roster.import",
                         f"{first} {last} added {size} delegates to {name}.",
                         actor_person_id=sponsor_id, school_id=school,
                         entity_type="school", entity_id=school, ts=created)

                # A SUBMITTED SHEET WITH NO SELECTIONS IS NOT A STATE THE
                # APPLICATION CAN PRODUCE. Academic testing blocks below one
                # choice, so a delegate cannot submit an empty sheet -- yet
                # every chapter except the host used to get exactly that: a
                # form_submissions row marked "submitted" and nothing chosen.
                #
                # It went unnoticed because nothing read the selections until
                # the Entries page existed, which then showed every test being
                # taken by one chapter. Demonstration data that cannot occur in
                # production is worse than none: it hides the bugs it should be
                # finding.
                items = tx.all("catalog.items")
                tests = [i for i in items
                         if i["category_key"] == "academic_testing"]
                other = [i for i in items
                         if i["category_key"] in ("creative_arts", "ludi",
                                                  "graphic_arts")
                         and i["registration_scope"] == "individual"]

                for pid in roster_ids:
                    if self.rng.random() < progress:
                        when = days_ago(self.rng.randint(3, 40))
                        person = tx.one("people.get", (pid,))

                        eligible = [
                            t for t in tests
                            if not t["eligible_latin_levels"]
                            or person["latin_level"] in
                               t["eligible_latin_levels"].split(",")
                        ]
                        if eligible:
                            for item in self.rng.sample(
                                    eligible, min(len(eligible),
                                                  self.rng.randint(1, 3))):
                                tx.insert("forms.add_selection",
                                          (pid, item["id"], when))
                        for item in self.rng.sample(other,
                                                    self.rng.randint(0, 3)):
                            tx.insert("forms.add_selection",
                                      (pid, item["id"], when))

                        tx.run("people.set_meal",
                               (self.rng.choice(MEALS), when, pid))
                        tx.run("forms.upsert_submission",
                               (pid, "student_activity", "submitted", when, when))
                        for form_type in ("student_waiver", "student_medical"):
                            if self.rng.random() < 0.7:
                                tx.run("forms.mark_paper",
                                       (pid, form_type, 1, sponsor_id, when))

    def _seed_scl(self, days_ago) -> None:
        """The exempt chapter, so the zero-invoice path is demonstrated rather
        than merely believed."""
        with self.db.tx() as tx:
            created = days_ago(56)
            scl = self._school(tx, "SCL", "HS", "Statewide", exempt=1, created=created)
            tx.audit("school.create",
                     "Mark Michalak added SCL, which is not billed for the convention.",
                     school_id=scl, entity_type="school", entity_id=scl, ts=created)

            for first, last in (("Gwen", "Halvorsen"), ("Desmond", "Abara")):
                self._person(tx, scl, first, "", last, person_type="adult",
                             adult_type="scl", role="delegate", created=created,
                             email=f"{first.lower()}@example.org",
                             latin_knowledge="advanced", meal="regular")
            self.scl_id = scl

    def _seed_payment(self, uni: int, days_ago) -> None:
        """One partial payment, so the invoice shows a real outstanding balance."""
        with self.db.tx() as tx:
            admin = tx.one("admin.people_search", (
                tx.one("schools.get", (1,))["id"],))
            when = days_ago(9)
            tx.insert("payments.create", (
                uni, 250000, "check", "3418", clock.local_date_of(when),
                "Partial payment, remainder to follow", admin["id"], when))
            tx.audit("payment.record",
                     "Mark Michalak recorded a $2,500.00 check from "
                     "University High School.",
                     actor_person_id=admin["id"], school_id=uni,
                     entity_type="payment", entity_id=uni,
                     value_detail={"amount_cents": 250000, "reference": "3418",
                                   "previous_total_cents": 0},
                     ts=when)

    def _finish(self) -> None:
        """Recompute every counter, and raise the demonstration-data marker."""
        with self.db.tx() as tx:
            tx.run("settings.update", ("1", clock.now_iso(), None, "ops.demo_mode"))
            tx.audit("settings.update",
                     "Demonstration data was loaded and the demo marker was turned on.",
                     changed_fields=["ops.demo_mode"])
            settings.invalidate()
            stats.recompute_all(tx, settings=settings.fee_settings(tx))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="dev.db")
    ap.add_argument("--reset", action="store_true",
                    help="drop everything and rebuild from the migrations")
    args = ap.parse_args()

    db = connect(args.db)
    settings.invalidate()

    if args.reset:
        print("dropping all tables")
        wipe(db)
    print("running migrations")
    migrate(db)

    print("seeding demonstration data")
    codes = Seeder(db).run()

    with db.read() as tx:
        public = tx.one("stats.public")
        schools = len(tx.all("schools.list"))

    print()
    print(f"  {schools} chapters  "
          f"({public['schools_ms']} middle school, {public['schools_hs']} high school)")
    print(f"  {public['delegates']} delegates, {public['adults']} adults")
    print()
    print("ACCESS CODES FOR THE DEMO (also written to demo-codes.txt)")
    print("These are freshly generated every run: a reproducible code is not a code.")
    print()
    lines = [f"{label}\n    {code}" for label, code in codes.items()]
    for line in lines:
        print("  " + line.replace("\n    ", "\n      "))

    out = pathlib.Path("demo-codes.txt")
    out.write_text(
        "Demonstration access codes - fabricated data, safe to lose.\n"
        "Regenerated every time scripts/seed.py runs.\n\n" + "\n".join(lines) + "\n",
        encoding="utf-8")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
