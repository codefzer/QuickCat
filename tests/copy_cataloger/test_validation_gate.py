"""Tests for skills/copy-cataloger/scripts/validation_gate.py"""

import validation_gate as vg


# ─── validate_isbn13 ──────────────────────────────────────────────────────────

def test_validate_isbn13_valid():
    ok, msg = vg.validate_isbn13("9780743273565")
    assert ok is True
    assert msg == "valid"


def test_validate_isbn13_bad_check_digit():
    ok, _ = vg.validate_isbn13("9780743273566")
    assert ok is False


def test_validate_isbn13_too_short():
    ok, msg = vg.validate_isbn13("97807432")
    assert ok is False
    assert "digit" in msg.lower() or "must" in msg.lower()


# ─── validate_isbn10 ──────────────────────────────────────────────────────────

def test_validate_isbn10_valid():
    ok, msg = vg.validate_isbn10("0743273567")
    assert ok is True


def test_validate_isbn10_bad_check():
    ok, _ = vg.validate_isbn10("0743273568")
    assert ok is False


def test_validate_isbn10_with_x():
    """ISBN-10 ending in X as check digit."""
    ok, _ = vg.validate_isbn10("080442957X")
    assert ok is True


# ─── validate_lccn ────────────────────────────────────────────────────────────

def test_validate_lccn_prefix_digits_valid():
    ok, msg = vg.validate_lccn("n78890335")
    assert ok is True


def test_validate_lccn_legacy_digits_valid():
    ok, msg = vg.validate_lccn("12345678")
    assert ok is True


def test_validate_lccn_invalid_pattern():
    ok, _ = vg.validate_lccn("INVALID!")
    assert ok is False


# ─── detect_material_type ─────────────────────────────────────────────────────

def test_detect_material_type_hint_override():
    result = vg.detect_material_type("9780743273565", hint="ebook")
    assert result == "ebook"


def test_detect_material_type_issn_journal():
    # ISSN format → journal
    result = vg.detect_material_type("0028-0836")
    assert result == "journal"


def test_detect_material_type_isbn_defaults_to_book():
    result = vg.detect_material_type("9780743273565")
    assert result == "book"


def test_detect_material_type_unknown_hint_ignored():
    result = vg.detect_material_type("9780743273565", hint="dvd")
    assert result == "book"
