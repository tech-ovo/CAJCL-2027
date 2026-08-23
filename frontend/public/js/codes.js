/* codes.js — the check symbol, validated in the browser.
 *
 * THIS MIRRORS backend/lib/codes.py EXACTLY. If you change one, change both,
 * and check backend/tests/test_codes.py still passes.
 *
 * Why it exists: a mistyped code must produce "check that code again"
 * immediately, without a request. Otherwise every typo burns an attempt against
 * the rate limiter, and a delegate who fumbles their code five times locks
 * themselves out of their own account for an hour.
 *
 * This proves nothing about whether a code EXISTS -- only that it was typed
 * correctly. The server is the authority on everything else.
 */

/* Crockford Base32 minus 'Z'. There are exactly CHECK_MODULUS characters and
 * every value is distinct modulo it. With 32 characters and a modulus of 31,
 * 'Z' (31) and '0' (0) are congruent and swapping them is undetectable -- that
 * bug shipped once. Keep ALPHABET.length === CHECK_MODULUS. */
export const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXY";
const CHECK_MODULUS = 31;

/* I and L read as 1, O reads as 0. Someone typing what they see must get in. */
const CONFUSABLES = { I: "1", L: "1", O: "0" };

const PREFIXES = ["SPO", "DEL", "VOL", "ADM"];
const DATA_LENGTH = 9;

/** Fold a typed code into the exact string the server hashes, or null. */
export function normalize(code) {
  const stripped = String(code || "")
    .replace(/[\s–-]/g, "")
    .toUpperCase();

  if (stripped.length !== 3 + DATA_LENGTH + 1) return null;

  const prefix = stripped.slice(0, 3);
  if (!PREFIXES.includes(prefix)) return null;

  // Fold confusables in the BODY only -- folding the prefix turns VOL into V01.
  let body = "";
  for (const character of stripped.slice(3)) {
    const folded = CONFUSABLES[character] || character;
    if (!ALPHABET.includes(folded)) return null;
    body += folded;
  }
  return prefix + body;
}

/** The check symbol for a run of data characters. */
export function checkSymbol(data) {
  let total = 0;
  for (let i = 0; i < data.length; i += 1) {
    total += (i + 1) * ALPHABET.indexOf(data[i]);
  }
  return ALPHABET[total % CHECK_MODULUS];
}

/** True if the code parses and its check symbol agrees. */
export function checkSymbolOk(code) {
  const normalized = normalize(code);
  if (!normalized) return false;
  const data = normalized.slice(3, -1);
  return checkSymbol(data) === normalized.slice(-1);
}

/** PPPXXXXXXXXXX -> PPP-XXXXX-XXXXX, for display as someone types. */
export function formatCode(code) {
  const raw = String(code || "").replace(/[^A-Za-z0-9]/g, "").toUpperCase();
  const parts = [raw.slice(0, 3), raw.slice(3, 8), raw.slice(8, 13)].filter(Boolean);
  return parts.join("-");
}
