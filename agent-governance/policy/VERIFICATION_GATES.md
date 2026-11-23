# Verification gates

Every change declares which gates it satisfies (`gates` in the manifest)
and records evidence per gate (`gate_evidence`). A tier defines the
**minimum** gates; a change may declare more, never fewer.

**Evidence format:** `exact command(s)` + `observed result` (exit code,
counts, or a stable excerpt of output). `scripts/policy_check.py` rejects
evidence that doesn't look like this shape, and specifically rejects the
unfilled template placeholder text.

## G0 — Hygiene

- Lint/format for the touched languages
- No build artifacts, editor files, or unintended generated files
- Line endings and encoding per `.gitattributes`

Evidence example: `python3 -m ruff check . -> All checks passed`

## G1 — Correctness

- The full existing test suite passes
- New behavior has new tests; edge cases are named in the manifest
- No test was deleted or weakened without justification in the manifest

Evidence example: `python3 -m pytest -> 42 passed in 3.1s`

## G2 — Security

- Secret scan clean: `python3 scripts/secret_scan.py .`
- Dependency posture: no new dependencies, or a named justification (a
  security-surface dependency forces T3 via the topic trigger)
- A one-paragraph threat note for any new input, external call, or
  privilege

## G3 — Maintainability

- No copy-paste duplication of logic
- No unexplained deep nesting or 50+ line functions
- Dead code introduced by the change is removed

## G4 — Documentation

- Public behavior change → docs/CHANGELOG updated in the **same** change
- No stale doc left that contradicts the new behavior

## G5 — Reproducibility

- Every verification command runs on a clean clone with only the
  documented toolchain (bash + python3 stdlib; `classify_diff.py` and
  `policy_check.py` have zero third-party dependencies)
- No environment-dependent behavior in code under test or in the checks
  themselves

## G6 — Auditability

- The manifest is committed in the **same commit** as the change
- The `audit/log.jsonl` entry matches the manifest exactly and its
  `prev_hash` correctly chains to the prior entry
- The CHANGELOG references the manifest id (tier T1+)

## G7 — Independent verifiability

A party with zero context from the authoring session can, from a clean
clone:

1. Run `bash scripts/validate.sh` → exit 0
2. Re-run every command in the manifest's Verification section
3. Match each `gate_evidence` entry against the observed output

If any of this requires trusting the author instead of observing a result,
G7 fails.

## G8 — Diff-faithfulness *(new)*

The property the other seven gates all quietly assume: that the manifest is
actually describing the diff it claims to describe.

- `scripts/classify_diff.py` reads risk rules from the **base/merge
  commit**, never the diff's own working tree copy — a diff cannot loosen
  the rules it is judged against.
- It computes `git diff --name-only <base> <head>` and requires this set to
  equal the manifest's `files` field exactly. A file touched but not
  declared, or declared but not touched, fails.
- It derives a risk tier from path rules **and** a content grep over the
  diff body (auth/crypto/secrets-related identifiers, dependency-lock
  files, workflow/CI syntax) so that moving a sensitive file to an
  unmatched path does not silently lower its classification.
- The manifest's declared `risk_tier` must be at least the derived tier.
  Understating it is a hard failure, not a warning.
- For T3, the recorded `approval_ref` must be an external identifier (PR
  number, ticket URL) that a CI-side step — run with credentials the
  agent's sandbox does not hold — resolves against an actual reviewer.
  Locally, `validate.sh` can only confirm the field is present and
  well-formed; it explicitly reports that full resolution happens in CI,
  rather than claiming a green local run means approval is real.

Evidence example:
`python3 scripts/classify_diff.py --base a1b2c3d --head HEAD -> derived T1, declared T1, files match, disposition PASSED`
