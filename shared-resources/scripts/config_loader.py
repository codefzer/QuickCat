"""Shared configuration loaders for QuickCat scripts.

Centralises the three JSON config files so every skill script imports from
one place instead of duplicating the same 3-line load function.
"""

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent   # QuickCat/


@lru_cache(maxsize=None)
def load_config() -> dict:
    """Load config.json from the repository root.

    Result is cached for the lifetime of the process — the file is read
    once no matter how many scripts call this function.
    """
    with open(ROOT / "config.json") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_servers() -> dict:
    """Load servers.json from the repository root.

    Result is cached for the lifetime of the process.
    """
    with open(ROOT / "servers.json") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_validation_rules() -> dict:
    """Load shared-resources/references/validation-rules.json.

    Result is cached for the lifetime of the process.
    """
    with open(ROOT / "shared-resources" / "references" / "validation-rules.json") as f:
        return json.load(f)
