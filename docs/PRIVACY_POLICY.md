# Privacy Policy — 72nd Annual CAJCL State Convention Platform

> **Note:** Per CAJCL leadership guidelines, CAJCL State Co-Chair Fred Muth is drafting the official CAJCL Privacy Policy to link in registration materials. This document is the platform-specific draft aligned with the 2027 CAJCL Convention Book and CAJCL leadership's data guidelines, and should be reconciled with Mr. Muth's official policy before launch.

**Effective Date:** December 1, 2026  
**Last Updated:** November 24, 2026  
**Platform:** `https://state.uhsjcl.org`  
**Operator:** California Junior Classical League ("CAJCL"), a California 501(c)(3) Non-Profit Public Benefit Corporation  
**Host Institutions:** University High School & Woodbridge High School (Irvine Unified School District), Irvine, California  

---

## 1. Purpose, Scope, and Statutory Alignment

This Privacy Policy ("**Policy**") governs the collection, processing, storage, security, and mandatory post-convention deletion of information across the digital registration, scheduling, and competition platform at `https://state.uhsjcl.org` (the "**Platform**") operated by the California Junior Classical League ("**CAJCL**," "**we**," "**us**," or "**our**") in connection with the 72nd Annual CAJCL State Convention held on March 12–13, 2027, at University High School in Irvine, California (co-hosted by University High School and Woodbridge High School) (the "**Convention**").

Because the Platform serves middle school and high school chapters (Grades 6–12), faculty sponsors, adult chaperones, and student delegates across California, we collect only the minimum attendee information needed to run the Convention — **strictly after verifiable parental consent** on the physical **CAJCL Student Waiver and Permission Form** — and align our data governance practices with:

1. **California Student Online Personal Information Protection Act ("SOPIPA")** — Cal. Bus. & Prof. Code § 22584;
2. **California Pupil Records Privacy Statute ("AB 1584")** — Cal. Educ. Code § 49073.1;
3. **Family Educational Rights and Privacy Act ("FERPA")** — 20 U.S.C. § 1232g and 34 C.F.R. Part 99;
4. **Children's Online Privacy Protection Act ("COPPA")** — 15 U.S.C. §§ 6501–6506 and 16 C.F.R. Part 312 (adhered to voluntarily as a strict baseline standard alongside our 501(c)(3) non-profit status);
5. **California Online Privacy Protection Act ("CalOPPA")** — Cal. Bus. & Prof. Code §§ 22575–22579; and
6. **California Information Security & Breach Notification Statutes** — Cal. Civ. Code §§ 1798.81.5 and 1798.82.

---

## 2. Parental Consent & Data Minimization

### 2.1 Mandatory Parental Consent Before Online Registration
All student delegates attending the Convention must have a parent or legal guardian sign the physical **2027 CAJCL Student Waiver and Permission Form**, which includes explicit parental consent for the online use of attendee data necessary to run the Convention.
- **No Consent, No Attendance:** Students without a parent-signed CAJCL Waiver cannot attend the Convention and must not be given a chapter Join Code.
- **Single-System Consistency:** To operate the Convention reliably and safely, all registered attendees are housed in a single system under the same parental consent standard.

### 2.2 Minimum Necessary Data
We collect only the Personally Identifiable Information ("**PII**") strictly required to administer registration, meals, academic exams, contests, and event logistics (such as attendee name, school/chapter, grade, Latin level, meal preference, and event selections). We never collect student email addresses, student phone numbers, home addresses, dates of birth, Social Security numbers, payment cards, or digital medical records.

---

## 3. Categories of Information We Collect and Process

| Category | Specific Data Elements Collected | Data Subjects | Collection Method | Retention & Purge Schedule |
| :--- | :--- | :--- | :--- | :--- |
| **Student Delegate Records** | Legal Name, Chapter & Division (MS/HS), Academic Grade (6–12), Latin Level (`MS-1` through `HS-Adv`), Meal Preference, Attendance Status (`active`, `cancelled`, `cancelled_paid`) | Student Delegates (Grades 6–12) | Chapter Join Code (`#/join`) distributed **only after** signed paper waiver & medical form are submitted, or Chapter Sponsor Roster Import (`#/roster`) | Operational PII purged **April 12, 2027** (rolling backups deleted after 10 days) |
| **Student Activity, Testing & Event Selections** | Academic exam selections (1–3 tests), Creative/Graphic Arts, Olympika athletic event sign-ups, Ludi sign-ups (Open Certamen, Pandora's Breakout Box, That's Entertainment Auditions, etc.), Activities Potluck helper picks | Student Delegates | Delegate or Chapter Sponsor (`#/activity-sheet`, `#/olympika`) | Operational selections purged **April 12, 2027**; only de-identified aggregate counts and placements retained |
| **Pre-Convention Creative Contest Submissions** | Uploaded digital contest files (Digital Art/Poster, Latin Slogan, English Slogan, Modern Myth, Original Poetry, Scrapbook Pictures, Digital Scrapbook, Publicity Portfolio; max 20 MB), division, word count, and double-blind judging ballots | Student Delegates & Chapters | Digital Contest Upload (`#/contests`) transmitted via signed webhook to restricted Google Drive | Permanently deleted from Google Drive on **April 12, 2027** (or immediately upon withdrawal or redaction) |
| **At-Convention Photo Contest Entries** | Uploaded convention photograph (JPEG/PNG; re-encoded to ≤2400 px + 480 px thumbnail with all EXIF/GPS metadata stripped), optional caption, category | Student Delegates | Student upload (`#/photos`) during Convention while category is open | Permanently deleted from Google Drive on **April 12, 2027** (or immediately upon student withdrawal, chair takedown, or redaction) |
| **Adult Registrant & Officer Profiles** | Full legal name, adult role (`SPO` Sponsor, `VOL` Chaperone/Volunteer, SCL, or Board role), email address (for Sponsor 2FA & check arrival notifications), mobile phone number, Latin competency tier, meal preference, and volunteer availability notes | Chapter Sponsors, Adult Chaperones, Volunteers, SCL, Convention Officers & Judges | Sponsor provisioning / Join Code / Digital Adult Activity Sheet (`#/adult-sheet`) | All adult names, emails, phones, and notes permanently purged **April 12, 2027** |
| **Authentication & Security Telemetry** | Keyed `HMAC-SHA256` digest of Login Token (`PPP-XXXXX-XXXXX`), sponsor email one-time code (2FA) verification, `SHA-256` hash of 256-bit session bearer token, keyed `HMAC-SHA256` digest of client IP address, user-agent string, and transactional `audit_log` entries | All Authenticated Users & Sign-In Attempts | Automated cryptographic generation upon sign-in, 2FA verification, or database mutation | Session tokens and telemetry permanently purged **April 12, 2027** |
| **Institutional Financial Ledger Records** | Chapter name, institutional check number, payment amount (in cents), discount amount and justification (including 75% New School discount), billing exemption status, and remittance notes | Participating School Chapters | Administrative entry by Registration Chairs (`#/chapters`) | Retained for **seven (7) years** pursuant to IRS 501(c)(3) and Cal. Corp. Code § 6320 tax audit mandates (contains zero student PII) |
| **Physical Waiver & Medical Forms (Paper Only — Off-Database)** | Physical ink-signed *2027 CAJCL Student Waiver and Permission Form* (students) and *2027 Medical Form* (students, sponsors, and chaperones) | Student Delegates & Attending Adults | Collected on paper by Chapter Sponsors and mailed with the chapter's check to University High School c/o Mark Michalak (or brought at check-in for substitutions). **Not scanned or uploaded to Google Drive.** | **Zero ingestion into the Platform database or Google Drive.** Physical paper copies destroyed or returned post-Convention |

---

## 4. Information We Explicitly Never Collect Online

The Platform is architected to reject and never request the following data elements:
1. **Student Contact Details:** We never collect student email addresses, student mobile phone numbers, or social media handles. All communications regarding students route exclusively through adult Chapter Sponsors.
2. **Residential Addresses, Birth Dates, or Government Identifiers:** We never collect home street addresses, exact dates of birth (eligibility is determined strictly by academic grade 6–12), Social Security numbers, driver's license numbers, or state/district student ID numbers.
3. **Electronic Payment Card or Banking Credentials:** We do not accept credit cards, debit cards, ACH transfers, or online payments. All registration fees are remitted via a single physical institutional or chapter check.
4. **Digital Health or Medical Database Records:** No medical conditions, prescriptions, insurance numbers, or doctor contact details are ever entered into the Platform's database or uploaded to Google Drive.
5. **Behavioral Tracking or Biometric Data:** We use zero advertising pixels, zero third-party analytics scripts, zero cross-site cookies, and zero facial-recognition or biometric tools.

---

## 5. Specific Platform Workflows and Privacy Guardrails

### 5.1 Consent-Gated Join Code Registration (`#/join`)
1. The **Chapter Sponsor** logs into the Platform using their `SPO-` Login Token and a **one-time verification code** sent on every sign-in.
2. Separate from the Platform, the Chapter Sponsor distributes physical copies of the **2027 Medical Form** (all attendees) and **2027 CAJCL Student Waiver and Permission Form** (students only).
3. **Only after a student's signed waiver and medical form are turned in**, the Chapter Sponsor distributes the chapter's **Join Code sheet** so the attendee can join on the Platform and complete their Activity Sheet.
4. Once a student enters their **name, grade, and Latin level**, **only the Chapter Sponsor can change those details**. Sponsors can observe and edit all data students enter, approve or remove students, reset the chapter join code, and enable or disable joining at any time.
5. If a Chapter Sponsor denies or redacts a delegate (`roster.redact`), the Platform immediately and permanently erases all personal fields, form selections, contest entries, photo uploads, and active sessions associated with that record in a single atomic database transaction.

### 5.2 Double-Blind Pre-Convention Contests (`#/contests`)
Students uploading pre-convention creative entries (due **March 6, 2027**; Digital Scrapbook due **March 13, 2027 at 10:00 AM**) transmit files through an authenticated serverless pipeline to a restricted Google Drive folder. Evaluators holding the `judge` role view submissions strictly as anonymized **`Entry N`** files with all student names, chapter affiliations, and original filenames programmatically stripped.

### 5.3 At-Convention Photo Contest and Convention Photography (`#/photos`)
1. **Metadata Stripping:** When a delegate uploads a photograph to the optional At-Convention Photo Contest, the client browser (`frontend/public/js/pages/photos.js`) re-encodes the image onto an HTML5 canvas (producing a ≤2400 px JPEG and 480 px thumbnail, removing phone location, camera, and timestamp metadata) and the backend server (`backend/lib/photos.py`) verifies magic bytes and strips all JPEG `APP1` (EXIF/XMP), `APP13` (IPTC), and `COM` segments as well as PNG `eXIf`, `tEXt`, `iTXt`, `zTXt`, and `tIME` chunks prior to storage.
2. **Parental Authorization:** Participation in the Convention requires a parent or legal guardian to execute the physical **2027 CAJCL Student Waiver and Permission Form**, which includes a media and photography release covering convention photography and non-commercial CAJCL use.
3. **Restricted Access & Immediate Takedown:** Within the Platform, uploaded Photo Contest entries are visible only to the Activities Chair (scope `activities`) and Convention Presidents. A submitting delegate may withdraw their photo at any time, the Activities Chair or Convention Presidents may remove any photo immediately, and the entire `Photo Contest` storage directory is permanently deleted on **April 12, 2027**.

### 5.4 Local Browser Storage and "Do Not Track" (CalOPPA Disclosure)
- **First-Party `localStorage` Only:** The Platform uses browser `localStorage` strictly for two essential technical functions: (a) storing your opaque session bearer token after you sign in, and (b) remembering your visual display preference (`light` or `dark` theme).
- **Self-Hosted Assets:** All fonts (`.woff2` subsets), stylesheets (`tokens.css`, `app.css`), and scripts are self-hosted on our origin domain. Visiting the Platform triggers zero requests to Google Fonts or third-party ad networks.
- **Do Not Track ("DNT") Signals:** Because the Platform never tracks users across third-party websites or over time for commercial or profiling purposes, we treat all visitors under a strict zero-tracking standard regardless of DNT settings.

---

## 6. How We Use Information & Categorical Prohibitions (SOPIPA Compliance)

Pursuant to Cal. Bus. & Prof. Code § 22584(b) (SOPIPA) and Cal. Educ. Code § 49073.1 (AB 1584), CAJCL uses information collected through the Platform **solely for K–12 school and interscholastic academic convention purposes**, specifically to:
1. Authenticate registrants and enforce chapter-level and role-based access boundaries;
2. Schedule and administer academic exams, pre-convention contests, Olympika athletic heats/brackets, Ludi events, and adult volunteer shifts;
3. Tabulate individual and chapter sweepstakes awards and distribute results privately to Chapter Sponsors (never as public awards lists with student names);
4. Calculate chapter registration invoices, complimentary adult ratios, New School discounts, and aggregate meal counts;
5. Verify completion of mandatory physical permission, waiver, and medical documentation; and
6. Maintain system security, rate-limit brute-force attacks, maintain reliable operational backups, and audit database modifications.

**We Never Sell, Rent, or Monetize Data:**
- We **never** sell, rent, lease, or trade student or adult information to any third party.
- We **never** use or disclose information collected on the Platform for targeted advertising, behavioral advertising, or commercial marketing.
- We **never** amass a commercial profile about any K–12 student except in direct furtherance of administering the Convention.

---

## 7. Access Controls, Role Isolation, and Sub-Processors

### 7.1 Strict Role-Based Access Control (RBAC)
Access to data within the Platform and any backup Google Sheets is strictly controlled:
- **Public Visitors:** View only the Convention schedule (`#/schedule`), campus map, published informational pages, and pre-aggregated headcounts (`/public/stats`). **No student names, individual records, or public awards lists are ever publicly visible.** Public links are shared only via physical QR codes or emails to registered attendees, not widely on social media.
- **Student Delegates (`delegate`):** View and edit only their own activity sheet, contest uploads, and event sign-ups/schedules.
- **Chapter Sponsors (`sponsor`):** View and manage only the students, adult registrants, test scores, and invoices belonging to their own `school_id`. Cross-chapter access is blocked (`HTTP 403 Forbidden`).
- **Contest Judges (`judge`):** View only anonymized pre-convention contest submissions (`Entry N`) within their assigned division.
- **Athletics Director (`athletics`), Activities Chair (`activities`), Logistics Chair (`logistics`):** Narrow operational scopes limited to their assigned functions (no access to full chapter rosters or billing).
- **Convention Hosts & Board (`*`, `registration`, `academics`, `awards`):** Authorized board officers and host school advisors access state-wide operational rosters, invoicing ledgers, and tabulation views strictly to run the Convention.

### 7.2 Authorized Infrastructure Sub-Processors
All websites and services with access to student PII must not sell student data or advertise to students, and must be vetted by an adult CAJCL leader before use.

| Sub-Processor | Operational Function | Security Standards & Safeguards | Data Processed |
| :--- | :--- | :--- | :--- |
| **Modal Labs, Inc.** | Serverless API Compute Tier & Background Workers *(Approved by CAJCL leadership)* | SOC 2 Type II, TLS 1.3, isolated container secrets | Ephemeral API requests, authentication verification, PDF generation |
| **Turso (ChiselStrike, Inc.)** | Distributed Relational Database Engine (libSQL / SQLite) *(Approved by CAJCL leadership)* | SOC 2 Type II, AES-256 volume encryption at rest, TLS 1.3 in transit | Attendee operational records, chapter invoices, hashed credentials, and `audit_log` |
| **GitHub, Inc.** | Private Source Repository, Static Frontend Hosting (Pages) & CI/CD | SOC 2 Type II, ISO/IEC 27001, TLS 1.3 | Static HTML/CSS/JS assets, public informational pages (zero attendee PII) |
| **Google LLC** | Google Workspace / Drive, Sheets & Apps Script | SOC 2/3, ISO/IEC 27001/27018, AES-256 encryption | Uploaded contest entries, Photo Contest images/thumbnails, sponsor 2FA emails, restricted operational backup Sheets (NO medical or waiver scans) |

### 7.3 Legal and Safety Disclosures
We may disclose information outside the ordinary course of Convention administration only if required to do so by a valid subpoena, court order, or other compulsory legal process, or when we believe in good faith that disclosure to school officials, emergency medical personnel, or law enforcement is immediately necessary to protect the physical health or safety of a student or attendee.

---

## 8. Technical and Organizational Security Program (Cal. Civ. Code § 1798.81.5)

CAJCL maintains a Written Information Security Program ("**WISP**") overseen by the Host School Sponsors and featuring technical and organizational controls appropriate to K–12 educational operations:
1. **Private Codebase:** All website source code — especially back-end server code — is maintained in a private repository, never open to the public.
2. **Encryption in Transit and at Rest:** All network traffic is encrypted via TLS 1.3. Database storage volumes and Google Drive repositories are encrypted at rest using AES-256.
3. **Zero Cleartext Credentials or IPs:** Login tokens (`PPP-XXXXX-XXXXX`) and logged client IP addresses are salted and hashed using `HMAC-SHA256` with a high-entropy secret pepper stored exclusively in isolated serverless secrets. Session bearer tokens contain 256 bits of cryptographic entropy and are stored solely as `SHA-256` digests.
4. **Sponsor One-Time Codes (2FA):** Chapter sponsors receive a one-time verification code each time they sign in alongside their Login Token.
5. **Brute-Force Rate Limiting:** Authentication endpoints enforce automatic lockouts after 5 failed attempts per login token per hour, 10 failed sign-in attempts per IP per 15 minutes, and 30 failed join-code attempts per IP per 15 minutes.
6. **Injection & XSS Hardening:** 100% of database queries execute via pre-compiled, parameterized SQL statements (`backend/queries/*.sql`). The frontend renders dynamic content via safe DOM text nodes (`document.createTextNode`) and enforces a strict Content Security Policy (`CSP`), `X-Frame-Options: DENY`, and `X-Content-Type-Options: nosniff`.
7. **Mandatory Transactional Audit Logging:** Database triggers reject any data mutation that does not simultaneously write an immutable attribution record to `audit_log`.

---

## 9. Data Retention, Reliable Backups, and Mandatory Post-Convention Purge (April 12, 2027)

Pursuant to COPPA (16 C.F.R. § 312.10) and SOPIPA (Cal. Bus. & Prof. Code § 22584(d)(2)), CAJCL retains operational data only for the duration of the 2027 Convention cycle:

1. **Reliable Secondary Backups (10-Day Rolling Deletion):** Critical registration data and the convention schedule are backed up/synced to a restricted Google Sheet / Drive backup in case of an outage. Rolling backups are automatically and permanently deleted after **ten (10) days**, ensuring redacted or deleted records disappear from backups within 10 days.
2. **Active Convention & Tabulation Window (Through April 11, 2027):** Operational records remain active through the Convention (March 12–13, 2027) and a 30-day post-convention verification window so Chapter Sponsors can review student test scores and placement reports.
3. **Mandatory Complete Purge Date (April 12, 2027):** Exactly thirty (30) calendar days after the close of the Convention, CAJCL executes a comprehensive data purge (`scripts/purge_convention_data.py` and Drive cleanup) that permanently expunges:
   - All student and adult legal names, adult email addresses, mobile phone numbers, and volunteer notes;
   - All authentication credentials, session token hashes, rate-limit logs, and operational audit trail PII references;
   - All pre-convention creative contest files and At-Convention Photo Contest images and thumbnails stored in Google Drive; and
   - All restricted Google Sheet / Drive operational backups containing attendee PII.
4. **Permanent De-Identified Historical Archive:** Following the April 12, 2027 purge, CAJCL retains only a strictly de-identified statistical archive recording the convention year (`2027`), person/badge number, chapter name, academic grade (6–12), Latin level, and competition placements, with zero personal names or contact details.
5. **Non-Profit Financial Accounting Retention:** Chapter-level institutional accounting records (`schools` and `payments` tables recording institutional check numbers and chapter balances, containing zero student PII) are retained for seven (7) years to comply with Internal Revenue Code § 501(c)(3) and California Corporations Code § 6320 recordkeeping mandates.

---

## 10. California Education Code § 49073.1 (AB 1584) School District Addendum

For participating California public school districts, county offices of education, and charter schools ("**Local Educational Agencies**" or "**LEAs**"), CAJCL incorporates the following statutory terms into its relationship with each participating LEA pursuant to Cal. Educ. Code § 49073.1:

1. **LEA Ownership and Control:** Any pupil records (as defined in Cal. Educ. Code § 49073.1(d)(2)) provided by or on behalf of an LEA or its employees (Chapter Sponsors) continue to be the property of and under the legal control of the participating LEA.
2. **Student-Generated Content:** Student competition entries created or uploaded by a pupil may be managed and withdrawn by the pupil at any time prior to the April 12, 2027 purge.
3. **Strict Purpose Limitation:** CAJCL shall not use any information in a pupil record for any purpose other than those expressly required or permitted by this Policy and the Terms of Service to administer the 72nd Annual CAJCL State Convention.
4. **Parent, Legal Guardian, and Eligible Pupil Review & Correction:** A parent, legal guardian, or eligible pupil (aged 18 or older) may review personal information in the pupil's records and correct erroneous information by contacting their school's Chapter Sponsor (who has direct portal editing controls) or by submitting a written request to the Host School Sponsor at the address in Section 14.
5. **Security and Training:** CAJCL implements the encryption, access-control, and audit safeguards detailed in Section 8 and restricts operational scopes to designated Convention Officers and Chapter Sponsors who are instructed on strict confidentiality obligations.
6. **Breach Notification Compliance:** In the event of an unauthorized disclosure of pupil records, CAJCL will follow the statutory notification procedures set forth in Section 12.
7. **Post-Term Non-Retention Certification:** CAJCL certifies that pupil records shall not be retained or available to CAJCL beyond the mandatory **April 12, 2027** purge date (or immediately upon an LEA's or Chapter Sponsor's earlier invocation of redaction), except for de-identified historical placement statistics exempt under Cal. Educ. Code § 49073.1(d)(2) and Cal. Bus. & Prof. Code § 22584(g).
8. **FERPA Compliance Cooperation:** CAJCL and the participating LEA shall work cooperatively to ensure continuous compliance with FERPA (20 U.S.C. § 1232g), supported by explicit parental consent on the physical CAJCL Waiver.
9. **Prohibition on Targeted Advertising:** CAJCL is strictly prohibited from using any information in a pupil record to engage in targeted advertising.

---

## 11. Parental, Student, and Adult Privacy Rights

Regardless of age or chapter affiliation, parents, legal guardians, student delegates, and adult registrants have the following rights:
1. **Right to Inspect and Review:** You may request confirmation of all data fields, event selections, or uploaded files associated with your child's or your own registration record.
2. **Right to Correct:** Once a student sets their name, grade, and Latin level, only their Chapter Sponsor can modify those fields. Activity sheets lock after **February 13, 2027**; substitutions may be made through **February 26, 2027**. Parents or sponsors may request administrative corrections through the Host School Sponsor or Registration Chairs at any time.
3. **Right to Immediate Deletion / Redaction:** You may request that a student's or adult's record, uploaded contest files, or Photo Contest submissions be permanently deleted prior to the April 12, 2027 purge. A Chapter Sponsor can remove/redact a student directly from the chapter roster (`#/roster`), or you may write to the Host School Sponsor, who will process verified deletion requests within ten (10) business days.
4. **Right to Revoke Consent and Scope of Erasure:** A parent or legal guardian may revoke consent for a student's participation at any time by notifying the student's Chapter Sponsor or the Host School Sponsor in writing, whereupon the student's digital record and any uploaded media on the Platform will be immediately redacted (and removed from rolling backups within 10 days). Note that a student without active parental consent cannot attend the Convention.

---

## 12. Incident Response and Data Breach Notification Protocol (Cal. Civ. Code § 1798.82)

CAJCL maintains a formal four-phase incident response plan:
1. **Phase 1 — Containment (Within 1 Hour of Discovery):** Revoke compromised sessions or login tokens and rotate serverless cryptographic secrets (`CODE_PEPPER`, database tokens, or webhook keys).
2. **Phase 2 — Forensic Assessment (Within 24 Hours):** Audit the immutable `audit_log` and access logs to determine the exact scope of affected records.
3. **Phase 3 — Remediation:** Patch any underlying vulnerability and verify integrity across all automated security tests.
4. **Phase 4 — Written Notification (Within 30 Days) & California Attorney General Filing:** If unencrypted personal information is confirmed to have been acquired by an unauthorized person, CAJCL will notify affected Chapter Sponsors, participating school districts, and affected individuals/families in writing without unreasonable delay—and in no event later than thirty (30) calendar days following discovery—in full compliance with Cal. Civ. Code § 1798.82 and Cal. Educ. Code § 49073.1(b)(6). Pursuant to **Cal. Civ. Code § 1798.82(f)**, if a single breach requires notification to **more than 500 California residents**, CAJCL will electronically submit a single sample copy of the security breach notification (excluding any PII) to the **California Attorney General**.

---

## 13. Changes to This Privacy Policy

We may update this Privacy Policy to reflect operational refinements or regulatory guidance. The "Last Updated" date at the top of this page indicates when revisions took effect. Material changes that expand the categories of information collected or alter how information is shared will be communicated directly to registered Chapter Sponsors via email prior to taking effect.

---

## 14. Designated Host School Sponsors and Contact Information

All questions, parental review or deletion requests, school district compliance inquiries, and formal legal notices regarding this Privacy Policy should be directed to:

**Mark Michalak, Host School Sponsor & Convention Advisor**  
California Junior Classical League (CAJCL) / University High School JCL  
University High School  
4771 Campus Drive, Irvine, CA 92612  
**Email:** [MarkMichalak@iusd.org](mailto:MarkMichalak@iusd.org) / [state@uhsjcl.org](mailto:state@uhsjcl.org)  
**Phone:** (714) 514-8815

**Co-Host School Sponsor:** John Conant ([JohnConant@iusd.org](mailto:JohnConant@iusd.org), (714) 360-8923)  
**Convention Presidents:** Chenyue Zhou & Sriya Kushwaha ([conventionpresident@cajcl.org](mailto:conventionpresident@cajcl.org))
