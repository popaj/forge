#!/usr/bin/env python3
"""secret_scan.py — fail-closed scan for likely embedded credentials.

Stdlib only. Usage:

    python3 scripts/secret_scan.py [ROOT]

Exit 0 = clean, 1 = findings, 2 = usage error.

This is a tripwire, not a guarantee: it catches the classic patterns so an
agent cannot accidentally (or conveniently) commit a real credential. It is
intentionally simple, deterministic, and dependency-free — see
docs/reproducible-verification.md.
"""
from __future__ import annotations

import os
import re
import sys

# (name, regex) — matched line by line.
PATTERNS = [
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws-secret-access-key",
     re.compile(r"(?i)aws.{0,20}secret.{0,20}['\"][0-9A-Za-z/+=]{40}['\"]")),
    ("github-token",
     re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b|\bgithub_pat_[A-Za-z0-9_]{16,}\b")),
    ("private-key-block",
     re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b")),
]

# credential-looking assignment:  name[:=] value (value 16+ chars)
ASSIGN = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|passwd|password|access[_-]?key)\b"
    r"\s*[:=]\s*['\"]?([A-Za-z0-9+/=_\-]{16,})['\"]?")

# Values that are clearly placeholders, not credentials.
PLACEHOLDER = re.compile(
    r"(?:<[^>]*>|\{\{.*?\}\}|x{4,}|YOUR_|your-|REPLACE|CHANGEME|EXAMPLE|example|redacted)",
    re.I)

SKIP_DIRS = {".git"}


def is_binary(data):
    return b"\x00" in data[:8192]


def scan_file(path, rel):
    findings = []
    with open(path, "rb") as f:
        data = f.read()
    if is_binary(data):
        return findings
    text = data.decode("utf-8", "replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, rx in PATTERNS:
            if rx.search(line):
                findings.append((rel, lineno, name, line.strip()[:80]))
        for m in ASSIGN.finditer(line):
            if not PLACEHOLDER.search(m.group(0)):
                findings.append((rel, lineno, "credential-assignment", m.group(0)[:80]))
    return findings


def scan_tree(root):
    findings = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            findings.extend(scan_file(p, rel))
    return findings


def main(argv):
    root = argv[1] if len(argv) > 1 else "."
    if not os.path.isdir(root):
        print("usage: secret_scan.py [ROOT]", file=sys.stderr)
        return 2
    findings = scan_tree(root)
    if findings:
        print("secret_scan: FAIL — %d potential secret(s):" % len(findings))
        for rel, ln, name, snippet in findings:
            print("  %s:%d  [%s]  %s" % (rel, ln, name, snippet))
        return 1
    print("secret_scan: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
