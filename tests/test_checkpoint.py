"""
tests/test_checkpoint.py
========================
Pytest tests for CheckpointManager in checkpoint.py.
All tests use tmp_path for isolation — no files written to the project directory.
"""

import json
import pytest
from pathlib import Path

from checkpoint import CheckpointManager


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def ckpt_path(tmp_path) -> Path:
    return tmp_path / "test_checkpoint.json"


@pytest.fixture
def manager(ckpt_path) -> CheckpointManager:
    return CheckpointManager(str(ckpt_path))


SAMPLE_STATE = {
    "processed_ids": ["1", "2", "3"],
    "clean_rows": [{"Name": "Acme", "Phone": "5551234567"}],
    "flagged_rows": [{"Name": "X", "Flag Reason": "Name too short"}],
    "records_clean": [{"id": "1", "name": "Acme"}],
}


# ─────────────────────────────────────────────────────────────────────
# save / load round-trip
# ─────────────────────────────────────────────────────────────────────

class TestSaveLoad:
    def test_save_then_load_round_trips_state(self, manager):
        manager.save(SAMPLE_STATE)
        loaded = manager.load()
        assert loaded == SAMPLE_STATE

    def test_load_returns_none_when_no_file(self, manager):
        assert manager.load() is None

    def test_save_creates_file(self, manager, ckpt_path):
        manager.save(SAMPLE_STATE)
        assert ckpt_path.exists()

    def test_saved_file_is_valid_json(self, manager, ckpt_path):
        manager.save(SAMPLE_STATE)
        with open(ckpt_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["processed_ids"] == ["1", "2", "3"]

    def test_overwrite_updates_state(self, manager):
        manager.save(SAMPLE_STATE)
        new_state = {**SAMPLE_STATE, "processed_ids": ["1", "2", "3", "4"]}
        manager.save(new_state)
        loaded = manager.load()
        assert len(loaded["processed_ids"]) == 4

    def test_load_with_corrupted_file_returns_none(self, ckpt_path):
        # Write invalid JSON to simulate a mid-write corruption
        ckpt_path.write_text("{ not valid json !!!", encoding="utf-8")
        manager = CheckpointManager(str(ckpt_path))
        assert manager.load() is None


# ─────────────────────────────────────────────────────────────────────
# clear
# ─────────────────────────────────────────────────────────────────────

class TestClear:
    def test_clear_deletes_file(self, manager, ckpt_path):
        manager.save(SAMPLE_STATE)
        assert ckpt_path.exists()
        manager.clear()
        assert not ckpt_path.exists()

    def test_clear_on_missing_file_does_not_raise(self, manager):
        manager.clear()  # should complete silently

    def test_load_after_clear_returns_none(self, manager):
        manager.save(SAMPLE_STATE)
        manager.clear()
        assert manager.load() is None


# ─────────────────────────────────────────────────────────────────────
# exists
# ─────────────────────────────────────────────────────────────────────

class TestExists:
    def test_exists_false_before_save(self, manager):
        assert manager.exists() is False

    def test_exists_true_after_save(self, manager):
        manager.save(SAMPLE_STATE)
        assert manager.exists() is True

    def test_exists_false_after_clear(self, manager):
        manager.save(SAMPLE_STATE)
        manager.clear()
        assert manager.exists() is False


# ─────────────────────────────────────────────────────────────────────
# Atomic write — no .tmp left behind
# ─────────────────────────────────────────────────────────────────────

class TestAtomicWrite:
    def test_tmp_file_not_left_after_successful_save(self, manager, ckpt_path):
        manager.save(SAMPLE_STATE)
        tmp_path = ckpt_path.with_suffix(".tmp")
        assert not tmp_path.exists(), ".tmp file should not remain after successful save"

    def test_checkpoint_file_exists_after_save(self, manager, ckpt_path):
        manager.save(SAMPLE_STATE)
        assert ckpt_path.exists()

    def test_multiple_saves_no_tmp_accumulation(self, manager, ckpt_path):
        for i in range(5):
            manager.save({**SAMPLE_STATE, "processed_ids": list(range(i))})
        tmp_path = ckpt_path.with_suffix(".tmp")
        assert not tmp_path.exists()
