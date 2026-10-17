"""Run: python3 -m unittest discover -s tests"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "pci_shield.py")
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import pci_shield  # noqa: E402

BAD = os.path.join(HERE, "fixtures", "bad")
GOOD = os.path.join(HERE, "fixtures", "good")
EXPECT = re.compile(r"expect:\s*((?:[A-Z]{3}\d{3}[\s,]*)+)")


def expected(path):
    with open(path) as fh:
        return sorted((no, rule) for no, line in enumerate(fh, 1)
                      for m in EXPECT.finditer(line) for rule in re.findall(r"[A-Z]{3}\d{3}", m.group(1)))


def actual(path):
    return sorted((f.line, f.rule) for f in pci_shield.scan_file(path))


class FixtureTest(unittest.TestCase):
    def test_bad_fixtures_report_exactly_the_marked_lines(self):
        for name in sorted(os.listdir(BAD)):
            path = os.path.join(BAD, name)
            if name.endswith(".properties"):
                continue
            with self.subTest(name):
                self.assertEqual(actual(path), expected(path))

    def test_properties(self):
        got = actual(os.path.join(BAD, "application-dev.properties"))
        self.assertEqual(got, [(1, "CFG001"), (2, "CFG002"), (3, "CFG003")])

    def test_good_fixtures_are_clean(self):
        for name in sorted(os.listdir(GOOD)):
            with self.subTest(name):
                self.assertEqual(actual(os.path.join(GOOD, name)), [])


class ClassifierTest(unittest.TestCase):
    def test_sensitive_identifiers(self):
        for ident in ["pan", "cardNumber", "CARD_NUMBER", "cvv2", "getCvc", "accountNumber",
                      "trackData", "pinBlock", "PANValue", "card.number", "req.getCardNumber"]:
            with self.subTest(ident):
                self.assertTrue(pci_shield.is_sensitive_chain(ident))

    def test_safe_identifiers(self):
        for ident in ["company", "span", "expand", "maskedPan", "panLast4", "cardToken", "panHash",
                      "card.maskedNumber", "cardType", "spinner", "pinned", "orderNumber"]:
            with self.subTest(ident):
                self.assertFalse(pci_shield.is_sensitive_chain(ident))


class HookTest(unittest.TestCase):
    def run_hook(self, payload, env=None):
        return subprocess.run([sys.executable, SCRIPT, "--hook"], input=json.dumps(payload),
                              capture_output=True, text=True, env={**os.environ, **(env or {})})

    def test_blocks_on_errors(self):
        res = self.run_hook({"tool_name": "Edit", "tool_input": {"file_path": os.path.join(BAD, "CardDto.java")}})
        self.assertEqual(res.returncode, 2)
        self.assertIn("PCI002", res.stderr)
        self.assertIn("@ToString.Exclude", res.stderr)

    def test_warnings_become_context(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "application.yml")
            with open(path, "w") as fh:
                fh.write("spring:\n  jpa:\n    show-sql: true\n")
            res = self.run_hook({"tool_name": "Write", "tool_input": {"file_path": path}})
        self.assertEqual(res.returncode, 0)
        out = json.loads(res.stdout)
        self.assertIn("CFG001", out["hookSpecificOutput"]["additionalContext"])

    def test_ignores_other_files_and_bad_input(self):
        res = self.run_hook({"tool_name": "Write", "tool_input": {"file_path": "/tmp/notes.md"}})
        self.assertEqual((res.returncode, res.stdout, res.stderr), (0, "", ""))
        res = subprocess.run([sys.executable, SCRIPT, "--hook"], input="not json", capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

    def test_relative_path_uses_cwd(self):
        res = self.run_hook({"cwd": BAD, "tool_name": "Write", "tool_input": {"file_path": "WebConfig.java"}})
        self.assertEqual(res.returncode, 0)  # PCI003 is only a warning
        self.assertIn("PCI003", res.stdout)

    def test_disable_env(self):
        res = self.run_hook({"tool_input": {"file_path": os.path.join(BAD, "CardDto.java")}},
                            env={"PCI_SHIELD_DISABLE": "1"})
        self.assertEqual(res.returncode, 0)


class CliTest(unittest.TestCase):
    def test_cli_exit_codes(self):
        bad = subprocess.run([sys.executable, SCRIPT, BAD], capture_output=True, text=True)
        good = subprocess.run([sys.executable, SCRIPT, GOOD], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(good.returncode, 0, good.stdout)


if __name__ == "__main__":
    unittest.main()
