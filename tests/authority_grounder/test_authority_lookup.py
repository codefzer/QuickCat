"""Tests for skills/authority-grounder/scripts/authority_lookup.py"""

import pytest
import respx
import httpx

import pymarc

import authority_lookup as al


# ─── _best_match ──────────────────────────────────────────────────────────────

def test_best_match_above_threshold():
    candidates = [
        {"label": "American fiction", "uri": "http://id.loc.gov/authorities/subjects/sh85004306"},
        {"label": "British fiction", "uri": "http://id.loc.gov/authorities/subjects/sh85016859"},
    ]
    result = al._best_match("American fiction", candidates, threshold=0.85)
    assert result is not None
    assert result["score"] >= 0.85
    assert "American fiction" in result["label"]


def test_best_match_below_threshold():
    candidates = [
        {"label": "Completely unrelated subject heading here", "uri": "http://id.loc.gov/foo"},
    ]
    result = al._best_match("Short title", candidates, threshold=0.85)
    assert result is None


def test_best_match_empty_candidates():
    result = al._best_match("Any heading", [], threshold=0.85)
    assert result is None


# ─── _normalize_isbd_punctuation ──────────────────────────────────────────────

def test_normalize_isbd_100_a_adds_period():
    """100 $a without period or comma should get a period if no $d follows."""
    f = pymarc.Field("100", ["1", " "], ["a", "Fitzgerald, F. Scott"])
    result = al._normalize_isbd_punctuation(f)
    assert result["a"].endswith(".")


def test_normalize_isbd_650_adds_period():
    f = pymarc.Field("650", [" ", "0"], ["a", "American fiction"])
    result = al._normalize_isbd_punctuation(f)
    assert result["a"].endswith(".")


def test_normalize_isbd_100_a_before_d_gets_comma():
    """100 $a before $d must end with comma, not period."""
    f = pymarc.Field("100", ["1", " "], ["a", "Fitzgerald, F. Scott", "d", "1896-1940."])
    result = al._normalize_isbd_punctuation(f)
    # $a should have a comma before $d
    a_idx = result.subfields.index("a") + 1
    assert result.subfields[a_idx].endswith(",")


# ─── _suggest (mocked) ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_suggest_returns_label_uri_pairs():
    mock_response = [
        "American fiction",
        ["American fiction", "American fiction--History and criticism"],
        [],
        [
            "http://id.loc.gov/authorities/subjects/sh85004306",
            "http://id.loc.gov/authorities/subjects/sh85004307",
        ],
    ]
    respx.get("https://id.loc.gov/authorities/subjects/suggest").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    results = await al._suggest("American fiction", vocab="subjects")
    assert len(results) == 2
    assert results[0]["label"] == "American fiction"
    assert "id.loc.gov" in results[0]["uri"]


# ─── authority_lookup integration ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_authority_lookup_injects_0_on_match(monkeypatch):
    """If _suggest returns a good match, 650 should get $0 URI and $2 lcsh."""
    async def mock_suggest(heading, vocab="subjects"):
        return [{"label": heading, "uri": "http://id.loc.gov/authorities/subjects/sh85004306"}]

    monkeypatch.setattr(al, "_suggest", mock_suggest)

    record = pymarc.Record()
    record.leader = "00000nam a2200000   4500"
    record.add_field(pymarc.Field("650", [" ", "0"], ["a", "American fiction"]))

    updated, audit = await al.authority_lookup(record, threshold=0.85)

    field = updated["650"]
    subs = field.subfields
    # Find $0
    zero_idx = [i for i in range(0, len(subs), 2) if subs[i] == "0"]
    assert zero_idx, "Expected $0 subfield to be injected"
    assert "id.loc.gov" in subs[zero_idx[0] + 1]

    # Find $2
    two_idx = [i for i in range(0, len(subs), 2) if subs[i] == "2"]
    assert two_idx, "Expected $2 subfield to be injected"
    assert subs[two_idx[0] + 1] == "lcsh"
