"""Pure, reusable cleaning helpers. No network, no scraping selectors."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

from schema import SCHEMA_FIELDS, SOURCE_QUOTES

MISSING_TOKENS = {"", "n/a", "na", "none", "null", "nan", "-", "--"}
CURRENCY_SYMBOLS = {"£": "GBP", "$": "USD", "€": "EUR", "₹": "INR"}
RATING_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_QUOTE_CHARS = "“”„«»\"' "


def clean_text(value: Any) -> Optional[str]:
    """Unicode-normalise, collapse all whitespace, map 'missing' tokens to None."""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).replace("\u00ad", "")
    text = " ".join(text.split())
    return None if text.lower() in MISSING_TOKENS else text


def strip_wrapping_quotes(text: Optional[str]) -> Optional[str]:
    """'“To be”' -> 'To be'. Only strips double-quote style marks at the ends."""
    if text is None:
        return None
    return clean_text(text.strip("“”„«»\" "))


def parse_price(value: Any) -> Tuple[Optional[float], Optional[str]]:
    """'£51.77' / 'Â£51.77' / '1,234.50' / '12,5 €' -> (number, ISO currency or None)."""
    if value is None:
        return None, None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 2), None
    text = clean_text(str(value).replace("Â", ""))
    if not text:
        return None, None
    currency = next((code for sym, code in CURRENCY_SYMBOLS.items() if sym in text), None)
    match = re.search(r"\d[\d.,]*", text)
    if not match:
        return None, currency
    number = match.group().rstrip(".,")
    if "," in number and "." in number:
        number = number.replace(",", "")                 # 1,234.50
    elif "," in number:
        if number.count(",") == 1 and re.search(r",\d{1,2}$", number):
            number = number.replace(",", ".")            # 12,5 -> 12.5
        else:
            number = number.replace(",", "")             # 1,234
    try:
        return round(float(number), 2), currency
    except ValueError:
        return None, currency


def parse_rating(value: Any) -> Optional[float]:
    """'Three' / '3' / '4/5' / 3 -> 3. Range is checked later by validation."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
    else:
        text = clean_text(value)
        if not text:
            return None
        if text.lower() in RATING_WORDS:
            return RATING_WORDS[text.lower()]
        match = re.search(r"\d+(?:\.\d+)?", text)
        if not match:
            return None
        number = float(match.group())
    return int(number) if number == int(number) else number


def normalize_url(url: Any, base: Optional[str] = None) -> Optional[str]:
    """Absolute, lower-cased scheme/host, no fragment, default port dropped; None if invalid."""
    text = clean_text(url)
    if not text or re.search(r"\s", text):
        return None
    try:
        if base:
            text = urljoin(base, text)
        parts = urlsplit(text)
        if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
            return None
        port = parts.port
        default = 80 if parts.scheme.lower() == "http" else 443
        netloc = parts.hostname.lower() + (f":{port}" if port and port != default else "")
        path = parts.path or "/"
        return f"{parts.scheme.lower()}://{netloc}{path}" + (f"?{parts.query}" if parts.query else "")
    except ValueError:
        return None


def normalize_for_matching(value: Any) -> str:
    """Aggressive comparison key: NFKD, no accents, casefolded, punctuation -> space."""
    text = clean_text(value)
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def clean_tags(tags: Any) -> List[str]:
    """Accepts a list or a 'a, b|c' string; lower-cases, trims, de-duplicates, keeps order."""
    if tags is None:
        return []
    if isinstance(tags, str):
        tags = re.split(r"[,|]", tags)
    seen, out = set(), []
    for tag in tags:
        t = clean_text(tag)
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t.lower())
    return out


def clean_record(raw: dict) -> dict:
    """Raw scraper dict -> standardised record with exactly SCHEMA_FIELDS."""
    source = clean_text(raw.get("source"))
    name = clean_text(raw.get("name_or_title"))
    if source == SOURCE_QUOTES:
        name = strip_wrapping_quotes(name)
    price, currency = parse_price(raw.get("price"))

    rec = {
        "source": source,
        "source_url": normalize_url(raw.get("source_url")),
        "name_or_title": name,
        "category": clean_text(raw.get("category")),
        "price": price,
        "currency": currency,
        "rating": parse_rating(raw.get("rating")),
        "author": clean_text(raw.get("author")),
        "author_born": clean_text(raw.get("author_born")),
        "tags": clean_tags(raw.get("tags")),
        "description": clean_text(raw.get("description")),
        "availability": clean_text(raw.get("availability")),
        "scraped_at": clean_text(raw.get("scraped_at")),
    }
    assert list(rec) == SCHEMA_FIELDS  # guards schema drift
    return rec
