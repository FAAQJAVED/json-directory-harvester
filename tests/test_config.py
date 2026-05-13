"""
tests/test_config.py
====================
Pytest tests for config.py — load_config() and _apply_env_overrides().

All tests are pure-function or use tmp_path for isolation.
No network calls. Full suite runs in under 1 second.
"""

import pytest
from pathlib import Path
from config import load_config


MINIMAL_VALID_CONFIG = """\
api:
  url: "https://example.com/api"
  method: "POST"
  headers: {}
  payload: {}
  response_path: ["data"]
  pagination:
    enabled: false
    page_param: "page"
    max_pages: 1
    page_in_path: false

geo_filter:
  enabled: false

field_mapping:
  id: "id"
  name: "name"
  phone: "phone"
  website: "website"
  postcode: "postcode"

output:
  directory: "output"
  filename_prefix: "Export"
  category: "Member"
  source: "Test"

runtime:
  stop_at: "23:00"
  save_every: 10
  progress_every: 10
  request_timeout: 15
  low_disk_mb: 500
  max_consec_fail: 3
"""


def _write_config(tmp_path: Path, content: str) -> str:
    p = tmp_path / "config.yaml"
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestFileNotFound:

    def test_raises_when_file_missing(self, tmp_path):
        missing = str(tmp_path / "does_not_exist.yaml")
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(missing)

    def test_error_message_contains_copy_hint(self, tmp_path):
        missing = str(tmp_path / "no_file.yaml")
        with pytest.raises(FileNotFoundError, match="config.yaml.example"):
            load_config(missing)


class TestMissingRequiredSections:

    def test_raises_when_api_missing(self, tmp_path):
        content = MINIMAL_VALID_CONFIG.replace("api:\n", "")
        path = _write_config(tmp_path, content)
        with pytest.raises(ValueError, match="missing required"):
            load_config(path)

    def test_raises_when_output_missing(self, tmp_path):
        lines = [l for l in MINIMAL_VALID_CONFIG.splitlines()
                 if not l.startswith("output:")]
        path = _write_config(tmp_path, "\n".join(lines))
        with pytest.raises(ValueError, match="missing required"):
            load_config(path)

    def test_raises_when_runtime_missing(self, tmp_path):
        lines = [l for l in MINIMAL_VALID_CONFIG.splitlines()
                 if not l.startswith("runtime:")]
        path = _write_config(tmp_path, "\n".join(lines))
        with pytest.raises(ValueError, match="missing required"):
            load_config(path)

    def test_raises_when_field_mapping_missing(self, tmp_path):
        lines = [l for l in MINIMAL_VALID_CONFIG.splitlines()
                 if not l.startswith("field_mapping:")]
        path = _write_config(tmp_path, "\n".join(lines))
        with pytest.raises(ValueError, match="missing required"):
            load_config(path)


class TestPlaceholderUrlGuard:

    def test_raises_on_placeholder_url(self, tmp_path):
        content = MINIMAL_VALID_CONFIG.replace(
            '"https://example.com/api"', '"YOUR_API_ENDPOINT_URL"'
        )
        path = _write_config(tmp_path, content)
        with pytest.raises(ValueError, match="api.url is not configured"):
            load_config(path)

    def test_raises_on_empty_url(self, tmp_path):
        content = MINIMAL_VALID_CONFIG.replace(
            '"https://example.com/api"', '""'
        )
        path = _write_config(tmp_path, content)
        with pytest.raises(ValueError, match="api.url is not configured"):
            load_config(path)

    def test_valid_url_does_not_raise(self, tmp_path):
        path = _write_config(tmp_path, MINIMAL_VALID_CONFIG)
        config = load_config(path)
        assert config["api"]["url"] == "https://example.com/api"


class TestEnvVarOverrides:

    def test_scraper_api_url_overrides_config(self, tmp_path, monkeypatch):
        path = _write_config(tmp_path, MINIMAL_VALID_CONFIG)
        monkeypatch.setenv("SCRAPER_API_URL", "https://override.example.com/api")
        config = load_config(path)
        assert config["api"]["url"] == "https://override.example.com/api"

    def test_scraper_api_key_sets_bearer_token(self, tmp_path, monkeypatch):
        path = _write_config(tmp_path, MINIMAL_VALID_CONFIG)
        monkeypatch.setenv("SCRAPER_API_KEY", "mysecretkey")
        config = load_config(path)
        assert config["api"]["headers"]["Authorization"] == "Bearer mysecretkey"

    def test_env_var_not_set_does_not_override(self, tmp_path, monkeypatch):
        path = _write_config(tmp_path, MINIMAL_VALID_CONFIG)
        monkeypatch.delenv("SCRAPER_API_URL", raising=False)
        monkeypatch.delenv("SCRAPER_API_KEY", raising=False)
        config = load_config(path)
        assert config["api"]["url"] == "https://example.com/api"
        assert "Authorization" not in config["api"].get("headers", {})
