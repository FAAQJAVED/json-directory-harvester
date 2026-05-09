"""
processor.py
============
Pure data transformation functions — no I/O, no side effects.

Responsibilities:
  - Geographic bounding-box filtering
  - Two-pass deduplication (by ID, then by name + postcode)
  - Field extraction and normalisation (HTML stripping, phone formatting, etc.)
  - Row validation against configurable rules

All field names are driven by config.yaml — nothing is hardcoded.
"""

import logging
import re
from typing import Any, Dict, List, Tuple

log = logging.getLogger(__name__)


# ── HTML / text cleaning ──────────────────────────────────────────────

def strip_html(text: str) -> str:
    """
    Remove all HTML tags and collapse whitespace to a single space.

    Args:
        text: Raw string, possibly containing HTML markup.

    Returns:
        Cleaned plain-text string.
    """
    if not text:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", without_tags).strip()


# ── Phone normalisation ───────────────────────────────────────────────

def validate_phone(raw: str) -> str:
    """
    Normalise a phone number string — strips punctuation and validates
    length (7-15 digits, covering local to international formats).

    - Strips spaces, dashes, parentheses, dots, and plus signs.
    - Returns the cleaned digit string if between 7 and 15 characters
      (E.164 international standard range).
    - Returns an empty string if the result falls outside that range.

    Args:
        raw: Raw phone string from the API.

    Returns:
        Normalised digit-only phone string, or "" if invalid.
    """
    if not raw:
        return ""
    digits = re.sub(r"[\s\-\(\)\.\+]", "", str(raw))
    return digits if 7 <= len(digits) <= 15 else ""


# ── Nested field access ───────────────────────────────────────────────

def get_nested(obj: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Safely access a nested dict value using a dot-separated key path.

    Example:
        get_nested(record, "coordinates.latitude", 0)

    Args:
        obj    : The dictionary to traverse.
        path   : Dot-separated key path (e.g. "address.postcode").
        default: Value to return if the path is unreachable.

    Returns:
        The value at the given path, or default if not found.
    """
    current: Any = obj
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


# ── Geographic filtering ──────────────────────────────────────────────

def apply_geo_filter(
    records: List[Dict[str, Any]], geo_cfg: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Retain only records whose coordinates fall within the configured bounding box.

    If geo_filter.enabled is False in config, the original list is returned unchanged.

    Args:
        records : Raw records from the API.
        geo_cfg : The geo_filter section of config.yaml.

    Returns:
        Filtered list of records within the bounding box.
    """
    if not geo_cfg.get("enabled", False):
        log.info("Geo filter disabled — all %d records retained.", len(records))
        return records

    lat_min: float = geo_cfg["lat_min"]
    lat_max: float = geo_cfg["lat_max"]
    lng_min: float = geo_cfg["lng_min"]
    lng_max: float = geo_cfg["lng_max"]
    lat_field: str = geo_cfg.get("lat_field", "latitude")
    lng_field: str = geo_cfg.get("lng_field", "longitude")

    filtered = []
    for record in records:
        try:
            lat = float(get_nested(record, lat_field, 0) or 0)
            lng = float(get_nested(record, lng_field, 0) or 0)
            if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
                filtered.append(record)
        except (ValueError, TypeError):
            pass  # records with unparseable coordinates are excluded

    log.info(
        "Geo filter: %d -> %d records (bounding box lat %.2f-%.2f, lng %.2f-%.2f).",
        len(records), len(filtered), lat_min, lat_max, lng_min, lng_max,
    )
    return filtered


# ── Deduplication ─────────────────────────────────────────────────────

def dedup_records(
    records: List[Dict[str, Any]], field_mapping: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Remove duplicate records using a two-pass strategy.

    Pass 1 — by unique ID:
        If two records share an ID, keep the one with more filled fields
        (richer data wins).

    Pass 2 — by name + postcode:
        Records with identical name and postcode are collapsed to one,
        even if they carry different IDs.

    Args:
        records       : Records after geographic filtering.
        field_mapping : Maps logical names to actual API field names.

    Returns:
        Deduplicated list of records.
    """
    id_field       = field_mapping.get("id",       "id")
    name_field     = field_mapping.get("name",     "name")
    postcode_field = field_mapping.get("postcode", "postcode")

    # ── Pass 1: deduplicate by ID ─────────────────────────────────────
    by_id: Dict[str, Dict[str, Any]] = {}
    no_id_records: List[Dict[str, Any]] = []

    for record in records:
        rid = str(record.get(id_field, "")).strip()
        if not rid:
            no_id_records.append(record)
            continue
        if rid not in by_id:
            by_id[rid] = record
        else:
            filled_new = sum(1 for v in record.values() if v)
            filled_old = sum(1 for v in by_id[rid].values() if v)
            if filled_new > filled_old:
                by_id[rid] = record  # prefer the richer record

    candidates = list(by_id.values()) + no_id_records

    # ── Pass 2: deduplicate by name + postcode ────────────────────────
    seen: set = set()
    unique: List[Dict[str, Any]] = []

    for record in candidates:
        key: Tuple[str, str] = (
            str(record.get(name_field, "")).strip().lower(),
            str(record.get(postcode_field, "")).strip().upper(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)

    removed = len(records) - len(unique)
    log.info(
        "Deduplication: %d -> %d records (%d duplicates removed).",
        len(records), len(unique), removed,
    )
    return unique


# ── Row extraction ────────────────────────────────────────────────────

def extract_row(
    record: Dict[str, Any],
    field_mapping: Dict[str, str],
    output_cfg: Dict[str, Any],
) -> Dict[str, str]:
    """
    Extract, clean, and normalise a single API record into the output row format.

    Field names in the output are fixed ("Name", "Phone", etc.) because
    they map to the Excel column headers. The *source* field names are driven
    entirely by config.yaml -> field_mapping.

    Args:
        record       : Raw record dict from the API.
        field_mapping: Maps output field names to API field names.
        output_cfg   : The output section of config.yaml (for category/source).

    Returns:
        Normalised row dict with string values.
    """
    name = strip_html(
        str(record.get(field_mapping.get("name", "name"), "") or "")
    ).strip()

    phone = validate_phone(
        record.get(field_mapping.get("phone", "phone"), "") or ""
    )

    website = str(
        record.get(field_mapping.get("website", "website"), "") or ""
    ).strip()
    if website and not website.startswith(("http://", "https://")):
        website = "https://" + website

    postcode = str(
        record.get(field_mapping.get("postcode", "postcode"), "") or ""
    ).strip().upper()

    return {
        "Name":     name,
        "Phone":    phone,
        "Website":  website,
        "Postcode": postcode,
        "Category": output_cfg.get("category", ""),
        "Source":   output_cfg.get("source", ""),
    }


# ── Row validation ────────────────────────────────────────────────────

def validate_row(row: Dict[str, str], validation_cfg: Dict[str, Any]) -> str:
    """
    Validate a processed row against configurable rules.

    Args:
        row            : The normalised output row dict.
        validation_cfg : The validation section of config.yaml.

    Returns:
        A non-empty reason string if the row is suspicious/invalid,
        or an empty string if the row passes all checks.
    """
    name             = row.get("Name", "").strip()
    postcode         = row.get("Postcode", "").strip()
    min_name_len     = validation_cfg.get("min_name_length", 3)
    require_postcode = validation_cfg.get("require_postcode", True)
    postcode_regex   = validation_cfg.get("postcode_regex", "")

    if len(name) < min_name_len:
        return f"Name too short (minimum {min_name_len} characters)"
    if require_postcode and not postcode:
        return "Missing postcode"
    if postcode_regex and postcode:
        if not re.match(postcode_regex, postcode, re.IGNORECASE):
            return "Invalid postcode format"
    return ""
