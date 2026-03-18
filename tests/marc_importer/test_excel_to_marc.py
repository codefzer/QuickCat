"""Tests for skills/marc-importer/scripts/excel_to_marc.py"""

import csv
from pathlib import Path

import pymarc
import pytest

import excel_to_marc as em


# ─── _invert_name ─────────────────────────────────────────────────────────────

def test_invert_name_already_inverted():
    assert em._invert_name("Fitzgerald, F. Scott") == "Fitzgerald, F. Scott"


def test_invert_name_forward_order():
    result = em._invert_name("F. Scott Fitzgerald")
    assert result == "Fitzgerald, F. Scott"


def test_invert_name_single_word():
    assert em._invert_name("Madonna") == "Madonna"


# ─── _normalize_col_name ──────────────────────────────────────────────────────

def _aliases():
    return {
        "245": ["Title", "Book Title", "TITLE", "title", "name"],
        "100": ["Author", "AUTHOR", "Creator"],
        "020": ["ISBN", "isbn"],
    }


def test_normalize_col_name_exact_match():
    assert em._normalize_col_name("Title", _aliases()) == "245"


def test_normalize_col_name_case_insensitive():
    assert em._normalize_col_name("TITLE", _aliases()) == "245"


def test_normalize_col_name_unknown_returns_none():
    assert em._normalize_col_name("XYZABC123", _aliases()) is None


# ─── row_to_record ────────────────────────────────────────────────────────────

def _minimal_templates():
    return {
        "book": {
            "leader": {"6": "a", "7": "m"}
        }
    }


def _minimal_aliases():
    return {
        "245": ["Title", "title"],
        "100": ["Author", "author"],
        "020": ["ISBN", "isbn"],
    }


def _minimal_crosswalk():
    return {}


def test_row_to_record_with_title():
    row = {"Title": "The Great Gatsby", "Author": "Fitzgerald, F. Scott"}
    record, warnings = em.row_to_record(
        row, "book", _minimal_templates(), _minimal_aliases(), _minimal_crosswalk()
    )
    assert record["245"] is not None
    assert "Gatsby" in record["245"]["a"]


def test_row_to_record_isbn_stripped_of_hyphens():
    row = {"Title": "A Book", "ISBN": "978-0-7432-7356-5"}
    record, _ = em.row_to_record(
        row, "book", _minimal_templates(), _minimal_aliases(), _minimal_crosswalk()
    )
    isbn_field = record["020"]
    if isbn_field:
        assert "-" not in isbn_field["a"]


# ─── excel_to_records (CSV) ───────────────────────────────────────────────────

def test_excel_to_records_csv(tmp_path):
    csv_path = tmp_path / "books.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Title", "Author", "ISBN"])
        writer.writeheader()
        writer.writerow({
            "Title": "The Hobbit",
            "Author": "Tolkien, J. R. R.",
            "ISBN": "9780261102217",
        })
        writer.writerow({
            "Title": "1984",
            "Author": "Orwell, George",
            "ISBN": "9780451524935",
        })

    records, report = em.excel_to_records(str(csv_path), material_type="book")
    assert len(records) == 2
    titles = [r["245"]["a"] for r in records if r["245"]]
    assert any("Hobbit" in t for t in titles)
    assert any("1984" in t for t in titles)
