-- Supabase Database Diagnostics Script
-- Checks for common issues flagged by Supabase Dashboard Advisors

\echo '========================================='
\echo 'SUPABASE DATABASE DIAGNOSTICS'
\echo '========================================='
\echo ''

-- 1. Tables without Primary Keys
\echo '1. TABLES WITHOUT PRIMARY KEYS'
\echo '-------------------------------------'
SELECT
    schemaname,
    tablename,
    'Missing primary key' as issue_type,
    'Add primary key for efficient row identification' as recommendation
FROM pg_tables t
WHERE schemaname IN ('public', 'private')
AND NOT EXISTS (
    SELECT 1 FROM pg_indexes i
    WHERE i.schemaname = t.schemaname
    AND i.tablename = t.tablename
    AND i.indexdef LIKE '%PRIMARY KEY%'
)
ORDER BY schemaname, tablename;
\echo ''

-- 2. Tables without Row Level Security (RLS)
\echo '2. TABLES WITHOUT RLS ENABLED'
\echo '-------------------------------------'
SELECT
    schemaname,
    tablename,
    'RLS not enabled' as issue_type,
    'Enable RLS to protect data access' as recommendation
FROM pg_tables
WHERE schemaname IN ('public', 'private')
AND rowsecurity = false
ORDER BY schemaname, tablename;
\echo ''

-- 3. Tables with RLS but no policies
\echo '3. TABLES WITH RLS BUT NO POLICIES'
\echo '-------------------------------------'
SELECT
    t.schemaname,
    t.tablename,
    'RLS enabled but no policies' as issue_type,
    'Add RLS policies or disable RLS' as recommendation
FROM pg_tables t
WHERE t.schemaname IN ('public', 'private')
AND t.rowsecurity = true
AND NOT EXISTS (
    SELECT 1 FROM pg_policies p
    WHERE p.schemaname = t.schemaname
    AND p.tablename = t.tablename
)
ORDER BY t.schemaname, t.tablename;
\echo ''

-- 4. Foreign Keys without indexes
\echo '4. FOREIGN KEYS WITHOUT INDEXES'
\echo '-------------------------------------'
SELECT
    tc.table_schema,
    tc.table_name,
    kcu.column_name,
    'Foreign key without index' as issue_type,
    'Add index on foreign key column for performance' as recommendation
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_schema IN ('public', 'private')
AND NOT EXISTS (
    SELECT 1 FROM pg_indexes i
    WHERE i.schemaname = tc.table_schema
    AND i.tablename = tc.table_name
    AND (
        i.indexdef LIKE '%' || kcu.column_name || '%'
        OR i.indexdef LIKE '%' || kcu.column_name || ',%'
    )
)
ORDER BY tc.table_schema, tc.table_name, kcu.column_name;
\echo ''

-- 5. Unused indexes
\echo '5. UNUSED INDEXES'
\echo '-------------------------------------'
SELECT
    schemaname,
    tablename,
    indexname,
    'Index never used' as issue_type,
    'Consider removing unused index' as recommendation
FROM pg_stat_user_indexes
WHERE schemaname IN ('public', 'private')
AND idx_scan = 0
AND indexrelname NOT LIKE 'pg_%'
ORDER BY pg_relation_size(indexrelid) DESC;
\echo ''

-- 6. Duplicate indexes
\echo '6. DUPLICATE INDEXES'
\echo '-------------------------------------'
SELECT
    a.schemaname,
    a.tablename,
    a.indexname as index1,
    b.indexname as index2,
    'Duplicate index' as issue_type,
    'Remove one of the duplicate indexes' as recommendation
FROM pg_indexes a
JOIN pg_indexes b
    ON a.schemaname = b.schemaname
    AND a.tablename = b.tablename
    AND a.indexname < b.indexname
WHERE a.schemaname IN ('public', 'private')
AND a.indexdef = b.indexdef
ORDER BY a.schemaname, a.tablename;
\echo ''

-- 7. Tables without updated_at timestamp
\echo '7. TABLES WITHOUT UPDATED_AT TIMESTAMP'
\echo '-------------------------------------'
SELECT
    t.schemaname,
    t.tablename,
    'Missing updated_at column' as issue_type,
    'Add updated_at timestamp for audit trail' as recommendation
FROM pg_tables t
WHERE t.schemaname IN ('public', 'private')
AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns c
    WHERE c.table_schema = t.schemaname
    AND c.table_name = t.tablename
    AND c.column_name IN ('updated_at', 'modified_at')
)
ORDER BY t.schemaname, t.tablename;
\echo ''

-- 8. Large tables without partitioning
\echo '8. LARGE TABLES (>100K rows) WITHOUT PARTITIONING'
\echo '-------------------------------------'
SELECT
    schemaname,
    tablename,
    n_live_tup as row_count,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    'Large table not partitioned' as issue_type,
    'Consider partitioning for better performance' as recommendation
FROM pg_stat_user_tables
WHERE schemaname IN ('public', 'private')
AND n_live_tup > 100000
ORDER BY n_live_tup DESC;
\echo ''

-- 9. Tables with bloat
\echo '9. TABLES WITH SIGNIFICANT BLOAT'
\echo '-------------------------------------'
SELECT
    schemaname,
    tablename,
    n_dead_tup as dead_tuples,
    n_live_tup as live_tuples,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as bloat_pct,
    'Table bloat detected' as issue_type,
    'Run VACUUM ANALYZE' as recommendation
FROM pg_stat_user_tables
WHERE schemaname IN ('public', 'private')
AND n_dead_tup > 1000
AND n_dead_tup > n_live_tup * 0.1
ORDER BY bloat_pct DESC;
\echo ''

-- 10. Missing NOT NULL constraints on important columns
\echo '10. ID COLUMNS WITHOUT NOT NULL CONSTRAINT'
\echo '-------------------------------------'
SELECT
    table_schema,
    table_name,
    column_name,
    'ID column allows NULL' as issue_type,
    'Add NOT NULL constraint to ID column' as recommendation
FROM information_schema.columns
WHERE table_schema IN ('public', 'private')
AND column_name LIKE '%_id'
AND is_nullable = 'YES'
ORDER BY table_schema, table_name, column_name;
\echo ''

-- 11. Public schema exposure
\echo '11. FUNCTIONS IN PUBLIC SCHEMA'
\echo '-------------------------------------'
SELECT
    n.nspname as schema,
    p.proname as function_name,
    pg_get_function_arguments(p.oid) as arguments,
    'Function exposed in public schema' as issue_type,
    'Review function security and consider moving to private schema' as recommendation
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
AND p.prokind = 'f'
AND p.proname NOT LIKE 'pg_%'
ORDER BY p.proname;
\echo ''

-- 12. Missing indexes on timestamp columns
\echo '12. TIMESTAMP COLUMNS WITHOUT INDEXES'
\echo '-------------------------------------'
SELECT
    c.table_schema,
    c.table_name,
    c.column_name,
    'Timestamp column without index' as issue_type,
    'Add index on timestamp for time-based queries' as recommendation
FROM information_schema.columns c
WHERE c.table_schema IN ('public', 'private')
AND c.data_type IN ('timestamp with time zone', 'timestamp without time zone')
AND c.column_name IN ('created_at', 'updated_at', 'deleted_at', 'published_at')
AND NOT EXISTS (
    SELECT 1 FROM pg_indexes i
    WHERE i.schemaname = c.table_schema
    AND i.tablename = c.table_name
    AND i.indexdef LIKE '%' || c.column_name || '%'
)
ORDER BY c.table_schema, c.table_name, c.column_name;
\echo ''

-- 13. Realtime not configured
\echo '13. TABLES WITHOUT REALTIME ENABLED (if needed)'
\echo '-------------------------------------'
SELECT
    schemaname,
    tablename,
    'Realtime not configured' as issue_type,
    'Enable realtime if live updates needed' as recommendation
FROM pg_tables
WHERE schemaname = 'public'
AND tablename NOT IN (
    SELECT tablename FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
)
ORDER BY tablename;
\echo ''

-- Summary count
\echo ''
\echo '========================================='
\echo 'SUMMARY'
\echo '========================================='
SELECT
    COUNT(*) as total_potential_issues,
    'Run individual queries above for details' as note
FROM (
    -- Count from each category (simplified - actual counts would need UNION ALL)
    SELECT 1 FROM pg_tables WHERE schemaname = 'public' LIMIT 1
) summary;
