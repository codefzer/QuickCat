---
name: record-rollback
description: >-
  This skill should be used when the user wants to 'undo a change', 'rollback a record',
  'revert to original', 'restore before edits', 'check edit history', 'undo authority
  changes', 'restore a MARC record', 'view transaction log', 'list revisions', or says
  'I accidentally corrupted a record' or 'the record looked better before'. Also trigger
  when the user mentions the transaction log, .quickcat.log, QuickCat undo, or wants to
  see what changes were made to a specific MARC record by QuickCat.
---

# Record Rollback

Browse the QuickCat transaction journal (`.quickcat.log`) and restore any
MARC record to its state before a specific edit was applied.

Every QuickCat editing skill (vision-to-marc, authority-grounder,
brief-to-full-enhancer, batch-cleaner, copy-cataloger, marc-importer)
writes a before/after snapshot to `.quickcat.log` in the same directory
as the processed `.mrc` file.

## Workflow

### List revisions for a record

```
python3 skills/record-rollback/scripts/rollback.py --list --record-id "001:ocn12345678" --log .quickcat.log
```

Output:
```
Revisions for record 001:ocn12345678:
  1. 2026-03-18T14:32:00Z  authority-grounder  [650 $0 injected, 100 ISBD punctuation]
  2. 2026-03-18T15:01:22Z  brief-to-full-enhancer  [520 generated, 505 generated]
```

### Rollback to a specific revision

```
python3 skills/record-rollback/scripts/rollback.py \
    --record-id "001:ocn12345678" \
    --timestamp "2026-03-18T14:32:00Z" \
    --mrc records.mrc \
    --log .quickcat.log
```

This writes a file `records_rollback_20260318143200.mrc` alongside the original.

### Rollback all records in a log to their first recorded state

```
python3 skills/record-rollback/scripts/rollback.py --rollback-all --log .quickcat.log --mrc records.mrc
```

## Log Location

The `.quickcat.log` file is written to the same directory as the processed
`.mrc` file. Each line is a JSON object containing:
- `timestamp` — ISO 8601 UTC
- `skill` — which skill made the change
- `record_id` — the 001 control number
- `before` / `after` — full MARC record snapshots
- `changes` — human-readable list of modifications
