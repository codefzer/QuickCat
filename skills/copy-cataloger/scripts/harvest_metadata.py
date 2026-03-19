"""Sub-Skill A: harvest_metadata — query a single library source for a MARC record.

Returns MARCXML string on success, or a structured error string on failure.
Error strings are designed so the orchestrator can decide to retry or skip.

Usage:
    python3 skills/copy-cataloger/scripts/harvest_metadata.py --isbn 9780743273565 --source loc
    python3 skills/copy-cataloger/scripts/harvest_metadata.py --lccn n78890335 --source nls
"""

import argparse
import asyncio
import sys
from io import BytesIO
from pathlib import Path

import httpx
import pymarc
from tenacity import retry, stop_after_attempt, wait_exponential

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "shared-resources" / "scripts"))
import quickcat_loader  # noqa: F401  – registers shared-resources aliases

from shared_resources.scripts.config_loader import load_config, load_servers  # noqa: E402


# ─── SRU harvest ─────────────────────────────────────────────────────────────

async def _sru_query(server: dict, query: str, timeout: int) -> str:
    """Perform an SRU search and return the first MARCXML record as a string."""
    params = {
        "operation": "searchRetrieve",
        "version": "1.1",
        "query": query,
        "maximumRecords": "1",
        "recordSchema": "marcxml",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(server["url"], params=params)
        resp.raise_for_status()

    content = resp.text
    if "<numberOfRecords>0" in content or "<numberOfRecords>0<" in content:
        return "Record Not Found"

    # Extract the first <marc:record> block
    start = content.find("<marc:record")
    if start == -1:
        start = content.find("<record")
    end_tag = "</marc:record>" if "<marc:record" in content else "</record>"
    end = content.find(end_tag, start)
    if start == -1 or end == -1:
        return "Record Not Found"

    raw_record = content[start: end + len(end_tag)]
    # Wrap in collection for pymarc parsing
    return f'<?xml version="1.0"?><collection xmlns="http://www.loc.gov/MARC21/slim">{raw_record}</collection>'


# ─── Z39.50 harvest ───────────────────────────────────────────────────────────

def _z3950_query(server: dict, identifier: str, search_type: str, cfg: dict) -> str:
    """Perform a Z39.50 search using PyZ3950."""
    try:
        from PyZ3950 import zoom  # type: ignore
    except ImportError:
        return "Authentication Failure: PyZ3950 not installed"

    import os
    conn = zoom.Connection(server["host"], server["port"])
    conn.databaseName = server["database"]
    conn.preferredRecordSyntax = "MARCXML"

    user = os.environ.get("QC_Z3950_USER")
    password = os.environ.get("QC_Z3950_PASS")
    if user:
        conn.user = user
    if password:
        conn.password = password

    bib1 = cfg["search"].get(f"bib1_{search_type}", cfg["search"]["bib1_isbn"])
    query_str = f'@attr 1={bib1["use"]} @attr 2={bib1["relation"]} @attr 4={bib1["structure"]} "{identifier}"'

    try:
        conn.connect()
        query = zoom.Query("PQF", query_str.encode())
        rs = conn.search(query)
        if len(rs) == 0:
            return "Record Not Found"
        rec = rs[0]
        raw = rec.data
        if isinstance(raw, str):
            raw = raw.encode("latin-1")
        reader = pymarc.MARCReader(BytesIO(raw), to_unicode=True, force_utf8=True)
        record = next(reader, None)
        if record is None:
            return "Record Not Found"
        buf = BytesIO()
        writer = pymarc.XMLWriter(buf)
        writer.write(record)
        writer.close()
        return buf.getvalue().decode("utf-8")
    except Exception as exc:
        err = str(exc).lower()
        if "timeout" in err or "timed out" in err:
            return "Protocol Timeout"
        if "auth" in err or "access" in err:
            return "Authentication Failure"
        return f"Protocol Timeout: {exc}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ─── Public interface ─────────────────────────────────────────────────────────

async def harvest_metadata(identifier: str, source_key: str) -> str:
    """Query one library source and return MARCXML or a structured error string.

    Args:
        identifier: ISBN-13, ISBN-10, or LCCN string.
        source_key: Key in config.json 'servers' dict (e.g., 'loc', 'nls').

    Returns:
        MARCXML collection string, or one of:
        'Record Not Found', 'Protocol Timeout', 'Authentication Failure'
    """
    cfg = load_config()
    servers = load_servers()
    if source_key not in servers:
        return f"Authentication Failure: unknown source_key {source_key!r}"

    server = servers[source_key]
    timeout = cfg["timeouts"].get("z3950_search" if server["type"] == "Z3950" else "sru_request", 30)
    max_attempts = cfg["retry"]["max_attempts"]
    backoff = cfg["retry"]["backoff_factor"]

    # Determine search type from identifier format
    import re
    search_type = "isbn" if re.match(r"^[\d\-X]+$", identifier) else "title"

    @retry(stop=stop_after_attempt(max_attempts), wait=wait_exponential(multiplier=backoff, min=1, max=30))
    async def _attempt():
        if server["type"] == "SRU":
            if search_type == "isbn":
                cql = f'bath.isbn="{identifier}"'
            else:
                cql = f'dc.title="{identifier}"'
            return await _sru_query(server, cql, timeout)
        else:
            return await asyncio.to_thread(_z3950_query, server, identifier, search_type, cfg)

    try:
        return await _attempt()
    except Exception as exc:
        return f"Protocol Timeout: {exc}"


async def _main_async(args):
    identifier = args.isbn or args.lccn
    result = await harvest_metadata(identifier, args.source)
    if result.startswith("Record Not Found") or result.startswith("Protocol") or result.startswith("Authentication"):
        print(f"[harvest_metadata] {result}", file=sys.stderr)
        sys.exit(1 if not args.allow_errors else 0)
    print(result)


def main():
    parser = argparse.ArgumentParser(description="Harvest a MARC record from one library source")
    parser.add_argument("--isbn", help="ISBN-10 or ISBN-13")
    parser.add_argument("--lccn", help="Library of Congress Control Number")
    parser.add_argument("--source", required=True, help="Source key from config.json (loc, bl, nls, oclc)")
    parser.add_argument("--allow-errors", action="store_true", help="Exit 0 even on 'Record Not Found'")
    parser.add_argument("--test", action="store_true", help="Run connectivity test and exit")
    args = parser.parse_args()

    if args.test:
        print("[harvest_metadata] --test: verifying config.json loads...")
        load_config()
        print(f"  Configured sources: {list(load_servers().keys())}")
        print("  OK")
        return

    if not args.isbn and not args.lccn:
        print("ERROR: provide --isbn or --lccn", file=sys.stderr)
        sys.exit(1)

    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
