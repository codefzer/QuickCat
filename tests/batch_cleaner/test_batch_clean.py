"""Tests for skills/batch-cleaner/scripts/batch_clean.py"""

import unicodedata

import pymarc
import pytest

import batch_clean as bc


# ─── _should_delete ───────────────────────────────────────────────────────────

def test_should_delete_exact_match():
    assert bc._should_delete("035", ["035", "019"], []) is True


def test_should_delete_range_9xx():
    assert bc._should_delete("950", [], [["900", "999"]]) is True


def test_should_delete_outside_all():
    assert bc._should_delete("245", ["035"], [["900", "999"]]) is False


def test_should_delete_boundary_start():
    assert bc._should_delete("900", [], [["900", "999"]]) is True


def test_should_delete_boundary_end():
    assert bc._should_delete("999", [], [["900", "999"]]) is True


# ─── _normalize_field ─────────────────────────────────────────────────────────

def test_normalize_field_control_nfd():
    nfd = unicodedata.normalize("NFD", "café")
    f = pymarc.Field("001", data=nfd)
    count = bc._normalize_field(f)
    assert count == 1
    assert unicodedata.is_normalized("NFC", f.data)


def test_normalize_field_already_nfc():
    f = pymarc.Field("001", data="already NFC text")
    count = bc._normalize_field(f)
    assert count == 0


def test_normalize_field_variable_subfield_nfd():
    nfd = unicodedata.normalize("NFD", "café")
    f = pymarc.Field("500", [" ", " "], ["a", nfd])
    count = bc._normalize_field(f)
    assert count == 1
    assert unicodedata.is_normalized("NFC", f.subfields[1])


# ─── clean_record ─────────────────────────────────────────────────────────────

def _make_dirty_record():
    r = pymarc.Record()
    leader = list("00000nam a2200000   4500")
    leader[9] = " "  # Not Unicode
    r.leader = "".join(leader)
    r.add_field(pymarc.Field("001", data="ocn999"))
    r.add_field(pymarc.Field("245", ["1", "0"], ["a", "Test title"]))
    r.add_field(pymarc.Field("035", [" ", " "], ["a", "(OCoLC)12345"]))
    r.add_field(pymarc.Field("938", [" ", " "], ["a", "vendor data"]))
    r.add_field(pymarc.Field("003", data="OLD_ORG"))
    return r


def test_clean_record_deletes_listed_tags():
    r = _make_dirty_record()
    cleaned, _ = bc.clean_record(r, delete_tags=["035", "938"], delete_ranges=[], org_code="MYLIB")
    assert cleaned["035"] is None
    assert cleaned["938"] is None


def test_clean_record_preserves_245():
    r = _make_dirty_record()
    cleaned, _ = bc.clean_record(r, delete_tags=["035"], delete_ranges=[], org_code="MYLIB")
    assert cleaned["245"] is not None
    assert cleaned["245"]["a"] == "Test title"


def test_clean_record_sets_leader_9_to_a():
    r = _make_dirty_record()
    cleaned, stats = bc.clean_record(r, delete_tags=[], delete_ranges=[], org_code="MYLIB")
    assert cleaned.leader[9] == "a"
    assert stats["leader_fixed"] is True


def test_clean_record_stamps_003_with_org_code():
    r = _make_dirty_record()
    cleaned, _ = bc.clean_record(r, delete_tags=[], delete_ranges=[], org_code="TESTLIB")
    assert cleaned["003"].data == "TESTLIB"


def test_clean_record_replaces_existing_003():
    r = _make_dirty_record()
    assert r["003"].data == "OLD_ORG"
    cleaned, _ = bc.clean_record(r, delete_tags=[], delete_ranges=[], org_code="NEWLIB")
    # Only one 003 should exist
    fields_003 = cleaned.get_fields("003")
    assert len(fields_003) == 1
    assert fields_003[0].data == "NEWLIB"
