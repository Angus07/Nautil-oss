"""Web tools: web_search and web_fetch — ported from nanobot."""
from __future__ import annotations

import html
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from .base import Tool

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"
MAX_REDIRECTS = 5


def _strip_tags(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _validate_url(url: str) -> tuple[bool, str]:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
        if not p.netloc:
            return False, "Missing domain"
        return True, ""
    except Exception as e:
        return False, str(e)


class WebSearchTool(Tool):
    """Search the web using Brave Search API."""

    def __init__(
        self,
        api_key: str | None = None,
        max_results: int = 5,
        proxy: str | None = None,
    ):
        self._init_api_key = api_key
        self.max_results = max_results
        self.proxy = proxy

    @property
    def api_key(self) -> str:
        return self._init_api_key or os.environ.get("BRAVE_API_KEY", "")

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the internet and return titles, URLs, and snippets. Use for obtaining up-to-date information and facts."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "count": {
                    "type": "integer",
                    "description": "Number of results to return (1-10)",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        }

    @property
    def searxng_url(self) -> str:
        return os.environ.get("SEARXNG_URL", "")

    async def execute(self, query: str, count: int | None = None, **kw: Any) -> str:
        n = min(max(count or self.max_results, 1), 10)
        if self.api_key:
            return await self._brave_search(query, n)
        if self.searxng_url:
            return await self._searxng_search(query, n)
        return "Error: No search engine configured. Please set BRAVE_API_KEY or SEARXNG_URL."

    async def _brave_search(self, query: str, n: int) -> str:
        try:
            async with httpx.AsyncClient(proxy=self.proxy) as client:
                r = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": n},
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": self.api_key,
                    },
                    timeout=10.0,
                )
                r.raise_for_status()

            results = r.json().get("web", {}).get("results", [])[:n]
            if not results:
                return f"No results for: {query}"

            lines = [f"Results for: {query}\n"]
            for i, item in enumerate(results, 1):
                lines.append(
                    f"{i}. {item.get('title', '')}\n   {item.get('url', '')}"
                )
                if desc := item.get("description"):
                    lines.append(f"   {desc}")
            return "\n".join(lines)
        except Exception as e:
            if self.searxng_url:
                return await self._searxng_search(query, n)
            return f"Brave search error: {e}"

    async def _searxng_search(self, query: str, n: int) -> str:
        """Fallback: query local SearXNG instance JSON API."""
        base = self.searxng_url.rstrip("/")
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=15.0, proxy=self.proxy,
            ) as client:
                r = await client.get(
                    f"{base}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "categories": "general",
                        "language": "en",
                    },
                    headers={"User-Agent": USER_AGENT},
                )
                r.raise_for_status()

            data = r.json()
            results = data.get("results", [])[:n]
            if not results:
                return f"No results for: {query}"

            lines = [f"Results for: {query}  (via SearXNG)\n"]
            for i, item in enumerate(results, 1):
                title = item.get("title", "")
                url = item.get("url", "")
                desc = item.get("content", "")
                lines.append(f"{i}. {title}\n   {url}")
                if desc:
                    lines.append(f"   {desc}")
            return "\n".join(lines)
        except Exception as e:
            return f"SearXNG search error: {e}"


class WebFetchTool(Tool):
    """Fetch and extract content from a URL."""

    def __init__(self, max_chars: int = 50000, proxy: str | None = None):
        self.max_chars = max_chars
        self.proxy = proxy

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch the content of a specified URL, extract the body text, and convert to readable text. Use for obtaining detailed webpage information."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "extractMode": {
                    "type": "string",
                    "enum": ["markdown", "text"],
                    "description": "Extraction mode, default: markdown",
                },
                "maxChars": {
                    "type": "integer",
                    "minimum": 100,
                    "description": "Maximum characters to return",
                },
            },
            "required": ["url"],
        }

    async def execute(
        self,
        url: str,
        extractMode: str = "markdown",
        maxChars: int | None = None,
        **kw: Any,
    ) -> str:
        max_chars = maxChars or self.max_chars
        is_valid, error_msg = _validate_url(url)
        if not is_valid:
            return json.dumps(
                {"error": f"URL validation failed: {error_msg}", "url": url},
                ensure_ascii=False,
            )
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                max_redirects=MAX_REDIRECTS,
                timeout=30.0,
                proxy=self.proxy,
            ) as client:
                r = await client.get(url, headers={"User-Agent": USER_AGENT})
                r.raise_for_status()

            ctype = r.headers.get("content-type", "")

            if "application/json" in ctype:
                text, extractor = (
                    json.dumps(r.json(), indent=2, ensure_ascii=False),
                    "json",
                )
            elif "text/html" in ctype or r.text[:256].lower().startswith(
                ("<!doctype", "<html")
            ):
                text, extractor = self._extract_html(r.text, extractMode)
            else:
                text, extractor = r.text, "raw"

            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]

            return json.dumps(
                {
                    "url": url,
                    "status": r.status_code,
                    "extractor": extractor,
                    "truncated": truncated,
                    "length": len(text),
                    "text": text,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)

    def _extract_html(self, raw: str, mode: str) -> tuple[str, str]:
        try:
            from readability import Document

            doc = Document(raw)
            summary = doc.summary()
            title = doc.title()
            if mode == "markdown":
                content = self._to_markdown(summary)
            else:
                content = _strip_tags(summary)
            text = f"# {title}\n\n{content}" if title else content
            return text, "readability"
        except ImportError:
            content = _strip_tags(raw)
            return _normalize(content), "fallback"

    def _to_markdown(self, raw_html: str) -> str:
        text = re.sub(
            r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            lambda m: f"[{_strip_tags(m[2])}]({m[1]})",
            raw_html,
            flags=re.I,
        )
        text = re.sub(
            r"<h([1-6])[^>]*>([\s\S]*?)</h\1>",
            lambda m: f'\n{"#" * int(m[1])} {_strip_tags(m[2])}\n',
            text,
            flags=re.I,
        )
        text = re.sub(
            r"<li[^>]*>([\s\S]*?)</li>",
            lambda m: f"\n- {_strip_tags(m[1])}",
            text,
            flags=re.I,
        )
        text = re.sub(r"</(p|div|section|article)>", "\n\n", text, flags=re.I)
        text = re.sub(r"<(br|hr)\s*/?>", "\n", text, flags=re.I)
        return _normalize(_strip_tags(text))
