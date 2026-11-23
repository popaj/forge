# Reproducible, independent verification

## The contract

Any party — a human reviewer, a second agent with **no context** from the
authoring session, or CI on another machine — can verify the governance
claims of this repository from a clean clone using only:

- `bash`
- `python3` >= 3.9 (standard library only — no pip installs, no network)
- `git`

## Clean-room recipe

```bash
git clone <repo-url> && cd <repo>
python3 --version
bash scripts/validate.sh
python3 scripts/classify_diff.py --base <merge-base-of-change> --head <change-commit> \
  --manifest manifests/<id>.md
python3 -m unittest discover -s tests
```

## Why it is reproducible

- **No third-party code.** `policy_check.py`, `classify_diff.py`, and
  `secret_scan.py` are all stdlib-only. There is no supply chain below git
  and the OS Python, and no lockfile to pin.
- **No network, no environment-dependent inputs.** Every check is a pure
  function of repository content at specific revisions.
- **The rule cannot mark its own homework.** `classify_diff.py` reads
  `policy/rules.json` from the base commit via `git show`, never from the
  working tree of the diff being judged — this is the specific property
  that closes the "diff edits its own rules" bypass found in an earlier
  design.
- **Deterministic order.** Files are walked in sorted order.
- **CI is data.** `.github/workflows/ci.yml` is a plain file anyone can
  read.

## What full G8 verification requires that a clean clone alone cannot give

Locally, `validate.sh` can confirm a manifest is internally well-formed and
even run `classify_diff.py` against the last commit's parent — but it
cannot resolve whether a claimed `approval_ref` corresponds to a real
review, because that requires reading an external system (your PR host,
your ticket tracker) with credentials a local clone or an agent's sandbox
does not have. This is intentional, not a gap to close locally: if a local
run *could* fully verify approval, an agent running locally could forge it.
The CI job that runs `scripts/verify_approval_external.py` with
repo-scoped, read-only credentials is the actual approval gate; treat a
green `validate.sh` alone as "structurally complete," not as "approved."

## Pinning the pipeline (optional, stronger)

Version tags (`actions/checkout@v4`) can move. Resolve the tag to a commit
and pin the SHA. Do this as a T3 guardrail change with an external
approver.

## Verification of the verifier

`tests/` contains unit tests for the restricted-YAML parser, the manifest
checks, the audit hash chain, and the diff classifier (including its
rename-evasion content check). A fix to any of these is itself a guardrail
change (T3).
