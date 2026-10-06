from processing.cleaning import clean_record
from processing.deduplication import deduplicate

TS = "2026-01-01T00:00:00+00:00"


def book(title, price="£10.00", url="http://x.com/1"):
    return clean_record({"source": "Books to Scrape", "source_url": url, "name_or_title": title,
                         "price": price, "rating": "One", "scraped_at": TS})


def quote(text, author="Ann"):
    return clean_record({"source": "Quotes to Scrape", "source_url": "http://q.com/", "name_or_title": text,
                         "author": author, "scraped_at": TS})


def test_title_variants_are_duplicates():
    recs = [book("Example Book Title", url="http://x.com/1"),
            book(" Example Book Title ", url="http://x.com/2"),
            book("EXAMPLE BOOK TITLE", url="http://x.com/3")]
    unique, dups = deduplicate(recs)
    assert len(unique) == 1 and len(dups) == 2
    assert dups[0]["duplicate_rule"] == "same_title_and_price"


def test_same_title_different_price_is_kept():
    unique, dups = deduplicate([book("Same", "£1.00", "http://x.com/1"), book("Same", "£2.00", "http://x.com/2")])
    assert len(unique) == 2 and not dups


def test_same_url_is_duplicate():
    unique, dups = deduplicate([book("A", url="http://x.com/1"), book("B", "£5.00", url="http://X.com/1#top")])
    assert len(unique) == 1 and dups[0]["duplicate_rule"] == "same_url"


def test_quotes_need_same_author():
    unique, dups = deduplicate([quote("Hi there!"), quote("hi   THERE"), quote("Hi there!", "Bob")])
    assert len(unique) == 2 and len(dups) == 1


def test_sources_never_collide():
    unique, _ = deduplicate([book("Same"), quote("Same")])
    assert len(unique) == 2
