# Advanced Database Architecture

Database technology selection, polyglot persistence, sharding, replicas, and monitoring.

## Database Technology Selection

### By Use Case

| Category | Technology | Use When |
|----------|------------|----------|
| **Relational** | PostgreSQL | Complex queries, JSON, vector search (pgvector) |
| | MySQL | High performance, wide ecosystem |
| | Supabase | Managed PostgreSQL + auth/storage/realtime |
| **Document** | MongoDB | Flexible schema, aggregation |
| | CouchDB | Eventual consistency, offline-first |
| **Key-Value** | Redis | Caching, sessions, pub/sub |
| | DynamoDB | Serverless, predictable performance |
| **Search** | Elasticsearch | Full-text search, analytics |
| | Meilisearch | Fast, typo-tolerant search |
| **Vector** | pgvector | PostgreSQL extension for embeddings |
| | Pinecone | Managed vector database |
| | Weaviate | Open-source with GraphQL |
| **Time-Series** | InfluxDB | Metrics, IoT data |
| | TimescaleDB | PostgreSQL extension, SQL compatible |

---

## Polyglot Persistence

Use multiple databases for different purposes:

```python
class DataLayer:
    def __init__(self):
        self.postgres = PostgreSQLConnection()      # Transactional
        self.mongodb = MongoDBConnection()          # Flexible schema
        self.redis = RedisConnection()              # Caching
        self.elasticsearch = ElasticsearchConnection()  # Search
        self.pgvector = PgVectorConnection()        # Semantic search

    async def save_order(self, order_data):
        """Save order across multiple databases"""

        # 1. PostgreSQL for transactional data
        async with self.postgres.transaction():
            order_id = await self.postgres.execute("""
                INSERT INTO orders (customer_id, total_amount, status)
                VALUES (%(customer_id)s, %(total)s, 'pending')
                RETURNING id
            """, order_data)

        # 2. Redis for cache
        await self.redis.setex(
            f"order:{order_id}",
            3600,
            json.dumps({'status': 'pending', 'total': float(order_data['total'])})
        )

        # 3. Elasticsearch for search
        await self.elasticsearch.index(
            index='orders',
            id=str(order_id),
            body={
                'order_id': str(order_id),
                'status': 'pending',
                'total_amount': float(order_data['total'])
            }
        )

        return order_id
```

---

## Horizontal Sharding

### Application-Level Sharding

```python
class ShardManager:
    def __init__(self, shard_config):
        self.shards = {}
        for shard_id, config in shard_config.items():
            self.shards[shard_id] = DatabaseConnection(config)

    def get_shard_for_customer(self, customer_id):
        """Consistent hashing for customer data distribution"""
        import hashlib
        hash_value = hashlib.md5(str(customer_id).encode()).hexdigest()
        shard_number = int(hash_value[:8], 16) % len(self.shards)
        return f"shard_{shard_number}"

    async def get_customer_orders(self, customer_id):
        """Retrieve from appropriate shard"""
        shard_key = self.get_shard_for_customer(customer_id)
        shard_db = self.shards[shard_key]

        return await shard_db.fetch_all("""
            SELECT * FROM orders
            WHERE customer_id = %(customer_id)s
            ORDER BY created_at DESC
        """, {'customer_id': customer_id})

    async def cross_shard_analytics(self, query_template, params):
        """Execute across all shards in parallel"""
        import asyncio

        tasks = [
            shard_db.fetch_all(query_template, params)
            for shard_db in self.shards.values()
        ]

        shard_results = await asyncio.gather(*tasks)
        results = []
        for shard_result in shard_results:
            results.extend(shard_result)

        return results
```

---

## Read Replica Configuration

### PostgreSQL Setup

```sql
-- Master: postgresql.conf
wal_level = replica
max_wal_senders = 3
wal_keep_size = '1GB'  -- PostgreSQL 13+ (replaces wal_keep_segments)
archive_mode = on

-- Create replication user
CREATE USER replicator REPLICATION LOGIN CONNECTION LIMIT 1
ENCRYPTED PASSWORD 'strong_password';
```

**Replica Setup (PostgreSQL 12+):**
```bash
# 1. Add to replica's postgresql.conf:
primary_conninfo = 'host=master.db port=5432 user=replicator password=...'

# 2. Create standby signal file (replaces recovery.conf):
touch $PGDATA/standby.signal

# 3. Start PostgreSQL - it will enter standby mode automatically
```

**Legacy (PostgreSQL 11 and earlier):**
```conf
# recovery.conf (deprecated in PostgreSQL 12+)
standby_mode = 'on'
primary_conninfo = 'host=master.db port=5432 user=replicator password=...'
```

---

## Performance Monitoring

### PostgreSQL Health Queries

```sql
-- Connection monitoring
SELECT
    state,
    COUNT(*) as connection_count,
    AVG(EXTRACT(epoch FROM (now() - state_change))) as avg_duration_seconds
FROM pg_stat_activity
WHERE state IS NOT NULL
GROUP BY state;

-- Query performance analysis
SELECT
    query,
    calls,
    total_time,
    mean_time,
    rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS cache_hit_percent
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 20;

-- Index usage analysis
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    CASE
        WHEN idx_scan = 0 THEN 'Unused'
        WHEN idx_scan < 10 THEN 'Low Usage'
        ELSE 'Active'
    END as usage_status
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Lock monitoring
SELECT
    pg_class.relname,
    pg_locks.mode,
    COUNT(*) as lock_count
FROM pg_locks
JOIN pg_class ON pg_locks.relation = pg_class.oid
WHERE pg_locks.granted = true
GROUP BY pg_class.relname, pg_locks.mode
ORDER BY lock_count DESC;
```

---

## Security Architecture

- **Authentication**: Multi-factor auth, secure session management
- **Authorization**: Role-based (RBAC), attribute-based (ABAC)
- **Data Protection**: Encryption at rest and in transit, PII handling
- **API Security**: Rate limiting, input validation, SQL injection prevention
- **Network Security**: VPC configuration, firewall rules
