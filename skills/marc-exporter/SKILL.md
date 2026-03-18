---
name: marc-exporter
description: >-
  This skill should be used when the user wants to 'export MARC records', 'export
  to ISO-2709', 'create a .mrc export file', 'generate a MARC batch', 'export for
  ILS import', 'output validated records', 'produce a MARC file', 'get cataloging
  statistics', 'productivity metrics', 'how many records were AI-generated', or
  needs to export a validated set of MARC records with a processing statistics report.
---

# MARC Exporter

Validate and export MARC records to ISO-2709 binary format, with a
productivity metrics report showing original vs. copy-cataloged counts
and AI-tagged field statistics.

## Workflow

```
python3 skills/marc-exporter/scripts/export.py records.mrc
python3 skills/marc-exporter/scripts/export.py records.mrc --out export.mrc --report metrics.json
```

## Metrics Report

```json
{
  "total_records": 150,
  "exported": 148,
  "skipped_invalid": 2,
  "original_cataloging": 12,
  "copy_cataloging": 136,
  "ai_enhanced_records": 45,
  "ai_tagged_fields": {
    "520": 45,
    "505": 38,
    "100": 12,
    "650": 23
  }
}
```

A record is counted as:
- **Original**: has no 035 field (no external system control number)
- **Copy-cataloged**: has a 035 field from OCLC or another utility
- **AI-enhanced**: has at least one field with `$9 AI_QUICKCAT`
