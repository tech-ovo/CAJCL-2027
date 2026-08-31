"""The activity and volunteer-role catalog, and who is eligible for what.

CACHING
    ~150 rows, read on nearly every form load. Loaded ONCE per container into
    memory and refreshed on mutation. It is never queried per request: doing so
    would spend 150 row reads to render a form that has not changed since
    September.

ELIGIBILITY IS RETURNED, NOT APPLIED
    The server sends every item the person's chapter and type allow, each with
    its eligibility rule and a computed `eligible_now`. It does NOT filter out
    the ones they cannot pick.

    That is deliberate. Both forms require ineligible options to be shown
    DISABLED with the requirement stated, never hidden -- a delegate who cannot
    find Grammar 2 assumes the site is broken, and an adult who cannot find
    Certamen Reader assumes they were not trusted with it. It also means the
    delegate can change their Latin level and watch the tests enable and disable
    live, with no round trip on a cold container.

    The client's gating is a courtesy. validate_selections() below is the
    authority, and it runs again on submit.
"""

from __future__ import annotations

import time

from .db import Tx

CACHE_SECONDS = 300

LATIN_RANK = {"none": 0, "novice": 1, "intermediate": 2, "advanced": 3}

_cache: dict | None = None
_loaded_at: float = 0.0


def load(tx: Tx, *, force: bool = False) -> dict:
    """The whole catalog: categories, items, and options, cross-linked."""
    global _cache, _loaded_at

    if _cache is not None and not force and (time.monotonic() - _loaded_at) < CACHE_SECONDS:
        return _cache

    categories = [dict(r) for r in tx.all("catalog.categories")]
    items = [dict(r) for r in tx.all("catalog.items")]
    options = [dict(r) for r in tx.all("catalog.options")]

    by_item: dict[int, list[dict]] = {}
    for option in options:
        if option["active"]:
            by_item.setdefault(option["item_id"], []).append(option)

    for item in items:
        item["options"] = by_item.get(item["id"], [])
        item["eligible_latin_levels"] = _csv(item["eligible_latin_levels"])
        item["eligible_school_levels"] = _csv(item["eligible_school_levels"])

    by_category: dict[int, list[dict]] = {}
    for item in items:
        by_category.setdefault(item["category_id"], []).append(item)
    for category in categories:
        category["items"] = by_category.get(category["id"], [])

    _cache = {
        "categories": categories,
        "items_by_id": {i["id"]: i for i in items},
        "categories_by_key": {c["key"]: c for c in categories},
        # EVERY option, including the inactive ones. `item["options"]` above is
        # deliberately the active list -- that is what a delegate may pick from
        # -- but the editing screen has to be able to see a retired medium in
        # order to bring it back, and nothing else can reach it.
        "options": options,
    }
    _loaded_at = time.monotonic()
    return _cache


def invalidate() -> None:
    """Drop this container's cache. Called after any catalog write."""
    global _cache, _loaded_at
    _cache = None
    _loaded_at = 0.0


def _csv(value: str | None) -> list[str]:
    """NULL means 'no restriction', which is not the same as an empty list."""
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

def item_eligibility(item: dict, *, school_level: str,
                     latin_level: str | None = None,
                     latin_knowledge: str | None = None) -> tuple[bool, str]:
    """(eligible, reason). The reason is shown to the person when they cannot.

    The reason is written for the person reading it, not for a log: "Open to
    MS-3 and HS-2" tells a delegate what to do; "ineligible" does not.
    """
    levels = item["eligible_school_levels"]
    if levels and school_level not in levels:
        which = "middle school" if levels == ["MS"] else "high school"
        return False, f"Open to {which} chapters."

    latin_levels = item["eligible_latin_levels"]
    if latin_levels:
        if not latin_level:
            return False, f"Choose your Latin level first. Open to {_join(latin_levels)}."
        if latin_level not in latin_levels:
            return False, f"Open to {_join(latin_levels)}."

    minimum = item.get("min_latin_knowledge")
    if minimum:
        have = LATIN_RANK.get(latin_knowledge or "none", 0)
        if have < LATIN_RANK[minimum]:
            return False, f"Needs {minimum} Latin."

    return True, ""


def _join(values: list[str]) -> str:
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + " and " + values[-1]


def for_person(tx: Tx, *, person_type: str, school_level: str,
               latin_level: str | None = None,
               latin_knowledge: str | None = None) -> list[dict]:
    """The catalog as one person sees it.

    Filtered only on what CANNOT change while the form is open -- person type,
    and the chapter's school level. Everything else is returned with an
    eligibility verdict attached so the client can gate live.

    Chapter-scope items are excluded from an individual's sheet: Kickball,
    Fugepilam, and Ultimate Frisbee are entered once per school by a sponsor or
    chapter leader, not by each delegate.
    """
    data = load(tx)
    out = []
    for category in data["categories"]:
        if not category["active"] or category["applies_to"] != person_type:
            continue

        items = []
        for item in category["items"]:
            if not item["active"] or item["registration_scope"] == "chapter":
                continue
            eligible, reason = item_eligibility(
                item, school_level=school_level, latin_level=latin_level,
                latin_knowledge=latin_knowledge)
            items.append({
                "id": item["id"],
                "name": item["name"],
                "description": item["description"],
                "eligible_now": eligible,
                "reason": reason,
                "eligible_latin_levels": item["eligible_latin_levels"],
                "min_latin_knowledge": item.get("min_latin_knowledge"),
                "max_sub_selections": item["max_sub_selections"],
                "options": [{"id": o["id"], "name": o["name"]} for o in item["options"]],
            })

        if items:
            out.append({
                "key": category["key"],
                "name": category["name"],
                "description": category["description"],
                "min_selections": category["min_selections"],
                "max_selections": category["max_selections"],
                "enforcement": category["enforcement"],
                "items": items,
            })
    return out


def chapter_items(tx: Tx, *, school_level: str) -> list[dict]:
    """Team entries a sponsor or chapter leader registers for the whole school."""
    data = load(tx)
    out = []
    for category in data["categories"]:
        if not category["active"] or category["applies_to"] != "delegate":
            continue
        for item in category["items"]:
            if not item["active"] or item["registration_scope"] != "chapter":
                continue
            levels = item["eligible_school_levels"]
            if levels and school_level not in levels:
                continue
            out.append({"id": item["id"], "name": item["name"],
                        "category": category["name"]})
    return out


# ---------------------------------------------------------------------------
# Validation -- the authority, re-run on every submit
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Blocking problems. The message is shown to the person as-is."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_selections(tx: Tx, selected_ids: list[int], *, person_type: str,
                        school_level: str, latin_level: str | None = None,
                        latin_knowledge: str | None = None) -> list[str]:
    """Check a whole form. Raises on blocking problems; returns warnings.

    Blocking and warning are per-category settings in the dashboard, not
    constants here: academic testing blocks at one-to-three, adult roles warn at
    two, and a future chair can change either without a deploy.
    """
    data = load(tx)
    errors: list[str] = []
    warnings: list[str] = []

    chosen = set(selected_ids)
    if len(chosen) != len(selected_ids):
        errors.append("The same entry was selected twice.")

    for item_id in chosen:
        item = data["items_by_id"].get(item_id)
        if item is None or not item["active"]:
            errors.append("One of those entries is no longer offered.")
            continue
        if item["registration_scope"] == "chapter":
            errors.append(
                f"{item['name']} is a chapter team entry. Your sponsor "
                f"registers it for the whole chapter.")
            continue
        eligible, reason = item_eligibility(
            item, school_level=school_level, latin_level=latin_level,
            latin_knowledge=latin_knowledge)
        if not eligible:
            errors.append(f"{item['name']} is not open to you. {reason}")

    for category in data["categories"]:
        if not category["active"] or category["applies_to"] != person_type:
            continue
        if category["enforcement"] == "none":
            continue

        count = sum(
            1 for item_id in chosen
            if (item := data["items_by_id"].get(item_id))
            and item["category_id"] == category["id"]
        )
        message = _count_message(category, count)
        if message is None:
            continue
        (errors if category["enforcement"] == "block" else warnings).append(message)

    if errors:
        raise ValidationError(errors)
    return warnings


def _count_message(category: dict, count: int) -> str | None:
    """Error copy that says what happened and how to fix it.

    Never "Invalid input" -- "Pick between one and three tests. You have four
    selected." is the standard the whole site is held to.
    """
    low, high = category["min_selections"], category["max_selections"]
    label = category["name"]
    have = f"You have {_word(count)} selected." if count else "You have none selected."

    if low and high and (count < low or count > high):
        if low == high:
            return f"Pick exactly {_word(low)} from {label}. {have}"
        return f"Pick between {_word(low)} and {_word(high)} from {label}. {have}"
    if low and not high and count < low:
        return f"Please pick at least {_word(low)} from {label}. {have}"
    if high and not low and count > high:
        return f"Pick no more than {_word(high)} from {label}. {have}"
    return None


_WORDS = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
          6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
          11: "eleven", 12: "twelve"}


def _word(n: int) -> str:
    return _WORDS.get(n, str(n))


def validate_options(tx: Tx, item_id: int, option_ids: list[int]) -> None:
    """Sub-options must belong to their item and respect its maximum."""
    data = load(tx)
    item = data["items_by_id"].get(item_id)
    if item is None:
        raise ValidationError(["That entry is no longer offered."])

    valid = {o["id"] for o in item["options"]}
    if not set(option_ids) <= valid:
        raise ValidationError([f"An option was chosen that {item['name']} does not offer."])

    limit = item["max_sub_selections"]
    if limit and len(option_ids) > limit:
        raise ValidationError([
            f"Pick no more than {_word(limit)} options for {item['name']}. "
            f"You have {len(option_ids)} selected."
        ])
