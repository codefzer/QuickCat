"""Tests for shared marc_utils module."""

import unicodedata
import marc_utils


def test_nfc_normalises_nfd():
    nfd = unicodedata.normalize("NFD", "café")
    result = marc_utils.nfc(nfd)
    assert result == unicodedata.normalize("NFC", "café")


def test_nfc_strips_whitespace():
    assert marc_utils.nfc("  hello  ") == "hello"


def test_nfc_none_returns_none():
    assert marc_utils.nfc(None) is None


def test_similarity_identical_strings():
    assert marc_utils.similarity("hello", "hello") == 1.0


def test_similarity_different_strings():
    assert marc_utils.similarity("hello", "goodbye") < 0.5


def test_similarity_case_insensitive():
    assert marc_utils.similarity("Hello", "hello") == 1.0
