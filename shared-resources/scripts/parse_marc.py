"""Parse MARC records (binary .mrc or MARCXML) to standardized JSON dicts.

Usage:
    python3 shared-resources/scripts/parse_marc.py records.mrc
    python3 shared-resources/scripts/parse_marc.py records.xml --format marcxml

Outputs one JSON object per line (newline-delimited JSON).
"""

import argparse
import json
import sys
import unicodedata
from pathlib import Path

import pymarc


def _clean(value: str | None) -> str | None:
    """Apply NFC normalization and strip whitespace."""
    if value is None:
        return None
    return unicodedata.normalize("NFC", value).strip()


def record_to_dict(record: pymarc.Record) -> dict:
    """Convert a pymarc Record to a standardized dict.

    Returns:
        dict with keys: title, author_main, author_added, isbn, issn,
        publisher, publication_date, edition, physical_desc, series,
        subjects_topical, subjects_geographic, subjects_genre,
        lc_classification, dewey, language, summary, toc,
        local_call_number, record_id, source_tags.
    """
    def first(tag: str, subfield: str = "a") -> str | None:
        f = record[tag]
        return _clean(f[subfield]) if f else None

    def all_values(tag: str, subfield: str = "a") -> list[str]:
        return [_clean(f[subfield]) for f in record.get_fields(tag) if f[subfield]]

    # Control fields
    record_id = _clean(record["001"].data) if record["001"] else None

    # Title (245)
    title_field = record["245"]
    title = None
    if title_field:
        parts = [title_field["a"] or "", title_field["b"] or ""]
        title = _clean(" ".join(p for p in parts if p).rstrip(" /").strip())

    # Main author (100 personal, 110 corporate, 111 meeting)
    author_main = None
    for tag in ("100", "110", "111"):
        f = record[tag]
        if f:
            author_main = _clean(f.value())
            break

    # Added authors / editors (700, 710, 711)
    added_authors = []
    for tag in ("700", "710", "711"):
        for f in record.get_fields(tag):
            val = _clean(f.value())
            if val:
                added_authors.append(val)

    # ISBN / ISSN
    isbn = [_clean(f["a"]) for f in record.get_fields("020") if f["a"]]
    issn = [_clean(f["a"]) for f in record.get_fields("022") if f["a"]]

    # Publication (prefer 264, fallback to 260)
    pub_field = record["264"] or record["260"]
    publisher = _clean(pub_field["b"]) if pub_field else None
    publication_date = _clean(pub_field["c"]) if pub_field else None

    # Edition (250)
    edition = first("250")

    # Physical description (300)
    phys = first("300")

    # Series (490, 830)
    series = all_values("490") or all_values("830")

    # Subjects
    subjects_topical = all_values("650")
    subjects_geographic = all_values("651")
    subjects_genre = all_values("655")

    # Classification
    lc_class = first("050")
    dewey = first("082")

    # Language (008 positions 35-37, fallback to 041)
    language = None
    if record["008"] and len(record["008"].data) >= 38:
        language = record["008"].data[35:38].strip() or None
    if not language:
        lang_field = record["041"]
        language = _clean(lang_field["a"]) if lang_field else None

    # Notes
    summary = first("520")
    toc = first("505")

    # Local call number
    local_call = first("090") or first("099")

    # Collect which AI-tagged fields are present ($9 AI_QUICKCAT)
    ai_tagged = []
    for field in record.fields:
        if hasattr(field, "subfields"):
            subs = field.subfields
            for i in range(0, len(subs) - 1, 2):
                if subs[i] == "9" and "AI_QUICKCAT" in (subs[i + 1] or ""):
                    ai_tagged.append(field.tag)
                    break

    return {
        "record_id": record_id,
        "title": title,
        "author_main": author_main,
        "author_added": added_authors,
        "isbn": isbn,
        "issn": issn,
        "publisher": publisher,
        "publication_date": publication_date,
        "edition": edition,
        "physical_desc": phys,
        "series": series,
        "subjects_topical": subjects_topical,
        "subjects_geographic": subjects_geographic,
        "subjects_genre": subjects_genre,
        "lc_classification": lc_class,
        "dewey": dewey,
        "language": language,
        "summary": summary,
        "toc": toc,
        "local_call_number": local_call,
        "ai_tagged_fields": ai_tagged,
    }


def parse_binary(path: str) -> list[dict]:
    records = []
    with open(path, "rb") as f:
        reader = pymarc.MARCReader(f, to_unicode=True, force_utf8=True)
        for record in reader:
            if record:
                records.append(record_to_dict(record))
    return records


def parse_marcxml(path: str) -> list[dict]:
    records = []
    for record in pymarc.parse_xml_to_array(path):
        if record:
            records.append(record_to_dict(record))
    return records


def main():
    parser = argparse.ArgumentParser(description="Parse MARC records to JSON")
    parser.add_argument("file", help="Path to .mrc binary or .xml MARCXML file")
    parser.add_argument("--format", choices=["binary", "marcxml"], default=None)
    args = parser.parse_args()

    fmt = args.format
    if fmt is None:
        suffix = Path(args.file).suffix.lower()
        fmt = "marcxml" if suffix in (".xml", ".marcxml") else "binary"

    records = parse_marcxml(args.file) if fmt == "marcxml" else parse_binary(args.file)
    for rec in records:
        print(json.dumps(rec, ensure_ascii=False))


if __name__ == "__main__":
    main()
