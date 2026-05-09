"""
scraper.py
==========
JSON Directory Harvester — CLI entry point and orchestration loop.

Usage:
    python scraper.py [--config CONFIG] [--dry-run] [--reset]

Options:
    --config FILE   Path to YAML config file (default: config.yaml)
    --dry-run       Fetch and report record counts without writing any files
    --reset         Delete any saved checkpoint and start a fresh run

Runtime controls (press key in terminal while running):
    P   Pause the processing loop
    R   Resume after a pause
    S   Print current status to the console
    Q   Quit cleanly (saves checkpoint for later resumption)

Auto-protection features:
    - Stop time check         : exits cleanly at the configured stop time
    - Low disk guard          : auto-pauses if free disk drops below threshold
    - Consecutive failure cap : auto-pauses after N consecutive record errors
    - Retry queue             : failed records are retried once at the end
"""

__version__ = "1.0.0"

import argparse
import logging
import logging.handlers
import shutil
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Set

from checkpoint import CheckpointManager
from config import load_config
from controls import InputController, beep, sound_sequence
from exporter import export_excel
from fetcher import fetch_all_records
from processor import (
    apply_geo_filter,
    dedup_records,
    extract_row,
    validate_row,
)

log = logging.getLogger("scraper")


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="scraper.py",
        description=(
            "Configurable, resumable harvester for JSON-based directory APIs. "
            "Fetches records, validates and deduplicates them, and exports a "
            "formatted Excel workbook."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        metavar="FILE",
        help="Path to YAML config file (default: config.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch records and report counts without writing output files",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear any saved checkpoint and run from scratch",
    )
    return parser.parse_args()


# ─────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────

def setup_logging(output_dir: Path, prefix: str) -> None:
    """
    Configure root logger with:
      - Console handler (INFO level, no timestamps — clean terminal output)
      - Rotating file handler (DEBUG level, timestamped — full audit trail)

    Args:
        output_dir : Directory where the log file will be written.
        prefix     : Filename prefix (matches the Excel output prefix).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / f"{prefix}_{date.today().strftime('%Y%m%d')}.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console: clean, INFO-level only
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))

    # File: full DEBUG with timestamps, rotates at 5 MB (keeps 3 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
    )

    root.addHandler(console)
    root.addHandler(file_handler)


# ─────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────

def elapsed_str(start: float) -> str:
    """Return a human-readable elapsed time string: [Xm YYs]."""
    total_s = int(time.time() - start)
    return f"[{total_s // 60}m{total_s % 60:02d}s]"


def progress_bar(done: int, total: int, width: int = 35) -> str:
    """Return an ASCII progress bar string."""
    if total == 0:
        return "[" + "-" * width + "]"
    filled = int(width * done / total)
    return "[" + "█" * filled + "-" * (width - filled) + "]"


def stop_time_reached(stop_at: str) -> bool:
    """Return True if the current wall-clock time has reached or passed stop_at (HH:MM)."""
    return datetime.now().strftime("%H:%M") >= stop_at


def disk_ok(min_free_mb: int) -> bool:
    """Return True if free disk space exceeds min_free_mb."""
    free_mb = shutil.disk_usage(".").free / (1_024 * 1_024)
    return free_mb > min_free_mb


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # ── Load configuration ────────────────────────────────────────────
    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    output_cfg      = config.get("output", {})
    runtime_cfg     = config.get("runtime", {})
    field_mapping   = config.get("field_mapping", {})
    geo_cfg         = config.get("geo_filter", {})
    validation_cfg  = config.get("validation", {})

    output_dir      = Path(output_cfg.get("directory", "output"))
    prefix          = output_cfg.get("filename_prefix", "DirectoryExport")
    today_str       = date.today().strftime("%Y%m%d")
    excel_path      = output_dir / f"{prefix}_{today_str}.xlsx"
    checkpoint_path = output_dir / f"{prefix}_checkpoint.json"

    stop_at         = runtime_cfg.get("stop_at",         "23:00")
    save_every      = runtime_cfg.get("save_every",      10)
    progress_every  = runtime_cfg.get("progress_every",  10)
    low_disk_mb     = runtime_cfg.get("low_disk_mb",     500)
    max_consec_fail = runtime_cfg.get("max_consec_fail", 3)

    # ── Logging ───────────────────────────────────────────────────────
    setup_logging(output_dir, prefix)

    # ── Checkpoint + reset ────────────────────────────────────────────
    ckpt_mgr = CheckpointManager(str(checkpoint_path))
    if args.reset:
        ckpt_mgr.clear()
        log.info("Checkpoint cleared by --reset flag.")

    # ── Input controller ──────────────────────────────────────────────
    controller = InputController()
    if not args.dry_run:
        controller.start()

    # ─────────────────────────────────────────────────────────────────
    # PHASE 1: Fetch and prepare, or restore from checkpoint
    # ─────────────────────────────────────────────────────────────────
    ckpt          = ckpt_mgr.load()
    resuming      = ckpt is not None
    records_clean : List[Dict[str, Any]] = []
    processed_ids : Set[str]             = set()
    clean_rows    : List[Dict[str, str]] = []
    flagged_rows  : List[Dict[str, str]] = []

    if resuming:
        log.info("=" * 60)
        log.info("  JSON DIRECTORY HARVESTER — RESUMING FROM CHECKPOINT")
        log.info("=" * 60)
        sound_sequence([700, 900])

        processed_ids = set(ckpt.get("processed_ids", []))
        clean_rows    = ckpt.get("clean_rows",    [])
        flagged_rows  = ckpt.get("flagged_rows",  [])
        records_clean = ckpt.get("records_clean", [])

        log.info(
            "Checkpoint: %d already processed | %d clean | %d flagged",
            len(processed_ids), len(clean_rows), len(flagged_rows),
        )

    else:
        log.info("=" * 60)
        log.info("  JSON DIRECTORY HARVESTER — STARTING")
        log.info("  Config  : %s", args.config)
        log.info("  Version : %s", __version__)
        log.info("  Target  : %s", config["api"]["url"])
        if args.dry_run:
            log.info("  Mode    : DRY RUN (no files will be written)")
        log.info("=" * 60)
        sound_sequence([600, 800, 1000])

        log.info("\nPhase 1: Fetching records from API...")
        try:
            raw_records = fetch_all_records(config)
        except Exception as exc:
            log.error("Fatal: could not fetch from API — %s", exc)
            controller.stop()
            sys.exit(1)

        log.info("API returned %d total records.", len(raw_records))

        # Geographic filter
        filtered = apply_geo_filter(raw_records, geo_cfg)

        # Deduplication
        records_clean = dedup_records(filtered, field_mapping)
        dupes_removed = len(filtered) - len(records_clean)

        # ── Dry-run exits here ────────────────────────────────────────
        if args.dry_run:
            log.info("─" * 60)
            log.info("  DRY RUN RESULTS")
            log.info("  Raw from API      : %d", len(raw_records))
            log.info("  After geo filter  : %d", len(filtered))
            log.info("  After dedup       : %d", len(records_clean))
            log.info("  Duplicates removed: %d", dupes_removed)
            log.info("  Would write to    : %s", excel_path)
            log.info("─" * 60)
            controller.stop()
            return

        # Save Phase 1 state to checkpoint before entering Phase 2
        ckpt_mgr.save({
            "processed_ids": [],
            "clean_rows":    [],
            "flagged_rows":  [],
            "records_clean": records_clean,
            "dupes_removed": dupes_removed,
        })

    # ─────────────────────────────────────────────────────────────────
    # PHASE 2: Process each record
    # ─────────────────────────────────────────────────────────────────
    total       = len(records_clean)
    start_time  = time.time()
    paused      = False
    consec_fail = 0
    retry_queue : List[Dict[str, Any]] = []

    log.info("\nPhase 2: Processing %d records...", total)
    log.info("Controls: P=pause  R=resume  S=status  Q=quit\n")

    # ── Inner helpers ─────────────────────────────────────────────────

    def show_status(current_idx: int) -> None:
        pct       = int(100 * current_idx / total) if total else 0
        bar       = progress_bar(current_idx, total)
        ela       = elapsed_str(start_time)
        elapsed_s = max(1, int(time.time() - start_time))
        rate      = int(current_idx / elapsed_s * 60)
        eta_min   = int((total - current_idx) / max(rate, 1))
        print(
            f"\r  {ela} {bar} {pct:3d}% | "
            f"{current_idx}/{total} | "
            f"clean: {len(clean_rows)} | "
            f"flagged: {len(flagged_rows)} | "
            f"{rate}/min | ETA ~{eta_min}m",
            end="", flush=True,
        )

    def process_record(record: Dict[str, Any]) -> None:
        """Extract, validate, and route one record to clean or flagged list."""
        rid = str(record.get(field_mapping.get("id", "id"), "")).strip()
        if rid and rid in processed_ids:
            return

        row         = extract_row(record, field_mapping, output_cfg)
        flag_reason = validate_row(row, validation_cfg)

        if flag_reason:
            flagged_row = {**row, "Flag Reason": flag_reason}
            flagged_rows.append(flagged_row)
        else:
            clean_rows.append(row)

        if rid:
            processed_ids.add(rid)

    def save_state() -> None:
        """Persist current progress to the checkpoint file."""
        ckpt_mgr.save({
            "processed_ids": list(processed_ids),
            "clean_rows":    clean_rows,
            "flagged_rows":  flagged_rows,
            "records_clean": records_clean,
        })

    # ── Main processing loop ──────────────────────────────────────────
    for idx, record in enumerate(records_clean):

        # ── Keyboard controls ─────────────────────────────────────────
        key = controller.get_key()
        if key == "p":
            print("\n  [PAUSED] Press R to resume, Q to quit and save...")
            sound_sequence([900, 600])
            paused = True
        elif key == "q":
            print("\n  [STOPPING] Saving checkpoint and exiting...")
            break
        elif key == "s":
            print()
            show_status(idx)
            print()

        # ── Wait while paused ─────────────────────────────────────────
        while paused:
            k = controller.get_key()
            if k == "r":
                print("  [RESUMING]")
                sound_sequence([700, 900])
                paused = False
            elif k == "q":
                print("\n  [STOPPING] Saving checkpoint and exiting...")
                paused = False
                break
            time.sleep(0.2)

        # ── Auto-protections ──────────────────────────────────────────
        if stop_time_reached(stop_at):
            log.warning("\nStop time %s reached — saving and exiting.", stop_at)
            sound_sequence([900, 600])
            break

        if not disk_ok(low_disk_mb):
            log.warning(
                "\nLow disk space (< %d MB free) — auto-pausing. "
                "Free space, then press R to resume.",
                low_disk_mb,
            )
            sound_sequence([1000, 1000, 1000])
            paused = True
            continue

        # ── Skip already-processed records (relevant on resume) ───────
        rid = str(record.get(field_mapping.get("id", "id"), "")).strip()
        if rid and rid in processed_ids:
            continue

        # ── Process ───────────────────────────────────────────────────
        try:
            process_record(record)
            consec_fail = 0
        except Exception as exc:
            log.debug("Record error (id=%s): %s", rid, exc)
            beep(300, 120)
            consec_fail += 1
            retry_queue.append(record)
            if consec_fail >= max_consec_fail:
                log.warning(
                    "\n%d consecutive failures — auto-pausing. Press R to resume.",
                    max_consec_fail,
                )
                sound_sequence([1000, 1000, 1000])
                paused      = True
                consec_fail = 0
            continue

        show_status(idx + 1)

        if (idx + 1) % save_every == 0:
            save_state()

        if (idx + 1) % progress_every == 0:
            elapsed_s = max(1, int(time.time() - start_time))
            rate = int((idx + 1) / elapsed_s * 60)
            log.debug(
                "Progress: %d/%d | clean: %d | flagged: %d | %d/min",
                idx + 1, total, len(clean_rows), len(flagged_rows), rate,
            )

    # ── Retry queue ───────────────────────────────────────────────────
    if retry_queue:
        log.info("\nRetrying %d failed records...", len(retry_queue))
        for record in retry_queue:
            try:
                process_record(record)
            except Exception as exc:
                log.warning("Retry failed: %s", exc)

    # ─────────────────────────────────────────────────────────────────
    # PHASE 3: Export
    # ─────────────────────────────────────────────────────────────────
    elapsed_s = max(1, int(time.time() - start_time))
    all_done  = len(processed_ids) >= total

    stats: Dict[str, Any] = {
        "Run date":        date.today().isoformat(),
        "Source label":    output_cfg.get("source", ""),
        "Source endpoint": config["api"]["url"],
        "Total processed": len(records_clean),
        "Clean records":   len(clean_rows),
        "Flagged records": len(flagged_rows),
        "With phone":      sum(1 for r in clean_rows if r.get("Phone", "").strip()),
        "With website":    sum(1 for r in clean_rows if r.get("Website", "").strip()),
        "Elapsed":         f"{elapsed_s // 60}m {elapsed_s % 60:02d}s",
        "Status":          "COMPLETE" if all_done else "PARTIAL (checkpoint saved)",
        "Generated by":    "JSON Directory Harvester",
        "Version":         __version__,
    }

    try:
        export_excel(clean_rows, flagged_rows, excel_path, stats)
    except Exception as exc:
        log.error("Export failed: %s", exc)

    if all_done:
        ckpt_mgr.clear()
    else:
        save_state()

    # ── Terminal summary ──────────────────────────────────────────────
    print("\n\n" + "=" * 60)
    print("  JSON DIRECTORY HARVESTER —",
          "COMPLETE" if all_done else "STOPPED (checkpoint saved)")
    print("=" * 60)
    for key, value in stats.items():
        print(f"  {key:<24}: {value}")
    print(f"  Output file             : {excel_path}")
    print("=" * 60)

    controller.stop()
    sound_sequence([600, 800, 1000, 1200] if all_done else [900, 600])


if __name__ == "__main__":
    main()
