"""#368 S2.4: the bundled examples show the listener target model and validate cleanly."""
from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "framework" / "tools"))
sys.path.insert(0, str(ROOT))

import migrate_relationships as mr  # noqa: E402
from draft_table import catalog  # noqa: E402

EXAMPLES = ROOT / "examples"
SFTP = {"01KVFRT368-SF01": "01KVFRT368-PCB1", "01KVFRT368-SF02": "01KVFRT368-PC12"}
PAGERDUTY, PAGERDUTY_LISTENER = "01KVFRT368-SY01", "01KVFRT368-PD03"
NEW_FILES = [
    "catalog/engineering/listeners/listener-billing-export-sftp.yaml",
    "catalog/engineering/listeners/listener-image-import-sftp.yaml",
    "catalog/engineering/listeners/listener-pagerduty-events-v2.yaml",
    "catalog/engineering/product-components/product-component-billing-export-service.yaml",
    "catalog/engineering/product-components/product-component-image-import-service.yaml",
    "catalog/governance/systems/system-pagerduty.yaml",
    "catalog/governance/relationships/relationship-ops-console-downloads-billing-exports.yaml",
    "catalog/governance/relationships/relationship-ops-console-uploads-images.yaml",
    "catalog/governance/relationships/relationship-ops-console-alerts-pagerduty.yaml",
    "catalog/governance/relationships/relationship-billing-export-service-alerts-pagerduty.yaml",
    "catalog/governance/relationships/relationship-image-import-service-alerts-pagerduty.yaml",
]


class ExampleTargetModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.objects = catalog.load_effective_catalog(EXAMPLES)

    def test_new_example_objects_validate_cleanly_without_the_baseline(self) -> None:
        proc = subprocess.run([sys.executable, str(ROOT / "framework" / "tools" / "validate.py"), "--workspace", str(EXAMPLES), "--no-baseline"],
                              capture_output=True, text=True, check=False)
        out = proc.stdout + proc.stderr
        for rel_path in NEW_FILES:
            with self.subTest(rel_path):
                self.assertIn(f"PASS examples/{rel_path}", out)
                self.assertNotIn(f"examples/{rel_path}:", out)  # no error or warning names the file

    def test_look_alike_sftp_listeners_are_two_listeners(self) -> None:
        keys = {uid: catalog.listener_identity_key(self.objects[uid]) for uid in SFTP}
        self.assertEqual({key[2:] for key in keys.values()}, {("tcp", 22, "/")})  # same protocol, port and path
        self.assertEqual({key[1] for key in keys.values()}, set(SFTP.values()))  # different owners
        for uid, owner in SFTP.items():
            with self.subTest(uid):
                name = self.objects[owner]["name"]
                self.assertEqual(catalog.lookup_listener(self.objects, "product_component", name, "TCP", 22, "/")["uid"], uid)
                self.assertEqual(catalog.near_match_listeners(self.objects, "product_component", name, "TCP", 22, "/"), [])
        targeted = {obj["targetListener"]: obj["target"] for obj in self.objects.values()
                    if obj.get("type") == "relationship" and obj.get("targetListener") in SFTP}
        self.assertEqual(targeted, SFTP)

    def test_one_external_listener_is_reused_by_several_callers(self) -> None:
        self.assertEqual(self.objects[PAGERDUTY]["type"], "system")
        self.assertEqual(self.objects[PAGERDUTY_LISTENER]["owner"], {"kind": "external_system", "ref": PAGERDUTY})
        callers = [obj for obj in self.objects.values() if obj.get("type") == "relationship" and obj.get("targetListener") == PAGERDUTY_LISTENER]
        self.assertEqual(len({obj["source"] for obj in callers}), 3)
        for rel in callers:
            self.assertEqual(rel["target"], PAGERDUTY)
            self.assertNotIn("externalTarget", rel)
            self.assertNotIn("flow", rel)
        self.assertEqual(catalog.link_or_stub_listener(self.objects, "external_system", "PagerDuty Events API", "https", None, "/v2/enqueue"),
                         {"action": "linked", "uid": PAGERDUTY_LISTENER})

    def test_migration_helper_leaves_the_new_examples_alone(self) -> None:
        planner = mr.propose(EXAMPLES)
        self.assertFalse([item for item in planner.items if item.uid.startswith("01KVFRT368")])
        self.assertEqual(len({item.uid for item in planner.items}), 12)  # the baselined legacy externalTarget relationships


class AdoptionNoteTests(unittest.TestCase):
    def test_changelog_documents_the_adoption_path(self) -> None:
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        # The note stays in whichever release section carries it (Unreleased until promoted, then its version).
        start = text.index("Adoption path for the relationship deprecations (#368)")
        begin = text.rfind("\n## ", 0, start)
        following = re.search(r"(?m)^## ", text[start:])
        section = text[begin: start + following.start()] if following else text[begin:]
        for phrase in ("--write-baseline", "/draft migrate", "relationship-flow-deprecated", "relationship-external-target-freetext",
                       "relationship-source-is-listener-side", "on touch"):
            self.assertIn(phrase, section, phrase)


if __name__ == "__main__":
    unittest.main()
