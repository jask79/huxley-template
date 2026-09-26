-- Sourcerer — SQLite Schema
-- Database: monitoring/product-sourcing.db

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id     TEXT PRIMARY KEY,
    platform        TEXT NOT NULL,
    name            TEXT NOT NULL,
    name_cn         TEXT,
    url             TEXT NOT NULL,
    location        TEXT,
    supplier_type   TEXT DEFAULT 'unknown',
    gold_years      INTEGER DEFAULT 0,
    trade_assurance INTEGER DEFAULT 0,
    verified        INTEGER DEFAULT 0,
    response_rate   REAL,
    transaction_count INTEGER DEFAULT 0,
    on_time_delivery REAL,
    employee_count  TEXT,
    year_established INTEGER,
    main_products   TEXT,
    notes           TEXT DEFAULT '',
    quality_score   REAL,
    red_flags       TEXT DEFAULT '[]',
    first_seen      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_updated    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_suppliers_platform ON suppliers(platform);
CREATE INDEX IF NOT EXISTS idx_suppliers_quality ON suppliers(quality_score DESC);

CREATE TABLE IF NOT EXISTS products (
    product_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id     TEXT NOT NULL REFERENCES suppliers(supplier_id),
    platform        TEXT NOT NULL,
    url             TEXT NOT NULL,
    title           TEXT NOT NULL,
    title_cn        TEXT,
    category        TEXT,
    hs_code         TEXT,
    moq             INTEGER,
    moq_unit        TEXT DEFAULT 'pieces',
    price_min       REAL,
    price_max       REAL,
    price_currency  TEXT DEFAULT 'USD',
    customization   TEXT DEFAULT 'unknown',
    sample_price    REAL,
    sample_available INTEGER DEFAULT 1,
    lead_time_days  INTEGER,
    image_urls      TEXT DEFAULT '[]',
    specs           TEXT DEFAULT '{}',
    notes           TEXT DEFAULT '',
    first_seen      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_updated    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_hs_code ON products(hs_code);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(product_id),
    price_min       REAL NOT NULL,
    price_max       REAL NOT NULL,
    price_currency  TEXT NOT NULL DEFAULT 'USD',
    moq             INTEGER,
    exchange_rate   REAL,
    snapshot_time   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_price_snap_product_time ON price_snapshots(product_id, snapshot_time DESC);

CREATE TABLE IF NOT EXISTS search_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    query           TEXT NOT NULL,
    query_cn        TEXT,
    platform        TEXT NOT NULL,
    result_count    INTEGER DEFAULT 0,
    top_results     TEXT DEFAULT '[]',
    searched_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_search_query ON search_history(query, platform);

CREATE TABLE IF NOT EXISTS rfqs (
    rfq_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id     TEXT NOT NULL REFERENCES suppliers(supplier_id),
    product_id      INTEGER REFERENCES products(product_id),
    status          TEXT NOT NULL DEFAULT 'draft',
    description     TEXT NOT NULL,
    quantity        INTEGER,
    target_price    REAL,
    supplier_quote  REAL,
    quote_currency  TEXT DEFAULT 'USD',
    quote_moq       INTEGER,
    lead_time_quoted INTEGER,
    sample_requested INTEGER DEFAULT 0,
    sample_cost     REAL,
    notes           TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_rfqs_supplier ON rfqs(supplier_id);
CREATE INDEX IF NOT EXISTS idx_rfqs_status ON rfqs(status);

CREATE TABLE IF NOT EXISTS supplier_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id     TEXT NOT NULL REFERENCES suppliers(supplier_id),
    overall_score   REAL NOT NULL,
    breakdown       TEXT NOT NULL DEFAULT '{}',
    scored_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_scores_supplier_time ON supplier_scores(supplier_id, scored_at DESC);

CREATE TABLE IF NOT EXISTS cost_calculations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER REFERENCES products(product_id),
    quantity        INTEGER NOT NULL,
    unit_cost_usd   REAL NOT NULL,
    hs_code         TEXT,
    duty_rate       REAL,
    duty_amount_usd REAL,
    freight_mode    TEXT,
    freight_cost_usd REAL,
    insurance_usd   REAL DEFAULT 0.0,
    customs_fee_usd REAL DEFAULT 0.0,
    total_landed_usd REAL NOT NULL,
    per_unit_landed_usd REAL NOT NULL,
    margin_at_price REAL,
    notes           TEXT DEFAULT '',
    calculated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_cost_product ON cost_calculations(product_id);

CREATE TABLE IF NOT EXISTS exchange_rates (
    pair            TEXT PRIMARY KEY,
    rate            REAL NOT NULL,
    fetched_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Communication log for supplier interactions
CREATE TABLE IF NOT EXISTS supplier_communications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id     TEXT NOT NULL REFERENCES suppliers(supplier_id),
    rfq_id          INTEGER REFERENCES rfqs(rfq_id),
    direction       TEXT NOT NULL DEFAULT 'outbound',
    channel         TEXT DEFAULT 'alibaba',
    subject         TEXT,
    content         TEXT NOT NULL,
    attachments     TEXT DEFAULT '[]',
    sent_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_comms_supplier ON supplier_communications(supplier_id);
CREATE INDEX IF NOT EXISTS idx_comms_rfq ON supplier_communications(rfq_id);

-- Compliance tracking per product
CREATE TABLE IF NOT EXISTS compliance_checks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER REFERENCES products(product_id),
    category        TEXT NOT NULL,
    requirement     TEXT NOT NULL,
    agency          TEXT,
    status          TEXT NOT NULL DEFAULT 'unknown',
    estimated_cost  REAL,
    actual_cost     REAL,
    notes           TEXT DEFAULT '',
    checked_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_compliance_product ON compliance_checks(product_id);
CREATE INDEX IF NOT EXISTS idx_compliance_status ON compliance_checks(status);

-- Supply chain risk assessments
CREATE TABLE IF NOT EXISTS risk_assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id     TEXT NOT NULL REFERENCES suppliers(supplier_id),
    overall_risk    REAL NOT NULL,
    concentration_risk REAL,
    geographic_risk REAL,
    financial_risk  REAL,
    quality_risk    REAL,
    lead_time_risk  REAL,
    compliance_risk REAL,
    breakdown       TEXT NOT NULL DEFAULT '{}',
    recommendations TEXT DEFAULT '[]',
    assessed_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_risk_supplier ON risk_assessments(supplier_id);

-- Price and score alerts
CREATE TABLE IF NOT EXISTS price_alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER REFERENCES products(product_id),
    supplier_id     TEXT REFERENCES suppliers(supplier_id),
    alert_type      TEXT NOT NULL DEFAULT 'price',
    condition_desc  TEXT NOT NULL,
    threshold       REAL,
    active          INTEGER DEFAULT 1,
    last_checked    TEXT,
    last_triggered  TEXT,
    trigger_count   INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_active ON price_alerts(active);
