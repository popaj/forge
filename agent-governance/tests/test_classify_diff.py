"""Unit tests for scripts/classify_diff.py.

These specifically re-create the bypasses found by adversarial testing of
a prior design: renaming a sensitive file out of a matched path, and a
diff editing the rules it is about to be judged by.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS)

import classify_diff as cd  # noqa: E402


RULES = {
    "path_rules": [
        {"pattern": "^auth/", "dimension": "security_boundary", "level": "T3"},
    ],
    "content_rules": [
        {"pattern": "(?i)authenticate|verify_password", "dimension": "security_boundary", "level": "T3"},
    ],
    "protected_paths": ["policy/"],
    "protected_path_level": "T3",
}


def git(root, *args):
    p = subprocess.run(["git", *args], cwd=root, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    return p.stdout


class ClassifyDiffTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="classify-")
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        os.makedirs(os.path.join(self.root, "policy"))
        os.makedirs(os.path.join(self.root, "auth"))
        os.makedirs(os.path.join(self.root, "misc"))
        with open(os.path.join(self.root, "policy", "rules.json"), "w") as f:
            json.dump(RULES, f)
        with open(os.path.join(self.root, "auth", "login.py"), "w") as f:
            f.write("def login(): pass\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "base")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _branch(self, name):
        git(self.root, "checkout", "-q", "-b", name)

    def test_docs_only_change_derives_t0(self):
        self._branch("docs")
        with open(os.path.join(self.root, "readme.md"), "w") as f:
            f.write("notes\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "docs")
        os.chdir(self.root)
        rules = cd.load_rules_from_base("main")
        paths = cd.changed_paths("main", "docs")
        derived, dims, reasons = cd.derive_tier(paths, "main", "docs", rules)
        self.assertEqual(derived, "T0", reasons)

    def test_touching_matched_auth_path_derives_t3(self):
        self._branch("benign")
        with open(os.path.join(self.root, "auth", "login.py"), "a") as f:
            f.write("# comment\n")
        git(self.root, "commit", "-q", "-am", "comment")
        os.chdir(self.root)
        rules = cd.load_rules_from_base("main")
        paths = cd.changed_paths("main", "benign")
        derived, dims, reasons = cd.derive_tier(paths, "main", "benign", rules)
        self.assertEqual(derived, "T3", reasons)

    def test_rename_evasion_is_still_caught_by_content_rule(self):
        self._branch("evade")
        os.rename(os.path.join(self.root, "auth", "login.py"),
                  os.path.join(self.root, "misc", "login.py"))
        with open(os.path.join(self.root, "misc", "login.py"), "a") as f:
            f.write("def authenticate(u, p): return verify_password(u, p)\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "move and extend")
        os.chdir(self.root)
        rules = cd.load_rules_from_base("main")
        paths = cd.changed_paths("main", "evade")
        derived, dims, reasons = cd.derive_tier(paths, "main", "evade", rules)
        self.assertEqual(derived, "T3", reasons)
        self.assertTrue(any("content" in d for d in dims), dims)

    def test_diff_cannot_loosen_its_own_rules(self):
        """A diff that edits policy/rules.json to stop matching auth/ must
        still be judged by the BASE version of the rules, because the base
        commit's auth/login.py edit should still classify as T3."""
        self._branch("selfweaken")
        with open(os.path.join(self.root, "auth", "login.py"), "a") as f:
            f.write("# change\n")
        loosened = {"path_rules": [], "content_rules": [], "protected_paths": [],
                    "protected_path_level": "T3"}
        with open(os.path.join(self.root, "policy", "rules.json"), "w") as f:
            json.dump(loosened, f)
        git(self.root, "commit", "-q", "-am", "weaken rules + touch auth")
        os.chdir(self.root)

        rules = cd.load_rules_from_base("main")  # must be the ORIGINAL rules
        self.assertTrue(rules["path_rules"], "rules read from base must not be the loosened copy")
        paths = cd.changed_paths("main", "selfweaken")
        derived, dims, reasons = cd.derive_tier(paths, "main", "selfweaken", rules)
        self.assertEqual(derived, "T3", reasons)

    def test_manifest_files_mismatch_is_detected(self):
        self._branch("mismatch")
        with open(os.path.join(self.root, "auth", "login.py"), "a") as f:
            f.write("# x\n")
        with open(os.path.join(self.root, "misc", "extra.py"), "w") as f:
            f.write("x = 1\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "two files")

        manifest = {
            "risk_tier": "T3",
            "files": ["auth/login.py"],  # misc/extra.py omitted
            "human_approval": {"required": True, "approval_ref": "https://example/pr/1"},
        }
        mpath = os.path.join(self.root, "manifest.md")
        with open(mpath, "w") as f:
            f.write("```json\n" + json.dumps(manifest) + "\n```\n")

        os.chdir(self.root)
        rules = cd.load_rules_from_base("main")
        paths = cd.changed_paths("main", "mismatch")
        derived, _, _ = cd.derive_tier(paths, "main", "mismatch", rules)
        meta = cd.load_manifest_meta(mpath)
        manifest_files = sorted(meta["files"])
        self.assertNotEqual(manifest_files, paths)

    def test_t3_without_approval_ref_is_an_error_via_main(self):
        self._branch("needsapproval")
        with open(os.path.join(self.root, "auth", "login.py"), "a") as f:
            f.write("# x\n")
        git(self.root, "commit", "-q", "-am", "touch auth")
        manifest = {
            "risk_tier": "T3",
            "files": ["auth/login.py"],
            "human_approval": {"required": True, "approval_ref": ""},
        }
        mpath = os.path.join(self.root, "manifest.md")
        with open(mpath, "w") as f:
            f.write("```json\n" + json.dumps(manifest) + "\n```\n")
        os.chdir(self.root)
        sys.argv = ["classify_diff.py", "--base", "main", "--head", "needsapproval",
                    "--manifest", mpath]
        rc = cd.main()
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
