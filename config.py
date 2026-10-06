"""Central, overridable settings (all of them can be set from the CLI in main.py)."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Config:
    books_url: str = "https://books.toscrape.com/"
    quotes_url: str = "https://quotes.toscrape.com/"
    output_dir: str = "output"
    log_dir: str = "logs"

    timeout: float = 15.0          # seconds per request
    max_retries: int = 3           # retries after the first attempt
    backoff_base: float = 1.0      # waits 1s, 2s, 4s ... between retries
    delay: float = 0.25            # polite pause after every successful request
    max_pages: Optional[int] = None  # per source; None = follow pagination to the end
    fetch_details: bool = True     # open product / author pages for extra fields
    respect_robots: bool = True
    user_agent: str = "scraping-assignment/1.0 (interview take-home; polite crawler)"

    def public_dict(self) -> dict:
        return asdict(self)
