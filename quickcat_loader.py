"""QuickCat bootstrap — resolves cross-package imports in the hyphenated directory layout.

The repository uses hyphenated directory names (shared-resources, copy-cataloger, …)
which Python's import system cannot traverse as dotted package paths.  This module
registers every inter-dependent script into sys.modules under both its short name
and its full dotted path, so statements like

    from shared_resources.scripts.transaction_log import log_edit
    from skills.copy_cataloger.scripts.harvest_metadata import harvest_metadata

work correctly without renaming any directories.

USAGE — add ONE line to each script that uses cross-package imports, immediately
after the sys.path.insert line:

    ROOT = Path(__file__).parent...
    sys.path.insert(0, str(ROOT))
    import quickcat_loader          # noqa: F401  ← add this
    from shared_resources.scripts.transaction_log import log_edit

Re-entry is safe: every _reg() call is guarded by ``if name in sys.modules: return``
so importing quickcat_loader twice has no effect.
"""

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).parent


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _reg(name: str, path: Path) -> None:
    """Load a script by file path; register it in sys.modules under *name*."""
    if name in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)


def _alias(dotted: str, short: str) -> None:
    """Make sys.modules[short] also reachable as sys.modules[dotted].

    Creates lightweight parent-package stubs so ``from dotted import X`` works.
    """
    mod = sys.modules[short]
    parts = dotted.split(".")
    for i in range(1, len(parts)):
        pkg = ".".join(parts[:i])
        if pkg not in sys.modules:
            sys.modules[pkg] = types.ModuleType(pkg)
    if len(parts) > 1:
        setattr(sys.modules[".".join(parts[:-1])], parts[-1], mod)
    sys.modules[dotted] = mod


# ── Step 1: standalone shared-resource scripts (no cross-dependencies) ────────
_reg("normalize_dates", ROOT / "shared-resources/scripts/normalize_dates.py")
_reg("transaction_log", ROOT / "shared-resources/scripts/transaction_log.py")
_reg("parse_marc",      ROOT / "shared-resources/scripts/parse_marc.py")

_alias("shared_resources.scripts.normalize_dates", "normalize_dates")
_alias("shared_resources.scripts.transaction_log", "transaction_log")
_alias("shared_resources.scripts.parse_marc",      "parse_marc")

# ── Step 2: copy-cataloger base scripts (no cross-deps among themselves) ──────
_reg("validation_gate",  ROOT / "skills/copy-cataloger/scripts/validation_gate.py")
_reg("audit_consensus",  ROOT / "skills/copy-cataloger/scripts/audit_consensus.py")
_reg("harvest_metadata", ROOT / "skills/copy-cataloger/scripts/harvest_metadata.py")

_alias("skills.copy_cataloger.scripts.validation_gate",  "validation_gate")
_alias("skills.copy_cataloger.scripts.audit_consensus",  "audit_consensus")
_alias("skills.copy_cataloger.scripts.harvest_metadata", "harvest_metadata")

# ── Step 3: resolve_tie_breaker (depends on harvest_metadata + audit_consensus)
_reg("resolve_tie_breaker", ROOT / "skills/copy-cataloger/scripts/resolve_tie_breaker.py")
_alias("skills.copy_cataloger.scripts.resolve_tie_breaker", "resolve_tie_breaker")

# ── Step 4: batch_clean (depends on transaction_log, already registered above) ─
_reg("batch_clean", ROOT / "skills/batch-cleaner/scripts/batch_clean.py")
_alias("skills.batch_cleaner.scripts.batch_clean", "batch_clean")

# ── Step 5: excel_to_marc (standalone — no cross-package imports) ──────────────
_reg("excel_to_marc", ROOT / "skills/marc-importer/scripts/excel_to_marc.py")
_alias("skills.marc_importer.scripts.excel_to_marc", "excel_to_marc")
