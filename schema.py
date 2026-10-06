"""The common data model shared by both sources."""

SOURCE_BOOKS = "Books to Scrape"
SOURCE_QUOTES = "Quotes to Scrape"

SCHEMA_FIELDS = [
    "source",          # which website the record came from
    "source_url",      # book: product page URL; quote: URL of the listing page it was found on
    "name_or_title",   # book: title; quote: quote text
    "category",        # book: category; quote: null
    "price",           # book: float; quote: null
    "currency",        # book: ISO code derived from the price symbol; quote: null
    "rating",          # book: 1-5 (int); quote: null
    "author",          # quote: author; book: null
    "author_born",     # quote: "<date> <location>" from the author page; book: null
    "tags",            # quote: list of tags (joined with '|' in the CSV); book: empty
    "description",     # book: product description; quote: null
    "availability",    # book: e.g. "In stock"; quote: null
    "scraped_at",      # UTC ISO-8601 timestamp
]
