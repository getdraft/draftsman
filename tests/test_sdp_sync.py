"""#195 S1.1: pack a product repository, receive it into a central workspace, and validate the result."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "framework" / "tools"
sys.path.insert(0, str(TOOLS))

import sdp_sync  # noqa: E402
from tests import sdp_sync_identity as identity  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "sdp_sync"
REPOSITORY = "example-org/absence-service"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
SLUG = "example-org__absence-service"


class Fixture:
    def __init__(self, test: unittest.TestCase) -> None:
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.product = self.tmp / "product_repo"
        self.central = self.tmp / "central_workspace"
        shutil.copytree(FIXTURES / "product_repo", self.product)
        shutil.copytree(FIXTURES / "central_workspace", self.central)

    def pack(self, **kw) -> dict:
        return sdp_sync.pack(self.product, REPOSITORY, COMMIT, "refs/heads/main", correlation_id="run-1", **kw)

    def cache(self) -> Path:
        return self.central / ".draft" / "external_sdps" / SLUG

    def validate(self) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(TOOLS / "validate.py"), "--workspace", str(self.central)],
                              capture_output=True, text=True, check=False)
        return proc.returncode, proc.stdout + proc.stderr


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / "sdp_sync.py"), *args], capture_output=True, text=True, check=False)


class RoundTripTests(unittest.TestCase):
    def test_cli_round_trip_stores_yaml_that_validates(self) -> None:
        fx = Fixture(self)
        payload_file = fx.tmp / "payload.json"
        packed = run_cli("pack", "--repo-root", str(fx.product), "--repository", REPOSITORY, "--commit", COMMIT,
                         "--ref", "refs/heads/main", "--correlation-id", "run-1", "--output", str(payload_file))
        self.assertEqual(packed.returncode, 0, packed.stderr)
        # The receiver gets the payload inside a GitHub event file.
        event = fx.tmp / "event.json"
        # pack without --central-repository attaches no token (there is no runner here); sign it as GitHub would.
        signed = identity.sign(json.loads(payload_file.read_text()))
        event.write_text(json.dumps({"action": "sdp_updated", "client_payload": signed}), encoding="utf-8")
        result_file = fx.tmp / "result.json"
        received = run_cli("receive", "--workspace", str(fx.central), "--payload", str(event), "--central-repository", identity.CENTRAL,
                           "--jwks", str(identity.write_jwks(fx.tmp / "jwks.json")), "--result", str(result_file))
        self.assertEqual(received.returncode, 0, received.stderr)

        stored = fx.cache() / "sdp.yaml"
        original = (fx.product / ".draft" / "sdp.yaml").read_text(encoding="utf-8")
        self.assertEqual(stored.read_text(encoding="utf-8"), original)  # byte-for-byte, apostrophe included
        self.assertIsInstance(yaml.safe_load(stored.read_text(encoding="utf-8")), dict)  # YAML, not a quoted JSON string
        self.assertIn("It's quoted", original)
        result = json.loads(result_file.read_text())
        self.assertEqual((result["status"], result["product"], result["correlationId"]), ("accepted", SLUG, "run-1"))
        self.assertEqual(result["written"], [f".draft/external_sdps/{SLUG}/sdp.yaml"])
        self.assertNotIn(signed["oidcToken"], result_file.read_text() + received.stdout + received.stderr)
        code, out = fx.validate()
        self.assertEqual(code, 0, out)
        self.assertIn(f"external_sdps/{SLUG}/sdp.yaml", out)

    def test_the_old_payload_shape_would_have_stored_a_quoted_string(self) -> None:
        # Gap 1 of #195: `jq -s -R .` makes a JSON string and toJson() quotes it again, so the file held a string.
        text = (FIXTURES / "product_repo" / ".draft" / "sdp.yaml").read_text(encoding="utf-8")
        legacy_file_text = json.dumps(json.dumps(text))
        self.assertIsInstance(yaml.safe_load(legacy_file_text), str)
        result = identity.receive(Fixture(self).central, {"product_id": REPOSITORY, "sdp_content": text})
        self.assertEqual(result.status, "rejected")
        self.assertIn("old sdp_content format", result.message)

    def test_a_resync_replaces_the_snapshot_and_drops_the_legacy_flat_file(self) -> None:
        fx = Fixture(self)
        legacy = fx.central / ".draft" / "external_sdps" / "example-org_absence-service.yaml"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("old: true\n", encoding="utf-8")
        stale = fx.cache() / "catalog" / "stale.yaml"
        stale.parent.mkdir(parents=True)
        stale.write_text("type: product_component\n", encoding="utf-8")
        result = identity.receive(fx.central, fx.pack())
        self.assertEqual(result.status, "accepted", result.message)
        self.assertFalse(legacy.exists())
        self.assertFalse(stale.exists())
        self.assertIn(".draft/external_sdps/example-org_absence-service.yaml", result.removed)

    def test_a_missing_sdp_packs_and_receives_a_delete(self) -> None:
        fx = Fixture(self)
        self.assertEqual(identity.receive(fx.central, fx.pack()).status, "accepted")
        (fx.product / ".draft" / "sdp.yaml").unlink()
        payload = fx.pack()
        self.assertEqual((payload["action"], payload["files"]), ("delete", {}))
        result = identity.receive(fx.central, payload)
        self.assertEqual(result.status, "accepted", result.message)
        self.assertFalse(fx.cache().exists())
        self.assertEqual(result.removed, [f".draft/external_sdps/{SLUG}/sdp.yaml"])


class PayloadLimitTests(unittest.TestCase):
    def test_pack_refuses_an_oversized_payload(self) -> None:
        fx = Fixture(self)
        sdp = fx.product / ".draft" / "sdp.yaml"
        sdp.write_text(sdp.read_text(encoding="utf-8") + "notes:\n  big: " + "x" * 70_000 + "\n", encoding="utf-8")
        with self.assertRaisesRegex(sdp_sync.SyncError, "at most 65000"):
            fx.pack()
        self.assertEqual(run_cli("pack", "--repo-root", str(fx.product), "--repository", REPOSITORY, "--commit", COMMIT,
                                 "--ref", "refs/heads/main", "--output", str(fx.tmp / "p.json")).returncode, 1)

    def test_payload_fits_repository_dispatch_limits(self) -> None:
        payload = identity.sign(Fixture(self).pack())
        self.assertLessEqual(len(payload), sdp_sync.MAX_TOP_LEVEL_PROPERTIES)
        self.assertLess(len(json.dumps(payload).encode()), 65_536)


class RejectionTests(unittest.TestCase):
    def reject(self, fx: Fixture, payload: dict, expected: str) -> None:
        result = identity.receive(fx.central, payload)
        self.assertEqual(result.status, "rejected", payload)
        self.assertIn(expected, result.message)
        self.assertFalse((fx.central / ".draft" / "external_sdps").exists(), "nothing is written on rejection")

    def test_malformed_payloads_are_rejected_with_a_reason(self) -> None:
        fx = Fixture(self)
        good = fx.pack()
        cases = [
            ({**good, "format": "draft-sdp-sync/9"}, "unsupported payload format"),
            ({**good, "repository": "../etc"}, "not a GitHub repository name"),
            ({**good, "repository": "a/b; rm -rf /"}, "not a GitHub repository name"),
            ({**good, "commit": "$(id)"}, "not a git commit SHA"),
            ({**good, "ref": "main"}, "not a git ref"),
            ({**good, "action": "merge"}, "action must be one of"),
            ({**good, "correlationId": "a b"}, "correlationId"),
            ({**good, "files": {}}, "an upsert must include .draft/sdp.yaml"),
            ({**good, "action": "delete"}, "a delete carries no files"),
            ({**good, "files": {".draft/sdp.yaml": "schemaVersion: [unclosed"}}, "not valid YAML"),
            ({**good, "files": {".draft/sdp.yaml": json.dumps("type: x")}}, "not a DRAFT object"),
            ({**good, "files": {".draft/sdp.yaml": "type: product_component\n"}}, "must be a software_deployment_pattern"),
        ]
        for payload, expected in cases:
            with self.subTest(expected):
                self.reject(fx, payload, expected)

    def test_paths_outside_the_product_cache_are_refused(self) -> None:
        fx = Fixture(self)
        good = fx.pack()
        for path in ("../catalog/x.yaml", "/etc/passwd", ".draft/catalog/../../catalog/x.yaml", "catalog/x.yaml",
                     ".draft/workspace.yaml", ".draft/catalog/x.txt", ".github/workflows/x.yaml", ".draft\\catalog\\x.yaml"):
            with self.subTest(path):
                self.reject(fx, {**good, "files": {**good["files"], path: "type: product_component\n"}}, "refusing path")

    def test_cli_reports_rejection_with_exit_code_and_result_file(self) -> None:
        fx = Fixture(self)
        bad = fx.tmp / "bad.json"
        bad.write_text(json.dumps({"client_payload": {"format": "nope"}}), encoding="utf-8")
        out = run_cli("receive", "--workspace", str(fx.central), "--payload", str(bad), "--central-repository", identity.CENTRAL,
                      "--result", str(fx.tmp / "r.json"))
        self.assertEqual(out.returncode, 1)
        self.assertIn("rejected", out.stderr)
        self.assertEqual(json.loads((fx.tmp / "r.json").read_text())["status"], "rejected")
        unreadable = run_cli("receive", "--workspace", str(fx.central), "--payload", str(fx.tmp / "missing.json"),
                             "--central-repository", identity.CENTRAL)
        self.assertEqual(unreadable.returncode, 1)
        self.assertIn("cannot read the payload file", unreadable.stderr)



def component(uid: str, name: str, **fields: object) -> str:
    return yaml.safe_dump({"schemaVersion": "1.0", "uid": uid, "type": "product_component", "name": name,
                           "repoUrl": f"https://github.com/{REPOSITORY}", "owner": {"team": "absence"},
                           "classification": "worker", "catalogStatus": "stub", "lifecycleStatus": "candidate", **fields}, sort_keys=False)


WORKER = "01M7SYNC0D-PC04"
CONFIG_UID = "01KSWVZSZ5-71PY"  # defined in framework/configurations, which every workspace resolves


class ProductCatalogTests(unittest.TestCase):
    """#195 S2.3: .draft/catalog/ objects travel with the SDP, and every reference must resolve."""

    def add(self, fx: Fixture, rel: str, text: str) -> Path:
        path = fx.product / ".draft" / "catalog" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_pack_includes_catalog_yaml_and_receive_stores_it_in_the_product_cache(self) -> None:
        fx = Fixture(self)
        self.add(fx, "components/worker.yaml", component(WORKER, "Absence Worker", dependsOn=["01M7SYNC02-PC01"]))
        self.add(fx, "README.md", "not synced\n")
        self.add(fx, "notes.txt", "not synced\n")
        payload = fx.pack()
        self.assertEqual(sorted(payload["files"]), [".draft/catalog/components/worker.yaml", ".draft/sdp.yaml"])
        result = identity.receive(fx.central, payload)
        self.assertEqual(result.status, "accepted", result.message)
        self.assertEqual(sorted(result.written), [f".draft/external_sdps/{SLUG}/catalog/components/worker.yaml",
                                                  f".draft/external_sdps/{SLUG}/sdp.yaml"])
        self.assertEqual((fx.cache() / "catalog" / "components" / "worker.yaml").read_text(encoding="utf-8"),
                         (fx.product / ".draft" / "catalog" / "components" / "worker.yaml").read_text(encoding="utf-8"))
        code, out = fx.validate()
        self.assertEqual(code, 0, out)

    def test_the_sdp_may_place_a_component_from_the_same_sync(self) -> None:
        fx = Fixture(self)
        self.add(fx, "worker.yaml", component(WORKER, "Absence Worker"))
        sdp = fx.product / ".draft" / "sdp.yaml"
        sdp.write_text(sdp.read_text(encoding="utf-8") + f"  - ref: {WORKER}\n    diagramTier: application\n", encoding="utf-8")
        self.assertEqual(identity.receive(fx.central, fx.pack()).status, "accepted")

    def test_an_unresolved_reference_is_refused_and_named(self) -> None:
        fx = Fixture(self)
        self.add(fx, "worker.yaml", component(WORKER, "Absence Worker", dependsOn=["01M7SYNC0E-PC99", "01M7SYNC02-PC01"]))
        sdp = fx.product / ".draft" / "sdp.yaml"
        sdp.write_text(sdp.read_text(encoding="utf-8") + "  - ref: 01M7SYNC0F-PC98\n", encoding="utf-8")
        result = identity.receive(fx.central, fx.pack())
        self.assertEqual(result.status, "rejected")
        self.assertIn("unresolved references", result.message)
        self.assertIn(".draft/catalog/worker.yaml references 01M7SYNC0E-PC99", result.message)
        self.assertIn(".draft/sdp.yaml references 01M7SYNC0F-PC98", result.message)
        self.assertNotIn("01M7SYNC02-PC01", result.message, "central catalog references resolve")
        self.assertFalse(fx.cache().exists())

    def test_references_resolve_against_configurations_and_other_products(self) -> None:
        fx = Fixture(self)
        other = fx.central / ".draft" / "external_sdps" / "example-org__payroll-service" / "catalog" / "pay.yaml"
        other.parent.mkdir(parents=True)
        other.write_text(component("01M7SYNC0G-PC05", "Payroll"), encoding="utf-8")
        self.add(fx, "worker.yaml", component(WORKER, "Absence Worker", dependsOn=["01M7SYNC0G-PC05"], capabilities=[CONFIG_UID]))
        result = identity.receive(fx.central, fx.pack())
        self.assertEqual(result.status, "accepted", result.message)

    def test_the_products_previous_snapshot_does_not_resolve_references(self) -> None:
        fx = Fixture(self)
        worker = self.add(fx, "worker.yaml", component(WORKER, "Absence Worker"))
        self.add(fx, "helper.yaml", component("01M7SYNC0H-PC06", "Helper", dependsOn=[WORKER]))
        self.assertEqual(identity.receive(fx.central, fx.pack()).status, "accepted")
        worker.unlink()  # helper still points at the worker, which this sync no longer carries
        result = identity.receive(fx.central, fx.pack())
        self.assertEqual(result.status, "rejected")
        self.assertIn(f".draft/catalog/helper.yaml references {WORKER}", result.message)
        self.assertTrue((fx.cache() / "catalog" / "worker.yaml").exists(), "a rejected sync leaves the last snapshot")

    def test_a_resync_drops_catalog_files_the_product_removed(self) -> None:
        fx = Fixture(self)
        worker = self.add(fx, "worker.yaml", component(WORKER, "Absence Worker"))
        self.assertEqual(identity.receive(fx.central, fx.pack()).status, "accepted")
        worker.unlink()
        result = identity.receive(fx.central, fx.pack())
        self.assertEqual(result.status, "accepted", result.message)
        self.assertEqual(result.removed, [f".draft/external_sdps/{SLUG}/catalog/worker.yaml"])
        self.assertFalse((fx.cache() / "catalog").exists())

    def test_a_missing_sdp_deletes_every_cached_file_even_with_catalog_files_left(self) -> None:
        fx = Fixture(self)
        self.add(fx, "worker.yaml", component(WORKER, "Absence Worker"))
        self.add(fx, "nested/helper.yaml", component("01M7SYNC0H-PC06", "Helper"))
        self.assertEqual(identity.receive(fx.central, fx.pack()).status, "accepted")
        (fx.product / ".draft" / "sdp.yaml").unlink()
        payload = fx.pack()
        self.assertEqual((payload["action"], payload["files"]), ("delete", {}))
        result = identity.receive(fx.central, payload)
        self.assertEqual(result.status, "accepted", result.message)
        self.assertEqual(result.removed, sorted([f".draft/external_sdps/{SLUG}/sdp.yaml", f".draft/external_sdps/{SLUG}/catalog/worker.yaml",
                                                 f".draft/external_sdps/{SLUG}/catalog/nested/helper.yaml"]))
        self.assertFalse(fx.cache().exists())

    def test_pack_refuses_central_types_hidden_paths_and_symlinks(self) -> None:
        fx = Fixture(self)
        system = self.add(fx, "system.yaml", yaml.safe_dump({"uid": "01M7SYNC0J-SY01", "type": "system", "name": "x"}))
        with self.assertRaisesRegex(sdp_sync.SyncError, "cannot sync a 'system' object"):
            fx.pack()
        system.unlink()
        hidden = self.add(fx, ".hidden/x.yaml", component(WORKER, "Hidden"))
        with self.assertRaisesRegex(sdp_sync.SyncError, "refusing path"):
            fx.pack()
        hidden.unlink()
        outside = fx.tmp / "outside.yaml"
        outside.write_text(component(WORKER, "Outside"), encoding="utf-8")
        (fx.product / ".draft" / "catalog" / "link.yaml").symlink_to(outside)
        with self.assertRaisesRegex(sdp_sync.SyncError, "cannot be symbolic links"):
            fx.pack()
        (fx.product / ".draft" / "catalog" / "link.yaml").unlink()
        (fx.product / ".draft" / "catalog" / "linked-dir").symlink_to(fx.tmp, target_is_directory=True)
        with self.assertRaisesRegex(sdp_sync.SyncError, "cannot be symbolic links"):
            fx.pack()

    def test_pack_refuses_an_unreadable_catalog_object(self) -> None:
        fx = Fixture(self)
        self.add(fx, "broken.yaml", "uid: [unclosed\n")
        with self.assertRaisesRegex(sdp_sync.SyncError, "broken.yaml is not valid YAML"):
            fx.pack()

    def test_references_are_collected_like_validate(self) -> None:
        import validate
        obj = {"uid": WORKER, "a": [{"ref": "01M7SYNC02-PC01"}, "01M7SYNC0E-PC99 in prose", "not-a-uid"], "b": {"c": CONFIG_UID}}
        theirs: set[str] = set()
        validate.extract_referenced_uids(obj, theirs)
        self.assertEqual(sdp_sync.referenced_uids(obj, set()), theirs)
        self.assertEqual(theirs, {WORKER, "01M7SYNC02-PC01", CONFIG_UID})


class FixtureTests(unittest.TestCase):
    def test_fixture_central_workspace_registers_the_product(self) -> None:
        regs = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in (FIXTURES / "central_workspace").rglob("*.yaml")]
        urls = [r["repository"]["url"] for r in regs if r.get("type") == "product_registration"]
        self.assertEqual(urls, [f"https://github.com/{REPOSITORY}"])


if __name__ == "__main__":
    unittest.main()
