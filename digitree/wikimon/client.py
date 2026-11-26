"""A polite client for Wikimon's MediaWiki API (https://wikimon.net/api.php).

Politeness rules it follows:

* One request at a time, with at least ``min_interval`` seconds between
  requests (default 2 s, from the ``wikimon_rate_limit`` config value).
* ``maxlag=5`` on every request, so the wiki can tell us to back off when
  it's busy, and we honour ``Retry-After`` on 429/503 responses.
* Page text is fetched 50 pages per request (the API's normal batch size),
  so the whole Digimon list takes a few dozen requests, not thousands.
* A descriptive User-Agent, as MediaWiki's API etiquette asks for.
"""

from __future__ import annotations

import time
from typing import Callable, Iterator

import requests

API_URL = "https://wikimon.net/api.php"
USER_AGENT = "DigiTree/0.2 (desktop Digimon evolution tree builder; personal use)"
BATCH_SIZE = 50


class WikimonError(RuntimeError):
    pass


class StopRequested(Exception):
    """Raised inside a wait when the caller asked us to stop."""


class WikimonClient:
    def __init__(self, api_url: str = API_URL, min_interval: float = 2.0,
                 session: requests.Session | None = None,
                 should_stop: Callable[[], bool] | None = None,
                 max_retries: int = 5, timeout: float = 60.0):
        self.api_url = api_url
        self.min_interval = max(0.0, min_interval)
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self.should_stop = should_stop or (lambda: False)
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_request = 0.0
        self.request_count = 0

    # -- low level -----------------------------------------------------

    def _sleep(self, seconds: float) -> None:
        """Sleep in small steps so a Stop button responds quickly."""
        end = time.monotonic() + seconds
        while True:
            if self.should_stop():
                raise StopRequested()
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.2, remaining))

    def get(self, **params) -> dict:
        params = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
        for attempt in range(self.max_retries + 1):
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                self._sleep(wait)
            if self.should_stop():
                raise StopRequested()
            self._last_request = time.monotonic()
            self.request_count += 1
            try:
                resp = self.session.get(self.api_url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    raise WikimonError(f"Network error: {exc}") from exc
                self._sleep(min(60, 5 * 2 ** attempt))
                continue

            if resp.status_code in (429, 502, 503, 504):
                if attempt == self.max_retries:
                    raise WikimonError(f"Wikimon is busy (HTTP {resp.status_code})")
                self._sleep(self._retry_after(resp, attempt))
                continue
            if resp.status_code != 200:
                raise WikimonError(f"HTTP {resp.status_code} from Wikimon")

            data = resp.json()
            err = data.get("error")
            if err:
                if err.get("code") == "maxlag" and attempt < self.max_retries:
                    self._sleep(self._retry_after(resp, attempt))
                    continue
                raise WikimonError(f"{err.get('code')}: {err.get('info')}")
            return data
        raise WikimonError("Too many retries")

    @staticmethod
    def _retry_after(resp, attempt: int) -> float:
        try:
            return min(120.0, float(resp.headers.get("Retry-After", "")))
        except ValueError:
            return min(120.0, 5.0 * 2 ** attempt)

    def _continued(self, **params) -> Iterator[dict]:
        """Follow MediaWiki 'continue' tokens."""
        cont: dict = {}
        while True:
            data = self.get(**params, **cont)
            yield data
            if "continue" not in data:
                return
            cont = data["continue"]

    # -- enumeration ---------------------------------------------------

    def category_members(self, category: str) -> list[str]:
        if not category.lower().startswith("category:"):
            category = "Category:" + category
        titles = []
        for data in self._continued(action="query", list="categorymembers",
                                    cmtitle=category, cmnamespace="0",
                                    cmlimit="500", cmtype="page"):
            titles += [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
        return titles

    def pages_using_template(self, template: str) -> list[str]:
        if not template.lower().startswith("template:"):
            template = "Template:" + template
        titles = []
        for data in self._continued(action="query", list="embeddedin",
                                    eititle=template, einamespace="0", eilimit="500"):
            titles += [m["title"] for m in data.get("query", {}).get("embeddedin", [])]
        return titles

    # -- content -------------------------------------------------------

    def fetch_wikitext(self, titles: list[str]) -> tuple[dict[str, dict], dict[str, str]]:
        """Fetch up to 50 pages' wikitext in one request.

        Returns (pages, redirects) where pages maps the requested-or-resolved
        title to {"title", "rev_id", "wikitext", "missing"} and redirects maps
        alias -> target for any titles that were redirects.
        """
        if len(titles) > BATCH_SIZE:
            raise ValueError(f"At most {BATCH_SIZE} titles per request")
        data = self.get(action="query", prop="revisions", rvprop="content|ids",
                        rvslots="main", redirects="1", titles="|".join(titles))
        q = data.get("query", {})
        redirects = {r["from"]: r["to"] for r in q.get("redirects", [])}
        normalized = {n["from"]: n["to"] for n in q.get("normalized", [])}
        pages: dict[str, dict] = {}
        for p in q.get("pages", []):
            if p.get("missing") or p.get("invalid"):
                pages[p.get("title", "")] = {"title": p.get("title", ""), "missing": True,
                                             "rev_id": None, "wikitext": ""}
                continue
            rev = (p.get("revisions") or [{}])[0]
            slot = rev.get("slots", {}).get("main", {})
            text = slot.get("content", rev.get("content", ""))
            pages[p["title"]] = {"title": p["title"], "missing": False,
                                 "rev_id": rev.get("revid"), "wikitext": text}
        # Fold normalisation into the redirect map so callers can look up
        # their original title.
        for orig, norm in normalized.items():
            redirects.setdefault(orig, redirects.get(norm, norm))
        return pages, redirects

    def resolve_redirects(self, titles: list[str]) -> dict[str, str]:
        """alias -> target for any of ``titles`` that are redirects (50 per call)."""
        out: dict[str, str] = {}
        for i in range(0, len(titles), BATCH_SIZE):
            chunk = titles[i:i + BATCH_SIZE]
            data = self.get(action="query", redirects="1", titles="|".join(chunk))
            q = data.get("query", {})
            for n in q.get("normalized", []):
                out[n["from"]] = n["to"]
            for r in q.get("redirects", []):
                out[r["from"]] = r["to"]
            # Chain: original -> normalized -> redirect target
            for k, v in list(out.items()):
                for _ in range(5):  # bounded, in case of a redirect loop
                    if v not in out or out[v] == v or v == k:
                        break
                    v = out[v]
                out[k] = v
        return {k: v for k, v in out.items() if k != v}
