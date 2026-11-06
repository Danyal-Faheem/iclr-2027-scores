#!/usr/bin/env python3
"""Turn API pages saved by hand into a snapshot that build_site.py can read.

Expects files in notes/, each the JSON body of one /notes response. The snapshot is
marked complete only if the files hold every submission exactly once.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from download import DEFAULT_VENUE, write_atomic, write_manifest


def natural_key(path):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", path.name)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--notes", type=Path, default=Path("notes"))
    parser.add_argument("--out", type=Path, default=Path("snapshots"))
    parser.add_argument("--venue", default=DEFAULT_VENUE)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args(argv)

    files = sorted(args.notes.glob("*.json"), key=natural_key)
    if not files:
        print(f"No JSON files in {args.notes}", file=sys.stderr)
        return 1

    pages, hashes, owners, totals = [], defaultdict(list), defaultdict(list), set()
    for path in files:
        data = path.read_bytes()
        hashes[hashlib.sha256(data).hexdigest()].append(path.name)
        page = json.loads(data)
        totals.add(page["count"])
        for note in page["notes"]:
            owners[note["id"]].append(path.name)
        pages.append(page["notes"])

    problems = [f"identical files: {', '.join(v)}" for v in hashes.values() if len(v) > 1]
    repeated = sum(len(v) > 1 for v in owners.values())
    if repeated:
        problems.append(f"{repeated} submissions appear in more than one file")
    if len(totals) != 1:
        problems.append(f"files disagree on the total: {sorted(totals)}")
    total = max(totals)
    if len(owners) != total:
        problems.append(f"{len(owners)} unique submissions, expected {total}")
    for problem in problems:
        print(f"PROBLEM: {problem}", file=sys.stderr)
    if problems and not args.allow_incomplete:
        print("Nothing imported.", file=sys.stderr)
        return 1

    newest = max(path.stat().st_mtime for path in files)
    taken_at = datetime.fromtimestamp(newest, timezone.utc)
    snapshot_dir = args.out / taken_at.strftime("%Y-%m-%dT%H%MZ")
    snapshot_dir.mkdir(parents=True)
    for index, notes in enumerate(pages):
        write_atomic(snapshot_dir / f"page_{index:07d}.json.gz", notes, compress=True)
    manifest = write_manifest(snapshot_dir, args.venue, total, taken_at)
    print(json.dumps({k: v for k, v in manifest.items() if k != "ratings"}, indent=2))
    print(f"Saved {snapshot_dir}. Next: python build_site.py")
    return 0 if manifest["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
