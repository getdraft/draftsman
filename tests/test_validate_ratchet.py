"""Validation ratchet (plan decision D49): baseline file, --write-baseline, --no-baseline.

Each test builds a small temp workspace and runs validate.py as a subprocess. The
test-only ratcheted rule `ratchet-test-marker` fires on `xRatchetTest: fail`.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, List, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATE = REPO_ROOT / "framework" / "tools" / "validate.py"
RULE = "ratchet-test-marker"
UID_A = "01M7C497MS-MSDM"
UID_B = "01M7C497MT-MSDN"


def _domain(uid: str, name: str, fail: bool) -> str:
    doc: dict[str, Any] = {"schemaVersion": "1.0", "uid": uid, "type": "domain", "name": name}
    if fail:
        doc["xRatchetTest"] = "fail"
    return yaml.safe_dump(doc, sort_keys=True)


class RatchetTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name)
        (self.ws / "catalog").mkdir()
        self.baseline = self.ws / ".draft" / "validation-baseline.yaml"

    def put(self, uid: str, name: str = "Fx Domain", fail: bool = True) -> Path:
        path = self.ws / "catalog" / f"{uid}.yaml"
        path.write_text(_domain(uid, name, fail), encoding="utf-8")
        return path

    def run_validate(self, *flags: str) -> Tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, str(VALIDATE), "--workspace", str(self.ws), *flags],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout + proc.stderr

    def entries(self) -> List[dict]:
        return yaml.safe_load(self.baseline.read_text(encoding="utf-8"))["entries"]

    def test_write_baseline_then_plain_run_warns_and_exits_zero(self) -> None:
        self.put(UID_A)
        code, _ = self.run_validate("--write-baseline")
        self.assertEqual(0, code)
        data = yaml.safe_load(self.baseline.read_text(encoding="utf-8"))
        self.assertEqual("1.0", data["schemaVersion"])
        self.assertTrue(data["frameworkVersion"])
        self.assertEqual(1, len(data["entries"]))
        entry = data["entries"][0]
        self.assertEqual({"rule", "uid", "hash"}, set(entry))
        self.assertEqual((RULE, UID_A), (entry["rule"], entry["uid"]))
        self.assertEqual(64, len(entry["hash"]))
        code, out = self.run_validate()
        self.assertEqual(0, code, out)
        self.assertIn("baseline:", out)
        self.assertNotIn("Validation failures", out)

    def test_baseline_file_is_deterministic_and_sorted(self) -> None:
        self.put(UID_B)
        self.put(UID_A)
        self.run_validate("--write-baseline")
        first = self.baseline.read_text(encoding="utf-8")
        self.assertEqual([UID_A, UID_B], [e["uid"] for e in self.entries()])
        self.run_validate("--write-baseline")
        self.assertEqual(first, self.baseline.read_text(encoding="utf-8"))

    def test_changed_object_becomes_error_and_fixed_object_empties_entries(self) -> None:
        path = self.put(UID_A)
        self.run_validate("--write-baseline")
        self.put(UID_A, name="Renamed")
        code, out = self.run_validate()
        self.assertEqual(1, code)
        self.assertIn("Validation failures", out)
        self.assertIn(RULE, out)
        self.assertNotIn("baseline: ", out.split("Validation failures")[0])
        path.write_text(_domain(UID_A, "Renamed", False), encoding="utf-8")
        code, _ = self.run_validate("--write-baseline")
        self.assertEqual(0, code)
        self.assertEqual([], self.entries())

    def test_second_violating_object_without_entry_is_an_error(self) -> None:
        self.put(UID_A)
        self.run_validate("--write-baseline")
        self.put(UID_B)
        code, out = self.run_validate()
        self.assertEqual(1, code)
        failures = out.split("Validation failures:")[1].split("Validation warnings:")[0]
        self.assertIn(UID_B, failures)
        self.assertNotIn(UID_A, failures)
        self.assertEqual([UID_A], [e["uid"] for e in self.entries()])

    def test_no_baseline_makes_every_violation_an_error(self) -> None:
        self.put(UID_A)
        self.put(UID_B)
        self.run_validate("--write-baseline")
        code, out = self.run_validate("--no-baseline")
        self.assertEqual(1, code)
        failures = out.split("Validation failures:")[1].split("Validation warnings:")[0]
        self.assertIn(UID_A, failures)
        self.assertIn(UID_B, failures)
        self.assertNotIn("baseline:", out)

    def test_stale_entry_warns_and_write_baseline_drops_it(self) -> None:
        self.put(UID_A)
        path_b = self.put(UID_B)
        self.run_validate("--write-baseline")
        path_b.unlink()  # object no longer exists
        self.put(UID_A)
        code, out = self.run_validate()
        self.assertEqual(0, code, out)
        self.assertIn("stale baseline entry", out)
        self.assertIn(UID_B, out)
        self.run_validate("--write-baseline")
        self.assertEqual([UID_A], [e["uid"] for e in self.entries()])
        # object that exists but no longer violates
        self.put(UID_A, fail=False)
        code, out = self.run_validate()
        self.assertEqual(0, code, out)
        self.assertIn("stale baseline entry", out)

    def test_no_baseline_file_changes_nothing_for_clean_workspace(self) -> None:
        self.put(UID_A, fail=False)
        code, out = self.run_validate()
        self.assertEqual(0, code, out)
        self.assertNotIn("baseline", out.lower())
        self.assertFalse(self.baseline.exists())

    def test_write_baseline_with_other_errors_writes_then_exits_one(self) -> None:
        self.put(UID_A)
        (self.ws / "catalog" / "bad.yaml").write_text(
            yaml.safe_dump({"schemaVersion": "1.0", "uid": "01M7C497MU-MSDP", "type": "domain"}), encoding="utf-8"
        )
        code, out = self.run_validate("--write-baseline")
        self.assertEqual(1, code)
        self.assertIn("Wrote 1 baseline entries", out)
        self.assertEqual([UID_A], [e["uid"] for e in self.entries()])
        self.assertIn("Validation failures:", out)
        self.assertIn("bad.yaml", out)
        self.assertNotIn(RULE, out.split("Validation failures:")[1].split("Validation warnings:")[0])
        self.assertIn("baseline:", out)

    def test_unparseable_object_blocks_write_baseline(self) -> None:
        self.put(UID_A)
        self.run_validate("--write-baseline")
        (self.ws / "catalog" / "broken.yaml").write_text("uid: [unclosed\n", encoding="utf-8")
        before = self.baseline.read_text(encoding="utf-8")
        code, out = self.run_validate("--write-baseline")
        self.assertEqual(1, code)
        self.assertIn("Refusing to write the baseline", out)
        self.assertIn("broken.yaml", out)
        self.assertEqual(before, self.baseline.read_text(encoding="utf-8"))

    def test_malformed_baseline_is_an_error(self) -> None:
        self.put(UID_A, fail=False)
        self.baseline.parent.mkdir(parents=True)
        self.baseline.write_text("entries: [unclosed\n", encoding="utf-8")
        code, out = self.run_validate()
        self.assertEqual(1, code)
        self.assertIn("validation baseline", out)
        self.baseline.write_text("entries: not-a-list\n", encoding="utf-8")
        code, _ = self.run_validate()
        self.assertEqual(1, code)

    def test_empty_baseline_file_means_no_entries(self) -> None:
        self.put(UID_A, fail=False)
        self.baseline.parent.mkdir(parents=True)
        for text in ("", "  \n\n"):
            self.baseline.write_text(text, encoding="utf-8")
            code, out = self.run_validate()
            self.assertEqual(0, code, out)
        self.put(UID_A)
        code, _ = self.run_validate()
        self.assertEqual(1, code)

    def test_duplicate_entries_are_an_error(self) -> None:
        self.put(UID_A)
        self.run_validate("--write-baseline")
        data = yaml.safe_load(self.baseline.read_text(encoding="utf-8"))
        data["entries"].append(dict(data["entries"][0]))
        self.baseline.write_text(yaml.safe_dump(data), encoding="utf-8")
        code, out = self.run_validate()
        self.assertEqual(1, code)
        self.assertIn("duplicate baseline entry", out)

    def test_missing_baseline_file_treats_violation_as_error(self) -> None:
        self.put(UID_A)
        code, _ = self.run_validate()
        self.assertEqual(1, code)

    def test_no_baseline_ignores_stale_entry(self) -> None:
        self.put(UID_A)
        self.run_validate("--write-baseline")
        self.put(UID_A, fail=False)
        code, out = self.run_validate("--no-baseline")
        self.assertEqual(0, code, out)
        self.assertNotIn("stale baseline entry", out)

    def test_hash_formula(self) -> None:
        self.put(UID_A)
        self.run_validate("--write-baseline")
        obj = yaml.safe_load((self.ws / "catalog" / f"{UID_A}.yaml").read_text(encoding="utf-8"))
        expected = hashlib.sha256(yaml.safe_dump(obj, sort_keys=True, allow_unicode=True).encode("utf-8")).hexdigest()
        self.assertEqual(expected, self.entries()[0]["hash"])

    def test_framework_version_comes_from_manifest_then_lock(self) -> None:
        manifest = yaml.safe_load((REPO_ROOT / "draft-framework.yaml").read_text(encoding="utf-8"))
        self.put(UID_A)
        self.run_validate("--write-baseline")
        data = yaml.safe_load(self.baseline.read_text(encoding="utf-8"))
        self.assertEqual(str(manifest["version"]), data["frameworkVersion"])
        sys.path.insert(0, str(REPO_ROOT / "framework" / "tools"))
        try:
            import validate  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        lock = self.ws / ".draft" / "framework.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("framework:\n  version: 9.8.7\n", encoding="utf-8")
        empty = self.ws / "nowhere"
        old = (validate.REPO_ROOT, validate.FRAMEWORK_ROOT)
        validate.REPO_ROOT = validate.FRAMEWORK_ROOT = empty
        try:
            self.assertEqual("9.8.7", validate.framework_version_text(self.ws))
        finally:
            validate.REPO_ROOT, validate.FRAMEWORK_ROOT = old


if __name__ == "__main__":
    unittest.main()
