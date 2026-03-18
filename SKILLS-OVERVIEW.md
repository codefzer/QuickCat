# QuickCat: AI-Enhanced Metadata Agent


Modular AI Agent Toolbox for professional library cataloging. Automates the
mechanical aspects of cataloging (harvesting, cleaning, validation) while
augmenting the intellectual aspects (original cataloging, summary generation,
authority grounding).

---

## Skills Summary

### 1. copy-cataloger ← Start here for new records
Harvest MARC records from Z39.50 (LOC, BL, NLS, OCLC) and SRU sources.
Runs ISBN-first search hierarchy, consensus engine (Green/Yellow/Red conflicts),
and tie-breaker protocol for unresolvable discrepancies.

**When to use:** Searching for, downloading, or copy-cataloging a MARC record by ISBN or LCCN.

**Key scripts:**
- `scripts/validation_gate.py` — ISBN-13 check digit, LCCN format, material type detection
- `scripts/harvest_metadata.py` — Single-source async query (SRU or Z39.50)
- `scripts/audit_consensus.py` — Field-level conflict scoring
- `scripts/resolve_tie_breaker.py` — Third-library juror for Red conflicts
- `scripts/harvest_orchestrator.py` — Full pipeline orchestrator

---

### 2. vision-to-marc
Multimodal OCR of title page photos → MARC 21 bibliographic record.
Uses Claude Vision API; every field stamped `$9 AI_QUICKCAT`.

**When to use:** Cataloging from an image, scan, or photo of a title page.

**Key script:** `scripts/image_to_marc.py`

---

### 3. authority-grounder
Validate LCSH/LCNAF headings in 1XX/6XX/7XX fields via id.loc.gov SRU.
Injects `$0` URI subfields, applies ISBD punctuation normalization, flags
unmatched headings for HITL review.

**When to use:** Authority control, $0 URI injection, LCSH/LCNAF validation.

**Key script:** `scripts/authority_lookup.py`

---

### 4. brief-to-full-enhancer
Generate MARC 520 (Summary) and 505 (Contents Note) fields using Claude.
Context extracted from existing 100/245/260/650 fields.

**When to use:** Upgrading brief copy-catalog records to full bibliographic level.

**Key script:** `scripts/enhance_record.py`

---

### 5. batch-cleaner
Profile-driven MARC sanitation: delete unwanted tags (9XX, 019, 035, etc.),
normalize Unicode to NFC, set Leader byte 09='a', stamp 003 with local MARC org code.

**When to use:** Cleaning vendor/OCLC files before local ILS import.

**Key script:** `scripts/batch_clean.py`
**Profile:** `assets/default-profile.json` (customize org_code before use)

---

### 6. marc-importer
Full import pipeline: ISO-2709 or Excel → clean → validate → export.
Excel columns mapped via `config.json` column aliases and `crosswalk.json`.

**When to use:** Batch importing from vendor MARC files or acquisitions spreadsheets.

**Key scripts:** `scripts/import_pipeline.py`, `scripts/excel_to_marc.py`

---

### 7. record-rollback
Browse and restore from the QuickCat transaction journal (`.quickcat.log`).
Every editing skill writes before/after snapshots; rollback to any prior state.

**When to use:** Undoing a change, reviewing edit history, restoring a corrupted record.

**Key script:** `scripts/rollback.py`

---

### 8. url-checker
Async HTTP HEAD validation of all 856 $u URLs in a `.mrc` file.
Outputs CSV report: status code, redirect chain, response time.

**When to use:** Auditing electronic access links, finding dead URLs.

**Key script:** `scripts/check_856.py`

---

### 9. marc-exporter
Validate and export records to ISO-2709 with productivity metrics:
original vs. copy-cataloged counts, AI-enhanced record statistics.

**When to use:** Final export step before ILS import; generating cataloging statistics.

**Key script:** `scripts/export.py`

---

## Integrated Workflow Examples

### Scenario 1: Copy Catalog a New Book

```bash
# 1. Harvest and merge from LOC + BL
python3 skills/copy-cataloger/scripts/harvest_orchestrator.py --isbn 9780743273565

# 2. Validate subject headings and inject $0 URIs
python3 skills/authority-grounder/scripts/authority_lookup.py merged_9780743273565.mrc

# 3. Add summary and table of contents
python3 skills/brief-to-full-enhancer/scripts/enhance_record.py merged_9780743273565_verified.mrc

# 4. Export final record
python3 skills/marc-exporter/scripts/export.py merged_9780743273565_verified_enhanced.mrc
```

### Scenario 2: Catalog from a Title Page Photo

```bash
# 1. Extract MARC fields from image
python3 skills/vision-to-marc/scripts/image_to_marc.py --image title_page.jpg --type book

# 2. Ground subject headings
python3 skills/authority-grounder/scripts/authority_lookup.py title_page.mrc

# 3. Generate summary note
python3 skills/brief-to-full-enhancer/scripts/enhance_record.py title_page_verified.mrc
```

### Scenario 3: Clean a Vendor MARC File

```bash
# 1. Clean vendor file (delete 9XX, normalize unicode, stamp 003)
python3 skills/batch-cleaner/scripts/batch_clean.py vendor_records.mrc --org-code MYLIB

# 2. Validate and export
python3 skills/marc-exporter/scripts/export.py vendor_records_cleaned.mrc
```

### Scenario 4: Import from Acquisitions Spreadsheet

```bash
# 1. Convert Excel → MARC and clean
python3 skills/marc-importer/scripts/import_pipeline.py acquisitions.xlsx --type book

# 2. Check electronic links before upload
python3 skills/url-checker/scripts/check_856.py acquisitions_import_ready.mrc
```

---

## Shared Resources

```
shared-resources/
├── scripts/
│   ├── parse_marc.py           # MARC binary/XML → standardized JSON
│   ├── transaction_log.py      # Before/after snapshot journal (undo support)
│   └── normalize_dates.py      # Date normalization utilities
├── references/
│   ├── marc-fields.md          # MARC 21 field reference
│   ├── validation-rules.json   # Required fields, format rules
│   ├── priority-rules.json     # Global vs. local field priority
│   └── crosswalk.json          # DC→MARC and Excel→MARC mappings
└── templates/
    └── marc-templates.json     # Material-specific Leader/008 byte defaults
```

---

## Technical Standards

| Standard | Implementation |
|----------|---------------|
| MARC validation | `pymarc` in every script |
| Data models | `pydantic` for API responses and config |
| Unicode | `unicodedata.normalize('NFC')` + Leader byte 09=`'a'` |
| ISBD punctuation | Enforced in `authority-grounder` and `vision-to-marc` |
| Provenance | `$9 AI_QUICKCAT` on all AI-generated subfields |
| AI resilience | `tenacity` exponential backoff (max 5 retries) |
| Security | Credentials via env vars (`QC_Z3950_USER`, `QC_Z3950_PASS`) |
| HITL | All AI changes shown as diff before write |
| Undo | `.quickcat.log` transaction journal for every edit |

---

## Configuration

Edit `config.json` to configure:
- Library server endpoints (LOC, BL, NLS, OCLC)
- Timeout and retry parameters
- Consensus similarity threshold
- Tie-breaker server
- Excel column aliases
- MARC org code for 003 stamping

**Never store credentials in `config.json`.** Use environment variables:
```bash
export QC_Z3950_USER=your_username
export QC_Z3950_PASS=your_password
export ANTHROPIC_API_KEY=sk-ant-...
```

---

*QuickCat — Built from scratch for professional library cataloging workflows.*
*All AI-generated fields marked $9 AI_QUICKCAT for full auditability.*
