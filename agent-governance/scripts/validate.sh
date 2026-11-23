#!/usr/bin/env bash
# validate.sh — THE command: verify the governance layer of this repository.
#
# Zero third-party dependencies: bash + python3 (>= 3.9, stdlib only) + git.
# No network. Any human or agent, from a clean clone, can re-verify every
# claim a change manifest makes by running this script.
#
# Exit 0 = all steps pass, 1 = at least one step failed.
set -uo pipefail
cd "$(dirname "$0")/.."

POLICY_VERSION="$(sed -n 's/^version:[[:space:]]*//p' policy/policy.yaml 2>/dev/null | head -1)"
echo "validate.sh — governance verification (policy v${POLICY_VERSION:-unknown})"
echo "python3 $(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"

FAILED=0
step() {
  local name="$1"
  shift
  echo
  echo "== $name =="
  if "$@"; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"
    FAILED=1
  fi
}

step "policy-check"  python3 scripts/policy_check.py
step "secret-scan"   python3 scripts/secret_scan.py .

if [ -d tests ] && ls tests/test_*.py >/dev/null 2>&1; then
  step "validator-tests" python3 -m unittest discover -s tests -t .
fi

step "shell-syntax" bash -n scripts/validate.sh scripts/new_change.sh

# G8, best effort, locally: if we're in a git repo with more than one
# commit, classify the most recent commit's diff against any manifest it
# introduced. This is a convenience check for local development; the
# authoritative run happens in CI, where --base is the actual PR base and
# cannot be spoofed by checking out a different local branch.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && git rev-parse HEAD~1 >/dev/null 2>&1; then
  new_manifest="$(git diff --name-only --diff-filter=A HEAD~1 HEAD -- manifests/ | grep -v -e README.md -e TEMPLATE.md | head -1 || true)"
  if [ -n "${new_manifest:-}" ]; then
    step "diff-faithfulness (G8, local, base=HEAD~1)" \
      python3 scripts/classify_diff.py --base HEAD~1 --head HEAD --manifest "$new_manifest"
  else
    echo
    echo "== diff-faithfulness (G8) =="
    echo "no new manifest in HEAD~1..HEAD; skipping locally (CI runs this against the real PR base for every change)"
  fi
else
  echo
  echo "== diff-faithfulness (G8) =="
  echo "not enough git history for a local check; CI runs this against the real PR base for every change"
fi

# Project-specific lint/test/audit commands live here (created by the
# adopting project as a human-approved guardrail change).
if [ -f scripts/project_checks.sh ]; then
  step "project-checks" bash scripts/project_checks.sh
fi

echo
if [ "$FAILED" -eq 0 ]; then
  echo "RESULT: PASS — governance layer verified."
else
  echo "RESULT: FAIL — see FAIL lines above."
fi

python3 - "$FAILED" > audit/last-validation.json <<'PY'
import datetime, json, sys
print(json.dumps({
    "schema": 1,
    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "command": "bash scripts/validate.sh",
    "passed": sys.argv[1] == "0",
}, indent=2))
PY

exit "$FAILED"
