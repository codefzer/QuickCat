---
name: marc-importer
description: >-
  This skill should be used when the user wants to 'import MARC records', 'batch import',
  'ingest a MARC file', 'import from Excel', 'import from spreadsheet', 'process a vendor
  file', 'load records into catalog', 'clean and import', 'ISO-2709 import', 'bulk load MARC',
  or needs to take a raw MARC file or Excel spreadsheet and prepare it for ingestion into
  a local ILS. Also trigger for 'profile-based import', 'MARC file processing', or 'Excel to MARC'.
---

# MARC Importer

Ingest MARC records from ISO-2709 binary files or Excel spreadsheets,
apply the batch-cleaner profile, validate structure, and output an
import-ready `.mrc` file with a processing report.

## Workflow

### ISO-2709 (.mrc) import
```
python3 skills/marc-importer/scripts/import_pipeline.py records.mrc
python3 skills/marc-importer/scripts/import_pipeline.py records.mrc --profile ../batch-cleaner/assets/default-profile.json
```

### Excel spreadsheet import
```
python3 skills/marc-importer/scripts/import_pipeline.py acquisitions.xlsx
python3 skills/marc-importer/scripts/import_pipeline.py titles.xlsx --type ebook
```

Steps performed automatically:

1. **Detect format** — ISO-2709 binary or Excel (.xlsx/.csv) based on file extension.
2. **Parse input** — Read all records/rows.
3. **Excel → MARC** — Map column headers using `shared-resources/references/crosswalk.json` + `config.json` aliases.
4. **Apply cleaner** — Run batch-cleaner profile (tag deletion, Unicode NFC, Leader byte).
5. **Validate** — Check required fields (001, 245, 008) against `shared-resources/references/validation-rules.json`.
6. **Output** — `{stem}_import_ready.mrc` + summary report.

## Excel Column Mapping

Column headers are normalized using `column_aliases` in `config.json`.
Unrecognized columns are logged as warnings — partial imports succeed.

| Excel Column | MARC Field |
|-------------|-----------|
| Title / Book Title | 245 $a |
| Author | 100 $a (name inverted) |
| ISBN / ISBN-13 | 020 $a |
| Publisher | 264 $b |
| Year / Pub Year | 264 $c |
| Pages | 300 $a |
| Subject | 650 $a (repeatable; split on `;`) |

## Output

- `{stem}_import_ready.mrc` — Cleaned, validated records
- `{stem}_import_report.json` — Per-record status: valid/warning/error

## Shared Dependencies

| File | Purpose |
|------|---------|
| `shared-resources/references/crosswalk.json` | DC→MARC and Excel column→MARC field mappings |
| `shared-resources/references/validation-rules.json` | Required fields (001, 245, 008) and format rules |
| `skills/batch-cleaner/assets/default-profile.json` | Default tag deletion profile (customize org_code) |
