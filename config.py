"""
config.py
=========
Loads and validates the YAML configuration file.

Secrets (API keys, tokens) are never stored in config.yaml — they are
injected at runtime from environment variables defined in .env.

Supported environment variable overrides:
  SCRAPER_API_URL   -> config.api.url
  SCRAPER_API_KEY   -> config.api.headers.Authorization  (as Bearer token)
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError as exc:
    raise ImportError(
        "PyYAML is required. Install with: pip install pyyaml"
    ) from exc

log = logging.getLogger(__name__)

# Top-level sections that must be present for the scraper to function
_REQUIRED_TOP_LEVEL = {"api", "field_mapping", "output", "runtime"}


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load, validate, and return the configuration dictionary.

    Also applies any environment variable overrides (see module docstring).

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Validated configuration dictionary.

    Raises:
        FileNotFoundError : Config file does not exist.
        ValueError        : Required top-level keys are missing, or api.url
                            is empty after environment variable overrides.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Copy config.yaml.example -> config.yaml and fill in your values."
        )

    with open(path, "r", encoding="utf-8") as f:
        config: Dict[str, Any] = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError("config.yaml must be a YAML mapping (key: value pairs).")

    missing = _REQUIRED_TOP_LEVEL - set(config.keys())
    if missing:
        raise ValueError(
            f"config.yaml is missing required top-level sections: {missing}"
        )

    _apply_env_overrides(config)

    # Validate that the API URL is set and not a placeholder
    api_url = config.get("api", {}).get("url", "")
    if not api_url or api_url == "YOUR_API_ENDPOINT_URL":
        raise ValueError(
            "api.url is not configured. Set it in config.yaml or via the "
            "SCRAPER_API_URL environment variable."
        )

    log.info("Configuration loaded from: %s", path)
    return config


def _apply_env_overrides(config: Dict[str, Any]) -> None:
    """
    Overwrite config values with environment variables where set.
    Environment variables take precedence over config file values.
    """
    if url := os.environ.get("SCRAPER_API_URL"):
        config.setdefault("api", {})["url"] = url
        log.debug("api.url overridden from SCRAPER_API_URL environment variable.")

    if key := os.environ.get("SCRAPER_API_KEY"):
        api_headers = config.setdefault("api", {}).setdefault("headers", {})
        api_headers["Authorization"] = f"Bearer {key}"
        log.debug("Authorization header applied from SCRAPER_API_KEY environment variable.")
