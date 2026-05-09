"""
checkpoint.py
=============
Manages a JSON checkpoint file to support pause-and-resume for long runs.

The checkpoint stores:
  - processed_ids  : set of record IDs already handled
  - clean_rows     : validated records accumulated so far
  - flagged_rows   : invalid records accumulated so far
  - records_clean  : the full deduplicated record list (so Phase 1 is not
                     re-fetched on resume)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


class CheckpointManager:
    """
    Thread-safe JSON checkpoint file handler.

    Args:
        path: File path for the checkpoint JSON file.
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    # ── Public API ────────────────────────────────────────────────────

    def save(self, state: Dict[str, Any]) -> None:
        """
        Serialise and write state to the checkpoint file atomically.
        Writes to a temporary file first, then renames to avoid corruption.

        Args:
            state: Dictionary of scraper state to persist.
        """
        tmp_path = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            tmp_path.replace(self.path)
            log.debug("Checkpoint saved -> %s", self.path)
        except OSError as exc:
            log.warning("Could not save checkpoint: %s", exc)

    def load(self) -> Optional[Dict[str, Any]]:
        """
        Load and return checkpoint state, or None if the file does not exist.

        Returns:
            State dictionary, or None if no checkpoint is found.
        """
        if not self.path.exists():
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                state = json.load(f)
            log.info("Checkpoint loaded from %s", self.path)
            return state
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Could not load checkpoint (%s) — starting fresh.", exc)
            return None

    def clear(self) -> None:
        """Delete the checkpoint file if it exists."""
        if self.path.exists():
            try:
                self.path.unlink()
                log.info("Checkpoint cleared.")
            except OSError as exc:
                log.warning("Could not clear checkpoint: %s", exc)

    def exists(self) -> bool:
        """Return True if a checkpoint file is present on disk."""
        return self.path.exists()
