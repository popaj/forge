# Incident response

If an autonomous change is suspected to have caused harm:

1. Stop further automated rollout.
2. Preserve logs, revisions, manifests, and `audit/log.jsonl` — do not let
   an agent "clean up" any of these while attempting remediation; the
   hash chain will show if it tries.
3. Identify the affected revision and scope from the manifest's `files`
   field, cross-checked against `git diff` — do not trust the manifest
   alone if there's any doubt; re-run `classify_diff.py` against the
   actual commit.
4. Use the documented rollback path from the manifest, where authorized.
5. Assess whether credentials or sensitive data were exposed.
6. Escalate according to the deploying organization's incident process.
7. Record the root cause and control improvement as its own T3 change if
   it touches the guardrails.

Do not allow an agent to edit `audit/log.jsonl` while attempting
remediation, even with good intentions — a correction is a new entry, and
the chain will detect an edit to an old one either way.
