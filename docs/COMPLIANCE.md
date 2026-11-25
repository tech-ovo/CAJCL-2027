# Regulatory Compliance & Data Governance Reference

**Platform:** 72nd Annual CAJCL State Convention Platform (`state.uhsjcl.org`)  
**Operator:** California Junior Classical League (CAJCL), 501(c)(3) Non-Profit  
**Architectural Model:** **Parental-Consent-Gated Single-System Architecture** — Per CAJCL leadership's decision (superseding earlier ID-only proposals), the CAJCL Waiver includes an explicit parental consent clause for online use of attendee data necessary to run convention. The platform stores minimum necessary attendee data (name, school, grade, Latin level, meal preference, event selections) in a single system, strictly gated behind parental consent on the physical waiver. Medical forms and signed waivers stay **strictly on paper** (mailed with the check; no Google Drive scanning).  
**Audience:** Internal CAJCL Adults (Board of Directors, Convention Presidents, Host School Sponsors, Technology Chairs, Registration & Activity Chairs, Chapter Sponsors)  
**Last Reviewed:** November 24, 2026  
**Source Specifications:** Aligned with the **2027 CAJCL Convention Book**, CAJCL leadership data guidelines, [`docs/PRIVACY_POLICY.md`](PRIVACY_POLICY.md), [`docs/TERMS_OF_SERVICE.md`](TERMS_OF_SERVICE.md), [`docs/PRIVACY.md`](PRIVACY.md), [`docs/SECURITY.md`](SECURITY.md), [`docs/RISKS.md`](RISKS.md), [`docs/REGISTRATION.md`](REGISTRATION.md), [`docs/RUNBOOK.md`](RUNBOOK.md), and [`docs/TODO.md`](TODO.md)

---

## 1. Executive Summary: Core Governance Principles

CAJCL leadership approved the digital registration platform subject to clear operational and privacy principles:
1. **Explicit Parental Consent Required for All Attendees:** The CAJCL Waiver includes a parental consent clause covering online use of student data necessary to run convention. Students without a signed waiver cannot attend and **must not** be given a chapter Join Code.
2. **Single-System Simplicity:** All registration data lives in one unified system rather than splitting IDs from names or maintaining opt-in/opt-out tracks.
3. **Strict Data Minimization & Paper-Only Health Forms:** Collect only the PII needed to run convention (name, school, grade, Latin level, meal preference, event selections). Never collect student emails, student phones, DOBs, home addresses, or payment cards. Medical forms and signed waivers remain **exclusively on paper** (mailed with the chapter check; no scanning or uploading to Google Drive).
4. **Tight Access Control & Private Code:** Convention hosts see everything; sponsors see only their own chapter (authenticated with Login Token + one-time code on every sign-in); logged-in students see only themselves; the public sees only schedule/map/aggregate counts (zero student names, no public awards lists, and public links not shared widely on social media). All website code — especially backend server code — must remain **private**.
5. **Vetted Vendors, Reliable Backup & Mandatory Purge:** All tools touching student PII must not sell data or advertise to students (Modal and Turso are approved; any other tool requires adult review before use). Critical registration data and the schedule must be backed up/synced to a reliable secondary store (e.g., restricted Google Sheet). All PII is permanently deleted on **April 12, 2027** (30 days post-convention).

---

## 2. Regulatory Compliance Narrative

### COPPA *(15 U.S.C. §§ 6501–6506 and 16 C.F.R. Part 312 — Children's Online Privacy Protection Act)*
Although 501(c)(3) non-profit organizations are generally exempt from COPPA under Section 5 of the FTC Act, we voluntarily adhere to COPPA's safeguards because middle school delegates include students aged 11–12.
- **Verifiable Parental Consent Before Collection (§ 312.5):** Sponsors distribute and collect signed physical **CAJCL Waivers** (which include the parental consent clause for online data use) and **Medical Forms** *before* distributing the chapter Join Code. No student may register online without prior parental consent.
- **Privacy Notice (§ 312.4):** CAJCL State Co-Chair Fred Muth is authoring the official CAJCL Privacy Policy to link in all registration materials, mirrored by the platform's `#/privacy` notice.
- **Data Minimization (§ 312.7) & Photo Contest Safeguards:** Zero student emails, phone numbers, home addresses, or birth dates are collected. For the optional at-convention Photo Contest, the browser (`photos.js`) re-encodes uploads onto an HTML5 canvas (removing GPS/camera/timestamp metadata) and the server (`backend/lib/photos.py`) strips JPEG `APP1`/`APP13`/`COM` and PNG `eXIf`/`tEXt`/`iTXt`/`zTXt`/`tIME` metadata.
- **Parental Review, Deletion (§ 312.6) & Retention (§ 312.10):** Parents can review, correct, or delete their child's record at any time through their Chapter Sponsor or Host School Sponsor (`roster.redact`). All operational PII and uploaded files are permanently deleted on **April 12, 2027** (rolling backups expire in 10 days).

### SOPIPA *(Cal. Bus. & Prof. Code § 22584 — Student Online Personal Information Protection Act)*
SOPIPA applies mandatorily to online platforms designed and used primarily for K–12 school purposes, with no exemption for 501(c)(3) non-profits.
- **No Selling, Ads, or Profiling (§ 22584(b)):** The platform carries zero advertisements, zero tracking pixels, zero commercial analytics, and self-hosts all fonts and scripts. All vendors with access to student PII must not sell data or advertise to students (Modal and Turso reviewed and approved; any other tool requires adult sign-off before use).
- **Security & Deletion (§ 22584(d)):** Reasonable security procedures (TLS 1.3, AES-256 at rest, HMAC-hashed credentials, sponsor 2FA, private codebase, immutable audit logging) and guaranteed deletion on **April 12, 2027** (or earlier upon sponsor/parent request).

### FERPA *(20 U.S.C. § 1232g and 34 C.F.R. Part 99)* & *Cal. Educ. Code § 49073*
FERPA and California Education Code § 49073 govern disclosure of student education records held by schools.
- **Written Parental Consent:** Under 34 C.F.R. § 99.30, disclosure of student information for an extracurricular interscholastic convention is authorized via written parental consent executed on the physical **2027 CAJCL Student Waiver and Permission Form**.
- **Tenancy Isolation:** Every API endpoint enforces role-based access control (`test_endpoints.py`), strictly isolating each chapter's records to its own `school_id` so sponsors can view only their own students.

### AB 1584 *(Cal. Educ. Code § 49073.1 — Local Educational Agency Digital Contracts)*
AB 1584 governs contracts between California public school districts (LEAs) and third-party digital operators managing pupil records. We include the full statutory School District Addendum in [`docs/PRIVACY_POLICY.md`](PRIVACY_POLICY.md) §10 affirming LEA ownership, purpose limitation, parent/student review and correction rights, security and confidentiality controls, breach notification, prohibition on targeted advertising, and post-convention deletion certification (**April 12, 2027**).

### California Reasonable Security Law *(Cal. Civ. Code § 1798.81.5)*
Cal. Civ. Code § 1798.81.5 requires reasonable security procedures and practices for California residents' personal information. We protect student and adult records through:
- Private source code repository (especially backend server code);
- Mandatory TLS 1.3 in transit and AES-256 volume encryption at rest on Turso;
- Zero cleartext credentials (`HMAC-SHA256` with isolated `CODE_PEPPER` for login tokens and client IP addresses; `SHA-256` for 256-bit session tokens);
- Sponsor email one-time code (2FA) on every sign-in;
- Strict brute-force rate limiting (5/code/hr, 10/IP/15 min, 30 join codes/IP/15 min);
- 100% parameterized SQL queries (`backend/queries/*.sql`), safe DOM text-node rendering (`document.createTextNode`), HTML allowlist sanitization (`backend/lib/htmlclean.py`), strict HTTP security headers (`CSP`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`);
- Mandatory database-level `audit_log` checks on every mutation; and
- Written Information Security Program (WISP) overseen by the Host School Sponsors.

### California Data Breach Notification Law *(Cal. Civ. Code § 1798.82)*
Because student and adult names are stored in the operational database during the convention cycle, a confirmed unauthorized acquisition of unencrypted database records or restricted backup Sheets would trigger breach notification obligations. We maintain a four-phase incident response plan (`docs/PRIVACY.md` §8 and `docs/RUNBOOK.md` §11):
1. Containment and secret rotation within 1 hour;
2. `audit_log` forensic assessment within 24 hours;
3. Vulnerability remediation; and
4. Written notice to affected individuals, sponsors, and school districts within 30 days — plus electronic submission of a sample notice (excluding PII) to the **California Attorney General** under **Cal. Civ. Code § 1798.82(f)** if more than 500 California residents are affected.

### CalOPPA *(Cal. Bus. & Prof. Code §§ 22575–22579)* & CCPA/CPRA *(Cal. Civ. Code § 1798.100 et seq.)*
- **CalOPPA:** Our plain-language privacy notice (`#/privacy`) is linked in the global footer of every page and on `#/join`, disclosing data categories, sub-processors, effective date, contact information, and our zero-tracking DNT posture.
- **CCPA / CPRA:** CAJCL is exempt as a 501(c)(3) non-profit organization (Cal. Civ. Code § 1798.140(d)), while still voluntarily providing full inspection, correction, and deletion rights and never selling data.

### California Right of Publicity & Minor Likeness Rules *(Cal. Civ. Code § 3344 & COPPA)*
CAJCL is a non-profit educational organization running an internal convention photo contest and non-commercial convention events (exempt under § 3344(d)). Every student's physical *CAJCL Student Waiver and Permission Form* includes a media/photography release; uploaded Photo Contest images have all EXIF/GPS metadata stripped in both browser and server; access inside the portal is limited to the Activities Chair and Convention Presidents; photos can be withdrawn or taken down at any time; and all uploaded photos in Google Drive are permanently deleted on **April 12, 2027**.

### Non-Profit Financial Recordkeeping *(IRC § 501(c)(3) & Cal. Corp. Code § 6320)*
Our append-only financial ledger (`payments` and `schools` tables) records only chapter-level institutional check numbers, payment amounts, discounts, and aggregate headcounts — zero student PII — allowing retention for the full seven-year tax audit window without impacting student privacy.
