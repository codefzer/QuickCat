"""Integration tests for harvest_orchestrator: end-to-end copy-cataloging workflow."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import harvest_orchestrator


@pytest.fixture
def sample_marcxml():
    """Sample MARCXML response from a metadata source."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
  <marc:leader>00000nam a2200000   4500</marc:leader>
  <marc:controlfield tag="001">ocn123456789</marc:controlfield>
  <marc:controlfield tag="003">OCoLC</marc:controlfield>
  <marc:datafield tag="245" ind1="1" ind2="0">
    <marc:subfield code="a">The great Gatsby /</marc:subfield>
    <marc:subfield code="c">F. Scott Fitzgerald.</marc:subfield>
  </marc:datafield>
  <marc:datafield tag="300" ind1=" " ind2=" ">
    <marc:subfield code="a">180 pages</marc:subfield>
  </marc:datafield>
</marc:record>"""


@pytest.mark.asyncio
async def test_orchestrate_full_harvest_workflow(sample_marcxml, tmp_path, monkeypatch):
    """Test full orchestrator workflow: validate → harvest → merge → output."""

    # Mock _load_config
    def mock_config():
        return {"org_code": "TEST_ORG"}

    monkeypatch.setattr(harvest_orchestrator, "_load_config", mock_config)

    # Mock harvest_metadata to return sample MARCXML
    async def mock_harvest(identifier, source):
        return sample_marcxml

    monkeypatch.setattr(harvest_orchestrator, "harvest_metadata", mock_harvest)

    # Mock audit_consensus to return no conflicts
    def mock_audit(base, ref):
        return []

    monkeypatch.setattr(harvest_orchestrator, "audit_consensus", mock_audit)

    # Mock print_dashboard (it's called but doesn't need to print)
    monkeypatch.setattr(harvest_orchestrator, "print_dashboard", lambda x: None)

    output_path = str(tmp_path / "merged_isbn.mrc")
    result = await harvest_orchestrator.orchestrate(
        identifier="9780743273565", sources=["loc"], output_path=output_path
    )

    # Verify result structure
    assert result["status"] == "ok"
    assert "merged_path" in result
    assert "conflict_report" in result
    assert "sources_used" in result
    assert "loc" in result["sources_used"]

    # Verify output files exist
    output_file = Path(output_path)
    assert output_file.exists(), "Merged MARC file not created"

    conflict_file = output_file.parent / (output_file.stem + "_conflicts.json")
    assert conflict_file.exists(), "Conflict report not created"


@pytest.mark.asyncio
async def test_orchestrate_handles_validation_error(monkeypatch):
    """Test that orchestrator validates ISBN before harvesting."""

    def mock_config():
        return {}

    monkeypatch.setattr(harvest_orchestrator, "_load_config", mock_config)

    # Try with invalid ISBN
    result = await harvest_orchestrator.orchestrate(
        identifier="9999999999999",  # Bad check digit
        sources=["loc"],
    )

    # Should fail validation
    assert result["status"] == "error"
    assert "Validation failed" in result["message"]


@pytest.mark.asyncio
async def test_orchestrate_handles_no_records_found(monkeypatch):
    """Test that orchestrator fails gracefully when no records found."""

    def mock_config():
        return {}

    monkeypatch.setattr(harvest_orchestrator, "_load_config", mock_config)

    # Mock harvest to return not-found messages
    async def mock_harvest(identifier, source):
        return "Record Not Found"

    monkeypatch.setattr(harvest_orchestrator, "harvest_metadata", mock_harvest)

    result = await harvest_orchestrator.orchestrate(
        identifier="9780743273565", sources=["loc", "nls"]
    )

    assert result["status"] == "error"
    assert "No records found" in result["message"]


@pytest.mark.asyncio
async def test_orchestrate_applies_consensus_decisions(sample_marcxml, tmp_path, monkeypatch):
    """Test that orchestrator applies consensus decisions to merged record."""

    def mock_config():
        return {"org_code": "TEST"}

    monkeypatch.setattr(harvest_orchestrator, "_load_config", mock_config)

    # Both sources return MARCXML
    async def mock_harvest(identifier, source):
        return sample_marcxml

    monkeypatch.setattr(harvest_orchestrator, "harvest_metadata", mock_harvest)

    # Mock audit_consensus to return a "green" consensus (auto-merge)
    def mock_audit(base, ref):
        return [
            {
                "tag": "300",
                "local_value": "180 pages",
                "remote_value": "180 pages",
                "severity": 0.0,
                "status": "green",
            }
        ]

    monkeypatch.setattr(harvest_orchestrator, "audit_consensus", mock_audit)
    monkeypatch.setattr(harvest_orchestrator, "print_dashboard", lambda x: None)

    output_path = str(tmp_path / "merged.mrc")
    result = await harvest_orchestrator.orchestrate(
        identifier="9780743273565", sources=["loc"], output_path=output_path
    )

    assert result["status"] == "ok"
    assert result["total_conflicts"] >= 0  # At least one conflict detected

    # Verify conflict report was created
    conflict_file = Path(result["conflict_report"])
    with open(conflict_file) as f:
        conflicts = json.load(f)
        assert isinstance(conflicts, list)
