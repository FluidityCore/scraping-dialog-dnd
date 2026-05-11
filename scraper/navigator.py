"""
Parse the Critical Role Transcripts index page into a structured list.

The wiki uses three distinct HTML layouts:
  - C1 / C2  : h2 campaign → one <div class="mw-collapsible"> per arc
               Each arc-collapsible contains an h3 + mw-collapsible-content > ul
  - C3 / EU  : h2 is absent; whole campaign is ONE mw-collapsible whose
               mw-collapsible-content holds sub-mw-collapsible divs per arc
  - C4       : h2 campaign → h3 arc → <ul> episodes (no collapsible wrappers)

Returns a flat list of section dicts:
  {
      "campaign": str,
      "arc": str,
      "episodes": [{"title": str, "url": str | None}, ...]
  }
"""

import logging
import re

from bs4 import BeautifulSoup, NavigableString, Tag

logger = logging.getLogger(__name__)

BASE_URL = "https://criticalrole.fandom.com"
INDEX_PAGE_TITLE = "Transcripts"

_SKIP_HEADINGS = {"contents", "table of contents", "references"}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _clean_heading(tag: Tag) -> str:
    """Strip [edit] spans and return plain heading text."""
    for span in tag.find_all("span", class_="mw-editsection"):
        span.decompose()
    return tag.get_text(separator=" ", strip=True)


def _first_heading(div: Tag) -> str:
    """Return the text of the first heading element inside *div*, or ''."""
    heading = div.find(["h2", "h3", "h4"])
    return _clean_heading(heading) if heading else ""


def _absolute(href: str) -> str:
    return href if href.startswith("http") else BASE_URL + href


def _find_transcript_url(li: Tag) -> str | None:
    """
    Return the first href that looks like a transcript link inside an <li>.
    Checks (in order):
      1. Link text contains 'transcript'
      2. href path segment contains '/Transcript'
      3. Sole link whose href ends with /Transcript (case-insensitive)
    """
    anchors = li.find_all("a", href=True)
    for a in anchors:
        href: str = a["href"]
        if "transcript" in a.get_text(strip=True).lower() or "/Transcript" in href:
            return href

    if len(anchors) == 1:
        href = anchors[0]["href"]
        if re.search(r"/Transcript$", href, re.IGNORECASE):
            return href

    return None


def _collect_episodes(ul: Tag, campaign: str, arc: str, sections: list) -> None:
    """Parse a <ul> of episode <li> items and append a section dict if non-empty."""
    episodes = []
    for li in ul.find_all("li", recursive=False):
        raw = li.get_text(separator=" ", strip=True)
        title = re.sub(r"\s*\(.*?\)\s*", " ", raw).strip()
        href = _find_transcript_url(li)
        episodes.append({"title": title, "url": _absolute(href) if href else None})
    if episodes:
        sections.append({"campaign": campaign, "arc": arc, "episodes": episodes})


# ---------------------------------------------------------------------------
# Recursive collapsible handler
# ---------------------------------------------------------------------------

def _collect_h3_ul_pairs(content: Tag, campaign: str, sections: list) -> None:
    """
    Walk direct children of *content* pairing <h3> headings with the <ul>
    that follows each one.  Used when arcs are separated by headings rather
    than wrapped in their own mw-collapsible div (Campaign Three pattern).
    """
    current_arc = "General"
    for child in content.children:
        if not isinstance(child, Tag):
            continue
        if child.name in ("h3", "h4"):
            current_arc = _clean_heading(child)
        elif child.name == "ul":
            _collect_episodes(child, campaign, current_arc, sections)


def _process_collapsible(
    div: Tag,
    parent_campaign: str,
    parent_arc: str,
    sections: list,
) -> None:
    """
    Handle a <div class="mw-collapsible"> — three possible patterns:

    1. Sub-collapsibles inside content  → section/campaign wrapper (C3 outer, EU, Misc)
       heading = new campaign; recurse into each sub-collapsible.

    2. h3 headings alternating with <ul> inside content → campaign with inline arcs
       (Campaign Three inner, Miscellaneous sub-sections)
       heading = new campaign; walk h3+ul pairs.

    3. Direct <ul> children, no headings → simple arc (C1/C2 individual arcs)
       heading = arc name; collect episodes under parent_campaign.
    """
    content = div.find("div", class_="mw-collapsible-content")
    if not content:
        return

    heading_text = _first_heading(div)

    sub_collapsibles = content.find_all("div", class_="mw-collapsible", recursive=False)
    if sub_collapsibles:
        # Pattern 1: section wrapper with sub-collapsible arcs
        campaign_name = heading_text or parent_campaign
        for sub in sub_collapsibles:
            _process_collapsible(sub, campaign_name, parent_arc, sections)
        for ul in content.find_all("ul", recursive=False):
            _collect_episodes(ul, campaign_name, parent_arc, sections)

    elif content.find(["h3", "h4"]):
        # Pattern 2: campaign content with interleaved h3+ul arc sections
        campaign_name = heading_text or parent_campaign
        _collect_h3_ul_pairs(content, campaign_name, sections)

    else:
        # Pattern 3: simple arc with direct <ul> episode list
        arc_name = heading_text or parent_arc
        for ul in content.find_all("ul", recursive=False):
            _collect_episodes(ul, parent_campaign, arc_name, sections)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_index(soup: BeautifulSoup) -> list[dict]:
    """Walk the .mw-parser-output of the index page and build the episode list."""
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
        classes = element.get("class", [])

        if tag == "h2":
            heading = _clean_heading(element)
            if heading.lower() in _SKIP_HEADINGS or not heading:
                continue
            current_campaign = heading
            current_arc = "General"

        elif tag == "h3" and current_campaign:
            current_arc = _clean_heading(element) or "General"

        elif tag == "ul" and current_campaign:
            # C4 style: <ul> is a direct child of mw-parser-output
            _collect_episodes(element, current_campaign, current_arc, sections)

        elif tag == "div" and current_campaign and "mw-collapsible" in classes:
            # C1/C2 arc collapsibles, or campaign-level wrappers (C3, EU, Specials, Misc)
            _process_collapsible(element, current_campaign, current_arc, sections)

    logger.info(
        "Index parsed: %d sections, %d total episodes.",
        len(sections),
        sum(len(s["episodes"]) for s in sections),
    )
    return sections
