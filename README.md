# Multi-Source Web Scraping & Data Consolidation

A Python pipeline that scrapes **Books to Scrape** and **Quotes to Scrape**, maps both into one
schema, cleans and validates the data, removes duplicates, and writes a consolidated CSV plus a
JSON summary.

```
Books ─┐
       ├─> scrape ─> clean ─> validate ─> deduplicate ─> consolidate ─> final_dataset.csv
Quotes ┘                         │              │                       summary_report.json
                        rejected_records.csv  duplicate_records.csv
```

## Python version
Python 3.9+ (developed and tested on 3.12).

## Setup
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
Dependencies: `requests`, `beautifulsoup4` (parser: built-in `html.parser`, no lxml needed), `pytest` (tests only).

## Run
```bash
python main.py                     # full run, ~1,000 book pages + 10 quote pages + 50 authors
python main.py --no-details        # fast run: listing pages only (no category/description/author_born)
python main.py --max-pages 3       # 3 listing pages per source (quick check)
python main.py --help              # all options: --delay, --retries, --backoff, --timeout, --output-dir ...
pytest                             # run the tests (no internet needed)
```
A full run makes ~1,100 requests at a 0.25 s polite delay, so expect roughly 5–8 minutes.
Outputs go to `output/`, logs to `logs/scrape_<timestamp>.log`.

## Project structure
```
main.py                    CLI + logging setup
pipeline.py                orchestration and output writing
config.py                  all settings in one dataclass
schema.py                  the common data model (field list, source names)
http_client.py             timeouts, retry + exponential backoff, throttling, robots.txt
scrapers/books_scraper.py  Books selectors + pagination (only place with Books HTML knowledge)
scrapers/quotes_scraper.py Quotes selectors + pagination
processing/cleaning.py     pure cleaning helpers
processing/validation.py   validation rules
processing/deduplication.py duplicate detection
tests/                     unit tests + end-to-end test against a local mock server
```

## How pagination works
Both sites render a `<li class="next"><a href="…">` link on every page except the last. The scraper
fetches a page, extracts items, reads that link, resolves it to an absolute URL with `urljoin`
(the sites use different relative forms), and repeats until there is no "next" link. No page URL
is listed by hand. A `visited` set prevents loops and `--max-pages` caps it for quick runs.

## Data model
One row per book or quote. Fields that don't apply are empty (never invented):

| field | Books | Quotes |
|---|---|---|
| source | `Books to Scrape` | `Quotes to Scrape` |
| source_url | product page URL | URL of the listing page the quote appeared on (quotes have no page of their own) |
| name_or_title | title | quote text (surrounding quote marks removed) |
| category | breadcrumb category | – |
| price / currency | float / ISO code (`GBP`) | – |
| rating | 1–5 (int) | – |
| author / author_born | – | author name / "date + place" from the author page |
| tags | – | lower-cased tags joined with `\|` |
| description | product description | – |
| availability | e.g. "In stock" | – |
| scraped_at | UTC ISO-8601 | UTC ISO-8601 |

`price`/`currency` and `availability` are additions to the suggested schema; they keep `price` purely numeric.

## Cleaning approach (`processing/cleaning.py`)
- Unicode NFKC normalisation, all whitespace (incl. non-breaking spaces) collapsed, trimmed.
- Missing-value tokens (`""`, `N/A`, `null`, `nan`, `-` …) become empty.
- Price → float, currency from the symbol; handles `£51.77`, mojibake `Â£51.77`, `1,234.50`, `12,5 €`.
- Rating words (`Three`) / digits / `4/5` → number.
- URLs → absolute, lower-case scheme and host, fragment and default port dropped; invalid ones become empty.
- Tags lower-cased, trimmed, de-duplicated within a record.
- Responses are decoded as UTF-8 explicitly (the sites omit/mislabel the charset).

## Validation approach (`processing/validation.py`)
A record is rejected (written to `rejected_records.csv` with the reasons) if:
- the source is not one of the two known sources;
- a required field is missing — Books: title, URL, price, rating; Quotes: text, URL, author; both: `scraped_at`;
- price is not a non-negative number; rating is outside 1–5;
- `source_url` is not a valid-looking http(s) URL; `scraped_at` is not ISO-8601.

`category`/`description` are *not* required: if a detail page fails, the book is kept with what the listing gave us.

## Deduplication approach (`processing/deduplication.py`)
Comparison uses a **normalised key** (NFKD, accents stripped, casefolded, punctuation → space, whitespace
collapsed), so `"Example Book Title"`, `" Example Book Title "` and `"EXAMPLE BOOK TITLE"` match.
- **Books:** duplicate if same normalised URL, **or** same normalised title **and** same price. Price is part of the key
  because two different editions can share a title; same title with a different price is kept.
- **Quotes:** duplicate if same normalised text **and** same normalised author (the same sentence from two
  authors is two quotes). Page URL is not used, because many quotes share a page.
- Records from different sources never match each other.
- **Policy:** the first occurrence is kept; later ones are *removed* from the final CSV but written to
  `duplicate_records.csv` with `duplicate_of` and `duplicate_rule`, so nothing is silently lost and the rule is auditable.

## Error-handling approach
- `http_client.py`: per-request timeout; connection errors, timeouts and HTTP 429/500/502/503/504 are retried with
  exponential backoff (1 s, 2 s, 4 s); other 4xx (e.g. 404) fail immediately without retry; `robots.txt` is checked.
- A failed **listing** page ends pagination for that source only (without the page we cannot read its "next" link);
  the other source still runs.
- A failed **detail** page (book page / author page) keeps the record with listing data; failures are counted.
  Author pages are cached, including failures, so a broken page is not requested again.
- A malformed card / quote is skipped and logged; missing sub-elements become `None` instead of raising.
- A crash inside a whole scraper is caught; records collected so far are kept.
- Everything is logged (console + `logs/`), and counts appear in `summary_report.json`.

## Output (`output/`)
- `final_dataset.csv` – consolidated, deduplicated records (UTF-8).
- `summary_report.json` – per-source collected / cleaned / rejected / duplicates / final counts, scraper stats
  (pages scraped/failed, items skipped, detail failures), rejection reasons, duplicates by rule, HTTP request/retry
  counts, execution time and the configuration used.
- `rejected_records.csv`, `duplicate_records.csv` – audit trails.

## Assumptions
- Prices are GBP (derived from the `£` symbol, not assumed).
- A quote's `source_url` is the page it was found on.
- Only one request at a time with a short delay; the sites are small practice sites and this keeps traffic polite.

## Known limitations
- If a listing page fails after retries, remaining pages of that source are not scraped (re-run to retry).
- No checkpoint/resume or incremental scraping; no database output.
- Duplicate detection is exact-after-normalisation; it does not catch typos or paraphrases (no fuzzy matching).
- Cleaned book prices are in the site's currency; no conversion is done.

## AI usage summary
Claude was used to generate the initial implementation, tests and documentation. See `AI_USAGE.md`.

## Bonus features included
Exponential-backoff retries, configurable settings + CLI arguments, rate limiting, unit and end-to-end tests,
data-quality report (summary + rejected/duplicate files).
