"""Books to Scrape: all source-specific selectors live in this file."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from http_client import FetchError, HttpClient
from schema import SOURCE_BOOKS

log = logging.getLogger(__name__)


def parse_listing(html: str, page_url: str) -> Tuple[List[dict], int, Optional[str]]:
    """Return (raw book dicts, number of skipped items, absolute next-page URL or None)."""
    soup = BeautifulSoup(html, "html.parser")
    items: List[dict] = []
    skipped = 0
    for article in soup.select("article.product_pod"):
        try:
            link = article.select_one("h3 a")
            if link is None or not link.get("href"):
                raise ValueError("product link missing")
            title = link.get("title") or link.get_text(strip=True)  # title attr is not truncated

            price_tag = article.select_one("p.price_color")
            avail_tag = article.select_one("p.availability")
            rating_tag = article.select_one("p.star-rating")
            rating = None
            if rating_tag is not None:
                rating = next((c for c in rating_tag.get("class", []) if c != "star-rating"), None)

            items.append({
                "source": SOURCE_BOOKS,
                "source_url": urljoin(page_url, link["href"]),
                "name_or_title": title,
                "price": price_tag.get_text(strip=True) if price_tag else None,
                "rating": rating,
                "availability": avail_tag.get_text(" ", strip=True) if avail_tag else None,
                "category": None,
                "description": None,
            })
        except Exception as exc:  # one bad card must not kill the page
            skipped += 1
            log.warning("Skipping unparseable book card on %s: %s", page_url, exc)

    next_link = soup.select_one("li.next a")
    next_url = urljoin(page_url, next_link["href"]) if next_link and next_link.get("href") else None
    return items, skipped, next_url


def parse_detail(html: str) -> Dict[str, Optional[str]]:
    """Extract category (breadcrumb) and description from a product page."""
    soup = BeautifulSoup(html, "html.parser")
    crumbs = [li.get_text(" ", strip=True) for li in soup.select("ul.breadcrumb li")]
    category = crumbs[2] if len(crumbs) >= 4 else None  # Home / Books / <Category> / <Title>

    description = None
    header = soup.select_one("#product_description")
    if header is not None:
        para = header.find_next_sibling("p")
        if para is not None:
            description = para.get_text(" ", strip=True)
    return {"category": category, "description": description}


class BooksScraper:
    name = SOURCE_BOOKS

    def __init__(self, client: HttpClient, base_url: str, max_pages: Optional[int] = None,
                 fetch_details: bool = True):
        self.client = client
        self.base_url = base_url
        self.max_pages = max_pages
        self.fetch_details = fetch_details
        self.stats = {"pages_scraped": 0, "pages_failed": 0, "items_skipped": 0, "detail_failures": 0}

    def scrape(self) -> Iterator[dict]:
        url: Optional[str] = self.base_url
        visited = set()
        while url and url not in visited:
            if self.max_pages is not None and self.stats["pages_scraped"] >= self.max_pages:
                log.info("[books] max_pages=%s reached", self.max_pages)
                break
            visited.add(url)
            try:
                html = self.client.get(url)
            except FetchError as exc:
                # Without the page we cannot read its "next" link, so pagination stops here.
                self.stats["pages_failed"] += 1
                log.error("[books] listing page failed, stopping this source: %s", exc)
                break

            items, skipped, next_url = parse_listing(html, url)
            self.stats["pages_scraped"] += 1
            self.stats["items_skipped"] += skipped
            log.info("[books] page %d: %d items (%s)", self.stats["pages_scraped"], len(items), url)

            for item in items:
                if self.fetch_details:
                    self._enrich(item)
                item["scraped_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                yield item
            url = next_url

    def _enrich(self, item: dict) -> None:
        try:
            detail = parse_detail(self.client.get(item["source_url"]))
            item["category"] = detail["category"]
            item["description"] = detail["description"]
        except FetchError as exc:
            self.stats["detail_failures"] += 1
            log.warning("[books] detail page failed, keeping listing data only: %s", exc)
