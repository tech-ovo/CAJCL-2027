"""The printed packet and invoice.

ONE IMPLEMENTATION, NOT TWO. The same HTML is served to the browser as a print
view and handed to WeasyPrint for the PDF, so anything asserted here holds for
both. These tests guard the properties that would otherwise only be discovered
by holding a bad printout at a board meeting.
"""

from __future__ import annotations

import re

import pytest

from backend.lib import clock, printing, roster

from .helpers import Fixture


@pytest.fixture
def fx(tmp_path):
    with Fixture(tmp_path) as f:
        yield f


def packet_for(fx, school_id=None, **kw):
    with fx.db.read() as tx:
        school = dict(tx.one("schools.get", (school_id or fx.uni_id,)))
        return printing.render_packet(tx, school, **kw)


def invoice_for(fx, school_id=None):
    with fx.db.read() as tx:
        school = dict(tx.one("schools.get", (school_id or fx.uni_id,)))
        return printing.render_invoice(tx, school)


# ---------------------------------------------------------------------------
# One layout, two renderers
# ---------------------------------------------------------------------------

def test_the_print_css_uses_no_css_grid():
    """WeasyPrint does not support the full CSS grid.

    If a print template reaches for `display: grid`, the browser print view and
    the PDF disagree -- which defeats the entire point of one template. Flow,
    tables and simple flex only.
    """
    import pathlib
    source = pathlib.Path(printing.__file__).read_text(encoding="utf-8")
    css = source[source.index("PRINT_CSS = "):source.index("def _document(")]
    assert "display: grid" not in css
    assert "grid-template" not in css


def test_the_packet_is_self_contained():
    """No external stylesheet, no CDN font, no remote image. It has to render
    identically in a browser, in WeasyPrint, and on a school network that blocks
    half the internet."""
    import pathlib
    source = pathlib.Path(printing.__file__).read_text(encoding="utf-8")
    assert "http://" not in source.replace("http://www.w3.org", "")
    assert "fonts.googleapis" not in source


# ---------------------------------------------------------------------------
# The credential sheet
# ---------------------------------------------------------------------------

def test_every_active_attendee_gets_a_sheet(fx):
    html = packet_for(fx)
    with fx.db.read() as tx:
        active = [r for r in tx.all("roster.list", (fx.uni_id,))
                  if r["status"] == "active"]
    # A cover, one sheet each, and the paper-forms page.
    assert html.count('class="sheet"') == len(active) + 2


def test_each_sheet_carries_a_real_qr(fx):
    html = packet_for(fx)
    assert html.count("<svg") >= 1
    assert "viewBox" in html          # scalable, not a fixed-size bitmap


def test_the_sheet_says_it_is_a_credential(fx):
    """Because the printed sheet IS a bearer credential, it says so."""
    html = packet_for(fx)
    assert "This sheet is your key" in html
    assert "Anyone holding it can sign in" in html


def test_the_sheet_shows_the_name_large(fx):
    """So a sponsor cannot hand the wrong page to the wrong student."""
    html = packet_for(fx)
    assert 'class="tabula__name"' in html or 'class="name"' in html
    assert re.search(r"\.tabula \.name \{[^}]*font-size: 19pt", html, re.DOTALL)


def test_nobodys_credential_splits_across_two_pages(fx):
    html = packet_for(fx)
    assert "break-inside: avoid" in html
    # A break BEFORE each sheet after the first, not after each one. Stated the
    # other way it needed a `:last-child` exemption that never matched --
    # `_document` puts the footer after the body -- so every packet ended with
    # a blank page carrying nothing but the footer.
    assert ".sheet + .sheet { break-before: page; }" in html
    assert "break-after: page" not in html


def test_a_ninety_character_name_stays_inside_the_tabula(fx):
    """The parser accepts a name of any length and the schema sets no limit, so
    the layout has to cope rather than the data being trimmed to fit it."""
    long_last = "Wolfeschlegelsteinhausenbergerdorff" * 2
    with fx.db.tx() as tx:
        tx.run("people.update_details", (
            "Hubert", None, long_last, None, 10, "HS-2", "regular", None,
            None, None, clock.now_iso(), fx.delegate_id))
        tx.audit("person.update", "Test set a very long name.",
                 school_id=fx.uni_id, entity_type="person",
                 entity_id=fx.delegate_id, changed_fields=["last_name"])

    html = packet_for(fx)
    assert long_last in html
    assert "overflow-wrap: anywhere" in html


def test_a_single_attendee_reprint(fx):
    """What the sponsor gets immediately after regenerating a code. Without it
    they hold a packet page whose QR no longer works."""
    html = packet_for(fx, only_person=fx.delegate_id)
    assert html.count('class="sheet"') == 1
    assert "Dana" in html
    assert "Required paper forms" not in html      # one sheet, not the packet


def test_the_packet_lists_the_paper_forms(fx):
    html = packet_for(fx)
    assert "Student Waiver" in html
    assert "Student Medical Form" in html
    assert "Adult Medical Form" in html


def test_the_theme_appears_once_with_its_macrons(fx):
    """Content, not decoration: one privileged placement per document. An
    epigraph on thirty consecutive credential sheets would be ornament.

    The macrons are asserted by codepoint rather than by literal, so this test
    still means something in an editor that silently rewrites the file. This
    theme uses four of them -- mementō, rēbus, arduīs, servāre -- and no ū; the
    font subset covers all five anyway, because the 73rd convention will choose
    a different line.
    """
    html = packet_for(fx)
    assert html.count("aequam mement") == 1
    for codepoint in (0x0101, 0x0113, 0x012B, 0x014D):   # ā ē ī ō
        assert chr(codepoint) in html, \
            f"U+{codepoint:04X} missing from the printed theme"


def test_every_printed_date_is_readable_without_translation(fx):
    """The dates used to print as XII-XIII MARTII MMXXVII.

    It suited a classics convention and it also meant a sponsor checking a
    packet against a calendar, or a parent reading a payment due date, had to
    decode it first. The dates are the one thing on the page that nobody should
    have to work out.
    """
    months = (r"(January|February|March|April|May|June|July|August|"
              r"September|October|November|December)")

    packet = packet_for(fx)
    assert "MARTII" not in packet and "MMXXVII" not in packet
    assert re.search(months + r" \d{1,2}–\d{1,2}, \d{4}", packet),         "the packet should carry the convention dates in plain English"

    invoice = invoice_for(fx)
    assert re.search(months + r" \d{1,2}, \d{4}", invoice)


# ---------------------------------------------------------------------------
# The invoice
# ---------------------------------------------------------------------------

def test_the_invoice_shows_the_free_adult_line(fx):
    """So the arithmetic is visible rather than magic. A sponsor who cancels a
    delegate and sees the bill fall by $65 instead of $140 can find the reason
    here instead of sending an email."""
    html = invoice_for(fx)
    assert "Adults included at no charge" in html
    assert "one per 10 delegates" in html


def test_the_invoice_totals_add_up(fx):
    with fx.db.read() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        context = printing.invoice_context(tx, school)
    lines = sum(line["amount_cents"] for line in context["lines"])
    assert context["amount_owed_cents"] == max(0, lines - context["discount_cents"])
    assert context["balance_cents"] == \
        context["amount_owed_cents"] - context["amount_paid_cents"]


def test_an_exempt_chapter_gets_words_not_a_blank_page(fx):
    """A blank invoice reads as a bug."""
    html = invoice_for(fx, fx.exempt_id)
    assert "not billed" in html
    assert "Nothing due" in html
    assert "$" not in html.split("</style>")[1]     # no totals table at all


def test_the_invoice_explains_a_cancelled_but_paid_attendee(fx):
    """There are no refunds, and the invoice says so rather than leaving a
    sponsor to work out why the number did not move."""
    actor = fx.principal("chair")
    with fx.db.tx() as tx:
        tx.insert("payments.create", (fx.uni_id, 50000, "check", "1", None, None,
                                      fx.chair_id, clock.now_iso()))
        tx.audit("payment.record", "Chair recorded a payment.",
                 school_id=fx.uni_id, value_detail={"amount_cents": 50000})
    with fx.db.tx() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        person = dict(tx.one("people.get", (fx.delegate_id,)))
        assert roster.cancel(tx, school, actor, person) == "cancelled_paid"

    html = invoice_for(fx)
    assert "withdrew after payment was received" in html
    assert "no refunds" in html


def test_the_invoice_shows_a_discount_with_its_reason(fx):
    with fx.db.tx() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        tx.run("schools.update", (
            school["name"], school["level"], school["city"], 0,
            5000, "New chapter, first year at state", "active", None, None,
            clock.now_iso(), fx.uni_id))
        tx.audit("school.update", "Chair applied a discount.", school_id=fx.uni_id)
        from backend.lib import settings, stats
        stats.recompute(tx, fx.uni_id, settings=settings.fee_settings(tx))

    html = invoice_for(fx)
    assert "Discount" in html
    assert "New chapter, first year at state" in html


def test_the_footer_carries_the_contact_address_on_every_document(fx):
    for html in (packet_for(fx), invoice_for(fx), invoice_for(fx, fx.exempt_id)):
        assert "state@uhsjcl.org" in html
        assert "University High School" in html


def test_no_access_code_is_ever_rendered_into_the_packet(fx):
    """Only the HMAC is stored, so the packet CANNOT print a live code -- and
    that is the correct behaviour, not a limitation. A sponsor prints from the
    code they were shown once at creation or regeneration."""
    html = packet_for(fx)
    from backend.lib import codes
    assert codes.normalize(fx.codes["delegate"]) not in html


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

def test_both_sql_exports_restore_into_a_working_database(fx, tmp_path):
    """The anonymised file is the one handed to an outside helper, so it has to
    LOAD, not merely exist.

    An earlier version dropped the redacted columns instead of blanking them.
    `audit_log.summary` is NOT NULL, so the dump failed on its first audit row,
    and `people.code_hmac` is uniquely indexed, so a constant placeholder failed
    on the second person. Both are now blanked per-row and constraint-aware.
    """
    import sqlite3

    from backend.workers import export as exporter

    conn = exporter.open_db(fx.path)
    try:
        for anonymized in (False, True):
            path = exporter.export_sql(conn, tmp_path, anonymized)
            restored = sqlite3.connect(":memory:")
            restored.execute("PRAGMA foreign_keys = ON")
            restored.executescript(path.read_text(encoding="utf-8"))

            people = restored.execute("SELECT COUNT(*) FROM people").fetchone()[0]
            assert people > 0, f"{path.name} restored no people"

            name = restored.execute(
                "SELECT last_name FROM people LIMIT 1").fetchone()[0]
            if anonymized:
                assert name == "[redacted]"
            else:
                assert name and name != "[redacted]"

            # Unique indexes survive the redaction.
            hashes = [r[0] for r in restored.execute("SELECT code_hmac FROM people")]
            assert len(set(hashes)) == len(hashes)
            restored.close()
    finally:
        conn.close()


def test_the_anonymised_export_carries_no_attendee_data(fx, tmp_path):
    """No attendee's identity survives into the anonymised export.

    Matched on FULL names and on contact details, not on individual name parts.
    The fixture's people are deliberately named after their roles -- Cleo Chair,
    Sam Sponsor -- and `roles.name` legitimately contains "Registration Chair".
    A per-word check flags that and teaches whoever sees it to ignore the test.
    """
    import re

    from backend.workers import export as exporter

    conn = exporter.open_db(fx.path)
    try:
        text = exporter.export_sql(conn, tmp_path, True).read_text(encoding="utf-8")
        identities = set()
        for row in conn.execute(
                "SELECT first_name, last_name, guardian_name, guardian_phone, "
                "email FROM people"):
            first, last, guardian, phone, email = row
            if first and last:
                identities.add(f"{first} {last}")
            for value in (guardian, phone, email):
                if value:
                    identities.add(str(value))
    finally:
        conn.close()

    # Only the INSERT statements. The schema is dumped verbatim and its comments
    # contain a fabricated example name, which is documentation, not data.
    inserts = chr(10).join(
        line for line in text.splitlines() if line.startswith("INSERT"))
    leaked = sorted(v for v in identities
                    if re.search(rf"{re.escape(v)}", inserts))
    assert leaked == [], f"anonymised export leaked {leaked}"


# ---------------------------------------------------------------------------
# Reprinting a chosen few
# ---------------------------------------------------------------------------

def test_a_subset_reprint_is_sheets_only(fx):
    """After a selective code reissue, the sponsor prints exactly the sheets
    that changed.

    Not the cover, whose first line is "This packet contains one sheet per
    attendee", and not the paper-forms page. Both would be wrong on a
    three-page reprint, and printing the whole packet to replace three sheets is
    how two versions of the same page end up in circulation.
    """
    with fx.db.read() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        people = [dict(r) for r in tx.all("roster.list", (fx.uni_id,))]
        active = [p for p in people if p["status"] == "active"][:2]
        chosen = [p["id"] for p in active]
        html = printing.render_packet(tx, school, only_people=chosen)

    assert html.count('class="sheet"') == len(chosen)
    assert "packet contains one sheet" not in html
    for person in active:
        assert person["first_name"] in html


def test_a_subset_reprint_keeps_the_order_it_was_given(fx):
    """The printed stack matches the list the sponsor ticked, so they can hand
    the sheets out without re-sorting them."""
    with fx.db.read() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        people = [dict(r) for r in tx.all("roster.list", (fx.uni_id,))]
        active = [p for p in people if p["status"] == "active"][:3]
        reversed_ids = [p["id"] for p in reversed(active)]
        html = printing.render_packet(tx, school, only_people=reversed_ids)

    positions = [html.index(p["first_name"]) for p in reversed(active)]
    assert positions == sorted(positions), "sheets came out in the wrong order"


def test_the_whole_packet_still_has_its_cover_and_paper_page(fx):
    packet = packet_for(fx)
    assert "packet contains one sheet" in packet


# ---------------------------------------------------------------------------
# A name that does not fit
# ---------------------------------------------------------------------------

LONG_NAME = ("Maximiliana Aleksandra "
             "Wojciechowska-Featherstonehaugh de la Cruz y Villalobos III")


def _person_with_name(fx, first, middle, last, suffix):
    from backend.lib import clock
    with fx.db.tx() as tx:
        person_id = tx.insert("people.create", (
            fx.uni_id, "delegate", None, None,
            first, middle, last, suffix, None,
            11, "HS-3", None, None, None, None, None, None, None,
            f"fixture-{last}-{clock.now_iso()}", "DEL", 1,
            clock.now_iso(), clock.now_iso(), clock.now_iso(), None,
            fx.uni_id))
        tx.audit("person.create", "long-name fixture", school_id=fx.uni_id,
                 entity_type="person", entity_id=person_id)
    return person_id


def test_a_very_long_name_prints_whole(fx):
    """`break-inside: avoid` on the credential block means an overflowing name
    pushes rather than splits — but nothing had ever checked that the name
    survives at all, or that the suffix is not silently dropped."""
    person_id = _person_with_name(
        fx, "Maximiliana", "Aleksandra",
        "Wojciechowska-Featherstonehaugh de la Cruz y Villalobos", "III")

    with fx.db.read() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        html = printing.render_packet(tx, school, only_person=person_id)

    assert "Wojciechowska-Featherstonehaugh" in html
    assert "de la Cruz y Villalobos" in html
    assert "III" in html
    assert len(LONG_NAME) > 80


def test_a_long_name_is_set_smaller_rather_than_running_to_four_lines(fx):
    """At 19pt an 82-character name takes four lines and pushes the QR and the
    instructions down the sheet."""
    long_id = _person_with_name(
        fx, "Maximiliana", "Aleksandra",
        "Wojciechowska-Featherstonehaugh de la Cruz y Villalobos", "III")
    short_id = _person_with_name(fx, "Mei", None, "Ng", None)

    with fx.db.read() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        long_html = printing.render_packet(tx, school, only_person=long_id)
        short_html = printing.render_packet(tx, school, only_person=short_id)

    assert 'class="name name--verylong"' in long_html

    # A short name is untouched: the shrink is an exception, not the rule.
    # Asserted on the ATTRIBUTE, because the stylesheet in every document
    # defines both classes whether or not anything uses them.
    assert 'class="name"' in short_html
    assert 'class="name name--' not in short_html

    # And the class it applies is one the stylesheet actually defines.
    assert ".tabula .name--verylong" in long_html


def test_the_size_thresholds_are_where_they_claim_to_be():
    from backend.lib.printing import _name_size

    assert _name_size("Mei Ng") == ""
    assert _name_size("A" * 38) == ""
    assert _name_size("A" * 39) == " name--long"
    assert _name_size("A" * 60) == " name--long"
    assert _name_size("A" * 61) == " name--verylong"


# ---------------------------------------------------------------------------
# The proctor's sign-in sheet
# ---------------------------------------------------------------------------

def test_the_signin_sheet_lists_everyone_with_a_box_to_tick(fx):
    """Carried into a room with no power, no signal and a pen."""
    with fx.db.read() as tx:
        item = dict(tx.one("academics.item", (1,)))
        people = [dict(r) for r in tx.all("academics.item_people", (1,))]
        html = printing.render_signin_sheet(tx, item, people)

    assert item["name"] in html
    assert "Room _____________" in html
    assert 'class="tick"' in html
    assert html.count('<td class="tick"></td>') == len(people)
    for person in people:
        assert person["last_name"] in html
        assert person["school_name"] in html


def test_the_signin_sheet_says_what_to_do_with_an_unexpected_delegate(fx):
    """A name not on the list is the case a proctor will actually hit, because
    a sponsor may have added somebody that morning. Turning them away is the
    wrong answer and the sheet should not leave it to judgement."""
    with fx.db.read() as tx:
        item = dict(tx.one("academics.item", (1,)))
        people = [dict(r) for r in tx.all("academics.item_people", (1,))]
        html = printing.render_signin_sheet(tx, item, people)

    assert "registration desk" in html
    assert "rather than turning" in html


def test_an_empty_item_still_prints_a_usable_sheet(fx):
    """An item nobody entered is worth printing anyway: it is how a proctor
    finds out the room is not needed, rather than waiting in it."""
    with fx.db.read() as tx:
        item = dict(tx.one("academics.item", (1,)))
        html = printing.render_signin_sheet(tx, item, [])

    assert "0 entered" in html
    assert item["name"] in html


def test_the_paper_forms_page_lists_only_the_forms_that_apply(fx):
    """A chaperone reading "Student Waiver — every delegate" has to work out
    that two of the three lines are not about them, which is exactly the
    reading nobody does on a form."""
    from backend.lib import printing

    with fx.db.read() as tx:
        delegates_only = printing._paper_forms_page(
            tx, [{"person_type": "delegate"}])
        adults_only = printing._paper_forms_page(
            tx, [{"person_type": "adult"}])
        both = printing._paper_forms_page(
            tx, [{"person_type": "delegate"}, {"person_type": "adult"}])

    assert "Student Waiver" in delegates_only
    assert "Adult Medical Form" not in delegates_only
    assert "These two forms are" in delegates_only

    assert "Adult Medical Form" in adults_only
    assert "Student Waiver" not in adults_only
    assert "This form is" in adults_only

    assert "These three forms are" in both


# ---------------------------------------------------------------------------
# The PDF path, end to end
# ---------------------------------------------------------------------------
# WeasyPrint is not installed here and is not worth installing: it needs Pango
# and Cairo from apt. What these cover is everything on either side of it --
# the endpoint, the scope checks, the codes reaching the template, and the
# bytes reaching the browser -- because the bug this path actually had was
# never in WeasyPrint. It was that nothing called any of this.

@pytest.fixture
def pdf_client(fx, monkeypatch):
    from fastapi.testclient import TestClient

    from backend import api

    monkeypatch.setattr(api, "_db", fx.db)
    return TestClient(api.app, raise_server_exceptions=False)


class FakeModal:
    """Stands in for `modal.Function.from_name(...).remote(...)`.

    Records what it was asked to render, so a test can assert the codes
    survived the trip rather than only that a request succeeded.
    """

    def __init__(self, answer=b"%PDF-1.7 fake", boom=None):
        self.answer, self.boom, self.calls = answer, boom, []

    def install(self, monkeypatch):
        import types

        outer = self

        class Function:
            @staticmethod
            def from_name(app, name):
                outer.calls.append(("from_name", app, name))
                return outer

            pass

        monkeypatch.setitem(__import__("sys").modules, "modal",
                            types.SimpleNamespace(Function=Function))
        return self

    def remote(self, **kw):
        self.calls.append(("remote", kw))
        if self.boom:
            raise RuntimeError(self.boom)
        return self.answer


def test_the_pdf_endpoint_hands_back_the_bytes_it_was_given(fx, pdf_client,
                                                            monkeypatch):
    """The whole point: a caller, a file, a name to save it under."""
    fake = FakeModal().install(monkeypatch)

    response = pdf_client.post(
        "/sponsor/packet.pdf",
        headers={"Authorization": f"Bearer {fx.sign_in('uni_sponsor')}"},
        json={"codes": [{"person_id": fx.delegate_id, "code": "DEL-K7M2N-9PQ4T"}]})

    assert response.status_code == 200, response.text
    assert response.content == b"%PDF-1.7 fake"
    assert response.headers["content-type"] == "application/pdf"
    assert "university-high-school" in response.headers["content-disposition"]


def test_the_codes_reach_the_renderer(fx, pdf_client, monkeypatch):
    """The bug that made this path pointless before it had a caller: the
    packet rendered blocks where every access code belongs, because nothing
    passed them down. A PDF full of blocks is not a reprint."""
    fake = FakeModal().install(monkeypatch)

    pdf_client.post(
        "/sponsor/packet.pdf",
        headers={"Authorization": f"Bearer {fx.sign_in('uni_sponsor')}"},
        json={"codes": [{"person_id": fx.delegate_id, "code": "DEL-K7M2N-9PQ4T"}]})

    sent = [kw for kind, kw in
            [(c[0], c[-1]) for c in fake.calls] if kind == "remote"][0]
    assert sent["codes"] == {str(fx.delegate_id): "DEL-K7M2N-9PQ4T"}
    assert sent["school_id"] == fx.uni_id


def test_a_code_for_another_chapter_is_refused(fx, pdf_client, monkeypatch):
    """A sponsor may not render a sheet for somebody who is not theirs, even
    holding a plausible-looking code. Checked BEFORE the renderer is reached,
    so a refusal costs nothing."""
    fake = FakeModal().install(monkeypatch)

    response = pdf_client.post(
        "/sponsor/packet.pdf",
        headers={"Authorization": f"Bearer {fx.sign_in('uni_sponsor')}"},
        json={"codes": [{"person_id": fx.other_delegate_id,
                         "code": "DEL-K7M2N-9PQ4T"}]})

    assert response.status_code == 403
    assert [c for c in fake.calls if c[0] == "remote"] == []


def test_a_renderer_that_does_not_answer_becomes_a_sentence(fx, pdf_client,
                                                            monkeypatch):
    """The fat image is a second thing that can be down, and it must not take
    the page with it. Print is right there and produces the same document, so
    the message says so."""
    FakeModal(boom="no such function").install(monkeypatch)

    response = pdf_client.post(
        "/sponsor/packet.pdf",
        headers={"Authorization": f"Bearer {fx.sign_in('uni_sponsor')}"},
        json={"codes": [{"person_id": fx.delegate_id, "code": "DEL-K7M2N-9PQ4T"}]})

    assert response.status_code == 422
    assert "Use Print instead" in response.json()["error"]


def test_the_worker_builds_the_same_html_the_browser_prints(fx):
    """`build_html` is everything the PDF is, short of WeasyPrint. If it and
    the print view ever diverge, there are two layouts again."""
    from backend.workers import pdf as worker

    codes = {fx.delegate_id: "DEL-K7M2N-9PQ4T"}
    built = worker.build_html(fx.db, "packet", fx.uni_id, codes=codes)

    assert "DEL-K7M2N-9PQ4T" in built
    assert built == packet_for(fx, codes=codes)
