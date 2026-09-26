# Huxley Debugging Integration

Pattern learning, Code Reviewer integration, and quality.db workflows.

## Code Reviewer ↔ Debugger Bidirectional Learning

### Code Reviewer → Debugger (Risk Signals)

**Reviewer flags bug-prone code:**
```sql
-- Query code hotspots flagged by reviewer
SELECT
    c.file_path,
    c.complexity_score,
    c.bug_density,
    c.code_smell_type,
    COUNT(DISTINCT p.pattern_id) as historical_bugs
FROM debug_code_correlations c
JOIN debug_patterns p ON c.pattern_id = p.pattern_id
WHERE c.file_path = ?
GROUP BY c.file_path, c.complexity_score, c.bug_density, c.code_smell_type
ORDER BY bug_density DESC, historical_bugs DESC;
```

**Raise suspicion index for flagged modules:**
```python
def adjust_hypothesis_confidence_for_code_risk(hypothesis, file_path):
    """Boost confidence if bug occurs in high-risk code"""
    hotspot = query_bug_hotspots(file_path)

    if hotspot:
        risk_boost = 0.0

        # High complexity = higher bug probability
        if hotspot.complexity_score > 20:
            risk_boost += 0.10

        # Historical bug density
        if hotspot.unique_patterns > 3:
            risk_boost += 0.15

        # Recent review findings
        if hotspot.code_smell_type:
            risk_boost += 0.05

        hypothesis.confidence += risk_boost

    return hypothesis
```

**Example Output:**
```
🔬 Hypothesis: Null pointer in order.py:145

Base confidence: 0.70
├─ Pattern match: 0.30
├─ Evidence: 0.25
└─ Reproduction: 0.15

Code Risk Adjustment: +0.20
├─ Complexity (CC=28): +0.10
├─ Bug history (5 patterns): +0.15
└─ Code smell (long method): +0.05

Final confidence: 0.90 (HIGH - prioritize investigation)
```

### Debugger → Code Reviewer (Bug Pattern Feedback)

**Feed confirmed root causes back to reviewer:**
```python
def create_code_correlation(pattern_id, files, review_findings):
    """Link debug patterns to code review findings"""
    for file in files:
        review = get_latest_review_for_file(file)

        db.execute("""
            INSERT INTO debug_code_correlations (
                correlation_id, pattern_id, review_id,
                file_path, complexity_score, bug_density,
                code_smell_type, correlation_strength
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            generate_id(),
            pattern_id,
            review.id if review else None,
            file,
            review.complexity_score if review else None,
            calculate_bug_density(file, pattern_id),
            review.code_smell if review else None,
            calculate_correlation_strength(pattern_id, review)
        ))
```

**Feedback Example:**
```
📊 Debugger Feedback to Code Reviewer:

File: api/services/order.py
├─ Bugs: 5 incidents in 60 days
├─ Pattern: Null pointer errors in calculateOrderTotal()
├─ Root cause: Missing input validation
├─ Complexity: CC=28 (flagged in review)
└─ Recommendation: Escalate findings for high-complexity functions

Action: Code Reviewer now flags CC>20 as CRITICAL in order processing modules
```

---

## Shared Bug Hotspot Detection

**Both agents contribute to hotspot identification:**
```sql
-- Comprehensive hotspot view
CREATE VIEW comprehensive_hotspots AS
SELECT
    c.file_path,
    -- Debugger metrics
    COUNT(DISTINCT c.pattern_id) as bug_count,
    AVG(p.time_to_fix_minutes) as avg_fix_time,
    MAX(p.last_seen) as most_recent_bug,
    -- Code Reviewer metrics
    MAX(r.complexity_score) as max_complexity,
    MAX(r.duplication_percent) as duplication,
    MAX(r.technical_debt_hours) as tech_debt
FROM debug_code_correlations c
JOIN debug_patterns p ON c.pattern_id = p.pattern_id
LEFT JOIN code_review_findings r ON c.review_id = r.review_id
GROUP BY c.file_path
HAVING bug_count > 2 OR max_complexity > 20
ORDER BY bug_count DESC, max_complexity DESC, avg_fix_time DESC;
```

---

## Preventive Linting Rules

**When pattern frequency > threshold, suggest preventive rule:**
```python
def suggest_preventive_linting(pattern):
    """High-frequency patterns should become linting rules"""
    if pattern.frequency > 5:
        suggestions = []

        if 'null pointer' in pattern.error_signature:
            suggestions.append({
                'rule_type': 'eslint',
                'rule': 'no-null-guard',
                'config': 'Require null checks before property access',
                'rationale': f'{pattern.frequency} incidents in {pattern.capsule}'
            })

        if 'async' in pattern.error_signature and 'race' in pattern.root_cause:
            suggestions.append({
                'rule_type': 'eslint',
                'rule': 'no-unguarded-async',
                'config': 'Require proper async error handling',
                'rationale': f'{pattern.frequency} race conditions detected'
            })

        return suggestions
```

---

## Historical Pattern Learning

### Pattern Storage

```python
def create_debug_pattern(error, resolution, files_affected):
    """Store pattern for future learning"""
    import hashlib
    import json
    import sqlite3

    # Generate unique pattern ID
    pattern_id = hashlib.sha256(
        f"{error.type}:{error.signature}:{error.context}".encode()
    ).hexdigest()[:16]

    context_fingerprint = json.dumps({
        'capsule': error.capsule,
        'module': error.module,
        'error_type': error.type,
        'stack_signature': error.stack_hash
    })

    db = sqlite3.connect('{{CATALYST_ROOT}}/monitoring/quality.db')
    db.execute("""
        INSERT INTO debug_patterns (
            pattern_id, error_signature, context_fingerprint,
            root_cause, resolution, time_to_fix_minutes,
            supporting_evidence, mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pattern_id,
        error.signature,
        context_fingerprint,
        error.root_cause,
        resolution,
        error.time_to_fix,
        json.dumps({'files': files_affected, 'evidence': error.evidence}),
        error.mode or 'legacy'
    ))
    db.commit()
```

### Pattern Retrieval

```sql
-- Find similar patterns for current issue
SELECT
    pattern_id,
    error_signature,
    root_cause,
    resolution,
    time_to_fix_minutes,
    (julianday('now') - julianday(last_seen)) as days_since_seen
FROM debug_patterns
WHERE error_signature LIKE '%' || ? || '%'
   OR context_fingerprint LIKE '%' || ? || '%'
ORDER BY
    CASE WHEN error_signature LIKE '%' || ? || '%' THEN 0 ELSE 1 END,
    days_since_seen ASC
LIMIT 5;
```

---

## Hypothesis Confidence Scoring

### Confidence Calculation

```python
def calculate_hypothesis_confidence(hypothesis, evidence):
    """
    Calculate confidence score (0.0 - 1.0) for a debugging hypothesis
    """
    confidence = 0.0

    # Pattern match contribution (0-0.35)
    if evidence.pattern_match:
        pattern_score = evidence.pattern_match.similarity * 0.35
        confidence += pattern_score

    # Evidence strength (0-0.30)
    evidence_score = 0.0
    if evidence.stack_trace_match:
        evidence_score += 0.15
    if evidence.log_correlation:
        evidence_score += 0.10
    if evidence.metric_anomaly:
        evidence_score += 0.05
    confidence += min(evidence_score, 0.30)

    # Reproduction success (0-0.20)
    if evidence.reproduced:
        confidence += 0.20
    elif evidence.partial_reproduction:
        confidence += 0.10

    # Code risk adjustment (0-0.15)
    if evidence.code_hotspot:
        hotspot = evidence.code_hotspot
        if hotspot.complexity_score > 20:
            confidence += 0.05
        if hotspot.bug_history > 3:
            confidence += 0.05
        if hotspot.recent_changes:
            confidence += 0.05

    return min(confidence, 1.0)
```

### Confidence Thresholds

| Score | Classification | Action |
|-------|----------------|--------|
| 0.85+ | High confidence | Proceed with fix |
| 0.60-0.84 | Medium confidence | Gather more evidence |
| 0.40-0.59 | Low confidence | Alternative hypotheses |
| <0.40 | Very low | Reconsider approach |

---

## Session Observability

### Context Tracking Template

```markdown
## Debug Session Log

### Context Examined
- [x] Error logs (10 lines) - found stack trace
- [x] Config files (3 files) - verified settings
- [ ] Database state - pending
- [ ] Network traces - not yet examined

### Tools Used
| Tool | Usage | Insight |
|------|-------|---------|
| Read | 5 files | Stack trace in app.log |
| Grep | 3 patterns | Error occurs in auth module |
| Bash | 2 commands | Service is running |

### Hypotheses Status
| Hypothesis | Confidence | Status |
|------------|------------|--------|
| Auth token expiry | 85% | Investigating |
| Rate limiting | 30% | Ruled out |
| Network timeout | 20% | Pending |
```

### Progress Checkpoints

Every 5 tool calls, ask:
1. Am I getting closer to root cause?
2. Should I change approach?
3. Have I explored all likely causes?
4. Is there a pattern match I missed?

### When to Escalate

Escalate to human or different agent if:
- 10+ tool calls with no progress
- All hypotheses ruled out
- Domain requires expertise you lack
- Access constraints prevent investigation

---

## Integration with Phase 5

**After debugging, always:**
1. Log pattern to quality.db if systemic issue
2. Update autopsy agent knowledge if new pattern
3. Add monitoring/validation if preventable
4. Document in relevant component CLAUDE.md

```python
def log_debug_session(session):
    """Log session for Phase 5 learning"""
    db = sqlite3.connect('{{CATALYST_ROOT}}/monitoring/quality.db')
    db.execute("""
        INSERT INTO debug_sessions (
            session_id, issue_type, context_type,
            tools_used, hypotheses_tested,
            resolution_time_seconds, root_cause,
            pattern_id_matched, new_pattern_created
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session.id,
        session.issue_type,
        session.context_type,
        json.dumps(session.tools_used),
        json.dumps(session.hypotheses),
        session.duration_seconds,
        session.root_cause,
        session.matched_pattern_id,
        session.new_pattern_id
    ))
    db.commit()
```
