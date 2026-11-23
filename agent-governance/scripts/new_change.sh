#!/usr/bin/env bash
# new_change.sh — scaffold a change manifest.
#
# Usage:
#   scripts/new_change.sh <slug> <T0|T1|T2|T3> [author-name] [agent|human]
#
# Creates manifests/<YYYYMMDD-HHMM>-<slug>.md from the tier's required
# gates (read live from policy/policy.yaml). Do NOT append the audit line
# yet — finalize the manifest first, then run:
#   python3 scripts/log_change.py manifests/<id>.md
# and before that, for anything above T0/T1, run:
#   python3 scripts/classify_diff.py --base <merge-base> --head HEAD --manifest manifests/<id>.md
# to confirm your declared tier and files actually match your diff.
set -euo pipefail
cd "$(dirname "$0")/.."

slug="${1:?usage: new_change.sh <slug> <T0|T1|T2|T3> [author-name] [agent|human]}"
tier="${2:?missing tier: T0|T1|T2|T3}"
author_name="${3:-agent:unspecified}"
author_type="${4:-agent}"

case "$tier" in
  T0|T1|T2|T3) ;;
  *) echo "error: tier must be T0, T1, T2, or T3" >&2; exit 2 ;;
esac
case "$author_type" in
  agent|human) ;;
  *) echo "error: author type must be 'agent' or 'human'" >&2; exit 2 ;;
esac

ts="$(date +%Y%m%d-%H%M)"
slug_lc="$(printf '%s' "$slug" | tr '[:upper:]' '[:lower:]' | sed -e 's/[^a-z0-9]\{1,\}/-/g' -e 's/^-//' -e 's/-$//')"
id="${ts}-${slug_lc}"
path="manifests/${id}.md"

if [ -e "$path" ]; then
  echo "error: manifest already exists: $path" >&2
  exit 1
fi

required_gates="$(python3 - "$tier" <<'PY'
import sys
sys.path.insert(0, "scripts")
from policy_check import parse_yaml_subset
policy = parse_yaml_subset(open("policy/policy.yaml", encoding="utf-8").read())
for t in policy["risk_tiers"]:
    if t["id"] == sys.argv[1]:
        print(" ".join(t["gates"]))
        break
PY
)"

gates_json=""
evidence_json=""
nl=$'\n'
for g in $required_gates; do
  if [ -n "$gates_json" ]; then
    gates_json="${gates_json},"
    evidence_json="${evidence_json},${nl}"
  fi
  gates_json="${gates_json}\"${g}\""
  evidence_json="${evidence_json}  \"${g}\": \"TODO: exact command -> observed result\""
done

date_field="$(date +%Y-%m-%d)"
approval_required="false"
trigger_note=""
if [ "$tier" = "T3" ]; then
  approval_required="true"
  trigger_note='
## Human approval (REQUIRED for T3)
- Boundary hit (path or topic): TODO — cite the trigger from policy/HUMAN_BOUNDARIES.md
- Decision needed from the human: TODO
- Approval reference (PR/ticket URL resolved externally in CI — NOT a
  self-written name): TODO
'
fi

cat > "$path" <<EOF
\`\`\`json
{
  "id": "${id}",
  "date": "${date_field}",
  "title": "TODO: short imperative title",
  "author": { "type": "${author_type}", "name": "${author_name}", "model": null },
  "risk_tier": "${tier}",
  "human_approval": { "required": ${approval_required}, "reason": "TODO: boundary ref if required, else empty string", "approval_ref": "TODO: external PR/ticket URL, only after real review; leave empty until T3 approval is genuinely in place" },
  "gates": [${gates_json}],
  "gate_evidence": {
${evidence_json}
  },
  "files": [],
  "rollback": "TODO: how to undo, including any side effects"
}
\`\`\`

# TODO: title

## Summary
What changes, in two or three sentences.

## TODO before finalize
- Set title, files (every file this change touches, except this manifest
  and audit/log.jsonl), and gate_evidence (exact commands + observed
  results — not the placeholder text above) in the meta block.
- Run: python3 scripts/classify_diff.py --base <merge-base> --head HEAD
  --manifest ${path}
  and confirm it reports "passed" before finalizing.
- For T3: fill human_approval and get the actual external approval_ref
  first.

## Why
Motivation and alternatives considered.

## Verification
Exact commands run, with observed exit codes:

\`\`\`bash
bash scripts/validate.sh
python3 scripts/classify_diff.py --base <merge-base> --head HEAD --manifest ${path}
# TODO: project-specific commands
\`\`\`

## Independent verification
A reviewer with zero context can verify by:
1. \`git checkout\` of this change
2. \`bash scripts/validate.sh\` → must exit 0
3. \`python3 scripts/classify_diff.py --base <merge-base> --head <this commit> --manifest ${path}\` → must report "passed"
4. re-running every command in "Verification" above
5. matching each \`gate_evidence\` entry against the observed output
${trigger_note}
## Rollback
How to undo this change, including side effects (data, external systems).
EOF

echo "created $path"
echo "next: implement, verify (bash scripts/validate.sh), classify (scripts/classify_diff.py),"
echo "finalize the meta block, then: python3 scripts/log_change.py $path"
