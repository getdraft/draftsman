"""#368 S2.2: the relationship migration helper proposes reviewable conversions and never edits catalog files."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "framework" / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

import migrate_relationships as mr  # noqa: E402
from draft_table.catalog import link_or_stub_listener, resolve_listener_owner  # noqa: E402

LEGACY = REPO_ROOT / "tests" / "fixtures" / "legacy_v155_workspace"
VALIDATE = TOOLS / "validate.py"
CALLER, VENDOR_SYS, REL = "01M7D0AA01-CMP1", "01M7D0AA02-SYS1", "01M7D0AA03-RS01"


def snapshot(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def write(ws: Path, rel_path: str, doc: object) -> Path:
    path = ws / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def component(uid: str = CALLER, name: str = "Checkout") -> dict:
    return {"schemaVersion": "1.0", "uid": uid, "type": "product_component", "name": name,
            "repoUrl": "https://github.com/example/checkout", "owner": {"team": "shop"}, "classification": "api-service",
            "catalogStatus": "incomplete", "lifecycleStatus": "candidate"}


def relationship(uid: str = REL, **fields: object) -> dict:
    return {"schemaVersion": "1.0", "uid": uid, "type": "relationship", "name": f"rel {uid}", "catalogStatus": "complete",
            "source": CALLER, "label": "pays through", "technology": "HTTPS", "direction": "synchronous", **fields}


class Workspace:
    def __init__(self, test: unittest.TestCase, source: Path | None = None) -> None:
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "ws"
        if source:
            shutil.copytree(source, self.root)
        else:
            (self.root / "catalog").mkdir(parents=True)
        self.out = Path(tmp.name)

    def run(self, *args: str) -> tuple[str, str]:
        report, patch = self.out / "report.md", self.out / "migration.patch"
        code = mr.main(["--workspace", str(self.root), "--report", str(report), "--patch", str(patch), *args])
        assert code == 0
        return report.read_text(encoding="utf-8"), patch.read_text(encoding="utf-8")

    def apply(self, patch: str) -> None:
        (self.out / "apply.patch").write_text(patch, encoding="utf-8")
        result = subprocess.run(["git", "apply", str(self.out / "apply.patch")], cwd=self.root, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def validate(self) -> str:
        proc = subprocess.run([sys.executable, str(VALIDATE), "--workspace", str(self.root), "--no-baseline"],
                              capture_output=True, text=True, check=False)
        return proc.stdout + proc.stderr


def kinds(planner: mr.Planner) -> list[tuple[str, str]]:
    return [(item.kind, item.uid) for item in planner.items]


class LegacyFixtureTests(unittest.TestCase):
    def test_proposals_for_each_legacy_shape(self) -> None:
        planner = mr.propose(LEGACY)
        self.assertEqual(kinds(planner), [
            ("flow-bidirectional", "01M7C4AA03-RS01"),
            ("flow-inbound-swap", "01M7C4AA04-RS02"),
            ("needs-input", "01M7C4AA04-RS02"),  # name the listener on the new target
            ("needs-input", "01M7C4AA05-RS03"),  # LDAPS has no listener protocol with a default port
            ("inbound-external-remove", "01M7C4AA06-RS04"),
        ])
        self.assertEqual(planner.new_files, {})  # no orphan system for the externalTarget that could not convert
        removal = [i for i in planner.items if i.kind == "inbound-external-remove"][0]
        self.assertIn("record on Legacy Order API's listener instead", removal.details[0])

    def test_never_edits_the_workspace_and_the_patch_applies(self) -> None:
        ws = Workspace(self, LEGACY)
        before = snapshot(ws.root)
        report, patch = ws.run()
        self.assertEqual(snapshot(ws.root), before)
        self.assertIn("Nothing has been changed", report)
        ws.apply(patch)
        rels = {p.name: yaml.safe_load(p.read_text(encoding="utf-8")) for p in (ws.root / "catalog" / "relationships").glob("*.yaml")}
        self.assertNotIn("relationship-internet-calls-order-api.yaml", rels)
        self.assertEqual(rels["relationship-web-shop-calls-order-api.yaml"]["flow"], "outbound")
        swapped = rels["relationship-order-api-fronted-by-web-shop.yaml"]
        self.assertEqual((swapped["source"], swapped["target"], swapped["flow"]), ("01M7C4AA01-WEB1", "01M7C4AA02-AP01", "outbound"))
        self.assertNotIn("targetInterface", swapped)
        self.assertIn("externalTarget", rels["relationship-order-api-calls-ldap-directory.yaml"])  # left for input
        out = ws.validate()
        self.assertNotIn("[relationship-flow-deprecated]", out)
        self.assertNotIn("[relationship-source-is-listener-side]", out)

    def test_runs_are_deterministic(self) -> None:
        ws = Workspace(self, LEGACY)
        self.assertEqual(ws.run(), ws.run())

    def test_output_inside_the_catalog_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            mr.main(["--workspace", str(LEGACY), "--patch", str(LEGACY / "catalog" / "x.patch")])
        self.assertFalse((LEGACY / "catalog" / "x.patch").exists())


class ExternalTargetTests(unittest.TestCase):
    def build(self, *extra: tuple[str, dict], **rel_fields: object) -> Workspace:
        ws = Workspace(self)
        write(ws.root, "catalog/engineering/product-components/checkout.yaml", component())
        write(ws.root, "catalog/governance/relationships/rel.yaml", relationship(externalTarget="Stripe", **rel_fields))
        for path, doc in extra:
            write(ws.root, path, doc)
        return ws

    def test_new_system_and_stub_listener_validate_after_apply(self) -> None:
        ws = self.build()
        report, patch = ws.run()
        self.assertIn("externalTarget 'Stripe' -> target", report)
        self.assertIn("catalog/governance/systems/system-stripe.yaml", report)
        self.assertIn("catalog/engineering/listeners/listener-stripe-https-443.yaml", report)
        ws.apply(patch)
        rel = yaml.safe_load((ws.root / "catalog/governance/relationships/rel.yaml").read_text(encoding="utf-8"))
        system = yaml.safe_load((ws.root / "catalog/governance/systems/system-stripe.yaml").read_text(encoding="utf-8"))
        listener = yaml.safe_load((ws.root / "catalog/engineering/listeners/listener-stripe-https-443.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("externalTarget", rel)
        self.assertEqual((rel["target"], rel["targetListener"]), (system["uid"], listener["uid"]))
        self.assertEqual((system["type"], system["catalogStatus"]), ("system", "stub"))
        self.assertEqual((listener["owner"], listener["protocol"], listener["port"], listener["catalogStatus"]),
                         ({"kind": "external_system", "ref": system["uid"]}, "HTTPS", 443, "stub"))
        out = ws.validate()
        for rule in ("relationship-external-target-freetext", "relationship-target-listener", "listener-owner"):
            self.assertNotIn(f"[{rule}]", out, rule)

    def test_existing_system_by_alias_and_existing_listener_are_reused(self) -> None:
        system = {"schemaVersion": "1.0", "uid": VENDOR_SYS, "type": "system", "name": "Stripe Inc", "aliases": ["Stripe"],
                  "catalogStatus": "complete", "lifecycleStatus": "preferred"}
        listener = {"schemaVersion": "1.0", "uid": "01M7D0AA04-LS01", "type": "listener", "name": "Stripe API",
                    "owner": {"kind": "external_system", "ref": VENDOR_SYS}, "protocol": "HTTPS", "port": 443, "endpoint": "/",
                    "authenticationModel": "api-key", "catalogStatus": "complete"}
        ws = self.build(("catalog/governance/systems/stripe.yaml", system), ("catalog/engineering/listeners/stripe.yaml", listener))
        planner = mr.propose(ws.root)
        self.assertEqual(planner.new_files, {})
        (item,) = [i for i in planner.items if i.kind == "external-target"]
        self.assertIn(f"target {VENDOR_SYS}, targetListener 01M7D0AA04-LS01", item.summary)

    def test_ambiguous_system_names_ask(self) -> None:
        twins = [{"schemaVersion": "1.0", "uid": uid, "type": "system", "name": "Stripe", "catalogStatus": "complete",
                  "lifecycleStatus": "preferred"} for uid in ("01M7D0AA05-SYS2", "01M7D0AA06-SYS3")]
        ws = self.build(("catalog/governance/systems/a.yaml", twins[0]), ("catalog/governance/systems/b.yaml", twins[1]))
        planner = mr.propose(ws.root)
        (item,) = planner.items
        self.assertEqual(item.kind, "needs-input")
        self.assertIn("several match", item.summary)
        self.assertEqual((planner.edits, planner.new_files), ({}, {}))

    def test_vendor_stub_needs_an_internal_caller(self) -> None:
        ws = self.build()
        runtime = {"schemaVersion": "1.0", "uid": CALLER, "type": "runtime_service", "name": "Runtime"}
        write(ws.root, "catalog/engineering/product-components/checkout.yaml", runtime)
        planner = mr.propose(ws.root)
        (item,) = planner.items
        self.assertIn("needs a company-internal caller", item.summary)
        self.assertEqual((planner.edits, planner.new_files), ({}, {}))

    def test_two_callers_share_one_new_system_and_listener(self) -> None:
        ws = self.build(("catalog/governance/relationships/rel2.yaml", relationship("01M7D0AA07-RS02", externalTarget="stripe")))
        planner = mr.propose(ws.root)
        self.assertEqual(len(planner.new_files), 2)
        self.assertEqual([i.kind for i in planner.items], ["external-target", "external-target"])


class ScopeAndReportTests(unittest.TestCase):
    def test_scope_by_object_sdp_and_folder(self) -> None:
        ws = Workspace(self, LEGACY)
        by_object = {i.uid for i in mr.propose(ws.root, obj_uid="01M7C4AA01-WEB1").items}
        self.assertEqual(by_object, {"01M7C4AA03-RS01", "01M7C4AA04-RS02"})
        sdp = {"schemaVersion": "1.0", "uid": "01M7D0AA08-SDP1", "type": "software_deployment_pattern", "name": "P",
               "serviceGroups": [{"name": "G", "deployableObjects": [{"ref": "01M7C4AA02-AP01"}]}]}
        write(ws.root, "catalog/engineering/sdp.yaml", sdp)
        by_sdp = {i.uid for i in mr.propose(ws.root, sdp_uid="01M7D0AA08-SDP1").items}
        self.assertEqual(by_sdp, {"01M7C4AA03-RS01", "01M7C4AA04-RS02", "01M7C4AA05-RS03", "01M7C4AA06-RS04"})
        self.assertEqual(mr.propose(ws.root, folder="catalog/product-components").items, [])
        self.assertEqual(len({i.uid for i in mr.propose(ws.root, folder="catalog/relationships").items}), 4)

    def test_multi_object_files_are_reported_not_patched(self) -> None:
        ws = Workspace(self)
        docs = [component(), relationship(flow="bidirectional", target=CALLER)]
        (ws.root / "catalog" / "many.yaml").write_text(yaml.safe_dump(docs, sort_keys=False), encoding="utf-8")
        planner = mr.propose(ws.root)
        (item,) = planner.items
        self.assertEqual(item.kind, "needs-input")
        self.assertIn("several objects", item.summary)
        self.assertEqual(planner.patch(), "")

    def test_protection_descriptions_are_reported(self) -> None:
        ws = Workspace(self)
        write(ws.root, "catalog/c.yaml", component())
        write(ws.root, "catalog/r1.yaml", relationship("01M7D0AA09-RS03", target=CALLER, label="is fronted by the WAF"))
        write(ws.root, "catalog/r2.yaml", relationship("01M7D0AA0A-RS04", target=CALLER, label="authenticates via"))
        items = mr.propose(ws.root).items
        self.assertEqual([(i.kind, i.uid) for i in items], [("protection", "01M7D0AA09-RS03")])

    def test_json_output(self) -> None:
        ws = Workspace(self, LEGACY)
        planner = mr.propose(ws.root)
        data = planner.as_json()
        self.assertEqual(data["deletedFiles"], ["catalog/relationships/relationship-internet-calls-order-api.yaml"])
        self.assertEqual(len(data["changedFiles"]), 2)


class ExternalOwnerLookupTests(unittest.TestCase):
    def test_external_system_owner_resolves_a_system_object(self) -> None:
        objects = {"S": {"uid": "S", "type": "system", "name": "Vendor"}, "P": {"uid": "P", "type": "product_component", "name": "App"}}
        self.assertEqual(resolve_listener_owner(objects, "external_system", "Vendor"), {"status": "linked", "uid": "S"})
        result = link_or_stub_listener(objects, "external_system", "Vendor", "https", None, "/", source_uid="P")
        self.assertEqual((result["action"], result["stub"]["owner"]), ("created", {"kind": "external_system", "ref": "S"}))


if __name__ == "__main__":
    unittest.main()
