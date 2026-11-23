"""Unit tests for scripts/policy_check.py.

Focus is on the properties that were found broken by adversarial testing
of prior designs: hash-chain tamper detection, rejection of placeholder
evidence, requiring an external approval_ref for T3, and clean (non-crash)
handling of an invalid risk_tier.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS)

import policy_check as pc  # noqa: E402


POLICY_YAML = textwrap.dedent("""\
    version: 0.1.0
    gates:
      - id: G0
        name: hygiene
      - id: G1
        name: correctness
      - id: G2
        name: security
      - id: G3
        name: maintainability
      - id: G4
        name: documentation
      - id: G5
        name: reproducibility
      - id: G6
        name: auditability
      - id: G7
        name: independent-verifiability
      - id: G8
        name: diff-faithfulness
    risk_tiers:
      - id: T0
        name: documentation-only
        gates:
          - G0
          - G4
          - G6
          - G7
          - G8
      - id: T1
        name: internal-behavior
        gates:
          - G0
          - G1
          - G4
          - G6
          - G7
          - G8
      - id: T2
        name: public-facing
        gates:
          - G0
          - G1
          - G2
          - G3
          - G4
          - G5
          - G6
          - G7
          - G8
      - id: T3
        name: boundary-crossing
        requires_human_approval: true
        gates:
          - G0
          - G1
          - G2
          - G3
          - G4
          - G5
          - G6
          - G7
          - G8
    human_boundaries:
      require_approval_paths:
        - policy/**
        - AGENTS.md
      hard_rules:
        - "no self-approval"
""")


def _chain_entry(prev_hash, **fields):
    """Mirrors scripts/log_change.py's construction order exactly:
    prev_hash must be part of the entry BEFORE canonical/entry_hash is
    computed, since policy_check.py's verification includes prev_hash in
    the hashed content (it excludes only entry_hash itself)."""
    entry = dict(fields)
    entry.setdefault("schema", 2)
    entry["prev_hash"] = prev_hash
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    entry["entry_hash"] = hashlib.sha256((prev_hash + canonical).encode()).hexdigest()
    return entry


class YamlSubsetTests(unittest.TestCase):
    def test_parses_nested_policy(self):
        data = pc.parse_yaml_subset(POLICY_YAML)
        self.assertEqual(data["version"], "0.1.0")
        self.assertEqual([g["id"] for g in data["gates"]], pc.GATE_IDS)
        self.assertEqual([t["id"] for t in data["risk_tiers"]], pc.TIER_IDS)

    def test_rejects_tabs(self):
        with self.assertRaises(ValueError):
            pc.parse_yaml_subset("version: 0.1.0\n\tgates: []\n")

    def test_rejects_flow_collections(self):
        with self.assertRaises(ValueError):
            pc.parse_yaml_subset("gates: [a, b]\n")


class RepoFixture:
    """Builds a minimal valid repo layout in a temp dir for run_checks()."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="govcheck-")
        os.makedirs(os.path.join(self.root, "policy"))
        os.makedirs(os.path.join(self.root, "manifests"))
        os.makedirs(os.path.join(self.root, "audit"))
        os.makedirs(os.path.join(self.root, ".github"))
        with open(os.path.join(self.root, "policy", "policy.yaml"), "w") as f:
            f.write(POLICY_YAML)
        for rel in pc.FRAMEWORK_FILES:
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if not os.path.isfile(path):
                with open(path, "w") as f:
                    f.write("placeholder\n")
        with open(os.path.join(self.root, "manifests", "TEMPLATE.md"), "w") as f:
            f.write("template\n")
        open(os.path.join(self.root, "audit", "log.jsonl"), "w").close()
        open(os.path.join(self.root, "CHANGELOG.md"), "w").close()

    def write_manifest(self, meta):
        path = os.path.join(self.root, "manifests", meta["id"] + ".md")
        with open(path, "w") as f:
            f.write("```json\n" + json.dumps(meta, indent=2) + "\n```\n\n# t\n")
        for rel in meta.get("files", []):
            fp = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(fp) or self.root, exist_ok=True)
            if not os.path.isfile(fp):
                with open(fp, "w") as f:
                    f.write("x\n")
        return path

    def write_audit_line(self, entry):
        with open(os.path.join(self.root, "audit", "log.jsonl"), "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


def base_manifest(**overrides):
    meta = {
        "id": "20260101-0000-sample",
        "date": "2026-01-01",
        "title": "Sample",
        "author": {"type": "agent", "name": "a", "model": "m"},
        "risk_tier": "T1",
        "human_approval": {"required": False, "reason": "", "approval_ref": ""},
        "gates": ["G0", "G1", "G4", "G6", "G7", "G8"],
        "gate_evidence": {g: "pytest -> 1 passed" for g in
                          ["G0", "G1", "G4", "G6", "G7", "G8"]},
        "files": ["docs/note.md"],
        "rollback": "revert",
    }
    meta.update(overrides)
    return meta


class ManifestChecksTests(unittest.TestCase):
    def setUp(self):
        self.fx = RepoFixture()

    def tearDown(self):
        self.fx.cleanup()

    def _passes(self, meta):
        self.fx.write_manifest(meta)
        entry = _chain_entry(
            "0" * 64,
            id=meta["id"], ts="2026-01-01T00:00:00+00:00",
            author="agent:a", risk_tier=meta["risk_tier"],
            gates=sorted(meta["gates"]), files=sorted(meta["files"]), commit=None,
        )
        self.fx.write_audit_line(entry)
        with open(os.path.join(self.fx.root, "CHANGELOG.md"), "a") as f:
            f.write(meta["id"] + "\n")
        results = pc.run_checks(self.fx.root)
        return results

    def test_well_formed_manifest_passes(self):
        results = self._passes(base_manifest())
        failed = [m for ok, c, m in results if not ok]
        self.assertEqual(failed, [], failed)

    def test_placeholder_evidence_rejected(self):
        meta = base_manifest(gate_evidence={
            g: "EXACT COMMANDS + OBSERVED RESULT" for g in
            ["G0", "G1", "G4", "G6", "G7", "G8"]
        })
        results = self._passes(meta)
        codes = [(c, m) for ok, c, m in results if not ok]
        self.assertTrue(any("gate_evidence" in m for c, m in codes), codes)

    def test_evidence_without_result_shape_rejected(self):
        meta = base_manifest(gate_evidence={
            g: "passed" for g in ["G0", "G1", "G4", "G6", "G7", "G8"]
        })
        results = self._passes(meta)
        codes = [(c, m) for ok, c, m in results if not ok]
        self.assertTrue(any("gate_evidence" in m for c, m in codes), codes)

    def test_invalid_tier_fails_cleanly_no_crash(self):
        meta = base_manifest(risk_tier="T9")
        try:
            results = self._passes(meta)
        except Exception as e:  # pragma: no cover - the whole point is no crash
            self.fail("run_checks crashed on invalid tier: %r" % e)
        codes = [(c, m) for ok, c, m in results if not ok]
        self.assertTrue(any("risk_tier" in m for c, m in codes), codes)

    def test_t3_requires_approval_ref_not_self_written_approver(self):
        meta = base_manifest(
            risk_tier="T3",
            files=["policy/policy.yaml"],
            gates=["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"],
            gate_evidence={g: "x -> y" for g in
                          ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]},
            human_approval={"required": True, "reason": "policy change",
                             "approval_ref": ""},
        )
        results = self._passes(meta)
        codes = [(c, m) for ok, c, m in results if not ok]
        self.assertTrue(any("approval_ref" in m for c, m in codes), codes)

        # Self-written "approver name" style ref is rejected too.
        meta2 = dict(meta)
        meta2["human_approval"] = {"required": True, "reason": "policy change",
                                    "approval_ref": "self-approved by agent"}
        self.fx = RepoFixture()
        results2 = self._passes(meta2)
        codes2 = [(c, m) for ok, c, m in results2 if not ok]
        self.assertTrue(any("approval_ref" in m for c, m in codes2), codes2)

    def test_t3_with_real_looking_external_ref_passes_structurally(self):
        meta = base_manifest(
            risk_tier="T3",
            files=["policy/policy.yaml"],
            gates=["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"],
            gate_evidence={g: "x -> y" for g in
                          ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]},
            human_approval={"required": True, "reason": "policy change",
                             "approval_ref": "https://github.com/org/repo/pull/42"},
        )
        results = self._passes(meta)
        failed = [m for ok, c, m in results if not ok]
        self.assertEqual(failed, [], failed)


class AuditChainTests(unittest.TestCase):
    def setUp(self):
        self.fx = RepoFixture()

    def tearDown(self):
        self.fx.cleanup()

    def _write_two_entry_chain(self):
        e1 = _chain_entry("0" * 64, id="20260101-0000-a", ts="2026-01-01T00:00:00+00:00",
                           author="agent:a", risk_tier="T0", gates=["G0"], files=["x"],
                           commit=None)
        e2 = _chain_entry(e1["entry_hash"], id="20260101-0100-b",
                           ts="2026-01-01T01:00:00+00:00", author="agent:a",
                           risk_tier="T0", gates=["G0"], files=["y"], commit=None)
        self.fx.write_audit_line(e1)
        self.fx.write_audit_line(e2)
        return e1, e2

    def test_valid_chain_has_no_C3_failures(self):
        self._write_two_entry_chain()
        results = pc.run_checks(self.fx.root)
        c3_failed = [m for ok, c, m in results if not ok and c == "C3"]
        self.assertEqual(c3_failed, [], c3_failed)

    def test_tampering_a_past_entry_breaks_the_chain(self):
        self._write_two_entry_chain()
        path = os.path.join(self.fx.root, "audit", "log.jsonl")
        lines = open(path).read().splitlines()
        first = json.loads(lines[0])
        first["author"] = "agent:rogue"  # edit without recomputing entry_hash
        lines[0] = json.dumps(first, separators=(",", ":"))
        open(path, "w").write("\n".join(lines) + "\n")

        results = pc.run_checks(self.fx.root)
        c3_failed = [m for ok, c, m in results if not ok and c == "C3"]
        self.assertTrue(c3_failed, "tampered audit log should fail C3 but did not")


if __name__ == "__main__":
    unittest.main()
