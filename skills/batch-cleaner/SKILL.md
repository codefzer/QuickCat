---
name: batch-cleaner
description: >-
  This skill should be used when the user wants to 'clean MARC records', 'strip
  vendor tags', 'delete 9XX fields', 'normalize unicode', 'fix leader byte 09',
  'apply a profiler', 'batch sanitize records', 'remove local fields', 'stamp 003',
  'enforce UTF-8', 'NFC normalization', 'remove OCLC fields', 'delete holding fields',
  'tag deletion', or needs to prepare imported records for local catalog ingestion
  by stripping utility/vendor-specific fields. Also trigger for 'profiler-based
  cleaning' or 'MARC record sanitation'.
---

# Batch Cleaner

Profile-driven MARC record sanitation: delete unwanted tags, normalize all
string data to Unicode NFC, set Leader byte 09 to `'a'` (Unicode), and stamp
the 003 with your local MARC org code.

## Workflow

```
python3 skills/batch-cleaner/scripts/batch_clean.py input.mrc
python3 skills/batch-cleaner/scripts/batch_clean.py input.mrc --profile assets/default-profile.json
python3 skills/batch-cleaner/scripts/batch_clean.py input.mrc --org-code MYLIB --out clean.mrc
```

Steps performed automatically:

1. **Load profile** — Read tag deletion list and org code from JSON profile.
2. **Iterate records** — Process each record with `pymarc.MARCReader`.
3. **Delete tags** — Remove all fields matching the profile tag list (9XX deleted by range).
4. **Unicode NFC** — Apply `unicodedata.normalize('NFC', ...)` to all field data.
5. **Leader byte 09** — Set to `'a'` (Unicode/UTF-8 flag).
6. **003 stamp** — Overwrite (or create) 003 with the local MARC org code.
7. **Transaction log** — Per-record before/after snapshot to `.quickcat.log`.
8. **Output** — Write `{stem}_cleaned.mrc`; print summary statistics.

## Profile Format (`assets/default-profile.json`)

```json
{
  "delete_tags": ["019", "029", "035", "049", "263", "938"],
  "delete_ranges": [["900", "999"]],
  "org_code": "YOUR_MARC_ORG_CODE",
  "note": "Customize delete_tags and org_code for your institution"
}
```

Customize `org_code` with your institution's MARC organization code
(see https://www.loc.gov/marc/organizations/).

## Statistics Output

```
[batch_cleaner] Processed: 500 records
[batch_cleaner] Fields deleted: 1,847 (avg 3.7 per record)
[batch_cleaner] Tags: 019×234, 029×189, 938×412, 9XX×1012
[batch_cleaner] Unicode fixes: 23 subfields normalized
[batch_cleaner] Leader byte 09 set: 500 records
[batch_cleaner] Written: input_cleaned.mrc
```

## Reference Files

- `references/profiler-guide.md` — Leader byte positions, MARC org codes, tag deletion strategy
- `assets/default-profile.json` — Default deletion profile (customize before use)
