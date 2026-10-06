from processing.cleaning import (clean_record, clean_tags, clean_text, normalize_for_matching,
                                 normalize_url, parse_price, parse_rating, strip_wrapping_quotes)


def test_clean_text_whitespace_and_missing():
    assert clean_text("  A \n\t  B\u00a0C ") == "A B C"
    assert clean_text("   ") is None
    assert clean_text("N/A") is None
    assert clean_text(None) is None


def test_parse_price_variants():
    assert parse_price("£51.77") == (51.77, "GBP")
    assert parse_price("Â£51.77") == (51.77, "GBP")      # mojibake
    assert parse_price("1,234.50") == (1234.5, None)
    assert parse_price("12,5 €") == (12.5, "EUR")
    assert parse_price("free") == (None, None)
    assert parse_price(None) == (None, None)


def test_parse_rating():
    assert parse_rating("Three") == 3
    assert parse_rating("4/5") == 4
    assert parse_rating(5) == 5
    assert parse_rating("banana") is None
    assert parse_rating(None) is None


def test_normalize_url():
    assert normalize_url("HTTPS://Books.ToScrape.com:443/a#frag") == "https://books.toscrape.com/a"
    assert normalize_url("/x/y", base="http://h.com/a/") == "http://h.com/x/y"
    assert normalize_url("not a url") is None
    assert normalize_url("ftp://h.com/") is None
    assert normalize_url(None) is None


def test_matching_key_ignores_case_space_punct_accents():
    a = normalize_for_matching("Example Book Title")
    assert a == normalize_for_matching(" Example Book Title ")
    assert a == normalize_for_matching("EXAMPLE BOOK TITLE")
    assert normalize_for_matching("Café — “Test”") == normalize_for_matching("cafe test")


def test_tags_and_quotes():
    assert clean_tags([" Love ", "love", "Life", ""]) == ["love", "life"]
    assert clean_tags("a, b|a") == ["a", "b"]
    assert strip_wrapping_quotes("“Hello world”") == "Hello world"


def test_clean_record_book_and_quote_share_schema():
    book = clean_record({"source": "Books to Scrape", "source_url": "http://x.com/b", "name_or_title": " T ",
                         "price": "£1.50", "rating": "Two", "scraped_at": "2026-01-01T00:00:00+00:00"})
    quote = clean_record({"source": "Quotes to Scrape", "source_url": "http://x.com/", "name_or_title": "“Q”",
                          "author": " A ", "tags": ["x"], "scraped_at": "2026-01-01T00:00:00+00:00"})
    assert list(book) == list(quote)
    assert (book["price"], book["currency"], book["rating"]) == (1.5, "GBP", 2)
    assert quote["name_or_title"] == "Q" and quote["price"] is None and quote["category"] is None
