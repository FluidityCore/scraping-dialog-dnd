"""
HTTP client with polite rate-limiting and retry logic.

Fandom's servers will 429 you if you hammer them.
Delays of 1-2 s between requests keep us respectful.
"""

import logging
import random
import time

import requests

logger = logging.getLogger(__name__)

DELAY_MIN = 1.0
DELAY_MAX = 2.0
MAX_RETRIES = 2
TIMEOUT = 30

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def build_session() -> requests.Session:
    """Return a Session pre-loaded with browser-like headers."""
    session = requests.Session()
    session.headers.update(_HEADERS)
    return session


def fetch(session: requests.Session, url: str, retries: int = MAX_RETRIES):
    """
    GET *url*, sleeping 1-2 s before each attempt.

    On HTTP 404/500 or network error: retry up to *retries* times, then
    return None and log the failure so the caller can skip this episode.
    """
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
