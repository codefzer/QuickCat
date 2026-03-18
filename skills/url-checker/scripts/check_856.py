"""URL Checker — validate all 856 $u links in a MARC file via async HTTP HEAD.

Usage:
    python3 skills/url-checker/scripts/check_856.py records.mrc
    python3 skills/url-checker/scripts/check_856.py records.mrc --out links.csv --concurrency 20
"""

import argparse
import asyncio
import csv
import sys
import time
from pathlib import Path

import httpx
import pymarc


async def _check_url(client: httpx.AsyncClient, record_id: str, url: str) -> dict:
    """Send a HEAD request and return status info."""
    start = time.monotonic()
    try:
        resp = await client.head(url, follow_redirects=False, timeout=15)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        redirect = str(resp.headers.get("location", ""))
        return {
            "record_id": record_id,
            "url": url,
            "status_code": resp.status_code,
            "status_text": resp.reason_phrase,
            "redirect_url": redirect,
            "response_ms": elapsed_ms,
        }
    except httpx.TimeoutException:
        return {
            "record_id": record_id,
            "url": url,
            "status_code": 0,
            "status_text": "Timeout",
            "redirect_url": "",
            "response_ms": int((time.monotonic() - start) * 1000),
        }
    except Exception as exc:
        return {
            "record_id": record_id,
            "url": url,
            "status_code": -1,
            "status_text": f"Error: {exc}",
            "redirect_url": "",
            "response_ms": 0,
        }


async def check_all(mrc_path: str, concurrency: int = 10) -> list[dict]:
    """Extract all 856 $u URLs and check them concurrently."""
    links = []
    with open(mrc_path, "rb") as f:
        reader = pymarc.MARCReader(f, to_unicode=True, force_utf8=True)
        for record in reader:
            if not record:
                continue
            rec_id = record["001"].data.strip() if record["001"] else "unknown"
            for field in record.get_fields("856"):
                url = field["u"]
                if url:
                    links.append((f"001:{rec_id}", url.strip()))

    print(f"[url_checker] Found {len(links)} 856 $u URLs")

    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "QuickCat-URLChecker/1.0 (library cataloging tool)"},
        follow_redirects=False,
    ) as client:
        async def bounded_check(rec_id, url):
            async with semaphore:
                return await _check_url(client, rec_id, url)

        tasks = [bounded_check(rid, url) for rid, url in links]
        completed = await asyncio.gather(*tasks)
        results.extend(completed)

    # Sort: errors first, then redirects, then OK
    def sort_key(r):
        code = r["status_code"]
        if code == 0 or code == -1:
            return 0
        if code >= 400:
            return 1
        if code in (301, 302):
            return 2
        return 3

    results.sort(key=sort_key)
    return results


def main():
    parser = argparse.ArgumentParser(description="Check 856 $u URLs in a MARC file")
    parser.add_argument("mrc_file", nargs="?", help="Input .mrc file")
    parser.add_argument("--out", help="Output CSV file path")
    parser.add_argument("--concurrency", type=int, default=10,
                        help="Max concurrent HTTP requests (default: 10)")
    args = parser.parse_args()

    if not args.mrc_file:
        print("ERROR: provide mrc_file", file=sys.stderr)
        sys.exit(1)

    results = asyncio.run(check_all(args.mrc_file, args.concurrency))

    out_path = Path(args.out) if args.out else Path(args.mrc_file).with_suffix(".csv")

    fieldnames = ["record_id", "url", "status_code", "status_text", "redirect_url", "response_ms"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Summary
    ok = sum(1 for r in results if 200 <= r["status_code"] < 300)
    redirects = sum(1 for r in results if r["status_code"] in (301, 302, 303, 307, 308))
    errors = sum(1 for r in results if r["status_code"] >= 400)
    unreachable = sum(1 for r in results if r["status_code"] <= 0)

    print(f"\n[url_checker] Summary:")
    print(f"  ✅ Active (2xx):    {ok}")
    print(f"  ⚠️  Redirected:      {redirects}")
    print(f"  ❌ Dead (4xx/5xx):  {errors}")
    print(f"  ⏱️  Unreachable:     {unreachable}")
    print(f"\n[url_checker] Report: {out_path}")


if __name__ == "__main__":
    main()
