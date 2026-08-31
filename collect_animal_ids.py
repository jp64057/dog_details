#!/usr/bin/env python3
"""Collect adoptable dog Animal IDs from Maricopa County Animal Care & Control.

Iterates the public AnimalGrid endpoint page by page, extracts every
``ShowDetailsForAnimal('<AnimalID>')`` reference, de-duplicates, and writes the
IDs (one per line) to an output file.

Re-runnable: just run it again to refresh the list. Uses only the Python
standard library (no third-party dependencies).

Examples:
    python3 collect_animal_ids.py
    python3 collect_animal_ids.py --output all_ids.txt
    python3 collect_animal_ids.py --animal-type Dog --max-pages 50
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.parse
import urllib.request

BASE_URL = "https://apps.pets.maricopa.gov/adoptPets/Home/AnimalGrid"
ENV = "https://apps.pets.maricopa.gov/adoptPets"

# Matches ShowDetailsForAnimal('A5167431') and grabs the ID.
ID_RE = re.compile(r"ShowDetailsForAnimal\(['\"]([A-Z0-9]+)['\"]\)")
# The result header renders e.g. "<svg .../> 515 Found".
COUNT_RE = re.compile(r"([0-9,]+)\s+Found", re.IGNORECASE)


def build_url(page: int, animal_type: str) -> str:
    """Build the AnimalGrid URL for a given page number."""
    params = {
        "sizeFilter": "1",
        "ageFilter": "1",
        "genderFilter": "1",
        "pageNumber": str(page),
        "animalId": "",
        "animalName": "",
        "kennelNum": "",
        "env": ENV,
        "fosterEligible": "false",
        "shelterFilter": "All",
        "animalTypeFilter": animal_type,
        "isLongTimer": "false",
        "isReadyToday": "false",
        "breedFilter": "Any Breed",
    }
    return f"{BASE_URL}?{urllib.parse.urlencode(params)}"


def fetch(url: str, timeout: int, retries: int = 3) -> str:
    """GET a URL and return the response body as text, with simple retries."""
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
                return resp.read().decode("utf-8", errors="replace")
        except Exception as err:  # network hiccup -> back off and retry
            last_err = err
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_err}")


def collect(animal_type: str, max_pages: int, delay: float, timeout: int) -> list[str]:
    """Iterate pages until one returns no IDs (or max_pages), collecting IDs in order."""
    seen: set[str] = set()
    ordered: list[str] = []
    reported_total: int | None = None

    for page in range(1, max_pages + 1):
        html = fetch(build_url(page, animal_type), timeout=timeout)

        if reported_total is None:
            m = COUNT_RE.search(html)
            if m:
                reported_total = int(m.group(1).replace(",", ""))
                print(f"Header reports {reported_total} found", file=sys.stderr)

        ids = ID_RE.findall(html)
        if not ids:
            print(f"Page {page}: 0 IDs -> stopping.", file=sys.stderr)
            break

        new = 0
        for aid in ids:
            if aid not in seen:
                seen.add(aid)
                ordered.append(aid)
                new += 1
        print(f"Page {page}: {len(ids)} IDs ({new} new) | running total {len(ordered)}",
              file=sys.stderr)

        if delay:
            time.sleep(delay)
    else:
        print(f"Reached max-pages ({max_pages}); there may be more.", file=sys.stderr)

    if reported_total is not None and len(ordered) != reported_total:
        print(f"Note: collected {len(ordered)} displayed cards vs header count "
              f"{reported_total} (some animals may not be publicly listed).",
              file=sys.stderr)
    return ordered


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-o", "--output", default="all_ids.txt",
                   help="File to write IDs to, one per line (default: all_ids.txt). "
                        "Use '-' for stdout.")
    p.add_argument("--animal-type", default="All",
                   help="animalTypeFilter value, e.g. 'All' or 'Dog' (default: All). "
                        "The grid currently returns only dogs.")
    p.add_argument("--max-pages", type=int, default=100,
                   help="Safety cap on pages to fetch (default: 100).")
    p.add_argument("--delay", type=float, default=0.2,
                   help="Seconds to sleep between page requests (default: 0.2).")
    p.add_argument("--timeout", type=int, default=30,
                   help="Per-request timeout in seconds (default: 30).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ids = collect(args.animal_type, args.max_pages, args.delay, args.timeout)

    if args.output == "-":
        sys.stdout.write("\n".join(ids) + ("\n" if ids else ""))
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(ids) + ("\n" if ids else ""))
        print(f"Wrote {len(ids)} Animal IDs to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
