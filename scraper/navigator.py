"""
Parse the Critical Role Transcripts index page into a structured list.

The wiki page uses:
  <h2>  → Campaign name
  <h3>  → Arc / Act name (nested under a campaign)
  <ul>  → list of episodes; each <li> may contain a "Transcript" link

Returns a flat list of dicts:
  {
      "campaign": str,
      "arc": str,
      "episodes": [{"title": str, "url": str | None}, ...]
  }
"""

import logging
import re

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

BASE_URL = "https://criticalrole.fandom.com"
INDEX_URL = f"{BASE_URL}/wiki/Transcripts"

# Headings that exist on the page but are not real campaigns
_SKIP_HEADINGS = {"contents", "table of contents"}


def _clean_heading(tag: Tag) -> str:
    """Strip [edit] spans and excess whitespace from a heading tag."""
    for span in tag.find_all("span", class_="mw-editsection"):
        span.decompose()
    return tag.get_text(separator=" ", strip=True)


def _find_transcript_url(li: Tag) -> str | None:
    """
    Return the first href that looks like a transcript link inside an <li>.

    Criteria (checked in order):
    1. Link text contains "transcript" (case-insensitive)
    2. href contains "/Transcript"
    3. href is the only link in the <li> and points to a /wiki/ page
       whose title ends with "Transcript"
    """
    anchors = li.find_all("a", href=True)
    for a in anchors:
        href: str = a["href"]
        text = a.get_text(strip=True).lower()
        if "transcript" in text or "/Transcript" in href:
            return href

    # Fallback: sole link whose title ends in Transcript
    if len(anchors) == 1:
        href = anchors[0]["href"]
        if re.search(r"/Transcript$", href, re.IGNORECASE):
            return href

    return None


def _absolute(href: str) -> str:
    """Make a wiki-relative href absolute."""
    if href.startswith("http"):
        return href
    return BASE_URL + href


def parse_index(soup: BeautifulSoup) -> list[dict]:
    """
    Walk the .mw-parser-output of the index page and build the structure.
    """
    content = soup.find("div", class_="mw-parser-output")
    if not content:
        logger.error("Could not find .mw-parser-output on index page.")
        return []

    sections: list[dict] = []
    current_campaign: str | None = None
    current_arc: str = "General"

    for element in content.children:
        if not isinstance(element, Tag):
            continue

        tag = element.name

        if tag == "h2":
            heading = _clean_heading(element)
            if heading.lower() in _SKIP_HEADINGS or not heading:
                continue
            current_campaign = heading
            current_arc = "General"

        elif tag == "h3" and current_campaign:
            current_arc = _clean_heading(element) or "General"

        elif tag == "ul" and current_campaign:
            episodes = []
            for li in element.find_all("li", recursive=False):
                # Episode title: text of the <li> minus parenthetical notes
                raw_title = li.get_text(separator=" ", strip=True)
                title = re.sub(r"\s*\(.*?\)\s*", " ", raw_title).strip()

                href = _find_transcript_url(li)
                episodes.append({
                    "title": title,
                    "url": _absolute(href) if href else None,
                })

            if episodes:
                sections.append({
                    "campaign": current_campaign,
                    "arc": current_arc,
                    "episodes": episodes,
                })

    logger.info(
        "Index parsed: %d sections, %d total episodes.",
        len(sections),
        sum(len(s["episodes"]) for s in sections),
    )
    return sections
