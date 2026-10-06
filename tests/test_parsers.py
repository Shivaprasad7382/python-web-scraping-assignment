from scrapers.books_scraper import parse_detail, parse_listing
from scrapers.quotes_scraper import parse_author, parse_page

BOOKS_HTML = """
<ol>
<article class="product_pod"><p class="star-rating Three"></p>
 <h3><a href="catalogue/a_1/index.html" title="A Full Title That Is Long">A Full...</a></h3>
 <p class="price_color">Â£51.77</p><p class="instock availability"> In stock </p></article>
<article class="product_pod"><h3><a href="catalogue/b_2/index.html" title="No Price Book">No...</a></h3></article>
<article class="product_pod"><p>broken card without link</p></article>
</ol><li class="next"><a href="catalogue/page-2.html">next</a></li>"""


def test_books_listing_handles_missing_elements():
    items, skipped, nxt = parse_listing(BOOKS_HTML, "http://h.com/")
    assert len(items) == 2 and skipped == 1
    assert items[0]["name_or_title"] == "A Full Title That Is Long"
    assert items[0]["source_url"] == "http://h.com/catalogue/a_1/index.html"
    assert items[0]["rating"] == "Three"
    assert items[1]["price"] is None and items[1]["rating"] is None
    assert nxt == "http://h.com/catalogue/page-2.html"


def test_books_listing_last_page_has_no_next():
    assert parse_listing("<html></html>", "http://h.com/")[2] is None


def test_book_detail():
    html = ('<ul class="breadcrumb"><li>Home</li><li>Books</li><li>Poetry</li><li>T</li></ul>'
            '<div id="product_description"><h2>x</h2></div><p>Nice book.</p>')
    assert parse_detail(html) == {"category": "Poetry", "description": "Nice book."}
    assert parse_detail("<html></html>") == {"category": None, "description": None}


QUOTES_HTML = """
<div class="quote"><span class="text">“Hi”</span>
 <span>by <small class="author">Ann</small><a href="/author/Ann">(about)</a></span>
 <div class="tags"><a class="tag" href="/tag/x/">x</a><a class="tag" href="/tag/y/">y</a></div></div>
<div class="quote"><small class="author">No text here</small></div>
<li class="next"><a href="/page/2/">Next</a></li>"""


def test_quotes_page():
    items, skipped, nxt = parse_page(QUOTES_HTML, "http://q.com/")
    assert len(items) == 1 and skipped == 1
    assert items[0]["tags"] == ["x", "y"] and items[0]["_author_url"] == "http://q.com/author/Ann"
    assert nxt == "http://q.com/page/2/"


def test_author_page():
    html = '<span class="author-born-date">May 1, 1900</span><span class="author-born-location">in Paris</span>'
    assert parse_author(html) == "May 1, 1900 in Paris"
    assert parse_author("<html></html>") is None
