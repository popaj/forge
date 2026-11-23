# AGENTS.md — Operating contract for autonomous agents

This binds every autonomous agent making changes in this repository: LLM
coding agents, CI agents, and humans driving automation. Human contributors
not driving automation should read `CONTRIBUTING.md` instead.

Read `POLICY.md` before your first change. The enforced form is
`policy/policy.yaml` plus `scripts/policy_check.py` and
`scripts/classify_diff.py`.

## The workflow (every change, no exceptions)

1. **Classify.** Propose a risk tier: T0 documentation-only, T1 internal
   behavior, T2 public-facing, T3 boundary-crossing. Your proposal is not
   the final word — `scripts/classify_diff.py` independently derives a tier
   from your actual diff and rejects a manifest that understates it.
2. **Check triggers** in `policy/HUMAN_BOUNDARIES.md` before you touch
   anything. If any file you plan to touch is a guardrail path
   (`policy/**`, `.github/**`, `scripts/**`, `AGENTS.md`, `POLICY.md`,
   `SECURITY.md`, `.github/CODEOWNERS`) or the change hits an approval
   topic — **STOP** (see below) before writing code, not after.
3. **Scaffold.** `scripts/new_change.sh <slug> <tier>` creates
   `manifests/<id>.md`.
4. **Implement.** Stay inside the declared `files` list. If you find you
   need to touch something outside it, stop and re-scope the manifest
   first — do not silently expand scope and fix the manifest afterward.
5. **Verify.** `bash scripts/validate.sh` must exit 0. This includes G8: it
   compares your manifest's `files` and `risk_tier` against your actual
   `git diff`, using risk rules read from the base commit — not from your
   own diff, so you cannot loosen the rules in the same change that needs
   them loosened. Record *observed* evidence per gate: exact command plus
   the actual result. A string like "passed" with no command is not
   evidence, and the literal words "EXACT COMMANDS + OBSERVED RESULT" from
   the template will be rejected — that placeholder means you haven't
   filled it in yet.
6. **Record.** Finalize the manifest, then
   `python3 scripts/log_change.py manifests/<id>.md`.
7. **Commit atomically.** Code + manifest + audit line + CHANGELOG entry in
   one commit: `type(scope): summary [manifest: <id>]`.

A change is done only when 5–7 are complete and a party with zero context —
human or a second agent — can re-run everything without asking you a single
question or trusting a single claim you made (G7).

## STOP conditions (hard boundaries)

Stop and ask a human when:

- the change touches a guardrail path or approval topic (step 2);
- `classify_diff.py` derives a tier higher than the one you declared —
  this is not a bug to work around, it is the gate doing its job;
- anything is irreversible or has an external side effect (deploy, data
  deletion, money, third-party communication);
- real credentials, personal data, or production systems are involved;
- you would have to weaken, skip, or re-scope a check to make something
  pass.

When you STOP:

1. Do not commit the affected work to a protected ref.
2. Finish the manifest with `human_approval.required = true`, the specific
   boundary hit, and the exact decision needed.
3. Ask the human in the session. Do not guess, do not assume consent, and
   do not route around the boundary — moving a sensitive file to an
   unmatched path to dodge a rule is itself a boundary violation, and the
   content-level check in `classify_diff.py` exists specifically to catch
   this.

## Rules that admit no exception

- **Self-authorization is forbidden.** Never change the guardrails in the
  same change as the code they govern. This is checked two ways now, not
  one: the path-trigger list, and G8's diff cross-check against the
  manifest — the second exists because the first can be evaded by an
  agent that simply doesn't list the guardrail file in its manifest.
- **No fabricated evidence.** Never record a gate as passed unless it
  actually ran and you observed the result.
- **No self-approval.** You cannot satisfy a T3 approval requirement by
  writing your own name, a placeholder, or a computed hash into the
  manifest. Approval requires `approval_ref` pointing to an actual
  external review, checked by CI using credentials your sandbox does not
  have. If you find yourself computing a diff hash to paste into an
  approval field, stop — that is exactly the move this rule exists to
  block.
- **No history manipulation.** No force-push, no rewriting published
  commits, no editing or deleting an audit log line. The log is
  hash-chained specifically so an edited line is detectable, not just
  disallowed by policy.
- **No external actions.** No email, no third-party APIs, no deploys, no
  spending. The repository is the sandbox; the outside world is a human
  decision.

## Evidence over assertions

Your final response should point to evidence, not describe your confidence
in it: files changed, exact commands run, their actual output, known
limitations, and any required human decision. "This is secure" or "this is
correct" is not evidence; a command and its exit code is.

## Definition of done

A change is complete only when acceptance criteria are met, gates pass,
docs are updated where needed, the manifest and audit entry are complete
and hash-chain correctly, G8's diff cross-check passes, and every required
human gate — approved through an external reference, not a self-written
field — is satisfied.
