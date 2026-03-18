"""Tests for skills/record-rollback/scripts/rollback.py"""

import json
import sys
from pathlib import Path

import pymarc
import pytest

import rollback as rb
import transaction_log as tl


# ─── _load_log ────────────────────────────────────────────────────────────────

def test_load_log_empty_file(tmp_path):
    log = tmp_path / ".quickcat.log"
    log.write_text("")
    entries = rb._load_log(str(log))
    assert entries == []


def test_load_log_parses_entries(tmp_path):
    log = tmp_path / ".quickcat.log"
    entry = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "skill": "test-skill",
        "record_id": "001:ocn123",
        "before": {},
        "after": {},
        "changes": ["something changed"],
    }
    log.write_text(json.dumps(entry) + "\n")
    entries = rb._load_log(str(log))
    assert len(entries) == 1
    assert entries[0]["record_id"] == "001:ocn123"


def test_load_log_skips_corrupt_json(tmp_path):
    log = tmp_path / ".quickcat.log"
    good = json.dumps({"timestamp": "2026-01-01T00:00:00+00:00", "skill": "s",
                       "record_id": "001:aaa", "before": {}, "after": {}, "changes": []})
    log.write_text(good + "\n" + "NOT VALID JSON\n" + good + "\n")
    entries = rb._load_log(str(log))
    assert len(entries) == 2


# ─── cmd_list ─────────────────────────────────────────────────────────────────

def _write_log_entries(log_path: Path, entries: list[dict]) -> None:
    with open(log_path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _make_entry(record_id, skill="test"):
    return {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "skill": skill,
        "record_id": record_id,
        "before": {},
        "after": {},
        "changes": ["changed something"],
    }


def test_cmd_list_no_filter_prints_summary(tmp_path, capsys):
    log = tmp_path / ".quickcat.log"
    _write_log_entries(log, [_make_entry("001:aaa"), _make_entry("001:bbb")])

    log_path = str(log)

    class Args:
        pass

    args = Args()
    args.log = log_path
    args.record_id = None

    rb.cmd_list(args)
    captured = capsys.readouterr()
    assert "001:aaa" in captured.out
    assert "001:bbb" in captured.out


def test_cmd_list_filtered_by_record_id(tmp_path, capsys):
    log = tmp_path / ".quickcat.log"
    _write_log_entries(log, [_make_entry("001:aaa"), _make_entry("001:bbb")])

    log_path = str(log)

    class Args:
        pass

    args = Args()
    args.log = log_path
    args.record_id = "001:aaa"

    rb.cmd_list(args)
    captured = capsys.readouterr()
    assert "001:aaa" in captured.out
    assert "001:bbb" not in captured.out
