# Changelog

All notable changes to this repository are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).
Every tier T1+ change must reference its manifest id here (enforced by
`policy_check`, C4).

## [Unreleased]

## [0.1.0] - 2026-09-29

### Added
- Merged agent governance framework combining a manifest/audit-trail design
  with an independent, diff-derived risk classifier (gate G8).
- Risk tiers T0–T3, verification gates G0–G8, per-change manifests, a
  hash-chained append-only audit log, and a zero-dependency validator
  (`bash scripts/validate.sh`).
- `scripts/classify_diff.py`: derives risk tier from the actual `git diff`
  using rules read from the base commit (not the diff's own working tree),
  supplemented by a content-level grep so relocating a sensitive file to an
  unmatched path does not silently lower its classification. Cross-checks
  the manifest's declared `files` against the real diff.
- External approval references (`approval_ref`) replacing self-written
  approver fields for T3 changes.
- Hash-chained `audit/log.jsonl` entries so an edited or reordered line is
  detectable, not just disallowed.
- Explicit human judgment boundaries: hard "never" list, approval-required
  triggers, and the STOP/escalation protocol.
- CI pipeline that runs the diff classifier on every PR with full history,
  PR template, and CODEOWNERS placeholders for guardrail paths.

(manifest: 20260929-0000-bootstrap)
