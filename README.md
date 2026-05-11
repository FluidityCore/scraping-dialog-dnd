# Critical Role Transcript Scraper

Scrapes every transcript from the [Critical Role wiki](https://criticalrole.fandom.com/wiki/Transcripts)
and saves them locally, organised by **Campaign → Arc → Episode**.

Covers **563 episodes** across Campaign 1 (Vox Machina), Campaign 2 (The Mighty Nein),
Campaign Three (Bells Hells), Campaign Four, Exandria Unlimited, Specials, and Miscellaneous.

## Project structure

```
scraping-dialog-dnd/
├── main.py                  # Entry point
├── requirements.txt
├── AGENTS.md                # Full session context and design decisions
├── scraper/
│   ├── client.py            # HTTP session via MediaWiki API + retry + delay
│   ├── navigator.py         # Index page parser (Campaign / Arc / Episode)
│   ├── extractor.py         # Transcript page cleaner
│   └── organizer.py         # File I/O + missing-episode log
└── Output/                  # Created at runtime (git-ignored)
    ├── Campaña_<name>/
    │   └── Arco_<name>/
    │       ├── 001_<title>_Transcript.txt
    │       └── ...
    └── missing_transcripts.log
```

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Preview the index structure without downloading anything
py main.py --dry-run

# 3. Scrape a single campaign (substring match, case-insensitive)
py main.py --campaign "Campaign 1"

# 4. Scrape everything (~20 min with the 1-2 s polite delay)
py main.py

# 5. Resume an interrupted run / retry missing episodes only
py main.py --skip-existing
```

## CLI flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Parse the index and print the full structure, no downloads |
| `--campaign SUBSTR` | Only process campaigns whose name contains SUBSTR (case-insensitive) |
| `--skip-existing` | Skip episodes whose `.txt` file already exists — use to resume or retry |

## Build steps (git history)

| Commit | What was added |
|--------|----------------|
| step 1 | `.gitignore`, `requirements.txt` |
| step 2 | `scraper/client.py` – HTTP client, retry logic, polite delay |
| step 3 | `scraper/navigator.py` – index page parser |
| step 4 | `scraper/extractor.py` – transcript text cleaner |
| step 5 | `scraper/organizer.py` – file tree builder + missing log |
| step 6 | `main.py` – orchestrator with `--dry-run` and `--campaign` flags |
| step 7 | `README.md` |
| step 8 | Fix HTTP 403 (switch to MediaWiki API) + recursive collapsible parser for all campaigns |
| fix    | `redirects=1` in API calls — resolves pages that redirect on the wiki |
| feat   | `--skip-existing` flag for resuming / retrying missing episodes |

## Handling the data volume

Critical Role has 4 campaigns and hundreds of episodes. Each transcript
can be 50–150 KB of text. Here is how this project manages the load:

### 1 · Polite rate-limiting
`client.py` sleeps a **random 1–2 s** before every request (configurable via
`DELAY_MIN` / `DELAY_MAX`). This keeps the per-session request rate well below
Fandom's soft limits and avoids CAPTCHAs.

### 2 · Resumable runs
Every file is written immediately after extraction. If the process is interrupted,
re-run with `--skip-existing` to fetch only what is missing. Combine with
`--campaign` to cherry-pick a single campaign.

### 3 · Output directory is git-ignored
Hundreds of plain-text files totalling several hundred MB should **never**
be committed. The `.gitignore` excludes `Output/` entirely. Store the output
on a separate drive, cloud bucket, or database as fits your use case.

### 4 · Memory footprint
`BeautifulSoup` parses one page at a time; parsed objects are released between
episodes. Peak RAM usage is bounded by the largest single transcript page
(typically < 10 MB), not by the total corpus size.

### 5 · Logging and error recovery
All activity is written to `scraper.log`. Episodes that could not be fetched
or produced empty content are recorded in `Output/missing_transcripts.log`
so you can inspect and retry them with `--skip-existing`.

## Known limitations

| Issue | Status |
|-------|--------|
| November/December 2015 Critmas, SDCC 2016 Dating Game panel | No transcript subpage exists on the wiki — genuinely missing |
| Any future episodes added to the wiki | Re-run `py main.py --skip-existing` to fetch only the new ones |

## License

This scraper is for personal research and educational use only.
Critical Role transcripts are © Critical Role and their respective contributors.
