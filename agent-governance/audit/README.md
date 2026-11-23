# Audit log

`audit/log.jsonl` is the append-only, hash-chained machine record of
changes. One JSON object per line:

| field | meaning |
|---|---|
| `schema` | format version (currently `2`) |
| `id` | manifest id (unique, one entry per change) |
| `ts` | ISO-8601 time the entry was appended (non-decreasing) |
| `author` | `agent:<n>` or `human:<n>` |
| `risk_tier` | T0–T3, must match the manifest |
| `gates` | must match the manifest |
| `files` | must match the manifest |
| `commit` | `null` at append time; the git history ties the entry to its commit |
| `prev_hash` | `entry_hash` of the previous line, or 64 zeros for the first entry |
| `entry_hash` | `sha256(prev_hash + canonical_json(entry_without_entry_hash))` |

**Why hash-chained, not just "append-only" by policy.** A prior design in
this framework's history stated the log was append-only but had nothing
stopping a hand-edited line from passing validation — the rule existed only
in prose. Chaining `entry_hash` through `prev_hash` means editing,
reordering, or deleting any past line breaks the hash of every entry after
it, and `scripts/policy_check.py` (check C3) recomputes and verifies the
whole chain on every run. "Append-only" is now something the validator can
actually catch a violation of.

**Integrity rules enforced by `policy_check` (C3):**

- valid JSON per line, well-formed fields, unique ids, non-decreasing
  timestamps
- every `prev_hash` equals the previous line's `entry_hash`
- every `entry_hash` matches a fresh recomputation from that line's own
  content
- every manifest has a matching entry with identical tier, gates, and files

**The log is never rewritten.** Corrections happen as new changes (reverts
are changes too), and a human decides. Editing a line is now both a hard
boundary violation *and* a mechanically detectable one.

`audit/last-validation.json` (gitignored) is a transient report written by
`scripts/validate.sh`, not part of the audit trail.
