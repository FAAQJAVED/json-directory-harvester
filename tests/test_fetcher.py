"""
tests/test_fetcher.py
=====================
Pytest tests for fetcher.py using unittest.mock to avoid real network calls.
"""

import pytest
from unittest.mock import MagicMock, patch

from fetcher import fetch_all_records, _navigate_response


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_config(
    method="POST",
    response_path=None,
    pagination_enabled=False,
    max_pages=1,
):
    return {
        "api": {
            "url": "https://example.com/api",
            "method": method,
            "headers": {},
            "payload": {"query": "test"},
            # Use explicit None check so an empty list [] is preserved as-is
            "response_path": response_path if response_path is not None else ["data", "results"],
            "pagination": {
                "enabled": pagination_enabled,
                "max_pages": max_pages,
                "page_param": "page",
            },
        },
        "runtime": {
            "request_timeout": 5,
        },
    }


def _mock_response(data):
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


SAMPLE_RECORDS = [
    {"id": "1", "name": "Alpha"},
    {"id": "2", "name": "Beta"},
]


# ─────────────────────────────────────────────────────────────────────
# POST fetch
# ─────────────────────────────────────────────────────────────────────

class TestPostFetch:
    @patch("fetcher.requests.post")
    def test_single_page_post_returns_records(self, mock_post):
        mock_post.return_value = _mock_response({"data": {"results": SAMPLE_RECORDS}})
        result = fetch_all_records(_make_config(method="POST"))
        assert result == SAMPLE_RECORDS
        mock_post.assert_called_once()

    @patch("fetcher.requests.post")
    def test_post_sends_payload_as_data(self, mock_post):
        mock_post.return_value = _mock_response({"data": {"results": []}})
        fetch_all_records(_make_config(method="POST"))
        _, kwargs = mock_post.call_args
        assert "data" in kwargs


# ─────────────────────────────────────────────────────────────────────
# GET fetch
# ─────────────────────────────────────────────────────────────────────

class TestGetFetch:
    @patch("fetcher.requests.get")
    def test_single_page_get_returns_records(self, mock_get):
        mock_get.return_value = _mock_response({"data": {"results": SAMPLE_RECORDS}})
        result = fetch_all_records(_make_config(method="GET"))
        assert result == SAMPLE_RECORDS
        mock_get.assert_called_once()

    @patch("fetcher.requests.get")
    def test_get_sends_payload_as_params(self, mock_get):
        mock_get.return_value = _mock_response({"data": {"results": []}})
        fetch_all_records(_make_config(method="GET"))
        _, kwargs = mock_get.call_args
        assert "params" in kwargs


# ─────────────────────────────────────────────────────────────────────
# Pagination
# ─────────────────────────────────────────────────────────────────────

class TestPagination:
    @patch("fetcher.time.sleep")
    @patch("fetcher.requests.post")
    def test_stops_on_empty_page(self, mock_post, mock_sleep):
        page1 = _mock_response({"data": {"results": SAMPLE_RECORDS}})
        page2 = _mock_response({"data": {"results": []}})
        mock_post.side_effect = [page1, page2]

        result = fetch_all_records(_make_config(pagination_enabled=True, max_pages=10))
        assert result == SAMPLE_RECORDS
        assert mock_post.call_count == 2

    @patch("fetcher.time.sleep")
    @patch("fetcher.requests.post")
    def test_stops_at_max_pages(self, mock_post, mock_sleep):
        mock_post.return_value = _mock_response({"data": {"results": SAMPLE_RECORDS}})
        result = fetch_all_records(_make_config(pagination_enabled=True, max_pages=3))
        assert mock_post.call_count == 3
        assert len(result) == len(SAMPLE_RECORDS) * 3

    @patch("fetcher.time.sleep")
    @patch("fetcher.requests.post")
    def test_all_pages_combined(self, mock_post, mock_sleep):
        r1 = [{"id": "1", "name": "A"}]
        r2 = [{"id": "2", "name": "B"}]
        mock_post.side_effect = [
            _mock_response({"data": {"results": r1}}),
            _mock_response({"data": {"results": r2}}),
            _mock_response({"data": {"results": []}}),
        ]
        result = fetch_all_records(_make_config(pagination_enabled=True, max_pages=10))
        assert len(result) == 2


# ─────────────────────────────────────────────────────────────────────
# page_in_path pagination mode
# ─────────────────────────────────────────────────────────────────────

def _make_config_path_pagination(max_pages=10):
    """Config with page_in_path=True and a {page} placeholder in the URL."""
    return {
        "api": {
            "url": "https://example.com/directory/{page}",
            "method": "GET",
            "headers": {},
            "payload": {"q": "test"},
            "response_path": ["data", "results"],
            "pagination": {
                "enabled": True,
                "max_pages": max_pages,
                "page_param": "page",   # should be ignored when page_in_path=True
                "page_in_path": True,
            },
        },
        "runtime": {"request_timeout": 5},
    }


class TestPageInPath:
    @patch("fetcher.time.sleep")
    @patch("fetcher.requests.get")
    def test_page_substituted_in_url(self, mock_get, mock_sleep):
        """Page number must be baked into the URL, not passed as a query param."""
        mock_get.side_effect = [
            _mock_response({"data": {"results": SAMPLE_RECORDS}}),
            _mock_response({"data": {"results": []}}),
        ]
        fetch_all_records(_make_config_path_pagination())

        first_call_args = mock_get.call_args_list[0]
        called_url = first_call_args[0][0]          # first positional arg = URL
        assert called_url == "https://example.com/directory/1", (
            f"Expected URL with page baked in, got: {called_url}"
        )

    @patch("fetcher.time.sleep")
    @patch("fetcher.requests.get")
    def test_page_increments_in_url(self, mock_get, mock_sleep):
        """Each subsequent page must increment the number in the URL."""
        mock_get.side_effect = [
            _mock_response({"data": {"results": [{"id": "1"}]}}),
            _mock_response({"data": {"results": [{"id": "2"}]}}),
            _mock_response({"data": {"results": []}}),
        ]
        fetch_all_records(_make_config_path_pagination())

        urls = [call[0][0] for call in mock_get.call_args_list]
        assert urls == [
            "https://example.com/directory/1",
            "https://example.com/directory/2",
            "https://example.com/directory/3",
        ]

    @patch("fetcher.time.sleep")
    @patch("fetcher.requests.get")
    def test_page_param_not_in_query_string(self, mock_get, mock_sleep):
        """When page_in_path=True, the page key must NOT appear in params."""
        mock_get.side_effect = [
            _mock_response({"data": {"results": SAMPLE_RECORDS}}),
            _mock_response({"data": {"results": []}}),
        ]
        fetch_all_records(_make_config_path_pagination())

        _, kwargs = mock_get.call_args_list[0]
        params = kwargs.get("params", {})
        assert "page" not in params, (
            f"page key should not be in query params when page_in_path=True, got: {params}"
        )

    @patch("fetcher.time.sleep")
    @patch("fetcher.requests.get")
    def test_other_payload_params_still_sent(self, mock_get, mock_sleep):
        """Non-page payload keys (e.g. 'q') must still be passed as params."""
        mock_get.side_effect = [
            _mock_response({"data": {"results": SAMPLE_RECORDS}}),
            _mock_response({"data": {"results": []}}),
        ]
        fetch_all_records(_make_config_path_pagination())

        _, kwargs = mock_get.call_args_list[0]
        params = kwargs.get("params", {})
        assert "q" in params, f"Non-page payload key 'q' missing from params: {params}"

    @patch("fetcher.time.sleep")
    @patch("fetcher.requests.get")
    def test_page_in_path_returns_correct_records(self, mock_get, mock_sleep):
        """End-to-end: records from all pages are combined correctly."""
        mock_get.side_effect = [
            _mock_response({"data": {"results": [{"id": "1"}]}}),
            _mock_response({"data": {"results": [{"id": "2"}]}}),
            _mock_response({"data": {"results": []}}),
        ]
        result = fetch_all_records(_make_config_path_pagination())
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "2"


# ─────────────────────────────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────────────────────────────

class TestErrorHandling:
    @patch("fetcher.requests.post")
    def test_http_error_raises(self, mock_post):
        import requests as req
        mock = MagicMock()
        mock.raise_for_status.side_effect = req.exceptions.HTTPError("404")
        mock_post.return_value = mock
        with pytest.raises(req.exceptions.HTTPError):
            fetch_all_records(_make_config())

    @patch("fetcher.requests.post")
    def test_timeout_raises(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.Timeout()
        with pytest.raises(req.exceptions.Timeout):
            fetch_all_records(_make_config())

    @patch("fetcher.requests.post")
    def test_network_error_raises(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("connection refused")
        with pytest.raises(req.exceptions.RequestException):
            fetch_all_records(_make_config())


# ─────────────────────────────────────────────────────────────────────
# _navigate_response
# ─────────────────────────────────────────────────────────────────────

class TestNavigateResponse:
    def test_nested_path_returns_list(self):
        data = {"data": {"results": SAMPLE_RECORDS}}
        assert _navigate_response(data, ["data", "results"]) == SAMPLE_RECORDS

    def test_empty_path_returns_raw_list(self):
        # Empty path: loop doesn't execute, current stays as SAMPLE_RECORDS (a list)
        assert _navigate_response(SAMPLE_RECORDS, []) == SAMPLE_RECORDS

    def test_missing_key_returns_empty_list(self):
        data = {"data": {}}
        assert _navigate_response(data, ["data", "results"]) == []

    def test_non_dict_intermediate_returns_empty_list(self):
        data = {"data": "not a dict"}
        assert _navigate_response(data, ["data", "results"]) == []

    def test_non_list_at_end_returns_empty_list(self):
        data = {"data": {"results": {"not": "a list"}}}
        assert _navigate_response(data, ["data", "results"]) == []
