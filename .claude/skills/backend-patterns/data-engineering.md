# Data Engineering & Analytics Patterns

ETL/ELT pipelines, data warehouses, streaming architectures, and ML pipeline integration.

## ETL/ELT Pipeline Design

### Extract-Transform-Load (ETL) Pattern

```python
from datetime import datetime, timedelta

class DataPipeline:
    def __init__(self, source_db, target_warehouse):
        self.source = source_db
        self.warehouse = target_warehouse

    async def extract(self, source_query, batch_size=1000):
        """Extract data from source in batches

        Note: batch_size and offset are safe internal integers.
        source_query should be validated before passing to this method.
        """
        offset = 0
        while True:
            batch = await self.source.fetch_all(
                f"{source_query} LIMIT {batch_size} OFFSET {offset}"
            )
            if not batch:
                break
            yield batch
            offset += batch_size

    def transform(self, raw_data):
        """Apply business logic transformations"""
        transformed = []
        for record in raw_data:
            order_count = len(record['orders'])
            transformed.append({
                'customer_id': record['id'],
                'total_spent': float(record['total']),
                'order_count': order_count,
                'avg_order_value': float(record['total']) / order_count if order_count > 0 else 0,
                'first_order_date': record['created_at'],
                'customer_lifetime_days': (datetime.now() - record['created_at']).days,
                'is_active': record['last_order_date'] > datetime.now() - timedelta(days=90)
            })
        return transformed

    async def load(self, transformed_data, table_name):
        """Load transformed data into warehouse"""
        async with self.warehouse.transaction():
            await self.warehouse.copy_records_to_table(
                table_name,
                transformed_data,
                on_conflict='update'
            )

    async def run_pipeline(self, source_query, target_table):
        """Execute complete ETL pipeline"""
        async for batch in self.extract(source_query):
            transformed = self.transform(batch)
            await self.load(transformed, target_table)
```

### ELT Pattern (Modern Data Warehouses)

- Load raw data first, transform in warehouse using SQL/dbt
- Leverage warehouse compute power for transformations
- Enable multiple transformation views from same raw data

---

## Data Warehouse Architecture

### Star Schema Design

```sql
-- Fact table (measures/metrics)
CREATE TABLE fact_sales (
    sale_id BIGSERIAL PRIMARY KEY,
    date_key INTEGER REFERENCES dim_date(date_key),
    product_key INTEGER REFERENCES dim_product(product_key),
    customer_key INTEGER REFERENCES dim_customer(customer_key),
    store_key INTEGER REFERENCES dim_store(store_key),

    quantity INTEGER,
    unit_price DECIMAL(10,2),
    total_amount DECIMAL(12,2),
    discount_amount DECIMAL(10,2),
    tax_amount DECIMAL(10,2)
);

-- Dimension tables (context/attributes)
CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE,
    day_of_week VARCHAR(10),
    month INTEGER,
    quarter INTEGER,
    year INTEGER,
    is_weekend BOOLEAN,
    is_holiday BOOLEAN
);

CREATE TABLE dim_product (
    product_key SERIAL PRIMARY KEY,
    product_id VARCHAR(50),
    product_name VARCHAR(200),
    category VARCHAR(100),
    subcategory VARCHAR(100),
    brand VARCHAR(100),
    unit_cost DECIMAL(10,2)
);

-- Optimized for analytical queries
CREATE INDEX idx_fact_sales_date ON fact_sales(date_key);
CREATE INDEX idx_fact_sales_product ON fact_sales(product_key);
CREATE INDEX idx_fact_sales_customer ON fact_sales(customer_key);
```

---

## Streaming Data Architecture

### Real-time Event Processing

```python
from kafka import KafkaConsumer
import asyncio

class StreamProcessor:
    def __init__(self, kafka_brokers, postgres_conn):
        self.consumer = KafkaConsumer(
            'user_events',
            bootstrap_servers=kafka_brokers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        self.db = postgres_conn
        self.batch = []
        self.batch_size = 100

    async def process_events(self):
        """Process streaming events with micro-batching"""
        for message in self.consumer:
            event = message.value

            # Real-time aggregation
            await self.update_user_metrics(event)

            # Batch events for warehouse
            self.batch.append(event)

            if len(self.batch) >= self.batch_size:
                await self.flush_batch()

    async def update_user_metrics(self, event):
        """Real-time metrics update"""
        await self.db.execute("""
            INSERT INTO user_metrics (user_id, event_count, last_seen)
            VALUES (%(user_id)s, 1, %(timestamp)s)
            ON CONFLICT (user_id) DO UPDATE SET
                event_count = user_metrics.event_count + 1,
                last_seen = EXCLUDED.last_seen
        """, event)

    async def flush_batch(self):
        """Write batch to data warehouse"""
        await self.db.copy_records_to_table('event_stream', self.batch)
        self.batch = []
```

---

## Data Quality & Validation

```python
class DataQualityError(Exception):
    """Raised when data quality checks fail"""
    pass


class DataQualityChecker:
    def __init__(self, db_connection):
        self.db = db_connection

    async def check_completeness(self, table, required_columns):
        """Ensure no NULL values in critical columns"""
        for column in required_columns:
            null_count = await self.db.fetch_val(f"""
                SELECT COUNT(*) FROM {table}
                WHERE {column} IS NULL
            """)
            if null_count > 0:
                raise DataQualityError(f"{column} has {null_count} NULL values")

    async def check_uniqueness(self, table, unique_columns):
        """Verify uniqueness constraints"""
        duplicates = await self.db.fetch_val(f"""
            SELECT COUNT(*) FROM (
                SELECT {', '.join(unique_columns)}
                FROM {table}
                GROUP BY {', '.join(unique_columns)}
                HAVING COUNT(*) > 1
            ) dups
        """)
        if duplicates > 0:
            raise DataQualityError(f"Found {duplicates} duplicate rows")

    async def check_referential_integrity(self, child_table, parent_table, fk_column):
        """Verify foreign key relationships"""
        orphans = await self.db.fetch_val(f"""
            SELECT COUNT(*) FROM {child_table} c
            LEFT JOIN {parent_table} p ON c.{fk_column} = p.id
            WHERE p.id IS NULL AND c.{fk_column} IS NOT NULL
        """)
        if orphans > 0:
            raise DataQualityError(f"Found {orphans} orphaned records")
```

---

## ML Pipeline Integration

### Feature Store Pattern

```python
class FeatureStore:
    def __init__(self, db_connection):
        self.db = db_connection

    async def create_customer_features(self):
        """Generate ML features from raw data"""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS ml_customer_features AS
            SELECT
                c.customer_id,

                -- Recency features
                EXTRACT(EPOCH FROM (NOW() - MAX(o.order_date))) / 86400 AS days_since_last_order,

                -- Frequency features
                COUNT(o.order_id) AS total_orders,
                COUNT(DISTINCT DATE_TRUNC('month', o.order_date)) AS active_months,

                -- Monetary features
                SUM(o.total_amount) AS lifetime_value,
                AVG(o.total_amount) AS avg_order_value,
                STDDEV(o.total_amount) AS order_value_std,

                -- Behavioral features
                COUNT(DISTINCT o.product_category) AS product_diversity,
                AVG(o.items_per_order) AS avg_items_per_order,

                -- Time-based features
                EXTRACT(DOW FROM MIN(o.order_date)) AS first_order_day_of_week,
                COUNT(CASE WHEN EXTRACT(DOW FROM o.order_date) IN (0,6) THEN 1 END)::FLOAT /
                    NULLIF(COUNT(*), 0) AS weekend_order_ratio

            FROM customers c
            LEFT JOIN orders o ON c.customer_id = o.customer_id
            GROUP BY c.customer_id
        """)

    async def get_features_for_prediction(self, customer_ids):
        """Retrieve features for ML model inference"""
        return await self.db.fetch_all("""
            SELECT * FROM ml_customer_features
            WHERE customer_id = ANY(%(ids)s)
        """, {'ids': customer_ids})
```

### Exploratory Data Analysis (EDA) Queries

```sql
-- Distribution analysis
SELECT
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY order_value) AS q1,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY order_value) AS median,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY order_value) AS q3,
    AVG(order_value) AS mean,
    STDDEV(order_value) AS std_dev
FROM orders;

-- Correlation analysis (product co-occurrence)
SELECT
    p1.product_name AS product_a,
    p2.product_name AS product_b,
    COUNT(*) AS co_occurrence_count
FROM order_items oi1
JOIN order_items oi2 ON oi1.order_id = oi2.order_id AND oi1.product_id < oi2.product_id
JOIN products p1 ON oi1.product_id = p1.product_id
JOIN products p2 ON oi2.product_id = p2.product_id
GROUP BY p1.product_name, p2.product_name
ORDER BY co_occurrence_count DESC
LIMIT 20;

-- Time series decomposition
SELECT
    DATE_TRUNC('day', order_date) AS date,
    SUM(total_amount) AS daily_revenue,
    AVG(SUM(total_amount)) OVER (
        ORDER BY DATE_TRUNC('day', order_date)
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS ma_7day
FROM orders
GROUP BY DATE_TRUNC('day', order_date)
ORDER BY date;
```

### Model Training Pipeline

```python
class MLPipelineOrchestrator:
    def __init__(self, feature_store, model_registry):
        self.features = feature_store
        self.models = model_registry

    async def train_churn_prediction_model(self):
        """Complete ML pipeline for customer churn prediction"""
        import pandas as pd
        from sklearn.model_selection import train_test_split
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.metrics import roc_auc_score

        # 1. Extract features
        training_data = await self.features.db.fetch_all("""
            SELECT f.*, CASE WHEN c.churned_at IS NOT NULL THEN 1 ELSE 0 END AS target
            FROM ml_customer_features f
            JOIN customers c ON f.customer_id = c.customer_id
            WHERE c.created_at < NOW() - INTERVAL '3 months'
        """)

        # 2. Prepare data
        df = pd.DataFrame(training_data)
        X = df.drop(['customer_id', 'target'], axis=1)
        y = df['target']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y)

        # 3. Train model
        model = GradientBoostingClassifier(n_estimators=100, max_depth=5)
        model.fit(X_train, y_train)

        # 4. Evaluate
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_pred_proba)

        # 5. Register model
        await self.models.register_model(
            name='churn_prediction_v1',
            model=model,
            metrics={'auc': auc}
        )

        return model, auc
```
