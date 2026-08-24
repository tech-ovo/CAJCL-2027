-- 003_money_audit.sql -- payments, the two counter caches, the audit log,
-- roster imports, announcements, and editable prose.

-- ---------------------------------------------------------------------------
-- payments
-- ---------------------------------------------------------------------------
-- Append-only. A correction is a NEW row, possibly negative, never an edit.
-- The payment history and the audit log together are the record, and when a
-- sponsor disputes a balance in March that history is the whole answer.
--
-- All money is INTEGER cents. Never a float, anywhere, for any reason.
CREATE TABLE payments (
  id                    INTEGER PRIMARY KEY,
  school_id             INTEGER NOT NULL REFERENCES schools(id),
  amount_cents          INTEGER NOT NULL,
  method                TEXT CHECK (method IN ('check','other')),
  reference             TEXT,          -- check number
  received_on           TEXT,          -- calendar date, not a timestamp
  note                  TEXT,
  recorded_by_person_id INTEGER NOT NULL REFERENCES people(id),
  created_at            TEXT NOT NULL
);
CREATE INDEX idx_payments_school ON payments (school_id, created_at);

-- ---------------------------------------------------------------------------
-- counter caches
-- ---------------------------------------------------------------------------
-- Aggregates are NEVER computed live. Both tables below are updated inside the
-- same transaction as the mutation that changes them.
--
-- The arithmetic that makes this non-negotiable: COUNT(*) over `people` at full
-- size costs ~1,150 row reads. The welcome page is unauthenticated and reachable
-- by crawlers; 100,000 hits computed live is 115 million reads against a
-- 500M/month quota. Served from public_stats_cache it is one read per hit.
-- Exceeding the quota is not a bill, it is a BLOCKED error and an outage you
-- cannot buy your way out of during convention.
-- The `_cancelled_paid` columns are what make "no refunds" arithmetic rather
-- than policy: someone who withdrew after their chapter paid still counts
-- toward the amount owed, so the balance reads zero instead of showing a credit
-- nobody intends to pay back.
CREATE TABLE school_stats (
  school_id                INTEGER PRIMARY KEY REFERENCES schools(id),
  delegates_active         INTEGER NOT NULL DEFAULT 0,
  delegates_cancelled      INTEGER NOT NULL DEFAULT 0,
  delegates_cancelled_paid INTEGER NOT NULL DEFAULT 0,
  adults_active            INTEGER NOT NULL DEFAULT 0,
  adults_cancelled         INTEGER NOT NULL DEFAULT 0,
  adults_cancelled_paid    INTEGER NOT NULL DEFAULT 0,
  delegates_complete       INTEGER NOT NULL DEFAULT 0,
  adults_complete          INTEGER NOT NULL DEFAULT 0,
  -- Snapshotted from schools.discount_cents at recompute time so the invoice
  -- page can show the discount as its own line without a second lookup.
  discount_cents           INTEGER NOT NULL DEFAULT 0,
  amount_owed_cents        INTEGER NOT NULL DEFAULT 0,
  amount_paid_cents        INTEGER NOT NULL DEFAULT 0,
  updated_at               TEXT NOT NULL
);

-- Exactly one row, forever. The CHECK is what guarantees that.
CREATE TABLE public_stats_cache (
  id         INTEGER PRIMARY KEY CHECK (id = 1),
  schools_ms INTEGER NOT NULL,
  schools_hs INTEGER NOT NULL,
  delegates  INTEGER NOT NULL,
  adults     INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- audit_log
-- ---------------------------------------------------------------------------
-- Append-only, enforced by trigger rather than by convention. Written in the
-- SAME transaction as the mutation it describes: if the mutation rolls back, so
-- does its log entry, and there is no code path that changes data without
-- writing one.
--
-- This table is also the disaster-recovery story. If the current-state tables
-- are destroyed by a bad migration or a deletion, restoring the most recent
-- export and replaying this log reconstructs the sequence of changes since.
CREATE TABLE audit_log (
  id                     INTEGER PRIMARY KEY,
  ts_utc                 TEXT NOT NULL,
  actor_person_id        INTEGER REFERENCES people(id),   -- NULL for system actions
  actor_role_snapshot    TEXT,                            -- roles at the moment of the action
  impersonator_person_id INTEGER REFERENCES people(id),
  action                 TEXT NOT NULL,
  entity_type            TEXT,
  entity_id              INTEGER,
  school_id              INTEGER REFERENCES schools(id),  -- denormalized so filtering is indexed
  -- A complete human-readable sentence, rendered at insert time:
  -- "Rosalind Ferraro added 28 delegates to University High School."
  -- A future commissioner reads this log with no access to the source.
  summary                TEXT NOT NULL,
  -- Field NAMES only, never values. This keeps PII out of the log: the log says
  -- "Bob updated their activity sheet", not what Bob chose.
  changed_fields         TEXT,                            -- JSON array of names
  -- The one exception. Payments carry before/after values, because money
  -- disputes are exactly when you need them.
  value_detail           TEXT,                            -- JSON, payment.record only
  request_id             TEXT,
  ip_hash                TEXT
);
CREATE INDEX idx_audit_ts     ON audit_log (ts_utc);
CREATE INDEX idx_audit_school ON audit_log (school_id, ts_utc);
CREATE INDEX idx_audit_actor  ON audit_log (actor_person_id, ts_utc);
CREATE INDEX idx_audit_entity ON audit_log (entity_type, entity_id);

CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;

-- ---------------------------------------------------------------------------
-- roster_imports
-- ---------------------------------------------------------------------------
-- Written only on COMMIT, never on preview. Preview parses and returns; it
-- touches no table.
--
-- The idempotency key is issued with the preview as an HMAC-signed token
-- carrying the school, a hash of the pasted text, and a timestamp -- so an
-- abandoned preview costs nothing and leaves nothing behind. On commit the key
-- is stored here, and the UNIQUE constraint is what makes a double-click, a
-- flaky connection, or an impatient refresh harmless: the second commit finds
-- the row and returns the first commit's result instead of importing again.
--
-- A sponsor accidentally creating their roster twice is the single most
-- damaging thing available to them, and this constraint is what prevents it.
CREATE TABLE roster_imports (
  id              INTEGER PRIMARY KEY,
  school_id       INTEGER NOT NULL REFERENCES schools(id),
  actor_person_id INTEGER NOT NULL REFERENCES people(id),
  idempotency_key TEXT NOT NULL UNIQUE,
  raw_text        TEXT NOT NULL,       -- what was pasted, for audit
  parsed_count    INTEGER NOT NULL,
  committed_count INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- announcements and documents
-- ---------------------------------------------------------------------------
-- For a schedule change, a room change, or a pig on campus: an admin must be
-- able to put a banner on every page in under a minute without touching code.
-- frontend/public/announcement.json is the second layer, editable from the
-- GitHub web UI so a banner can still be published with Modal completely down.
-- The live value overrides the static one whenever the API is reachable.
CREATE TABLE announcements (
  id         INTEGER PRIMARY KEY,
  body_md    TEXT NOT NULL,
  level      TEXT NOT NULL CHECK (level IN ('info','warning','critical')),
  active     INTEGER NOT NULL DEFAULT 0,
  starts_at  TEXT,
  ends_at    TEXT,
  created_by INTEGER REFERENCES people(id),
  created_at TEXT NOT NULL
);
CREATE INDEX idx_announcements_active ON announcements (active, starts_at);

-- Every block of printed or displayed prose an admin might want to reword --
-- the packet instructions above all -- so changing wording never needs a deploy.
CREATE TABLE documents (
  id         INTEGER PRIMARY KEY,
  key        TEXT NOT NULL UNIQUE,   -- 'packet_instructions', 'invoice_terms', ...
  title      TEXT NOT NULL,
  body_md    TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by INTEGER REFERENCES people(id)
);
