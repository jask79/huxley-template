Research CLI (Perplexity-style)

Features
- Multi-provider search: DuckDuckGo (no key), Tavily (if `TAVILY_API_KEY`).
- Optional providers: Brave (`BRAVE_API_KEY`), SerpAPI Google (`SERPAPI_API_KEY`).
- Clean extraction: BeautifulSoup cleanup for HTML, PDF via `pypdf`.
- Ranking: query relevance + recency; domain diversification.
- Follow-ups: optional multi-hop sub-queries to broaden coverage (`--follow`).
- Quotes: extracts top supporting quotes with citations (`--quotes`).
- Summarization: LLM (OpenAI/Anthropic if keys present) or extractive fallback (LexRank).
- Outputs a concise answer with bracketed citations and a source list, or JSON.

Quickstart
1) Install deps:
   pip install -r tools/research/requirements.txt

2) Optional: set API keys for stronger results/summaries:
   export TAVILY_API_KEY=...
   export OPENAI_API_KEY=...    # or ANTHROPIC_API_KEY=...
   export BRAVE_API_KEY=...     # optional
   export SERPAPI_API_KEY=...   # optional

3) Run queries:
   python -m tools.research.cli "latest on Llama 4 release timeline" -n 8 --providers tavily,ddg --llm auto --follow 1 --quotes 5

   JSON output:
   python -m tools.research.cli "EU AI Act conformity deadlines" --json --llm off --max-per-domain 1 --recency 0.4

Codex integration
- JSON bridge (stdin → stdout):
  echo '{"query":"AI safety evals", "n":8, "providers":"tavily,brave,ddg", "llm":"auto", "quotes":4}' | \
    python -m tools.research.bridge --stdin --pretty

Flags
- `--max-per-domain`: diversify sources by domain (default 1).
- `--recency`: weight for recency in doc ranking [0–1], default 0.35.
- `--follow`: number of follow-up passes (0 = off). Heuristic sub-queries are generated from titles and domains.
- `--quotes`: top-K supporting quotes to extract and print.

Notes
- Without keys, it uses DuckDuckGo and extractive summaries.
- Respect sites’ robots/ToS. Avoid high-rate scraping.
- Cache is stored under `~/.cache/codex-research`.
