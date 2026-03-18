"""Tests for shared-resources/scripts/transaction_log.py"""

import json
from pathlib import Path

import pymarc
import pytest

import transaction_log as tl


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_record(record_id="ocn999"):
    r = pymarc.Record()
    r.leader = "00000nam a2200000   4500"
    r.add_field(pymarc.Field("001", data=record_id))
    r.add_field(pymarc.Field("245", ["1", "0"], ["a", "Test title"]))
    return r


# ─── log_edit ─────────────────────────────────────────────────────────────────

def test_log_edit_creates_log_file(tmp_path):
    mrc = str(tmp_path / "records.mrc")
    before = _make_record()
    after = _make_record()
    tl.log_edit("test-skill", before, after, mrc_path=mrc)
    log_file = tmp_path / ".quickcat.log"
    assert log_file.exists()


def test_log_edit_appends_on_second_call(tmp_path):
    mrc = str(tmp_path / "records.mrc")
    before = _make_record()
    after = _make_record()
    tl.log_edit("skill-a", before, after, mrc_path=mrc)
    tl.log_edit("skill-b", before, after, mrc_path=mrc)
    log_file = tmp_path / ".quickcat.log"
    lines = [l for l in log_file.read_text().splitlines() if l.strip()]
    assert len(lines) == 2


def test_log_edit_entry_has_required_keys(tmp_path):
    mrc = str(tmp_path / "records.mrc")
    before = _make_record()
    after = _make_record()
    tl.log_edit("skill", before, after, mrc_path=mrc, changes=["added 520"])
    log_file = tmp_path / ".quickcat.log"
    entry = json.loads(log_file.read_text().strip())
    for key in ("timestamp", "skill", "record_id", "before", "after", "changes"):
        assert key in entry


# ─── list_revisions ───────────────────────────────────────────────────────────

def test_list_revisions_returns_empty_when_no_log(tmp_path):
    mrc = str(tmp_path / "records.mrc")
    result = tl.list_revisions("001:ocn999", mrc_path=mrc)
    assert result == []


def test_list_revisions_filters_by_record_id(tmp_path):
    mrc = str(tmp_path / "records.mrc")
    rec_a = _make_record("AAA")
    rec_b = _make_record("BBB")
    tl.log_edit("skill", rec_a, rec_a, mrc_path=mrc)
    tl.log_edit("skill", rec_b, rec_b, mrc_path=mrc)
    results = tl.list_revisions("001:AAA", mrc_path=mrc)
    assert len(results) == 1
    assert results[0]["record_id"] == "001:AAA"


# ─── rollback ─────────────────────────────────────────────────────────────────

def test_rollback_writes_file_and_returns_record(tmp_path):
    mrc = str(tmp_path / "records.mrc")
    before = _make_record("ocn123")
    after = _make_record("ocn123")
    after.add_field(pymarc.Field("520", [" ", " "], ["a", "Added summary."]))
    tl.log_edit("enhancer", before, after, mrc_path=mrc)
    # Get the timestamp from the log
    log_file = tmp_path / ".quickcat.log"
    entry = json.loads(log_file.read_text().strip())
    ts = entry["timestamp"]
    restored = tl.rollback("001:ocn123", ts, mrc)
    assert restored is not None
    assert isinstance(restored, pymarc.Record)
    # The rolled-back record should NOT have the 520 added by 'after'
    assert restored["520"] is None


def test_rollback_returns_none_for_unmatched_timestamp(tmp_path):
    mrc = str(tmp_path / "records.mrc")
    rec = _make_record("ocn777")
    tl.log_edit("skill", rec, rec, mrc_path=mrc)
    result = tl.rollback("001:ocn777", "2000-01-01T00:00:00+00:00", mrc)
    assert result is None


# ─── round-trip serialization ─────────────────────────────────────────────────

def test_record_round_trip_preserves_fields(sample_record):
    d = tl._record_to_dict(sample_record)
    restored = tl._dict_to_record(d)
    # All tags should survive the round-trip
    original_tags = sorted(f.tag for f in sample_record.fields)
    restored_tags = sorted(f.tag for f in restored.fields)
    assert original_tags == restored_tags
