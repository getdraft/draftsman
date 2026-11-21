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


class FixtureTests(unittest.TestCase):
    def test_fixture_central_workspace_registers_the_product(self) -> None:
        regs = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in (FIXTURES / "central_workspace").rglob("*.yaml")]
        urls = [r["repository"]["url"] for r in regs if r.get("type") == "product_registration"]
        self.assertEqual(urls, [f"https://github.com/{REPOSITORY}"])


if __name__ == "__main__":
    unittest.main()
