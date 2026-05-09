"""
fetcher.py
==========
Handles all HTTP communication with the target directory API.

Supports:
  - POST and GET methods
  - Configurable pagination (loops until empty page or max_pages reached)
  - Two pagination modes:
      page_in_path: false  (default) — page number sent as a query/payload param
      page_in_path: true             — page number substituted into the URL via
                                       a {page} placeholder, e.g. /listings/{page}
  - Configurable timeout and polite inter-page delay
  - Navigating a nested JSON response via a dot-separated path
"""

import logging
import time
from typing import Any, Dict, List

import requests

log = logging.getLogger(__name__)

# Courtesy delay between paginated requests (seconds).
# Keeps request rate polite toward the target server.
# To make this configurable, add inter_page_delay to runtime: in config.yaml.
_INTER_PAGE_DELAY = 0.5


def fetch_all_records(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fetch all records from the configured API endpoint.

    Iterates through pages until either:
      - The API returns an empty list for the current page, or
      - The configured max_pages limit is reached.

    Pagination modes (set via api.pagination.page_in_path in config.yaml):
      page_in_path: false (default)
          The page number is injected into the payload/query string under
          the key named by api.pagination.page_param (e.g. "page").
      page_in_path: true
          The page number is substituted into the URL by replacing the
          literal placeholder {page}. Useful for REST-style URLs such as
          "https://example.com/directory/{page}". The payload is sent
          unchanged (no page key is added to it).

    Args:
        config: Full configuration dictionary loaded from config.yaml.

    Returns:
        Flat list of all raw record dicts returned by the API.

    Raises:
        requests.RequestException: On network or HTTP error.
    """
    api_cfg     = config["api"]
    runtime_cfg = config["runtime"]

    method        = api_cfg.get("method", "POST").upper()
    url           = api_cfg["url"]
    headers       = api_cfg.get("headers", {})
    base_payload  = dict(api_cfg.get("payload", {}))
    timeout       = runtime_cfg.get("request_timeout", 15)
    response_path : List[str] = api_cfg.get("response_path", [])

    pagination_cfg     = api_cfg.get("pagination", {})
    pagination_enabled = pagination_cfg.get("enabled", False)
    max_pages          = pagination_cfg.get("max_pages", 1)
    page_param         = pagination_cfg.get("page_param", "page")
    page_in_path       = pagination_cfg.get("page_in_path", False)

    all_records: List[Dict[str, Any]] = []
    page = 1

    while True:
        payload = dict(base_payload)

        if pagination_enabled:
            if page_in_path:
                # Substitute {page} placeholder directly in the URL.
                # The page number is not added to the payload/params.
                # Example: url = "https://example.com/listings/{page}"
                #          page=3  ->  "https://example.com/listings/3"
                request_url = url.replace("{page}", str(page))
            else:
                # Default behaviour: add page number as a payload/query parameter.
                request_url = url
                payload[page_param] = page
        else:
            request_url = url

        log.info("Fetching page %d (max: %d)...", page, max_pages)

        try:
            if method == "POST":
                response = requests.post(
                    request_url, headers=headers, data=payload, timeout=timeout
                )
            else:
                response = requests.get(
                    request_url, headers=headers, params=payload, timeout=timeout
                )
            response.raise_for_status()
            raw_json = response.json()

        except requests.exceptions.Timeout:
            log.error("Request timed out on page %d (timeout=%ds).", page, timeout)
            raise
        except requests.exceptions.HTTPError as exc:
            log.error("HTTP error on page %d: %s", page, exc)
            raise
        except requests.exceptions.RequestException as exc:
            log.error("Network error on page %d: %s", page, exc)
            raise

        records = _navigate_response(raw_json, response_path)

        if not records:
            log.info("Page %d returned 0 records — pagination complete.", page)
            break

        log.info("Page %d: %d records received.", page, len(records))
        all_records.extend(records)

        if not pagination_enabled or page >= max_pages:
            break

        page += 1
        time.sleep(_INTER_PAGE_DELAY)

    log.info("Total records fetched across all pages: %d", len(all_records))
    return all_records


def _navigate_response(
    data: Any, path: List[str]
) -> List[Dict[str, Any]]:
    """
    Traverse a nested JSON structure using a list of keys.

    Example:
        path = ["data", "results"]
        data = {"data": {"results": [...]}}
        -> returns the results list

    Args:
        data : Parsed JSON (dict or list).
        path : Ordered list of string keys to traverse.

    Returns:
        The value at the end of the path, or [] if unreachable / not a list.
    """
    current = data
    for key in path:
        if isinstance(current, dict):
            current = current.get(key, [])
        else:
            log.warning(
                "Response navigation failed at key '%s' — "
                "expected dict, got %s. Check api.response_path in config.",
                key, type(current).__name__,
            )
            return []

    if not isinstance(current, list):
        log.warning(
            "Expected a list at response path %s, got %s. "
            "Check api.response_path in config.",
            path, type(current).__name__,
        )
        return []

    return current
