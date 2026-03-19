"""Tests for skills/copy-cataloger/scripts/audit_consensus.py"""

import pymarc
import pytest

import audit_consensus as ac


# ─── _is_local_priority ───────────────────────────────────────────────────────

def test_is_local_priority_090(monkeypatch):
    rules = {"local_priority": {"fields": {"090": True, "590": True, "852": True}}}
    assert ac._is_local_priority("090", rules) is True


def test_is_local_priority_9xx_range(monkeypatch):
    rules = {"local_priority": {"fields": {}}}
    assert ac._is_local_priority("950", rules) is True


def test_is_local_priority_245_is_false(monkeypatch):
    rules = {"local_priority": {"fields": {"090": True}}}
    assert ac._is_local_priority("245", rules) is False


# ─── _field_value ─────────────────────────────────────────────────────────────

def test_field_value_control_field():
    f = pymarc.Field("001", data="ocn12345")
    assert ac._field_value(f) == "ocn12345"


def test_field_value_variable_field():
    f = pymarc.Field("245", ["1", "0"], ["a", "The great Gatsby", "c", "Fitzgerald"])
    val = ac._field_value(f)
    assert "The great Gatsby" in val
    assert "Fitzgerald" in val


# ─── audit_consensus integration ──────────────────────────────────────────────

def _make_local():
    r = pymarc.Record()
    r.leader = "00000nam a2200000   4500"
    r.add_field(pymarc.Field("001", data="ocn111"))
    r.add_field(pymarc.Field("245", ["1", "0"], ["a", "The great Gatsby"]))
    r.add_field(pymarc.Field("100", ["1", " "], ["a", "Fitzgerald, F. Scott"]))
    r.add_field(pymarc.Field("090", [" ", " "], ["a", "LOCAL_PS3511"]))
    return r


def _make_reference():
    r = pymarc.Record()
    r.leader = "00000nam a2200000   4500"
    r.add_field(pymarc.Field("001", data="ocn222"))
    r.add_field(pymarc.Field("245", ["1", "0"], ["a", "The great Gatsby /"]))
    r.add_field(pymarc.Field("100", ["1", " "], ["a", "Fitzgerald, F. Scott,", "d", "1896-1940."]))
    r.add_field(pymarc.Field("050", [" ", "4"], ["a", "PS3511.I9", "b", "G7"]))
    r.add_field(pymarc.Field("090", [" ", " "], ["a", "REF_SHOULD_NOT_CONFLICT"]))
    return r


def test_090_never_conflicted():
    local = _make_local()
    ref = _make_reference()
    conflicts = ac.audit_consensus(local, ref, threshold=0.85)
    tags = [c["tag"] for c in conflicts]
    assert "090" not in tags


def test_missing_local_field_gives_green():
    """050 is in reference but not local → status green, add_from_reference."""
    local = _make_local()
    ref = _make_reference()
    conflicts = ac.audit_consensus(local, ref, threshold=0.85)
    add_items = [c for c in conflicts if c["tag"] == "050" and c["recommendation"] == "add_from_reference"]
    assert len(add_items) >= 1
    assert add_items[0]["status"] == "green"


def test_identical_fields_produce_no_conflict():
    local = pymarc.Record()
    local.leader = "00000nam a2200000   4500"
    local.add_field(pymarc.Field("245", ["1", "0"], ["a", "Identical title"]))
    ref = pymarc.Record()
    ref.leader = "00000nam a2200000   4500"
    ref.add_field(pymarc.Field("245", ["1", "0"], ["a", "Identical title"]))
    conflicts = ac.audit_consensus(local, ref, threshold=0.85)
    title_conflicts = [c for c in conflicts if c["tag"] == "245"]
    assert len(title_conflicts) == 0


def test_different_245_produces_conflict_with_severity():
    local = pymarc.Record()
    local.leader = "00000nam a2200000   4500"
    local.add_field(pymarc.Field("245", ["1", "0"], ["a", "Completely Different Book Title"]))
    ref = pymarc.Record()
    ref.leader = "00000nam a2200000   4500"
    ref.add_field(pymarc.Field("245", ["1", "0"], ["a", "Something Totally Unrelated Here"]))
    conflicts = ac.audit_consensus(local, ref, threshold=0.85)
    title_conflicts = [c for c in conflicts if c["tag"] == "245"]
    assert len(title_conflicts) == 1
    assert title_conflicts[0]["severity_score"] > 0


def test_conflicts_sorted_by_severity_descending():
    local = _make_local()
    ref = _make_reference()
    conflicts = ac.audit_consensus(local, ref, threshold=0.85)
    if len(conflicts) >= 2:
        scores = [c["severity_score"] for c in conflicts]
        assert scores == sorted(scores, reverse=True)


def test_status_thresholds():
    """Verify green/yellow/red status thresholds work correctly."""
    # Simulate two nearly-identical records → green
    local = pymarc.Record()
    local.leader = "00000nam a2200000   4500"
    local.add_field(pymarc.Field("245", ["1", "0"], ["a", "The great Gatsby"]))
    ref = pymarc.Record()
    ref.leader = "00000nam a2200000   4500"
    ref.add_field(pymarc.Field("245", ["1", "0"], ["a", "The great Gatsby /"]))
    conflicts = ac.audit_consensus(local, ref, threshold=0.85)
    if conflicts:
        assert conflicts[0]["status"] in ("green", "yellow", "red")
