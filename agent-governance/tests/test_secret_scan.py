"""Unit tests for scripts/secret_scan.py.

Positive fixtures are built by string concatenation so that the test file
itself never contains a full credential pattern (the scanner runs on this
repository, including these tests).
"""
import os
import shutil
import sys
import tempfile
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS)

import secret_scan as ss  # noqa: E402


class SecretScanTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="secscan-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write_and_scan(self, name, text):
        with open(os.path.join(self.root, name), "w", encoding="utf-8") as f:
            f.write(text)
        return ss.scan_tree(self.root)

    def test_finds_aws_access_key(self):
        key = "AKIA" + "IOSFODNN7EXAMPLE"  # concatenation keeps this file clean
        findings = self.write_and_scan("c.txt", 'aws = "%s"\n' % key)
        self.assertTrue(any(f[2] == "aws-access-key-id" for f in findings), findings)

    def test_finds_github_token(self):
        tok = "ghp_" + "A" * 20
        findings = self.write_and_scan("c.txt", "github token is %r here\n" % tok)
        self.assertTrue(any(f[2] == "github-token" for f in findings), findings)

    def test_finds_private_key_block(self):
        header = "-----BEGIN RSA PRIVATE KEY" + "-----"
        findings = self.write_and_scan("keyfile", header + "\nabc\n")
        self.assertTrue(any(f[2] == "private-key-block" for f in findings), findings)

    def test_clean_text_passes(self):
        findings = self.write_and_scan("ok.txt", "hello world\nversion: 1.2.3\n")
        self.assertEqual(findings, [])

    def test_placeholder_not_flagged(self):
        findings = self.write_and_scan("cfg", 'api_key: "<redacted>"\n')
        self.assertEqual([f for f in findings if f[2] == "credential-assignment"], [])

    def test_binary_file_skipped(self):
        with open(os.path.join(self.root, "blob.bin"), "wb") as f:
            f.write(b"\x00\x01\x02AKIAIOSFODNN7EXAMPLE")
        self.assertEqual(ss.scan_tree(self.root), [])


if __name__ == "__main__":
    unittest.main()
