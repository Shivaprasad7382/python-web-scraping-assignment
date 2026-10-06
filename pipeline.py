"""Orchestration: scrape -> clean -> validate -> deduplicate -> consolidate -> write."""
from __future__ import annotations

import csv
import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from config import Config
from http_client import HttpClient
from processing.cleaning import clean_record
from processing.deduplication import deduplicate
from processing.validation import validate_records
from schema import SCHEMA_FIELDS, SOURCE_BOOKS, SOURCE_QUOTES
from scrapers.books_scraper import BooksScraper
from scrapers.quotes_scraper import QuotesScraper

log = logging.getLogger(__name__)


def _write_csv(path: Path, rows: List[dict], fields: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", restval="")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            if isinstance(out.get("tags"), list):
                out["tags"] = "|".join(out["tags"])
            writer.writerow(out)


def run(cfg: Config, client: Optional[HttpClient] = None) -> dict:
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    client = client or HttpClient(cfg)
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scrapers = [
        BooksScraper(client, cfg.books_url, cfg.max_pages, cfg.fetch_details),
        QuotesScraper(client, cfg.quotes_url, cfg.max_pages, cfg.fetch_details),
    ]

    # 1) SCRAPE - a crash in one source never discards the other source
    raw_records: List[dict] = []
    scraper_stats = {}
    for scraper in scrapers:
        log.info("=== Scraping %s ===", scraper.name)
        try:
            for item in scraper.scrape():
                raw_records.append(item)
        except Exception:
            scraper.stats["crashed"] = True
            log.exception("Scraper for %s crashed; keeping what was collected so far", scraper.name)
        scraper_stats[scraper.name] = scraper.stats

    # 2) CLEAN
    cleaned, rejected = [], []
    for raw in raw_records:
        try:
            cleaned.append(clean_record(raw))
        except Exception as exc:
            log.warning("Cleaning failed for %s: %s", raw.get("source_url"), exc)
            rejected.append({"record": {"source": raw.get("source"),
                                        "source_url": raw.get("source_url"),
                                        "name_or_title": raw.get("name_or_title")},
                             "errors": [f"cleaning error: {exc}"]})
    cleaning_failures = len(rejected)

    # 3) VALIDATE
    valid, invalid = validate_records(cleaned)
    rejected.extend(invalid)

    # 4) DEDUPLICATE
    unique, duplicates = deduplicate(valid)

    # 5) WRITE
    _write_csv(out_dir / "final_dataset.csv", unique, SCHEMA_FIELDS)
    _write_csv(out_dir / "rejected_records.csv",
               [{**r["record"], "errors": "; ".join(r["errors"])} for r in rejected],
               SCHEMA_FIELDS + ["errors"])
    _write_csv(out_dir / "duplicate_records.csv", duplicates,
               SCHEMA_FIELDS + ["duplicate_of", "duplicate_rule"])

    # 6) SUMMARY
    def count(rows, source):
        return sum(1 for r in rows if r.get("source") == source)

    per_source = {}
    for name in (SOURCE_BOOKS, SOURCE_QUOTES):
        per_source[name] = {
            "records_collected": count(raw_records, name),
            "records_after_cleaning": count(cleaned, name),
            "records_rejected_validation": count([r["record"] for r in invalid], name),
            "duplicates_detected_and_removed": count(duplicates, name),
            "final_records": count(unique, name),
            "scraper_stats": scraper_stats.get(name, {}),
        }

    reasons = Counter(err for r in rejected for err in r["errors"])
    duplicate_rules = Counter(d["duplicate_rule"] for d in duplicates)
    summary = {
        "run": {
            "started_at": started.isoformat(timespec="seconds"),
            "execution_seconds": round(time.perf_counter() - t0, 2),
            "config": cfg.public_dict(),
        },
        "per_source": per_source,
        "totals": {
            "records_collected": len(raw_records),
            "records_after_cleaning": len(cleaned),
            "cleaning_failures": cleaning_failures,
            "records_rejected_validation": len(invalid),
            "duplicates_detected_and_removed": len(duplicates),
            "final_records": len(unique),
        },
        "rejection_reasons": dict(reasons),
        "duplicates_by_rule": dict(duplicate_rules),
        "http": {"requests_made": client.requests_made, "retries": client.retries},
        "duplicate_policy": "first occurrence kept; later duplicates removed and listed in duplicate_records.csv",
    }
    with open(out_dir / "summary_report.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    log.info("Done: %d collected -> %d rejected, %d duplicates -> %d final records",
             len(raw_records), len(rejected), len(duplicates), len(unique))
    return summary
