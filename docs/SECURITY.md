# Security

What protects the people in this database, what would have to fail, and what is
deliberately not protected. Written to be handed to somebody outside the
project — a district reviewer, a parent who asks, next year's commissioner.

Kept honest rather than reassuring. Everything below was read out of the code
rather than remembered, and the parts that are weak say so.

---

## 1. What is actually in here

**The sensitive thing is a list of minors' names**, with their school, grade,
Latin level, and the events they entered. For delegates there is also a
guardian's name and phone number where a sponsor typed one in.

**What is deliberately absent, and cannot leak because it was never collected:**

| | |
| --- | --- |
| Delegate email addresses | Never asked for. Several delegates are eleven years old. |
| Medical information | Paper. Scanned by sponsors into a Drive folder no code here reads. |
| Waivers and signatures | Same. |
| Home addresses | Never asked for. |
| Payment card details | None. Chapters pay by cheque, by post. |
| Passwords | There are none. |

The largest realistic loss is **a roster of names** — one chapter's, or all of
them. That is what the rest of this document is about.

---

## 2. How somebody proves who they are

One code per person, `PPP-XXXXX-XXXXX`: a three-letter prefix saying what they
are, nine random Crockford Base32 characters, and a check symbol.

**Entropy: 9 × log₂(31) = 44.6 bits.** About 26 trillion possibilities.

**Codes are never stored.** The database holds `HMAC-SHA256(pepper, code)`. The
pepper lives in Modal Secrets — not in the database, not in this repository, not
in the frontend. Somebody who steals the whole database still cannot work out
anybody's code, and cannot brute-force 44.6 bits without also stealing the
pepper from a different system.

This is why a lost code cannot be recovered and has to be reissued. That is a
real inconvenience and it is the direct consequence of the property above.

**Session tokens** are 32 random bytes (256 bits), stored as a SHA-256 hash. No
pepper there, and none is needed: there is nothing to brute-force at 256 bits.

### Rate limits, and what they actually stop

| | |
| --- | --- |
| Five wrong attempts on **one code** within an hour | That code stops answering |
| Ten wrong attempts from **one address** within fifteen minutes | That address is paused |

**Be precise about what the first one does.** It is keyed by the code that was
*typed*, so it protects a real person whose code somebody is guessing at. It
does **not** slow an attacker trying many *different* codes, because each guess
lands in its own bucket. Against that attacker only the per-address limit
applies: ten per fifteen minutes, or about 960 a day.

Even so the arithmetic is not close. From a thousand addresses at once, 2⁴⁴·⁶
guesses at 960 a day each is **on the order of seventy million years**. Guessing
codes is not the way in.

---

## 3. How somebody is stopped from reading what is not theirs

Every endpoint declares the scope it requires as a real object, not a comment.
The test suite walks all fifty-six guarded routes and asserts each one refuses a
wrong-scope credential and a wrong-school credential. **A route added without a
guard fails that test**, which is the point of writing it that way.

Scopes reach a person **only** through `person_roles → roles → role_scopes`.
There is no table attaching a scope to a person, and there never will be — the
schema says so in a comment above the tables and the tests enforce it.

Identity scopes (`sponsor`, `delegate`, `chapter`) are always limited to the
holder's own school. Administrative scopes (`registration`, `academics`,
`awards`, `*`) are global; there are a handful of holders and they are the
convention board.

**Nothing unauthenticated returns a name.** The three public endpoints return
aggregate counts, convention facts, and the announcement banner. That is the
whole unauthenticated surface besides sign-in and a health check.

---

## 4. What would have to fail

Ordered by how likely it is, not how bad it is.

| What fails | What is lost |
| --- | --- |
| **A sponsor's sheet is photographed, forwarded, or left on a desk** | That one chapter's roster, about thirty names. This is the realistic one. |
| **A chair's or president's code leaks the same way** | Every chapter. |
| A shared laptop is left signed in | Whatever that person could see. Sign-out is on every page for this reason, and sessions can be revoked individually from the account page. |
| The Turso auth token leaks | The whole database. Names are plaintext there — see §5. Codes are not. |
| Modal Secrets are compromised | The pepper *and* the database token. Everything, including the ability to compute codes from the stored hashes. |
| A new endpoint ships without a guard | Nothing — CI fails first. |
| SQL injection | Nothing. Every statement is a named, parameterised query in `backend/queries/*.sql`; a test refuses any query containing a format placeholder. There is no string-built SQL anywhere. |
| Cross-site scripting | Nothing found. The frontend never uses `innerHTML`; every value goes through `document.createTextNode`. A test enforces it. |

**The honest summary: the codes are the security.** Almost every path above is
somebody's sheet going astray rather than a technical break. That is worth
knowing because it decides where effort belongs — see §7.

---

## 5. Encryption

**In transit:** HTTPS everywhere. The browser talks to Modal over TLS; Modal
talks to Turso over TLS. The frontend never holds a database credential.

**At rest:** the database sits on Turso's hosted storage, which is encrypted at
rest by the provider. **The application encrypts nothing at the column level.**

State that plainly to a reviewer: **names, guardian names and phone numbers are
readable to anybody holding the database file or its auth token.** Only three
things are protected against that: access codes (peppered HMAC), session tokens
(hashed), and IP addresses (peppered HMAC).

Column-level encryption was not done, and the reason is that it would buy less
than it looks like. The application has to search and sort on names — that is
what a roster is — so they would have to be decrypted in the same process that
holds the key, which is the process an attacker would already have to reach. It
would defend against exactly one attacker: somebody who obtains the storage and
nothing else.

---

## 6. Weaknesses this review found

Listed because a review that finds nothing was not a review.

**Fixed while writing this.** IP addresses were hashed with a plain SHA-256.
IPv4 is 2³² addresses; anybody holding the database could have recovered every
address in it by hashing the whole space, which is minutes of ordinary
hardware. Now peppered, like the codes. There is a test.

**Fixed while writing this.** The API sent no security headers at all. It now
sends `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: strict-origin-when-cross-origin`, and a
`Content-Security-Policy` of `frame-ancestors 'none'; base-uri 'none'`.

The policy is deliberately only those two directives. A `default-src 'none'`
would also have applied to the two responses that are real HTML documents — the
printed packet and the printed invoice — both of which carry an inline
`<style>`, and both of which would have printed as unstyled text. The packet is
the most important thing this system produces on paper.

**Still open:** the frontend itself is served by GitHub Pages, which sets no CSP
of its own. A meta-tag policy on `index.html` would cover it, and has not been
written.

**Open — a 180-day session.** A sponsor's session on a school Chromebook is
valid for six months. That is a deliberate trade against making people re-enter
a code they keep on paper, but six months is longer than a convention year needs
and the holder can see thirty minors' names.

**Accepted — CORS is not a boundary.** The allow-list stops a *browser* on
another origin. It stops nothing that is not a browser. Every real control is
the scope check on the server; CORS is defence in depth and nothing more.

**Accepted — the audit log records who, not what was read.** Every *change* is
logged in the same transaction as the change itself. Reads are not logged, so a
sponsor who signs in and looks at their own roster leaves a sign-in record and
nothing more.

---

## 7. Would two-factor authentication help?

**Yes, and it addresses the actual threat.** Section 4 says almost every
realistic path is a code going astray. A second factor is precisely a defence
against a leaked credential, which is the thing most likely to happen here.

**Scoped to adults and the board — not delegates.** A delegate's code protects
their own event choices and nothing else, delegate email addresses are not
collected, and asking eleven-year-olds for a second factor at a convention with
patchy wifi would break the thing rather than protect it. The rule that matches
the risk: **anybody whose code reaches more than their own activity sheet.**
That is sponsors, chaperones, and every board member.

**On the two delivery options.** Apps Script on the Workspace account is the
better choice: 1,500 a day against 300, no DNS work, no third-party account, no
API key to leak, and the project already has an Apps Script deployment planned
for Drive exports. Brevo needs SPF and DKIM set up on `uhsjcl.org` before
anything sends reliably, and adds a vendor holding a log of who signed in when.

**What it costs, honestly.** A sponsor with no signal in a school car park
cannot get in. Build the recovery path — a chair can issue a one-time bypass —
before the convention rather than during it. Three days is a reasonable session
after a second factor.

**On IP addresses:** not worth building on. School networks NAT hundreds of
students behind one address, phones change address between cells, and the
hashes are one-way by design, so an IP rule would lock out real chapters while
barely inconveniencing anybody deliberate. Two-factor is the better spend.

**My recommendation:** build it for adults and the board, over Apps Script,
after the queued registration work and before codes are sent to chapters — the
codes go out once, and changing the sign-in flow afterwards means telling fifty
sponsors that it changed.
