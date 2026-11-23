# Contributing

For **humans**. Autonomous agents follow `AGENTS.md` instead.

## The one rule

Every change ships with a manifest and passes `bash scripts/validate.sh`
plus `scripts/classify_diff.py` against its own diff. There is no "small
change" exemption — tier T0 exists for documentation-only changes and
still gets the full record, still gets checked against the actual diff.

## Process

1. Read `POLICY.md`.
2. Classify the risk tier and check the triggers
   (`policy/HUMAN_BOUNDARIES.md`).
3. Branch, scaffold a manifest (`scripts/new_change.sh <slug> <tier>`),
   implement, verify, run
   `python3 scripts/classify_diff.py --base <merge-base> --head HEAD
   --manifest manifests/<id>.md` and confirm it passes, then record the
   audit line (`python3 scripts/log_change.py manifests/<id>.md`).
4. Open a pull request with the template; it mirrors the manifest.
5. Guardrail paths (`policy/`, `.github/`, `scripts/`, `AGENTS.md`,
   `POLICY.md`, `SECURITY.md`, CODEOWNERS) require review from the owners
   in `.github/CODEOWNERS`, must be separate changes from the code they
   govern, and their T3 approval must be a real `approval_ref` — your own
   PR-author approval of your own PR does not satisfy this; that's what
   the external CI-side resolution step checks for.

## Conventions

- **Commit:** `type(scope): summary [manifest: <id>]`
- **CHANGELOG:** entry referencing the manifest id for every T1+ change
- **Policy version:** bump in `policy/policy.yaml` on any policy change,
  with a CHANGELOG entry under the new version

## Good first contributions

- Clarifications to docs (T0)
- New unit tests for the validator or classifier (T1)
- Extending `tests/` coverage of the manifest workflow (T1)
