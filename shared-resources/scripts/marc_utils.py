"""Shared MARC utility functions for QuickCat scripts.

Small, pure helpers used by multiple skills that were previously duplicated
as private functions in each script file.
"""

import difflib
import unicodedata


def nfc(s: str | None) -> str | None:
    """Apply NFC Unicode normalisation and strip whitespace.

    None-safe: returns None unchanged.

    Args:
        s: String to normalise, or None.

    Returns:
        NFC-normalised, stripped string, or None if input was None.
    """
    if s is None:
        return None
    return unicodedata.normalize("NFC", s).strip()


def similarity(a: str | None, b: str | None) -> float:
    """Compute string similarity as a SequenceMatcher ratio.

    Both inputs are lowercased before comparison so the score is
    case-insensitive.  Either input being None or empty returns 0.0.

    Args:
        a: First string (or None).
        b: Second string (or None).

    Returns:
        Float in [0.0, 1.0] where 1.0 means identical.
    """
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
