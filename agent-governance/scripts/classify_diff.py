#!/usr/bin/env python3
"""classify_diff.py — independent, diff-derived risk classification (gate G8).

Stdlib only (Python >= 3.9) + git on PATH.

    python3 scripts/classify_diff.py --base <rev> --head <rev> [--manifest manifests/<id>.md]

This exists to close two specific bypasses found in prior designs:

1. A manifest can declare "docs only" while the diff also touches a
   guardrail file, and nothing checks the two against each other. Here,
   the changed-paths set from `git diff` is compared against the
   manifest's declared `files` field; any mismatch is a hard failure.

2. A diff can edit the risk rules it is about to be judged by (e.g.
   loosen a path pattern, or remove a path from `protected_paths`) and,
   if the classifier reads rules from the diff's own working tree, pass
   under its own loosened rules. Here, `policy/rules.json` is always read
   from the BASE revision via `git show <base>:policy/rules.json`, never
   from the working tree — a diff cannot soften the ruler it is measured
   against.

Path rules alone can be evaded by moving a sensitive file to an unmatched
path while keeping its content unchanged (a "rename evasion"). This is
mitigated, not eliminated, by also grepping the added/modified lines of
the diff for content patterns (`content_rules` in rules.json) regardless
of which file they land in.

Exit codes: 0 = derived tier <= declared tier and files match (or no
manifest given), 1 = mismatch or under-classification, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}


def git(args, cwd=None):
    """Run git in `cwd`, defaulting to the current working directory.

    Deliberately NOT hardcoded to this script's own repo location: the
    caller (a human, CI, or a test harness pointed at a disposable repo)
    is responsible for running this from the repository root being judged.
    """
    p = subprocess.run(["git", *args], cwd=cwd or os.getcwd(), text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), p.stderr.strip()))
    return p.stdout


def load_rules_from_base(base):
    """Read policy/rules.json as it existed at `base`, not the working tree."""
    try:
        text = git(["show", "%s:policy/rules.json" % base])
    except RuntimeError as e:
        raise SystemExit("cannot read policy/rules.json at base %r: %s" % (base, e))
    return json.loads(text)


def changed_paths(base, head):
    out = git(["diff", "--name-only", base, head])
    return sorted(x for x in out.splitlines() if x)


def diff_added_lines(base, head):
    """Yield (path, added-line-text) for every '+' line in the diff, excluding
    the '+++' file headers."""
    raw = git(["diff", "--unified=0", base, head])
    current = None
    for line in raw.splitlines():
        if line.startswith("+++ "):
            p = line[4:]
            current = p[2:] if p.startswith("b/") else p
            continue
        if line.startswith("+") and not line.startswith("+++"):
            yield current, line[1:]


def derive_tier(paths, base, head, rules):
    level = "T0"
    dimensions = set()
    reasons = []

    def bump(new_level, path, dim):
        nonlocal level
        dimensions.add(dim)
        if TIER_ORDER[new_level] > TIER_ORDER[level]:
            level = new_level
        reasons.append("%s: %s -> %s" % (path, dim, new_level))

    for path in paths:
        for rule in rules.get("path_rules", []):
            if re.search(rule["pattern"], path):
                bump(rule["level"], path, rule["dimension"])
        for protected in rules.get("protected_paths", []):
            if path == protected or path.startswith(protected):
                bump(rules["protected_path_level"], path, "governance_control")

    # Content signal: independent of which path a matching line lands in,
    # so moving a file does not by itself lower the score.
    content_rules = [(cr["dimension"], cr["level"], re.compile(cr["pattern"]))
                      for cr in rules.get("content_rules", [])]
    if content_rules:
        for path, text in diff_added_lines(base, head):
            for dim, lvl, rx in content_rules:
                if rx.search(text):
                    bump(lvl, path or "(unknown path)", dim + " (content)")

    if level == "T0" and any(
        not (p.endswith((".md", ".txt", ".rst"))) for p in paths
    ):
        bump("T1", "(non-doc path present)", "semantic_change")

    return level, sorted(dimensions), reasons


def load_manifest_meta(path):
    text = open(path, encoding="utf-8").read()
    m = re.match(r"^\s*```json[ \t]*\n(.*?)\n```", text, re.S)
    if not m:
        raise SystemExit("%s: must begin with a ```json meta block" % path)
    return json.loads(m.group(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--manifest", help="manifests/<id>.md to cross-check; optional")
    args = ap.parse_args()

    rules = load_rules_from_base(args.base)
    paths = changed_paths(args.base, args.head)
    derived, dimensions, reasons = derive_tier(paths, args.base, args.head, rules)

    result = {
        "base": args.base,
        "head": args.head,
        "changed_paths": paths,
        "derived_tier": derived,
        "risk_dimensions": dimensions,
        "reasons": reasons,
        "disposition": "passed",
        "errors": [],
    }

    if args.manifest:
        meta = load_manifest_meta(args.manifest)
        declared = meta.get("risk_tier")
        manifest_files = sorted(meta.get("files", []))
        result["declared_tier"] = declared
        result["manifest_files"] = manifest_files

        if declared not in TIER_ORDER:
            result["errors"].append("invalid or missing declared risk_tier: %r" % declared)
        elif TIER_ORDER[declared] < TIER_ORDER[derived]:
            result["errors"].append(
                "manifest under-classifies: declared %s, derived %s (%s)"
                % (declared, derived, "; ".join(reasons) or "no specific rule, but non-doc files present"))

        if manifest_files != paths:
            missing = set(paths) - set(manifest_files)
            extra = set(manifest_files) - set(paths)
            if missing:
                result["errors"].append("files changed but not declared in manifest: %s" % sorted(missing))
            if extra:
                result["errors"].append("files declared but not actually changed: %s" % sorted(extra))

        if derived in ("T3",):
            approval = meta.get("human_approval", {}) or {}
            ref = approval.get("approval_ref")
            if not (isinstance(ref, str) and ref.strip()):
                result["errors"].append(
                    "T3 change requires human_approval.approval_ref (external PR/ticket "
                    "reference) — a self-written approver name/hash is not accepted")

    if result["errors"]:
        result["disposition"] = "rejected"

    print(json.dumps(result, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
