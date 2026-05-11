"""
HTTP client with polite rate-limiting and retry logic.

Uses the MediaWiki JSON API (api.php) instead of scraping HTML directly —
Fandom returns 403 for plain HTML requests from scripts but the API is open.
"""

import logging
import random
import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DELAY_MIN = 1.0
DELAY_MAX = 2.0
MAX_RETRIES = 2
TIMEOUT = 30

API_BASE = "https://criticalrole.fandom.com/api.php"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(_HEADERS)
    return session


def _raw_fetch(session: requests.Session, url: str, retries: int = MAX_RETRIES):
    """GET *url* with retry + polite delay. Returns Response or None."""
    for attempt in range(retries + 1):
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        try:
            response = session.get(url, timeout=TIMEOUT)
            if response.status_code == 200:
                return response
            logger.warning(
                "HTTP %s for %s (attempt %d/%d)",
                response.status_code, url, attempt + 1, retries + 1,
            )
            if attempt < retries:
                time.sleep(2)
        except requests.RequestException as exc:
            logger.warning(
                "Request error for %s: %s (attempt %d/%d)",
                url, exc, attempt + 1, retries + 1,
            )
            if attempt < retries:
                time.sleep(2)

    logger.error("Giving up on %s after %d attempts.", url, retries + 1)
    return None


def wiki_url_to_title(url: str) -> str | None:
    """
    Extract the MediaWiki page title from a /wiki/<Title> URL.

    '/wiki/Vox_Machina_vs._Percival/Transcript' → 'Vox Machina vs. Percival/Transcript'
    """
    match = re.search(r"/wiki/(.+?)(?:\?|#|$)", url)
    if not match:
        return None
    return urllib.parse.unquote(match.group(1)).replace("_", " ")


def fetch_page(session: requests.Session, page_title: str) -> BeautifulSoup | None:
    """
    Fetch a wiki page by title via the MediaWiki API and return a BeautifulSoup
    of the parsed HTML content.

    Returns None on any error (API error, network error, bad JSON).
    """
    params = {
        "action": "parse",
        "page": page_title,
        "prop": "text",
        "format": "json",
        "disablelimitreport": "1",
        "redirects": "1",  # follow MediaWiki redirects automatically
    }
    api_url = API_BASE + "?" + urllib.parse.urlencode(params)

    resp = _raw_fetch(session, api_url)
    if not resp:
        return None

    try:
        data = resp.json()
    except ValueError as exc:
        logger.error("JSON decode error for '%s': %s", page_title, exc)
        return None

    if "error" in data:
        code = data["error"].get("code", "unknown")
        info = data["error"].get("info", "")
        logger.error("API error for '%s': [%s] %s", page_title, code, info)
        return None

    html = data["parse"]["text"]["*"]
    return BeautifulSoup(html, "lxml")
