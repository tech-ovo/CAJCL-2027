# Risk Register & Technical Threat Assessment

**Platform:** 72nd Annual CAJCL State Convention Platform (`state.uhsjcl.org`)  
**Document Classification:** Enterprise Risk Governance & Mitigation Register  
**Audience:** Technology Commissioners, Board Reviewers, Systems Engineering  

---

## 1. Risk Governance & Classification Framework

Risks are categorized across severity, likelihood, and mitigation state:

| Status Flag | Definition |
| :--- | :--- |
| **MITIGATED** | Fully addressed in codebase with verified, automated regression tests. |
| **PARTIAL** | Substantively mitigated; bounded residual edge cases remain under active monitoring. |
| **ACCEPTED** | Understood engineering trade-off intentionally sustained based on cost/benefit analysis. |
| **OPEN** | Unaddressed vulnerability or gap requiring scheduled engineering remediation. |

---

## 2. Risk Register by Functional Domain

### 2.1 Data Loss, Concurrency & State Integrity

| Risk Scenario | Impact | Severity | Status | Mitigation & Architectural Defense |
| :--- | :--- | :--- | :--- | :--- |
| **Duplicate Roster Commits** | Accidental double-submission of attendee rosters creating phantom records. | High | **MITIGATED** | Previews issue an HMAC-signed idempotency token binding `school_id`, payload hash, and roster state fingerprint. Commits record `idempotency_key` with a database `UNIQUE` constraint. Duplicate requests return initial results idempotently. |
| **Concurrent Roster Overwrite** | Two chapter sponsors edit or commit distinct rosters simultaneously. | High | **MITIGATED** | Preview tokens embed a cryptographic fingerprint of the target roster. If a concurrent actor mutates the roster prior to commit, the stale commit is rejected, preventing accidental duplicate merges. |
| **Massive Payload Injection (DoS)** | Malicious or accidental submission of >5,000 lines into parser. | Medium | **MITIGATED** | FastAPI middleware rejects payloads exceeding 1 MB based on `Content-Length`. Ingestion logic strictly caps roster imports at 500 lines per transaction. |
| **Stale Transaction Reads** | In-flight transactions committing against concurrent updates. | High | **MITIGATED** | Switched from singleton connection handles to dynamic, thread-local pooled connections. Every mutation operates within an explicit ACID transaction. |

---

### 2.2 Identity, Credentialing & Session Security

| Risk Scenario | Impact | Severity | Status | Mitigation & Architectural Defense |
| :--- | :--- | :--- | :--- | :--- |
| **Session Invalidation Desync** | Attendee maintains active sessions after credential reissuance. | High | **MITIGATED** | Access code regeneration executes an atomic transaction revoking all active sessions derived from the predecessor credential, returning HTTP 401 on subsequent requests. |
| **Unusable Paper Reprints** | Sponsors generate printed sheets missing raw access codes. | Medium | **MITIGATED** | Since plaintext codes are never persisted, the portal forbids generic full-roster packet reprints. Replacement requires invoking the **Issue New Codes** workflow, which surfaces plaintext credentials once alongside a dedicated print link. |
| **Shared Terminal Exposure** | Students abandon active sessions on shared school computers. | Medium | **PARTIAL** | Prominent global sign-out immediately revokes sessions server-side. Account dashboard permits selective remote revocation. 180-day default longevity accepted to accommodate young students lacking persistent devices. |
| **Keyspace Enumeration** | Brute-force guessing attacks targeting 13-character access codes. | Critical | **MITIGATED** | 44.6 bits of entropy combined with keyed `HMAC-SHA256(CODE_PEPPER, code)`. Enforces dual-layer rate limiting: 5 failed attempts per code/hour; 10 failed attempts per IP/15 minutes. |
| **Checksum False Positives** | Keyboard input confusion passing Luhn/checksum checks. | Medium | **MITIGATED** | Alphabet excludes ambiguous symbols (`I`, `L`, `O`, `Z`). Check character represents a position-weighted modulo-31 checksum over exactly 31 distinct characters. |

---

### 2.3 Financial Accounting & Ledger Integrity

| Risk Scenario | Impact | Severity | Status | Mitigation & Architectural Defense |
| :--- | :--- | :--- | :--- | :--- |
| **Post-Payment Chapter Withdrawal**| Chapter demands refund post-check reconciliation. | High | **MITIGATED** | Strict non-refund policy. Chapter status transitions to `withdrawn`; historical ledger entries and receipts remain intact for financial audit compliance. |
| **Post-Payment Attendee Drop** | Delegate cancels attendance after school check has cleared. | Medium | **MITIGATED** | System assigns three-state status: `active`, `cancelled`, and `cancelled_paid`. Cancellations post-payment convert to `cancelled_paid`, excluding attendees from meal planning while preserving billable totals so accounting balances remain settled. |
| **Negative Invoice / Surcharges** | Excessive or negative discount entries distorting balances. | Medium | **MITIGATED** | `schools.discount_cents` enforces `CHECK (discount_cents >= 0)`. The invoice calculation engine floors net obligations at zero cents (`MAX(0, total)`). |
| **Unintended Free-Adult Fluctuations**| Cancelling a delegate increases chapter balance unexpectedly. | Low | **ACCEPTED** | Complimentary adult ratios are calculated via $\lceil\text{delegates} / 10\rceil$. Cancelling the 1st, 11th, or 21st delegate removes an adult waiver. UI explicitly itemizes the adult allowance calculation on the invoice to eliminate confusion. |

---

### 2.4 Timezone, Scheduling & Deadlines

| Risk Scenario | Impact | Severity | Status | Mitigation & Architectural Defense |
| :--- | :--- | :--- | :--- | :--- |
| **Premature Deadline Lockout** | System locks forms at 00:00 UTC instead of 23:59:59 Pacific Time. | Critical | **MITIGATED** | Administrative dashboard accepts wall-clock California dates and internally computes deterministic UTC timestamps via `America/Los_Angeles` timezone parsing (accounting automatically for PST/PDT shifts). |
| **In-Flight Deadline Rejection** | Submissions in progress rejected at the exact second of deadline lock. | Medium | **PARTIAL** | Requests crossing the deadline are currently rejected. Administrative override exists via individual **Reopen Form** controls. |
| **Abandoned Administrative Impersonation**| Admin forgets open impersonation session on support terminal. | High | **MITIGATED** | Impersonation tokens enforce a strict 30-minute expiration, default to read-only mode, display persistent UI warning banners, and record dual-identity audit trails. |

---

### 2.5 Infrastructure, Resource Limits & Performance

| Risk Scenario | Impact | Severity | Status | Mitigation & Architectural Defense |
| :--- | :--- | :--- | :--- | :--- |
| **Turso Monthly Read Quota Exhaustion**| Unindexed query scans exhausting free tier (500M reads/mo), triggering service block. | Critical | **MITIGATED** | All queries declared in `backend/queries/*.sql`. CI validates query plans with `EXPLAIN QUERY PLAN`, blocking full table scans. Aggregates are cached transactional single-row counters. Public homepage statistics are baked at build time. |
| **Modal Container Cold-Start Latency**| First request after idle takes 5–8 seconds, degrading UX. | Medium | **MITIGATED** | Implemented persistent warming scheduler: `ops.warm_until` stored in database; background worker reconciles instance warmth every 5 minutes, surviving redeployments. |
| **Backend Outage / Loss of Connectivity**| Internet failure or upstream API downtime during convention. | High | **MITIGATED** | Public pages display pre-rendered static content snapshots. Critical announcements toggleable via static `announcement.json`. Complete application operable offline via local SQLite engine. |
| **Apps Script Endpoint Drift** | Google Apps Script URL regenerates on republish, breaking Drive uploads. | Medium | **OPEN** | Apps Script URL and secret key managed via Modal Secrets. Need to implement automated health checks alerting administrators if file upload webhooks fail. |

---

### 2.6 Data Quality, Normalization & Localization

| Risk Scenario | Impact | Severity | Status | Mitigation & Architectural Defense |
| :--- | :--- | :--- | :--- | :--- |
| **International Name Corruption** | Parser mangling diacritics, compound surnames, or non-Latin tokens. | Medium | **MITIGATED** | Full Unicode normalization support (e.g., `Nguyễn Thị Minh Anh`, `Seán O'Brien`). Strip invisible formatting (BOM, zero-width spaces). Warning heuristics surface ambiguous multi-token tokens without blocking. |
| **Accidental Roster Cross-Contamination**| Transferring attendees across schools corrupting category eligibility. | High | **MITIGATED** | The platform explicitly disallows moving records across institutions. Erroneous entries are soft-cancelled in the source school and re-created in the destination school. |
| **Data Leakage in Anonymized Exports** | Free-text fields exposing treasurer or participant names. | High | **MITIGATED** | Anonymized export engine redacts all free-text prose (`settings` strings, discount reasons, announcement bodies) in addition to core identity columns. |

---

## 3. Empirical Capacity & Resource Headroom

Telemetry measurements derived via `scripts/measure_usage.py` extrapolated to a full 1,150-person convention load:

| Resource Metric | Projected Consumption | Free-Tier Allocation | Measured Safety Margin |
| :--- | :--- | :--- | :--- |
| **Database Storage** | 2.2 MB | 5,000.0 MB | **2,272× Headroom** |
| **Monthly Reads (Off-Peak)** | 434,000 | 500,000,000 | **1,152× Headroom** |
| **Monthly Reads (Convention Month)**| 1,700,000 | 500,000,000 | **294× Headroom** |
| **Monthly Row Writes** | 120,000 | 10,000,000 | **83× Headroom** |

---

## 4. Open Risk Remediation Tracking

| Risk Reference | Vulnerability Description | Severity | Target Remediation |
| :--- | :--- | :--- | :--- |
| **RISK-SEC-01** | Certamen practice arena allows PIN overrides and lacks rate limiting. | High | Implement PIN hashing and enforce authorization guards on question bank imports. |
| **RISK-OPS-01** | Google Apps Script webhook lacks automated heartbeat alerting. | Medium | Implement proactive automated monitoring on digital contest upload pipelines. |
| **RISK-SEC-02** | 180-day session lifespan on shared educational terminals. | Medium | Shorten administrative session lifespans to 72 hours alongside 2FA deployment. |
| **RISK-UI-01** | 90-character attendee names potentially overflowing printed tabula boxes. | Low | Verify print template layout boundaries against long-character stress fixtures. |
