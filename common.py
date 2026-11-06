"""Reading a downloaded snapshot. Shared by download.py and build_site.py."""
import gzip
import json
from pathlib import Path

REVIEW_SUFFIX = "/-/Official_Review"


def page_paths(snapshot_dir):
    return sorted(Path(snapshot_dir).glob("page_*.json.gz"))


def read_page(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def iter_notes(snapshot_dir):
    """Yield each submission once, keeping the first copy if pages overlap."""
    seen = set()
    for path in page_paths(snapshot_dir):
        for note in read_page(path):
            if note["id"] not in seen:
                seen.add(note["id"])
                yield note


def value(field):
    """OpenReview v2 wraps content fields as {"value": x}."""
    return field.get("value") if isinstance(field, dict) else field


def reviews_of(note):
    """Return the official reviews among a submission's direct replies."""
    found = {}
    for reply in (note.get("details") or {}).get("directReplies") or []:
        if reply.get("ddate"):
            continue
        if any(i.endswith(REVIEW_SUFFIX) for i in reply.get("invitations") or []):
            found[reply["id"]] = reply
    return list(found.values())
