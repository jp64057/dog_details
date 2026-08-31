#!/usr/bin/env python3
"""Download per-animal detail pages for Maricopa County ACC dogs.

Reads Animal IDs (one per line, as produced by ``collect_animal_ids.py``) and
downloads each animal's full detail page from ``/Home/Details/<AnimalID>`` into a
local cache directory. The huge inline base64 photos are stripped on the fly so
each cached file stays small.

Re-runnable: already-downloaded IDs are skipped unless ``--force`` is given.
Uses only the Python standard library (no third-party dependencies).

Pipeline:
    python3 collect_animal_ids.py            # -> all_ids.txt
    python3 fetch_details.py                 # all_ids.txt -> details/*.html
    python3 parse_dogs.py                    # details/*.html -> dogs_data.json
    python3 build_outputs.py                 # dogs_data.json -> md / txt

Examples:
    python3 fetch_details.py
    python3 fetch_details.py --input all_ids.txt --out-dir details --workers 8
    python3 fetch_details.py --force
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

DETAIL_URL = "https://apps.pets.maricopa.gov/adoptPets/Home/Details/{animal_id}"

# Strip `data:image/...;base64,....` blobs (up to the closing quote) to keep files small.
B64_RE = re.compile(r'data:image/[a-zA-Z]+;base64,[^"\']*')


def read_ids(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        ids = [line.strip() for line in f if line.strip()]
    # de-dupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for aid in ids:
        if aid not in seen:
            seen.add(aid)
            out.append(aid)
    return out


def fetch_one(animal_id: str, out_dir: str, timeout: int, retries: int,
              force: bool) -> tuple[str, str]:
    """Download and cache one detail page. Returns (animal_id, status)."""
    out_path = os.path.join(out_dir, f"{animal_id}.html")
    if not force and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return animal_id, "skip"

    url = DETAIL_URL.format(animal_id=animal_id)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; dog-details/1.0)",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            html = B64_RE.sub("[B64]", html)
            if not html.strip():
                raise RuntimeError("empty response")
            # atomic-ish write
            tmp = out_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(html)
            os.replace(tmp, out_path)
            return animal_id, "ok"
        except Exception as err:
            last_err = err
            if attempt < retries:
                time.sleep(1.5 * attempt)
    return animal_id, f"FAIL: {last_err}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-i", "--input", default="all_ids.txt",
                   help="File of Animal IDs, one per line (default: all_ids.txt).")
    p.add_argument("-d", "--out-dir", default="details",
                   help="Directory to write cached detail pages to (default: details).")
    p.add_argument("--workers", type=int, default=8,
                   help="Concurrent download workers (default: 8).")
    p.add_argument("--timeout", type=int, default=30,
                   help="Per-request timeout in seconds (default: 30).")
    p.add_argument("--retries", type=int, default=3,
                   help="Retries per animal on failure (default: 3).")
    p.add_argument("--force", action="store_true",
                   help="Re-download even if a cached file already exists.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not os.path.exists(args.input):
        print(f"Input file not found: {args.input}\n"
              f"Run collect_animal_ids.py first.", file=sys.stderr)
        return 1

    ids = read_ids(args.input)
    if not ids:
        print(f"No Animal IDs found in {args.input}", file=sys.stderr)
        return 1

    os.makedirs(args.out_dir, exist_ok=True)
    print(f"Fetching {len(ids)} detail pages into {args.out_dir}/ "
          f"with {args.workers} workers...", file=sys.stderr)

    counts = {"ok": 0, "skip": 0, "fail": 0}
    failures: list[str] = []
    done = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(fetch_one, aid, args.out_dir, args.timeout,
                        args.retries, args.force): aid
            for aid in ids
        }
        for fut in as_completed(futures):
            aid, status = fut.result()
            done += 1
            if status == "ok":
                counts["ok"] += 1
            elif status == "skip":
                counts["skip"] += 1
            else:
                counts["fail"] += 1
                failures.append(aid)
                print(f"  {aid}: {status}", file=sys.stderr)
            if done % 50 == 0 or done == len(ids):
                print(f"  progress {done}/{len(ids)} "
                      f"(ok={counts['ok']} skip={counts['skip']} fail={counts['fail']})",
                      file=sys.stderr)

    print(f"Done. downloaded={counts['ok']} skipped={counts['skip']} "
          f"failed={counts['fail']}", file=sys.stderr)
    if failures:
        print("Failed IDs: " + ", ".join(failures), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
