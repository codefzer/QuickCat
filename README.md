# QuickCat — AI-Enhanced Metadata Agent

<p align="center">
  <img src="assets/quickcat-logo.svg" alt="QuickCat logo" width="460" />
</p>

<p align="center"><sub>Canonical repository logo: <code>assets/quickcat-logo.svg</code></sub></p>

Modular AI Agent Toolbox for professional library cataloging. QuickCat automates the mechanical aspects of cataloging (harvesting, cleaning, validation) while augmenting the intellectual aspects (original cataloging, summary generation, authority grounding).

Built as a collection of Claude skills — each skill is a focused, self-contained unit with its own SKILL.md, scripts, references, and assets.

---

## Skills

| Skill | Purpose | Key Script |
|-------|---------|-----------|
| `copy-cataloger` | Harvest MARC records from Z39.50/SRU (LOC, BL, NLS, OCLC). ISBN-first search hierarchy, Green/Yellow/Red consensus engine, tie-breaker protocol. | `harvest_orchestrator.py` |
| `vision-to-marc` | Multimodal OCR of title page photos → MARC 21 fields via Claude Vision API. | `image_to_marc.py` |
| `authority-grounder` | Validate LCSH/LCNAF headings, inject `$0` URI subfields from id.loc.gov, apply ISBD punctuation. | `authority_lookup.py` |
| `brief-to-full-enhancer` | Generate MARC 520 (Summary) and 505 (Contents Note) using Claude. | `enhance_record.py` |
| `batch-cleaner` | Profile-driven tag deletion (9XX, vendor fields), Unicode NFC normalization, Leader byte fix, 003 stamping. | `batch_clean.py` |
| `marc-importer` | Ingest ISO-2709 binary or Excel/CSV → clean → validate → import-ready `.mrc`. | `import_pipeline.py` |
| `record-rollback` | Browse the transaction journal (`.quickcat.log`) and restore any record to a prior state. | `rollback.py` |
| `url-checker` | Async HTTP HEAD validation of all 856 $u electronic access URLs. | `check_856.py` |
| `marc-exporter` | Export validated records to ISO-2709 with productivity metrics (original vs. copy-cataloged, AI-tagged counts). | `export.py` |

---

## Installation

```bash
git clone https://github.com/codefzer/QuickCat.git
cd QuickCat
pip install -r requirements.txt
```

### Requirements

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/) for vision and generation skills
- Z39.50/SRU network access (institutional IP or credentials for OCLC/BL/NLS)

---

## Configuration

Copy the environment template and set your credentials:

```bash
# Required for vision-to-marc and brief-to-full-enhancer
export ANTHROPIC_API_KEY=sk-ant-...

# Required for Z39.50 sources that need authentication (e.g. OCLC)
export QC_Z3950_USER=your_username
export QC_Z3950_PASS=your_password
```

All server endpoints, timeouts, retry policy, consensus thresholds, and Excel column mappings are in **`config.json`**. Edit it for your institution before first use — in particular set `org_code` in `skills/batch-cleaner/assets/default-profile.json` to your [MARC organization code](https://www.loc.gov/marc/organizations/).

---

## Quick Start

### Copy catalog a book by ISBN

```bash
python3 skills/copy-cataloger/scripts/harvest_orchestrator.py --isbn 9780743273565
```

### Catalog from a title page photo

```bash
python3 skills/vision-to-marc/scripts/image_to_marc.py --image title_page.jpg --type book
```

### Clean a vendor MARC file before ILS import

```bash
python3 skills/batch-cleaner/scripts/batch_clean.py vendor_records.mrc --org-code MYLIB
```

### Import an acquisitions spreadsheet

```bash
python3 skills/marc-importer/scripts/import_pipeline.py acquisitions.xlsx --type book
```

### Validate subject headings and inject LC URIs

```bash
python3 skills/authority-grounder/scripts/authority_lookup.py records.mrc
```

### Undo a change

```bash
python3 skills/record-rollback/scripts/rollback.py --list --log .quickcat.log
python3 skills/record-rollback/scripts/rollback.py \
    --record-id "001:ocn12345678" --timestamp "2026-03-18T14:32:00Z" \
    --mrc records.mrc --log .quickcat.log
```

---

## Technical Standards

| Standard | Implementation |
|----------|---------------|
| MARC validation | `pymarc` structural checks in every script |
| Data models | `pydantic` for API responses and config objects |
| Unicode | `unicodedata.normalize('NFC')` + Leader byte 09=`'a'` |
| ISBD punctuation | Enforced in `authority-grounder` and `vision-to-marc` |
| Provenance | `$9 AI_QUICKCAT` on every AI-generated subfield |
| AI resilience | `tenacity` exponential backoff (max 5 retries, params from `config.json`) |
| Security | All credentials via environment variables — never in `config.json` |
| HITL | All AI-generated changes displayed as diff before any file write |
| Undo | Every edit logged to `.quickcat.log` transaction journal |

---

## Project Structure

```
QuickCat/
├── config.json                    # Runtime configuration (servers, thresholds, mappings)
├── requirements.txt
├── SKILLS-OVERVIEW.md             # Full workflow guide and skill index
├── skills/
│   ├── copy-cataloger/            # Z39.50 + SRU harvester + consensus engine
│   ├── vision-to-marc/            # Claude Vision → MARC
│   ├── authority-grounder/        # id.loc.gov authority validation
│   ├── brief-to-full-enhancer/    # Claude-generated 520/505 fields
│   ├── batch-cleaner/             # Tag deletion + Unicode normalization
│   ├── marc-importer/             # ISO-2709 / Excel import pipeline
│   ├── record-rollback/           # Transaction journal undo
│   ├── url-checker/               # 856 $u link validation
│   └── marc-exporter/             # ISO-2709 export + metrics
└── shared-resources/
    ├── scripts/                   # parse_marc.py, transaction_log.py, normalize_dates.py
    ├── references/                # marc-fields.md, validation-rules.json, crosswalk.json
    └── templates/                 # marc-templates.json (Book / E-book / Journal)
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
