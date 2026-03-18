"""Normalize date strings to 4-digit year or YYYYMMDD for MARC 008 positions 07-10.

Usage:
    from shared_resources.scripts.normalize_dates import normalize_year, marc_008_date
"""

import re


_YEAR_PATTERNS = [
    r"\b(1[0-9]{3}|20[0-9]{2})\b",  # plain 4-digit year
    r"c\.?\s*(1[0-9]{3}|20[0-9]{2})",  # circa dates
    r"\[(1[0-9]{3}|20[0-9]{2})\]",    # bracketed
    r"©\s*(1[0-9]{3}|20[0-9]{2})",    # copyright date
]


def normalize_year(raw: str) -> str | None:
    """Extract the first 4-digit year from a date string.

    Args:
        raw: Any date string, e.g. '©2021', 'c.1985', '[2003]', 'May 15, 2010'

    Returns:
        4-digit year string or None if not found.
    """
    if not raw:
        return None
    for pattern in _YEAR_PATTERNS:
        m = re.search(pattern, raw)
        if m:
            return m.group(1)
    return None


def marc_008_date(year: str | None) -> str:
    """Format a year string for 008 positions 07-10 (or 11-14).

    Returns 4 characters: the year or '    ' (four spaces) if unknown.
    """
    if year and re.match(r"^\d{4}$", year):
        return year
    return "    "


def format_pagination(raw: str | None) -> str | None:
    """Convert a bare page count to ISBD-formatted pagination.

    '250' -> '250 pages'
    '250 p.' -> '250 pages'
    'xii, 250' -> 'xii, 250 pages'
    """
    if not raw:
        return None
    raw = raw.strip().rstrip(".")
    # Already looks formatted
    if "page" in raw.lower() or "vol" in raw.lower():
        return raw
    # Bare number
    if re.match(r"^\d+$", raw):
        return f"{raw} pages"
    # Prefix + number: 'xii, 250'
    m = re.match(r"^([xivXIV]+,\s*\d+)$", raw)
    if m:
        return f"{m.group(1)} pages"
    return raw
