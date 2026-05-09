# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.0] — 2025-01-01

### Added
- Paginated API fetch supporting both POST and GET methods
- Configurable JSON response path navigation for nested structures
- Geographic bounding-box filter (lat/lng, optional)
- Two-pass deduplication: by record ID, then by name + postcode
- Configurable validation with Flagged sheet (invalid records stored with reason)
- Three-sheet Excel export: Data, Flagged, Summary — frozen headers, alternating row shading, auto-width columns
- Checkpoint / resume system — saves state every N records, atomic JSON write
- Cross-platform interactive keyboard controls: P pause · R resume · S status · Q quit
- Auto-protection: configurable stop time, low-disk guard, consecutive-failure cap, retry queue
- Rotating log file (5 MB cap, 3 backups) with clean console output
- `--dry-run` mode — reports counts without writing any files
- `--reset` flag — clears checkpoint for a fresh run
- Environment variable overrides: `SCRAPER_API_URL`, `SCRAPER_API_KEY`
