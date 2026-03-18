"""Tests for shared-resources/scripts/parse_marc.py"""

import unicodedata

import pymarc
import pytest

import parse_marc as pm


# ─── record_to_dict ───────────────────────────────────────────────────────────

def test_record_to_dict_title(sample_record):
    d = pm.record_to_dict(sample_record)
    # Trailing " /" should be stripped
    assert d["title"] == "The great Gatsby"


def test_record_to_dict_author(sample_record):
    d = pm.record_to_dict(sample_record)
    assert "Fitzgerald" in d["author_main"]


def test_record_to_dict_isbn_as_list(sample_record):
    """ISBN must be a list (even if empty for this record)."""
    d = pm.record_to_dict(sample_record)
    assert isinstance(d["isbn"], list)


def test_record_to_dict_subjects_as_list(sample_record):
    d = pm.record_to_dict(sample_record)
    assert isinstance(d["subjects_topical"], list)
    assert any("fiction" in s.lower() for s in d["subjects_topical"])


def test_record_to_dict_ai_tagged_fields(ai_tagged_record):
    d = pm.record_to_dict(ai_tagged_record)
    assert "520" in d["ai_tagged_fields"]


def test_record_to_dict_record_id_none_when_001_missing():
    r = pymarc.Record()
    r.add_field(pymarc.Field("245", ["1", "0"], ["a", "Some title"]))
    d = pm.record_to_dict(r)
    assert d["record_id"] is None


# ─── parse_binary ─────────────────────────────────────────────────────────────

def test_parse_binary_reads_mrc(tmp_mrc_file):
    results = pm.parse_binary(str(tmp_mrc_file))
    assert len(results) == 1
    assert results[0]["title"] == "The great Gatsby"


# ─── _clean (NFC normalization) ───────────────────────────────────────────────

def test_clean_nfc_strip():
    """NFD input must become NFC after _clean."""
    nfd_string = unicodedata.normalize("NFD", "café")
    result = pm._clean(nfd_string)
    assert unicodedata.is_normalized("NFC", result)
    assert result == "café"
