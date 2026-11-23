# Change manifests

One manifest per change, committed in the **same commit** as the change.
The manifest is the change's claims made checkable — and, since gate G8,
made checkable *against the actual diff*, not just against itself.

- **Naming:** `YYYYMMDD-HHMM-slug.md`; the manifest `id` equals the
  filename without `.md`.
- **Scaffold:** `scripts/new_change.sh <slug> <T0|T1|T2|T3>` — generates
  from the tier's required gates read live from `policy/policy.yaml`.
- **Machine block:** the first fenced block must be ```json and must be
  valid JSON; `scripts/policy_check.py` parses it, and
  `scripts/classify_diff.py` cross-checks its `files` and `risk_tier`
  fields against `git diff`.
- **`files` field:** every file the change touches, except the manifest
  itself and `audit/log.jsonl`. This must now equal the actual diff's
  changed-paths set exactly — G8 fails on either a file touched but not
  declared, or declared but not touched.
- **`gate_evidence`:** one non-empty string per declared gate, shaped like
  `command -> observed result`. The literal scaffold placeholder text is
  explicitly rejected by `policy_check`.
- **`human_approval.approval_ref`:** for T3, an external PR or ticket
  reference — never a self-written approver name or a self-computed hash.
  CI resolves this against the actual review system with credentials the
  agent's own sandbox does not have.
- **Immutability:** do not edit a manifest after its commit. If the change
  evolves, make a new manifest whose Summary references the old id.
- **Audit:** finalize the manifest, then
  `python3 scripts/log_change.py manifests/<id>.md` appends the matching,
  hash-chained line to `audit/log.jsonl`.

## Required meta fields

| field | meaning |
|---|---|
| `id` | `YYYYMMDD-HHMM-slug`, must equal the filename |
| `date` | `YYYY-MM-DD` |
| `title` | short imperative title |
| `author` | `{type: agent\|human, name, model}` — agents name their model |
| `risk_tier` | `T0`–`T3` — a proposal; `classify_diff.py` is authoritative |
| `human_approval` | `{required, reason, approval_ref}` — external ref required for T3 |
| `gates` | declared gates (must include the tier minimum) |
| `gate_evidence` | per-gate evidence strings, shaped like real evidence |
| `files` | changed files (relative paths) — must equal the actual diff |
| `rollback` | how to undo, including side effects |
