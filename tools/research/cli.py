import argparse
import json
import os
from typing import Any, Dict, List

from .search import SearchResult, composite_search
from .extract import extract
from .summarize import (
    SourceDoc,
    summarize_extractive,
    summarize_with_llm,
    _llm_available,
    extract_quotes,
)
from .utils import score_relevance, diversify_by_domain, recency_score, tokenize, domain_from_url


def propose_followups(question: str, results: List[SearchResult]) -> List[str]:
    # Heuristic follow-ups: add distinctive title keywords and diversify by domain
    q_tokens = set(tokenize(question))
    keywords: Dict[str, int] = {}
    domains: Dict[str, int] = {}
    for r in results[:12]:
        # Title-based keywords
        title = (r.title or "")
        for tok in title.split():
            t = tok.strip().strip('"\'(),.').lower()
            if not t or len(t) < 4 or t in q_tokens:
                continue
            if any(ch.isdigit() for ch in t):
                continue
            keywords[t] = keywords.get(t, 0) + 1
        # Domain bucket
        d = domain_from_url(r.url)
        if d:
            domains[d] = domains.get(d, 0) + 1

    # Top distinct keywords
    top_kw = sorted(keywords.items(), key=lambda x: x[1], reverse=True)
    kw_queries = [f"{question} {w}" for w, _ in top_kw[:3]]

    # Top domains: craft site-specific queries to pull deeper pages
    top_domains = [d for d, _ in sorted(domains.items(), key=lambda x: x[1], reverse=True)[:3]]
    site_queries = [f"site:{d} {question}" for d in top_domains]

    merged = []
    seen = set()
    for q in kw_queries + site_queries:
        if q not in seen and q.strip() != question.strip():
            seen.add(q)
            merged.append(q)
    return merged


def pick_top(results: List[SearchResult], query: str, limit: int, max_per_domain: int = 1) -> List[SearchResult]:
    scored: List[SearchResult] = []
    for r in results:
        r.score = 0.5 * score_relevance(query, r.title or "", r.snippet or "") + 0.5 * (r.score or 0.0)
        scored.append(r)
    scored.sort(key=lambda x: x.score, reverse=True)
    # Diversify by domain
    indices = diversify_by_domain([r.url for r in scored], max_per_domain=max_per_domain)
    diversified = [scored[i] for i in indices]
    return diversified[:limit]


def run(
    query: str,
    n: int = 8,
    provider_list: str = "tavily,ddg",
    llm: str = "auto",
    json_out: bool = False,
    max_per_domain: int = 1,
    recency_weight: float = 0.35,
    follow: int = 0,
    quotes_k: int = 0,
) -> Dict[str, Any]:
    providers = [p.strip() for p in provider_list.split(",") if p.strip()]
    results = composite_search(query, max_results=max(10, n), providers=providers)

    # Optional follow-up passes to broaden coverage
    base_results = list(results)
    subqueries: List[str] = []
    if follow > 0:
        subqueries = propose_followups(query, base_results)[: max(2, min(6, follow * 3))]
        for sq in subqueries:
            extra = composite_search(sq, max_results=6, providers=providers)
            # Merge; composite_search already dedupes internally per call
            results.extend(extra)
            # Deduplicate across calls by URL
            seen = set()
            uniq = []
            for r in results:
                if r.url and r.url not in seen:
                    seen.add(r.url)
                    uniq.append(r)
            results = uniq

    results = pick_top(results, query, limit=max(n, len(results)), max_per_domain=max_per_domain)
    results = results[:n]

    docs: List[SourceDoc] = []
    tmp_docs: List[SourceDoc] = []
    for r in results:
        page = extract(r.url)
        tmp_docs.append(
            SourceDoc(index=0, title=page.title or r.title or None, url=r.url, published=page.published or r.published, text=page.text)
        )

    # Re-rank docs with recency weighting
    def doc_score(d: SourceDoc) -> float:
        rel = score_relevance(query, d.title or "", (d.text or "")[:400])
        rec = recency_score(d.published)
        return (1 - recency_weight) * rel + recency_weight * rec

    tmp_docs.sort(key=doc_score, reverse=True)
    for idx, d in enumerate(tmp_docs, start=1):
        d.index = idx
        docs.append(d)

    # Choose LLM provider
    chosen_llm = None
    if llm == "auto":
        if _llm_available("openai"):
            chosen_llm = "openai"
        elif _llm_available("anthropic"):
            chosen_llm = "anthropic"
    elif llm in ("openai", "anthropic"):
        if _llm_available(llm):
            chosen_llm = llm

    if chosen_llm:
        answer = summarize_with_llm(query, docs, provider=chosen_llm)
        mode = f"llm:{chosen_llm}"
    else:
        answer = summarize_extractive(query, docs)
        mode = "extractive"

    quotes: List[Dict[str, Any]] = []
    if quotes_k and docs:
        for s, idx in extract_quotes(query, docs, k=quotes_k):
            quotes.append({"quote": s, "index": idx})

    payload: Dict[str, Any] = {
        "query": query,
        "mode": mode,
        "answer": answer,
        "sources": [
            {
                "index": d.index,
                "title": d.title,
                "url": d.url,
                "published": d.published,
            }
            for d in docs
        ],
        "stats": {
            "providers": providers,
            "num_sources": len(docs),
            "followups": subqueries,
        },
    }
    if quotes:
        payload["quotes"] = quotes
    if json_out:
        return payload

    # Pretty print formatting as text
    lines = []
    lines.append(f"Question: {query}")
    lines.append("")
    lines.append("Answer:")
    lines.append(answer)
    lines.append("")
    lines.append("Sources:")
    for d in docs:
        title = d.title or "(no title)"
        if d.published:
            title = f"{title} — {d.published}"
        lines.append(f"[{d.index}] {title}\n{d.url}")
    if quotes:
        lines.append("")
        lines.append("Key Quotes:")
        for q in quotes:
            lines.append(f"- {q['quote']} [{q['index']}]")
    payload["text"] = "\n".join(lines)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(prog="research", description="Web research with citations (Perplexity-style)")
    parser.add_argument("query", help="Research question or query")
    parser.add_argument("-n", "--num", type=int, default=8, help="Number of sources to retrieve")
    parser.add_argument("--providers", default="tavily,ddg", help="Comma-separated providers: tavily,ddg")
    parser.add_argument("--llm", default="auto", choices=["auto", "off", "openai", "anthropic"], help="Summarization mode")
    parser.add_argument("--max-per-domain", type=int, default=1, help="Limit per domain for diversity")
    parser.add_argument("--recency", type=float, default=0.35, help="Weight for recency in doc ranking [0-1]")
    parser.add_argument("--follow", type=int, default=0, help="Follow-up passes to broaden coverage")
    parser.add_argument("--quotes", type=int, default=0, help="Extract top-K supporting quotes")
    parser.add_argument("--json", action="store_true", help="Output JSON payload instead of text")
    args = parser.parse_args()

    payload = run(
        query=args.query,
        n=args.num,
        provider_list=args.providers,
        llm=(args.llm if args.llm != "off" else ""),
        json_out=args.json,
        max_per_domain=args.max_per_domain,
        recency_weight=max(0.0, min(1.0, args.recency)),
        follow=max(0, args.follow),
        quotes_k=max(0, args.quotes),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload["text"])


if __name__ == "__main__":
    main()
