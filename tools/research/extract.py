import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Optional, Tuple

import httpx


CACHE_DIR = os.path.expanduser("~/.cache/codex-research")
os.makedirs(CACHE_DIR, exist_ok=True)


@dataclass
class Page:
    url: str
    title: Optional[str]
    text: str
    content_type: Optional[str]
    published: Optional[str]


def _cache_paths(url: str) -> Tuple[str, str]:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.bin"), os.path.join(CACHE_DIR, f"{h}.meta.json")


def fetch(url: str, force: bool = False) -> Tuple[bytes, dict]:
    bin_path, meta_path = _cache_paths(url)
    if not force and os.path.exists(bin_path) and os.path.exists(meta_path):
        try:
            with open(bin_path, "rb") as bf:
                content = bf.read()
            with open(meta_path, "r", encoding="utf-8") as mf:
                meta = json.load(mf)
            return content, meta
        except Exception:
            pass
    headers = {
        "User-Agent": "Codex-Research/1.0 (+https://openai.com)"
    }
    with httpx.Client(follow_redirects=True, timeout=20.0, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        content = resp.content
        meta = {
            "url": str(resp.url),
            "status": resp.status_code,
            "content_type": resp.headers.get("content-type"),
        }
    try:
        with open(bin_path, "wb") as bf:
            bf.write(content)
        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(meta, mf)
    except Exception:
        pass
    return content, meta


def _is_pdf(url: str, content_type: Optional[str]) -> bool:
    if content_type and "pdf" in content_type.lower():
        return True
    return url.lower().endswith(".pdf")


def extract(url: str) -> Page:
    raw, meta = fetch(url)
    ctype = (meta.get("content_type") or "").split(";")[0].strip().lower()
    published = None
    title = None
    text = ""

    if _is_pdf(url, ctype):
        try:
            from pypdf import PdfReader  # type: ignore
            import io

            reader = PdfReader(io.BytesIO(raw))
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
            text = "\n".join(parts)
            title = None
        except Exception:
            text = ""
    else:
        # HTML or text
        html = None
        try:
            html = raw.decode("utf-8", errors="ignore")
        except Exception:
            html = None
        if html:
            try:
                import trafilatura  # type: ignore

                downloaded = trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=False,
                    include_links=False,
                    url=url,
                    favor_recall=True,
                    with_metadata=True,
                    output_format="json",
                )
                if downloaded:
                    data = json.loads(downloaded)
                    text = (data.get("text") or "").strip()
                    title = data.get("title")
                    published = data.get("date") or data.get("published_time")
            except Exception:
                pass
            if not text:
                # Fallback: basic BeautifulSoup clean
                try:
                    from bs4 import BeautifulSoup  # type: ignore

                    soup = BeautifulSoup(html, "html.parser")
                    if not title:
                        t = soup.find("title")
                        if t and t.text:
                            title = t.text.strip()
                    # Grab common publish-time metas if present
                    try:
                        if not published:
                            for prop in [
                                "article:published_time",
                                "og:updated_time",
                                "article:modified_time",
                                "pubdate",
                                "date",
                            ]:
                                m = soup.find("meta", attrs={"property": prop}) or soup.find(
                                    "meta", attrs={"name": prop}
                                )
                                if m and m.get("content"):
                                    published = m.get("content").strip()
                                    break
                    except Exception:
                        pass

                    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "form", "aside"]):
                        tag.extract()
                    text = re.sub(r"\s+", " ", soup.get_text(" ").strip())
                except Exception:
                    pass
    return Page(url=url, title=title, text=text or "", content_type=ctype, published=published)
