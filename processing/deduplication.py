"""Duplicate detection on normalised keys (not raw strings).

A record is a duplicate if ANY of its keys was already seen. The first occurrence
is kept; later ones are removed from the final dataset but written to
output/duplicates.csv with a pointer to the record they duplicate (audit trail).
"""
from __future__ import annotations

from typing import List, Tuple

from processing.cleaning import normalize_for_matching
from schema import SOURCE_BOOKS, SOURCE_QUOTES


def record_keys(rec: dict) -> List[tuple]:
    source = rec.get("source")
    title = normalize_for_matching(rec.get("name_or_title"))
    keys: List[tuple] = []
    if source == SOURCE_BOOKS:
        if rec.get("source_url"):
            keys.append(("same_url", source, rec["source_url"]))
        if title:
            # same normalised title AND same price -> same product listed twice
            keys.append(("same_title_and_price", source, title, rec.get("price")))
    elif source == SOURCE_QUOTES:
        if title:
            keys.append(("same_text_and_author", source, title,
                         normalize_for_matching(rec.get("author"))))
    elif title:
        keys.append(("same_title", source, title))
    return keys


def deduplicate(records: List[dict]) -> Tuple[List[dict], List[dict]]:
    """Return (unique records, duplicate records annotated with duplicate_of / duplicate_rule)."""
    seen = {}
    unique, duplicates = [], []
    for rec in records:
        keys = record_keys(rec)
        hit = next((k for k in keys if k in seen), None)
        if hit is None:
            unique.append(rec)
            for k in keys:
                seen[k] = rec
        else:
            original = seen[hit]
            duplicates.append({
                **rec,
                "duplicate_of": f"{(original.get('name_or_title') or '')[:60]} <{original.get('source_url')}>",
                "duplicate_rule": hit[0],
            })
            for k in keys:  # chain: later copies match whichever key they share
                seen.setdefault(k, original)
    return unique, duplicates
