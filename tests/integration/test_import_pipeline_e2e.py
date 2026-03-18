"""Integration tests for import_pipeline: end-to-end MARC processing."""

import json
from pathlib import Path

import pymarc
import pytest

import import_pipeline


@pytest.fixture
def mrc_with_issues(tmp_path):
    """Create a MARC file with validation issues (missing 245)."""
    path = tmp_path / "issues.mrc"
    r = pymarc.Record()
    r.leader = "00000nam a2200000   4500"
    r.add_field(pymarc.Field("001", data="ocn999999999"))
    # Missing 245 — will trigger validation error
    r.add_field(pymarc.Field("300", [" ", " "], ["a", "100 pages"]))

    with open(path, "wb") as f:
        writer = pymarc.MARCWriter(f)
        writer.write(r)
        writer.close()
    return path


def test_import_pipeline_mrc_to_output(tmp_mrc_file, tmp_path, mock_load_profile_factory, argv_manager):
    """Test full pipeline: read .mrc → clean → validate → write output."""
    # Setup mocks using shared factories
    mock_load_profile_factory(import_pipeline)
    argv_manager("import_pipeline.py", str(tmp_mrc_file))

    # Run with ISO-2709 input
    import_pipeline.main()

    # Check that output files were created
    import_ready = tmp_mrc_file.parent / f"{tmp_mrc_file.stem}_import_ready.mrc"
    report = tmp_mrc_file.parent / f"{tmp_mrc_file.stem}_import_report.json"

    assert import_ready.exists(), "Output .mrc file not created"
    assert report.exists(), "Report JSON not created"

    # Verify output MARC is readable
    with open(import_ready, "rb") as f:
        reader = pymarc.MARCReader(f, to_unicode=True)
        records = list(reader)
        assert len(records) >= 1, "Output MARC file is empty"

    # Verify report has expected structure
    with open(report) as f:
        data = json.load(f)
        assert isinstance(data, list)
        assert all("record_id" in item for item in data)
        assert all("status" in item for item in data)


def test_import_pipeline_validation_report(mrc_with_issues, tmp_path, mock_load_profile_factory, argv_manager):
    """Test that validation errors are reported and problematic records excluded."""
    # Setup mocks using shared factories
    mock_load_profile_factory(import_pipeline)
    argv_manager("import_pipeline.py", str(mrc_with_issues))

    import_pipeline.main()

    report_path = mrc_with_issues.parent / f"{mrc_with_issues.stem}_import_report.json"
    with open(report_path) as f:
        report = json.load(f)

    # Should have at least one error (missing 245)
    errors = [item for item in report if item["status"] == "error"]
    assert len(errors) > 0, "Expected validation errors in report"

    # Check that error record is documented
    assert any("245" in str(issue) for error in errors for issue in error.get("issues", []))


def test_import_pipeline_output_format(tmp_mrc_file, mock_load_profile_factory, argv_manager):
    """Test that output MARC has correct encoding and structure."""
    # Use factory with custom profile that deletes 035 field
    mock_load_profile_factory(import_pipeline, {
        "delete_tags": ["035"], "delete_ranges": [[]], "org_code": "TEST",
    })
    argv_manager("import_pipeline.py", str(tmp_mrc_file))

    import_pipeline.main()

    import_ready = tmp_mrc_file.parent / f"{tmp_mrc_file.stem}_import_ready.mrc"

    with open(import_ready, "rb") as f:
        reader = pymarc.MARCReader(f, to_unicode=True)
        for rec in reader:
            # Verify leader
            assert len(rec.leader) == 24
            # Verify org code was stamped
            if rec["003"]:
                assert rec["003"].data == "TEST"
            # Verify tag was deleted
            assert not rec.get_fields("035"), "035 should be deleted per profile"
