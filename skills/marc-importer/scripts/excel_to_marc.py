"""Excel/CSV → pymarc Records using the crosswalk.json and config.json column aliases.

Usage:
    from skills.marc_importer.scripts.excel_to_marc import excel_to_records
    records = excel_to_records('acquisitions.xlsx', material_type='book')
"""

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
import pymarc

ROOT = Path(__file__).parent.parent.parent.parent


def _load_config() -> dict:
    with open(ROOT / "config.json") as f:
        return json.load(f)


def _load_crosswalk() -> dict:
    cfg = _load_config()
    # crosswalk lives in shared-resources/references/
    cw_path = ROOT / "shared-resources" / "references" / "crosswalk.json"
    with open(cw_path) as f:
        return json.load(f)


def _load_templates() -> dict:
    with open(ROOT / "shared-resources" / "templates" / "marc-templates.json") as f:
        return json.load(f)


def _nfc(s) -> str | None:
    if s is None or (isinstance(s, float) and str(s) == "nan"):
        return None
    s = str(s).strip()
    if not s:
        return None
    return unicodedata.normalize("NFC", s)


def _invert_name(name: str) -> str:
    """Convert 'Firstname Lastname' to 'Lastname, Firstname'."""
    name = name.strip()
    if "," in name:
        return name  # Already inverted
    parts = name.rsplit(" ", 1)
    if len(parts) == 2:
        return f"{parts[1]}, {parts[0]}"
    return name


def _normalize_year(raw: str) -> str | None:
    m = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", str(raw))
    return m.group(1) if m else None


def _normalize_col_name(col: str, aliases: dict) -> str | None:
    """Map a column header to a MARC key using aliases."""
    col_stripped = col.strip()
    for marc_key, alias_list in aliases.items():
        if col_stripped in alias_list or col_stripped.lower() in [a.lower() for a in alias_list]:
            return marc_key
    return None


def row_to_record(row: dict, material_type: str, templates: dict, aliases: dict, crosswalk: dict) -> tuple[pymarc.Record, list[str]]:
    """Convert one spreadsheet row to a pymarc Record.

    Returns (record, warnings).
    """
    warnings = []
    record = pymarc.Record()

    # Apply Leader from template
    template = templates.get(material_type, templates["book"])
    leader = list("00000nam a2200000   4500")
    for pos, val in template.get("leader", {}).items():
        try:
            leader[int(pos)] = val
        except (ValueError, IndexError):
            pass
    record.leader = "".join(leader)

    # Map row columns to MARC fields
    mapped = {}
    for col, raw_val in row.items():
        marc_key = _normalize_col_name(str(col), aliases)
        if marc_key is None:
            warnings.append(f"Unrecognized column: {col!r}")
            continue
        val = _nfc(raw_val)
        if val:
            mapped[marc_key] = val

    # 100 — Main Author
    if "100" in mapped:
        author = _invert_name(mapped["100"])
        if not author.endswith((",", ".", "-")):
            author += ","
        record.add_field(pymarc.Field("100", ["1", " "], ["a", author]))

    # 245 — Title
    title = mapped.get("245", "")
    subtitle = mapped.get("245b", "")
    if not title:
        warnings.append("No title found — 245 field will be missing")
    else:
        subs_245 = ["a", title]
        if subtitle:
            if not title.endswith(":"):
                subs_245[-1] += " :"
            subs_245 += ["b", subtitle]
        if not subs_245[-1].endswith((".", "!", "?")):
            subs_245[-1] += "."
        ind1 = "1" if "100" in mapped else "0"
        record.add_field(pymarc.Field("245", [ind1, "0"], subs_245))

    # 264 — Publication
    pub_subs = []
    if "264b" in mapped:
        pub_subs += ["b", mapped["264b"] + ","]
    if "264c" in mapped:
        year = _normalize_year(mapped["264c"])
        if year:
            pub_subs += ["c", year + "."]
    if pub_subs:
        record.add_field(pymarc.Field("264", [" ", "1"], pub_subs))

    # 300 — Physical description
    if "300a" in mapped:
        pages = mapped["300a"]
        if re.match(r"^\d+$", pages):
            pages = f"{pages} pages"
        record.add_field(pymarc.Field("300", [" ", " "], ["a", pages + "."]))

    # 020 — ISBN
    if "020" in mapped:
        isbn = re.sub(r"[^0-9X]", "", mapped["020"].upper())
        record.add_field(pymarc.Field("020", [" ", " "], ["a", isbn]))

    # 022 — ISSN
    if "022" in mapped:
        record.add_field(pymarc.Field("022", [" ", " "], ["a", mapped["022"]]))

    # 650 — Subjects (may be semicolon-separated)
    if "650" in mapped:
        subjects = [s.strip() for s in mapped["650"].split(";") if s.strip()]
        for subj in subjects:
            if not subj.endswith((".",")")):
                subj += "."
            record.add_field(pymarc.Field("650", [" ", "0"], ["a", subj]))

    # 041 — Language
    if "041" in mapped:
        lang = mapped["041"].lower()[:3]
        record.add_field(pymarc.Field("041", [" ", " "], ["a", lang]))

    # 040 — Cataloging source
    record.add_field(pymarc.Field("040", [" ", " "],
                                   ["a", "QuickCat", "b", "eng", "e", "rda", "c", "QuickCat"]))

    return record, warnings


def excel_to_records(
    file_path: str,
    material_type: str = "book",
) -> tuple[list[pymarc.Record], list[dict]]:
    """Convert an Excel or CSV file to pymarc Records.

    Returns (records, report) where report is a list of per-row dicts with warnings/errors.
    """
    cfg = _load_config()
    aliases = cfg.get("column_aliases", {})
    crosswalk = _load_crosswalk()
    templates = _load_templates()

    path = Path(file_path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        df = pd.read_excel(path, dtype=str)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path, dtype=str)
    else:
        raise ValueError(f"Unsupported format: {path.suffix}")

    records = []
    report = []
    for idx, row in df.iterrows():
        row_dict = row.to_dict()
        try:
            record, warnings = row_to_record(row_dict, material_type, templates, aliases, crosswalk)
            records.append(record)
            report.append({
                "row": idx + 2,
                "status": "warning" if warnings else "ok",
                "warnings": warnings,
            })
        except Exception as exc:
            report.append({
                "row": idx + 2,
                "status": "error",
                "error": str(exc),
            })

    return records, report
