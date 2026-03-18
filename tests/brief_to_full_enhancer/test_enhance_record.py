"""Tests for skills/brief-to-full-enhancer/scripts/enhance_record.py"""

import pymarc
import pytest

import enhance_record as er


# ─── _build_context ───────────────────────────────────────────────────────────

def test_build_context_title_extracted(sample_record):
    ctx = er._build_context(sample_record)
    assert "Gatsby" in ctx["title"]


def test_build_context_subjects_joined(sample_record):
    ctx = er._build_context(sample_record)
    assert "fiction" in ctx["subjects"].lower()


def test_build_context_fallback_author_unknown():
    r = pymarc.Record()
    r.leader = "00000nam a2200000   4500"
    r.add_field(pymarc.Field("245", ["1", "0"], ["a", "Anonymous work"]))
    ctx = er._build_context(r)
    assert ctx["author"] == "Unknown"


# ─── _call_claude (mocked) ────────────────────────────────────────────────────

def test_call_claude_returns_dict(monkeypatch):
    def fake_call(prompt):
        return {
            "summary_520": "Examines the American Dream.",
            "contents_505": "Chapter 1 -- Chapter 2 -- Chapter 3.",
        }

    monkeypatch.setattr(er, "_call_claude", fake_call)
    result = er._call_claude("any prompt")
    assert "summary_520" in result
    assert "contents_505" in result


# ─── enhance_record ───────────────────────────────────────────────────────────

def _mock_claude_returns(monkeypatch, summary="Examines the novel.", contents="Ch 1 -- Ch 2."):
    monkeypatch.setattr(er, "_call_claude", lambda prompt: {
        "summary_520": summary,
        "contents_505": contents,
    })


def test_enhance_record_adds_520(sample_record, monkeypatch):
    _mock_claude_returns(monkeypatch)
    updated, changes = er.enhance_record(sample_record, ["520", "505"])
    assert updated["520"] is not None


def test_enhance_record_adds_505(sample_record, monkeypatch):
    _mock_claude_returns(monkeypatch)
    updated, changes = er.enhance_record(sample_record, ["520", "505"])
    assert updated["505"] is not None


def test_enhance_record_stamps_ai_quickcat_on_520(sample_record, monkeypatch):
    _mock_claude_returns(monkeypatch)
    updated, _ = er.enhance_record(sample_record, ["520"])
    field = updated["520"]
    subs = field.subfields
    nine_vals = [subs[i + 1] for i in range(0, len(subs), 2) if subs[i] == "9"]
    assert any("AI_QUICKCAT" in v for v in nine_vals)


def test_enhance_record_skips_existing_520_when_not_forced(monkeypatch):
    _mock_claude_returns(monkeypatch)
    r = pymarc.Record()
    r.leader = "00000nam a2200000   4500"
    r.add_field(pymarc.Field("245", ["1", "0"], ["a", "Some Book"]))
    r.add_field(pymarc.Field("520", [" ", " "], ["a", "Existing summary."]))
    updated, changes = er.enhance_record(r, ["520"], force=False)
    # Existing 520 should be untouched
    assert updated["520"]["a"] == "Existing summary."
    assert not any("520" in c for c in changes)


def test_enhance_record_force_overwrites_520(monkeypatch):
    _mock_claude_returns(monkeypatch, summary="New AI summary.")
    r = pymarc.Record()
    r.leader = "00000nam a2200000   4500"
    r.add_field(pymarc.Field("245", ["1", "0"], ["a", "Some Book"]))
    r.add_field(pymarc.Field("520", [" ", " "], ["a", "Old summary."]))
    updated, changes = er.enhance_record(r, ["520"], force=True)
    assert "New AI summary." in updated["520"]["a"]


def test_enhance_record_returns_changes_list(sample_record, monkeypatch):
    _mock_claude_returns(monkeypatch)
    _, changes = er.enhance_record(sample_record, ["520", "505"])
    assert isinstance(changes, list)
    assert len(changes) >= 1
