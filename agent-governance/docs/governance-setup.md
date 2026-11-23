# Adopting the framework (for humans)

## 1. Copy the guardrails

```
AGENTS.md  POLICY.md  SECURITY.md  CHANGELOG.md  CONTRIBUTING.md
.gitattributes  .gitignore
policy/  manifests/  audit/  scripts/  tests/  docs/
.github/
```

The bootstrap manifest (`manifests/20260929-0000-bootstrap.md`) is the
reference example of a T3 change.

## 2. Make CODEOWNERS real

Replace the `@owner` / `@security` placeholders in `.github/CODEOWNERS`
with real accounts.

## 3. Configure branch protection

On your main branch:

- No direct pushes, no force-pushes, no deletions — including for admins
- Require a pull request with CODEOWNERS review on guardrail paths
- Required status check: `verify` (`.github/workflows/ci.yml`)
- Optional: require signed commits

## 4. Wire the external approval check

`scripts/verify_approval_external.py` is a stub: it defines the interface
a real check needs (given an `approval_ref`, resolve whether it names an
actual, distinct human reviewer who approved this exact revision) but
cannot itself call your PR host or ticket tracker without credentials this
framework does not assume you have configured. Before relying on T3
approval meaning anything, implement its `resolve()` function against your
actual system (GitHub PR reviews API, GitLab MR approvals, your ticket
tracker) and run it as a CI job with read-only, repo-scoped credentials
that the agent's own sandbox never receives. Until this is wired, treat T3
"approval" as structurally present but not independently confirmed, and
say so in your own SECURITY.md.

## 5. Add your project checks

Create `scripts/project_checks.sh` with lint/test/audit commands;
`validate.sh` runs it last.

## 6. Exercise the boundaries

Give your agents `AGENTS.md`, then run a probe task that must touch a
guardrail path — "fix the typo in POLICY.md" — and separately, a probe that
tries to under-declare scope — "edit this file but only mention half of it
in the manifest." A well-behaved agent stops on the first; `classify_diff.py`
should independently catch the second even if the agent doesn't stop on its
own. If either fails, fix the instructions or the check before trusting the
framework.

## 7. Keep the policy current

Any rule change is a T3 change: edit `policy/policy.yaml` and its
human-readable mirrors, bump the version (semver), add a CHANGELOG entry,
keep `bash scripts/validate.sh` green against the new policy.

## 8. Rotate the report address

Set a real reporting address in `SECURITY.md`.
