# Critical Role Transcript Scraper

Scrapes every transcript from the [Critical Role wiki](https://criticalrole.fandom.com/wiki/Transcripts)
and saves them locally, organised by **Campaign → Arc → Episode**.

## Project structure

```
scraping-dialog-dnd/
├── main.py                  # Entry point
├── requirements.txt
├── scraper/
│   ├── client.py            # HTTP session + fetch with retry + delay
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

# 4. Scrape everything (takes several hours — ~1-2 s delay per request)
py main.py
```

## Build steps (git history)

| Commit | What was added |
|--------|----------------|
| step 1 | `.gitignore`, `requirements.txt` |
| step 2 | `scraper/client.py` – HTTP client, retry logic, polite delay |
| step 3 | `scraper/navigator.py` – index page parser |
| step 4 | `scraper/extractor.py` – transcript text cleaner |
| step 5 | `scraper/organizer.py` – file tree builder + missing log |
| step 6 | `main.py` – orchestrator with `--dry-run` and `--campaign` flags |
| step 7 | This README |

## Handling the data volume

Critical Role has **3 campaigns** and hundreds of episodes. Each transcript
can be 50–150 KB of text. Here is how this project manages the load:

### 1 · Polite rate-limiting
`client.py` sleeps a **random 1–2 s** before every request (configurable via
`DELAY_MIN` / `DELAY_MAX`). This keeps the per-session request rate well below
Fandom's soft limits and avoids CAPTCHAs.

### 2 · Resumable runs
`organizer.py` writes each file immediately after extraction. If the process
is interrupted (power cut, Ctrl-C) you can simply re-run and skip the
campaigns/arcs you already have — use `--campaign` to cherry-pick.
Adding an existence check (`if not path.exists()`) before re-downloading
is a one-line improvement for production use.

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
so you can inspect and retry them manually.

## License

This scraper is for personal research and educational use only.
Critical Role transcripts are © Critical Role and their respective contributors.
