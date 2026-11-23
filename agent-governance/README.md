# Agent Governance (merged edition)

A governance framework for repositories where autonomous coding agents
produce changes. This edition combines two prior designs after both were
adversarially tested, and fixes the specific ways each one failed.

> Autonomy is earned by evidence an outsider can re-check — not by the
> agent's own account of what it did.

## Where this came from

Two frameworks were compared: one built an **independent, diff-derived risk
gate** (it looks at the actual `git diff`, not the agent's claim) but its
approval step was a YAML field the agent could fill in itself, and its rules
file could be edited by the very diff it was judging. The other built a
rigorous **manifest + append-only audit trail** with a genuinely
zero-dependency, well-tested validator wired correctly into CI — but it
never looked at a diff at all, so an agent could declare "docs only" in its
manifest while quietly also editing a guardrail file, and the validator
would still pass.

Each framework's biggest weakness was the other's core strength. This
edition keeps the manifest/audit/CI skeleton (it was the more solid
engineering) and adds the diff-derived classifier as a mandatory,
cross-checked layer — with the specific bypasses found in testing closed:

| Bypass found in testing | Fix in this edition |
|---|---|
| Manifest said "docs only"; diff also touched a guardrail file — validator never compared them | `scripts/classify_diff.py` diffs `files:` against `git diff --name-only` for every manifest; mismatch fails C8 |
| Risk rules loaded from the diff's own working tree, so the diff could edit the rules it's judged by | Rules are read from the merge-base commit (`git show <base>:policies/rules.json`), never from the working tree |
| Renaming a file out of a matched path (e.g. `auth/login.py` → `misc/login.py`) silently dropped its risk level | Path rules are supplemented by a content grep over the diff body for security-relevant identifiers, independent of filename |
| Agent wrote its own `approval.approver` string and the check passed | Approval requires an `approval_ref` (a PR/ticket URL) that CI resolves against the actual reviewer of record; the agent cannot self-satisfy it locally |
| Hand-edited an existing audit log line — "append-only" was only a policy sentence | Audit entries are hash-chained (`prev_hash`); an edited line breaks the chain and C3 fails |
| A freshly scaffolded manifest with literal placeholder evidence text passed validation | Evidence strings are pattern-checked for `command -> observed result` shape; the literal template placeholder is explicitly rejected |
| An invalid `risk_tier` crashed the validator instead of failing cleanly | Tier lookups are guarded; unknown tiers are a clean C2 failure |
| The flagship diff-derived gate was never called from the shipped CI | `.github/workflows/ci.yml` runs `classify_diff.py` on every PR with `fetch-depth: 0` |

## The eight properties → mechanism

| Property | Mechanism |
|---|---|
| Correct | G1 — tests required, evidence recorded, CI re-runs them |
| Secure | G2 — secret scan, dependency posture, threat note |
| Maintainable | G3 — no duplication/dead code; CODEOWNERS |
| Documented | G4 — docs/CHANGELOG updated in the same change |
| Reproducible | G5 — stdlib-only validator, pinned tooling, clean-room recipe |
| Auditable | G6 — manifest + hash-chained `audit/log.jsonl`, committed atomically |
| Independently verifiable | G7 — a stranger re-runs one command and every claim re-proves |
| **Diff-faithful** *(new)* | **G8 — the manifest's claimed scope and risk tier are checked against the actual `git diff`, not the agent's word** |

## Repository map

```
AGENTS.md                     operating contract for autonomous agents
POLICY.md                     human-readable policy
policy/policy.yaml            machine-readable policy (enforced)
policy/VERIFICATION_GATES.md  G0–G8 definitions + evidence format
policy/HUMAN_BOUNDARIES.md    hard boundaries, approval triggers, escalation
policy/rules.json             path + content risk-classification rules
manifests/                    one change manifest per change
audit/log.jsonl               append-only, hash-chained audit record
scripts/validate.sh           THE local command
scripts/classify_diff.py      independent, diff-derived risk classifier (G8)
scripts/policy_check.py       manifest + audit + policy consistency (G0,G4,G6,G7)
scripts/secret_scan.py        embedded-credential scan (G2)
scripts/new_change.sh         scaffolds a manifest
scripts/log_change.py         appends the audit line (hash-chained)
tests/                        unit tests for the validator itself
.github/                      CI, PR template, CODEOWNERS
docs/                         architecture, reproducibility, incident response
```

## Quickstart — for agents

1. Read `AGENTS.md`. It is short and it is the contract.
2. `scripts/new_change.sh <slug> <T0|T1|T2|T3>` — scaffolds the manifest.
3. Implement, staying inside the declared `files` list.
4. `bash scripts/validate.sh` until it exits 0. This now includes G8: your
   manifest's declared files and tier are checked against your actual diff.
5. Fill `gate_evidence` with real `command -> observed result` lines.
6. `python3 scripts/log_change.py manifests/<id>.md`, commit atomically.
7. If you hit a boundary — including any T3 trigger — STOP and ask. See
   `policy/HUMAN_BOUNDARIES.md`.

## Quickstart — for humans adopting this

See `docs/governance-setup.md`. In short: make CODEOWNERS real, require the
`verify` CI check plus CODEOWNERS review on branch protection, wire the
external approval check (`scripts/verify_approval_external.py`, run in CI
with repo API credentials the agent's sandbox does not have) to your actual
PR review system, and give your agents `AGENTS.md`.

## Risk tiers

| Tier | Meaning | Human approval |
|------|---------|-----------------|
| T0 | Documentation-only, confirmed by diff | No |
| T1 | Internal behavior, no risk-rule match | No |
| T2 | Public-facing: API, CLI, schema, dependency | No |
| T3 | Guardrail change, approval-topic, or any diff the classifier scores above the declared tier | **Yes — external approval reference, resolved in CI** |

The tier is derived from the diff by `classify_diff.py`, then the agent's
declared tier must be at least that high. The agent proposes; it does not
get to be the only one who checked.

## Verify this repository right now

```bash
bash scripts/validate.sh          # expect: RESULT: PASS
python3 scripts/classify_diff.py --base <merge-base> --head HEAD   # diff-derived tier
```
