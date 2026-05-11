"""
File I/O: build the output directory tree and persist transcript text.

Directory layout
----------------
Output/
  Campaña_<campaign>/
    Arco_<arc>/
      001_<episode-title>_Transcript.txt
      002_<episode-title>_Transcript.txt
      ...

Episode files include a small header block so they are self-contained
(campaign, arc, episode title) even when opened in isolation.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_ROOT = Path("Output")
MISSING_LOG = OUTPUT_ROOT / "missing_transcripts.log"


def _slugify(name: str, max_len: int = 80) -> str:
    """
    Turn an arbitrary string into a safe directory/file name component.

    Removes characters illegal on Windows/macOS/Linux, collapses whitespace
    to underscores, and trims to *max_len* characters.
    """
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"[\s\-]+", "_", name.strip())
    return name[:max_len]


def episode_path(campaign: str, arc: str, episode_num: int, title: str) -> Path:
    """Return the full Path where this episode's transcript will be saved."""
    campaign_dir = OUTPUT_ROOT / f"Campaña_{_slugify(campaign)}"
    arc_dir = campaign_dir / f"Arco_{_slugify(arc)}"
    filename = f"{episode_num:03d}_{_slugify(title)}_Transcript.txt"
    return arc_dir / filename


def save_transcript(
    campaign: str,
    arc: str,
    episode_num: int,
    title: str,
    text: str,
) -> Path:
    """
    Write *text* to the appropriate path and return that path.

    Creates parent directories on first use.
    """
    path = episode_path(campaign, arc, episode_num, title)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"Campaign : {campaign}\n")
        fh.write(f"Arc      : {arc}\n")
        fh.write(f"Episode  : {title}\n")
        fh.write("=" * 60 + "\n\n")
        fh.write(text)
        fh.write("\n")

    logger.info("Saved → %s", path)
    return path


def write_missing_log(entries: list[str]) -> None:
    """Append missing-episode entries to the shared missing log file."""
    if not entries:
        return
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with MISSING_LOG.open("a", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(entry + "\n")
    logger.warning("%d episode(s) logged as missing → %s", len(entries), MISSING_LOG)
