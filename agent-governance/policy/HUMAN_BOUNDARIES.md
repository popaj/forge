# Human judgment boundaries

Machines are good at checking; they are not good at deciding what is worth
doing, or what is safe in the real world. This file draws that line
explicitly so an agent never has to judge where the boundary is.

## A. Hard boundaries (never — not even "approved")

1. **Self-authorization.** Do not change the guardrails (`policy/**`,
   `.github/**`, `scripts/**`, `AGENTS.md`, `POLICY.md`, `SECURITY.md`,
   `.github/CODEOWNERS`) in the same change as the code being governed.
   This is enforced two ways: the path-trigger list below, and G8's
   independent diff-vs-manifest cross-check, which exists precisely because
   an agent could otherwise just leave the guardrail file out of its
   declared `files` list.
2. **Protected history.** Do not push to protected branches, force-push,
   rewrite published commits, or edit an existing line of `audit/log.jsonl`
   — entries are hash-chained specifically so an edit is detectable, not
   merely disallowed.
3. **Credentials.** Do not read, copy, print, or commit real credentials;
   do not send repository contents to external systems.
4. **Irreversible real-world operations.** No production deploys, no
   destructive data operations, no money movement, no mass deletion.
5. **External communication.** Do not send email, messages, or third-party
   API calls on the human's behalf.
6. **Check integrity.** Do not weaken, disable, or skip a gate to make a
   change pass; do not record evidence that was not observed.
7. **Self-approval.** Do not write your own name, a placeholder, or a
   computed hash into `human_approval` / `approval_ref` fields. Approval
   must reference an actual external review that CI resolves independently
   — if you can fill the field in yourself without anyone else acting,
   it isn't approval.
8. **Personal data.** Do not process personal data beyond what the task
   requires; stop and ask.

## B. Approval-required triggers (tier T3 + external `approval_ref`)

**Path triggers** — any of these in the change's `files`:

`policy/**`, `.github/**`, `scripts/**`, `AGENTS.md`, `POLICY.md`,
`SECURITY.md`, `.github/CODEOWNERS`

**Topic triggers** — any of these in the change:

- adding or removing a dependency with a security surface (network, native
  code, auth/identity, process execution)
- a breaking change to a public API, CLI, data format, or schema
- a data migration or persistence-format change
- changes to auth/authz or secrets handling
- changes to which checks run or how they are interpreted (meta changes)
- any action with external side effects (deploy, publish, message, spend)

**Derived trigger** — `scripts/classify_diff.py` scores the actual diff
above the tier the manifest declares. This includes cases where the
filename doesn't match a path rule but the diff's *content* does (e.g. a
security-relevant identifier moved to an unguarded path) — the classifier's
content check exists for exactly this evasion.

## C. What agents may do autonomously

Tier T0–T2 changes that touch only project code, tests, and documentation,
pass every declared gate including G8, and trigger nothing above.

## Escalation protocol (what STOP looks like)

1. Stop editing the affected area.
2. Keep the work on a feature branch; do not commit it to a protected ref.
3. Finish the manifest: `human_approval.required = true`, the boundary hit
   (path, topic, or classifier score), and the specific decision needed.
4. Ask the human in the session — one clear question with the context
   needed to answer it.
5. Do not route around: re-scoping, renaming, or moving files to dodge a
   trigger is itself a boundary violation, and is one of the specific
   behaviors `classify_diff.py`'s content check was added to catch.

## Examples

**Agent adds a database migration that drops a column.**
→ Topic trigger (irreversible data operation, T3). STOP: manifest with
`required: true`, reason "irreversible schema change", and the question
"should I proceed with a staged migration (add column, backfill, drop in a
follow-up)?"

**Agent renames `auth/login.py` to `misc/login.py` while editing it,
hoping the path rule for `auth/**` won't match `misc/**`.**
→ The content check in `classify_diff.py` greps the diff body for
auth-related identifiers regardless of the new path, and derives T3 anyway.
The manifest under-classifies; G8 fails. This is not a false positive to
argue around — it is the mechanism working.

**Agent computes the exact diff hash for an L3 change and writes its own
name into the approval field.**
→ Hard boundary A7. `approval_ref` must point to an actual external review;
a self-supplied hash or name is not approval, and the CI-side resolution
step (which the agent's sandbox cannot reach) will not find a matching
record.

**Agent is asked to "quickly tweak the CI to skip the flaky job."**
→ `.github/**` is a guardrail path and a meta change. STOP; propose the
change as its own T3 change with an external approver, and ask.

**Agent is asked to fix a typo in POLICY.md.**
→ Guardrail path. Even a typo fix is T3: separate change, external
approval, policy version bumped (patch), CHANGELOG entry.
