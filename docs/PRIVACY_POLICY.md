# Privacy Policy — 72nd Annual CAJCL State Convention Platform

**Effective Date:** October 1, 2026  
**Last Updated:** October 18, 2026  
**Platform:** `https://state.uhsjcl.org`  
**Operator:** California Junior Classical League ("CAJCL"), a California 501(c)(3) Non-Profit Public Benefit Corporation  
**Host Institutions:** University High School & Woodbridge High School (Irvine Unified School District), Irvine, California  

---

## 1. Purpose, Scope, and Statutory Alignment

This Privacy Policy ("**Policy**") governs the collection, processing, storage, security, and mandatory post-convention deletion of information across the digital registration, scheduling, and competition platform at `https://state.uhsjcl.org` (the "**Platform**") operated by the California Junior Classical League ("**CAJCL**," "**we**," "**us**," or "**our**") in connection with the 72nd Annual CAJCL State Convention held on March 12–13, 2027, at University High School and Woodbridge High School in Irvine, California (the "**Convention**").

Because the Platform serves middle school and high school chapters (Grades 6–12), faculty sponsors, adult chaperones, and student delegates across California, we have engineered the Platform around an **ID-Only Student Architecture** and aligned our data governance practices with:

1. **California Student Online Personal Information Protection Act ("SOPIPA")** — Cal. Bus. & Prof. Code § 22584;
2. **California Pupil Records Privacy Statute ("AB 1584")** — Cal. Educ. Code § 49073.1;
3. **Family Educational Rights and Privacy Act ("FERPA")** — 20 U.S.C. § 1232g and 34 C.F.R. Part 99;
4. **Children's Online Privacy Protection Act ("COPPA")** — 15 U.S.C. §§ 6501–6506 and 16 C.F.R. Part 312 (adhered to voluntarily as a strict baseline standard alongside our 501(c)(3) non-profit status);
5. **California Online Privacy Protection Act ("CalOPPA")** — Cal. Bus. & Prof. Code §§ 22575–22579; and
6. **California Information Security & Breach Notification Statutes** — Cal. Civ. Code §§ 1798.81.5 and 1798.82.

---

## 2. Privacy by Design: The ID-Only Student Model

### 2.1 Zero Student Names or Contact Details in the Application Database
To protect student privacy and eliminate unnecessary collection of minor Personally Identifiable Information ("**PII**"), the Platform's application database collects and stores **zero student first or last names, zero student email addresses, zero student telephone numbers, zero home street addresses, zero dates of birth, and zero Social Security numbers**.

Every student delegate on the Platform is identified exclusively by:
- A system-generated, pseudonymous **Assigned Delegate ID / Badge Number** (e.g., `Delegate #1042`);
- Their participating school **Chapter** and division (Middle School or High School);
- Their **Academic Grade** (6–12); and
- Their **Latin Course Level** (`MS-1`, `MS-2`, `MS-3`, `HS-1`, `HS-2`, `HS-3`, or `HS-Adv`).

### 2.2 School-Held Re-Identification Key (FERPA & SOPIPA De-Identification Safe Harbor)
In accordance with 34 C.F.R. § 99.31(b)(1) (FERPA) and Cal. Bus. & Prof. Code § 22584(g) (SOPIPA), the correlation key mapping a student's **Assigned Delegate ID** to the student's legal name is retained locally by the student's school Latin teacher / faculty advisor (the "**Chapter Sponsor**") and on physical, ink-signed parent permission and medical forms. Assigned Delegate IDs and login tokens are generated sequentially or via cryptographically secure random number generation and are never derived from a student's name, initials, Social Security number, or school district student ID number.

---

## 3. Categories of Information We Collect and Process

| Category | Specific Data Elements Collected | Data Subjects | Collection Method | Retention & Purge Schedule |
| :--- | :--- | :--- | :--- | :--- |
| **De-Identified Student Delegate Records** | Assigned Delegate ID / Badge Number, Chapter, Division (MS/HS), Academic Grade (6–12), Latin Level, Approval Status (`pending`, `approved`, `denied`), Attendance Status (`active`, `cancelled`, `cancelled_paid`) | Student Delegates (Grades 6–12) | Chapter Join Code self-registration (`#/join`) or Chapter Sponsor roster slot provisioning (`#/roster`) | De-identified from inception; operational records purged **April 12, 2027** (denied joiners purged immediately) |
| **Student Activity, Testing & Event Selections** | Academic exam selections (1–3 tests), meal/dietary preference, Olympika individual event sign-ups (heats/lanes), Olympika team sign-ups (captain's Assigned Delegate ID and free-text team name), Activities Potluck helper picks | Student Delegates | Digital Student Activity Sheet (`#/activity-sheet`) and Olympika portal (`#/olympika`) | Operational selections purged **April 12, 2027**; only de-identified aggregate counts and placements retained |
| **Pre-Convention Creative Contest Submissions** | Uploaded digital contest files (essays, poetry, graphic/digital art; max 20 MB), division, word count, and double-blind judging ballots | Student Delegates | Digital Contest Upload (`#/contests`) transmitted via signed webhook to restricted Google Drive | Permanently deleted from Google Drive on **April 12, 2027** (or immediately upon withdrawal or redaction) |
| **At-Convention Photo Contest Entries** | Uploaded convention photograph (JPEG/PNG; re-encoded to ≤2400 px + 480 px thumbnail with all EXIF/GPS metadata stripped), optional caption, category, tagged only by Chapter + Assigned Delegate ID | Student Delegates | Student upload (`#/photos`) during Convention while category is open | Permanently deleted from Google Drive on **April 12, 2027** (or immediately upon student withdrawal, chair takedown, or redaction) |
| **Adult Registrant & Officer Profiles** | Full legal name, adult role (`SPO` Sponsor, `VOL` Chaperone/Volunteer, or Board role), email address, mobile phone number, Latin competency tier, meal preference, and volunteer/chaperone availability notes | Chapter Sponsors, Adult Chaperones, Volunteers, Convention Officers & Judges | Sponsor provisioning and Digital Adult Registration Sheet (`#/adult-sheet`) | All adult names, emails, phones, and notes permanently purged **April 12, 2027** |
| **Authentication & Security Telemetry** | Keyed `HMAC-SHA256` digest of Login Token (`PPP-XXXXX-XXXXX`), `SHA-256` hash of 256-bit session bearer token, keyed `HMAC-SHA256` digest of client IP address, user-agent string, and transactional `audit_log` entries | All Authenticated Users & Sign-In Attempts | Automated cryptographic generation upon sign-in, join-code use, or database mutation | Session tokens expire automatically (180 days standard; 72 hours admin) and are permanently purged **April 12, 2027** |
| **Institutional Financial Ledger Records** | Chapter name, institutional check number, payment amount (in cents), discount amount and justification, billing exemption status, and remittance notes | Participating School Chapters | Administrative entry by Registration Chairs (`#/chapters`) | Retained for **seven (7) years** pursuant to IRS 501(c)(3) and Cal. Corp. Code § 6320 tax audit mandates (contains zero student PII) |
| **Physical Waiver & Medical Forms (Off-Database)** | Physical ink-signed *2027 CAJCL Student Waiver and Permission Form*, *2027 Student Medical Form*, and *2027 Adult Medical Form* (containing legal names, parent/guardian emergency contacts, health/allergy disclosures, and media release signatures) | Student Delegates & Attending Adults | Collected on paper by Chapter Sponsors; PDF scans uploaded directly to a restricted Google Workspace Drive folder | **Zero ingestion into the Platform database.** Restricted Drive scans permanently deleted **April 12, 2027**; physical paper copies destroyed or returned post-Convention |

---

## 4. Information We Explicitly Never Collect Online

The Platform is architected to reject and never request the following data elements:
1. **Student Legal Names or Initials in the Database:** The database neither requests nor stores student names; delegates are tracked strictly by Assigned Delegate ID.
2. **Student Contact Details:** We never collect student email addresses, student mobile phone numbers, or social media handles. All communications regarding students route exclusively through adult Chapter Sponsors.
3. **Residential Addresses, Birth Dates, or Government Identifiers:** We never collect home street addresses, exact dates of birth (eligibility is determined strictly by academic grade 6–12), Social Security numbers, driver's license numbers, or state/district student ID numbers.
4. **Electronic Payment Card or Banking Credentials:** We do not accept credit cards, debit cards, ACH transfers, or online payments. All registration fees are remitted via physical institutional or chapter checks.
5. **Digital Health or Medical Database Records:** No medical conditions, prescriptions, insurance numbers, or doctor contact details are ever entered into or stored within the Platform's database.
6. **Behavioral Tracking or Biometric Data:** We use zero advertising pixels, zero third-party analytics scripts, zero cross-site cookies, and zero facial-recognition or biometric tools.

---

## 5. Specific Platform Workflows and Privacy Guardrails

### 5.1 Self-Registration via Chapter Join Code (`#/join`)
When a student uses their chapter's 8-character plaintext join code (`XXXX-XXXX`) from the Chapter Sponsor's printed handout:
1. The student selects only their **Academic Grade (6–12)** and **Latin Level** (no name, email, or phone number is requested).
2. The Platform provisions a preliminary (`pending`) record, assigns a unique **Assigned Delegate ID**, and displays a one-time **Login Token** (`DEL-XXXXX-XXXXX`).
3. The student writes their Assigned Delegate ID and Login Token on their physical waiver packet and submits the signed paperwork to their Chapter Sponsor.
4. Until the Chapter Sponsor approves the Assigned Delegate ID in the portal's *Waiting for approval* panel, the record remains marked **Preliminary** and is excluded from all invoices, public statistics, catering totals, and competition rosters.
5. If the Chapter Sponsor denies the pending entry (or redacts any delegate via `roster.redact`), the Platform immediately and permanently erases all form selections, contest entries, photo uploads, and active sessions associated with that ID in a single atomic database transaction.

### 5.2 Double-Blind Pre-Convention Contests (`#/contests`)
Students uploading pre-convention creative entries (such as essays, poetry, or digital art) transmit files through an authenticated serverless pipeline to a restricted Google Drive folder. Evaluators holding the `judge` role view submissions strictly as anonymized **`Entry N`** files with all chapter affiliations, Assigned Delegate IDs, and original filenames programmatically stripped.

### 5.3 At-Convention Photo Contest and Convention Photography (`#/photos`)
1. **Metadata Stripping & ID-Only Tagging:** When a delegate uploads a photograph to the optional At-Convention Photo Contest, the client browser re-encodes the image (to a ≤2400 px JPEG and 480 px thumbnail) and the backend server (`backend/lib/photos.py`) strips all EXIF, XMP, IPTC, GPS coordinates, camera serial numbers, and timestamp metadata prior to storage. Stored files are labeled strictly by **Chapter + Assigned Delegate ID**—never by a student's name.
2. **Parental Authorization for Convention Scene & Awards Assembly Photography:** In accordance with COPPA (16 C.F.R. § 312.5) and California Civil Code § 3344(d) (non-commercial educational and organizational proceedings), participation in the Convention requires a parent or legal guardian to execute the physical **2027 CAJCL Student Waiver and Permission Form**, which includes an express media and photography release authorizing convention scene photography and the projection or display of winning Photo Contest entries at the live Convention General Assembly / Awards Ceremony and in official non-commercial CAJCL publications.
3. **Restricted Access & Immediate Takedown:** Within the Platform, uploaded Photo Contest entries are visible only to the Activities Chair (scope `activities`) and Convention Presidents. A submitting delegate may withdraw their photo at any time, the Activities Chair or Convention Presidents may remove any photo immediately, and the entire `Photo Contest` storage directory is permanently deleted on **April 12, 2027**.

### 5.4 Local Browser Storage and "Do Not Track" (CalOPPA Disclosure)
- **First-Party `localStorage` Only:** The Platform uses browser `localStorage` strictly for two essential technical functions: (a) storing your opaque session bearer token after you sign in so you remain authenticated across page loads, and (b) remembering your visual display preference (`light` or `dark` theme).
- **Self-Hosted Assets:** All fonts (`.woff2` subsets), stylesheets (`tokens.css`, `app.css`), and scripts are self-hosted on our origin domain. Visiting the Platform triggers zero requests to Google Fonts or third-party ad networks.
- **Do Not Track ("DNT") Signals:** Because the Platform never tracks users across third-party websites or over time for commercial or profiling purposes, we treat all visitors—regardless of browser DNT header configuration—under a strict zero-tracking standard.

---

## 6. How We Use Information & Categorical Prohibitions (SOPIPA Compliance)

Pursuant to Cal. Bus. & Prof. Code § 22584(b) (SOPIPA) and Cal. Educ. Code § 49073.1 (AB 1584), CAJCL uses information collected through the Platform **solely for K–12 school and interscholastic academic convention purposes**, specifically to:
1. Authenticate registrants and enforce chapter-level and role-based access boundaries;
2. Schedule and administer academic exams, pre-convention contests, Olympika athletic heats/brackets, and volunteer shifts;
3. Tabulate individual and chapter sweepstakes awards and distribute results to Chapter Sponsors;
4. Calculate chapter registration invoices, complimentary chaperone ratios, and aggregate meal counts;
5. Verify completion of mandatory physical permission, waiver, and medical documentation; and
6. Maintain system security, rate-limit brute-force attacks, and audit database modifications.

**We Never Sell, Rent, or Monetize Data:**
- We **never** sell, rent, lease, or trade student or adult information to any third party.
- We **never** use or disclose information collected on the Platform for targeted advertising, behavioral advertising, or commercial marketing.
- We **never** amass a commercial profile about any K–12 student except in direct furtherance of administering the Convention.

---

## 7. Access Controls, Role Isolation, and Sub-Processors

### 7.1 Strict Role-Based Access Control (RBAC)
Access to data within the Platform is compartmentalized by role and enforced across every API route:
- **Public Visitors:** View only the Convention schedule (`#/schedule`), published informational pages, and pre-aggregated headcounts (`/public/stats`). No individual records are ever publicly visible.
- **Student Delegates (`delegate`):** View and edit only their own activity sheet, contest uploads, and assigned heat/bracket times.
- **Chapter Sponsors (`sponsor`):** View and manage only the Assigned Delegate IDs, adult registrants, and invoices belonging to their own `school_id`. Cross-chapter access is cryptographically blocked (`HTTP 403 Forbidden`).
- **Contest Judges (`judge`):** View only anonymized pre-convention contest submissions (`Entry N`) within their assigned division.
- **Athletics Director (`athletics`):** Views Olympika entrants solely by Assigned Delegate ID, chapter, grade, and Latin level to assign heats and brackets.
- **Activities Chair (`activities`):** Views Photo Contest submissions (tagged by Chapter + Assigned Delegate ID) and Sponsor-approved Activities Potluck helpers.
- **Logistics Chair (`logistics`):** Edits the public master schedule without access to any registrant records.
- **Convention Presidents & Registration/Academics/Awards Chairs (`*`, `registration`, `academics`, `awards`):** Authorized board officers and adult advisors access state-wide operational rosters, invoicing ledgers, and tabulation views strictly to run the Convention. Only the Convention Presidents have access to the restricted Google Workspace Drive folder housing scanned physical medical and waiver PDFs.

### 7.2 Authorized Infrastructure Sub-Processors
We engage a minimal set of industry-standard cloud infrastructure sub-processors to host and operate the Platform:

| Sub-Processor | Operational Function | Security Standards & Safeguards | Data Processed |
| :--- | :--- | :--- | :--- |
| **GitHub, Inc.** | Static Frontend Hosting (GitHub Pages CDN) & Automated Deployment (GitHub Actions) | SOC 2 Type II, ISO/IEC 27001, TLS 1.3 | Static HTML/CSS/JS assets, public informational pages, standard edge HTTP request logs |
| **Modal Labs, Inc.** | Serverless API Compute Tier & Background Workers | SOC 2 Type II, TLS 1.3, isolated container secrets | Ephemeral API requests, authentication verification, PDF badge/packet generation |
| **Managed Cloud Database Provider** | Distributed Relational Database Engine (libSQL / SQLite) | SOC 2 Type II, AES-256 volume encryption at rest, TLS 1.3 in transit | De-identified student delegate rows (Assigned IDs), adult registrant profiles, chapter invoices, hashed credentials, and `audit_log` |
| **Google LLC** | Google Workspace for Education / Google Drive & Apps Script | SOC 2/3, ISO/IEC 27001/27018, AES-256 encryption | Uploaded contest entries, Photo Contest images/thumbnails, public informational Doc sources, and President-restricted physical waiver/medical PDF scans |

Each sub-processor is governed by standard enterprise data processing terms prohibiting the use of CAJCL data for independent commercial purposes.

### 7.3 Legal and Safety Disclosures
We may disclose information outside the ordinary course of Convention administration only if required to do so by a valid subpoena, court order, or other compulsory legal process, or when we believe in good faith that disclosure to school officials, emergency medical personnel, or law enforcement is immediately necessary to protect the physical health or safety of a student or attendee.

---

## 8. Technical and Organizational Security Program (Cal. Civ. Code § 1798.81.5)

CAJCL maintains a Written Information Security Program ("**WISP**") featuring technical and organizational controls appropriate to K–12 educational operations:
1. **Encryption in Transit and at Rest:** All network traffic between browsers, our CDN, our serverless API, and our database engine is encrypted via TLS 1.3. Database storage volumes and Google Drive repositories are encrypted at rest using AES-256.
2. **Zero Cleartext Credentials or IPs:** Login tokens (`PPP-XXXXX-XXXXX`) and logged client IP addresses are salted and hashed using `HMAC-SHA256` with a high-entropy secret pepper stored exclusively in isolated serverless secrets. Session bearer tokens contain 256 bits of cryptographic entropy and are stored solely as `SHA-256` digests.
3. **Brute-Force Rate Limiting:** Authentication endpoints enforce automatic lockouts after 5 failed attempts per login token per hour, 10 failed sign-in attempts per IP address per 15 minutes, and 30 failed chapter join-code attempts per IP address per 15 minutes.
4. **Injection & XSS Hardening:** 100% of database queries execute via pre-compiled, parameterized SQL statements (`backend/queries/*.sql`). The frontend renders dynamic content via safe DOM text nodes (`document.createTextNode`) and enforces a strict Content Security Policy (`CSP`), `X-Frame-Options: DENY`, and `X-Content-Type-Options: nosniff`.
5. **Mandatory Transactional Audit Logging:** Database triggers reject any data mutation that does not simultaneously write an immutable attribution record to `audit_log`.

---

## 9. Data Retention and Mandatory Post-Convention Purge (April 12, 2027)

Pursuant to COPPA (16 C.F.R. § 312.10) and SOPIPA (Cal. Bus. & Prof. Code § 22584(d)(2)), CAJCL retains operational data only for the duration of the 2027 Convention cycle:

1. **Active Convention & Tabulation Window (Through April 11, 2027):** Operational records remain active through the Convention (March 12–13, 2027) and a 30-day post-convention verification window so Chapter Sponsors can review placement reports and resolve score inquiries.
2. **Mandatory Complete Purge Date (April 12, 2027):** Exactly thirty (30) calendar days after the close of the Convention, CAJCL executes a comprehensive data purge (`scripts/purge_convention_data.py` and Drive repository destruction) that permanently expunges:
   - All adult registrant names, email addresses, mobile phone numbers, and volunteer notes;
   - All authentication credentials, session token hashes, rate-limit logs, and operational audit trail references;
   - All pre-convention creative contest files and At-Convention Photo Contest images and thumbnails stored in Google Drive; and
   - All scanned PDF copies of physical *Student Waiver and Permission Forms*, *Student Medical Forms*, and *Adult Medical Forms* stored in the restricted President Google Drive repository.
3. **Permanent De-Identified Historical Archive:** Following the April 12, 2027 purge, CAJCL retains only a strictly de-identified statistical archive recording the convention year (`2027`), Assigned Delegate ID/badge number, chapter name, academic grade (6–12), Latin level, and competition placements, with zero personal names or contact details.
4. **Non-Profit Financial Accounting Retention:** Chapter-level institutional accounting records (`schools` and `payments` tables recording institutional check numbers and chapter balances, containing zero student PII) are retained for seven (7) years to comply with Internal Revenue Code § 501(c)(3) and California Corporations Code § 6320 recordkeeping mandates.

---

## 10. California Education Code § 49073.1 (AB 1584) School District Addendum

For participating California public school districts, county offices of education, and charter schools ("**Local Educational Agencies**" or "**LEAs**"), CAJCL incorporates the following statutory terms into its relationship with each participating LEA pursuant to Cal. Educ. Code § 49073.1:

1. **LEA Ownership and Control:** Any pupil records (as defined in Cal. Educ. Code § 49073.1(d)(2)) provided by or on behalf of an LEA or its employees (Chapter Sponsors) continue to be the property of and under the legal control of the participating LEA.
2. **De-Identified Possession & Student-Generated Content:** Student competition entries created or uploaded by a pupil may be managed and withdrawn by the pupil at any time prior to the April 12, 2027 purge.
3. **Strict Purpose Limitation:** CAJCL shall not use any information in a pupil record for any purpose other than those expressly required or permitted by this Policy and the Terms of Service to administer the 72nd Annual CAJCL State Convention.
4. **Parent, Legal Guardian, and Eligible Pupil Review & Correction:** A parent, legal guardian, or eligible pupil (aged 18 or older) may review personal information in the pupil's records and correct erroneous information by contacting their school's Chapter Sponsor (who holds the local `Assigned Delegate ID ↔ Student Name` mapping key and direct portal editing controls) or by submitting a written request to the CAJCL Privacy Coordinator at the address in Section 13.
5. **Security and Training:** CAJCL implements the encryption, access-control, and audit safeguards detailed in Section 8 and restricts operational scopes to designated Convention Officers and Chapter Sponsors who are instructed on strict confidentiality obligations.
6. **Breach Notification Compliance:** In the event of an unauthorized disclosure of pupil records, CAJCL will follow the statutory notification procedures set forth in Section 12.
7. **Post-Term Non-Retention Certification:** CAJCL certifies that pupil records shall not be retained or available to CAJCL beyond the mandatory **April 12, 2027** purge date (or immediately upon an LEA's or Chapter Sponsor's earlier invocation of redaction), except for de-identified historical placement statistics exempt under Cal. Educ. Code § 49073.1(d)(2) and Cal. Bus. & Prof. Code § 22584(g).
8. **FERPA Compliance Cooperation:** CAJCL and the participating LEA shall work cooperatively to ensure continuous compliance with FERPA (20 U.S.C. § 1232g) via the ID-Only de-identified record standard (34 C.F.R. § 99.31(b)(1)).
9. **Prohibition on Targeted Advertising:** CAJCL is strictly prohibited from using any information in a pupil record to engage in targeted advertising.

---

## 11. Parental, Student, and Adult Privacy Rights

Regardless of age or chapter affiliation, parents, legal guardians, student delegates, and adult registrants have the following rights:
1. **Right to Inspect and Review:** You may request confirmation of all data fields, event selections, or uploaded files associated with a specific Assigned Delegate ID or adult profile.
2. **Right to Correct:** Your Chapter Sponsor may update a delegate's grade, Latin level, or activity selections directly in the portal prior to the registration lock deadline (**February 13, 2027 at 11:59 PM PST**), or you may request administrative correction at any time.
3. **Right to Immediate Deletion / Redaction:** You may request that a student's or adult's record, uploaded contest files, or Photo Contest submissions be permanently deleted prior to the April 12, 2027 purge. A Chapter Sponsor can execute immediate redaction directly from the chapter roster (`#/roster`), or you may write to our Privacy Coordinator, who will process verified deletion requests within ten (10) business days.
4. **Right to Revoke Consent:** A parent or legal guardian may revoke consent for a student's participation at any time by notifying the student's Chapter Sponsor or the Privacy Coordinator in writing, whereupon the student's digital record and any uploaded media will be immediately redacted.

---

## 12. Incident Response and Data Breach Notification Protocol (Cal. Civ. Code § 1798.82)

Although student database rows contain no student names or contact information—providing structural protection against statutory identity exposure—CAJCL maintains a formal four-phase incident response plan for adult contact records and restricted Drive repositories:
1. **Phase 1 — Containment (Within 1 Hour of Discovery):** Revoke compromised sessions or login tokens and rotate serverless cryptographic secrets (`CODE_PEPPER`, database tokens, or webhook keys).
2. **Phase 2 — Forensic Assessment (Within 24 Hours):** Audit the immutable `audit_log` and access logs to determine the exact scope of affected records.
3. **Phase 3 — Remediation:** Patch any underlying vulnerability and verify integrity across all automated security tests.
4. **Phase 4 — Written Notification (Within 30 Days):** If unencrypted or re-identifiable personal information (such as adult contact records or restricted physical waiver/medical scans) is confirmed to have been acquired by an unauthorized person, CAJCL will notify affected Chapter Sponsors, participating school districts, and affected individuals/families in writing in the most expedient time possible and without unreasonable delay—and in no event later than thirty (30) calendar days following discovery—in full compliance with Cal. Civ. Code § 1798.82 and Cal. Educ. Code § 49073.1(b)(6).

---

## 13. Changes to This Privacy Policy

We may update this Privacy Policy to reflect operational refinements or regulatory guidance. The "Last Updated" date at the top of this page indicates when revisions took effect. Material changes that expand the categories of information collected or alter how information is shared will be communicated directly to registered Chapter Sponsors via email prior to taking effect and will never apply retroactively to student data without prior notice and authorization.

---

## 14. Designated Privacy Coordinator and Contact Information

All questions, parental review or deletion requests, school district compliance inquiries, and formal legal notices regarding this Privacy Policy should be directed to our designated Privacy Coordinator:

**Mark Michalak, Convention Advisor & Privacy Coordinator**  
California Junior Classical League (CAJCL) / University High School JCL  
University High School  
4771 Campus Drive  
Irvine, CA 92612  
**Email:** [state@uhsjcl.org](mailto:state@uhsjcl.org)
