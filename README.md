# JSON Directory Harvester

> A configurable, resumable Python pipeline for harvesting records from any JSON-based directory API — with geographic filtering, deduplication, data validation, and formatted three-sheet Excel export.

---

## Overview

JSON Directory Harvester fetches records from any JSON-based directory API, filters them by geographic bounding box, deduplicates them in two passes, validates each record against configurable rules, and exports the results to a professionally formatted Excel workbook.

Everything — the API endpoint, pagination, field names, geo bounds, validation rules, and output format — is controlled by a single `config.yaml` file. No source code changes are needed to point the tool at a new API.

---

## Features

- **Paginated fetching** — POST or GET, configurable page parameter and ceiling
- **Nested JSON navigation** — dot-path `response_path` traverses any response structure
- **Geographic bounding-box filter** — optional lat/lng filter to restrict to a region
- **Two-pass deduplication** — by record ID first, then by name + postcode
- **Configurable validation** — name length, postcode requirement, postcode regex
- **Three-sheet Excel export** — Data / Flagged / Summary with frozen headers, alternating row shading, and auto-width columns
- **Checkpoint / resume** — atomic JSON saves every N records; resume after any interruption
- **Interactive keyboard controls** — P pause · R resume · S status · Q quit (no Enter needed)
- **Auto-protection** — stop time, low-disk guard, consecutive-failure cap, retry queue
- **Rotating log file** — 5 MB cap, 3 backups, clean console output
- **Dry-run mode** — reports counts without writing any files
- **Environment variable overrides** — `SCRAPER_API_URL`, `SCRAPER_API_KEY`

---

## Project Structure

```
json-directory-harvester/
├── scraper.py            # CLI entry point and three-phase orchestrator
├── fetcher.py            # Paginated HTTP fetching (POST/GET)
├── processor.py          # Geo filter, dedup, field extraction, validation
├── exporter.py           # Three-sheet Excel workbook builder
├── checkpoint.py         # Atomic JSON checkpoint save/load/clear
├── controls.py           # Cross-platform keyboard listener + audio feedback
├── config.py             # YAML loader with env-var overrides
├── config.yaml.example   # Fully annotated configuration template
├── .env.example          # Secret injection template
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Package metadata
├── CHANGELOG.md          # Version history
├── LICENSE               # MIT License
└── tests/
    ├── __init__.py
    ├── test_processor.py
    ├── test_fetcher.py
    └── test_checkpoint.py
```

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

Edit `config.yaml` — set your API URL, field mapping, geo bounds, and output preferences. Every option is annotated in the example file.

### 3. Set secrets (optional)

```bash
cp .env.example .env
```

Add your API key to `.env`. It is injected at runtime and never stored in `config.yaml`.

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

| Section | Key | Description |
|---|---|---|
| `api` | `url` | Full API endpoint URL |
| `api` | `method` | `POST` or `GET` |
| `api` | `headers` | Dict of request headers |
| `api` | `payload` | POST body / GET query params |
| `api` | `response_path` | List of keys to reach the records list in the JSON |
| `api.pagination` | `enabled` | Enable multi-page fetching |
| `api.pagination` | `page_param` | Payload key for the page number (used when `page_in_path` is false) |
| `api.pagination` | `max_pages` | Hard ceiling on pages fetched |
| `api.pagination` | `page_in_path` | If true, substitute `{page}` in the URL instead of using a query/payload param |
| `geo_filter` | `enabled` | Toggle geographic filtering |
| `geo_filter` | `lat_min/max`, `lng_min/max` | Bounding box coordinates |
| `geo_filter` | `lat_field`, `lng_field` | Dot-path to lat/lng in each record |
| `field_mapping` | `id`, `name`, `phone`, `website`, `postcode` | Maps logical names to API field names |
| `output` | `directory` | Output folder for all generated files |
| `output` | `filename_prefix` | Prefix for Excel and log filenames |
| `output` | `category` | Value written to the Category column |
| `output` | `source` | Value written to the Source column |
| `validation` | `min_name_length` | Minimum name length (shorter → Flagged) |
| `validation` | `require_postcode` | Flag records with no postcode |
| `validation` | `postcode_regex` | Regex pattern for postcode format check |
| `runtime` | `stop_at` | HH:MM stop time (24-hour) |
| `runtime` | `save_every` | Checkpoint frequency (records) |
| `runtime` | `low_disk_mb` | Free-disk threshold for auto-pause (MB) |
| `runtime` | `max_consec_fail` | Consecutive failures before auto-pause |
| `runtime` | `request_timeout` | HTTP request timeout (seconds) |

---

## Output

### Excel workbook

The output file is named `{filename_prefix}_{YYYYMMDD}.xlsx` and contains three sheets:

| Sheet | Contents |
|---|---|
| **Data** | Clean, validated records with frozen header row and alternating row shading |
| **Flagged** | Records that failed validation, each with a `Flag Reason` column |
| **Summary** | Run metadata: date, record counts, elapsed time, source endpoint, version |

### Log file

A rotating log file (`{prefix}_{YYYYMMDD}.log`) is written alongside the Excel file. It captures full DEBUG-level output with timestamps. The console shows INFO-level only — clean, minimal output.

---

## Runtime Controls

While the scraper is running, press a key (no Enter needed):

| Key | Action |
|---|---|
| `P` | Pause processing |
| `R` | Resume after pause |
| `S` | Print current status (progress bar, counts, rate, ETA) |
| `Q` | Quit cleanly — saves checkpoint for later resumption |

---

## Auto-Protection Features

| Feature | Trigger | Behaviour |
|---|---|---|
| Stop time | Configurable HH:MM | Saves checkpoint and exits cleanly |
| Low disk guard | Free disk < `low_disk_mb` | Auto-pauses; resumes when R is pressed |
| Consecutive failure cap | N failures in a row | Auto-pauses; resets counter on resume |
| Retry queue | Any record-level exception | Failed records retried once after main loop |

---

## Resuming a Run

If a run is interrupted (keyboard Q, stop time, disk guard, or any crash after Phase 1), a checkpoint file is saved automatically. The next run detects it and resumes from where it left off — no re-fetching required.

To discard a checkpoint and start fresh:

```bash
python scraper.py --reset
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

## Running Tests

```bash
pip install pytest pytest-cov
pytest tests/ -v --cov=.
```

---

## Requirements

- Python 3.9+
- `requests`
- `pyyaml`
- `openpyxl`
- `python-dotenv`

See `requirements.txt` for pinned minimum versions.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Related Projects

This tool is part of the **FAAQJAVED B2B Lead Generation Toolkit** — a suite of modular, production-grade data collection tools:

| Tool | Purpose |
|---|---|
| [Google Maps Business Scraper](https://github.com/FAAQJAVED/Google-Maps-Business-Scraper) | Scrapes Google Maps listings and enriches with website contact data |
| [Email & Phone Enrichment Tool](https://github.com/FAAQJAVED/Email-Phone-Number-Enrichment-Tool) | Two-pass contact enricher for URL lists |
| [LeadHunter Pro](https://github.com/FAAQJAVED/Leadhunter_Pro) | Multi-engine search scraper with lead scoring |
| [Trustpilot Business Scraper](https://github.com/FAAQJAVED/trustpilot-business-scraper) | Extracts business contact data from Trustpilot |
| [JSON Directory Harvester](https://github.com/FAAQJAVED/json-directory-harvester) | Harvests records from any JSON-based directory API *(this repo)* |
