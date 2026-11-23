```json
{
  "id": "YYYYMMDD-HHMM-slug",
  "date": "YYYY-MM-DD",
  "title": "Short imperative title",
  "author": { "type": "agent", "name": "agent-id", "model": "model + version (null for human)" },
  "risk_tier": "T1",
  "human_approval": { "required": false, "reason": "", "approval_ref": "" },
  "gates": ["G0", "G1", "G4", "G6", "G7", "G8"],
  "gate_evidence": {
    "G0": "EXACT COMMAND -> OBSERVED RESULT",
    "G1": "EXACT COMMAND -> OBSERVED RESULT",
    "G4": "EXACT COMMAND -> OBSERVED RESULT",
    "G6": "EXACT COMMAND -> OBSERVED RESULT",
    "G7": "EXACT COMMAND -> OBSERVED RESULT",
    "G8": "EXACT COMMAND -> OBSERVED RESULT"
  },
  "files": ["path/changed/by/this/change.md"],
  "rollback": "revert the commit; no side effects"
}
```

# Short imperative title

## Summary
What changes, in two or three sentences.

## Why
Motivation and alternatives considered.

## Verification
Exact commands run, with observed exit codes:

```bash
bash scripts/validate.sh
python3 scripts/classify_diff.py --base <merge-base> --head <this commit> --manifest manifests/<id>.md
# project-specific commands
```

## Independent verification
A reviewer with zero context can verify by:
1. `git checkout` of this change
2. `bash scripts/validate.sh` → must exit 0
3. `python3 scripts/classify_diff.py --base <merge-base> --head <this commit> --manifest manifests/<id>.md` → must report "passed"
4. re-running every command in "Verification" above
5. matching each `gate_evidence` entry against the observed output

## Human approval
- Required: no — (for T3: boundary ref — path or topic from
  policy/HUMAN_BOUNDARIES.md; `approval_ref` must be an external PR/ticket
  URL, never a self-written name)
- Approval reference: — (URL, resolved by CI against the actual reviewer)

## Rollback
How to undo this change, including side effects (data, external systems).
