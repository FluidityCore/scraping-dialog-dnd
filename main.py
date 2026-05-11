#!/usr/bin/env python3
"""
Critical Role Transcript Scraper — main entry point.

Run:
    py main.py                  # scrape everything
    py main.py --dry-run        # parse index only, print structure, exit
    py main.py --campaign "C1"  # restrict to campaigns whose name contains C1

Output is written to  Output/<campaign>/<arc>/<episode>.txt
Missing episodes are logged to  Output/missing_transcripts.log
All activity is also streamed to  scraper.log
"""

import argparse
import logging
import sys

from scraper.client import build_session, fetch_page, wiki_url_to_title
from scraper.extractor import extract
from scraper.navigator import INDEX_PAGE_TITLE, parse_index
from scraper.organizer import episode_path, save_transcript, write_missing_log

# ---------------------------------------------------------------------------
# Logging setup – file + console
# ---------------------------------------------------------------------------
LOG_FILE = "scraper.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Critical Role transcripts.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse the index and print the structure without downloading anything.",
    )
    parser.add_argument(
        "--campaign",
        metavar="SUBSTR",
        default="",
        help="Only process campaigns whose name contains SUBSTR (case-insensitive).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip episodes whose output file already exists (resume / retry missing).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def run(dry_run: bool = False, campaign_filter: str = "", skip_existing: bool = False) -> None:
    session = build_session()

    # 1. Fetch and parse the index via MediaWiki API
    logger.info("Fetching index page '%s' via API…", INDEX_PAGE_TITLE)
    index_soup = fetch_page(session, INDEX_PAGE_TITLE)
    if not index_soup:
        logger.error("Failed to fetch index page. Aborting.")
        sys.exit(1)

    sections = parse_index(index_soup)
    if not sections:
        logger.error("No sections found in index. Check page structure.")
        sys.exit(1)

    # 2. Optional campaign filter
    if campaign_filter:
        sections = [
            s for s in sections
            if campaign_filter.lower() in s["campaign"].lower()
        ]
        logger.info(
            "Campaign filter '%s' → %d section(s) remaining.", campaign_filter, len(sections)
        )

    total_episodes = sum(len(s["episodes"]) for s in sections)
    logger.info(
        "Processing %d section(s), %d episode(s) total.", len(sections), total_episodes
    )

    if dry_run:
        _print_structure(sections)
        return

    # 3. Download and save each transcript
    missing: list[str] = []
    saved = 0
    global_ep_counter = 0

    for section in sections:
        campaign = section["campaign"]
        arc = section["arc"]
        episodes = section["episodes"]
        arc_ep_num = 0  # resets per arc for the file numbering

        logger.info("▶ Campaign: %s | Arc: %s (%d ep)", campaign, arc, len(episodes))

        for episode in episodes:
            global_ep_counter += 1
            arc_ep_num += 1
            title = episode["title"]
            url = episode["url"]

            prefix = f"  [{global_ep_counter}/{total_episodes}]"

            if not url:
                logger.warning("%s No transcript URL — skipping: %s", prefix, title)
                missing.append(f"[{campaign}] [{arc}] {title} — no URL on index page")
                continue

            # Convert wiki URL to page title for the API
            page_title = wiki_url_to_title(url)
            if not page_title:
                logger.warning("%s Cannot parse page title from %s", prefix, url)
                missing.append(f"[{campaign}] [{arc}] {title} — bad URL ({url})")
                continue

            if skip_existing and episode_path(campaign, arc, arc_ep_num, title).exists():
                logger.info("%s [skip] %s", prefix, title)
                saved += 1
                continue

            logger.info("%s %s", prefix, title)
            ep_soup = fetch_page(session, page_title)
            if not ep_soup:
                missing.append(f"[{campaign}] [{arc}] {title} — fetch failed ({url})")
                continue

            text = extract(ep_soup)
            if not text:
                logger.warning("     Empty extraction for %s", url)
                missing.append(f"[{campaign}] [{arc}] {title} — empty content ({url})")
                continue

            save_transcript(campaign, arc, arc_ep_num, title, text)
            saved += 1

    # 4. Write missing log and print summary
    write_missing_log(missing)
    logger.info(
        "\nDone. %d/%d transcripts saved. %d missing (see Output/missing_transcripts.log).",
        saved, total_episodes, len(missing),
    )


def _print_structure(sections: list[dict]) -> None:
    """Pretty-print the parsed index structure (dry-run mode)."""
    current_campaign = None
    for s in sections:
        if s["campaign"] != current_campaign:
            current_campaign = s["campaign"]
            print(f"\n{'=' * 60}")
            print(f"CAMPAIGN: {current_campaign}")
            print(f"{'=' * 60}")
        print(f"  ARC: {s['arc']} ({len(s['episodes'])} episodes)")
        for ep in s["episodes"]:
            marker = "OK" if ep["url"] else "!!"
            print(f"    [{marker}] {ep['title']}")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = _parse_args()
    run(dry_run=args.dry_run, campaign_filter=args.campaign, skip_existing=args.skip_existing)
