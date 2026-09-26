import os
import time
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: Optional[str] = None
    source: str = ""
    score: float = 0.0
    published: Optional[str] = None


class BaseSearch:
    name = "base"

    def available(self) -> bool:
        return True

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        raise NotImplementedError


class DuckDuckGoSearch(BaseSearch):
    name = "ddg"

    def __init__(self) -> None:
        try:
            from duckduckgo_search import DDGS  # type: ignore
            self._DDGS = DDGS
            self._ok = True
        except Exception:
            self._ok = False

    def available(self) -> bool:
        return self._ok

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if not self._ok:
            return []
        results: List[SearchResult] = []
        # DDG sometimes rate-limits; a small sleep helps when batched
        try:
            with self._DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results, region="wt-wt", safesearch="moderate"):
                    results.append(
                        SearchResult(
                            title=r.get("title") or r.get("source") or "",
                            url=r.get("href") or r.get("url") or "",
                            snippet=r.get("body") or r.get("snippet"),
                            source=self.name,
                            score=0.0,
                        )
                    )
        except Exception:
            time.sleep(0.25)
        return results


class TavilySearch(BaseSearch):
    name = "tavily"

    def __init__(self) -> None:
        self._key = os.getenv("TAVILY_API_KEY")
        self._client = None
        if self._key:
            try:
                from tavily import TavilyClient  # type: ignore
                self._client = TavilyClient(api_key=self._key)
            except Exception:
                self._client = None

    def available(self) -> bool:
        return self._client is not None

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if not self._client:
            return []
        results: List[SearchResult] = []
        try:
            data = self._client.search(query, max_results=max_results, include_answer=False)
            # Tavily returns a dict with "results"
            items = data.get("results", []) if isinstance(data, dict) else data
            for r in items[:max_results]:
                results.append(
                    SearchResult(
                        title=r.get("title") or "",
                        url=r.get("url") or "",
                        snippet=r.get("content") or r.get("snippet"),
                        source=self.name,
                        score=float(r.get("score") or 0.0),
                        published=r.get("published_date") or r.get("date"),
                    )
                )
        except Exception:
            pass
        return results


class BraveSearch(BaseSearch):
    name = "brave"

    def __init__(self) -> None:
        self._key = os.getenv("BRAVE_API_KEY")
        try:
            import httpx  # noqa: F401
            self._http_ok = True
        except Exception:
            self._http_ok = False

    def available(self) -> bool:
        return bool(self._key and self._http_ok)

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if not self.available():
            return []
        import httpx

        headers = {"X-Subscription-Token": self._key}
        params = {"q": query, "count": max_results, "country": "us"}
        results: List[SearchResult] = []
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get("https://api.search.brave.com/res/v1/web/search", headers=headers, params=params)
                if r.status_code != 200:
                    return []
                data = r.json()
                for it in (data.get("web", {}) or {}).get("results", [])[:max_results]:
                    results.append(
                        SearchResult(
                            title=it.get("title") or "",
                            url=it.get("url") or "",
                            snippet=it.get("description") or "",
                            source=self.name,
                            score=float(it.get("rankAbsolute") or 0.0),
                            published=(it.get("age") or {}).get("publishedDate") or None,
                        )
                    )
        except Exception:
            pass
        return results


class SerpAPISearch(BaseSearch):
    name = "serpapi"

    def __init__(self) -> None:
        self._key = os.getenv("SERPAPI_API_KEY")
        try:
            import httpx  # noqa: F401
            self._http_ok = True
        except Exception:
            self._http_ok = False

    def available(self) -> bool:
        return bool(self._key and self._http_ok)

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if not self.available():
            return []
        import httpx

        params = {
            "engine": "google",
            "q": query,
            "api_key": self._key,
            "num": max_results,
            "hl": "en",
        }
        results: List[SearchResult] = []
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get("https://serpapi.com/search.json", params=params)
                if r.status_code != 200:
                    return []
                data = r.json()
                for it in data.get("organic_results", [])[:max_results]:
                    results.append(
                        SearchResult(
                            title=it.get("title") or "",
                            url=it.get("link") or "",
                            snippet=it.get("snippet") or "",
                            source=self.name,
                            score=float(it.get("position") or 0.0),
                            published=it.get("date") or None,
                        )
                    )
        except Exception:
            pass
        return results


def composite_search(query: str, max_results: int = 8, providers: Optional[List[str]] = None) -> List[SearchResult]:
    order = providers or ["tavily", "brave", "serpapi", "ddg"]
    provider_impls: List[BaseSearch] = []
    for p in order:
        if p == "tavily":
            provider_impls.append(TavilySearch())
        elif p == "brave":
            provider_impls.append(BraveSearch())
        elif p == "serpapi":
            provider_impls.append(SerpAPISearch())
        elif p == "ddg":
            provider_impls.append(DuckDuckGoSearch())
    results: List[SearchResult] = []
    for impl in provider_impls:
        if impl.available():
            got = impl.search(query, max_results=max_results)
            results.extend(got)
    # Basic dedupe by URL
    seen = set()
    unique: List[SearchResult] = []
    for r in results:
        key = r.url.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique[: max_results]
