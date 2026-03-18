"""Tests for skills/marc-exporter/scripts/export.py"""

import pymarc
import pytest

import export_marc as em


# ─── _is_ai_tagged ────────────────────────────────────────────────────────────

def test_is_ai_tagged_true(ai_tagged_record):
    is_ai, ai_tags = em._is_ai_tagged(ai_tagged_record)
    assert is_ai is True
    assert "520" in ai_tags
    assert ai_tags["520"] >= 1


def test_is_ai_tagged_false(sample_record):
    is_ai, ai_tags = em._is_ai_tagged(sample_record)
    assert is_ai is False
    assert ai_tags == {}


# ─── _is_copy_cataloged ───────────────────────────────────────────────────────

def test_is_copy_cataloged_true(sample_record):
    # sample_record has a 035 field
    assert em._is_copy_cataloged(sample_record) is True


def test_is_copy_cataloged_false():
    r = pymarc.Record()
    r.leader = "00000nam a2200000   4500"
    r.add_field(pymarc.Field("001", data="local001"))
    r.add_field(pymarc.Field("245", ["1", "0"], ["a", "No 035 here"]))
    assert em._is_copy_cataloged(r) is False


# ─── _validate ────────────────────────────────────────────────────────────────

def test_validate_ok(sample_record, validation_rules):
    valid, issues = em._validate(sample_record, validation_rules)
    assert valid is True
    assert issues == []


def test_validate_missing_245(validation_rules):
    r = pymarc.Record()
    r.leader = "00000nam a2200000   4500"
    r.add_field(pymarc.Field("001", data="ocn999"))
    valid, issues = em._validate(r, validation_rules)
    assert valid is False
    assert any("245" in issue for issue in issues)


def test_validate_missing_001(validation_rules):
    r = pymarc.Record()
    r.leader = "00000nam a2200000   4500"
    r.add_field(pymarc.Field("245", ["1", "0"], ["a", "A title."]))
    valid, issues = em._validate(r, validation_rules)
    assert valid is False
    assert any("001" in issue for issue in issues)
