"""Validation ratchet (plan decision D49): baseline file, --write-baseline, --no-baseline.

Each test builds a small temp workspace and runs validate.py as a subprocess. The
test-only ratcheted rule `ratchet-test-marker` fires on `xRatchetTest: fail`.
"""

from __future__ import annotations

import hashlib
import re
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
RULE_LISTENER = "relationship-target-listener"


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

    def test_rewriting_baseline_does_not_duplicate_entries(self) -> None:
        self.put(UID_A)
        self.run_validate("--write-baseline")
        self.run_validate("--write-baseline")
        self.assertEqual([UID_A], [e["uid"] for e in self.entries()])
        code, out = self.run_validate()
        self.assertEqual(0, code, out)
        self.assertNotIn("duplicate baseline entry", out)

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


class RelationshipTargetListenerTests(unittest.TestCase):
    COMP = "01M7C497MX-MSDS"
    DATA = "01M7C497MY-MSDT"
    OTHER = "01M7C497MZ-MSDU"
    LISTENER = "01M7C497MV-MSDQ"
    REL = "01M7C497MW-MSDR"

    def _validate(self) -> Any:
        sys.path.insert(0, str(REPO_ROOT / "framework" / "tools"))
        try:
            import validate  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        return validate

    def _violations(self, *objs: dict) -> List[Tuple]:
        validate = self._validate()
        objects = {Path(f"/ws/catalog/{i}.yaml"): o for i, o in enumerate(objs)}
        catalog = {o["uid"]: o for o in objs}
        found = validate.collect_ratchet_violations(objects, catalog)
        return [v for v in found if v[0] == "relationship-target-listener"]

    def _data(self) -> dict:
        return {"schemaVersion": "1.0", "uid": self.DATA, "type": "data_component", "name": "Orders Data"}

    def _other(self) -> dict:
        return {"schemaVersion": "1.0", "uid": self.OTHER, "type": "data_component", "name": "Other Data"}

    def _listener(self, owner_ref: str | None = None, endpoint: str = "/") -> dict:
        return {
            "schemaVersion": "1.0", "uid": self.LISTENER, "type": "listener", "name": "Orders SQL",
            "owner": {"kind": "data_component", "ref": owner_ref or self.DATA},
            "protocol": "SQL", "port": 5432, "endpoint": endpoint, "authenticationModel": "iam",
            "catalogStatus": "complete",
        }

    def _relationship(self, **changes: Any) -> dict:
        rel: dict = {
            "schemaVersion": "1.0", "uid": self.REL, "type": "relationship", "name": "Comp → Data",
            "source": self.COMP, "target": self.DATA, "label": "reads", "catalogStatus": "complete",
            "targetListener": self.LISTENER,
        }
        rel.update(changes)
        return {k: v for k, v in rel.items() if v is not None}

    def _component(self, dependencies: list) -> dict:
        return {
            "schemaVersion": "1.0", "uid": self.COMP, "type": "product_component", "name": "Comp",
            "runtimeSpec": {"dependencies": dependencies},
        }

    def test_valid_internal_target_is_clean(self) -> None:
        self.assertEqual([], self._violations(self._data(), self._listener(), self._relationship()))

    def test_listener_endpoint_variants_normalize_to_one_identity(self) -> None:
        validate = self._validate()
        base = validate.listener_identity(self._listener(endpoint="/orders/{id}"))
        variant = validate.listener_identity(self._listener(endpoint="https://API.Example.COM/orders/:orderId/"))
        self.assertEqual(base, variant)

    def test_missing_targetListener_fails(self) -> None:
        found = self._violations(self._data(), self._listener(), self._relationship(targetListener=None))
        self.assertEqual(1, len(found))
        self.assertIn("no targetListener", found[0][2])

    def test_unknown_listener_uid_fails(self) -> None:
        found = self._violations(self._data(), self._listener(), self._relationship(targetListener="01M7C497MQ-MSDK"))
        self.assertEqual(1, len(found))
        self.assertIn("names no listener object", found[0][2])

    def test_listener_owned_by_other_object_fails(self) -> None:
        found = self._violations(self._data(), self._other(), self._listener(owner_ref=self.OTHER), self._relationship())
        self.assertEqual(1, len(found))
        self.assertIn("not by its target", found[0][2])

    def test_external_target_needs_a_listener_but_no_owner_match(self) -> None:
        external = self._relationship(target=None, externalTarget="LDAP Directory")
        self.assertEqual([], self._violations(self._other(), self._listener(owner_ref=self.OTHER), external))
        found = self._violations(self._relationship(target=None, externalTarget="LDAP Directory", targetListener=None))
        self.assertEqual(1, len(found))

    def test_dependency_interface_must_resolve_to_a_listener_of_its_ref(self) -> None:
        deps = [{"ref": self.DATA, "purpose": "reads", "interface": self.LISTENER}]
        self.assertEqual([], self._violations(self._data(), self._listener(), self._component(deps)))
        found = self._violations(self._data(), self._other(), self._listener(owner_ref=self.OTHER), self._component(deps))
        self.assertEqual(1, len(found))
        self.assertIn("not by its ref", found[0][2])

    def test_protocol_disagreement_warns_but_does_not_ratchet(self) -> None:
        validate = self._validate()
        objs = [self._data(), self._listener()]
        catalog = {o["uid"]: o for o in objs}
        warnings: list[str] = []
        validate._warn_listener_protocol(self._relationship(technology="AMQP"), Path("rel.yaml"), catalog, warnings)
        self.assertEqual(1, len(warnings))
        self.assertIn("does not match listener", warnings[0])
        self.assertEqual([], self._violations(*objs, self._relationship(technology="AMQP")))
        warnings.clear()
        validate._warn_listener_protocol(
            self._relationship(technology="PostgreSQL wire protocol"), Path("rel.yaml"), catalog, warnings
        )
        self.assertEqual([], warnings)


class WorkspaceValidateTests(unittest.TestCase):
    """Shared temp workspace, validate.py runner, and parsed failure/warning records."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name)
        (self.ws / "catalog").mkdir()
        self.baseline = self.ws / ".draft" / "validation-baseline.yaml"

    def _run(self, *flags: str) -> str:
        proc = subprocess.run(
            [sys.executable, str(VALIDATE), "--workspace", str(self.ws), *flags],
            capture_output=True, text=True, check=False,
        )
        return proc.stdout + proc.stderr

    @staticmethod
    def _section(out: str, header: str) -> str:
        if header not in out:
            return ""
        text = out.split(header, 1)[1]
        for stop in ("Validation failures:", "Validation warnings:"):
            if stop != header and stop in text:
                text = text.split(stop, 1)[0]
        return text

    @classmethod
    def _failures(cls, out: str) -> str:
        return cls._section(out, "Validation failures:")

    @classmethod
    def _warnings(cls, out: str) -> str:
        return cls._section(out, "Validation warnings:")

    @staticmethod
    def _records(section: str) -> List[dict[str, str]]:
        """Parse '- path: ...' lines into {path, rule, uid, message, text}."""
        out: List[dict[str, str]] = []
        for line in section.splitlines():
            raw = line.strip()
            if not raw.startswith("- "):
                continue
            text = raw[2:]
            rec = {"text": text, "path": "", "rule": "", "uid": "", "message": text}
            m = re.match(
                r"^(?P<path>.+?): \[(?P<rule>[^\]]+)\] (?P<uid>\S+): (?P<message>.*)$",
                text,
            )
            if m:
                rec.update(m.groupdict())
            else:
                path, _, rest = text.partition(": ")
                rec["path"] = path
                rec["message"] = rest or text
            out.append(rec)
        return out

    @classmethod
    def _failure_records(cls, out: str) -> List[dict[str, str]]:
        return cls._records(cls._failures(out))

    @classmethod
    def _warning_records(cls, out: str) -> List[dict[str, str]]:
        return cls._records(cls._warnings(out))

    @staticmethod
    def _file_verdicts(out: str) -> dict[str, str]:
        """Map basename (e.g. listener.yaml) to PASS or FAIL from validator file lines."""
        verdicts: dict[str, str] = {}
        for line in out.splitlines():
            if line.startswith("PASS ") or line.startswith("FAIL "):
                status, _, path = line.partition(" ")
                verdicts[Path(path.strip()).name] = status
        return verdicts


class LegacyInterfaceBaselineTests(WorkspaceValidateTests):
    SYS = "01M7C497NA-SYS1"
    LST = "01M7C497NB-STB1"
    COMP = "01M7C497NC-CMP1"
    REL = "01M7C497ND-RSH1"

    def _write(self, **rel_changes: Any) -> None:
        rel: dict[str, Any] = {
            "schemaVersion": "1.0", "uid": self.REL, "type": "relationship", "name": "Comp to LDAP",
            "source": self.COMP, "externalTarget": "LDAP Directory", "label": "calls", "catalogStatus": "complete",
        }
        rel.update(rel_changes)
        rel = {key: value for key, value in rel.items() if value is not None}  # None drops a field (externalTarget)
        docs = {
            "system.yaml": {
                "schemaVersion": "1.0", "uid": self.SYS, "type": "system", "name": "Directory System",
                "catalogStatus": "complete", "lifecycleStatus": "preferred",
            },
            "listener.yaml": {
                "schemaVersion": "1.0", "uid": self.LST, "type": "listener", "name": "LDAP listener",
                "owner": {"kind": "external_system", "ref": self.SYS}, "protocol": "HTTPS", "port": 443,
                "endpoint": "/ldap", "authenticationModel": "oauth", "catalogStatus": "stub",
            },
            "component.yaml": {
                "schemaVersion": "1.0", "uid": self.COMP, "type": "product_component", "name": "Comp",
                "repoUrl": "https://github.com/test/comp", "owner": {"team": "test"},
                "classification": "api-service", "catalogStatus": "incomplete", "lifecycleStatus": "candidate",
                "interfaces": [{"name": "Orders API", "protocol": "REST", "path": "/orders"}],
            },
            "relationship.yaml": rel,
        }
        for name, doc in docs.items():
            (self.ws / "catalog" / name).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    def test_baseline_preserves_unchanged_relationship_as_warning(self) -> None:
        self._write()
        self._run("--write-baseline")
        entries = yaml.safe_load(self.baseline.read_text(encoding="utf-8"))["entries"]
        self.assertIn((RULE_LISTENER, self.REL), [(e["rule"], e["uid"]) for e in entries])
        out = self._run()
        self.assertNotIn(self.REL, self._failures(out))
        self.assertIn("baseline:", out)

    def test_changed_relationship_without_listener_is_an_error(self) -> None:
        self._write()
        self._run("--write-baseline")
        self._write(label="reads")
        out = self._run()
        self.assertIn(self.REL, self._failures(out))
        self.assertIn(RULE_LISTENER, self._failures(out))

    def test_changed_relationship_naming_external_listener_passes(self) -> None:
        self._write()
        self._run("--write-baseline")
        # Migrated as #368 asks: the system object is the target (free-text externalTarget is deprecated).
        self._write(label="reads", targetListener=self.LST, externalTarget=None, target=self.SYS)
        out = self._run()
        self.assertNotIn(self.REL, self._failures(out))

    def test_stub_listener_upgrade_keeps_relationship_valid(self) -> None:
        self._write(label="reads", targetListener=self.LST, externalTarget=None, target=self.SYS)
        self.assertNotIn(self.REL, self._failures(self._run()))
        listener_path = self.ws / "catalog" / "listener.yaml"
        listener = yaml.safe_load(listener_path.read_text(encoding="utf-8"))
        listener.update({"catalogStatus": "complete", "authenticationModel": "oauth", "description": "LDAP bind"})
        listener_path.write_text(yaml.safe_dump(listener, sort_keys=False), encoding="utf-8")
        out = self._run()
        failure_uids = [rec.get("uid") for rec in self._failure_records(out)]
        failure_rules = [rec.get("rule") for rec in self._failure_records(out)]
        self.assertNotIn(self.REL, failure_uids)
        self.assertNotIn(RULE_LISTENER, failure_rules)
        verdicts = self._file_verdicts(out)
        self.assertEqual("PASS", verdicts.get("listener.yaml"))
        self.assertEqual("PASS", verdicts.get("relationship.yaml"))
        passed_listener = next(
            (line.split(" ", 1)[1] for line in out.splitlines()
             if line.startswith("PASS ") and line.endswith("catalog/listener.yaml")),
            "",
        )
        self.assertEqual(str(listener_path), passed_listener)

    def test_legacy_interfaces_are_not_reported(self) -> None:
        self._write()
        self._run("--write-baseline")
        self.assertTrue(self.baseline.is_file())
        out = self._run()
        for rec in self._failure_records(out) + self._warning_records(out):
            on_component = self.COMP in rec.get("uid", "") or self.COMP in rec.get("path", "")
            about_interfaces = (
                rec.get("rule") == "interfaces"
                or re.search(r"\binterfaces\b", rec.get("message") or "") is not None
            )
            self.assertFalse(on_component and about_interfaces, rec)
        schema = yaml.safe_load(
            (REPO_ROOT / "framework" / "schemas" / "product-component.schema.yaml").read_text(encoding="utf-8")
        )
        self.assertIn("interfaces", schema["optionalFields"])
        self.assertEqual("interface", schema["collectionSchemas"]["interfaces"])


class InternalTargetBaselineTests(WorkspaceValidateTests):
    COMP = "01M7C497NE-CMP2"
    DATA = "01M7C497NF-DAT2"
    OTHER = "01M7C497NJ-DAT3"
    LST = "01M7C497NG-STB2"
    REL = "01M7C497NH-RSH2"

    def _write(self, listener_owner: Any = None, **rel_changes: Any) -> None:
        owner = listener_owner or self.DATA
        rel: dict[str, Any] = {
            "schemaVersion": "1.0", "uid": self.REL, "type": "relationship", "name": "Comp reads orders",
            "source": self.COMP, "target": self.DATA, "label": "reads", "catalogStatus": "complete",
        }
        rel.update(rel_changes)
        docs = {
            "component.yaml": {
                "schemaVersion": "1.0", "uid": self.COMP, "type": "product_component", "name": "Comp",
                "repoUrl": "https://github.com/test/comp", "owner": {"team": "test"},
                "classification": "api-service", "catalogStatus": "incomplete", "lifecycleStatus": "candidate",
            },
            "data.yaml": {"schemaVersion": "1.0", "uid": self.DATA, "type": "data_component", "name": "Orders Data"},
            "listener.yaml": {
                "schemaVersion": "1.0", "uid": self.LST, "type": "listener", "name": "Orders SQL",
                "owner": {"kind": "data_component", "ref": owner}, "protocol": "SQL", "port": 5432,
                "endpoint": "/", "authenticationModel": "iam", "catalogStatus": "complete",
            },
            "relationship.yaml": rel,
        }
        for name, doc in docs.items():
            (self.ws / "catalog" / name).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    def test_internal_target_baselined_then_changed_relationship_passes(self) -> None:
        self._write()
        self._run("--write-baseline")
        entries = yaml.safe_load(self.baseline.read_text(encoding="utf-8"))["entries"]
        self.assertIn((RULE_LISTENER, self.REL), [(e["rule"], e["uid"]) for e in entries])
        out = self._run()
        self.assertNotIn(self.REL, self._failures(out))
        self.assertIn("baseline:", out)
        self._write(label="uses", targetListener=self.LST)
        out = self._run()
        self.assertNotIn(self.REL, self._failures(out))

    def test_internal_listener_written_after_baseline_is_clean_and_unrecorded(self) -> None:
        self._write()
        self._run("--write-baseline")
        self._write(targetListener=self.LST)
        self._run("--write-baseline")
        entries = yaml.safe_load(self.baseline.read_text(encoding="utf-8"))["entries"]
        self.assertNotIn(self.REL, [e["uid"] for e in entries])
        out = self._run()
        self.assertNotIn(RULE_LISTENER, self._failures(out))
        self.assertNotIn(self.REL, self._failures(out))

    def test_internal_listener_owned_by_other_object_fails_after_baseline(self) -> None:
        self._write()
        self._run("--write-baseline")
        self._write(listener_owner=self.OTHER, label="uses", targetListener=self.LST)
        out = self._run()
        self.assertIn(self.REL, self._failures(out))
        self.assertIn(RULE_LISTENER, self._failures(out))


RULE_SDP_GATE = "sdp-internal-stub-listener"


class SdpCompletenessGateRatchetTests(WorkspaceValidateTests):
    """S2.4: the SDP gate is ratcheted on the pattern and its dependent objects, never on a framework upgrade alone."""

    SDP = "01M7C497P0-SDP4"
    WEB = "01M7C497P1-CMP4"
    ORDERS = "01M7C497P2-CMP5"
    OTHER = "01M7C497P3-CMP6"
    LST = "01M7C497P4-STB4"
    REL = "01M7C497P5-RSH4"
    REL2 = "01M7C497P6-RSH5"

    def setUp(self) -> None:
        super().setUp()
        self.docs: dict[str, dict[str, Any]] = {
            "web.yaml": {"schemaVersion": "1.0", "uid": self.WEB, "type": "product_component", "name": "Web",
                         "catalogStatus": "incomplete", "lifecycleStatus": "candidate"},
            "orders.yaml": {"schemaVersion": "1.0", "uid": self.ORDERS, "type": "product_component",
                            "name": "Orders", "catalogStatus": "incomplete", "lifecycleStatus": "candidate"},
            "other.yaml": {"schemaVersion": "1.0", "uid": self.OTHER, "type": "product_component",
                           "name": "Unrelated", "catalogStatus": "incomplete", "lifecycleStatus": "candidate"},
            "listener.yaml": {"schemaVersion": "1.0", "uid": self.LST, "type": "listener", "name": "Orders API",
                              "owner": {"kind": "product_component", "ref": self.ORDERS}, "protocol": "HTTPS",
                              "port": 443, "endpoint": "/orders", "authenticationModel": "TBD",
                              "catalogStatus": "stub"},
            "relationship.yaml": {"schemaVersion": "1.0", "uid": self.REL, "type": "relationship",
                                  "name": "Web to Orders", "source": self.WEB, "target": self.ORDERS,
                                  "targetListener": self.LST},
            "sdp.yaml": {"schemaVersion": "1.0", "uid": self.SDP, "type": "software_deployment_pattern",
                         "name": "Orders pattern", "catalogStatus": "complete",
                         "serviceGroups": [{"name": "App", "deployableObjects": [{"ref": self.WEB}]}]},
        }
        self._flush()

    def _flush(self) -> None:
        for name, doc in self.docs.items():
            (self.ws / "catalog" / name).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    def _gate(self, out: str) -> Tuple[List[dict[str, str]], List[dict[str, str]]]:
        failures = [r for r in self._failure_records(out) if r["rule"] == RULE_SDP_GATE]
        warnings = [r for r in self._warning_records(out) if r["rule"] == RULE_SDP_GATE]
        return failures, warnings

    def _assert_baselined(self, out: str) -> None:
        failures, warnings = self._gate(out)
        self.assertEqual([], failures, out)
        self.assertEqual([self.SDP], [r["uid"] for r in warnings], out)
        self.assertTrue(all(r["path"].startswith("baseline: ") for r in warnings), warnings)

    def _assert_rearmed(self, out: str) -> None:
        failures, _warnings = self._gate(out)
        self.assertEqual([self.SDP], [r["uid"] for r in failures], out)
        self.assertIn("Orders API", failures[0]["message"])

    def _baseline_and_check(self) -> None:
        self._run("--write-baseline")
        entries = yaml.safe_load(self.baseline.read_text(encoding="utf-8"))["entries"]
        self.assertIn((RULE_SDP_GATE, self.SDP), [(e["rule"], e["uid"]) for e in entries])
        self._assert_baselined(self._run())

    def test_without_baseline_the_gate_is_an_error(self) -> None:
        self._assert_rearmed(self._run())

    def test_unchanged_pattern_and_dependents_stay_baseline_warnings(self) -> None:
        self._baseline_and_check()
        self._assert_baselined(self._run())

    def test_framework_upgrade_alone_does_not_fail_unchanged_content(self) -> None:
        self._baseline_and_check()
        document = yaml.safe_load(self.baseline.read_text(encoding="utf-8"))
        document["frameworkVersion"] = "0.0.1"
        self.baseline.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        self._assert_baselined(self._run())

    def test_unrelated_object_change_keeps_baseline(self) -> None:
        self._baseline_and_check()
        self.docs["other.yaml"]["name"] = "Unrelated, renamed"
        self._flush()
        self._assert_baselined(self._run())

    def test_changed_pattern_rearms_the_gate(self) -> None:
        self._baseline_and_check()
        self.docs["sdp.yaml"]["description"] = "Edited pattern"
        self._flush()
        self._assert_rearmed(self._run())

    def test_changed_deployable_object_rearms_the_gate(self) -> None:
        self._baseline_and_check()
        self.docs["web.yaml"]["name"] = "Web frontend"
        self._flush()
        self._assert_rearmed(self._run())

    def test_changed_relationship_rearms_the_gate(self) -> None:
        self._baseline_and_check()
        self.docs["relationship.yaml"]["name"] = "Web calls Orders"
        self._flush()
        self._assert_rearmed(self._run())

    def test_new_call_from_the_pattern_rearms_the_gate(self) -> None:
        self._baseline_and_check()
        self.docs["relationship-2.yaml"] = {
            "schemaVersion": "1.0", "uid": self.REL2, "type": "relationship", "name": "Web to Orders again",
            "source": self.WEB, "target": self.ORDERS, "targetListener": self.LST,
        }
        self._flush()
        self._assert_rearmed(self._run())

    def test_changed_called_listener_rearms_the_gate(self) -> None:
        self._baseline_and_check()
        self.docs["listener.yaml"]["description"] = "Still a stub, now described"
        self._flush()
        self._assert_rearmed(self._run())

    def test_finished_listener_clears_the_gate(self) -> None:
        self._baseline_and_check()
        self.docs["listener.yaml"].update({"catalogStatus": "incomplete", "authenticationModel": "oauth"})
        self._flush()
        out = self._run()
        failures, warnings = self._gate(out)
        self.assertEqual([], failures, out)
        self.assertEqual([], warnings, out)


if __name__ == "__main__":
    unittest.main()
