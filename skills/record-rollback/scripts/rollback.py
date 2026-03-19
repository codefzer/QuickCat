"""Record Rollback — browse and restore from the QuickCat transaction journal.

Usage:
    python3 skills/record-rollback/scripts/rollback.py --list --log .quickcat.log
    python3 skills/record-rollback/scripts/rollback.py --list --record-id "001:ocn12345678" --log .quickcat.log
    python3 skills/record-rollback/scripts/rollback.py \\
        --record-id "001:ocn12345678" --timestamp "2026-03-18T14:32:00Z" \\
        --mrc records.mrc --log .quickcat.log
    python3 skills/record-rollback/scripts/rollback.py --rollback-all --log .quickcat.log --mrc records.mrc
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "shared-resources" / "scripts"))
import quickcat_loader          # noqa: F401  – registers cross-package import aliases

from shared_resources.scripts.transaction_log import list_revisions, rollback, purge_log  # noqa: E402


def _load_log(log_path: str) -> list[dict]:
    p = Path(log_path)
    if not p.exists():
        print(f"ERROR: log file not found: {log_path}", file=sys.stderr)
        sys.exit(1)
    entries = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def cmd_list(args):
    """List revisions in the transaction log."""
    entries = _load_log(args.log)

    if args.record_id:
        entries = [e for e in entries if e.get("record_id") == args.record_id]
        if not entries:
            print(f"No revisions found for record_id={args.record_id!r}")
            return
        print(f"Revisions for record {args.record_id!r}:")
    else:
        # Group by record_id
        from collections import defaultdict
        by_record: dict = defaultdict(list)
        for e in entries:
            by_record[e.get("record_id", "unknown")].append(e)
        print(f"Transaction log: {len(entries)} entries, {len(by_record)} unique records")
        print()
        for rid, revs in sorted(by_record.items()):
            print(f"  {rid}  ({len(revs)} revision(s))")
            for i, rev in enumerate(revs, 1):
                changes = ", ".join(rev.get("changes", [])[:2])
                if len(rev.get("changes", [])) > 2:
                    changes += f" (+{len(rev['changes'])-2} more)"
                print(f"    {i}. {rev['timestamp']}  [{rev['skill']}]  {changes}")
        return

    for i, e in enumerate(entries, 1):
        changes = "; ".join(e.get("changes", []))
        print(f"  {i}. {e['timestamp']}  skill={e['skill']!r}")
        if changes:
            print(f"     Changes: {changes[:100]}")


def cmd_rollback_single(args):
    """Rollback one record to a specific timestamp."""
    if not args.mrc:
        print("ERROR: --mrc required for rollback", file=sys.stderr)
        sys.exit(1)

    result = rollback(
        record_id=args.record_id,
        timestamp=args.timestamp,
        mrc_path=args.mrc,
    )
    if result is None:
        sys.exit(1)
    print("[rollback] Success.")


def cmd_purge(args):
    """Purge the transaction log — all entries or those older than --keep-days."""
    removed = purge_log(args.log, keep_days=args.keep_days)
    if args.keep_days is None:
        print(f"[purge] Deleted log file. {removed} entries removed.")
    else:
        print(f"[purge] Removed {removed} entries older than {args.keep_days} day(s).")


def cmd_rollback_all(args):
    """Rollback all records in the log to their first recorded 'before' state."""
    if not args.mrc:
        print("ERROR: --mrc required for rollback-all", file=sys.stderr)
        sys.exit(1)

    entries = _load_log(args.log)
    from collections import defaultdict
    by_record: dict = defaultdict(list)
    for e in entries:
        by_record[e.get("record_id", "unknown")].append(e)

    print(f"[rollback-all] Rolling back {len(by_record)} record(s) to first recorded state...")
    success = 0
    for rid, revs in by_record.items():
        # First entry chronologically
        first = min(revs, key=lambda e: e["timestamp"])
        result = rollback(
            record_id=rid,
            timestamp=first["timestamp"],
            mrc_path=args.mrc,
        )
        if result:
            success += 1

    print(f"[rollback-all] Restored {success}/{len(by_record)} records.")


def main():
    parser = argparse.ArgumentParser(description="QuickCat record rollback utility")
    parser.add_argument("--log", default=".quickcat.log",
                        help="Path to .quickcat.log (default: .quickcat.log)")
    parser.add_argument("--mrc", help="Path to the .mrc file being restored")
    parser.add_argument("--record-id", help="Record identifier, e.g. '001:ocn12345678'")
    parser.add_argument("--timestamp", help="ISO timestamp from the log entry to restore")

    parser.add_argument("--keep-days", type=int, default=None, metavar="N",
                        help="With --purge: keep entries newer than N days, remove the rest. "
                             "Omit to delete the entire log.")

    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--list", action="store_true", help="List revisions in the log")
    actions.add_argument("--rollback-all", action="store_true",
                         help="Rollback all records to first recorded state")
    actions.add_argument("--purge", action="store_true",
                         help="Purge the log. Use with --keep-days N to retain recent entries.")

    args = parser.parse_args()

    if args.list:
        cmd_list(args)
    elif args.rollback_all:
        cmd_rollback_all(args)
    elif args.purge:
        cmd_purge(args)
    elif args.record_id and args.timestamp:
        cmd_rollback_single(args)
    else:
        print("Provide --list, --rollback-all, --purge, or (--record-id + --timestamp)", file=sys.stderr)
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
