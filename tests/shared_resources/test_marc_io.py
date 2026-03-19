"""Tests for shared marc_io module."""

import pymarc
import pytest
import marc_io


def test_read_mrc_returns_records(tmp_mrc_file):
    records = marc_io.read_mrc(tmp_mrc_file)
    assert len(records) == 1
    assert isinstance(records[0], pymarc.Record)


def test_read_mrc_empty_file_returns_empty_list(tmp_path):
    empty = tmp_path / "empty.mrc"
    empty.write_bytes(b"")
    records = marc_io.read_mrc(empty)
    assert records == []


def test_write_mrc_produces_readable_file(sample_record, tmp_path):
    out = tmp_path / "out.mrc"
    marc_io.write_mrc([sample_record], out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_round_trip_preserves_records(sample_record, tmp_path):
    out = tmp_path / "round.mrc"
    marc_io.write_mrc([sample_record, sample_record], out)
    records = marc_io.read_mrc(out)
    assert len(records) == 2
    assert records[0]["245"]["a"] == sample_record["245"]["a"]
