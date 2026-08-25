"""The invoice, discounts, and the no-refunds rule.

An event this size runs on pre-payment and there are no refunds. That single
policy decides what `cancelled` versus `cancelled_paid` means, why the discount
is a floor-at-zero subtraction, and why nothing here can ever produce a credit.
"""

from __future__ import annotations

import pytest

from backend.lib import clock, roster, settings, stats
from backend.lib.stats import billable_counts, invoice_cents

from .helpers import Fixture

FEES = {
    "fee.delegate_cents": 14000,     # $140
    "fee.extra_adult_cents": 7500,   # $75
    "fee.adult_ratio": 10,
}


@pytest.fixture
def fx(tmp_path):
    with Fixture(tmp_path) as f:
        yield f


def owed(delegates, adults, **kw):
    return invoice_cents(
        delegates_billable=delegates, adults_billable=adults,
        billing_exempt=kw.pop("exempt", False),
        delegate_cents=FEES["fee.delegate_cents"],
        extra_adult_cents=FEES["fee.extra_adult_cents"],
        adult_ratio=FEES["fee.adult_ratio"],
        **kw,
    )


# ---------------------------------------------------------------------------
# The formula
# ---------------------------------------------------------------------------

def test_a_chapter_with_five_delegates_gets_one_free_adult():
    """Straight from docs/structure.md."""
    assert owed(5, 1) == 5 * 14000
    assert owed(5, 2) == 5 * 14000 + 7500


def test_free_adults_round_up_per_ten_delegates():
    assert owed(30, 3) == 30 * 14000            # ceil(30/10) = 3 free
    assert owed(30, 4) == 30 * 14000 + 7500
    assert owed(21, 3) == 21 * 14000            # ceil(21/10) = 3 free


def test_more_free_adults_than_adults_never_produces_a_credit():
    """max(0, ...) -- a chapter with 30 delegates and 1 adult owes for the
    delegates only, not minus two adults."""
    assert owed(30, 1) == 30 * 14000


def test_a_chapter_with_no_delegates_still_pays_for_its_adults():
    assert owed(0, 2) == 2 * 7500


def test_an_empty_chapter_owes_nothing():
    assert owed(0, 0) == 0


# ---------------------------------------------------------------------------
# Exemption
# ---------------------------------------------------------------------------

def test_an_exempt_chapter_owes_nothing_however_large():
    assert owed(40, 6, exempt=True) == 0


def test_exemption_is_a_flag_not_a_name(fx):
    """A name check breaks the first time somebody types 'S.C.L.'"""
    with fx.db.read() as tx:
        scl = tx.one("schools.get", (fx.exempt_id,))
    assert scl["billing_exempt"] == 1
    # Renaming it changes nothing about whether it is billed.
    assert owed(10, 2, exempt=bool(scl["billing_exempt"])) == 0


# ---------------------------------------------------------------------------
# Discounts
# ---------------------------------------------------------------------------

def test_a_discount_comes_off_the_total():
    assert owed(10, 1, discount_cents=20000) == 10 * 14000 - 20000


def test_a_discount_larger_than_the_bill_floors_at_zero():
    """Never a credit. There are no refunds, so a credit is a number nobody
    would ever act on."""
    assert owed(1, 0, discount_cents=99999999) == 0


def test_a_negative_discount_cannot_inflate_the_bill():
    """The column has a CHECK, but the arithmetic refuses it too -- a discount
    that quietly became a surcharge is the worst possible rounding of this."""
    assert owed(2, 0, discount_cents=-5000) == 2 * 14000


def test_discount_applies_after_the_free_adult_allowance():
    gross = 12 * 14000 + 7500      # 12 delegates -> 2 free adults, 3rd charged
    assert owed(12, 3, discount_cents=10000) == gross - 10000


# ---------------------------------------------------------------------------
# No refunds: cancelled versus cancelled_paid
# ---------------------------------------------------------------------------

def test_billable_counts_include_people_cancelled_after_payment():
    counts = {
        "delegates_active": 28, "delegates_cancelled": 1,
        "delegates_cancelled_paid": 2,
        "adults_active": 4, "adults_cancelled": 0, "adults_cancelled_paid": 1,
    }
    assert billable_counts(counts) == (30, 5)


def test_cancelling_before_payment_lowers_the_invoice(fx):
    # Uni starts with 1 delegate and 2 adults: one adult is free, so
    # $140 + $75 = $215.
    assert fx.stats_for(fx.uni_id)["amount_owed_cents"] == 14000 + 7500

    actor = fx.principal("uni_sponsor")
    with fx.db.tx() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        person = dict(tx.one("people.get", (fx.delegate_id,)))
        applied = roster.cancel(tx, school, actor, person)

    assert applied == "cancelled"
    after = fx.stats_for(fx.uni_id)
    # Now 0 delegates and 2 adults. The bill falls by the delegate's $140 but
    # RISES by $75, because the free-adult allowance is ceil(delegates / 10) and
    # a chapter with no delegates earns no free adult. See the test below.
    assert after["amount_owed_cents"] == 2 * 7500
    assert after["delegates_cancelled"] == 1
    assert after["delegates_cancelled_paid"] == 0


def test_losing_a_delegate_can_cost_a_free_adult(fx):
    """A consequence of the fee rule that surprises people, so it is pinned here.

    The allowance is ceil(delegates / 10), so the 1st, 11th, and 21st delegate
    each carry a free adult with them. Cancelling one of those delegates removes
    that allowance, and the chapter's bill drops by $140 - $75 = $65 rather than
    by the full $140. Not a bug -- but a sponsor WILL ask, and the invoice page
    shows the free-adult line so the arithmetic is visible rather than magic.
    """
    # With 2 adults: the 11th delegate raises the allowance from 1 to 2, so the
    # second adult stops being charged and the chapter pays $140 - $75 = $65.
    assert owed(11, 2) - owed(10, 2) == 14000 - 7500

    # With 1 adult: the allowance already covers everyone, so there is no
    # discount to gain and the 11th delegate costs the full $140.
    assert owed(11, 1) - owed(10, 1) == 14000


def test_cancelling_after_payment_leaves_the_invoice_alone(fx):
    """THE no-refunds rule. A student who drops out after the chapter's check
    has arrived still counts, so the balance keeps reading zero rather than
    turning into a credit nobody intends to pay back."""
    actor = fx.principal("chair")
    with fx.db.tx() as tx:
        tx.insert("payments.create", (
            fx.uni_id, 50000, "check", "1041", "2027-01-15", None,
            fx.chair_id, clock.now_iso()))
        tx.audit("payment.record", "Chair recorded a payment.",
                 school_id=fx.uni_id, value_detail={"amount_cents": 50000})
        stats.recompute(tx, fx.uni_id, settings=settings.fee_settings(tx))

    before = fx.stats_for(fx.uni_id)["amount_owed_cents"]
    sponsor = fx.principal("uni_sponsor")
    with fx.db.tx() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        person = dict(tx.one("people.get", (fx.delegate_id,)))
        applied = roster.cancel(tx, school, sponsor, person)

    assert applied == "cancelled_paid"
    after = fx.stats_for(fx.uni_id)
    assert after["amount_owed_cents"] == before
    assert after["delegates_cancelled_paid"] == 1
    assert after["delegates_cancelled"] == 0


def test_a_cancelled_person_is_not_in_the_public_statistics(fx):
    """Billable is not the same as attending. Someone cancelled after payment
    counts toward the money and toward nothing else."""
    before = fx.public_stats()["delegates"]
    actor = fx.principal("uni_sponsor")
    with fx.db.tx() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        person = dict(tx.one("people.get", (fx.delegate_id,)))
        roster.cancel(tx, school, actor, person)
    assert fx.public_stats()["delegates"] == before - 1


def test_cancelling_is_audited_with_the_reason_in_words(fx):
    actor = fx.principal("uni_sponsor")
    with fx.db.tx() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        person = dict(tx.one("people.get", (fx.delegate_id,)))
        roster.cancel(tx, school, actor, person)

    with fx.db.read() as tx:
        entry = [r for r in tx.all("audit.recent", (10 ** 9, 50))
                 if r["action"] == "person.cancel"][0]
    assert "cancelled Dana Delegate" in entry["summary"]


def test_restoring_puts_them_back_on_the_invoice(fx):
    actor = fx.principal("uni_sponsor")
    with fx.db.tx() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        person = dict(tx.one("people.get", (fx.delegate_id,)))
        roster.cancel(tx, school, actor, person)
    assert fx.stats_for(fx.uni_id)["amount_owed_cents"] == 2 * 7500

    with fx.db.tx() as tx:
        school = dict(tx.one("schools.get", (fx.uni_id,)))
        person = dict(tx.one("people.get", (fx.delegate_id,)))
        roster.restore(tx, school, actor, person)

    # Exactly back where it started -- restore is a true inverse of cancel.
    assert fx.stats_for(fx.uni_id)["amount_owed_cents"] == 14000 + 7500
    assert fx.stats_for(fx.uni_id)["delegates_cancelled"] == 0


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

def test_payments_are_append_only_and_a_correction_is_a_new_row(fx):
    """A correction is a NEW row, possibly negative, never an edit. This is also
    the mechanism for sending money back if a fee is ever lowered mid-cycle."""
    with fx.db.tx() as tx:
        tx.insert("payments.create", (fx.uni_id, 500000, "check", "1041",
                                      "2027-01-15", None, fx.chair_id, clock.now_iso()))
        tx.audit("payment.record", "Chair recorded $5,000.00.",
                 school_id=fx.uni_id, value_detail={"amount_cents": 500000})
        stats.recompute(tx, fx.uni_id, settings=settings.fee_settings(tx))
    assert fx.stats_for(fx.uni_id)["amount_paid_cents"] == 500000

    with fx.db.tx() as tx:
        tx.insert("payments.create", (fx.uni_id, -100000, "check", "refund",
                                      "2027-02-01", "fee lowered", fx.chair_id,
                                      clock.now_iso()))
        tx.audit("payment.record", "Chair recorded a refund of $1,000.00.",
                 school_id=fx.uni_id, value_detail={"amount_cents": -100000})
        stats.recompute(tx, fx.uni_id, settings=settings.fee_settings(tx))

    assert fx.stats_for(fx.uni_id)["amount_paid_cents"] == 400000
    with fx.db.read() as tx:
        assert len(tx.all("payments.for_school", (fx.uni_id,))) == 2


def test_the_state_board_never_gets_an_invoice(fx):
    """It is an organization, not a chapter. It has admins attached to it only
    because people.school_id is NOT NULL."""
    assert fx.stats_for(fx.board_id)["amount_owed_cents"] == 0


def test_the_state_board_is_absent_from_the_public_school_count(fx):
    public = fx.public_stats()
    with fx.db.read() as tx:
        chapters = len(tx.all("schools.list"))
    assert public["schools_ms"] + public["schools_hs"] == chapters


def test_the_state_board_is_absent_from_the_chair_dashboard(fx):
    with fx.db.read() as tx:
        names = {r["name"] for r in tx.all("stats.dashboard")}
    assert "CAJCL State Board" not in names
    assert "University High School" in names


def test_money_is_always_integer_cents(fx):
    """Never a float, anywhere, for any reason."""
    row = fx.stats_for(fx.uni_id)
    for key in ("amount_owed_cents", "amount_paid_cents", "discount_cents"):
        assert isinstance(row[key], int)


# ---------------------------------------------------------------------------
# INVARIANT 2: the counters move with the data
# ---------------------------------------------------------------------------

COUNTER_KEYS = ("delegates_active", "adults_active",
                "delegates_cancelled_paid", "adults_cancelled_paid")


def stored_vs_actual(db):
    """Every school's stored counters, beside what the rows actually say.

    `SUM(...)` over zero rows is NULL, not 0, so a chapter with nobody in it
    reports None for every count while the stored value is a real 0. Both mean
    the same thing; normalising here keeps that out of the assertions.
    """
    out = []
    with db.read() as tx:
        for school in tx.all("schools.all_including_organizations"):
            stored = dict(tx.one("stats.for_school", (school["id"],)) or {})
            actual = dict(tx.one("stats.count_school", (school["id"],)) or {})
            out.append((
                school["name"],
                {k: stored.get(k) or 0 for k in COUNTER_KEYS},
                {k: actual.get(k) or 0 for k in COUNTER_KEYS},
            ))
    return out


def test_stored_counters_agree_with_the_rows(fx):
    """Recomputing must be a no-op. If it is not, something wrote to `people`
    without recomputing, and the difference is invisible until an invoice is
    wrong.

    This is how `scripts/add_board.py` was found charging a chapter for adults
    it then left out of the amount owed: it inserted people and never called
    stats.recompute, so `school_stats` held numbers from before. Nothing
    failed. The arithmetic simply stopped agreeing with itself.
    """
    disagreements = []
    for name, stored, actual in stored_vs_actual(fx.db):
        for key in COUNTER_KEYS:
            if stored.get(key, 0) != actual.get(key, 0):
                disagreements.append(
                    f"{name}.{key}: stored {stored.get(key)} != actual {actual.get(key)}")
    assert disagreements == [], "\n".join(disagreements)


def test_an_invoice_adds_up_to_what_is_owed(fx):
    """The lines are computed from the counters and the total is read from
    them, so the two can drift apart in exactly one way: stale counters."""
    from backend.lib import printing

    with fx.db.read() as tx:
        for row in tx.all("schools.list"):
            school = dict(tx.one("schools.get", (row["id"],)))
            context = printing.invoice_context(tx, school)
            if context["exempt"]:
                assert context["amount_owed_cents"] == 0
                continue
            lines = sum(line["amount_cents"] for line in context["lines"])
            expected = max(0, lines - context["discount_cents"])
            assert expected == context["amount_owed_cents"], (
                f"{school['name']}: lines add to {lines} less "
                f"{context['discount_cents']} discount, but owed is "
                f"{context['amount_owed_cents']}")


def test_provisioning_the_board_keeps_the_counters_honest(fx):
    """The specific path that was wrong."""
    import scripts.add_board as add_board

    add_board.run(fx.db, [
        {"first": "Grace", "last": "Hopper", "title": "Convention President",
         "school": "University High School", "roles": ["admin"]},
        {"first": "Ada", "last": "Lovelace", "type": "adult", "title": "Sponsor",
         "school": "University High School", "roles": ["sponsor"]},
    ], create_schools=True)

    disagreements = []
    for name, stored, actual in stored_vs_actual(fx.db):
        if stored.get("delegates_active", 0) != actual.get("delegates_active", 0) \
           or stored.get("adults_active", 0) != actual.get("adults_active", 0):
            disagreements.append(name)
    assert disagreements == [], disagreements
