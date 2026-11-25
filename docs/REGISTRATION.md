# Registration Chair Standard Operating Procedure (SOP)

**Platform:** `state.uhsjcl.org`  
**Target Event:** 72nd Annual CAJCL State Convention (March 12–13, 2027)  
**Audience:** Registration Chairs, Convention Presidents, Chapter Administrators  

---

## 1. System Overview & Authentication

The CAJCL Registration Platform operates entirely without conventional username/password pairs. Access control uses deterministic, cryptographically hashed login tokens.

### Credential Format
Every attendee is provisioned a unique 13-character identifier formatted as `PPP-XXXXX-XXXXX`:
- **`PPP` (Entity Prefix):** Identifies registrant classification.
  - `SPO`: Chapter Sponsor / Primary Teacher Contact
  - `VOL`: Adult Volunteer / Chaperone
  - `DEL`: Student Delegate (Grades 6–12)
- **`XXXXX-XXXXX`:** Nine Crockford Base32 characters plus a checksum symbol. Ambiguous characters (`I`, `L`, `O`, `Z`) are excluded.

### Access Protocols
1. **Desktop/Direct Entry:** Attendees input their login token at [state.uhsjcl.org](https://state.uhsjcl.org).
2. **Sponsor Two-Factor Authentication (One-Time Code):** To secure student data, chapter sponsors receive a one-time verification code each time they sign in alongside their `SPO-XXXXX-XXXXX` login token.
3. **Mobile / QR Scanning:** Attendee sheets feature a QR code that encodes the credential in the URL fragment (`#DEL-...`), ensuring credentials bypass intermediate web server logs.
4. **Session Persistence:** Authenticated sessions persist via client-side storage tokens (see `docs/SECURITY.md` for session lifespans).
5. **Credential Reissuance:** Raw codes are never stored in plaintext (stored exclusively as `HMAC-SHA256`). Lost codes cannot be recovered; they must be reissued, immediately invalidating former active sessions.

---

## 2. Navigation Architecture

Upon authentication, registration chairs have access to the administrative workspace:

| Navigation Item | Functional Scope |
| :--- | :--- |
| **Welcome** | Public portal view and live convention statistics. |
| **Registration** | Personal attendee registration form (meal preferences, emergency contact, dietary requirements). |
| **Overview** | Executive KPI summary (aggregate headcounts, completion rates, financial balances). |
| **Chapters** | Chapter directory, roster operations, payment logging, and credential management. |
| **Check-in** | Friday on-site registration desk workflow. |
| **Resources** | External links to Certamen practice arenas and digital materials. |

---

## 3. Chapter Provisioning Workflow

### Adding a New Chapter
Navigate to **Chapters → Add a chapter**:
1. **School Name:** Enter the official institution name, including explicit division designations (e.g., *University High School*, *Northwood Middle School*).
2. **City:** Municipal location of the institution.
3. **Level:** Select either **Middle School (MS)** or **High School (HS)**. If an institution sends both middle and high school delegations, **provision two discrete chapters**.
4. **Billing Exemption:** Toggle *This chapter is not billed* strictly for California Senior Classical League (SCL) delegations.
5. **Special Discounts:** Input any approved contractual discounts (in cents) with mandatory itemized justification.

### Assigning Chapter Sponsors
1. Once a chapter record is created, click **Add Sponsor**.
2. Complete the legal name and adult profile.
3. **Record the Login Token:** The generated `SPO-...` code is displayed **once**. Transmit this credential securely to the chapter sponsor via the official launch template.
4. **Forward the Join Code:** Every chapter has an 8-character join code (shown on the confirmation after *Add a chapter*, in the *Add Sponsor* confirmation, and any time from **Chapters → Join code**). Put it in the same email. Unlike the login token it is **not** a secret and can be viewed again.

---

## 4. Sponsor Onboarding Communication Template

Transmit this standard communication upon chapter provisioning (registration opens **December 1, 2026**):

```text
Subject: Registration Open: 72nd CAJCL State Convention (March 12–13, 2027)

salvē [Sponsor Name],

Registration is officially open for the 72nd California Junior Classical League State Convention, held March 12–13, 2027 at University High School (4771 Campus Drive, Irvine, CA 92612), hosted jointly by University High School and Woodbridge High School.

Access the digital registration platform at: https://state.uhsjcl.org
Your Chapter Login Token: [SPO-XXXXX-XXXXX]
Your Chapter Join Code:   [XXXX-XXXX]

(Note: Please do not share public links to the convention website on social media; distribute only to registered attendees and families.)

======================================================================
OPERATIONAL WORKFLOW
======================================================================
1. Access the Portal: Sign in using your sponsor login token above. To secure student data, you will receive a one-time code each time you sign in.
2. Distribute & Collect Paper Forms FIRST: Print and distribute the Medical Form (for all attendees: students, sponsors, and chaperones) and the CAJCL Waiver (students only). Because we may not collect student data without parental consent, ONLY distribute your chapter Join Code sheet to students AFTER their signed waiver and medical form have been submitted to you.
3. Invite Attendees via Join Code: Once a student's waiver and medical form are turned in, give them the chapter Join Code sheet (also used for adults: SCL, Sponsors, Chaperones) so they can complete their Activity Sheet on the website. Once a student sets their name, grade, and Latin level, only you (the sponsor) can change those details.
4. Monitor & Approve Registration: Review and edit all data students enter on the website. Approve joined students on your Roster; you can also remove students, reset your join code, and enable/disable joining at any time.
5. Chapter Details & Leaders: Input chapter details (e.g., event potluck sign-ups, meals requested), complete your own Adult Activity Sheet, and optionally assign chapter leaders (e.g., to manage chapter contests or team registration).
6. Generate Invoice & Mail Package: Generate your invoice from the website and mail ONE CHECK together with all physical signed waivers and medical forms by February 13, 2027.

======================================================================
FINANCIAL SCHEDULE
======================================================================
- Delegate Registration Fee: $140.00 per student (includes Friday dinner & Saturday breakfast, lunch, and dinner; only the snack bar requires money)
- Adult Chaperones: One complimentary adult per 10 registered students
- Additional Adults: $75.00 per adult (except SCL, who are complimentary)
- New Schools: Contact the Convention sponsors or presidents to receive 75% off!
- Refunds: Refunds will not be made. Substitutions may be made before February 26, 2027.

Invoices update dynamically as your roster evolves. Send ONE CHECK by February 13, 2027 to:
  University High School c/o Mark Michalak
  4771 Campus Drive, Irvine, CA 92612
  Memo: [Chapter Name] Registration

You will be notified via email and on the website when your check arrives.

======================================================================
CRITICAL DEADLINES
======================================================================
- Convention Registration Opens: December 1, 2026
- CARCER Registration Due (CAJCL Online Database): February 7, 2027
- Convention Registration & Activity Sheets Lock / Check & Forms Postmark: February 13, 2027
- CARCER (Menlo School N / Woodbridge HS S): February 21, 2027 (10:00 AM – 1:00 PM)
- Last Day for Substitutions: February 26, 2027
- Pre-Convention Contests, Scrapbook Pictures & Publicity Portfolio Due (Website): March 6, 2027
- State Convention: March 12–13, 2027 (University High School, Irvine)
- Digital Scrapbook Due (Website): March 13, 2027 at 10:00 AM

======================================================================
MANDATORY PHYSICAL DOCUMENTATION (PAPER ONLY — NO GOOGLE DRIVE SCANS)
======================================================================
The following hard-copy documents require physical ink signatures:
1. CAJCL Student Waiver & Permission Form (students only; parent/guardian signature required, including consent for online data use)
2. Medical Form (all attending convention: students, sponsors, and chaperones)

Mail ALL physical medical forms and waivers in the same package as your registration check by February 13, 2027. Unlike prior years, we are NOT asking sponsors to scan documents or upload them to Google Drive. Sponsors must ensure that the mailed documents match the website registration. If substitutions are made after February 13 (through February 26), sponsors may either mail the updated forms to the same address or bring them during Friday check-in.

Registration Questions: state@uhsjcl.org
Convention Presidents / Feedback: conventionpresident@cajcl.org
```

---

## 5. Registration Metrics & Status Criteria

The **Overview** dashboard aggregates live convention metrics:

| Metric | Business Logic & Criteria |
| :--- | :--- |
| **Chapters** | Total active chapters and count of chapters with populated rosters. |
| **Delegates** | Total active student registrations (Grades 6–12). |
| **Adults** | Total attending adult count, segmented by Sponsors and Chaperones. |
| **Forms Completed** | Count of fully validated attendees: <br>• **Delegate:** Online form submitted AND Sponsor attestation of physical waiver and medical forms confirmed.<br>• **Adult:** Online form submitted AND Sponsor attestation of physical medical form confirmed. |
| **Financial Balance** | Total billed fees minus verified cash/check receipts across all chapters. |

*Note: SCL records are excluded from completion requirements and invoicing calculations.*

---

## 6. Financial Ledger & Reconciliation SOP

The platform maintains an immutable audit ledger for all accounting actions.

### Invoicing Principles
- **Dynamic Calculation:** Account balances recalculate instantaneously on roster mutations. Never rely on static printouts.
- **Strict No-Refund Policy & Substitutions:** 
  - If a delegate is cancelled **prior to payment entry**, their fee is dropped from the invoice.
  - If a delegate is cancelled **after payment entry**, their record converts to `cancelled_paid`. They are excluded from food counts, but retain their billable charge so accounting balances remain settled.
  - **Substitutions** may be made before **February 26, 2027**. Updated paper waivers/medical forms for substituted attendees may be mailed to University High School c/o Mark Michalak or brought to Friday check-in.
  - **New School Discount:** New schools may contact the Convention sponsors or presidents to receive **75% off** registration fees (logged as an approved chapter discount).

### Processing Payments
1. Navigate to **Chapters** and locate the target school row.
2. Select **Payment**.
3. Record the transaction amount (in integer cents), check/reference number, and remittance notes.
4. **Confirm Receipt to Sponsor:** Per the Convention Book, sponsors are notified via email and on the website when their check arrives.
5. **Correcting Discrepancies:** Payment records are append-only and cannot be updated or deleted. To adjust an erroneous entry (e.g., entered $1,400 instead of $140), submit an offsetting negative entry (e.g., `-$1,260`) with explanatory audit remarks.

---

## 7. Chapter & Roster Management

From **Chapters → Roster**, administrators execute attendee-level interventions:

| Operation | Trigger & Standard Procedure |
| :--- | :--- |
| **Paste Roster** | Ingest new batch of attendees for a chapter. Supports additive uploads without overwriting existing entries. |
| **Add Person** | Provision a single delegate or adult. Generates and surfaces the login token once. |
| **Join Code** | Shown on every roster and under **Chapters → Join code**. Print the join sheet, close/reopen joining, or replace the code (old one stops working at once). |
| **Approve / Deny** | Students who joined by code wait in the roster's *Waiting for approval* panel, marked **Preliminary**. The sponsor approves or denies; a chair can see them (and their separate count on Chapters and Overview) but must sign in as the sponsor to decide. Denial removes all of the student's data. |
| **Edit Profile** | Correct spelling, suffix, or emergency guardian contact info. Does not alter login tokens or invalidate sessions. |
| **Administrative Submission** | Populate an attendee's digital form on their behalf; logged with administrative actor attribution. |
| **Team Athletics Entry** | Register chapter rosters for aggregate activities (Kickball, Ultimate Frisbee, etc.). |
| **Reissue Login Token** | Regenerates login token on loss. Immediately invalidates former credential and active sessions. |
| **Reopen Form** | Bypasses deadline lock for an individual registrant, allowing post-deadline modifications. |
| **Waive Activity Sheet** | Applies exclusively to walk-on attendees registered at the Friday desk, removing completion blockers. |
| **Cancel Attendee** | Soft-deletes attendee from active headcounts while retaining billing audit integrity. Fully reversible. |

---

## 8. Incident Response & Troubleshooting Playbook

| Scenario / Symptom | Root Cause Analysis | Remediation Protocol |
| :--- | :--- | :--- |
| **Lost Credentials** | Attendee misplaced paper credential sheet. | Open chapter roster, locate individual, click **New Code**. Instruct sponsor to print replacement sheet immediately. Old code is voided. |
| **Authentication Rejection** | User receiving "Code Not Recognized". | 1. Confirm code has not been superseded by a newer reissuance.<br>2. Check for temporary rate limit (5 failed attempts within 60 minutes triggers lockout).<br>3. Verify input against Crockford Base32 characters (system auto-corrects `O` to `0`, but check character validates structure). |
| **Attendee Profile Correction** | Name misspelled or incorrect grade. | Click **Edit** on roster row. Login token remains unchanged; printout remains valid. |
| **Form Revisions Post-Deadline** | Delegate requires category/test adjustment after February 13 lock. | Click **Reopen Form**. Delegate edits directly. Click **Close Form** upon resolution (form lock re-engages). |
| **Payment Ledger Discrepancy** | Check amount entered incorrectly. | Post an offsetting adjustment transaction with sign inverted (`-` or `+`) and detailed ledger memo. |
| **Invoice Variance** | Chapter claims fee calculation is inaccurate. | 1. Compare against live web roster rather than historical PDF printouts.<br>2. Verify adult-to-delegate ratio (1 free adult per 10 delegates; 11th delegate unlocks 2nd free adult).<br>3. Check if manual discounts were properly logged. |
| **Server Latency / Cold Start** | Initial page load takes 5–10 seconds. | Backend operates on serverless infrastructure and suspends during idle periods. Normal wake cycle takes 3–5 seconds. If timeout exceeds 30 seconds, escalate to Technology Commissioners. |

---

## 9. Day-Of Arrival & Check-In Operations

On Friday, March 12, 2027, the check-in desk executes chapter arrivals via **Check-in**:

1. **Chapter Arrival Record:** Click the school row to open the operational drawer.
2. **Physical Paperwork Audit:** Verify receipt of physical ink-signed Student Waivers, Student Medical Forms, and Adult Medical Forms.
3. **Walk-On Registrations:**
   - Select **Add Delegate**. Enter name and grade.
   - Record generated badge/code.
   - System automatically marks `activity_sheet_waived` (testing schedules are finalized).
   - **Hard Constraint:** Physical medical and waiver documents remain mandatory; walk-ons cannot enter without signed forms.
4. **Mark Complete:** Click **Registration Complete** to log official arrival timestamp.

---

## 10. Governance & Security Guardrails

To protect minor privacy and institutional compliance:
- **Parental Consent Required Before Collection:** Students without a parent-signed CAJCL Waiver (which includes consent for online use of attendee data) cannot attend and must not be given a chapter Join Code.
- **No Direct Student Emails:** The system explicitly forbids collecting delegate email addresses. All communications route through sponsors.
- **Physical Document Segregation (Paper Only):** Medical forms and signed liability waivers reside **exclusively on paper**, mailed with the chapter's registration check (or brought at check-in for substitutions). Sponsors are **not** asked to scan or upload them to Google Drive, and no health records are ingested into the web database.
- **Role Isolation & Private Code:** Convention hosts can see everything; sponsors can only see their own students; logged-in students can only see themselves; the public sees only schedule/map/aggregate counts. Public links must not be shared widely on social media. All website code (especially back-end server code) must remain private.
- **Reliable Backup:** All critical registration data and schedules must be backed up/synced to a reliable secondary store (e.g., restricted Google Sheet) in case of a tool outage.