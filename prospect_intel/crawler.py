"""Polite website crawler: robots.txt respected, few pages per site, fixed delay.

Only fetches public pages that a visitor could read without logging in. Never
submits forms or follows links off the business's own domain.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .config import settings

# Link text/href patterns worth visiting after the homepage, highest value first.
PRIORITY = [
    r"privacy|data[- ]?protection|ndpa|ndpr",
    r"cookie",
    r"contact",
    r"appointment|book|schedule",
    r"register|sign[- ]?up|open[- ]?an[- ]?account|get[- ]?started|apply|loan|quote",
    r"about",
]


@dataclass
class Page:
    url: str
    html: str


class Crawler:
    def __init__(self, client: httpx.Client | None = None, delay: float | None = None,
                 max_pages: int | None = None, user_agent: str | None = None):
        self.ua = user_agent or settings.user_agent
        self.client = client or httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": self.ua})
        self.delay = settings.crawl_delay if delay is None else delay
        self.max_pages = max_pages or settings.max_pages_per_site
        self._robots: dict[str, RobotFileParser | None] = {}

    def _robots_for(self, url: str) -> RobotFileParser | None:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = RobotFileParser()
            try:
                r = self.client.get(base + "/robots.txt")
                if r.status_code in (401, 403):
                    rp.parse(["User-agent: *", "Disallow: /"])  # treat as disallowed
                elif r.status_code >= 400:
                    rp.parse([])  # no robots.txt: allowed
                else:
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError:
                rp = None  # unreachable: we will not crawl
            self._robots[base] = rp
        return self._robots[base]

    def allowed(self, url: str) -> bool:
        rp = self._robots_for(url)
        return bool(rp and rp.can_fetch(self.ua, url))

    def fetch(self, url: str) -> Page | None:
        if not self.allowed(url):
            return None
        try:
            r = self.client.get(url)
        except httpx.HTTPError:
            return None
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200 or "html" not in ctype:
            return None
        return Page(url=str(r.url), html=r.text)

    def crawl_site(self, start_url: str) -> tuple[list[Page], str | None]:
        """Returns (pages, skip_reason). skip_reason is set when nothing was fetched."""
        if "://" not in start_url:
            start_url = "https://" + start_url
        if not self.allowed(start_url):
            return [], "robots.txt disallows crawling or site unreachable"
        home = self.fetch(start_url)
        if not home:
            return [], "homepage not fetched"
        pages = [home]
        host = urlparse(home.url).hostname
        candidates = self._ranked_links(home, host)
        for link in candidates:
            if len(pages) >= self.max_pages:
                break
            time.sleep(self.delay)
            page = self.fetch(link)
            if page:
                pages.append(page)
        return pages, None

    @staticmethod
    def _ranked_links(page: Page, host: str | None) -> list[str]:
        soup = BeautifulSoup(page.html, "html.parser")
        seen: set[str] = {page.url}
        buckets: list[list[str]] = [[] for _ in PRIORITY]
        for a in soup.find_all("a", href=True):
            href = urljoin(page.url, a["href"]).split("#")[0]
            if urlparse(href).hostname != host or href in seen:
                continue
            label = f"{a.get_text(' ', strip=True)} {href}".lower()
            for i, pat in enumerate(PRIORITY):
                if re.search(pat, label):
                    buckets[i].append(href)
                    seen.add(href)
                    break
        return [u for b in buckets for u in b[:2]]
