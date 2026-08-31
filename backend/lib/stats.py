"""Counter caches and the invoice.

Both `school_stats` and `public_stats_cache` are recomputed INSIDE the same
transaction as any mutation that changes them. Never afterwards, never on a
timer, never live for a page view. Every function here takes a `Tx`.

The invoice arithmetic lives in Python rather than SQL because it is the piece a
future commissioner is most likely to need to read and check by hand.
"""

from __future__ import annotations

import math

from . import clock
from .db import Tx


def invoice_cents(
    *,
    delegates_billable: int,
    adults_billable: int,
    billing_exempt: bool,
    delegate_cents: int,
    extra_adult_cents: int,
    adult_ratio: int,
    discount_cents: int = 0,
) -> int:
    """What a school owes, in cents.

        fee.delegate_cents x delegates
          + max(0, fee.extra_adult_cents x (adults - ceil(delegates / ratio)))
          - discount

    Each chapter gets one free adult per `adult_ratio` delegates, rounded up, so
    a chapter with five delegates gets one free adult.

    BILLABLE, NOT ACTIVE. There are no refunds -- an event this size runs on
    pre-payment. Someone who withdrew AFTER their chapter paid still counts,
    which is what the `cancelled_paid` status is for. Someone who withdrew
    before any payment arrived does not, and the invoice falls. See
    billable_counts().

    Exemption is a FLAG, never a name check. A name check breaks the first time
    someone types "S.C.L." or a second exempt chapter appears. SCL sends real
    people who need real accounts and real forms; it is simply not billed.

    MEMBERS AT LARGE PAY. They are an organization rather than a chapter, which
    is a separate question from whether they are billed -- the two ideas are
    deliberately two columns.

    The discount is an ad-hoc reduction an admin sets by hand: a new-chapter
    discount, a hardship arrangement, or the way a fee change gets honoured
    after invoices have gone out. Floored at zero -- a discount larger than the
    bill produces nothing owed, never a credit.
    """
    if billing_exempt:
        return 0

    delegate_total = delegate_cents * delegates_billable
    free_adults = math.ceil(delegates_billable / adult_ratio) if adult_ratio else 0
    chargeable_adults = max(0, adults_billable - free_adults)
    gross = delegate_total + extra_adult_cents * chargeable_adults
    return max(0, gross - max(0, discount_cents))


def billable_counts(counts: dict) -> tuple[int, int]:
    """(delegates, adults) that count toward the invoice.

    Active people, PLUS people who cancelled after their chapter had already
    paid. That second group is not attending, and appears nowhere in the public
    statistics or in the chair's completion tracking. They exist in this one
    calculation so a settled balance keeps reading zero, rather than turning
    into a credit nobody intends to refund.
    """
    delegates = counts["delegates_active"] + counts["delegates_cancelled_paid"]
    adults = counts["adults_active"] + counts["adults_cancelled_paid"]
    return delegates, adults


# --- On changing a fee mid-cycle -------------------------------------------
#
# Deliberately not modelled. There is no fee snapshot per school and no
# effective date on the fee setting, because the fee is not expected to change
# once registration opens.
#
# If it has to, it is handled by hand and the mechanism already exists:
#   - Fee goes UP: leave already-invoiced schools alone by giving each of them
#     a discount equal to the increase.
#   - Fee goes DOWN and you want to honour it: the recomputed invoice drops on
#     its own. For schools that already paid the higher amount, send the
#     difference back and record a NEGATIVE payment for it, so the history shows
#     the money leaving.
#
# Both paths leave a readable trail in the payment history and the audit log,
# which is worth more than machinery that runs once every ten years.
# ---------------------------------------------------------------------------


def recompute_school(tx: Tx, school_id: int, *, settings: dict) -> dict:
    """Recompute one school's counters. Call inside the mutating transaction.

    Reads only that school's own rows (indexed by idx_people_school), so this is
    cheap enough to run on every roster change.
    """
    counts = tx.one("stats.count_school", (school_id,)) or {}
    paid = tx.value("stats.paid_for_school", (school_id,), default=0) or 0

    school = tx.one("schools.get", (school_id,))
    if school is None:
        raise ValueError(f"no school {school_id}")

    numbers = {
        "delegates_active": counts.get("delegates_active") or 0,
        "delegates_cancelled": counts.get("delegates_cancelled") or 0,
        "delegates_cancelled_paid": counts.get("delegates_cancelled_paid") or 0,
        "adults_active": counts.get("adults_active") or 0,
        "adults_cancelled": counts.get("adults_cancelled") or 0,
        "adults_cancelled_paid": counts.get("adults_cancelled_paid") or 0,
        "delegates_complete": counts.get("delegates_complete") or 0,
        "adults_complete": counts.get("adults_complete") or 0,
        # Counted by the same query, over rows it was already reading. See
        # migration 012 for why these are stored rather than aggregated live.
        "meal_regular": counts.get("meal_regular") or 0,
        "meal_vegetarian": counts.get("meal_vegetarian") or 0,
        "meal_gluten_free": counts.get("meal_gluten_free") or 0,
        "meal_unanswered": counts.get("meal_unanswered") or 0,
        "meal_none": counts.get("meal_none") or 0,
        "adults_sponsors": counts.get("adults_sponsors") or 0,
        "adults_chaperones": counts.get("adults_chaperones") or 0,
    }

    delegates_billable, adults_billable = billable_counts(numbers)
    discount = int(school["discount_cents"] or 0)

    owed = invoice_cents(
        delegates_billable=delegates_billable,
        adults_billable=adults_billable,
        billing_exempt=bool(school["billing_exempt"]),
        delegate_cents=int(settings["fee.delegate_cents"]),
        extra_adult_cents=int(settings["fee.extra_adult_cents"]),
        adult_ratio=int(settings["fee.adult_ratio"]),
        discount_cents=discount,
    )

    # An organization is not a chapter: SCL, members at large. They have no
    # invoice, because there is no school to send one to.
    #
    # Their PEOPLE still count -- they are attending -- which is why
    # stats.recompute_public sums delegates and adults across every active
    # school and counts only chapters as chapters.
    if school["kind"] != "chapter":
        owed = 0
        discount = 0

    tx.run("stats.upsert_school", (
        school_id,
        numbers["delegates_active"], numbers["delegates_cancelled"],
        numbers["delegates_cancelled_paid"],
        numbers["adults_active"], numbers["adults_cancelled"],
        numbers["adults_cancelled_paid"],
        numbers["delegates_complete"], numbers["adults_complete"],
        numbers["meal_regular"], numbers["meal_vegetarian"],
        numbers["meal_gluten_free"], numbers["meal_unanswered"],
        numbers["meal_none"],
        numbers["adults_sponsors"], numbers["adults_chaperones"],
        discount, owed, paid, clock.now_iso(),
    ))

    return {
        **numbers,
        "delegates_billable": delegates_billable,
        "adults_billable": adults_billable,
        "discount_cents": discount,
        "amount_owed_cents": owed,
        "amount_paid_cents": paid,
    }


def recompute_public(tx: Tx) -> None:
    """Refresh the single row the welcome page reads.

    Derived from school_stats (~50 rows), never from `people` (~1,150 rows).
    """
    tx.run("stats.recompute_public", (clock.now_iso(),))


def recompute(tx: Tx, school_id: int, *, settings: dict) -> dict:
    """Recompute a school and the public totals together.

    Almost every caller wants both: a delegate added to a chapter changes that
    chapter's counters AND the number on the welcome page. Keeping them in one
    function means nobody forgets the second half.
    """
    numbers = recompute_school(tx, school_id, settings=settings)
    recompute_public(tx)
    return numbers


def recompute_all(tx: Tx, *, settings: dict) -> int:
    """Recompute every school. For seeding, and after a discount or fee change.

    Deliberately NOT called from a request path: it is O(schools) queries, which
    is exactly the "query inside a loop" this system forbids everywhere else.
    Acceptable here because it runs from a script or a rare admin action, and
    each iteration is itself indexed.
    """
    school_ids = [row["id"] for row in tx.all("schools.all_ids")]
    for school_id in school_ids:
        recompute_school(tx, school_id, settings=settings)
    recompute_public(tx)
    return len(school_ids)
