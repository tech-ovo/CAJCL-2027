# Registration Chair Standard Operating Procedure (SOP)

**Platform:** `state.uhsjcl.org`  
**Target Event:** 72nd Annual CAJCL State Convention (March 12–13, 2027)  
**Audience:** Registration Chairs, Convention Presidents, Chapter Administrators  

---

## 1. System Overview & Authentication

The CAJCL Registration Platform operates entirely without conventional username/password pairs. Access control uses deterministic, cryptographically hashed access codes.

### Credential Format
Every attendee is provisioned a unique 13-character identifier formatted as `PPP-XXXXX-XXXXX`:
- **`PPP` (Entity Prefix):** Identifies registrant classification.
  - `SPO`: Chapter Sponsor / Primary Teacher Contact
  - `VOL`: Adult Volunteer / Chaperone
  - `DEL`: Student Delegate (Grades 6–12)
- **`XXXXX-XXXXX`:** Nine Crockford Base32 characters plus a checksum symbol. Ambiguous characters (`I`, `L`, `O`, `Z`) are excluded.

### Access Protocols
1. **Desktop/Direct Entry:** Attendees input their code at [state.uhsjcl.org](https://state.uhsjcl.org).
2. **Mobile / QR Scanning:** Attendee sheets feature a QR code that encodes the credential in the URL fragment (`#DEL-...`), ensuring credentials bypass intermediate web server logs.
3. **Session Persistence:** Authenticated sessions persist via client-side storage tokens for up to 180 days.
4. **Credential Reissuance:** Raw codes are never stored in plaintext (stored exclusively as `HMAC-SHA256`). Lost codes cannot be recovered; they must be reissued, immediately invalidating former active sessions.

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
3. **Record the Access Code:** The generated `SPO-...` code is displayed **once**. Transmit this credential securely to the chapter sponsor via the official launch template.

---

## 4. Sponsor Onboarding Communication Template

Transmit this standard communication upon chapter provisioning:

```text
Subject: Registration Open: 72nd CAJCL State Convention (March 12–13, 2027)

salvē [Sponsor Name],

Registration is officially open for the 72nd California Junior Classical League State Convention, held March 12–13, 2027, hosted jointly by University High School and Woodbridge High School.

Access the digital registration platform at: https://state.uhsjcl.org
Your Chapter Access Code: [SPO-XXXXX-XXXXX]

======================================================================
OPERATIONAL WORKFLOW
======================================================================
1. Access the Portal: Sign in using your unique sponsor access code above.
2. Submit Roster: Paste your attendee list (names only) into the Roster Import tool. The parser accepts spreadsheet columns, bulleted lists, and unformatted text. Review the parsed output and confirm submission.
3. Distribute Attendee Credentials: Generate and print your chapter packet. Each delegate and adult receives an individual sheet with their personal code and QR sign-in.
4. Digital Activity Sheets: Attendees sign in individually to submit their test and workshop preferences.

======================================================================
FINANCIAL SCHEDULE
======================================================================
- Delegate Registration Fee: $140.00 per student
- Adult Chaperones: One complimentary chaperone per 10 registered delegates
- Additional Chaperones: $75.00 per adult
- SCL Attendees: Complimentary (non-billed)

Invoices update dynamically as your roster evolves. Remit checks payable to:
  University High School JCL c/o Mark Michalak
  4771 Campus Dr, Irvine, CA 92612
  Memo: [Chapter Name] Registration

======================================================================
CRITICAL DEADLINES
======================================================================
- Registration & Activity Sheets Lock: February 13, 2027 at 11:59 PM PST
- Postmark Deadline for Fees & Physical Paperwork: February 13, 2027
- Convention Dates: March 12–13, 2027

======================================================================
MANDATORY PHYSICAL DOCUMENTATION
======================================================================
The following hard-copy documents require physical ink signatures:
1. Student Waiver & Permission Form (Parent/Guardian signature required)
2. Student Medical Form (Parent/Guardian signature required)
3. Adult Medical Form (All attending adults)

Sponsors must collect, scan into their chapter's assigned Google Drive folder, and mail physical originals alongside registration checks.

Support Contact: state@uhsjcl.org
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
- **Strict No-Refund Policy:** 
  - If a delegate is cancelled **prior to payment entry**, their fee is dropped from the invoice.
  - If a delegate is cancelled **after payment entry**, their record converts to `cancelled_paid`. They are excluded from food counts, but retain their billable charge so accounting balances remain settled.

### Processing Payments
1. Navigate to **Chapters** and locate the target school row.
2. Select **Payment**.
3. Record the transaction amount (in integer cents), check/reference number, and remittance notes.
4. **Correcting Discrepancies:** Payment records are append-only and cannot be updated or deleted. To adjust an erroneous entry (e.g., entered $1,400 instead of $140), submit an offsetting negative entry (e.g., `-$1,260`) with explanatory audit remarks.

---

## 7. Chapter & Roster Management

From **Chapters → Roster**, administrators execute attendee-level interventions:

| Operation | Trigger & Standard Procedure |
| :--- | :--- |
| **Paste Roster** | Ingest new batch of attendees for a chapter. Supports additive uploads without overwriting existing entries. |
| **Add Person** | Provision a single delegate or adult. Generates and surfaces the access code once. |
| **Edit Profile** | Correct spelling, suffix, or emergency guardian contact info. Does not alter access codes or invalidate sessions. |
| **Administrative Submission** | Populate an attendee's digital form on their behalf; logged with administrative actor attribution. |
| **Team Athletics Entry** | Register chapter rosters for aggregate activities (Kickball, Ultimate Frisbee, etc.). |
| **Reissue Access Code** | Regenerates access code on loss. Immediately invalidates former credential and active sessions. |
| **Reopen Form** | Bypasses deadline lock for an individual registrant, allowing post-deadline modifications. |
| **Waive Activity Sheet** | Applies exclusively to walk-on attendees registered at the Friday desk, removing completion blockers. |
| **Cancel Attendee** | Soft-deletes attendee from active headcounts while retaining billing audit integrity. Fully reversible. |

---

## 8. Incident Response & Troubleshooting Playbook

| Scenario / Symptom | Root Cause Analysis | Remediation Protocol |
| :--- | :--- | :--- |
| **Lost Credentials** | Attendee misplaced paper credential sheet. | Open chapter roster, locate individual, click **New Code**. Instruct sponsor to print replacement sheet immediately. Old code is voided. |
| **Authentication Rejection** | User receiving "Code Not Recognized". | 1. Confirm code has not been superseded by a newer reissuance.<br>2. Check for temporary rate limit (5 failed attempts within 60 minutes triggers lockout).<br>3. Verify input against Crockford Base32 characters (system auto-corrects `O` to `0`, but check character validates structure). |
| **Attendee Profile Correction** | Name misspelled or incorrect grade. | Click **Edit** on roster row. Access code remains unchanged; printout remains valid. |
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
- **No Direct Student Emails:** The system explicitly forbids collecting delegate email addresses. All communications route through sponsors.
- **Physical Document Segregation:** Medical data and liability waivers reside exclusively on paper and in a restricted-access Google Drive folder. No health records are ingested into the web database.
- **Role Isolation:** Registration chairs hold operational privileges within their functional scope. System-wide configuration mutations (modifying convention pricing, global deadlines, or viewing raw audit trails) require Convention President authorization.