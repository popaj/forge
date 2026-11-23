## Change record (required)

- Manifest: `manifests/<id>.md`
- Risk tier declared: T0 | T1 | T2 | T3
- Risk tier derived by `classify_diff.py` (paste its output): T0 | T1 | T2 | T3
- `bash scripts/validate.sh` → exit 0 (paste the RESULT line)
- Guardrail paths touched (if any — must be a separate T3 change): yes / no

## Human judgment

- [ ] No human approval required
- [ ] Human approval required
  - Boundary hit (path or topic, per policy/HUMAN_BOUNDARIES.md):
  - `approval_ref` (external PR/ticket URL — not a self-written name):

## Verification (a stranger can follow this)

Commands a reviewer with zero context can run to re-verify this change:

```bash
bash scripts/validate.sh
python3 scripts/classify_diff.py --base <merge-base> --head <this commit> --manifest manifests/<id>.md
# project-specific commands:
```

## Rollback

How to undo this change, including side effects.
