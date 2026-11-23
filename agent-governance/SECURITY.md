# Security policy

## Reporting a vulnerability

Report to `security@example.com` — **replace with a real address before
adopting this framework.** Do not open a public issue for a suspected
vulnerability.

## Scope

- This framework: `scripts/`, `policy/`, `.github/`.
- Projects that adopt it: the adopted guardrail layer plus
  `scripts/project_checks.sh`.

## Ground rules (for everyone — agents included)

- Real credentials never appear in the repository, manifests, audit log,
  or pull requests. `scripts/secret_scan.py` runs on every verification.
- CI needs no credentials for the governance checks themselves and no
  network access for them. The external-approval resolution step
  (`scripts/verify_approval_external.py`) is the one exception: it needs
  read access to your PR/ticket system, scoped as narrowly as possible,
  and must run as a CI job the agent's own sandbox cannot reach — that
  separation is what makes G8's approval check meaningful rather than
  cosmetic.
- A flaw in the guardrails — for example, a way to make `classify_diff.py`
  under-score a diff, or a way to forge an `approval_ref` — is a **P1**:
  it is a hole in what "verified" means. Report it; do not self-approve a
  fix. Guardrail fixes are T3 changes with an external approver, same as
  any other guardrail change.
- Agents specifically: do not attempt to test the boundaries of these
  checks against a real repository's production branch. If you want to
  verify the checks catch something, do it on a disposable branch/clone
  and say so in the manifest.

## Response targets

Acknowledgement: 72 hours. Mitigation plan: 14 days. (Adjust for your
organization; the targets are policy, so changing them is a T3 change.)
