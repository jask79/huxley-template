from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .utils import split_sentences, score_sentence


@dataclass
class SourceDoc:
    index: int
    title: Optional[str]
    url: str
    published: Optional[str]
    text: str


def _llm_available(provider: str) -> bool:
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    return False


def summarize_with_llm(question: str, docs: List[SourceDoc], provider: str = "openai", model: Optional[str] = None) -> str:
    content_blocks = []
    for d in docs:
        # Truncate per doc to reduce prompt size
        snippet = d.text[:5000]
        content_blocks.append(f"[{d.index}] {d.title or ''} — {d.url}\n{snippet}")
    joined = "\n\n".join(content_blocks)
    prompt = (
        "You are a meticulous research assistant. Use the sources below to answer the question. "
        "Cite with bracketed numbers like [1], [2] matching the source indices. If unsure, say so.\n\n"
        f"Question: {question}\n\nSources:\n{joined}\n\nAnswer:"
    )

    if provider == "openai":
        # Prefer small, fast reasoning-safe model name if available; fallback
        model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI()
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"[LLM error: {e}]\n\nNon-LLM fallback not attempted."
    elif provider == "anthropic":
        model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
        try:
            import anthropic  # type: ignore

            client = anthropic.Anthropic()
            resp = client.messages.create(
                model=model,
                max_tokens=800,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip()
        except Exception as e:
            return f"[LLM error: {e}]\n\nNon-LLM fallback not attempted."
    return "[Unsupported LLM provider]"


def summarize_extractive(question: str, docs: List[SourceDoc], max_sentences: int = 10) -> str:
    # Use LexRank (sumy) as a decent extractive baseline, with per-source sentence tagging
    try:
        from sumy.nlp.tokenizers import Tokenizer  # type: ignore
        from sumy.parsers.plaintext import PlaintextParser  # type: ignore
        from sumy.summarizers.lex_rank import LexRankSummarizer  # type: ignore
    except Exception:
        # Fallback: pick first N informative sentences per doc
        return simple_fallback_summary(question, docs, max_sentences)

    joined_text = "\n\n".join([f"[{d.index}]\n{d.text}" for d in docs])
    parser = PlaintextParser.from_string(joined_text, Tokenizer("english"))
    summarizer = LexRankSummarizer()
    summary_sents = summarizer(parser.document, max_sentences)
    sents = [str(s) for s in summary_sents]

    # Attempt to map sentences back to sources by nearest preceding [idx] marker
    mapping = []
    current_idx = None
    for s in sents:
        m = re.search(r"\[(\d+)\]", s)
        if m:
            current_idx = int(m.group(1))
            clean = re.sub(r"\s*\[\d+\]\s*", " ", s).strip()
            mapping.append((clean, current_idx))
        else:
            mapping.append((s.strip(), current_idx or 1))

    lines = [f"Question: {question}", "", "Summary:"]
    for sent, idx in mapping:
        lines.append(f"- {sent} [{idx}]")
    return "\n".join(lines)


def simple_fallback_summary(question: str, docs: List[SourceDoc], max_sentences: int = 10) -> str:
    # Naive heuristic: pick leading sentences containing query terms from top docs
    import itertools

    terms = [t.lower() for t in re.findall(r"\w+", question) if len(t) > 3]
    picks: List[Tuple[str, int]] = []
    for d in docs:
        sentences = re.split(r"(?<=[.!?])\s+", d.text)
        for s in sentences[:50]:
            score = sum(s.lower().count(t) for t in terms)
            if score > 0 and len(s) > 40:
                picks.append((s.strip(), d.index))
    picks = picks[: max_sentences]
    lines = [f"Question: {question}", "", "Summary:"]
    for s, idx in picks:
        lines.append(f"- {s} [{idx}]")
    if not picks:
        # fallback to first sentences of first doc
        if docs:
            sentences = re.split(r"(?<=[.!?])\s+", docs[0].text)
            for s in itertools.islice(sentences, 0, max_sentences):
                lines.append(f"- {s.strip()} [1]")
    return "\n".join(lines)


def extract_quotes(question: str, docs: List[SourceDoc], k: int = 6) -> List[Tuple[str, int]]:
    # Return top-k sentences with highest query-term scores with their source index
    import heapq
    import re as _re

    terms = [t.lower() for t in _re.findall(r"\w+", question) if len(t) > 3]
    heap: List[Tuple[float, str, int]] = []
    for d in docs:
        for s in split_sentences(d.text)[:80]:
            sc = score_sentence(terms, s)
            if sc <= 0:
                continue
            # Keep a min-heap of size k
            if len(heap) < k:
                heapq.heappush(heap, (sc, s.strip(), d.index))
            else:
                if sc > heap[0][0]:
                    heapq.heapreplace(heap, (sc, s.strip(), d.index))
    # Sort descending by score
    heap.sort(key=lambda x: x[0], reverse=True)
    return [(s, idx) for sc, s, idx in heap]
