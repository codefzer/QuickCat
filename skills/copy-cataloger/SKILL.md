---
name: copy-cataloger
description: >-
  This skill should be used when the user wants to 'search for a MARC record',
  'harvest bibliographic data', 'copy catalog', 'fetch from Library of Congress',
  'search Z39.50', 'search SRU', 'look up ISBN in library catalog', 'find a MARC
  record online', 'download catalog record', 'get record from OCLC', 'get record
  from British Library', or 'get record from NLS'. Also trigger when the user
  provides an ISBN or LCCN and wants bibliographic data. Includes conflict
  resolution (Green/Yellow/Red consensus) and tie-breaker protocol.
---

# Copy Cataloger

Harvest MARC records from multiple library sources (Z39.50 and SRU), apply
a consensus engine to resolve field conflicts, and produce a merged record
ready for local editing.

## Workflow

### Step 1: Validation Gate

Before any network call, run `validation_gate.py` to:
- Validate ISBN-13 check digit (Mod 10) or LCCN format
- Check for existing record in local ILS (de-duplication)
- Identify material type and load the appropriate MARC template

If validation fails, output a clear error and stop — do not attempt harvest.

### Step 2: Harvest

Run `harvest_orchestrator.py`, which calls `harvest_metadata.py` per source:

```
python3 skills/copy-cataloger/scripts/harvest_orchestrator.py --isbn 9780743273565
python3 skills/copy-cataloger/scripts/harvest_orchestrator.py --lccn n78890335 --sources loc,nls
```

Search hierarchy:
1. ISBN exact match (all configured sources in parallel)
2. Title + Author fuzzy match (if ISBN returns no results)
3. Authority heading search (if title/author returns no results)

Each source call returns MARCXML or a structured error string:
- `"Record Not Found"` — skip this source
- `"Protocol Timeout"` — retry up to max_attempts (from config.json)
- `"Authentication Failure"` — log and skip

### Step 3: Consensus

Run `audit_consensus.py` to compare records field by field:

```
python3 skills/copy-cataloger/scripts/audit_consensus.py record_a.xml record_b.xml
```

Output: JSON list of ConflictItems with severity scores.

Conflict dashboard:
- 🟢 **Green** (score < 0.3): auto-merge, accept reference value
- 🟡 **Yellow** (0.3–0.7): review suggested, default accept reference
- 🔴 **Red** (score > 0.7): invoke tie-breaker, require manual review

Local-priority fields (090, 590, 852, 9XX) are never conflicted — always
preserve local values regardless of what the reference source contains.

### Step 4: Tie-Breaker (Red conflicts only)

Run `resolve_tie_breaker.py` automatically for Red conflicts:

```
python3 skills/copy-cataloger/scripts/resolve_tie_breaker.py --conflicts conflicts.json --isbn 9780743273565
```

Queries the juror library defined in `config.json → consensus.tie_breaker_server`.
Returns a third MARCXML record used as the deciding vote.

### Step 5: Output

- `merged_record.mrc` — binary MARC ready for local import
- `conflict_report.json` — full audit log of all resolved and unresolved conflicts
- HITL diff printed to stdout for all Yellow/Red fields

## Configuration

All server endpoints, timeouts, retry logic, and Bib-1 search attributes are
loaded from `config.json` at runtime. Never hardcode server addresses.

Credentials (if required) must be set as environment variables:
- `QC_Z3950_USER` / `QC_Z3950_PASS`

## Reference Files

- `references/z3950-bib1-attributes.md` — Bib-1 Use, Relation, Structure, Completeness values
- `references/search-hierarchy.md` — Detailed search strategy documentation
- `assets/conflict-severity-matrix.json` — Tag weights used in severity scoring
