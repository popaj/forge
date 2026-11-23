# POLICY.md — Governance policy (v0.1.0)

Policy version **0.1.0**, kept in sync with `policy/policy.yaml`. If the two
ever disagree, the machine form (`policy/policy.yaml`, enforced by
`scripts/policy_check.py` and `scripts/classify_diff.py`) wins, and the
discrepancy is itself a bug to report.

## Principles

- **P1 — Evidence over confidence.** A claim is only as good as the command
  that re-proves it.
- **P2 — Named boundaries.** Where a machine cannot judge, the line is
  written down in advance. Agents never have to decide where the boundary
  is.
- **P3 — Guardrails are human-owned.** Policy, CI, check scripts, and
  ownership rules change only through human-approved T3 changes, and never
  in the same change as the code they govern.
- **P4 — Least autonomy.** Default is the lowest tier that fits; crossing a
  trigger escalates, it never contracts, and the agent's own tier proposal
  is never the ceiling — the diff-derived tier is.
- **P5 — Stopping is success.** An agent that hits a boundary and stops
  with a clear question has done its job correctly.
- **P6 — Stranger-verifiability.** If verifying a change requires trusting
  the author instead of observing a result, the change is not done.
- **P7 — The classifier outranks the author.** *(new)* A risk tier or scope
  declared by the agent is a proposal. `scripts/classify_diff.py` derives
  the authoritative tier from the actual diff, using rules read from the
  base commit so the diff being judged cannot edit the ruler it's measured
  against. A manifest that understates the derived tier fails validation,
  full stop — this is not something a later manifest revision can talk its
  way around.
- **P8 — Approval is external.** *(new)* A human-approval field the agent
  itself can write is not evidence of human approval; it's the agent's
  claim of it. T3 approval must reference something the agent cannot
  generate — a specific reviewer, PR, or ticket — and CI must be able to
  independently resolve that reference against the actual review system,
  with credentials the agent's own sandbox does not hold.

## Risk tiers

| Tier | Scope | Minimum gates | Human approval |
|------|-------|----------------|-----------------|
| T0 | Documentation-only, diff-confirmed | G0, G4, G6, G7, G8 | No |
| T1 | Internal behavior, no risk-rule match | T0 + G1 | No |
| T2 | Public-facing: API, CLI, data, dependency | G0–G8 | No |
| T3 | Guardrail change or approval topic, or any diff the classifier scores above the declared tier | G0–G8 | **Yes — `approval_ref`, resolved externally** |

Full gate definitions: `policy/VERIFICATION_GATES.md`.

## Verification gates (summary)

| Gate | Property it protects |
|------|----------------------|
| G0 hygiene | repository not polluted by the change |
| G1 correctness | behavior is what was intended; tests prove it |
| G2 security | no secrets, sound dependency posture, threats considered |
| G3 maintainability | no duplication, dead code, unexplained complexity |
| G4 documentation | docs, CHANGELOG, manifest stay true to behavior |
| G5 reproducibility | claims re-run on a clean clone with pinned tools |
| G6 auditability | manifest + hash-chained audit log, committed atomically |
| G7 independent verifiability | a stranger re-proves every claim without trust |
| **G8 diff-faithfulness** | the manifest's `files` and `risk_tier` match the *actual* diff, judged by rules the diff cannot itself edit |

## Human judgment boundaries (summary)

- **Hard boundaries (never, even "approved"):** self-authorization,
  protected-branch or history manipulation, real credentials, irreversible
  real-world operations, external communication, weakening or faking
  checks, self-written approval fields, personal-data processing beyond
  the task.
- **Approval-required triggers (force T3 + external `approval_ref`):** any
  guardrail path, or any approval topic (security-surface dependencies,
  breaking public changes, data migrations, auth/secrets handling, meta
  changes to the checks themselves, external side effects) — or simply
  scoring above the declared tier under `classify_diff.py`.
- **Agent autonomy:** T0–T2 changes, confirmed by the diff, triggering
  nothing.

Full rules, escalation protocol, and worked examples:
`policy/HUMAN_BOUNDARIES.md`.

## Self-authorization rule

No change may both (a) modify the guardrails and (b) modify the code those
guardrails govern — checked twice: by the path-trigger list, and
independently by G8's diff-vs-manifest cross-check, which catches an agent
that simply omits a guardrail file from its declared `files` list.

## Changing this policy

Changing policy is itself a T3 change, human-driven:

1. A human proposes the edit as its own change, not bundled with anything
   else.
2. The change lists every affected manifest/gate convention.
3. Bump `policy/policy.yaml`'s version (semver).
4. Add a CHANGELOG entry under the new version.
5. `bash scripts/validate.sh` must pass against the *new* policy before
   merge, and `classify_diff.py`'s rules for the change to policy files
   themselves must correctly score this as T3 (tested in
   `tests/test_classify_diff.py`).
