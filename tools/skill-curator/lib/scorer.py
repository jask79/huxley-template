"""Scoring functions per Algo Wizard's ADR.

Implements:
  - S(s): staleness — exponential decay with adaptive half-life
  - Q(s): quality — Laplace-smoothed pos/neg ratio over recent feedback
  - R(a,b): redundancy — 0.30·J + 0.50·C + 0.20·D (tool Jaccard + TF-IDF + desc)

Pure functions, stdlib-only, deterministic. No I/O.

"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Re-use Phase 2's deduper for top-5-tool extraction (Algo Wizard's Q1.3 dep).
# We import lazily inside extract_top_tools() to avoid a hard package coupling
# when this module is unit-tested in isolation.


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NEWBORN_AGE_DAYS = 7
HALF_LIFE_MIN = 10
HALF_LIFE_MAX = 30
HALF_LIFE_BASE = 30  # days; reduced toward MIN by tanh(rate*7)
ARCHIVE_S_THRESHOLD = 0.7
IMPROVE_Q_THRESHOLD = 0.3
IMPROVE_NEG_FLOOR = 5
MERGE_R_THRESHOLD = 0.75
FEEDBACK_WINDOW_DAYS = 180
FEEDBACK_COLD_START = 3
TOOL_TOPN = 5

# Combined weights — sum to 1.0
W_TOOL = 0.30
W_BODY = 0.50
W_DESC = 0.20

# Stopwords — minimal English set, stdlib-only
STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "he", "her", "his", "i", "if", "in", "into", "is", "it",
    "its", "of", "on", "or", "she", "so", "such", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those",
    "to", "was", "we", "were", "what", "when", "where", "which", "who",
    "why", "will", "with", "you", "your", "be", "been", "being", "do",
    "does", "did", "doing", "had", "having", "would", "should", "could",
    "can", "may", "must", "shall", "ought", "use", "used", "using",
    "skill", "skills", "task", "tasks", "step", "steps",
}

# Stricter stopwords for description (fewer words to compare)
DESC_STOPWORDS: Set[str] = STOPWORDS | {
    "tool", "tools", "file", "files", "code", "user",
}

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_URL_RE = re.compile(r"https?://\S+")


# ---------------------------------------------------------------------------
# Skill record — the bundle of inputs the scorer/decider needs
# ---------------------------------------------------------------------------


@dataclass
class SkillRecord:
    """Everything a single skill contributes to the algorithm."""

    name: str
    path: Path
    body_text: str  # full SKILL.md text (frontmatter + body)
    frontmatter: Dict[str, Any]
    usage_record: Dict[str, Any]
    # Cached extracts (populated by build helpers below)
    top_tools: List[str] = None  # type: ignore[assignment]
    body_tokens: List[str] = None  # type: ignore[assignment]
    desc_tokens: Set[str] = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Staleness — S(s)
# ---------------------------------------------------------------------------


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_T0(record: SkillRecord, now: datetime) -> datetime:
    """T0 = max(first_used, proposed_at, file_mtime). Birth time of the skill."""
    candidates: List[datetime] = []

    fu = record.usage_record.get("first_used_at")
    if fu:
        try:
            dt = datetime.fromisoformat(str(fu))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            candidates.append(dt)
        except (TypeError, ValueError):
            pass

    pa = record.frontmatter.get("proposed_at")
    if pa:
        try:
            dt = datetime.fromisoformat(str(pa))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            candidates.append(dt)
        except (TypeError, ValueError):
            pass

    try:
        mtime = datetime.fromtimestamp(record.path.stat().st_mtime, tz=timezone.utc)
        candidates.append(mtime)
    except (OSError, ValueError):
        pass

    ca = record.usage_record.get("created_at")
    if ca:
        try:
            dt = datetime.fromisoformat(str(ca))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            candidates.append(dt)
        except (TypeError, ValueError):
            pass

    if not candidates:
        # No anchor — assume birthed now (treat as newborn, S=0)
        return now

    # ADR says max() i.e. most recent — newest of the timestamps. This means
    # if the file was recently modified, we treat it as "newborn-ish" relative
    # to its mtime. For our purposes (skill maintenance), that's the right
    # behavior: a recent rewrite resets the staleness clock.
    return max(candidates)


def staleness(record: SkillRecord, now: datetime) -> float:
    """S(s) ∈ [0,1] — exponential decay with adaptive half-life.

    See ADR section 1 for the formula. Newborn protection: S=0 if age < 7d.
    """
    T0 = compute_T0(record, now)

    last_used_raw = record.usage_record.get("last_used_at")
    last_used = None
    if last_used_raw:
        try:
            last_used = datetime.fromisoformat(str(last_used_raw))
            if last_used.tzinfo is None:
                last_used = last_used.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            last_used = None

    # age_days based on last_used if available, else from T0
    if last_used:
        age_days = (now - last_used).total_seconds() / 86400.0
    else:
        age_days = (now - T0).total_seconds() / 86400.0

    # Newborn protection — also covers negative-age clamping
    skill_age_days = max(0.0, (now - T0).total_seconds() / 86400.0)
    if skill_age_days < NEWBORN_AGE_DAYS:
        return 0.0

    if age_days < 0:
        age_days = 0.0

    # Adaptive half-life: rate of invocations per day since birth
    invocations = max(0, int(record.usage_record.get("use_count") or 0))
    days_since_birth = max(1.0, skill_age_days)
    rate = invocations / days_since_birth

    # tanh(rate*7) ∈ [0, ~1]; multiply by 20 → reduces base 30 toward 10
    half_life = clamp(
        HALF_LIFE_BASE - 20.0 * math.tanh(rate * 7.0),
        HALF_LIFE_MIN,
        HALF_LIFE_MAX,
    )

    s_raw = 1.0 - 0.5 ** (age_days / half_life)
    return clamp(s_raw, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Quality — Q(s)
# ---------------------------------------------------------------------------


def quality(record: SkillRecord, now: datetime) -> Tuple[float, int, int]:
    """Q(s) ∈ [0,1] — Laplace-smoothed pos/(pos+neg) over 180-day feedback.

    Returns (Q, n_pos, n_neg) so the decider can also gate on n_neg ≥ 5.
    """
    feedback = record.usage_record.get("feedback") or []
    if not isinstance(feedback, list):
        feedback = []

    cutoff = now - timedelta(days=FEEDBACK_WINDOW_DAYS)
    n_pos = 0
    n_neg = 0
    n_total = 0

    for f in feedback:
        if not isinstance(f, dict):
            continue
        ts_raw = f.get("ts")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_raw))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            continue
        n_total += 1
        sig = str(f.get("signal", "")).lower()
        if sig.startswith("pos"):
            n_pos += 1
        elif sig.startswith("neg"):
            n_neg += 1
        # 'neutral' counts toward n_total only

    if n_total < FEEDBACK_COLD_START:
        return 0.5, n_pos, n_neg

    # Laplace smoothing α=1
    q = (n_pos + 1) / (n_pos + n_neg + 2)
    return clamp(q, 0.0, 1.0), n_pos, n_neg


# ---------------------------------------------------------------------------
# Redundancy — R(a,b)
# ---------------------------------------------------------------------------


def extract_top_tools(skill_md_text: str, n: int = TOOL_TOPN) -> List[str]:
    """Top-N tools mentioned in `allowed-tools:` block or body.

    Reuses the same logic as Phase 2's deduper._hash_skill_md so the merge
    detector and the proposer dedupe agree on tool identity.
    """
    # Lazy import to keep this module standalone-testable.
    try:
        from .deduper import _hash_skill_md  # noqa: F401  # registered for parity
        from .deduper import KNOWN_TOOLS, ALLOWED_TOOL_LINE
    except ImportError:
        # Fallback minimal set
        KNOWN_TOOLS = {
            "Bash", "Read", "Write", "Edit", "Glob", "Grep", "Task",
            "WebFetch", "WebSearch", "TodoWrite", "ToolSearch",
            "NotebookEdit", "Skill",
        }
        ALLOWED_TOOL_LINE = re.compile(r"^\s*-\s+([A-Za-z][A-Za-z0-9_]*)\s*$")

    tools: Set[str] = set()
    in_allowed_block = False

    for line in skill_md_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("allowed-tools:"):
            in_allowed_block = True
            inline = stripped.split(":", 1)[1].strip()
            if inline.startswith("[") and inline.endswith("]"):
                for t in inline[1:-1].split(","):
                    t = t.strip().strip("'\"")
                    if t:
                        tools.add(t)
                in_allowed_block = False
            continue
        if in_allowed_block:
            m = ALLOWED_TOOL_LINE.match(line)
            if m:
                tools.add(m.group(1))
            elif stripped and not stripped.startswith("-") and not stripped.startswith("#"):
                in_allowed_block = False

    if not tools:
        for known in KNOWN_TOOLS:
            if known in skill_md_text:
                tools.add(known)

    return sorted(tools)[:n]


def tokenize_body(skill_md_text: str) -> List[str]:
    """Strip frontmatter / code / urls; tokenize; lowercase; drop short/stopword."""
    text = _FRONTMATTER_RE.sub("", skill_md_text, count=1)
    text = _CODE_FENCE_RE.sub(" ", text)
    text = _INLINE_CODE_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    tokens = []
    for tok in _TOKEN_RE.findall(text):
        low = tok.lower()
        if len(low) < 3:
            continue
        if low in STOPWORDS:
            continue
        tokens.append(low)
    return tokens


def tokenize_description(desc: str) -> Set[str]:
    """Token-bag for description Jaccard. Stricter stopwords."""
    if not desc:
        return set()
    tokens: Set[str] = set()
    for tok in _TOKEN_RE.findall(desc):
        low = tok.lower()
        if len(low) < 3:
            continue
        if low in DESC_STOPWORDS:
            continue
        tokens.add(low)
    return tokens


def jaccard(a: Iterable[Any], b: Iterable[Any]) -> float:
    """|A ∩ B| / |A ∪ B|. Returns 0.0 if either side empty."""
    sa = set(a)
    sb = set(b)
    if not sa or not sb:
        return 0.0
    inter = sa & sb
    union = sa | sb
    return len(inter) / len(union)


def compute_idf(corpus_token_lists: List[List[str]]) -> Dict[str, float]:
    """Smoothed IDF: log((N+1)/(df+1)) + 1.

    Per Algo Wizard's Q1: IDF computed over ALL skills (background corpus)
    so the document-frequency baseline is stable at N=119+ rather than
    recomputed for each curated subset.
    """
    n = len(corpus_token_lists)
    if n == 0:
        return {}
    df: Counter = Counter()
    for tokens in corpus_token_lists:
        for term in set(tokens):
            df[term] += 1

    idf: Dict[str, float] = {}
    log_num = math.log(n + 1)
    for term, df_t in df.items():
        idf[term] = log_num - math.log(df_t + 1) + 1.0
    return idf


def tfidf_vector(tokens: List[str], idf: Dict[str, float]) -> Dict[str, float]:
    """tf(t) * idf(t). Terms not in idf get idf = log(N+1)+1 default."""
    if not tokens:
        return {}
    total = len(tokens)
    counts = Counter(tokens)
    # Default IDF for unseen-in-corpus terms — use the max possible (df=0).
    default_idf = max(idf.values(), default=1.0) if idf else 1.0
    return {t: (c / total) * idf.get(t, default_idf) for t, c in counts.items()}


def cosine_similarity(va: Dict[str, float], vb: Dict[str, float]) -> float:
    if not va or not vb:
        return 0.0
    dot = 0.0
    for term, val in va.items():
        if term in vb:
            dot += val * vb[term]
    norm_a = math.sqrt(sum(v * v for v in va.values()))
    norm_b = math.sqrt(sum(v * v for v in vb.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return clamp(dot / (norm_a * norm_b), 0.0, 1.0)


def redundancy(
    a: SkillRecord, b: SkillRecord, idf: Dict[str, float]
) -> Tuple[float, float, float, float]:
    """R(a,b) = 0.30·J + 0.50·C + 0.20·D. Returns (R, J, C, D)."""
    j = jaccard(a.top_tools or [], b.top_tools or [])

    va = tfidf_vector(a.body_tokens or [], idf)
    vb = tfidf_vector(b.body_tokens or [], idf)
    c = cosine_similarity(va, vb)

    d = jaccard(a.desc_tokens or set(), b.desc_tokens or set())

    r = W_TOOL * j + W_BODY * c + W_DESC * d
    return clamp(r, 0.0, 1.0), j, c, d


# ---------------------------------------------------------------------------
# Confidence — for report annotation
# ---------------------------------------------------------------------------


def confidence_archive(s: float) -> float:
    return clamp((s - ARCHIVE_S_THRESHOLD) / (1.0 - ARCHIVE_S_THRESHOLD), 0.0, 1.0)


def confidence_improve(q: float, n_neg: int) -> float:
    qf = clamp((IMPROVE_Q_THRESHOLD - q) / IMPROVE_Q_THRESHOLD, 0.0, 1.0)
    nf = clamp(n_neg / 10.0, 0.0, 1.0)
    return qf * nf


def confidence_merge(r: float) -> float:
    return clamp((r - MERGE_R_THRESHOLD) / (1.0 - MERGE_R_THRESHOLD), 0.0, 1.0)


def confidence_keep_active(s: float, q: float) -> float:
    return clamp(1.0 - max(s, 1.0 - q), 0.0, 1.0)
