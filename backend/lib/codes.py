"""Access codes: generation, normalization, the check symbol, and the HMAC.

Pure functions. Nothing here touches the database or the network, so all of it
is testable in isolation and none of it can leak.

FORMAT
    PPP-XXXXX-XXXXX

    PPP   a three-letter prefix: SPO sponsor, DEL delegate, VOL adult
          volunteer or chaperone, ADM admin. The prefix is display and
          disambiguation only -- it is NOT a namespace. Codes are globally
          unique across prefixes, and the prefix is part of what gets hashed.

    The ten characters after the prefix are nine random Crockford Base32
    characters (45 bits of entropy) plus one check symbol, grouped 5 and 5
    purely so a human can read it aloud without losing their place.

WHY CROCKFORD BASE32
    Its alphabet omits I, L, O, and U. The first three are omitted because a
    delegate reading a code off a printed sheet will confuse them with 1 and 0;
    U is omitted so the generator cannot accidentally spell something a teacher
    would have to explain. Decoding maps I and L to 1 and O to 0, so a person
    who types what they think they see still gets in.

THE CHECK SYMBOL
    Crockford's own check symbol is modulo 37, which produces five characters
    (* ~ $ = U) outside the data alphabet. We do not use those: roughly one code
    in seven would carry one, `~` and `=` push the printed QR out of its compact
    alphanumeric mode, and a `U` check symbol looks like data to whoever is
    typing it back in.

    Instead: a position-weighted sum modulo 31, over an alphabet of 31
    characters. Thirty-one is prime, so this detects EVERY single-character
    substitution and EVERY transposition of two characters -- the two mistakes
    people actually make -- and every possible output is an ordinary Crockford
    character.

    THE ALPHABET AND THE MODULUS MUST MATCH. An earlier version of this kept all
    32 Crockford characters and took the sum modulo 31, which silently failed:
    'Z' has value 31 and '0' has value 0, and 31 is congruent to 0 modulo 31, so
    typing one for the other produced the same check symbol and sailed straight
    through. Dropping 'Z' makes the character values 0-30, all distinct modulo
    31, and the guarantee exact. The cost is 0.4 bits of entropy across the
    whole code, which is nothing; the exhaustive tests in test_codes.py are what
    caught it and what keeps it caught.

    The check symbol is validated in the browser before any request is sent, so
    a mistyped code produces "check that code again" immediately instead of
    burning an attempt against the rate limiter.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

# Crockford Base32, minus 'Z'. Index in this string IS the character's value,
# so there are exactly CHECK_MODULUS of them and every value is distinct modulo
# it. Adding a 32nd character back would break the check symbol -- see the
# module docstring. Keep len(ALPHABET) == CHECK_MODULUS.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXY"
CHECK_MODULUS = 31     # prime, so transpositions are always caught

# What a human might type instead of what we printed. I and L read as 1, O as 0.
CONFUSABLES = {"I": "1", "L": "1", "O": "0"}

VALID_PREFIXES = ("SPO", "DEL", "VOL", "ADM")

DATA_LENGTH = 9        # random characters: 9 * log2(31) = 44.6 bits

assert len(ALPHABET) == CHECK_MODULUS, (
    "the check symbol is only exact when the alphabet size equals the modulus"
)


def _char_value(ch: str) -> int:
    """Value of one Crockford character, after folding confusables.

    Raises ValueError on anything not in the alphabet, which is how a code
    containing a stray character fails fast rather than hashing to nothing.
    """
    ch = CONFUSABLES.get(ch, ch)
    index = ALPHABET.find(ch)
    if index < 0:
        raise ValueError(f"{ch!r} is not a Crockford Base32 character")
    return index


def check_symbol(data: str) -> str:
    """The check symbol for a run of Crockford data characters.

    Position-weighted so that swapping any two characters changes the result:
    weights are distinct and non-zero modulo a prime, which is the whole trick.
    """
    total = sum((i + 1) * _char_value(ch) for i, ch in enumerate(data))
    return ALPHABET[total % CHECK_MODULUS]


def normalize(code: str) -> str:
    """Fold a typed code into the exact string that gets hashed.

    Uppercases, drops hyphens and whitespace, and maps I/L to 1 and O to 0, so
    `del k7m2n 9pq4t`, `DEL-K7M2N-9PQ4T`, and `DELK7M2NgPQ4T` with a mistyped
    letter-O all normalize to the same thing where they legitimately should.

    Raises ValueError if the result is not a well-formed code. Callers treat
    that as "wrong code" -- never as a server error.
    """
    stripped = "".join(code.split()).replace("-", "").replace("–", "").upper()

    if len(stripped) != 3 + DATA_LENGTH + 1:
        raise ValueError("a code is a three-letter prefix followed by ten characters")

    prefix, body = stripped[:3], stripped[3:]
    if prefix not in VALID_PREFIXES:
        raise ValueError(f"{prefix!r} is not a known code prefix")

    # Fold confusables in the body only. The prefixes are all real letters and
    # folding them would turn VOL into V01.
    body = "".join(CONFUSABLES.get(ch, ch) for ch in body)
    for ch in body:
        if ch not in ALPHABET:
            raise ValueError(f"{ch!r} is not a Crockford Base32 character")

    return prefix + body


def is_well_formed(code: str) -> bool:
    """True if the code parses and its check symbol agrees.

    This is the function the browser mirrors. It proves nothing about whether
    the code exists -- only that it was typed correctly.
    """
    try:
        normalized = normalize(code)
    except ValueError:
        return False
    data, check = normalized[3:-1], normalized[-1]
    return check_symbol(data) == check


def format_code(normalized: str) -> str:
    """PPPXXXXXXXXXX -> PPP-XXXXX-XXXXX, for display and print only."""
    return f"{normalized[:3]}-{normalized[3:8]}-{normalized[8:]}"


def generate(prefix: str) -> tuple[str, str]:
    """Mint a new code. Returns (display_form, normalized_form).

    The display form is shown to a human exactly once -- on the printed sheet or
    in the one-time reveal after regeneration -- and is never stored anywhere.
    The normalized form is what gets peppered and hashed.

    Uses secrets.choice, not random.choice: this is a bearer credential.
    """
    if prefix not in VALID_PREFIXES:
        raise ValueError(f"{prefix!r} is not a known code prefix")
    data = "".join(secrets.choice(ALPHABET) for _ in range(DATA_LENGTH))
    normalized = prefix + data + check_symbol(data)
    return format_code(normalized), normalized


def code_hmac(normalized: str, pepper: bytes) -> str:
    """HMAC-SHA256(pepper, normalized_code), hex.

    Peppered rather than plain-hashed so that a database leak on its own cannot
    brute-force 45 bits of entropy -- which a laptop would do in minutes. The
    pepper lives in Modal Secrets and never in the database or the repository.

    Keyed hashing rather than Argon2 because this has to stay an O(1) indexed
    lookup: `WHERE code_hmac = ?` against a unique index. A slow KDF would make
    login a full table scan, which on Turso is billed per row.
    """
    return hmac.new(pepper, normalized.encode("ascii"), hashlib.sha256).hexdigest()


def attempted_hmac(raw: str, pepper: bytes) -> str:
    """HMAC of whatever was typed, valid or not, for the per-code rate limit.

    A failed attempt matches no row in `people` by definition, so without this
    there is nothing to count against. Storing it is safe -- it is a keyed hash
    of a guess and reveals nothing an attacker holding the database does not
    already have -- and it is what distinguishes one delegate fumbling their own
    code from someone walking the keyspace. Never store the raw guess.

    Falls back to hashing the raw string when it will not even normalize, so
    that garbage attempts are still rate-limited.
    """
    try:
        subject = normalize(raw)
    except ValueError:
        subject = "MALFORMED:" + "".join(raw.split()).upper()[:64]
    return hmac.new(pepper, subject.encode("utf-8", "replace"), hashlib.sha256).hexdigest()
