"""Web search done by the agent itself (used with Groq, which has no dependable built-in search).

Default: DuckDuckGo, no key needed. Better: add a free Tavily key in config.env (TAVILY_API_KEY).
Every source link the agent later shows comes from these results, never from the AI's memory.
"""
import time
from urllib.parse import urlparse

from . import config

SNIPPET_CHARS = 320


def _tavily(query: str, n: int):
    import httpx

    r = httpx.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {config.tavily_key()}"},
        json={"query": query, "max_results": n, "search_depth": "basic"},
        timeout=30,
    )
    r.raise_for_status()
    return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")}
            for x in r.json().get("results", [])]


def _ddg(query: str, n: int):
    from ddgs import DDGS

    rows = DDGS().text(query, region="in-en", max_results=n)
    return [{"title": x.get("title", ""), "url": x.get("href", ""), "snippet": x.get("body", "")} for x in rows or []]


def web_search(query: str, n: int = 5):
    """Returns a list of {title, url, snippet}. Retries once; returns [] if search keeps failing."""
    fn = _tavily if config.tavily_key() else _ddg
    for attempt in range(2):
        try:
            rows = fn(query, n)
            return [r for r in rows if r["url"].startswith("http")]
        except Exception:
            time.sleep(2 + 3 * attempt)
    return []


def gather(queries, per_query: int = 5, limit: int = 24):
    """Runs several searches and returns one de-duplicated, numbered-ready source list."""
    seen, out = set(), []
    for q in queries:
        for row in web_search(q, per_query):
            key = row["url"].split("#")[0].rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            row["snippet"] = " ".join((row["snippet"] or "").split())[:SNIPPET_CHARS]
            out.append(row)
            if len(out) >= limit:
                return out
    return out


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")
