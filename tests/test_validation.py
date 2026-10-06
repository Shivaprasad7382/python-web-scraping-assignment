from processing.cleaning import clean_record
from processing.validation import validate_record, validate_records

TS = "2026-01-01T00:00:00+00:00"


def book(**kw):
    raw = {"source": "Books to Scrape", "source_url": "http://x.com/b", "name_or_title": "T",
           "price": "£1.00", "rating": "Three", "scraped_at": TS}
    raw.update(kw)
    return clean_record(raw)


def test_valid_book():
    assert validate_record(book()) == []


def test_missing_price_and_bad_rating():
    assert any("price" in e for e in validate_record(book(price=None)))
    assert any("rating" in e for e in validate_record(book(rating="9")))


def test_bad_url_and_unknown_source():
    assert any("source_url" in e for e in validate_record(book(source_url="nope")))
    assert validate_record(book(source="Elsewhere"))[0].startswith("unrecognised source")


def test_split():
    valid, rejected = validate_records([book(), book(price=None)])
    assert len(valid) == 1 and len(rejected) == 1
