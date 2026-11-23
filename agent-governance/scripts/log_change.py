#!/usr/bin/env python3
"""log_change.py — append the hash-chained audit log entry for a manifest.

Stdlib only. Usage:

    python3 scripts/log_change.py manifests/<id>.md [commit-sha]

Each entry embeds `prev_hash` (the entry_hash of the previous line, or 64
zeros for the first entry) and `entry_hash` (sha256 of prev_hash + this
entry's canonical JSON, entry_hash field excluded). This makes the
append-only invariant something `policy_check.py` can actually detect a
violation of, rather than a rule stated in prose: editing, reordering, or
deleting any past line breaks every entry_hash after it.

Refuses to append a duplicate id — one change, one entry.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from policy_check import _load_meta  # noqa: E402

AUDIT_REL = os.path.join("audit", "log.jsonl")
GENESIS_HASH = "0" * 64


def _last_hash():
    if not os.path.isfile(AUDIT_REL):
        return GENESIS_HASH
    last = GENESIS_HASH
    with open(AUDIT_REL, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = json.loads(line).get("entry_hash", last)
    return last


def main(argv):
    if len(argv) < 2:
        print("usage: log_change.py <manifest.md> [commit-sha]", file=sys.stderr)
        return 2
    mpath = argv[1]
    sha = argv[2] if len(argv) > 2 else None

    with open(mpath, "r", encoding="utf-8") as f:
        text = f.read()
    meta, err = _load_meta(text)
    if meta is None:
        print("manifest error: %s" % err, file=sys.stderr)
        return 1

    prev_hash = _last_hash()
    entry = {
        "schema": 2,
        "id": meta["id"],
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "author": "%s:%s" % (meta["author"]["type"], meta["author"]["name"]),
        "risk_tier": meta["risk_tier"],
        "gates": sorted(meta["gates"]),
        "files": sorted(meta["files"]),
        "commit": sha,
        "prev_hash": prev_hash,
    }
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    entry["entry_hash"] = hashlib.sha256((prev_hash + canonical).encode()).hexdigest()

    if os.path.isfile(AUDIT_REL):
        with open(AUDIT_REL, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() and json.loads(line).get("id") == entry["id"]:
                    print("audit entry for %s already exists — the log is append-only; "
                          "make a new manifest if the change evolved" % entry["id"],
                          file=sys.stderr)
                    return 1

    os.makedirs(os.path.dirname(AUDIT_REL), exist_ok=True)
    with open(AUDIT_REL, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    print("appended audit entry for %s (entry_hash=%s...)" % (entry["id"], entry["entry_hash"][:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
