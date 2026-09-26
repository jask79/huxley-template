"""
SQLite storage layer for Sourcerer.

Database location: monitoring/product-sourcing.db (relative to Huxley root).
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CATALYST_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = CATALYST_ROOT / "monitoring" / "product-sourcing.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _now_utc() -> str:
    """ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_json(val: Any, default: Any = None) -> Any:
    """Safely parse a JSON string, returning *default* on None or decode error."""
    if val is None:
        return default
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


def get_connection() -> sqlite3.Connection:
    """Get a connection to the Product Sourcing database, initializing if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Initialize schema if tables don't exist
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='suppliers'"
    )
    if cursor.fetchone() is None:
        schema_sql = SCHEMA_PATH.read_text()
        conn.executescript(schema_sql)

    return conn


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

def upsert_supplier(
    supplier_id: str,
    platform: str,
    name: str,
    url: str,
    name_cn: Optional[str] = None,
    location: Optional[str] = None,
    supplier_type: str = "unknown",
    gold_years: int = 0,
    trade_assurance: int = 0,
    verified: int = 0,
    response_rate: Optional[float] = None,
    transaction_count: int = 0,
    on_time_delivery: Optional[float] = None,
    employee_count: Optional[str] = None,
    year_established: Optional[int] = None,
    main_products: Optional[str] = None,
    notes: str = "",
    quality_score: Optional[float] = None,
    red_flags: Optional[List[str]] = None,
) -> bool:
    """Insert or update a supplier. Returns True if newly inserted."""
    conn = get_connection()
    try:
        flags_json = json.dumps(red_flags) if red_flags is not None else "[]"
        now = _now_utc()
        cursor = conn.execute(
            "SELECT supplier_id FROM suppliers WHERE supplier_id = ?",
            (supplier_id,),
        )
        if cursor.fetchone():
            conn.execute(
                """UPDATE suppliers SET
                    platform = ?, name = ?, name_cn = ?, url = ?,
                    location = ?, supplier_type = ?, gold_years = ?,
                    trade_assurance = ?, verified = ?, response_rate = ?,
                    transaction_count = ?, on_time_delivery = ?,
                    employee_count = ?, year_established = ?,
                    main_products = ?, notes = ?, quality_score = ?,
                    red_flags = ?, last_updated = ?
                WHERE supplier_id = ?""",
                (
                    platform, name, name_cn, url, location, supplier_type,
                    gold_years, trade_assurance, verified, response_rate,
                    transaction_count, on_time_delivery, employee_count,
                    year_established, main_products, notes, quality_score,
                    flags_json, now, supplier_id,
                ),
            )
            conn.commit()
            return False
        else:
            conn.execute(
                """INSERT INTO suppliers (
                    supplier_id, platform, name, name_cn, url, location,
                    supplier_type, gold_years, trade_assurance, verified,
                    response_rate, transaction_count, on_time_delivery,
                    employee_count, year_established, main_products,
                    notes, quality_score, red_flags, first_seen, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    supplier_id, platform, name, name_cn, url, location,
                    supplier_type, gold_years, trade_assurance, verified,
                    response_rate, transaction_count, on_time_delivery,
                    employee_count, year_established, main_products,
                    notes, quality_score, flags_json, now, now,
                ),
            )
            conn.commit()
            return True
    finally:
        conn.close()


def get_supplier(supplier_id: str) -> Optional[Dict[str, Any]]:
    """Get a single supplier by ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM suppliers WHERE supplier_id = ?", (supplier_id,)
        ).fetchone()
        if row:
            result = dict(row)
            result["red_flags"] = _safe_json(result["red_flags"], [])
            return result
        return None
    finally:
        conn.close()


def list_suppliers(
    platform: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List suppliers, optionally filtered by platform."""
    conn = get_connection()
    try:
        if platform:
            rows = conn.execute(
                """SELECT * FROM suppliers
                   WHERE platform = ?
                   ORDER BY last_updated DESC
                   LIMIT ? OFFSET ?""",
                (platform, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM suppliers
                   ORDER BY last_updated DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["red_flags"] = _safe_json(d["red_flags"], [])
            results.append(d)
        return results
    finally:
        conn.close()


def search_suppliers(
    query: str,
    platform: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Search suppliers by name or main_products (case-insensitive LIKE)."""
    conn = get_connection()
    try:
        like_pattern = f"%{query}%"
        if platform:
            rows = conn.execute(
                """SELECT * FROM suppliers
                   WHERE platform = ?
                     AND (name LIKE ? OR main_products LIKE ? OR name_cn LIKE ?)
                   ORDER BY quality_score DESC NULLS LAST
                   LIMIT ?""",
                (platform, like_pattern, like_pattern, like_pattern, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM suppliers
                   WHERE name LIKE ? OR main_products LIKE ? OR name_cn LIKE ?
                   ORDER BY quality_score DESC NULLS LAST
                   LIMIT ?""",
                (like_pattern, like_pattern, like_pattern, limit),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["red_flags"] = _safe_json(d["red_flags"], [])
            results.append(d)
        return results
    finally:
        conn.close()


def update_supplier_score(
    supplier_id: str, quality_score: float
) -> bool:
    """Update a supplier's quality score. Returns True if supplier exists."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """UPDATE suppliers SET quality_score = ?, last_updated = ?
               WHERE supplier_id = ?""",
            (quality_score, _now_utc(), supplier_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def upsert_product(
    supplier_id: str,
    platform: str,
    url: str,
    title: str,
    title_cn: Optional[str] = None,
    category: Optional[str] = None,
    hs_code: Optional[str] = None,
    moq: Optional[int] = None,
    moq_unit: str = "pieces",
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    price_currency: str = "USD",
    customization: str = "unknown",
    sample_price: Optional[float] = None,
    sample_available: int = 1,
    lead_time_days: Optional[int] = None,
    image_urls: Optional[List[str]] = None,
    specs: Optional[Dict[str, Any]] = None,
    notes: str = "",
    product_id: Optional[int] = None,
) -> int:
    """Insert or update a product. Returns the product_id."""
    conn = get_connection()
    try:
        imgs_json = json.dumps(image_urls) if image_urls is not None else "[]"
        specs_json = json.dumps(specs) if specs is not None else "{}"
        now = _now_utc()

        if product_id is not None:
            conn.execute(
                """UPDATE products SET
                    supplier_id = ?, platform = ?, url = ?, title = ?,
                    title_cn = ?, category = ?, hs_code = ?, moq = ?,
                    moq_unit = ?, price_min = ?, price_max = ?,
                    price_currency = ?, customization = ?, sample_price = ?,
                    sample_available = ?, lead_time_days = ?, image_urls = ?,
                    specs = ?, notes = ?, last_updated = ?
                WHERE product_id = ?""",
                (
                    supplier_id, platform, url, title, title_cn, category,
                    hs_code, moq, moq_unit, price_min, price_max,
                    price_currency, customization, sample_price,
                    sample_available, lead_time_days, imgs_json, specs_json,
                    notes, now, product_id,
                ),
            )
            conn.commit()
            return product_id
        else:
            cursor = conn.execute(
                """INSERT INTO products (
                    supplier_id, platform, url, title, title_cn, category,
                    hs_code, moq, moq_unit, price_min, price_max,
                    price_currency, customization, sample_price,
                    sample_available, lead_time_days, image_urls, specs,
                    notes, first_seen, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    supplier_id, platform, url, title, title_cn, category,
                    hs_code, moq, moq_unit, price_min, price_max,
                    price_currency, customization, sample_price,
                    sample_available, lead_time_days, imgs_json, specs_json,
                    notes, now, now,
                ),
            )
            conn.commit()
            return cursor.lastrowid
    finally:
        conn.close()


def get_product(product_id: int) -> Optional[Dict[str, Any]]:
    """Get a single product by ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
        if row:
            result = dict(row)
            result["image_urls"] = _safe_json(result["image_urls"], [])
            result["specs"] = _safe_json(result["specs"], {})
            return result
        return None
    finally:
        conn.close()


def list_products_by_supplier(
    supplier_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """List all products from a given supplier."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM products
               WHERE supplier_id = ?
               ORDER BY last_updated DESC
               LIMIT ?""",
            (supplier_id, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["image_urls"] = _safe_json(d["image_urls"], [])
            d["specs"] = _safe_json(d["specs"], {})
            results.append(d)
        return results
    finally:
        conn.close()


def search_products(
    query: str,
    category: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Search products by title, category, or HS code."""
    conn = get_connection()
    try:
        like_pattern = f"%{query}%"
        conditions = ["(title LIKE ? OR title_cn LIKE ? OR hs_code LIKE ?)"]
        params: List[Any] = [like_pattern, like_pattern, like_pattern]

        if category:
            conditions.append("category = ?")
            params.append(category)
        if platform:
            conditions.append("platform = ?")
            params.append(platform)

        params.append(limit)
        where = " AND ".join(conditions)
        rows = conn.execute(
            f"""SELECT * FROM products
                WHERE {where}
                ORDER BY last_updated DESC
                LIMIT ?""",
            params,
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["image_urls"] = _safe_json(d["image_urls"], [])
            d["specs"] = _safe_json(d["specs"], {})
            results.append(d)
        return results
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Price Snapshots
# ---------------------------------------------------------------------------

def add_price_snapshot(
    product_id: int,
    price_min: float,
    price_max: float,
    price_currency: str = "USD",
    moq: Optional[int] = None,
    exchange_rate: Optional[float] = None,
) -> None:
    """Record a price snapshot for a product."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO price_snapshots
               (product_id, price_min, price_max, price_currency, moq, exchange_rate)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (product_id, price_min, price_max, price_currency, moq, exchange_rate),
        )
        conn.commit()
    finally:
        conn.close()


def get_price_history(
    product_id: int, limit: int = 90
) -> List[Dict[str, Any]]:
    """Get recent price snapshots for a product (default: last 90 entries)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT price_min, price_max, price_currency, moq,
                      exchange_rate, snapshot_time
               FROM price_snapshots
               WHERE product_id = ?
               ORDER BY snapshot_time DESC
               LIMIT ?""",
            (product_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Search History
# ---------------------------------------------------------------------------

def log_search(
    query: str,
    platform: str,
    result_count: int = 0,
    query_cn: Optional[str] = None,
    top_results: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Log a search query and its results."""
    conn = get_connection()
    try:
        results_json = json.dumps(top_results) if top_results is not None else "[]"
        conn.execute(
            """INSERT INTO search_history
               (query, query_cn, platform, result_count, top_results)
               VALUES (?, ?, ?, ?, ?)""",
            (query, query_cn, platform, result_count, results_json),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_searches(
    platform: Optional[str] = None, limit: int = 20
) -> List[Dict[str, Any]]:
    """Get recent search history, optionally filtered by platform."""
    conn = get_connection()
    try:
        if platform:
            rows = conn.execute(
                """SELECT * FROM search_history
                   WHERE platform = ?
                   ORDER BY searched_at DESC
                   LIMIT ?""",
                (platform, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM search_history
                   ORDER BY searched_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["top_results"] = _safe_json(d["top_results"], [])
            results.append(d)
        return results
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# RFQs (Request for Quotation)
# ---------------------------------------------------------------------------

def create_rfq(
    supplier_id: str,
    description: str,
    product_id: Optional[int] = None,
    quantity: Optional[int] = None,
    target_price: Optional[float] = None,
    notes: str = "",
) -> int:
    """Create a new RFQ. Returns the rfq_id."""
    conn = get_connection()
    try:
        now = _now_utc()
        cursor = conn.execute(
            """INSERT INTO rfqs (
                supplier_id, product_id, description, quantity,
                target_price, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (supplier_id, product_id, description, quantity, target_price,
             notes, now, now),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_rfq(
    rfq_id: int,
    status: Optional[str] = None,
    supplier_quote: Optional[float] = None,
    quote_currency: Optional[str] = None,
    quote_moq: Optional[int] = None,
    lead_time_quoted: Optional[int] = None,
    sample_requested: Optional[int] = None,
    sample_cost: Optional[float] = None,
    notes: Optional[str] = None,
) -> bool:
    """Update an existing RFQ. Returns True if found and updated."""
    conn = get_connection()
    try:
        # Build dynamic SET clause from non-None values
        updates: List[str] = []
        params: List[Any] = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if supplier_quote is not None:
            updates.append("supplier_quote = ?")
            params.append(supplier_quote)
        if quote_currency is not None:
            updates.append("quote_currency = ?")
            params.append(quote_currency)
        if quote_moq is not None:
            updates.append("quote_moq = ?")
            params.append(quote_moq)
        if lead_time_quoted is not None:
            updates.append("lead_time_quoted = ?")
            params.append(lead_time_quoted)
        if sample_requested is not None:
            updates.append("sample_requested = ?")
            params.append(sample_requested)
        if sample_cost is not None:
            updates.append("sample_cost = ?")
            params.append(sample_cost)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(_now_utc())
        params.append(rfq_id)

        set_clause = ", ".join(updates)
        cursor = conn.execute(
            f"UPDATE rfqs SET {set_clause} WHERE rfq_id = ?",
            params,
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def list_rfqs(
    status: Optional[str] = None,
    supplier_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List RFQs, optionally filtered by status or supplier."""
    conn = get_connection()
    try:
        conditions: List[str] = []
        params: List[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if supplier_id:
            conditions.append("supplier_id = ?")
            params.append(supplier_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        rows = conn.execute(
            f"""SELECT * FROM rfqs
                {where}
                ORDER BY updated_at DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_rfq(rfq_id: int) -> Optional[Dict[str, Any]]:
    """Get a single RFQ by ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM rfqs WHERE rfq_id = ?", (rfq_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Supplier Scores
# ---------------------------------------------------------------------------

def log_score(
    supplier_id: str,
    overall_score: float,
    breakdown: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a supplier score snapshot."""
    conn = get_connection()
    try:
        breakdown_json = json.dumps(breakdown) if breakdown is not None else "{}"
        conn.execute(
            """INSERT INTO supplier_scores (supplier_id, overall_score, breakdown)
               VALUES (?, ?, ?)""",
            (supplier_id, overall_score, breakdown_json),
        )
        conn.commit()
    finally:
        conn.close()


def get_score_history(
    supplier_id: str, limit: int = 20
) -> List[Dict[str, Any]]:
    """Get score history for a supplier."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT overall_score, breakdown, scored_at
               FROM supplier_scores
               WHERE supplier_id = ?
               ORDER BY scored_at DESC
               LIMIT ?""",
            (supplier_id, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["breakdown"] = _safe_json(d["breakdown"], {})
            results.append(d)
        return results
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Cost Calculations
# ---------------------------------------------------------------------------

def log_cost_calc(
    quantity: int,
    unit_cost_usd: float,
    total_landed_usd: float,
    per_unit_landed_usd: float,
    product_id: Optional[int] = None,
    hs_code: Optional[str] = None,
    duty_rate: Optional[float] = None,
    duty_amount_usd: Optional[float] = None,
    freight_mode: Optional[str] = None,
    freight_cost_usd: Optional[float] = None,
    insurance_usd: float = 0.0,
    customs_fee_usd: float = 0.0,
    margin_at_price: Optional[float] = None,
    notes: str = "",
) -> int:
    """Log a landed cost calculation. Returns the record ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO cost_calculations (
                product_id, quantity, unit_cost_usd, hs_code, duty_rate,
                duty_amount_usd, freight_mode, freight_cost_usd,
                insurance_usd, customs_fee_usd, total_landed_usd,
                per_unit_landed_usd, margin_at_price, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                product_id, quantity, unit_cost_usd, hs_code, duty_rate,
                duty_amount_usd, freight_mode, freight_cost_usd,
                insurance_usd, customs_fee_usd, total_landed_usd,
                per_unit_landed_usd, margin_at_price, notes,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_cost_history(
    product_id: int, limit: int = 20
) -> List[Dict[str, Any]]:
    """Get cost calculation history for a product."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM cost_calculations
               WHERE product_id = ?
               ORDER BY calculated_at DESC
               LIMIT ?""",
            (product_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Exchange Rates
# ---------------------------------------------------------------------------

def get_exchange_rate(pair: str) -> Optional[Dict[str, Any]]:
    """Get a cached exchange rate by pair (e.g. 'CNY_USD')."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM exchange_rates WHERE pair = ?", (pair,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_exchange_rate(pair: str, rate: float) -> None:
    """Insert or update a cached exchange rate."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO exchange_rates (pair, rate, fetched_at)
               VALUES (?, ?, ?)
               ON CONFLICT(pair) DO UPDATE SET
                   rate = excluded.rate,
                   fetched_at = excluded.fetched_at""",
            (pair, rate, _now_utc()),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Supplier Communications
# ---------------------------------------------------------------------------

def log_communication(
    supplier_id: str,
    content: str,
    direction: str = "outbound",
    channel: str = "alibaba",
    rfq_id: Optional[int] = None,
    subject: Optional[str] = None,
    attachments: Optional[List[str]] = None,
) -> int:
    """Log a supplier communication. Returns the record ID."""
    conn = get_connection()
    try:
        attach_json = json.dumps(attachments) if attachments is not None else "[]"
        cursor = conn.execute(
            """INSERT INTO supplier_communications
               (supplier_id, rfq_id, direction, channel, subject, content, attachments)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (supplier_id, rfq_id, direction, channel, subject, content, attach_json),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_communications(
    supplier_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """Get communication history for a supplier."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM supplier_communications
               WHERE supplier_id = ?
               ORDER BY sent_at DESC
               LIMIT ?""",
            (supplier_id, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["attachments"] = _safe_json(d["attachments"], [])
            results.append(d)
        return results
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Compliance Checks
# ---------------------------------------------------------------------------

def log_compliance_check(
    product_id: int,
    category: str,
    requirement: str,
    agency: Optional[str] = None,
    status: str = "unknown",
    estimated_cost: Optional[float] = None,
    notes: str = "",
) -> int:
    """Log a compliance check. Returns the record ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO compliance_checks
               (product_id, category, requirement, agency, status, estimated_cost, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (product_id, category, requirement, agency, status, estimated_cost, notes),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_compliance_checks(product_id: int) -> List[Dict[str, Any]]:
    """Get compliance checks for a product."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM compliance_checks
               WHERE product_id = ?
               ORDER BY checked_at DESC""",
            (product_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_compliance_status(
    check_id: int,
    status: str,
    actual_cost: Optional[float] = None,
    notes: Optional[str] = None,
) -> bool:
    """Update a compliance check status. Returns True if found and updated."""
    conn = get_connection()
    try:
        updates: List[str] = ["status = ?", "updated_at = ?"]
        params: List[Any] = [status, _now_utc()]

        if actual_cost is not None:
            updates.append("actual_cost = ?")
            params.append(actual_cost)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        params.append(check_id)
        set_clause = ", ".join(updates)
        cursor = conn.execute(
            f"UPDATE compliance_checks SET {set_clause} WHERE id = ?",
            params,
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Risk Assessments
# ---------------------------------------------------------------------------

def log_risk_assessment(
    supplier_id: str,
    overall_risk: float,
    breakdown: Dict[str, Any],
    recommendations: Optional[List[str]] = None,
    concentration_risk: Optional[float] = None,
    geographic_risk: Optional[float] = None,
    financial_risk: Optional[float] = None,
    quality_risk: Optional[float] = None,
    lead_time_risk: Optional[float] = None,
    compliance_risk: Optional[float] = None,
) -> int:
    """Log a risk assessment. Returns the record ID."""
    conn = get_connection()
    try:
        breakdown_json = json.dumps(breakdown) if breakdown else "{}"
        recs_json = json.dumps(recommendations) if recommendations else "[]"
        cursor = conn.execute(
            """INSERT INTO risk_assessments
               (supplier_id, overall_risk, concentration_risk, geographic_risk,
                financial_risk, quality_risk, lead_time_risk, compliance_risk,
                breakdown, recommendations)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                supplier_id, overall_risk, concentration_risk, geographic_risk,
                financial_risk, quality_risk, lead_time_risk, compliance_risk,
                breakdown_json, recs_json,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_risk_assessments(
    supplier_id: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """Get risk assessment history for a supplier."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM risk_assessments
               WHERE supplier_id = ?
               ORDER BY assessed_at DESC
               LIMIT ?""",
            (supplier_id, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["breakdown"] = _safe_json(d["breakdown"], {})
            d["recommendations"] = _safe_json(d["recommendations"], [])
            results.append(d)
        return results
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Price Alerts
# ---------------------------------------------------------------------------

def create_alert(
    product_id: Optional[int] = None,
    supplier_id: Optional[str] = None,
    alert_type: str = "price",
    condition_desc: str = "",
    threshold: Optional[float] = None,
) -> int:
    """Create a price/score alert. Returns the alert ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO price_alerts
               (product_id, supplier_id, alert_type, condition_desc, threshold)
               VALUES (?, ?, ?, ?, ?)""",
            (product_id, supplier_id, alert_type, condition_desc, threshold),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def list_alerts(active_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
    """List alerts, optionally filtered to active only."""
    conn = get_connection()
    try:
        if active_only:
            rows = conn.execute(
                """SELECT * FROM price_alerts
                   WHERE active = 1
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM price_alerts
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_active_alerts() -> List[Dict[str, Any]]:
    """Get all active alerts. Convenience wrapper around list_alerts."""
    return list_alerts(active_only=True)


def trigger_alert(alert_id: int) -> bool:
    """Mark an alert as triggered. Returns True if found and updated."""
    conn = get_connection()
    try:
        now = _now_utc()
        cursor = conn.execute(
            """UPDATE price_alerts
               SET last_triggered = ?, last_checked = ?,
                   trigger_count = trigger_count + 1
               WHERE id = ? AND active = 1""",
            (now, now, alert_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def deactivate_alert(alert_id: int) -> bool:
    """Deactivate an alert. Returns True if found and updated."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE price_alerts SET active = 0 WHERE id = ?",
            (alert_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
