# Architecture

## Three-principal model

**Agent.** Proposes and implements changes in an isolated workspace. It has
authority to edit; it does not have authority to approve its own risk
classification, fabricate evidence, or satisfy its own approval
requirement.

**Independent verifier.** Two scripts, deliberately separate from the
agent's own narrative:

- `scripts/policy_check.py` checks that the manifest and audit log are
  internally well-formed and consistent with each other and with policy.
- `scripts/classify_diff.py` checks that the manifest is consistent with
  reality — the actual `git diff` — using risk rules read from the base
  commit, not from the diff being judged. This split exists because the
  first kind of check, alone, can be satisfied by a manifest that is
  perfectly well-formed and simply untrue about what was changed.

**Human authority.** Resolves what cannot be reduced to policy and
mechanical evidence, and is the only party who can satisfy a T3 approval —
through an external `approval_ref` that CI resolves with credentials the
agent's sandbox does not hold, not through a field in a file the agent
itself can edit.

## Why the diff-derived check is separate from the manifest check

Two prior designs each got half of this right. One had a manifest and
audit trail that was internally rigorous but never looked at a diff, so an
agent could describe a smaller, safer change than it actually made and the
validator would still pass — nothing cross-checked the story against the
facts. The other had a diff-derived classifier, which is the right idea,
but read its own risk rules from the very diff it was judging, so a change
that wanted to be under-classified could simply edit the rules in the same
commit; and its human-approval check was satisfied by a YAML field the
agent could compute and fill in itself.

The fix is structural, not just "add more checks": `classify_diff.py` must
read its rules from a revision the diff cannot touch (the base/merge
commit), and approval must resolve against a system the agent cannot write
to (an external CI step). Anything less collapses back into the agent
grading its own homework.

## Evidence binding

A verification result is associated with:

- base and head revision;
- the actual changed-paths set (not a claimed one);
- derived risk tier and dimensions, including content-level signals;
- the manifest's declared tier and files, and whether they match;
- for T3, the approval_ref and whether it resolves.

## Fail-closed behavior

Missing or contradictory evidence is an error. An invalid or unrecognized
`risk_tier` value is a clean C2 failure, not a crash — a validator that
crashes on malformed input is itself a hole in what "verified" means.

## Enforcement boundary

`classify_diff.py` and the external approval resolution step should run in
a separate CI job or service principal from the agent's own workspace, with
permissions scoped to verification, not to the repository's write path.
