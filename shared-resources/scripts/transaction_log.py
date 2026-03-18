"""Transaction journal for QuickCat — log before/after snapshots for every record edit.

Usage:
    from shared_resources.scripts.transaction_log import log_edit, list_revisions, rollback

Every editing skill calls log_edit() before writing the modified record.
The log file is .quickcat.log in the same directory as the processed .mrc file.
"""

import json
import os
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pymarc


def _record_to_dict(record: pymarc.Record) -> dict:
    """Serialize a pymarc Record to a JSON-safe dict."""
    return {
        "leader": str(record.leader),
        "fields": [
            {
                "tag": field.tag,
                "data": field.data if hasattr(field, "data") else None,
                "indicator1": field.indicator1 if hasattr(field, "indicator1") else None,
                "indicator2": field.indicator2 if hasattr(field, "indicator2") else None,
                "subfields": field.subfields if hasattr(field, "subfields") else None,
            }
            for field in record.fields
        ],
    }


def _dict_to_record(data: dict) -> pymarc.Record:
    """Restore a pymarc Record from a serialized dict."""
    record = pymarc.Record()
    record.leader = data["leader"]
    for f in data["fields"]:
        if f["data"] is not None:
            record.add_field(pymarc.Field(tag=f["tag"], data=f["data"]))
        else:
            record.add_field(
                pymarc.Field(
                    tag=f["tag"],
                    indicators=[f["indicator1"] or " ", f["indicator2"] or " "],
                    subfields=f["subfields"] or [],
                )
            )
    return record


def _get_record_id(record: pymarc.Record) -> str:
    """Return the 001 value, or a fallback identifier."""
    field = record["001"]
    if field:
        return f"001:{field.data.strip()}"
    field245 = record["245"]
    if field245:
        return f"245:{field245.value()[:40]}"
    return "unknown"


def _log_path(mrc_path: str) -> Path:
    """Return the .quickcat.log path alongside the given .mrc file."""
    return Path(mrc_path).parent / ".quickcat.log"


def log_edit(
    skill_name: str,
    record_before: pymarc.Record,
    record_after: pymarc.Record,
    mrc_path: str = ".",
    changes: list[str] | None = None,
) -> None:
    """Append a before/after snapshot entry to the transaction log.

    Args:
        skill_name: Name of the skill making the edit (e.g., 'authority-grounder').
        record_before: The pymarc Record before modification.
        record_after: The pymarc Record after modification.
        mrc_path: Path to the .mrc file being edited — log lives alongside it.
        changes: Optional list of human-readable change descriptions.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "skill": skill_name,
        "record_id": _get_record_id(record_before),
        "before": _record_to_dict(record_before),
        "after": _record_to_dict(record_after),
        "changes": changes or [],
    }
    log_file = _log_path(mrc_path)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def list_revisions(record_id: str, mrc_path: str = ".") -> list[dict]:
    """Return all log entries for a given record_id.

    Args:
        record_id: Value as stored in the log, e.g. '001:ocn12345678'.
        mrc_path: Path to the .mrc file (used to locate the log).

    Returns:
        List of log entry dicts, oldest first.
    """
    log_file = _log_path(mrc_path)
    if not log_file.exists():
        return []
    entries = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("record_id") == record_id:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
    return entries


def clone_record(record: pymarc.Record) -> pymarc.Record:
    """Return a copy of a Record for before/after transaction snapshots.

    Args:
        record: The pymarc Record to copy.

    Returns:
        A new pymarc.Record with the same leader and fields.
    """
    copy = pymarc.Record()
    copy.leader = record.leader
    for field in record.fields:
        copy.add_field(field)
    return copy


def purge_log(mrc_path: str, keep_days: int | None = None) -> int:
    """Remove entries from the transaction log.

    Args:
        mrc_path: Path to the .mrc file (used to locate the log).
        keep_days: If given, remove only entries older than this many days.
                   If None, delete the entire log file.

    Returns:
        Number of entries removed.
    """
    log_file = _log_path(mrc_path)
    if not log_file.exists():
        return 0

    if keep_days is None:
        # Count entries before deleting
        count = sum(1 for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip())
        log_file.unlink()
        return count

    cutoff = datetime.now(timezone.utc).timestamp() - keep_days * 86400
    kept: list[str] = []
    removed = 0
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
                ts = datetime.fromisoformat(entry["timestamp"]).timestamp()
                if ts >= cutoff:
                    kept.append(stripped)
                else:
                    removed += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                kept.append(stripped)  # Keep malformed lines to avoid silent data loss

    if removed:
        with open(log_file, "w", encoding="utf-8") as f:
            for line in kept:
                f.write(line + "\n")

    return removed


def rollback(record_id: str, timestamp: str, mrc_path: str) -> pymarc.Record | None:
    """Restore the 'before' snapshot for a specific log entry.

    Writes the restored record back to a file named
    {original_stem}_rollback_{timestamp_short}.mrc alongside the original.

    Args:
        record_id: e.g. '001:ocn12345678'
        timestamp: ISO timestamp string matching a log entry.
        mrc_path: Path to the original .mrc file.

    Returns:
        The restored pymarc Record, or None if the entry was not found.
    """
    entries = list_revisions(record_id, mrc_path)
    matched = next((e for e in entries if e["timestamp"] == timestamp), None)
    if not matched:
        print(f"[rollback] No log entry found for record_id={record_id!r} at {timestamp!r}")
        return None

    restored = _dict_to_record(matched["before"])

    ts_short = timestamp.replace(":", "").replace("-", "")[:15]
    out_path = Path(mrc_path).parent / f"{Path(mrc_path).stem}_rollback_{ts_short}.mrc"
    with open(out_path, "wb") as out_file:
        writer = pymarc.MARCWriter(out_file)
        writer.write(restored)
        writer.close()

    print(f"[rollback] Restored record {record_id!r} to state at {timestamp}")
    print(f"[rollback] Written to: {out_path}")
    return restored
