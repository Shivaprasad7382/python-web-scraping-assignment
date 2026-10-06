"""End-to-end run of the real pipeline against a local mock of both sites.

Covers: pagination, relative links, a detail page that always 500s, a card with no price
(rejected), a title duplicate differing in case/whitespace, a quote duplicate differing in
case/curly quotes, a missing author page, and the output files.
"""
import csv
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from config import Config
from pipeline import run


def card(title, href, price, rating="Three"):
    price_html = f'<p class="price_color">{price}</p>' if price else ""
    return (f'<article class="product_pod"><p class="star-rating {rating}"></p>'
            f'<h3><a href="{href}" title="{title}">{title[:8]}...</a></h3>{price_html}'
            f'<p class="instock availability">In stock</p></article>')


def detail(cat, desc):
    return (f'<ul class="breadcrumb"><li>Home</li><li>Books</li><li>{cat}</li><li>x</li></ul>'
            f'<div id="product_description"><h2>d</h2></div><p>{desc}</p>')


def qdiv(text, author, tags):
    tag_html = "".join(f'<a class="tag" href="/tag/{t}/">{t}</a>' for t in tags)
    return (f'<div class="quote"><span class="text">“{text}”</span><span>by <small class="author">{author}</small>'
            f'<a href="/author/{author.strip().replace(" ", "-")}">(about)</a></span>'
            f'<div class="tags">{tag_html}</div></div>')


PAGES = {
    "/": '<ol>' + card("Alpha Book", "catalogue/alpha_1/index.html", "£10.00")
         + card("Beta Book", "catalogue/beta_2/index.html", "£11.50", "Five")
         + '</ol><li class="next"><a href="catalogue/page-2.html">n</a></li>',
    "/catalogue/page-2.html": '<ol>' + card("Gamma Book", "gamma_3/index.html", "£12.00", "One")
         + card("Delta Book", "delta_4/index.html", None)
         + '</ol><li class="next"><a href="page-3.html">n</a></li>',
    "/catalogue/page-3.html": '<ol>' + card("  ALPHA book ", "alpha_dup_5/index.html", "£10.00")
         + card("Epsilon Book", "epsilon_6/index.html", "£13.00", "Two") + '</ol>',
    "/catalogue/alpha_1/index.html": detail("Poetry", "First."),
    "/catalogue/beta_2/index.html": detail("Fiction", "Second."),
    "/catalogue/gamma_3/index.html": detail("Travel", "Third."),
    # beta/epsilon etc. detail pages: epsilon is deliberately missing (404), alpha_dup -> 500 below
    "/qpage1": None,
}
ERRORS = {"/catalogue/alpha_dup_5/index.html": 500}

QUOTES = {
    "/": qdiv("The world is as you make it", "Jane Doe", ["Life", "life"]) + qdiv("Second quote", "John Roe", ["x"])
         + '<li class="next"><a href="/page/2/">n</a></li>',
    "/page/2/": qdiv("Third quote", "Jane Doe", []) + qdiv("THE WORLD  is as you make it!", " Jane Doe", ["Life"]),
    "/author/Jane-Doe": '<span class="author-born-date">May 1, 1900</span><span class="author-born-location">in Paris</span>',
    # /author/John-Roe is missing -> 404
}


class Handler(BaseHTTPRequestHandler):
    site = "books"

    def do_GET(self):
        path = self.path.split("?")[0]
        status, body = 404, ""
        table = PAGES if self.server.site == "books" else QUOTES
        if path in ERRORS and self.server.site == "books":
            status = ERRORS[path]
        elif table.get(path):
            status, body = 200, table[path]
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html")  # note: no charset on purpose
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture()
def servers():
    started = []
    urls = {}
    for site in ("books", "quotes"):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        srv.site = site
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        started.append(srv)
        urls[site] = f"http://127.0.0.1:{srv.server_address[1]}/"
    yield urls
    for srv in started:
        srv.shutdown()


def test_full_pipeline(servers, tmp_path):
    cfg = Config(books_url=servers["books"], quotes_url=servers["quotes"],
                 output_dir=str(tmp_path / "out"), log_dir=str(tmp_path / "logs"),
                 max_retries=1, backoff_base=0, delay=0)
    summary = run(cfg)

    books = summary["per_source"]["Books to Scrape"]
    quotes = summary["per_source"]["Quotes to Scrape"]
    assert books["scraper_stats"]["pages_scraped"] == 3          # pagination followed to the end
    assert books["records_collected"] == 6
    assert books["records_rejected_validation"] == 1             # Delta: no price
    assert books["duplicates_detected_and_removed"] == 1         # ALPHA book
    assert books["final_records"] == 4
    assert books["scraper_stats"]["detail_failures"] == 3        # delta, alpha_dup (500), epsilon (404)
    assert quotes["scraper_stats"]["pages_scraped"] == 2
    assert quotes["records_collected"] == 4
    assert quotes["duplicates_detected_and_removed"] == 1
    assert quotes["final_records"] == 3
    assert quotes["scraper_stats"]["detail_failures"] == 1       # John Roe author page 404
    assert summary["totals"]["final_records"] == 7
    assert summary["rejection_reasons"] == {"missing required field: price": 1}

    out = tmp_path / "out"
    with open(out / "final_dataset.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 7
    alpha = next(r for r in rows if r["name_or_title"] == "Alpha Book")
    assert (alpha["price"], alpha["currency"], alpha["rating"], alpha["category"]) == ("10.0", "GBP", "3", "Poetry")
    jane = next(r for r in rows if r["name_or_title"] == "The world is as you make it")
    assert jane["tags"] == "life" and jane["author_born"] == "May 1, 1900 in Paris"
    assert jane["price"] == "" and jane["source_url"].startswith("http://127.0.0.1")
    assert json.loads((out / "summary_report.json").read_text())["totals"]["final_records"] == 7
    assert (out / "rejected_records.csv").exists() and (out / "duplicate_records.csv").exists()


def test_unreachable_sources_do_not_crash(tmp_path):
    cfg = Config(books_url="http://127.0.0.1:9/", quotes_url="http://127.0.0.1:9/",
                 output_dir=str(tmp_path / "out"), log_dir=str(tmp_path / "logs"),
                 max_retries=1, backoff_base=0, delay=0, timeout=1)
    summary = run(cfg)
    assert summary["totals"]["final_records"] == 0
    assert summary["per_source"]["Books to Scrape"]["scraper_stats"]["pages_failed"] == 1
    assert (tmp_path / "out" / "final_dataset.csv").exists()
