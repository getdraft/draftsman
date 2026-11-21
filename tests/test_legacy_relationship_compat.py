"""#368 S1.3: a workspace with v1.5.5-style relationships stays green after a framework refresh, and editing one
baselined relationship flags only that relationship (flag on touch)."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATE = REPO_ROOT / "framework" / "tools" / "validate.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "legacy_v155_workspace"
NEW_RULES = ("relationship-flow-deprecated", "relationship-external-target-freetext", "relationship-source-is-listener-side")
BIDIRECTIONAL, INBOUND, EXTERNAL, INBOUND_EXTERNAL = (
    "01M7C4AA03-RS01", "01M7C4AA04-RS02", "01M7C4AA05-RS03", "01M7C4AA06-RS04")
RULE_LINE = re.compile(r"^- (?P<baseline>baseline: )?.*?\[(?P<rule>[a-z0-9-]+)\] (?P<uid>\S+):")


def violations(out: str) -> list[tuple[bool, str, str]]:
    """(is_baseline, rule, uid) for each ratcheted line in the validator output."""
    found = []
    for line in out.splitlines():
        match = RULE_LINE.match(line)
        if match:
            found.append((bool(match.group("baseline")), match.group("rule"), match.group("uid")))
    return found


class LegacyWorkspaceCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ws = Path(tmp.name) / "ws"
        shutil.copytree(FIXTURE, self.ws)

    def run_validate(self, *flags: str) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(VALIDATE), "--workspace", str(self.ws), *flags],
                              capture_output=True, text=True, check=False)
        return proc.returncode, proc.stdout + proc.stderr

    def refresh(self) -> None:
        """What the documented framework refresh does: write the baseline once."""
        self.assertFalse((self.ws / ".draft" / "validation-baseline.yaml").exists())
        code, out = self.run_validate("--write-baseline")
        self.assertEqual(0, code, out)

    def test_fixture_carries_the_legacy_shapes(self) -> None:
        docs = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted((FIXTURE / "catalog").rglob("*.yaml"))]
        rels = {d["uid"]: d for d in docs if d["type"] == "relationship"}
        self.assertEqual(rels[BIDIRECTIONAL]["flow"], "bidirectional")
        self.assertEqual(rels[INBOUND]["flow"], "inbound")
        self.assertIn("externalTarget", rels[EXTERNAL])
        self.assertEqual((rels[INBOUND_EXTERNAL]["flow"], "externalTarget" in rels[INBOUND_EXTERNAL]), ("inbound", True))
        self.assertFalse([d for d in docs if "targetListener" in d or d["type"] == "listener"])

    def test_without_a_baseline_the_new_rules_are_errors(self) -> None:
        code, out = self.run_validate()
        self.assertEqual(1, code)
        errors = {(rule, uid) for baseline, rule, uid in violations(out) if not baseline and rule in NEW_RULES}
        self.assertEqual(errors, {
            ("relationship-flow-deprecated", BIDIRECTIONAL), ("relationship-flow-deprecated", INBOUND),
            ("relationship-flow-deprecated", INBOUND_EXTERNAL), ("relationship-external-target-freetext", EXTERNAL),
            ("relationship-external-target-freetext", INBOUND_EXTERNAL),
            ("relationship-source-is-listener-side", INBOUND_EXTERNAL),
        })

    def test_refreshed_workspace_exits_zero_with_only_baseline_warnings(self) -> None:
        self.refresh()
        code, out = self.run_validate()
        self.assertEqual(0, code, out)
        self.assertNotIn("Validation failures", out)
        found = violations(out)
        self.assertTrue(found)
        self.assertTrue(all(baseline for baseline, _, _ in found), [v for v in found if not v[0]])
        self.assertEqual({rule for _, rule, _ in found} & set(NEW_RULES), set(NEW_RULES))
        self.assertNotIn("stale baseline entry", out)

    def test_editing_one_relationship_flags_only_that_one(self) -> None:
        self.refresh()
        path = next(p for p in (self.ws / "catalog").rglob("*.yaml") if BIDIRECTIONAL in p.read_text(encoding="utf-8"))
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["label"] = "calls the orders API"
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
        code, out = self.run_validate()
        self.assertEqual(1, code)
        found = violations(out)
        errors = {(rule, uid) for baseline, rule, uid in found if not baseline}
        self.assertIn(("relationship-flow-deprecated", BIDIRECTIONAL), errors)
        self.assertEqual({uid for _, uid in errors}, {BIDIRECTIONAL})
        untouched = {uid for baseline, rule, uid in found if baseline and rule in NEW_RULES}
        self.assertEqual(untouched, {INBOUND, EXTERNAL, INBOUND_EXTERNAL})

    def test_migrating_the_edited_relationship_clears_its_new_rule_errors(self) -> None:
        self.refresh()
        path = next(p for p in (self.ws / "catalog").rglob("*.yaml") if BIDIRECTIONAL in p.read_text(encoding="utf-8"))
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["flow"] = "outbound"
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
        _, out = self.run_validate()
        errors = {(rule, uid) for baseline, rule, uid in violations(out) if not baseline}
        self.assertFalse([e for e in errors if e[0] in NEW_RULES], errors)
        # It still has to name its listener once touched: the #341 rule applies on touch too.
        self.assertIn(("relationship-target-listener", BIDIRECTIONAL), errors)


if __name__ == "__main__":
    unittest.main()
