"""Access code generation and the check symbol.

The check symbol's only job is to catch a typing mistake before it reaches the
rate limiter. These tests prove it catches the two mistakes people actually
make, exhaustively rather than by sampling.
"""

from __future__ import annotations

import pytest

from backend.lib import codes


def test_generated_codes_are_well_formed():
    for prefix in codes.VALID_PREFIXES:
        display, normalized = codes.generate(prefix)
        assert codes.is_well_formed(display)
        assert codes.normalize(display) == normalized
        assert display.startswith(prefix + "-")
        assert len(display) == len("PPP-XXXXX-XXXXX")


def test_codes_never_contain_confusable_characters():
    """I, L, O and U are absent by construction. A delegate reading a code off a
    printed sheet must not have to decide whether that is a 1 or an I."""
    for _ in range(500):
        _, normalized = codes.generate("DEL")
        assert not (set(normalized[3:]) & set("ILOU"))


def test_the_alphabet_size_equals_the_check_modulus():
    """The invariant the check symbol depends on.

    With 32 characters and a modulus of 31, 'Z' (31) and '0' (0) are congruent
    and swapping them is undetectable. That bug shipped once and these tests
    caught it; this assertion states the reason in one line.
    """
    assert len(codes.ALPHABET) == codes.CHECK_MODULUS
    assert len(set(codes.ALPHABET)) == len(codes.ALPHABET)


def test_check_symbol_catches_every_single_character_substitution():
    """Exhaustive: every data position, every wrong character, many codes."""
    for _ in range(50):
        _, normalized = codes.generate("DEL")
        for position in range(3, len(normalized) - 1):
            for replacement in codes.ALPHABET:
                if replacement == normalized[position]:
                    continue
                broken = normalized[:position] + replacement + normalized[position + 1:]
                assert not codes.is_well_formed(broken), f"missed {normalized} -> {broken}"




def test_check_symbol_catches_every_transposition():
    """Not just adjacent pairs -- any two characters swapped, over many codes."""
    for _ in range(50):
        _, normalized = codes.generate("DEL")
        body = normalized[3:-1]
        for i in range(len(body)):
            for j in range(i + 1, len(body)):
                if body[i] == body[j]:
                    continue
                chars = list(body)
                chars[i], chars[j] = chars[j], chars[i]
                broken = normalized[:3] + "".join(chars) + normalized[-1]
                assert not codes.is_well_formed(broken), f"missed swap in {normalized}"


def test_check_symbol_is_always_a_real_crockford_character():
    """The whole reason for not using Crockford's modulo-37 check: every symbol
    we emit must be typeable, printable, and safe in a URL fragment and a QR."""
    seen = set()
    for _ in range(2000):
        _, normalized = codes.generate("DEL")
        seen.add(normalized[-1])
    assert seen <= set(codes.ALPHABET)
    assert not (seen & set("*~$=U"))


def test_confusables_are_folded_on_input():
    """Someone typing what they see must get in. I and L read as 1; O reads as 0."""
    _, normalized = codes.generate("DEL")
    typed = normalized.replace("1", "I").replace("0", "O")
    assert codes.normalize(typed) == normalized
    assert codes.is_well_formed(typed)


def test_formatting_and_whitespace_are_ignored():
    display, normalized = codes.generate("SPO")
    for variant in (display, display.lower(), display.replace("-", ""),
                    display.replace("-", " "), f"  {display}  "):
        assert codes.normalize(variant) == normalized


def test_the_prefix_is_part_of_the_code():
    """Codes are globally unique ACROSS prefixes. Two people cannot share a body
    with different prefixes and both be valid, because the prefix is hashed."""
    _, normalized = codes.generate("DEL")
    swapped = "VOL" + normalized[3:]
    assert codes.code_hmac(normalized, b"pepper") != codes.code_hmac(swapped, b"pepper")


def test_prefix_letters_are_not_folded():
    """VOL must not normalize to V01. Folding applies to the body only."""
    _, normalized = codes.generate("VOL")
    assert codes.normalize(codes.format_code(normalized)).startswith("VOL")


@pytest.mark.parametrize("bad", [
    "", "DEL", "DEL-K7M2N", "XXX-K7M2N-9PQ4T", "DEL-K7M2N-9PQ4TT",
    "DEL-K7M2N-9PQ4!", "DEL K7M2N 9PQ4",
])
def test_malformed_codes_are_rejected_not_crashed(bad):
    assert codes.is_well_formed(bad) is False


def test_hmac_needs_the_pepper():
    """A database leak alone must not be enough to brute-force 45 bits."""
    _, normalized = codes.generate("DEL")
    assert codes.code_hmac(normalized, b"one") != codes.code_hmac(normalized, b"two")


def test_attempted_hmac_survives_garbage():
    """Rate limiting must still work when the input is nonsense, otherwise the
    per-code limit is trivially bypassed by sending malformed guesses."""
    assert codes.attempted_hmac("not a code at all", b"pepper")
    assert codes.attempted_hmac("", b"pepper")
    assert codes.attempted_hmac("DEL-— ​", b"pepper")
    # Same garbage hashes the same way, or there is nothing to count.
    assert codes.attempted_hmac("zzz", b"p") == codes.attempted_hmac("ZZZ", b"p")


def test_generated_codes_do_not_repeat():
    """45 bits, so collisions are not a practical concern -- but the unique
    index on code_hmac means a collision is an outage for one person, so this
    guards against a generator that is accidentally deterministic."""
    minted = {codes.generate("DEL")[1] for _ in range(5000)}
    assert len(minted) == 5000


# ---------------------------------------------------------------------------
# The prefix says what someone is, not what they can do
# ---------------------------------------------------------------------------

def test_a_prefix_never_depends_on_privileges():
    """Two sponsors doing the same job get the same prefix, whether or not one
    of them also sits on the board.

    The old rule returned ADM for anyone holding scope `*`, which made a stack
    of printed sheets harder to sort rather than easier -- and, far worse,
    implied that granting a role should change someone's code. The prefix is
    part of the string that gets hashed, so it silently would have.
    """
    from backend.lib import auth

    assert auth.code_prefix_for("adult", "sponsor") == "SPO"
    assert auth.code_prefix_for("adult", "chaperone") == "VOL"
    assert auth.code_prefix_for("adult", "other") == "VOL"
    assert auth.code_prefix_for("delegate", None) == "DEL"

    # And there is no way to ask for a different answer.
    import inspect
    signature = inspect.signature(auth.code_prefix_for)
    assert "scopes" not in signature.parameters, (
        "code_prefix_for should not be able to see privileges at all")


def test_nothing_mints_an_ADM_code_any_more():
    from backend.lib import auth

    for person_type, adult_type in [("delegate", None), ("adult", "sponsor"),
                                    ("adult", "chaperone"), ("adult", "scl"),
                                    ("adult", "other"), ("adult", None)]:
        assert auth.code_prefix_for(person_type, adult_type) != "ADM"


def test_an_ADM_code_no_longer_signs_anybody_in():
    """`ADM` is retired outright, not merely unminted.

    Leaving it accepted would have meant board members quietly keeping a code
    that says something the system no longer believes. Removing it means they
    each need a new code and a new sheet, which is the honest cost and is what
    `modal run backend/app.py::retire_adm_codes` pays.
    """
    from backend.lib import codes

    assert "ADM" not in codes.VALID_PREFIXES
    with pytest.raises(ValueError):
        codes.generate("ADM")
    with pytest.raises(ValueError):
        codes.normalize("ADM-K7M2N-9PQ4Z")
    assert not codes.is_well_formed("ADM-K7M2N-9PQ4Z")


def test_the_database_still_permits_an_ADM_row():
    """It has to. Those rows exist until the reissue has run, and a CHECK
    constraint cannot be added that rejects data already in the table. The
    application is the narrower gate."""
    import pathlib as _pathlib

    schema = (_pathlib.Path(__file__).resolve().parents[1]
              / "migrations" / "001_core.sql").read_text(encoding="utf-8")
    assert "code_prefix IN ('SPO','DEL','VOL','ADM')" in schema
