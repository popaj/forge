#!/usr/bin/env python3
"""verify_approval_external.py — STUB. Resolve a T3 manifest's approval_ref
against your actual review system. This is what makes G8's approval
requirement real rather than cosmetic; without it wired up, a manifest's
`approval_ref` is checked only for presence and shape, not for correctness.

Why this is not implemented against a real API here: doing so requires
credentials and an endpoint specific to your organization (GitHub PR
reviews, GitLab MR approvals, a ticket tracker's API, etc.), which this
framework cannot assume. Implement `resolve()` below against your system,
then run this script as its own CI job with read-only, repo-scoped
credentials that the agent's own sandbox never receives — that separation,
not the code here, is what prevents an agent from self-approving.

    python3 scripts/verify_approval_external.py manifests/<id>.md

Exit codes: 0 = approval_ref resolves to a valid, distinct human approval
for this exact revision; 1 = it does not; 2 = not implemented / usage error.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from policy_check import _load_meta  # noqa: E402


def resolve(approval_ref: str, manifest_meta: dict) -> tuple[bool, str]:
    """Replace this with a real call to your PR host or ticket tracker.

    Must confirm, independently of anything the manifest itself claims:
      - approval_ref identifies a real, specific review record
      - the reviewer is not the same identity as the manifest's author
      - the review was granted against this exact revision/diff, not an
        earlier or later one
      - the reviewer had the authority to approve a guardrail change

    Returning True here without actually implementing those checks makes
    the T3 approval gate purely decorative. Until this is implemented,
    this function intentionally always returns False so that unimplemented
    approval verification fails closed rather than silently passing.
    """
    return False, (
        "verify_approval_external.py is a stub and has not been wired to a "
        "real review system; T3 approval cannot be independently confirmed "
        "yet. See docs/governance-setup.md step 4."
    )


def main(argv):
    if len(argv) != 2:
        print("usage: verify_approval_external.py <manifest.md>", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        meta, err = _load_meta(f.read())
    if meta is None:
        print("manifest error: %s" % err, file=sys.stderr)
        return 2

    approval = meta.get("human_approval", {}) or {}
    ref = approval.get("approval_ref", "")
    if not (isinstance(ref, str) and ref.strip()):
        print("no approval_ref present")
        return 1

    ok, detail = resolve(ref, meta)
    print(detail)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
