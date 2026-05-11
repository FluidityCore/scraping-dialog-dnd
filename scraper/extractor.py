"""
Extract clean, plain-text dialogue from a transcript subpage.

A Critical Role transcript page contains:
  - Navigation / infobox tables  → removed
  - Table of contents (TOC)     → removed
  - <h2>/<h3> section headers   → kept as separators
  - <p> paragraphs with dialogue → kept (format: "CHARACTER: line")
  - References / Navigation sections at the bottom → removed

The result is a single string ready to be written to a .txt file.
"""

import logging
import re

from bs4 import BeautifulSoup, NavigableString, Tag

logger = logging.getLogger(__name__)

# Headings that signal the end of transcript content
_STOP_HEADINGS = {"references", "navigation", "see also", "external links", "notes"}


def _remove_noise(content: Tag) -> None:
    """Decompose unwanted elements in-place before walking the tree."""
    # Navboxes, infoboxes, TOC, edit-section links
    for sel in [
        ".navbox",
        ".toc",
        ".mw-editsection",
        ".infobox",
        ".thumb",          # image thumbnails
        ".reference",      # inline [1] citation superscripts
        ".mw-references-wrap",
    ]:
        for el in content.select(sel):
            el.decompose()

    # All <table> elements (episode info cards, navboxes that lack the class)
    for table in content.find_all("table"):
        table.decompose()


def _heading_text(tag: Tag) -> str:
    """Return lowercased heading text without [edit] artefacts."""
    for span in tag.find_all("span", class_="mw-editsection"):
        span.decompose()
    return tag.get_text(strip=True).lower()


def extract(soup: BeautifulSoup) -> str | None:
    """
    Return clean transcript text from *soup*, or None if the page has no
    recognisable content div.
    """
    content = soup.find("div", class_="mw-parser-output")
    if not content:
        logger.warning("No .mw-parser-output found on transcript page.")
        return None

    _remove_noise(content)

    lines: list[str] = []
    in_stop_section = False

    for node in content.children:
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text and not in_stop_section:
                lines.append(text)
            continue

        if not isinstance(node, Tag):
            continue

        tag = node.name

        # Section-boundary detection
        if tag in ("h2", "h3", "h4"):
            heading = _heading_text(node)
            if any(stop in heading for stop in _STOP_HEADINGS):
                in_stop_section = True
                continue
            in_stop_section = False
            label = node.get_text(strip=True)
            label = re.sub(r"\[edit.*?\]", "", label).strip()
            if label:
                lines.append("")
                lines.append("=" * 60)
                lines.append(label)
                lines.append("=" * 60)
            continue

        if in_stop_section:
            continue

        if tag == "p":
            text = node.get_text(separator=" ", strip=True)
            # Collapse multiple internal spaces
            text = re.sub(r" {2,}", " ", text)
            if text:
                lines.append(text)

        elif tag == "ul":
            for li in node.find_all("li", recursive=False):
                text = li.get_text(separator=" ", strip=True)
                if text:
                    lines.append(f"  - {text}")

        elif tag == "dl":
            # Definition lists sometimes hold stage-direction blocks
            for child in node.find_all(["dt", "dd"]):
                text = child.get_text(separator=" ", strip=True)
                if text:
                    lines.append(text)

    result = "\n".join(lines).strip()
    if not result:
        logger.warning("Extraction produced empty text.")
        return None
    return result
