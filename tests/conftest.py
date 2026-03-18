"""
Shared pytest fixtures and import shim for QuickCat.

WHY THE SHIM IS NEEDED:
  All skill directories use hyphens (shared-resources, copy-cataloger, batch-cleaner)
  but Python import statements use underscores. There are no __init__.py files in the
  skills tree. We load each script by file path via importlib and register it into
  sys.modules so test files can use normal 'import' statements.

  Some scripts also use dotted package-path imports like:
    from shared_resources.scripts.transaction_log import log_edit
    from skills.copy_cataloger.scripts.harvest_metadata import harvest_metadata
  We create lightweight package stubs in sys.modules so those resolve too.
"""

import importlib.util
import sys
import types
from io import BytesIO
from pathlib import Path

import pymarc
import pytest

ROOT = Path(__file__).parent.parent


# ─── Module shim ──────────────────────────────────────────────────────────────

def _reg(name: str, path: Path) -> None:
    """Load a script by file path and register it in sys.modules under `name`."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)


def _alias(dotted: str, short: str) -> None:
    """Register sys.modules[short] under the full dotted package path.

    Creates any missing intermediate package stubs so Python's import machinery
    can resolve `from dotted import X` statements inside scripts.
    """
    mod = sys.modules[short]
    parts = dotted.split(".")
    # Ensure every ancestor package exists in sys.modules
    for i in range(1, len(parts)):
        pkg_name = ".".join(parts[:i])
        if pkg_name not in sys.modules:
            pkg = types.ModuleType(pkg_name)
            sys.modules[pkg_name] = pkg
    # Wire the leaf onto its parent package and into sys.modules
    if len(parts) > 1:
        parent = sys.modules[".".join(parts[:-1])]
        setattr(parent, parts[-1], mod)
    sys.modules[dotted] = mod


# ── Step 1: load shared-resources (no cross-dependencies) ─────────────────────
_reg("normalize_dates", ROOT / "shared-resources/scripts/normalize_dates.py")
_reg("transaction_log", ROOT / "shared-resources/scripts/transaction_log.py")
_reg("parse_marc",      ROOT / "shared-resources/scripts/parse_marc.py")

# ── Step 2: register dotted aliases that scripts import by package path ────────
_alias("shared_resources.scripts.normalize_dates", "normalize_dates")
_alias("shared_resources.scripts.transaction_log", "transaction_log")
_alias("shared_resources.scripts.parse_marc",      "parse_marc")

# ── Step 3: load copy-cataloger scripts (harvest_metadata, audit_consensus first)
_reg("validation_gate",  ROOT / "skills/copy-cataloger/scripts/validation_gate.py")
_reg("audit_consensus",  ROOT / "skills/copy-cataloger/scripts/audit_consensus.py")
_reg("harvest_metadata", ROOT / "skills/copy-cataloger/scripts/harvest_metadata.py")

# Register copy-cataloger dotted aliases before loading modules that import them
_alias("skills.copy_cataloger.scripts.validation_gate", "validation_gate")
_alias("skills.copy_cataloger.scripts.harvest_metadata", "harvest_metadata")
_alias("skills.copy_cataloger.scripts.audit_consensus",  "audit_consensus")

_reg("resolve_tie_breaker",  ROOT / "skills/copy-cataloger/scripts/resolve_tie_breaker.py")

# Register resolve_tie_breaker alias before orchestrator loads it
_alias("skills.copy_cataloger.scripts.resolve_tie_breaker", "resolve_tie_breaker")

_reg("harvest_orchestrator", ROOT / "skills/copy-cataloger/scripts/harvest_orchestrator.py")

# ── Step 4: load remaining skills ─────────────────────────────────────────────
_reg("batch_clean",     ROOT / "skills/batch-cleaner/scripts/batch_clean.py")
_alias("skills.batch_cleaner.scripts.batch_clean", "batch_clean")
_reg("authority_lookup",ROOT / "skills/authority-grounder/scripts/authority_lookup.py")
_reg("enhance_record",  ROOT / "skills/brief-to-full-enhancer/scripts/enhance_record.py")
_reg("image_to_marc",   ROOT / "skills/vision-to-marc/scripts/image_to_marc.py")
_reg("excel_to_marc",   ROOT / "skills/marc-importer/scripts/excel_to_marc.py")
_alias("skills.marc_importer.scripts.excel_to_marc", "excel_to_marc")
_reg("import_pipeline", ROOT / "skills/marc-importer/scripts/import_pipeline.py")
_reg("export_marc",     ROOT / "skills/marc-exporter/scripts/export.py")
_reg("rollback",        ROOT / "skills/record-rollback/scripts/rollback.py")


# ─── Shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_record() -> pymarc.Record:
    """A minimal but realistic MARC 21 record for testing."""
    r = pymarc.Record()
    r.leader = "00000nam a2200000   4500"
    r.add_field(pymarc.Field("001", data="ocn123456789"))
    r.add_field(pymarc.Field("003", data="OCoLC"))
    r.add_field(pymarc.Field("035", [" ", " "], ["a", "(OCoLC)123456789"]))
    r.add_field(pymarc.Field("040", [" ", " "], ["a", "DLC", "b", "eng", "e", "rda", "c", "DLC"]))
    r.add_field(pymarc.Field("100", ["1", " "], ["a", "Fitzgerald, F. Scott,", "d", "1896-1940."]))
    r.add_field(pymarc.Field("245", ["1", "0"], ["a", "The great Gatsby /", "c", "F. Scott Fitzgerald."]))
    r.add_field(pymarc.Field("264", [" ", "1"], ["a", "New York :", "b", "Scribner,", "c", "1925."]))
    r.add_field(pymarc.Field("300", [" ", " "], ["a", "180 pages"]))
    r.add_field(pymarc.Field("650", [" ", "0"], ["a", "American fiction."]))
    r.add_field(pymarc.Field("090", [" ", " "], ["a", "PS3511.I9", "b", "G7"]))
    return r


@pytest.fixture
def ai_tagged_record(sample_record: pymarc.Record) -> pymarc.Record:
    """A record with an AI-generated 520 field stamped $9 AI_QUICKCAT."""
    sample_record.add_field(pymarc.Field(
        "520", [" ", " "],
        ["a", "A wealthy man throws lavish parties.", "9", "AI_QUICKCAT"],
    ))
    return sample_record


@pytest.fixture
def tmp_mrc_file(tmp_path: Path, sample_record: pymarc.Record) -> Path:
    """Write sample_record to a temporary .mrc file and return the path."""
    path = tmp_path / "sample.mrc"
    with open(path, "wb") as f:
        writer = pymarc.MARCWriter(f)
        writer.write(sample_record)
        writer.close()
    return path


@pytest.fixture
def validation_rules() -> dict:
    """Minimal validation rules dict (mirrors validation-rules.json structure)."""
    return {
        "required_fields": {
            "core_level": {"fields": ["001", "245", "008"]},
        },
        "encoding": {
            "leader_09": "Must be 'a' for Unicode records",
        },
    }
