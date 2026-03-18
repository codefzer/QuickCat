"""Shared MARC file I/O helpers for QuickCat scripts.

Provides consistent read/write wrappers around pymarc so every skill uses
the same flags (to_unicode=True, force_utf8=True) and writer lifecycle.
"""

from pathlib import Path

import pymarc


def read_mrc(path: str | Path) -> list[pymarc.Record]:
    """Read all records from a binary ISO-2709 MARC file.

    Uses to_unicode=True and force_utf8=True for consistent Unicode handling.
    Silently skips any None records (pymarc returns None for corrupt entries).

    Args:
        path: Path to the .mrc file.

    Returns:
        List of pymarc.Record objects (may be empty).
    """
    records: list[pymarc.Record] = []
    with open(path, "rb") as f:
        reader = pymarc.MARCReader(f, to_unicode=True, force_utf8=True)
        for rec in reader:
            if rec is not None:
                records.append(rec)
    return records


def write_mrc(records: list[pymarc.Record], path: str | Path) -> None:
    """Write records to a binary ISO-2709 MARC file.

    Args:
        records: List of pymarc.Record objects to write.
        path: Destination file path (created or overwritten).
    """
    with open(path, "wb") as f:
        writer = pymarc.MARCWriter(f)
        for rec in records:
            writer.write(rec)
        writer.close()
