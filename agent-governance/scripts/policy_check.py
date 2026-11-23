#!/usr/bin/env python3
"""policy_check.py — verify the governance invariants of this repository.

Stdlib only (Python >= 3.9).

    python3 scripts/policy_check.py [ROOT]

Exit codes: 0 = all checks pass, 1 = one or more checks failed.

Checks (human-readable policy: POLICY.md):
  C1  policy/policy.yaml exists, parses in the restricted YAML subset, and
      defines a semver version, gates G0..G8, and tiers T0..T3
  C2  every manifest is well-formed: valid id/filename, valid tier (fails
      cleanly on an unrecognized tier rather than crashing), gates satisfy
      the tier, evidence covers declared gates and looks like real
      evidence (not the unfilled template placeholder), listed files
      exist, human-boundary triggers are respected, T3 approval uses an
      external approval_ref rather than a self-written approver field,
      matching audit entry exists
  C3  audit/log.jsonl is well-formed, unique, time-ordered, hash-chained
      (each entry's prev_hash must equal the sha256 of the previous line;
      editing a past line breaks every entry after it), and consistent
      with the manifests
  C4  tier T1+ manifests are referenced from CHANGELOG.md
  C5  required framework files exist

Note: this script checks that manifests are internally well-formed and
consistent with the audit log. It does NOT check a manifest's claims
against an actual git diff — that is gate G8, performed independently by
scripts/classify_diff.py, because a diff should not be able to satisfy
itself by simply writing a truthful-looking manifest without an outside
check against what was actually changed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime

POLICY_PATH = os.path.join("policy", "policy.yaml")
MANIFESTS_DIR = "manifests"
AUDIT_PATH = os.path.join("audit", "log.jsonl")
CHANGELOG_PATH = "CHANGELOG.md"

GATE_IDS = ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]
TIER_IDS = ["T0", "T1", "T2", "T3"]
ID_RE = re.compile(r"^\d{8}-\d{4}-[a-z0-9][a-z0-9-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Evidence must look like a command plus an observed result, and must not
# be the unfilled template placeholder. This is intentionally loose (it
# cannot verify the command was *actually* run) but it closes the specific
# bypass of leaving the scaffold's placeholder text in place.
PLACEHOLDER_EVIDENCE = "EXACT COMMANDS + OBSERVED RESULT"
EVIDENCE_SHAPE_RE = re.compile(r"(->|→|:).{2,}")

FRAMEWORK_FILES = [
    "AGENTS.md",
    "POLICY.md",
    "README.md",
    "SECURITY.md",
    "CHANGELOG.md",
    ".github/CODEOWNERS",
    ".github/workflows/ci.yml",
    "scripts/validate.sh",
    "scripts/classify_diff.py",
    "manifests/TEMPLATE.md",
    "audit/README.md",
]


def _read(root, rel):
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------------
# Restricted YAML subset (deterministic, stdlib-only, no third-party deps)
# --------------------------------------------------------------------------

def _scalar(v):
    v = v.strip()
    if v == "":
        return None
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    if v[0] in "[{":
        raise ValueError("flow collections are not supported: %r" % v)
    return v


def parse_yaml_subset(text):
    toks = []
    for raw in text.splitlines():
        if "\t" in raw:
            raise ValueError("tabs are not allowed: %r" % raw)
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        toks.append((indent, raw.strip()))
    if not toks:
        return {}

    pos = 0

    def parse_list(indent):
        nonlocal pos
        out = []
        while pos < len(toks) and toks[pos][0] == indent and toks[pos][1].startswith("- "):
            body = toks[pos][1][2:].strip()
            m = re.match(r"^([A-Za-z0-9_.-]+):(?:\s+(.*))?$", body)
            if m:
                item = {}
                cont = indent + 2
                if m.group(2) is not None:
                    item[m.group(1)] = _scalar(m.group(2))
                    pos += 1
                else:
                    item[m.group(1)] = None
                    pos += 1
                while pos < len(toks) and toks[pos][0] == cont and not toks[pos][1].startswith("- "):
                    k, sep, v2 = toks[pos][1].partition(":")
                    if not sep:
                        raise ValueError("expected 'key:' in list item: %r" % toks[pos][1])
                    v2 = v2.strip()
                    pos += 1
                    if v2:
                        item[k.strip()] = _scalar(v2)
                    elif pos < len(toks) and toks[pos][0] > cont:
                        item[k.strip()] = parse_block(toks[pos][0])
                    else:
                        item[k.strip()] = None
                out.append(item)
            else:
                out.append(_scalar(body))
                pos += 1
        return out

    def parse_map(indent):
        nonlocal pos
        out = {}
        while pos < len(toks) and toks[pos][0] == indent and not toks[pos][1].startswith("- "):
            k, sep, v = toks[pos][1].partition(":")
            if not sep:
                raise ValueError("expected 'key: value': %r" % toks[pos][1])
            v = v.strip()
            pos += 1
            if v:
                out[k.strip()] = _scalar(v)
            elif pos < len(toks) and toks[pos][0] > indent:
                out[k.strip()] = parse_block(toks[pos][0])
            else:
                out[k.strip()] = None
        return out

    def parse_block(indent):
        if toks[pos][1].startswith("- "):
            return parse_list(indent)
        return parse_map(indent)

    result = parse_block(toks[0][0])
    if pos != len(toks):
        raise ValueError("unparsed content at: %r" % (toks[pos],))
    return result


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _iso_ok(value):
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _valid_date(s):
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _load_meta(text):
    if text is None:
        return None, "manifest file missing"
    m = re.match(r"^\s*```json[ \t]*\n(.*?)\n```", text, re.S)
    if not m:
        return None, "must begin with a ```json meta block"
    try:
        meta = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        return None, "meta JSON invalid: %s" % e
    if not isinstance(meta, dict):
        return None, "meta must be a JSON object"
    return meta, None


def _seg_pattern(seg):
    return ".*".join(re.escape(p) for p in seg.split("*"))


def path_matches(path, pattern):
    segs = ["[^/]+(?:/[^/]+)*" if g == "**" else _seg_pattern(g)
            for g in pattern.split("/")]
    return re.match("^" + "/".join(segs) + "$", path) is not None


def _chain_hash(prev_hash, line_without_hash_field):
    return hashlib.sha256((prev_hash + line_without_hash_field).encode()).hexdigest()


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def _check_manifest(check, root, rel, meta, audit_by_id, changelog_text, policy, hb_paths):
    prefix = rel + ": "
    mid = meta.get("id")
    if not (isinstance(mid, str) and ID_RE.match(mid)):
        check(False, "C2", prefix + "bad id %r" % (mid,))
        mid = None
    else:
        check(os.path.basename(rel) == mid + ".md", "C2", prefix + "filename must equal id.md")

    for field in ("id", "date", "title", "author", "risk_tier", "human_approval",
                  "gates", "gate_evidence", "files", "rollback"):
        check(field in meta, "C2", prefix + "missing field %r" % field)

    date = meta.get("date")
    check(date is None or (isinstance(date, str) and DATE_RE.match(date) and _valid_date(date)),
          "C2", prefix + "date must be a valid YYYY-MM-DD")

    author = meta.get("author")
    check(isinstance(author, dict) and author.get("type") in ("agent", "human")
          and isinstance(author.get("name"), str) and author["name"].strip(),
          "C2", prefix + "author must be {type: agent|human, name: ...}")

    tier = meta.get("risk_tier")
    tier_ok = tier in TIER_IDS
    check(tier_ok, "C2", prefix + "risk_tier must be one of %s (got %r)" % (TIER_IDS, tier))

    tier_obj = None
    if tier_ok and isinstance(policy, dict) and isinstance(policy.get("risk_tiers"), list):
        for t in policy["risk_tiers"]:
            if isinstance(t, dict) and t.get("id") == tier:
                tier_obj = t
                break

    gates = meta.get("gates")
    ok_gates = isinstance(gates, list) and len(gates) == len(set(gates)) \
        and set(gates) <= set(GATE_IDS)
    check(ok_gates, "C2", prefix + "gates must be a unique subset of %s" % GATE_IDS)
    if ok_gates and tier_obj is not None and isinstance(tier_obj.get("gates"), list):
        missing = set(tier_obj["gates"]) - set(gates)
        check(not missing, "C2", prefix + "tier %s requires gates %s" % (tier, sorted(missing)))
    elif ok_gates and tier_ok and tier_obj is None:
        check(False, "C2", prefix + "risk_tier %r not found in policy/policy.yaml risk_tiers" % tier)

    evidence = meta.get("gate_evidence")
    if ok_gates:
        def _evidence_ok(g):
            v = evidence.get(g) if isinstance(evidence, dict) else None
            if not (isinstance(v, str) and v.strip()):
                return False
            if PLACEHOLDER_EVIDENCE in v:
                return False
            return bool(EVIDENCE_SHAPE_RE.search(v))
        check(isinstance(evidence, dict) and all(_evidence_ok(g) for g in gates),
              "C2", prefix + "gate_evidence must cover every declared gate with an actual "
                              "'command -> observed result' line, not the template placeholder")

    files = meta.get("files")
    ok_files = isinstance(files, list) and all(
        isinstance(f, str) and f and not os.path.isabs(f) and ".." not in f.split("/")
        for f in files)
    check(ok_files, "C2", prefix + "files must be relative paths without '..'")
    if ok_files:
        for f in files:
            check(os.path.isfile(os.path.join(root, f)), "C2", prefix + "listed file missing: %s" % f)

    triggers = []
    if ok_files:
        triggers = [p for p in hb_paths if any(path_matches(f, p) for f in files)]

    ha = meta.get("human_approval")
    ha = ha if isinstance(ha, dict) else {}
    needs_t3 = bool(triggers) or (
        tier_obj is not None and tier_obj.get("requires_human_approval") is True)
    if needs_t3:
        detail = (" (%s)" % ", ".join(triggers)) if triggers else ""
        check(tier == "T3", "C2", prefix + "human-boundary trigger requires tier T3" + detail)
        approval_ref = ha.get("approval_ref")
        check(ha.get("required") is True
              and isinstance(approval_ref, str) and approval_ref.strip()
              and not re.match(r"^(TODO|self|me|n/?a)\b", approval_ref.strip(), re.I),
              "C2", prefix + "T3 change needs human_approval.required=true and an external "
                              "approval_ref (PR/ticket URL) — a self-written approver name is "
                              "not accepted; full resolution of the reference happens in CI, "
                              "outside the agent's own credentials")

    rb = meta.get("rollback")
    check(isinstance(rb, str) and rb.strip(), "C2", prefix + "rollback must be a non-empty string")

    if mid is not None:
        e = audit_by_id.get(mid)
        if e is None:
            check(False, "C2", prefix + "no matching entry in audit/log.jsonl")
        else:
            check(e["risk_tier"] == tier, "C2", prefix + "audit entry risk_tier mismatch")
            check(ok_gates and set(e["gates"]) == set(gates),
                  "C2", prefix + "audit entry gates mismatch")
            check(ok_files and sorted(e["files"]) == sorted(files),
                  "C2", prefix + "audit entry files mismatch")

    if tier in ("T1", "T2", "T3") and mid is not None:
        check(mid in changelog_text, "C4", prefix + "tier T1+ change must be referenced in CHANGELOG.md")


def run_checks(root):
    results = []

    def check(ok, code, msg):
        results.append((bool(ok), code, msg))

    # ---- C1: policy file ----
    policy = None
    policy_text = _read(root, POLICY_PATH)
    if policy_text is None:
        check(False, "C1", "missing %s" % POLICY_PATH)
    else:
        try:
            policy = parse_yaml_subset(policy_text)
            check(True, "C1", "policy/policy.yaml parses (restricted YAML subset)")
        except ValueError as e:
            check(False, "C1", "policy/policy.yaml parse failed: %s" % e)

    hb_paths = []
    if isinstance(policy, dict):
        version = policy.get("version")
        check(isinstance(version, str) and bool(VERSION_RE.match(version or "")),
              "C1", "policy version must be semver")
        gates = policy.get("gates")
        gate_ids = [g.get("id") for g in gates if isinstance(g, dict)] if isinstance(gates, list) else []
        check(gate_ids == GATE_IDS, "C1", "gates %s must be defined in order" % GATE_IDS)
        tiers = policy.get("risk_tiers")
        tier_ids = [t.get("id") for t in tiers if isinstance(t, dict)] if isinstance(tiers, list) else []
        check(tier_ids == TIER_IDS, "C1", "risk tiers T0..T3 must be defined in order")
        for t in (tiers if isinstance(tiers, list) else []):
            if not isinstance(t, dict):
                continue
            gs = t.get("gates")
            check(isinstance(gs, list) and len(gs) == len(set(gs)) and set(gs) <= set(GATE_IDS),
                  "C1", "tier %s must declare valid gates" % t.get("id"))
        hb = policy.get("human_boundaries")
        if isinstance(hb, dict):
            p = hb.get("require_approval_paths")
            if isinstance(p, list):
                hb_paths = [x for x in p if isinstance(x, str)]

    # ---- C3: audit log, hash-chained ----
    audit = []
    audit_text = _read(root, AUDIT_PATH)
    if audit_text is None:
        check(False, "C3", "missing %s" % AUDIT_PATH)
    else:
        prev_hash = "0" * 64
        for i, line in enumerate(audit_text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                check(False, "C3", "log.jsonl line %d: invalid JSON" % i)
                continue
            ok_e = (isinstance(e, dict)
                    and e.get("schema") == 2
                    and isinstance(e.get("id"), str) and bool(ID_RE.match(e["id"] or ""))
                    and _iso_ok(e.get("ts"))
                    and isinstance(e.get("author"), str) and e["author"].strip()
                    and e.get("risk_tier") in TIER_IDS
                    and isinstance(e.get("gates"), list) and bool(e["gates"])
                    and set(e["gates"]) <= set(GATE_IDS)
                    and isinstance(e.get("files"), list)
                    and all(isinstance(x, str) and x for x in e["files"])
                    and isinstance(e.get("prev_hash"), str) and len(e["prev_hash"]) == 64)
            check(ok_e, "C3", "log.jsonl line %d well-formed" % i)
            if ok_e:
                check(e["prev_hash"] == prev_hash, "C3",
                      "log.jsonl line %d: prev_hash does not chain to the prior entry "
                      "(the log was edited, reordered, or a line was removed)" % i)
                entry_wo_hash = {k: v for k, v in e.items() if k != "entry_hash"}
                canonical = json.dumps(entry_wo_hash, sort_keys=True, separators=(",", ":"))
                expected_entry_hash = _chain_hash(prev_hash, canonical)
                check(e.get("entry_hash") == expected_entry_hash, "C3",
                      "log.jsonl line %d: entry_hash does not match its own content "
                      "(the line was edited after being appended)" % i)
                prev_hash = e.get("entry_hash", prev_hash)
                audit.append(e)
        ids = [e["id"] for e in audit]
        check(len(ids) == len(set(ids)), "C3", "audit ids must be unique")
        tss = [e["ts"] for e in audit]
        check(tss == sorted(tss), "C3", "audit timestamps must be non-decreasing")
    audit_by_id = {e["id"]: e for e in audit}

    # ---- C2: manifests ----
    changelog_text = _read(root, CHANGELOG_PATH) or ""
    mdir = os.path.join(root, MANIFESTS_DIR)
    if not os.path.isdir(mdir):
        check(False, "C2", "missing %s/ directory" % MANIFESTS_DIR)
    else:
        for fn in sorted(os.listdir(mdir)):
            if not fn.endswith(".md") or fn in ("README.md", "TEMPLATE.md"):
                continue
            rel = os.path.join(MANIFESTS_DIR, fn)
            meta, err = _load_meta(_read(root, rel))
            if meta is None:
                check(False, "C2", "%s: %s" % (rel, err))
                continue
            _check_manifest(check, root, rel, meta, audit_by_id, changelog_text, policy, hb_paths)

    # ---- C5: framework files ----
    for rel in FRAMEWORK_FILES:
        check(_read(root, rel) is not None, "C5", "%s exists" % rel)

    return results


def main(argv):
    root = os.path.abspath(argv[1] if len(argv) > 1 else ".")
    results = run_checks(root)
    nfail = 0
    for ok, c, m in results:
        if not ok:
            nfail += 1
            print("FAIL %s %s" % (c, m))
    print("policy_check: %d checks, %d passed, %d failed"
          % (len(results), len(results) - nfail, nfail))
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
