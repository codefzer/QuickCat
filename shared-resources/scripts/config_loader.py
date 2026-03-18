"""Shared configuration loaders for QuickCat scripts.

Centralises the three JSON config files so every skill script imports from
one place instead of duplicating the same 3-line load function.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent   # QuickCat/


def load_config() -> dict:
    """Load config.json from the repository root."""
    with open(ROOT / "config.json") as f:
        return json.load(f)


def load_servers() -> dict:
    """Load servers.json from the repository root."""
    with open(ROOT / "servers.json") as f:
        return json.load(f)


def load_validation_rules() -> dict:
    """Load shared-resources/references/validation-rules.json."""
    with open(ROOT / "shared-resources" / "references" / "validation-rules.json") as f:
        return json.load(f)
