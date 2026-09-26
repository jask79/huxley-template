"""5-branch decision tree per Algo Wizard's ADR section 4.

Pipeline:
  1. Build merge clusters via redundancy graph (R ≥ 0.75 → edge).
  2. Per-cluster leader pick via 5-rule tiebreaker.
  3. Per-skill decision: KEEP (pinned) / MERGE-WITH-leader / ARCHIVE / IMPROVE / KEEP.

Pure functions, deterministic. No filesystem mutations — those live in curator.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from .scorer import (
    ARCHIVE_S_THRESHOLD,
    IMPROVE_NEG_FLOOR,
    IMPROVE_Q_THRESHOLD,
    MERGE_R_THRESHOLD,
    SkillRecord,
    confidence_archive,
    confidence_improve,
    confidence_keep_active,
    confidence_merge,
    quality,
    redundancy,
    staleness,
    tfidf_vector,
    cosine_similarity,
)
from .usage import (
    invocations_in_last_n_days,
    is_curated,
    is_pinned,
)


ACTION_KEEP = "KEEP"
ACTION_ARCHIVE = "ARCHIVE"
ACTION_IMPROVE = "IMPROVE"
ACTION_MERGE = "MERGE"


@dataclass
class Decision:
    """A single per-skill decision with full rationale for the report."""

    skill_name: str
    action: str  # ACTION_*
    confidence: float
    rationale: str
    # Scores (always populated)
    s_score: float
    q_score: float
    n_pos: int
    n_neg: int
    invocations_90d: int
    # Merge-specific (None for non-MERGE)
    merge_leader: Optional[str] = None
    r_to_leader: Optional[float] = None
    cluster_members: List[str] = field(default_factory=list)


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Merge-direction tiebreaker (5 rules, strict-greater required at each step)
# ---------------------------------------------------------------------------


def pick_leader(records: List[SkillRecord], now: datetime) -> SkillRecord:
    """Per ADR section 3e: invocations_90d → Q → body length → T0 → name."""
    if len(records) == 1:
        return records[0]

    def rank_key(r: SkillRecord) -> Tuple[int, float, int, float, str]:
        inv90 = invocations_in_last_n_days(r.usage_record, 90, now)
        q, _, _ = quality(r, now)
        body_len = len(r.body_text)
        t0 = _parse_iso(r.usage_record.get("first_used_at")) or _parse_iso(
            r.frontmatter.get("proposed_at")
        ) or _parse_iso(r.usage_record.get("created_at"))
        # Sort descending on first 4, ascending on name. Negate as needed.
        # invocations_90d: more wins → negate
        # Q: higher wins → negate
        # body_length: longer wins → negate
        # T0: older wins → use ascending order (smaller=older=better) → no negate
        t0_ts = t0.timestamp() if t0 else float("inf")
        return (-inv90, -q, -body_len, t0_ts, r.name)

    sorted_records = sorted(records, key=rank_key)
    return sorted_records[0]


# ---------------------------------------------------------------------------
# Cluster formation
# ---------------------------------------------------------------------------


@dataclass
class SimilarityPair:
    """One row in the similarity matrix (for the dry-run report)."""

    a: str
    b: str
    r: float
    j: float  # tool jaccard
    c: float  # body cosine
    d: float  # desc jaccard


def build_similarity_matrix(
    records: List[SkillRecord], idf: Dict[str, float]
) -> List[SimilarityPair]:
    """All pairs (a,b) with a < b. O(N²) but fine at N ≤ 100."""
    pairs: List[SimilarityPair] = []
    n = len(records)
    for i in range(n):
        for j in range(i + 1, n):
            r, jacc, cos, desc = redundancy(records[i], records[j], idf)
            pairs.append(
                SimilarityPair(
                    a=records[i].name,
                    b=records[j].name,
                    r=r,
                    j=jacc,
                    c=cos,
                    d=desc,
                )
            )
    pairs.sort(key=lambda p: -p.r)
    return pairs


def find_clusters(
    records: List[SkillRecord], pairs: List[SimilarityPair], threshold: float = MERGE_R_THRESHOLD
) -> List[List[SkillRecord]]:
    """Connected components in the graph of pairs with R ≥ threshold."""
    name_to_record = {r.name: r for r in records}
    # Adjacency list
    adj: Dict[str, Set[str]] = {r.name: set() for r in records}
    for p in pairs:
        if p.r >= threshold:
            adj[p.a].add(p.b)
            adj[p.b].add(p.a)

    visited: Set[str] = set()
    clusters: List[List[SkillRecord]] = []
    for name in adj:
        if name in visited:
            continue
        # BFS
        component: List[str] = []
        stack = [name]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for neigh in adj[node]:
                if neigh not in visited:
                    stack.append(neigh)
        if len(component) >= 2:
            clusters.append([name_to_record[n] for n in component])
    return clusters


# ---------------------------------------------------------------------------
# Per-skill decision
# ---------------------------------------------------------------------------


def decide_for_skill(
    record: SkillRecord,
    cluster: Optional[List[SkillRecord]],
    cluster_leader: Optional[SkillRecord],
    idf: Dict[str, float],
    now: datetime,
) -> Decision:
    """Apply the 5-branch decision tree to a single skill.

    `cluster` is the connected component this skill belongs to (or None if
    it's a singleton). `cluster_leader` is the pre-computed leader for the
    cluster.
    """
    # Pre-compute scores (always populated in Decision)
    s = staleness(record, now)
    q, n_pos, n_neg = quality(record, now)
    inv90 = invocations_in_last_n_days(record.usage_record, 90, now)

    # Branch 1: pinned → KEEP
    if is_pinned(record.frontmatter):
        return Decision(
            skill_name=record.name,
            action=ACTION_KEEP,
            confidence=1.0,
            rationale="pinned (metadata.pinned=true)",
            s_score=s,
            q_score=q,
            n_pos=n_pos,
            n_neg=n_neg,
            invocations_90d=inv90,
        )

    # Branch 2: not curated → defensive guard (input should pre-filter)
    if not is_curated(record.frontmatter):
        return Decision(
            skill_name=record.name,
            action=ACTION_KEEP,
            confidence=1.0,
            rationale="not curated (metadata.curated!=true) — defensive skip",
            s_score=s,
            q_score=q,
            n_pos=n_pos,
            n_neg=n_neg,
            invocations_90d=inv90,
        )

    # Branch 3: in cluster of size ≥ 2 and not the leader → MERGE
    if cluster is not None and cluster_leader is not None and len(cluster) >= 2:
        if record.name != cluster_leader.name:
            r_lead, _, _, _ = redundancy(record, cluster_leader, idf)
            return Decision(
                skill_name=record.name,
                action=ACTION_MERGE,
                confidence=confidence_merge(r_lead),
                rationale=(
                    f"in merge cluster with leader '{cluster_leader.name}' "
                    f"(R={r_lead:.3f} ≥ {MERGE_R_THRESHOLD})"
                ),
                s_score=s,
                q_score=q,
                n_pos=n_pos,
                n_neg=n_neg,
                invocations_90d=inv90,
                merge_leader=cluster_leader.name,
                r_to_leader=r_lead,
                cluster_members=[c.name for c in cluster],
            )
        # else: this IS the leader — fall through to normal evaluation

    # Branch 4: stale + zero-90d → ARCHIVE
    if s >= ARCHIVE_S_THRESHOLD and inv90 == 0:
        return Decision(
            skill_name=record.name,
            action=ACTION_ARCHIVE,
            confidence=confidence_archive(s),
            rationale=(
                f"stale (S={s:.3f} ≥ {ARCHIVE_S_THRESHOLD}) and zero invocations in last 90 days"
            ),
            s_score=s,
            q_score=q,
            n_pos=n_pos,
            n_neg=n_neg,
            invocations_90d=inv90,
        )

    # Branch 5: bad quality → IMPROVE
    if q <= IMPROVE_Q_THRESHOLD and n_neg >= IMPROVE_NEG_FLOOR:
        return Decision(
            skill_name=record.name,
            action=ACTION_IMPROVE,
            confidence=confidence_improve(q, n_neg),
            rationale=(
                f"low quality (Q={q:.3f} ≤ {IMPROVE_Q_THRESHOLD}) "
                f"with {n_neg} negative signals (≥ {IMPROVE_NEG_FLOOR})"
            ),
            s_score=s,
            q_score=q,
            n_pos=n_pos,
            n_neg=n_neg,
            invocations_90d=inv90,
        )

    # Default: KEEP
    return Decision(
        skill_name=record.name,
        action=ACTION_KEEP,
        confidence=confidence_keep_active(s, q),
        rationale=f"active (S={s:.3f}, Q={q:.3f}, inv_90d={inv90})",
        s_score=s,
        q_score=q,
        n_pos=n_pos,
        n_neg=n_neg,
        invocations_90d=inv90,
    )


def decide_all(
    records: List[SkillRecord],
    idf: Dict[str, float],
    now: datetime,
) -> Tuple[List[Decision], List[SimilarityPair], List[List[SkillRecord]]]:
    """Run the full pipeline.

    Returns:
        decisions: one Decision per record
        similarity_pairs: full sorted matrix (for dry-run report)
        clusters: list of connected components of size ≥ 2
    """
    pairs = build_similarity_matrix(records, idf)
    clusters = find_clusters(records, pairs)

    # Build name -> (cluster, leader) lookup
    cluster_lookup: Dict[str, Tuple[List[SkillRecord], SkillRecord]] = {}
    for cluster in clusters:
        leader = pick_leader(cluster, now)
        for member in cluster:
            cluster_lookup[member.name] = (cluster, leader)

    decisions: List[Decision] = []
    for r in records:
        cluster, leader = cluster_lookup.get(r.name, (None, None))
        decisions.append(decide_for_skill(r, cluster, leader, idf, now))

    return decisions, pairs, clusters
