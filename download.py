#!/usr/bin/env python3
"""Download one snapshot of all ICLR submissions with their reviews.

All submissions and reviews come from one paginated query, so a snapshot costs about
one request per 1000 submissions and never one request per paper. Each page is saved
as it arrives. If a run stops, running the script again continues from the next page.

Output goes to snapshots/<UTC time>/, which is git-ignored because it holds review text.

The client reads OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD from the environment if
they are set, and is anonymous otherwise.
"""
import argparse
import gzip
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from common import iter_notes, reviews_of, value

API_URL = "https://api2.openreview.net"
DEFAULT_VENUE = "ICLR.cc/2027/Conference"
PAGE_SIZE = 1000  # the API maximum
PAUSE_SECONDS = 1.0


def make_client():
    import openreview

    return openreview.api.OpenReviewClient(baseurl=API_URL)


def write_atomic(path, data, compress=False):
    tmp = path.with_name(path.name + ".tmp")
    opener = gzip.open if compress else open
    with opener(tmp, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def unfinished_snapshot(out_dir, venue):
    """Return the newest snapshot of this venue that has progress but no manifest."""
    for path in sorted(out_dir.glob("*/progress.json"), reverse=True):
        if (path.parent / "manifest.json").exists():
            continue
        if json.loads(path.read_text())["venue"] == venue:
            return path.parent
    return None


def fetch_pages(client, snapshot_dir, venue, page_size, pause):
    """Fetch pages from the saved position to the end. Returns the expected total."""
    progress_path = snapshot_dir / "progress.json"
    progress = json.loads(progress_path.read_text())
    query = dict(
        invitation=f"{venue}/-/Submission",
        details="directReplies",
        sort="number:asc",
        limit=page_size,
    )
    while True:
        offset, total = progress["offset"], progress["total"]
        if total is not None and offset >= total:
            return total
        if total is None:
            # The client returns the total only on a request without an offset.
            notes, total = client.get_notes(with_count=True, **query)
        else:
            notes = client.get_notes(offset=offset, **query)
        if not notes:
            return total
        rows = [{**n.to_json(), "number": n.number, "details": n.details} for n in notes]
        write_atomic(snapshot_dir / f"page_{offset:07d}.json.gz", rows, compress=True)
        progress.update(offset=offset + len(notes), total=total)
        write_atomic(progress_path, progress)
        print(f"  {progress['offset']:>6} / {total} submissions", flush=True)
        if progress["offset"] < total:
            time.sleep(pause)


def write_manifest(snapshot_dir, venue, total, taken_at=None):
    """Check the saved pages against the API total and record the result."""
    venues, ratings = Counter(), Counter()
    notes = reviews = with_reviews = 0
    for note in iter_notes(snapshot_dir):
        notes += 1
        venues[value(note["content"].get("venueid")) or "unknown"] += 1
        found = reviews_of(note)
        reviews += len(found)
        with_reviews += bool(found)
        for review in found:
            ratings[str(value(review["content"].get("rating")))] += 1
    manifest = {
        "venue": venue,
        "taken_at": (taken_at or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "api_total": total,
        "submissions": notes,
        "complete": notes == total and reviews > 0,
        "submissions_with_reviews": with_reviews,
        "reviews": reviews,
        "by_venueid": dict(venues),
        "ratings": dict(sorted(ratings.items())),
    }
    write_atomic(snapshot_dir / "manifest.json", manifest)
    return manifest


def main(argv=None, client_factory=make_client, pause=PAUSE_SECONDS):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--venue", default=DEFAULT_VENUE)
    parser.add_argument("--out", type=Path, default=Path("snapshots"))
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    parser.add_argument("--new", action="store_true",
                        help="start a new snapshot instead of continuing an unfinished one")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    snapshot_dir = None if args.new else unfinished_snapshot(args.out, args.venue)
    if snapshot_dir:
        print(f"Continuing {snapshot_dir}")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
        snapshot_dir = args.out / stamp
        snapshot_dir.mkdir()
        write_atomic(snapshot_dir / "progress.json",
                     {"venue": args.venue, "offset": 0, "total": None})
        print(f"Starting {snapshot_dir}")

    client = client_factory()
    try:
        total = fetch_pages(client, snapshot_dir, args.venue, args.page_size, pause)
    except Exception as error:
        if "ChallengeRequiredError" not in str(error):
            raise
        print(f"\nOpenReview refused the request:\n{error}\n"
              "Saved pages are kept. Run this script again to continue.", file=sys.stderr)
        return 2

    manifest = write_manifest(snapshot_dir, args.venue, total)
    print(json.dumps({k: v for k, v in manifest.items() if k != "ratings"}, indent=2))
    if not manifest["complete"]:
        print(f"WARNING: incomplete snapshot: {manifest['submissions']} of {total} "
              f"submissions, {manifest['reviews']} reviews.", file=sys.stderr)
        return 1
    print(f"Saved {snapshot_dir}. Next: python build_site.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
