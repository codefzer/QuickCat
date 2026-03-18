"""QuickCat bootstrap — resolves cross-package imports in the hyphenated directory layout.

The repository uses hyphenated directory names (shared-resources, copy-cataloger, …)
which Python's import system cannot traverse as dotted package paths.  This module
registers inter-dependent scripts into sys.modules under both a short name and their
full dotted path, so statements like

    from shared_resources.scripts.transaction_log import log_edit

work correctly without renaming any directories.

EAGER LAYER (runs on ``import quickcat_loader``):
  Only shared-resources scripts (transaction_log, normalize_dates, parse_marc).
  These are stdlib-weight and needed by almost every QuickCat script.

ON-DEMAND HELPERS (call before the imports that need them):

    import quickcat_loader
    quickcat_loader.register_copy_cataloger()  # resolve_tie_breaker, harvest_orchestrator
    quickcat_loader.register_tie_breaker()     # harvest_orchestrator
    quickcat_loader.register_batch_cleaner()   # import_pipeline
    quickcat_loader.register_marc_importer()   # import_pipeline (pulls pandas)

Re-entry is safe: every _reg() call is guarded by ``if name in sys.modules: return``
and by a __main__ guard that aliases rather than re-executes the calling script.
"""

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).parent


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _reg(name: str, path: Path) -> None:
    """Load a script by file path; register it in sys.modules under *name*.

    Guards:
    - Skips if *name* is already registered (idempotent).
    - If the target file is the currently-running __main__ script, aliases
      sys.modules[name] to the existing __main__ module instead of executing
      the file a second time (prevents double-import side effects).
    """
    if name in sys.modules:
        return
    # __main__ guard: don't re-execute a script that is already running
    main = sys.modules.get("__main__")
    if main and getattr(main, "__file__", None):
        try:
            if Path(main.__file__).resolve() == Path(path).resolve():
                sys.modules[name] = main
                return
        except (OSError, ValueError):
            pass
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


# ── Eager layer: shared-resources only (stdlib-weight, no third-party libs) ───
_reg("normalize_dates", ROOT / "shared-resources/scripts/normalize_dates.py")
_reg("transaction_log", ROOT / "shared-resources/scripts/transaction_log.py")
_reg("parse_marc",      ROOT / "shared-resources/scripts/parse_marc.py")

_alias("shared_resources.scripts.normalize_dates", "normalize_dates")
_alias("shared_resources.scripts.transaction_log", "transaction_log")
_alias("shared_resources.scripts.parse_marc",      "parse_marc")


# ── On-demand helpers — call these before the cross-skill imports that need them ─

def register_copy_cataloger() -> None:
    """Register validation_gate, audit_consensus, harvest_metadata.

    Kept out of the eager layer because harvest_metadata imports httpx and
    tenacity at module level; scripts unrelated to copy-cataloging (rollback,
    batch_clean, authority_lookup, etc.) should not require those packages.
    """
    _reg("validation_gate",  ROOT / "skills/copy-cataloger/scripts/validation_gate.py")
    _reg("audit_consensus",  ROOT / "skills/copy-cataloger/scripts/audit_consensus.py")
    _reg("harvest_metadata", ROOT / "skills/copy-cataloger/scripts/harvest_metadata.py")
    _alias("skills.copy_cataloger.scripts.validation_gate",  "validation_gate")
    _alias("skills.copy_cataloger.scripts.audit_consensus",  "audit_consensus")
    _alias("skills.copy_cataloger.scripts.harvest_metadata", "harvest_metadata")


def register_tie_breaker() -> None:
    """Register resolve_tie_breaker (depends on copy-cataloger base).

    Automatically calls register_copy_cataloger() first to satisfy
    resolve_tie_breaker's imports of harvest_metadata and audit_consensus.
    """
    register_copy_cataloger()
    _reg("resolve_tie_breaker", ROOT / "skills/copy-cataloger/scripts/resolve_tie_breaker.py")
    _alias("skills.copy_cataloger.scripts.resolve_tie_breaker", "resolve_tie_breaker")


def register_batch_cleaner() -> None:
    """Register batch_clean for scripts that import it (e.g. import_pipeline).

    Kept out of the eager layer because batch_clean.py itself imports quickcat_loader;
    eager registration would double-execute it when it runs as __main__.
    """
    _reg("batch_clean", ROOT / "skills/batch-cleaner/scripts/batch_clean.py")
    _alias("skills.batch_cleaner.scripts.batch_clean", "batch_clean")


def register_marc_importer() -> None:
    """Register excel_to_marc for scripts that import it (e.g. import_pipeline).

    Kept out of the eager layer because excel_to_marc imports pandas at module
    level; eager registration would force a pandas dependency on every script
    that does ``import quickcat_loader``, even scripts unrelated to Excel import.
    """
    _reg("excel_to_marc", ROOT / "skills/marc-importer/scripts/excel_to_marc.py")
    _alias("skills.marc_importer.scripts.excel_to_marc", "excel_to_marc")
