"""Unit tests for lib/sheets_client.py — tests that don't require real Google API."""

import pytest
from lib.sheets_client import mask_token, _USER_HEADERS, _user_to_row


class TestMaskToken:
    def test_normal_token(self):
        assert mask_token("abcdefghij1234") == "**********1234"

    def test_short_token(self):
        assert mask_token("abc") == "abc"

    def test_empty(self):
        assert mask_token("") == ""

    def test_exact_length(self):
        assert mask_token("1234") == "1234"

    def test_custom_visible(self):
        assert mask_token("abcdefgh", visible=2) == "******gh"


class TestUserToRow:
    def test_full_user(self):
        user = {h: f"val_{h}" for h in _USER_HEADERS}
        row = _user_to_row(user)
        assert len(row) == len(_USER_HEADERS)
        assert row[0] == "val_email"

    def test_partial_user(self):
        user = {"email": "test@example.com", "name": "Test"}
        row = _user_to_row(user)
        assert len(row) == len(_USER_HEADERS)
        assert row[0] == "test@example.com"
        assert row[1] == "Test"
        # Missing fields should be empty string
        assert row[2] == ""

    def test_header_order(self):
        assert _USER_HEADERS[0] == "email"
        assert "line_channel_token" in _USER_HEADERS
        assert "active" in _USER_HEADERS
