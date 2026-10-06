"""CLI entry point:  python main.py [--max-pages N] [--no-details] ..."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import Config
from pipeline import run


def setup_logging(log_dir: str) -> Path:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / f"scrape_{datetime.now():%Y%m%d_%H%M%S}.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in (logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(fmt)
        root.addHandler(handler)
    return log_file


def parse_args(argv=None) -> Config:
    d = Config()
    p = argparse.ArgumentParser(description="Multi-source web scraping & consolidation pipeline")
    p.add_argument("--books-url", default=d.books_url)
    p.add_argument("--quotes-url", default=d.quotes_url)
    p.add_argument("--output-dir", default=d.output_dir)
    p.add_argument("--log-dir", default=d.log_dir)
    p.add_argument("--max-pages", type=int, default=None, help="limit pages per source (default: all)")
    p.add_argument("--no-details", action="store_true",
                   help="skip product/author detail pages (faster; no category/description/author_born)")
    p.add_argument("--timeout", type=float, default=d.timeout)
    p.add_argument("--retries", type=int, default=d.max_retries)
    p.add_argument("--backoff", type=float, default=d.backoff_base)
    p.add_argument("--delay", type=float, default=d.delay, help="seconds to pause between requests")
    a = p.parse_args(argv)
    return Config(books_url=a.books_url, quotes_url=a.quotes_url, output_dir=a.output_dir,
                  log_dir=a.log_dir, max_pages=a.max_pages, fetch_details=not a.no_details,
                  timeout=a.timeout, max_retries=a.retries, backoff_base=a.backoff, delay=a.delay)


def main(argv=None) -> int:
    cfg = parse_args(argv)
    log_file = setup_logging(cfg.log_dir)
    logging.getLogger(__name__).info("Log file: %s", log_file)
    summary = run(cfg)
    print(f"\nFinal records: {summary['totals']['final_records']} "
          f"(see {cfg.output_dir}/final_dataset.csv and summary_report.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
