"""Tests for shared-resources/scripts/transaction_log.py"""

import json
from datetime import datetime, timezone
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


# ─── purge_log ────────────────────────────────────────────────────────────────

def test_purge_log_no_log_file_returns_zero(tmp_path):
    log_file = tmp_path / ".quickcat.log"
    removed = tl.purge_log(log_file)
    assert removed == 0


def test_purge_log_deletes_entire_log_when_no_keep_days(tmp_path):
    mrc = str(tmp_path / "records.mrc")
    rec = _make_record()
    tl.log_edit("skill", rec, rec, mrc_path=mrc)
    tl.log_edit("skill", rec, rec, mrc_path=mrc)
    log_file = tmp_path / ".quickcat.log"
    assert log_file.exists()

    removed = tl.purge_log(log_file, keep_days=None)

    assert removed == 2
    assert not log_file.exists()


def test_purge_log_returns_zero_when_all_entries_within_keep_days(tmp_path):
    mrc = str(tmp_path / "records.mrc")
    rec = _make_record()
    tl.log_edit("skill", rec, rec, mrc_path=mrc)
    log_file = tmp_path / ".quickcat.log"

    removed = tl.purge_log(log_file, keep_days=90)

    assert removed == 0
    # File still exists with the entry intact
    entries = tl.list_revisions("001:ocn999", mrc_path=mrc)
    assert len(entries) == 1


def test_purge_log_removes_old_entries_and_keeps_recent(tmp_path):
    from datetime import timedelta
    mrc = str(tmp_path / "records.mrc")
    log_file = tmp_path / ".quickcat.log"
    rec = _make_record()

    # Write one old entry (91 days ago) and one recent entry
    old_ts = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
    new_ts = datetime.now(timezone.utc).isoformat()

    old_entry = {
        "timestamp": old_ts,
        "skill": "old-skill",
        "record_id": "001:ocn999",
        "before": tl._record_to_dict(rec),
        "after": tl._record_to_dict(rec),
        "changes": [],
    }
    new_entry = {
        "timestamp": new_ts,
        "skill": "new-skill",
        "record_id": "001:ocn999",
        "before": tl._record_to_dict(rec),
        "after": tl._record_to_dict(rec),
        "changes": [],
    }
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(old_entry) + "\n")
        f.write(json.dumps(new_entry) + "\n")

    removed = tl.purge_log(log_file, keep_days=90)

    assert removed == 1
    remaining = tl.list_revisions("001:ocn999", mrc_path=mrc)
    assert len(remaining) == 1
    assert remaining[0]["skill"] == "new-skill"


# ─── round-trip serialization ─────────────────────────────────────────────────

def test_record_round_trip_preserves_fields(sample_record):
    d = tl._record_to_dict(sample_record)
    restored = tl._dict_to_record(d)
    # All tags should survive the round-trip
    original_tags = sorted(f.tag for f in sample_record.fields)
    restored_tags = sorted(f.tag for f in restored.fields)
    assert original_tags == restored_tags


# ─── clone_record ─────────────────────────────────────────────────────────────

def test_clone_record_is_different_object(sample_record):
    cloned = tl.clone_record(sample_record)
    assert cloned is not sample_record


def test_clone_record_preserves_leader_and_fields(sample_record):
    cloned = tl.clone_record(sample_record)
    assert cloned.leader == sample_record.leader
    original_tags = sorted(f.tag for f in sample_record.fields)
    cloned_tags = sorted(f.tag for f in cloned.fields)
    assert cloned_tags == original_tags


def test_clone_record_is_independent_from_original():
    """Mutating a field in the clone must not affect the source record."""
    record = _make_record("ocn456")
    cloned = tl.clone_record(record)
    # Mutate a subfield in the clone's 245
    cloned["245"].subfields[1] = "MUTATED"
    assert record["245"]["a"] == "Test title", (
        "Mutation of cloned field bled back into the original"
    )
