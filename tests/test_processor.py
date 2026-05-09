"""
tests/test_processor.py
=======================
Pytest tests for all pure functions in processor.py.
No network calls. All test data is inline.
"""

import pytest
from processor import (
    apply_geo_filter,
    dedup_records,
    extract_row,
    get_nested,
    strip_html,
    validate_phone,
    validate_row,
)


# ─────────────────────────────────────────────────────────────────────
# strip_html
# ─────────────────────────────────────────────────────────────────────

class TestStripHtml:
    def test_removes_single_tag(self):
        assert strip_html("<b>Hello</b>") == "Hello"

    def test_removes_nested_tags(self):
        assert strip_html("<div><p>Hello <em>world</em></p></div>") == "Hello world"

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_plain_text_unchanged(self):
        assert strip_html("Just plain text") == "Just plain text"

    def test_collapses_whitespace(self):
        assert strip_html("<p>Hello</p>   <p>World</p>") == "Hello World"

    def test_strips_only_tags_leaves_content(self):
        assert strip_html("<a href='x'>Link text</a>") == "Link text"


# ─────────────────────────────────────────────────────────────────────
# validate_phone
# ─────────────────────────────────────────────────────────────────────

class TestValidatePhone:
    def test_valid_international_number(self):
        # +1 (212) 555-0100 -> 12125550100 = 11 digits, within 7-15 range
        assert validate_phone("+1 (212) 555-0100") == "12125550100"

    def test_valid_ten_digit_number(self):
        # 10 digits after stripping spaces
        assert validate_phone("020 7946 0958") == "02079460958"

    def test_too_short_returns_empty(self):
        # 5 digits — below minimum of 7
        assert validate_phone("12345") == ""

    def test_too_long_returns_empty(self):
        # 16 digits — above maximum of 15
        assert validate_phone("1234567890123456") == ""

    def test_punctuation_stripped(self):
        # dashes, dots, plus all removed
        assert validate_phone("+44-20.7946.0958") == "442079460958"

    def test_empty_string_returns_empty(self):
        assert validate_phone("") == ""

    def test_exactly_seven_digits_valid(self):
        assert validate_phone("1234567") == "1234567"

    def test_exactly_fifteen_digits_valid(self):
        assert validate_phone("123456789012345") == "123456789012345"

    def test_no_country_code_conversion(self):
        # Generic normaliser: +44 prefix is NOT converted to leading 0
        assert validate_phone("+447911123456") == "447911123456"

    def test_dots_stripped(self):
        # Dots are stripped by the generic regex
        assert validate_phone("212.555.0100") == "2125550100"


# ─────────────────────────────────────────────────────────────────────
# get_nested
# ─────────────────────────────────────────────────────────────────────

class TestGetNested:
    def test_flat_key(self):
        assert get_nested({"name": "Acme"}, "name") == "Acme"

    def test_dot_separated_path(self):
        obj = {"address": {"postcode": "10001"}}
        assert get_nested(obj, "address.postcode") == "10001"

    def test_missing_key_returns_default(self):
        assert get_nested({"a": 1}, "b", "default") == "default"

    def test_non_dict_intermediate_returns_default(self):
        obj = {"address": "not a dict"}
        assert get_nested(obj, "address.postcode", None) is None

    def test_deeply_nested(self):
        obj = {"a": {"b": {"c": 42}}}
        assert get_nested(obj, "a.b.c") == 42


# ─────────────────────────────────────────────────────────────────────
# apply_geo_filter
# ─────────────────────────────────────────────────────────────────────

GEO_CFG = {
    "enabled": True,
    "lat_min": 40.48,
    "lat_max": 40.92,
    "lng_min": -74.26,
    "lng_max": -73.70,
    "lat_field": "lat",
    "lng_field": "lng",
}

RECORD_INSIDE  = {"id": "1", "name": "Inside",  "lat": 40.71, "lng": -74.00}
RECORD_OUTSIDE = {"id": "2", "name": "Outside", "lat": 51.50, "lng": -0.12}


class TestApplyGeoFilter:
    def test_disabled_returns_all(self):
        cfg = {**GEO_CFG, "enabled": False}
        records = [RECORD_INSIDE, RECORD_OUTSIDE]
        assert apply_geo_filter(records, cfg) == records

    def test_record_inside_box_kept(self):
        result = apply_geo_filter([RECORD_INSIDE], GEO_CFG)
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_record_outside_box_excluded(self):
        result = apply_geo_filter([RECORD_OUTSIDE], GEO_CFG)
        assert result == []

    def test_mixed_records(self):
        result = apply_geo_filter([RECORD_INSIDE, RECORD_OUTSIDE], GEO_CFG)
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_unparseable_coords_excluded(self):
        bad = {"id": "3", "lat": "not_a_number", "lng": "bad"}
        result = apply_geo_filter([bad], GEO_CFG)
        assert result == []


# ─────────────────────────────────────────────────────────────────────
# dedup_records
# ─────────────────────────────────────────────────────────────────────

FIELD_MAP = {"id": "id", "name": "name", "postcode": "postcode"}


class TestDedupRecords:
    def test_dedup_by_id_keeps_richer_record(self):
        r1 = {"id": "1", "name": "Acme", "postcode": "10001", "phone": ""}
        r2 = {"id": "1", "name": "Acme", "postcode": "10001", "phone": "5551234567"}
        result = dedup_records([r1, r2], FIELD_MAP)
        assert len(result) == 1
        assert result[0]["phone"] == "5551234567"

    def test_dedup_by_name_postcode(self):
        r1 = {"id": "1", "name": "Acme Corp", "postcode": "10001"}
        r2 = {"id": "2", "name": "Acme Corp", "postcode": "10001"}
        result = dedup_records([r1, r2], FIELD_MAP)
        assert len(result) == 1

    def test_records_with_no_id_are_kept(self):
        r1 = {"id": "",  "name": "No ID Corp",  "postcode": "10002"}
        r2 = {"id": "",  "name": "No ID Corp2", "postcode": "10003"}
        result = dedup_records([r1, r2], FIELD_MAP)
        assert len(result) == 2

    def test_distinct_records_all_kept(self):
        r1 = {"id": "1", "name": "Alpha", "postcode": "10001"}
        r2 = {"id": "2", "name": "Beta",  "postcode": "10002"}
        result = dedup_records([r1, r2], FIELD_MAP)
        assert len(result) == 2

    def test_name_postcode_comparison_is_case_insensitive(self):
        r1 = {"id": "1", "name": "acme corp", "postcode": "sw1a"}
        r2 = {"id": "2", "name": "ACME CORP", "postcode": "SW1A"}
        result = dedup_records([r1, r2], FIELD_MAP)
        assert len(result) == 1


# ─────────────────────────────────────────────────────────────────────
# extract_row
# ─────────────────────────────────────────────────────────────────────

FIELD_MAPPING = {
    "id":       "id",
    "name":     "name",
    "phone":    "phone",
    "website":  "website",
    "postcode": "postcode",
}
OUTPUT_CFG = {"category": "Member", "source": "Directory Harvester"}


class TestExtractRow:
    def _extract(self, record):
        return extract_row(record, FIELD_MAPPING, OUTPUT_CFG)

    def test_html_stripped_from_name(self):
        row = self._extract({"name": "<b>Acme Corp</b>", "phone": "", "website": "", "postcode": ""})
        assert row["Name"] == "Acme Corp"

    def test_output_uses_name_key_not_company_name(self):
        row = self._extract({"name": "Test", "phone": "", "website": "", "postcode": ""})
        assert "Name" in row
        assert "Company Name" not in row

    def test_phone_cleaned(self):
        row = self._extract({"name": "X", "phone": "+1 (212) 555-0100", "website": "", "postcode": ""})
        assert row["Phone"] == "12125550100"

    def test_website_gets_https_prefix(self):
        row = self._extract({"name": "X", "phone": "", "website": "example.com", "postcode": ""})
        assert row["Website"] == "https://example.com"

    def test_existing_https_not_doubled(self):
        row = self._extract({"name": "X", "phone": "", "website": "https://example.com", "postcode": ""})
        assert row["Website"] == "https://example.com"

    def test_postcode_uppercased(self):
        row = self._extract({"name": "X", "phone": "", "website": "", "postcode": "sw1a 1aa"})
        assert row["Postcode"] == "SW1A 1AA"

    def test_category_and_source_from_config(self):
        row = self._extract({"name": "X", "phone": "", "website": "", "postcode": ""})
        assert row["Category"] == "Member"
        assert row["Source"] == "Directory Harvester"


# ─────────────────────────────────────────────────────────────────────
# validate_row
# ─────────────────────────────────────────────────────────────────────

VAL_CFG = {
    "min_name_length": 3,
    "require_postcode": True,
    "postcode_regex": r"^\d{5}",
}


class TestValidateRow:
    def _row(self, name="Acme Corp", postcode="10001"):
        return {"Name": name, "Postcode": postcode}

    def test_name_too_short_flagged(self):
        reason = validate_row(self._row(name="AB"), VAL_CFG)
        assert "too short" in reason

    def test_missing_postcode_flagged(self):
        reason = validate_row(self._row(postcode=""), VAL_CFG)
        assert "postcode" in reason.lower()

    def test_invalid_postcode_format_flagged(self):
        reason = validate_row(self._row(postcode="SW1A"), VAL_CFG)
        assert "Invalid postcode" in reason

    def test_valid_row_passes(self):
        reason = validate_row(self._row(), VAL_CFG)
        assert reason == ""

    def test_postcode_regex_disabled(self):
        cfg = {**VAL_CFG, "postcode_regex": ""}
        reason = validate_row(self._row(postcode="SW1A"), cfg)
        assert reason == ""

    def test_postcode_not_required(self):
        cfg = {**VAL_CFG, "require_postcode": False, "postcode_regex": ""}
        reason = validate_row(self._row(postcode=""), cfg)
        assert reason == ""
