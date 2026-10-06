# AI Usage

## Tool
**Claude (Anthropic)**, via the claude.ai chat interface.

## What it was used for
- Reading the assignment and proposing the project structure and the common schema.
- Generating the first version of all modules (scrapers, cleaning, validation, deduplication, pipeline, CLI).
- Generating the unit tests and the end-to-end test (local mock server).
- Writing the README.

## Representative prompt
> "complete the assignment" (with the full assignment text attached)

## AI-assisted parts
All code and documentation in this submission was first drafted by Claude. Sections below record what was
checked and changed during review.

## Verification performed
- 26 automated tests (`pytest`) pass: cleaning helpers, validation rules, duplicate detection (including the
  whitespace/case variants from the brief), HTML parsers with missing elements, retry/backoff logic with a fake
  session, and a full end-to-end run against a local mock of both sites (3 book pages, 2 quote pages, a detail
  page returning HTTP 500, a 404 author page, an invalid record and one duplicate per source).
- An unreachable-network run completes cleanly and writes empty outputs plus a summary (graceful failure).
- The AI's sandbox could not reach the real websites (HTTP 403 from its proxy), so the AI could not run the
  pipeline against the live sites; that run was done by the candidate (see below).

## Candidate review notes (to be completed by the candidate after running the project)
- Live run result: `<final record count>`, `<number of pages scraped per source>`, `<run time>`.
- Manual spot-check of `<N>` random rows against the websites: `<result>`.
- Changes I made after reviewing the AI output: `<list>`.
- Incorrect or incomplete AI suggestions I found: `<list, or "none found">`.
- Selectors the AI wrote from its knowledge of the sites' HTML (not from fetching them) that I confirmed in the
  browser: `article.product_pod`, `p.price_color`, `p.star-rating`, `li.next a`, breadcrumb category,
  `#product_description + p`, `div.quote`, `span.text`, `small.author`, `div.tags a.tag`,
  `.author-born-date`, `.author-born-location`.
