"""HTTP layer: timeouts, retries with exponential backoff, throttling, robots.txt."""
from __future__ import annotations

import logging
import time
from typing import Callable, Dict
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

from config import Config

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class FetchError(Exception):
    """A URL could not be fetched (after retries where retrying makes sense)."""


class HttpClient:
    def __init__(self, cfg: Config, session: requests.Session | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.cfg = cfg
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": cfg.user_agent})
        self._sleep = sleep
        self._robots: Dict[str, RobotFileParser] = {}
        self.requests_made = 0
        self.retries = 0

    # -- robots.txt -------------------------------------------------------
    def _robots_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = RobotFileParser()
            try:
                resp = self.session.get(origin + "/robots.txt", timeout=self.cfg.timeout)
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                else:
                    # 4xx = no robots file = nothing is restricted; 5xx: be lenient but say so
                    if resp.status_code >= 500:
                        log.warning("robots.txt returned HTTP %s for %s; assuming allowed",
                                    resp.status_code, origin)
                    parser.allow_all = True
            except requests.RequestException as exc:
                log.warning("Could not read robots.txt for %s (%s); assuming allowed", origin, exc)
                parser.allow_all = True
            self._robots[origin] = parser
        return self._robots[origin]

    # -- GET --------------------------------------------------------------
    def get(self, url: str) -> str:
        if self.cfg.respect_robots and not self._robots_for(url).can_fetch(self.cfg.user_agent, url):
            raise FetchError(f"Blocked by robots.txt: {url}")

        last_error: object = None
        for attempt in range(self.cfg.max_retries + 1):
            if attempt:
                wait = self.cfg.backoff_base * 2 ** (attempt - 1)
                log.warning("Retry %d/%d for %s in %.1fs (%s)",
                            attempt, self.cfg.max_retries, url, wait, last_error)
                self.retries += 1
                self._sleep(wait)
            try:
                self.requests_made += 1
                resp = self.session.get(url, timeout=self.cfg.timeout)
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                continue
            except requests.RequestException as exc:  # invalid URL etc. - not worth retrying
                raise FetchError(f"Request failed for {url}: {exc}") from exc

            if resp.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {resp.status_code}"
                continue
            if resp.status_code >= 400:
                raise FetchError(f"HTTP {resp.status_code} for {url}")

            resp.encoding = "utf-8"  # both sites are UTF-8; avoids 'Â£' mojibake
            self._sleep(self.cfg.delay)
            return resp.text

        raise FetchError(f"Giving up on {url} after {self.cfg.max_retries + 1} attempts: {last_error}")
