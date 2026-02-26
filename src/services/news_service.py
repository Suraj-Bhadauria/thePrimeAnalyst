"""
src/services/news_service.py

Lightweight news service that fetches headlines from Google News RSS.
Uses only standard library — no extra dependencies required.
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time
import re
from datetime import datetime
from typing import List, Dict, Optional


class GoogleNewsService:
    """Fetches relevant news headlines from Google News RSS feed."""

    _BASE_URL = "https://news.google.com/rss/search"

    def __init__(
        self,
        use_live_feed: bool = True,
        cache_duration_minutes: int = 15,
        max_results: int = 3,
        timeout_seconds: int = 5,
    ):
        self._live = use_live_feed
        self._cache_ttl = cache_duration_minutes * 60  # seconds
        self._max = max_results
        self._timeout = timeout_seconds
        self._cache: Dict[str, dict] = {}  # query -> {ts, items}

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def get_relevant_news(self, query: str) -> List[Dict[str, str]]:
        """
        Return a list of news items related to ``query``.

        Each item has keys: headline, source, time, category.
        Returns [] on any failure so the UI always stays stable.
        """
        if not self._live or not query or not query.strip():
            return []

        # Normalise the query for caching
        cache_key = query.strip().lower()

        # Return cached results if still fresh
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached["ts"]) < self._cache_ttl:
            return cached["items"]

        items = self._fetch(query)
        self._cache[cache_key] = {"ts": time.time(), "items": items}
        return items

    # ------------------------------------------------------------------ #
    # Private
    # ------------------------------------------------------------------ #
    def _fetch(self, query: str) -> List[Dict[str, str]]:
        """Fetch from Google News RSS and parse into a simple list."""
        try:
            # Build a finance / fintech oriented search query
            search_q = f"{query} fintech payments UPI India"
            params = urllib.parse.urlencode({
                "q": search_q,
                "hl": "en-IN",
                "gl": "IN",
                "ceid": "IN:en",
            })
            url = f"{self._BASE_URL}?{params}"

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            items: List[Dict[str, str]] = []

            for item_el in root.iter("item"):
                if len(items) >= self._max:
                    break

                title = (item_el.findtext("title") or "").strip()
                pub_date = (item_el.findtext("pubDate") or "").strip()
                source_el = item_el.find("source")
                source = source_el.text.strip() if source_el is not None and source_el.text else ""

                # Extract readable time
                time_str = self._relative_time(pub_date)

                # Infer category from keywords
                category = self._infer_category(title, query)

                items.append({
                    "headline": self._clean_html(title),
                    "source": source,
                    "time": time_str,
                    "category": category,
                })

            return items

        except Exception:
            # Network errors, XML errors, timeouts — all silently return []
            return []

    @staticmethod
    def _relative_time(pub_date_str: str) -> str:
        """Convert an RSS pubDate string to a human-friendly relative time."""
        if not pub_date_str:
            return "Recently"
        try:
            # RSS date format: "Tue, 25 Feb 2026 12:34:00 GMT"
            dt = datetime.strptime(pub_date_str.strip(), "%a, %d %b %Y %H:%M:%S %Z")
            diff = datetime.utcnow() - dt
            minutes = int(diff.total_seconds() / 60)
            if minutes < 60:
                return f"{minutes}m ago"
            hours = minutes // 60
            if hours < 24:
                return f"{hours}h ago"
            days = hours // 24
            return f"{days}d ago"
        except Exception:
            return "Recently"

    @staticmethod
    def _clean_html(text: str) -> str:
        """Strip HTML tags from text."""
        return re.sub(r"<[^>]+>", "", text)

    @staticmethod
    def _infer_category(title: str, query: str) -> str:
        """Simple keyword-based category tagging."""
        title_lower = title.lower()
        if any(w in title_lower for w in ["fraud", "scam", "hack", "breach", "cybersecurity"]):
            return "Security"
        if any(w in title_lower for w in ["rbi", "regulation", "policy", "compliance", "sebi"]):
            return "Regulation"
        if any(w in title_lower for w in ["upi", "payment", "wallet", "fintech", "transaction"]):
            return "Payments"
        if any(w in title_lower for w in ["revenue", "profit", "growth", "market", "stock"]):
            return "Business"
        if any(w in title_lower for w in ["ai", "analytics", "data", "technology", "digital"]):
            return "Technology"
        return "News"
