"""Quotes to Scrape: all source-specific selectors live in this file."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from http_client import FetchError, HttpClient
from schema import SOURCE_QUOTES

log = logging.getLogger(__name__)


def parse_page(html: str, page_url: str) -> Tuple[List[dict], int, Optional[str]]:
    """Return (raw quote dicts, skipped count, absolute next-page URL or None)."""
    soup = BeautifulSoup(html, "html.parser")
    items: List[dict] = []
    skipped = 0
    for block in soup.select("div.quote"):
        try:
            text_tag = block.select_one("span.text")
            if text_tag is None:
                raise ValueError("quote text missing")
            author_tag = block.select_one("small.author")
            author_link = block.select_one("a[href^='/author/']")
            items.append({
                "source": SOURCE_QUOTES,
                "source_url": page_url,  # quotes have no page of their own
                "name_or_title": text_tag.get_text(strip=True),
                "author": author_tag.get_text(strip=True) if author_tag else None,
                "_author_url": urljoin(page_url, author_link["href"]) if author_link else None,
                "tags": [t.get_text(strip=True) for t in block.select("div.tags a.tag")],
            })
        except Exception as exc:
            skipped += 1
            log.warning("Skipping unparseable quote on %s: %s", page_url, exc)

    next_link = soup.select_one("li.next a")
    next_url = urljoin(page_url, next_link["href"]) if next_link and next_link.get("href") else None
    return items, skipped, next_url


def parse_author(html: str) -> Optional[str]:
    """'<born date> <born location>' from an author page; None if neither is present."""
    soup = BeautifulSoup(html, "html.parser")
    parts = []
    for selector in (".author-born-date", ".author-born-location"):
        tag = soup.select_one(selector)
        if tag is not None and tag.get_text(strip=True):
            parts.append(tag.get_text(" ", strip=True))
    return " ".join(parts) or None


class QuotesScraper:
    name = SOURCE_QUOTES

    def __init__(self, client: HttpClient, base_url: str, max_pages: Optional[int] = None,
                 fetch_details: bool = True):
        self.client = client
        self.base_url = base_url
        self.max_pages = max_pages
        self.fetch_details = fetch_details
        self._author_cache: Dict[str, Optional[str]] = {}
        self.stats = {"pages_scraped": 0, "pages_failed": 0, "items_skipped": 0, "detail_failures": 0}

    def scrape(self) -> Iterator[dict]:
        url: Optional[str] = self.base_url
        visited = set()
        while url and url not in visited:
            if self.max_pages is not None and self.stats["pages_scraped"] >= self.max_pages:
                log.info("[quotes] max_pages=%s reached", self.max_pages)
                break
            visited.add(url)
            try:
                html = self.client.get(url)
            except FetchError as exc:
                self.stats["pages_failed"] += 1
                log.error("[quotes] page failed, stopping this source: %s", exc)
                break

            items, skipped, next_url = parse_page(html, url)
            self.stats["pages_scraped"] += 1
            self.stats["items_skipped"] += skipped
            log.info("[quotes] page %d: %d items (%s)", self.stats["pages_scraped"], len(items), url)

            for item in items:
                author_url = item.pop("_author_url", None)
                item["author_born"] = self._author_born(author_url) if self.fetch_details else None
                item["scraped_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                yield item
            url = next_url

    def _author_born(self, author_url: Optional[str]) -> Optional[str]:
        if not author_url:
            return None
        if author_url not in self._author_cache:  # each author page is fetched once
            try:
                self._author_cache[author_url] = parse_author(self.client.get(author_url))
            except FetchError as exc:
                self.stats["detail_failures"] += 1
                log.warning("[quotes] author page failed: %s", exc)
                self._author_cache[author_url] = None  # cache the failure: don't hammer the server
        return self._author_cache[author_url]
