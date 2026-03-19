-- ============================================================
-- US Healthcare EDI Parser — Hybrid DB Schema
-- SQLite DDL for persisting parsed EDI transactions
-- ============================================================

-- INTERCHANGE / ENVELOPE
CREATE TABLE IF NOT EXISTS interchanges (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name            TEXT    NOT NULL,
    transaction_type     TEXT    NOT NULL,  -- '837P','837I','835','834'
    isa_control_num      TEXT    NOT NULL,
    iea_control_num      TEXT,
    sender_id            TEXT,
    receiver_id          TEXT,
    gs_control_num       TEXT,
    ge_control_num       TEXT,
    st_control_num       TEXT,
    se_control_num       TEXT,
    se_segment_count     INTEGER,
    actual_segment_count INTEGER,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 837 CLAIMS
CREATE TABLE IF NOT EXISTS claims (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    interchange_id      INTEGER NOT NULL REFERENCES interchanges(id),
    patient_control_num TEXT,
    total_charge        REAL,
    place_of_service    TEXT,
    diagnosis_codes     TEXT,    -- JSON array from HI segments
    billing_npi         TEXT,
    rendering_npi       TEXT,
    subscriber_id       TEXT,
    loop_id             TEXT    DEFAULT '2300'
);

CREATE TABLE IF NOT EXISTS service_lines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id        INTEGER NOT NULL REFERENCES claims(id),
    interchange_id  INTEGER NOT NULL REFERENCES interchanges(id),
    procedure_code  TEXT,
    line_charge     REAL,
    units           REAL,
    date_of_service TEXT,
    loop_id         TEXT    DEFAULT '2400'
);

-- 835 REMITTANCE
CREATE TABLE IF NOT EXISTS payments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    interchange_id  INTEGER NOT NULL REFERENCES interchanges(id),
    total_payment   REAL,
    payment_method  TEXT,
    check_date      TEXT,
    trace_number    TEXT
);

CREATE TABLE IF NOT EXISTS remittance_claims (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id      INTEGER NOT NULL REFERENCES payments(id),
    interchange_id  INTEGER NOT NULL REFERENCES interchanges(id),
    claim_id_ref    TEXT,
    claim_status    TEXT,
    billed_amount   REAL,
    paid_amount     REAL,
    patient_resp    REAL,
    loop_id         TEXT    DEFAULT '2100'
);

CREATE TABLE IF NOT EXISTS adjustments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    remittance_claim_id INTEGER NOT NULL REFERENCES remittance_claims(id),
    group_code          TEXT,
    reason_code         TEXT,
    amount              REAL,
    remark_code         TEXT
);

-- 834 ENROLLMENT
CREATE TABLE IF NOT EXISTS members (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    interchange_id     INTEGER NOT NULL REFERENCES interchanges(id),
    subscriber_id      TEXT,
    ssn                TEXT,
    last_name          TEXT,
    first_name         TEXT,
    maintenance_code   TEXT,
    member_indicator   TEXT,
    insurance_type     TEXT,
    benefit_start      TEXT,
    benefit_end        TEXT,
    loop_id            TEXT    DEFAULT '2000'
);

-- VALIDATION RESULTS
CREATE TABLE IF NOT EXISTS validation_errors (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    interchange_id   INTEGER NOT NULL REFERENCES interchanges(id),
    segment_id       TEXT,
    element_position INTEGER,
    loop_id          TEXT,
    snip_level       INTEGER NOT NULL,
    severity         TEXT    DEFAULT 'error',
    code             TEXT,
    message          TEXT,
    suggestion       TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);
