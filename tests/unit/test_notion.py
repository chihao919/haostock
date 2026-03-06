"""Unit tests for Notion client module."""

import pytest
from unittest.mock import patch, AsyncMock
from lib.notion import (
    _get_text,
    _get_number,
    _get_select,
    _get_multi_select,
    _get_date,
    NotionAPIError,
)


class TestPropertyExtractors:
    def test_get_text_from_title(self):
        prop = {"title": [{"plain_text": "NVDA"}]}
        assert _get_text(prop) == "NVDA"

    def test_get_text_from_rich_text(self):
        prop = {"rich_text": [{"plain_text": "台積電"}]}
        assert _get_text(prop) == "台積電"

    def test_get_text_empty(self):
        assert _get_text({"title": []}) == ""
        assert _get_text({}) == ""

    def test_get_number(self):
        assert _get_number({"number": 100.5}) == 100.5

    def test_get_number_none(self):
        assert _get_number({"number": None}) is None

    def test_get_select(self):
        prop = {"select": {"name": "Firstrade"}}
        assert _get_select(prop) == "Firstrade"

    def test_get_select_none(self):
        assert _get_select({"select": None}) is None

    def test_get_multi_select(self):
        prop = {"multi_select": [{"name": "Momentum"}, {"name": "Value"}]}
        assert _get_multi_select(prop) == ["Momentum", "Value"]

    def test_get_multi_select_empty(self):
        assert _get_multi_select({"multi_select": []}) == []

    def test_get_date(self):
        prop = {"date": {"start": "2026-03-13"}}
        assert _get_date(prop) == "2026-03-13"

    def test_get_date_none(self):
        assert _get_date({"date": None}) is None


class TestNotionAPIError:
    def test_error_message(self):
        err = NotionAPIError(500, "Internal Server Error")
        assert err.status_code == 500
        assert "500" in str(err)
        assert "Internal Server Error" in str(err)
