"""Validation rules applied to cleaned records before they enter the final dataset."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Dict, List, Tuple

from processing.cleaning import normalize_url
from schema import SOURCE_BOOKS, SOURCE_QUOTES

REQUIRED_BY_SOURCE = {
    SOURCE_BOOKS: ("name_or_title", "source_url", "price", "rating"),
    SOURCE_QUOTES: ("name_or_title", "source_url", "author"),
}


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and not math.isnan(x)


def validate_record(rec: dict) -> List[str]:
    """Return a list of human-readable problems (empty list = valid)."""
    source = rec.get("source")
    if source not in REQUIRED_BY_SOURCE:
        return [f"unrecognised source: {source!r}"]

    errors: List[str] = []
    for field in REQUIRED_BY_SOURCE[source]:
        if rec.get(field) in (None, "", []):
            errors.append(f"missing required field: {field}")

    price = rec.get("price")
    if price is not None and (not _is_number(price) or price < 0):
        errors.append("price is not a non-negative number")

    rating = rec.get("rating")
    if rating is not None and (not _is_number(rating) or not 1 <= rating <= 5):
        errors.append("rating outside 1-5")

    url = rec.get("source_url")
    if url and normalize_url(url) is None:
        errors.append("source_url is not a valid http(s) URL")

    if not isinstance(rec.get("tags", []), list):
        errors.append("tags is not a list")

    stamp = rec.get("scraped_at")
    if not stamp:
        errors.append("missing required field: scraped_at")
    else:
        try:
            datetime.fromisoformat(stamp)
        except ValueError:
            errors.append("scraped_at is not ISO-8601")
    return errors


def validate_records(records: List[dict]) -> Tuple[List[dict], List[Dict]]:
    """Split into (valid records, rejected [{'record':..., 'errors':[...]}])."""
    valid, rejected = [], []
    for rec in records:
        errors = validate_record(rec)
        if errors:
            rejected.append({"record": rec, "errors": errors})
        else:
            valid.append(rec)
    return valid, rejected
