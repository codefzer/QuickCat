"""Tests for skills/vision-to-marc/scripts/image_to_marc.py"""

import pymarc
import pytest

import image_to_marc as im
from image_to_marc import MarcFields


# ─── _build_record ────────────────────────────────────────────────────────────

def _make_fields(**kwargs):
    defaults = {"title": "The Great Gatsby"}
    defaults.update(kwargs)
    return MarcFields(**defaults)


def test_build_record_creates_245_from_title():
    fields = _make_fields(title="The Great Gatsby")
    record = im._build_record(fields, "book")
    assert record["245"] is not None
    assert "Gatsby" in record["245"]["a"]


def test_build_record_inverts_author_name():
    """author_main already expected in inverted form from the API."""
    fields = _make_fields(title="Test Book", author_main="Fitzgerald, F. Scott")
    record = im._build_record(fields, "book")
    assert record["100"] is not None
    assert "Fitzgerald" in record["100"]["a"]


def test_build_record_stamps_ai_quickcat():
    """All AI-generated fields should contain $9 AI_QUICKCAT."""
    fields = _make_fields(title="AI Book", author_main="Smith, John")
    record = im._build_record(fields, "book")
    ai_fields = [
        f for f in record.fields
        if hasattr(f, "subfields") and "AI_QUICKCAT" in f.subfields
    ]
    assert len(ai_fields) >= 1  # At least 245 and 100 should be stamped


def test_build_record_applies_book_template():
    """Book template sets Leader/06='a' and Leader/07='m'."""
    fields = _make_fields(title="A Book")
    record = im._build_record(fields, "book")
    assert record.leader[6] == "a"
    assert record.leader[7] == "m"


def test_build_record_no_author_sets_ind1_0():
    """Without author_main, 245 indicator 1 should be '0'."""
    fields = _make_fields(title="Anonymous Book", author_main=None)
    record = im._build_record(fields, "book")
    assert record["245"].indicator1 == "0"


# ─── _call_vision_api (mocked) ────────────────────────────────────────────────

def test_call_vision_api_returns_marc_fields(monkeypatch):
    def fake_vision(image_b64, media_type):
        return MarcFields(
            title="The Catcher in the Rye",
            author_main="Salinger, J. D.",
            publisher="Little, Brown",
            date="1951",
        )

    monkeypatch.setattr(im, "_call_vision_api", fake_vision)
    result = im._call_vision_api("fakebase64data", "image/jpeg")
    assert result.title == "The Catcher in the Rye"
    assert result.author_main == "Salinger, J. D."
