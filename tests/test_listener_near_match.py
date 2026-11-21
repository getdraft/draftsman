"""#368 S2.3: near-match listeners are asked about, never linked silently; /draft migrate routes to the helper."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "framework" / "tools"))
sys.path.insert(0, str(ROOT))

import migrate_relationships as mr  # noqa: E402
from draft_table import catalog  # noqa: E402
from draft_table.repo import vendored_framework_text  # noqa: E402


def objects_with(*listeners: dict) -> dict[str, dict]:
    objects = {
        "PROD-0001": {"uid": "PROD-0001", "type": "product_component", "name": "Checkout"},
        "PROD-0002": {"uid": "PROD-0002", "type": "product_component", "name": "Billing"},
        "SYS-0001": {"uid": "SYS-0001", "type": "system", "name": "Partner SFTP"},
    }
    for listener in listeners:
        objects[listener["uid"]] = {"type": "listener", "catalogStatus": "complete", **listener}
    return objects


def listener(uid: str, protocol: str, port: int | None, endpoint: str, owner: str = "PROD-0001", kind: str = "product_component") -> dict:
    return {"uid": uid, "name": uid, "owner": {"kind": kind, "ref": owner}, "protocol": protocol, "port": port, "endpoint": endpoint}


CASES = [
    # (existing, wanted (protocol, port, endpoint), expected differs)
    (("https", None, "/v1/orders"), ("https", None, "/v2/orders"), ["version"]),
    (("https", None, "/orders"), ("https", None, "/2024-06-01/orders"), ["version"]),
    (("https", None, "/"), ("https", None, "/orders"), ["path"]),
    (("https", None, "/orders"), ("https", None, "/orders/{}/items"), ["path"]),
    (("https", 443, "/orders"), ("https", 8443, "/orders"), ["port"]),
    (("https", 443, "/v1/orders"), ("https", 8443, "/v2/orders"), ["version", "port"]),
    (("sftp", 22, "/"), ("sftp", 2222, "/"), ["port"]),
    (("https", None, "/orders"), ("https", None, "/payments"), []),  # different path, not an extension
    (("https", 443, "/"), ("https", 8443, "/orders"), []),  # path and port both differ
    (("http", None, "/orders"), ("https", None, "/orders"), []),  # protocol differs
    (("https", None, "/orders/{id}"), ("https", 443, "/orders/:id/"), []),  # exact match, not near
]


class NearMatchRuleTests(unittest.TestCase):
    def test_cases(self) -> None:
        for existing, wanted, expected in CASES:
            with self.subTest(existing=existing, wanted=wanted):
                objects = objects_with(listener("LIS-0001", *existing))
                found = catalog.near_match_listeners(objects, "product_component", "Checkout", *wanted)
                self.assertEqual([item["differs"] for item in found], [expected] if expected else [])

    def test_the_owner_is_part_of_the_match(self) -> None:
        objects = objects_with(listener("LIS-0001", "sftp", 22, "/", owner="PROD-0002"))
        self.assertEqual(catalog.near_match_listeners(objects, "product_component", "Checkout", "sftp", 2222, "/"), [])

    def test_migration_helper_uses_the_same_rule(self) -> None:
        for existing, wanted, expected in CASES:
            a = catalog.listener_identity_key({"owner": {"kind": "k", "ref": "O"}, "protocol": wanted[0], "port": wanted[1], "endpoint": wanted[2]})
            b = catalog.listener_identity_key({"owner": {"kind": "k", "ref": "O"}, "protocol": existing[0], "port": existing[1], "endpoint": existing[2]})
            with self.subTest(existing=existing, wanted=wanted):
                self.assertEqual(mr.listener_near_match(a, b), catalog.listener_near_match(a, b))
                self.assertEqual(catalog.listener_near_match(a, b), expected)


class NeverLinkSilentlyTests(unittest.TestCase):
    def test_link_or_stub_asks_before_creating_next_to_a_near_match(self) -> None:
        objects = objects_with(listener("LIS-0001", "https", None, "/v1/orders"))
        result = catalog.link_or_stub_listener(objects, "product_component", "Checkout", "https", None, "/v2/orders")
        self.assertEqual(result["action"], "near_match")
        self.assertNotIn("uid", result)
        self.assertEqual([(c["uid"], c["differs"]) for c in result["candidates"]], [("LIS-0001", ["version"])])
        created = catalog.link_or_stub_listener(objects, "product_component", "Checkout", "https", None, "/v2/orders", confirmed_new=True)
        self.assertEqual(created["action"], "created")
        self.assertNotEqual(created["uid"], "LIS-0001")

    def test_exact_match_still_links_without_asking(self) -> None:
        objects = objects_with(listener("LIS-0001", "https", None, "/v1/orders"), listener("LIS-0002", "https", None, "/v2/orders"))
        result = catalog.link_or_stub_listener(objects, "product_component", "Checkout", "https", 443, "/v2/orders/")
        self.assertEqual(result, {"action": "linked", "uid": "LIS-0002"})

    def test_record_authored_listener_asks_too(self) -> None:
        objects = objects_with(listener("SFTP-0001", "sftp", 22, "/", owner="SYS-0001", kind="external_system"))
        authored = {"owner": {"kind": "external_system", "ref": "Partner SFTP"}, "protocol": "sftp", "port": 2222, "endpoint": "/",
                    "authenticationModel": "ssh-key"}
        result = catalog.record_authored_listener(objects, authored)
        self.assertEqual((result["action"], result["candidates"][0]["uid"]), ("near_match", "SFTP-0001"))
        self.assertEqual(catalog.record_authored_listener(objects, authored, confirmed_new=True)["action"], "created")


class MigrationNearMatchTests(unittest.TestCase):
    def test_helper_asks_instead_of_stubbing_next_to_a_near_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            docs = {
                "catalog/c.yaml": {"schemaVersion": "1.0", "uid": "01M7D0AA01-CMP1", "type": "product_component", "name": "Checkout"},
                "catalog/s.yaml": {"schemaVersion": "1.0", "uid": "01M7D0AA02-SYS1", "type": "system", "name": "Stripe"},
                "catalog/l.yaml": {"schemaVersion": "1.0", "uid": "01M7D0AA04-LS01", "type": "listener", "name": "Stripe charges",
                                   "owner": {"kind": "external_system", "ref": "01M7D0AA02-SYS1"}, "protocol": "HTTPS", "port": 443,
                                   "endpoint": "/v1/charges", "authenticationModel": "api-key"},
                "catalog/r.yaml": {"schemaVersion": "1.0", "uid": "01M7D0AA03-RS01", "type": "relationship", "name": "pays",
                                   "source": "01M7D0AA01-CMP1", "externalTarget": "Stripe", "technology": "HTTPS"},
            }
            for rel_path, doc in docs.items():
                (ws / rel_path).parent.mkdir(parents=True, exist_ok=True)
                (ws / rel_path).write_text(yaml.safe_dump(doc), encoding="utf-8")
            planner = mr.propose(ws)
        (item,) = planner.items
        self.assertEqual(item.kind, "needs-input")
        self.assertIn("Never link a near match silently", item.summary)
        self.assertIn("near match 01M7D0AA04-LS01", item.details[0])
        self.assertIn("differs by path", item.details[0])
        self.assertEqual((planner.edits, planner.new_files), ({}, {}))


class MigrateActionTests(unittest.TestCase):
    ACTION = ROOT / "framework" / "draft-actions" / "migrate.md"

    def test_draft_routes_migrate_to_its_action(self) -> None:
        router = (ROOT / "framework" / "commands" / "draft.md").read_text(encoding="utf-8")
        self.assertIn("| `migrate` | `draft-actions/migrate.md` (direct action, no skill)", router)
        self.assertIn("| `/draft migrate` |", router.split("## Show the verb list", 1)[1])
        self.assertTrue(self.ACTION.exists())

    def test_action_runs_the_helper_and_reviews_before_applying(self) -> None:
        text = self.ACTION.read_text(encoding="utf-8")
        front = yaml.safe_load(text.split("---", 2)[1])
        self.assertIn("description", front)
        self.assertIn(".draft/framework/tools/migrate_relationships.py", text)
        for flag in ("--object", "--sdp", "--folder", "--report", "--patch"):
            self.assertIn(flag, text)
        self.assertIn("Never link a near match silently", text)
        self.assertIn("Do not apply anything the user has not approved", text)
        self.assertIn("draft-actions/validate.md", text)

    def test_action_survives_vendoring(self) -> None:
        vendored = vendored_framework_text(self.ACTION.read_text(encoding="utf-8"))
        self.assertIn("python3 .draft/framework/tools/migrate_relationships.py", vendored)

    def test_docs_and_skills_say_ask_about_near_matches(self) -> None:
        for rel_path in ("framework/docs/draftsman.md", "framework/skills/draftsman-author/SKILL.md", "framework/skills/draftsman-core/SKILL.md"):
            text = " ".join((ROOT / rel_path).read_text(encoding="utf-8").lower().split())
            with self.subTest(rel_path):
                self.assertIn("near match", text.replace("near-match", "near match"))
                self.assertTrue("never link a near match silently" in text or "never link a near-match listener" in text)


if __name__ == "__main__":
    unittest.main()
