# JSON Directory Harvester

**Configurable, resumable Python pipeline for harvesting records from any JSON-based directory API — geographic filtering, two-pass deduplication, data validation, and professionally formatted three-sheet Excel export. Point it at a new API with a config change. No code edits required.**

> **⚠️ API access required.** This tool fetches data from an API endpoint you configure — it does not scrape HTML pages. You need an API URL that returns JSON records. See `config.yaml.example` for the full configuration reference.

[![CI](https://github.com/FAAQJAVED/json-directory-harvester/actions/workflows/ci.yml/badge.svg)](https://github.com/FAAQJAVED/json-directory-harvester/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-102%20passing-brightgreen)](tests/)
[![Coverage](https://codecov.io/gh/FAAQJAVED/json-directory-harvester/graph/badge.svg)](https://codecov.io/gh/FAAQJAVED/json-directory-harvester)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](https://github.com/FAAQJAVED/json-directory-harvester)

---

> Found this useful? A ⭐ on GitHub helps other developers find it.

---

## Table of Contents

- [Preview](#preview)
- [What It Does](#what-it-does)
- [Use Cases](#use-cases)
- [How It Works](#how-it-works)
- [Features](#features)
- [Performance](#performance)
- [What Data You Get](#what-data-you-get)
- [Quick Start](#quick-start)
- [Configuration Reference](#configuration-reference)
- [Output](#output)
- [Runtime Controls](#runtime-controls)
- [Auto-Protection Features](#auto-protection-features)
- [Resuming a Run](#resuming-a-run)
- [Extending](#extending)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)
- [Troubleshooting](#troubleshooting)
- [Part of the B2B Lead Toolkit](#part-of-the-b2b-lead-toolkit)
- [License](#license)

---

## Preview

| Terminal — live progress bar | Excel Output — three sheets |
|---|---|
| ![Terminal progress bar showing Phase 2 running with live hit% and ETA](Assets/terminal_progress.png) | ![Excel output — Data sheet with navy headers and alternating row shading](Assets/output_preview.png) |

---

## What It Does

1. **Reads config.yaml** — one file controls the API endpoint, pagination mode, geographic bounds, field mapping, validation rules, and output format.
2. **Fetches all records** from the configured JSON API via paginated GET or POST requests, with configurable inter-page delay and request timeout.
3. **Filters by geography** using a lat/lng bounding box — keeps only records whose coordinates fall within the configured region.
4. **Deduplicates in two passes** — first by unique ID field, then by Name + Postcode composite key.
5. **Validates each record** against configurable rules (name length, postcode requirement, postcode regex, or any custom pattern).
6. **Exports to Excel** — a styled Data sheet (clean records), a Flagged sheet (failed validation), and a Summary sheet (run statistics).

Everything is config-driven. The Python source files contain zero API-specific strings — every field path, URL, and cleaning rule lives in `config.yaml`. Switching to a new directory API requires only a new config file, not a code change.

---

## Use Cases

| Who uses it | What they do | Example config |
|---|---|---|
| **Property data analysts** | Harvest national directory APIs filtered to a city bounding box | `geo_filter: {enabled: true, lat_min: 51.4, lat_max: 51.6}` |
| **Lead gen teams** | Extract and validate business records from membership directory APIs | Any B2B directory with a JSON API |
| **Market researchers** | Pull structured datasets from industry directories for analysis | Configure once, re-run weekly for fresh data |
| **CRM admins** | Automate nightly imports from a members or listings API into Excel | Schedule with cron or Task Scheduler |
| **Data engineers** | Use as a lightweight ETL layer for JSON API → Excel pipelines | Extend `exporter.py` for custom output formats |
| **Developers** | Adapt to any new JSON directory API in minutes using a new config.yaml | Copy config.yaml.example, fill in 5 fields, run |

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1 — Fetch & Prepare                                      │
│                                                                 │
│  config.yaml ──► API endpoint (POST or GET)                    │
│                      │  paginated, configurable response path   │
│                      ▼                                          │
│                 raw_records[]                                   │
│                      │                                          │
│                      ├──► geo_filter()   ← lat/lng bounding box │
│                      ├──► dedup_records() ← ID, then name+post  │
│                      └──► checkpoint.save()  ← Phase 1 done     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  PHASE 2 — Process Records                                      │
│                                                                 │
│  records[] ──► extract_row()  ← field mapping, HTML strip,     │
│                                  phone normalise, https prefix  │
│                    │                                            │
│                    ├──► validate_row() ──► CLEAN or FLAGGED     │
│                    └──► checkpoint.save() every N records       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  PHASE 3 — Export                                               │
│                                                                 │
│  clean_rows[]   ──► Excel Sheet 1: Data                        │
│  flagged_rows[] ──► Excel Sheet 2: Flagged (with Flag Reason)  │
│  run stats{}    ──► Excel Sheet 3: Summary                     │
│                                                                 │
│  {prefix}_{YYYYMMDD}.xlsx  +  rotating .log file               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Detail |
|---|---|
| **Zero-code API targeting** | Point at any JSON directory API by editing config.yaml — no Python changes needed |
| **POST and GET** | Configurable HTTP method per endpoint |
| **Nested JSON navigation** | Dot-path `response_path` traverses any response structure: `["data", "results"]` → `response["data"]["results"]` |
| **Flexible pagination** | `page_in_path: false` (adds page as payload param) · `page_in_path: true` (substitutes `{page}` in URL path) |
| **Geographic bounding-box filter** | Optional lat/lng filter — restrict output to any city, region, or country |
| **Two-pass deduplication** | Pass 1: unique ID · Pass 2: Name + Postcode composite key |
| **Configurable validation** | Name length, postcode requirement, postcode regex — all config-driven; failures go to Flagged sheet |
| **Atomic checkpoint writes** | Write-to-temp-then-rename — checkpoint survives a crash mid-write |
| **Three-sheet Excel export** | Data · Flagged · Summary — styled, dated, named from config |
| **Checkpoint / resume** | Atomic JSON saves every N records — resume after any interruption with zero re-fetching |
| **Interactive keyboard controls** | P pause · R resume · S status · Q quit — no Enter needed on any platform |
| **Auto-protection** | Stop time · low-disk guard · consecutive-failure cap · retry queue |
| **Rotating log file** | 5 MB cap, 3 backups — full DEBUG to file, clean INFO to console |
| **Dry-run mode** | `--dry-run` reports record counts without writing any files |
| **Environment variable overrides** | `SCRAPER_API_URL`, `SCRAPER_API_KEY` — secrets never in `config.yaml` |
| **Ruff linting in CI** | Linter enforced on every push across Ubuntu, Windows, and macOS |
| **102 pure-function tests** | Full test suite runs offline in under 3 seconds — no API key needed |

---

## Performance

| Dataset size | Records fetched | Processing | Time |
|---|---|---|---|
| Small directory | 200–500 records | Geo-filter + dedup + validate | Under 2 min |
| Medium directory | 1,000–5,000 records | Full pipeline | 5–15 min |
| Large directory | 10,000+ records | Resumable overnight run | 1–4 hours |

> Actual speed depends on the target API's response time per page. The tool adds a configurable inter-page delay (`inter_page_delay` in `runtime:`) to stay polite. Processing (filtering, dedup, validation) adds negligible overhead on top of API fetch time.

---

## What Data You Get

| Field | Example |
|---|---|
| Name | Acme Property Management Ltd |
| Phone | 0161 234 5678 |
| Website | https://www.acme-property.co.uk |
| Postcode | M1 1AA |
| Category | Property Management |
| Source | Directory API |

See [`Assets/sample_output.csv`](Assets/sample_output.csv) for realistic sample output.

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/FAAQJAVED/json-directory-harvester.git
cd json-directory-harvester
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` — set your API URL, response path, field mapping, geo bounds, and output preferences. Every option is annotated in the example file.

### 3. Set secrets (optional)

```bash
cp .env.example .env
```

Add your API key to `.env`. It is injected at runtime via `SCRAPER_API_KEY` and never stored in `config.yaml`.

### 4. Run

```bash
# Standard run
python scraper.py

# Dry run — reports counts without writing files
python scraper.py --dry-run

# Use a different config file
python scraper.py --config my_config.yaml

# Start fresh (clears any saved checkpoint)
python scraper.py --reset
```

---

## Configuration Reference

### `api` section

| Key | Description |
|---|---|
| `url` | Full API endpoint URL. Can be overridden with `SCRAPER_API_URL` |
| `method` | `POST` or `GET` |
| `headers` | Dict of request headers (User-Agent, Content-Type, Referer, Origin, Authorization) |
| `payload` | POST body / GET query params |
| `response_path` | List of keys to navigate to the records list: `["data", "results"]` |

### `api.pagination` section

| Key | Description |
|---|---|
| `enabled` | Set `true` to enable multi-page fetching |
| `page_param` | Payload key for the page number (used when `page_in_path: false`) |
| `max_pages` | Hard ceiling on total pages fetched |
| `page_in_path` | If `true`, substitute `{page}` in the URL instead of adding a payload param |

### `geo_filter` section

| Key | Description |
|---|---|
| `enabled` | Toggle geographic filtering |
| `lat_min/max`, `lng_min/max` | Bounding box coordinates |
| `lat_field`, `lng_field` | Dot-path to lat/lng in each record (e.g. `"coordinates.latitude"`) |

### `field_mapping` section

Maps the scraper's logical field names (`id`, `name`, `phone`, `website`, `postcode`) to the actual key names in the API's JSON records.

### `output` section

| Key | Description |
|---|---|
| `directory` | Output folder for all generated files |
| `filename_prefix` | Prefix for Excel and log filenames |
| `category` | Value written to the Category column |
| `source` | Value written to the Source column |

### `validation` section

| Key | Description |
|---|---|
| `min_name_length` | Records with shorter names are flagged |
| `require_postcode` | Flag records with no postcode |
| `postcode_regex` | Regex pattern postcodes must match (blank = disabled) |

### `runtime` section

| Key | Default | Description |
|---|---|---|
| `stop_at` | `"23:00"` | HH:MM auto-stop time |
| `save_every` | `10` | Checkpoint every N records |
| `progress_every` | `10` | Log progress every N records |
| `request_timeout` | `15` | HTTP timeout in seconds |
| `low_disk_mb` | `500` | Auto-pause threshold (MB free) |
| `max_consec_fail` | `3` | Auto-pause after N consecutive failures |
| `inter_page_delay` | `0.5` | Seconds to wait between paginated API requests |

---

## Output

### Excel workbook — `{prefix}_{YYYYMMDD}.xlsx`

| Sheet | Contents |
|---|---|
| **Data** | Clean, validated records — frozen header row, navy header, alternating row shading, auto-width columns |
| **Flagged** | Records that failed validation, each annotated with a `Flag Reason` column |
| **Summary** | Run metadata: date, record counts, elapsed time, source endpoint, version, status |

### Log file — `{prefix}_{YYYYMMDD}.log`

Rotating log file (5 MB max, 3 backups). Full DEBUG output with timestamps to file. Clean INFO-level only to console.

---

## Runtime Controls

While the scraper is running, press a key (no Enter needed on any platform):

| Key | Action |
|---|---|
| `P` | Pause processing |
| `R` | Resume after pause |
| `S` | Print current status (progress bar, counts, rate, ETA) |
| `Q` | Quit cleanly — saves checkpoint for resumption |

---

## Auto-Protection Features

| Feature | Trigger | Behaviour |
|---|---|---|
| Stop time | Configured HH:MM | Saves checkpoint and exits cleanly |
| Low disk guard | Free disk < `low_disk_mb` MB | Auto-pauses; resumes when R is pressed |
| Consecutive failure cap | N failures in a row | Auto-pauses; resets counter on resume |
| Retry queue | Any record-level exception | Failed records retried once after main loop |

---

## Resuming a Run

If a run is interrupted — by `Q`, stop time, disk guard, or any crash after Phase 1 completes — the checkpoint file is saved automatically. The next run detects it and resumes Phase 2 from where it stopped. Phase 1 (API fetching) is never repeated.

```bash
python scraper.py          # automatically resumes if checkpoint exists
python scraper.py --reset  # discard checkpoint and start fresh
```

---

## Extending

| Goal | Where to change |
|---|---|
| Add a new output column | `processor.extract_row()` and `exporter.DATA_FIELDS` |
| Add a new validation rule | `processor.validate_row()` |
| Add a new field normaliser | New function in `processor.py` alongside `strip_html()` |
| Support a new auth scheme | `config._apply_env_overrides()` |
| Add a new runtime protection | Top of Phase 2 loop in `scraper.py` |

---

## Tech Stack

| Library | Role |
|---|---|
| `requests` | HTTP GET/POST to the configured API endpoint |
| `pyyaml` | YAML config loading |
| `openpyxl` | Three-sheet Excel output (Data · Flagged · Summary) |
| `python-dotenv` | Optional — loads `SCRAPER_API_URL` and `SCRAPER_API_KEY` from `.env` |

---

## Project Structure

```
json-directory-harvester/
├── scraper.py            # CLI entry point — three-phase orchestrator
├── fetcher.py            # Paginated HTTP fetching (POST/GET, two pagination modes)
├── processor.py          # Geo filter, dedup, field extraction, validation (pure functions)
├── exporter.py           # Three-sheet Excel workbook builder
├── checkpoint.py         # Atomic JSON checkpoint save/load/clear
├── controls.py           # Cross-platform keyboard listener and audio feedback
├── config.py             # YAML loader with validation and env-var overrides
├── config.yaml.example   # Fully annotated configuration template
├── .env.example          # Secret injection template
├── requirements.txt      # Runtime dependencies
├── requirements-dev.txt  # Development and testing dependencies
├── pyproject.toml        # Package metadata and tool configuration
├── CHANGELOG.md          # Version history
├── CONTRIBUTING.md       # Contribution guidelines
├── LICENSE               # MIT
├── Assets/
│   ├── terminal_progress.png   # Screenshot — live progress bar
│   ├── output_preview.png      # Screenshot — Excel output (three sheets)
│   └── sample_output.csv       # Sample output rows for reference
└── tests/
    ├── __init__.py
    ├── test_processor.py  # 44 tests — all pure functions
    ├── test_fetcher.py    # 20 tests — mocked HTTP, both pagination modes
    ├── test_checkpoint.py # 15 tests — save/load/clear/atomic write
    ├── test_config.py     # 12 tests — load_config, env overrides, validation
    └── test_exporter.py   # 11 tests — schema constants, Excel file generation
```

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --cov=. --cov-report=term-missing
```

102 tests. No API key required. Full suite runs offline in under 3 seconds.

---

## Requirements

- Python 3.9+
- `requests` — HTTP fetching
- `pyyaml` — YAML config loading
- `openpyxl` — Excel workbook output
- `python-dotenv` — `.env` secret injection

See `requirements.txt` for pinned minimum versions.

---

## Troubleshooting

**"Config file not found: config.yaml"**

Copy the annotated example: `cp config.yaml.example config.yaml`
Then open it and replace all `YOUR_*` placeholder values.

---

**API returning zero records**

Wrong `response_path`. Open browser DevTools → Network tab → find the API call → inspect the JSON structure. If records are at `{"data": {"results": [...]}}`, set `response_path: ["data", "results"]`. Use `--dry-run` first to confirm counts.

---

**Checkpoint not resuming**

Re-run `python scraper.py` — checkpoint is detected automatically.
To start fresh: `python scraper.py --reset`

---

**Excel output locked / PermissionError**

Close the previous output file in Excel before running. Excel holds an exclusive lock on open `.xlsx` files.

---

**Keyboard controls not responding on macOS**

macOS requires Accessibility permissions for raw keypress reading.
System Settings → Privacy & Security → Accessibility → add your terminal app.
Restart the terminal after granting permission.

---

**Inter-page delay too fast — API is rate-limiting**

Increase `inter_page_delay` in your `config.yaml` under `runtime:`.
Default is 0.5 seconds. For strict APIs, try 2.0 or higher:

```yaml
runtime:
  inter_page_delay: 2.0
```

---

## Part of the B2B Lead Toolkit

This tool is one component of a broader B2B lead generation pipeline targeting UK property management companies, letting agents, block managers, and HMO landlords.

| Repo | What it does |
|---|---|
| **[JSON Directory Harvester](https://github.com/FAAQJAVED/json-directory-harvester)** ← *you are here* | Configurable harvester for any JSON directory API |
| **[Google Maps Business Scraper](https://github.com/FAAQJAVED/Google-Maps-Business-Scraper)** | Extracts and enriches business listings from Google Maps |
| **[Email Phone Enrichment Tool](https://github.com/FAAQJAVED/Email-Phone-Number-Enrichment-Tool)** | Converts a website list into a verified email + phone database |
| **[LeadHunter Pro](https://github.com/FAAQJAVED/Leadhunter_Pro)** | Multi-engine search scraper with HOT/WARM/COLD lead scoring |
| **[Trustpilot Business Scraper](https://github.com/FAAQJAVED/trustpilot-business-scraper)** | Extracts business contact data from Trustpilot search results |

All five tools share the same Excel output schema (Data + Summary sheets) — results can be combined directly in Excel or imported together into a CRM.

---

## License

MIT © 2026 [FAAQJAVED](https://github.com/FAAQJAVED) — see [LICENSE](LICENSE)
