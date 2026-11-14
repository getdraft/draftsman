"""Pattern ownership rules (plan decisions D50, D51) over temp workspaces.

The objects are minimal; other validation errors may appear in the output, so the
tests look at the rule id in the failure and warning lines, not only the exit code.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATE = REPO_ROOT / "framework" / "tools" / "validate.py"
PLACEMENT = "sdp-placement-types"
DEFINITION = "relationship-definition-endpoint"

SDP = "01M7C497MS-MSDM"
COMP = "01M7C497MT-MSDN"
DATA = "01M7C497MV-MSDP"
RUNTIME = "01M7C497MW-MSDQ"
STORE = "01M7C497MX-MSDR"
NET = "01M7C497MY-MSDS"
REL = "01M7C497MZ-MSDT"
EXT = "01M7C497N0-MSDV"


def _obj(uid: str, typ: str, name: str, **extra: Any) -> Dict[str, Any]:
    doc: Dict[str, Any] = {"schemaVersion": "1.0", "uid": uid, "type": typ, "name": name}
    doc.update(extra)
    return doc


class OwnershipRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name)
        (self.ws / "catalog").mkdir()

    def put(self, folder: str, obj: Dict[str, Any]) -> Path:
        directory = self.ws / "catalog" / folder
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (str(obj["uid"]) + ".yaml")
        path.write_text(yaml.safe_dump(obj, sort_keys=True), encoding="utf-8")
        return path

    def workspace_config(self, paths: Optional[Dict[str, Any]]) -> None:
        (self.ws / ".draft").mkdir(exist_ok=True)
        (self.ws / ".draft" / "workspace.yaml").write_text(
            yaml.safe_dump({"workspace": {"name": "fx"}, "paths": paths or {}}), encoding="utf-8"
        )

    def run_validate(self, *flags: str) -> Tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, str(VALIDATE), "--workspace", str(self.ws), *flags],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout + proc.stderr

    @staticmethod
    def rule_lines(out: str, rule: str, prefix: str = "- ") -> List[str]:
        return [
            line
            for line in out.splitlines()
            if line.startswith(prefix) and not line.startswith("- baseline:") and f"[{rule}]" in line
        ]

    @staticmethod
    def baseline_lines(out: str, rule: str) -> List[str]:
        return [line for line in out.splitlines() if line.startswith("- baseline:") and f"[{rule}]" in line]

    def put_pattern(self, refs: List[str]) -> None:
        self.put(
            "engineering",
            _obj(
                SDP,
                "software_deployment_pattern",
                "Fx Pattern",
                serviceGroups=[{"name": "Group One", "deployableObjects": [{"ref": ref} for ref in refs]}],
            ),
        )

    # AC32
    def test_placement_names_the_corrective_field_for_each_type(self) -> None:
        self.put("engineering", _obj(COMP, "product_component", "Fx Component"))
        self.put("engineering", _obj(DATA, "data_component", "Fx Data"))
        self.put("shared", _obj(RUNTIME, "runtime_service", "Fx Runtime"))
        self.put("shared", _obj(STORE, "data_store_service", "Fx Store"))
        self.put("shared", _obj(NET, "network_service", "Fx Edge"))
        self.put_pattern([COMP, DATA, RUNTIME, STORE, NET])
        code, out = self.run_validate()
        self.assertEqual(1, code)
        lines = self.rule_lines(out, PLACEMENT)
        self.assertEqual(1, len(lines), out)
        line = lines[0]
        self.assertIn("'Fx Runtime' (type: runtime_service", line)
        self.assertIn("runtime or host belongs in the service group's substrate", line)
        self.assertIn("'Fx Store' (type: data_store_service", line)
        self.assertIn("data store belongs in a data component's runsOn", line)
        self.assertIn("'Fx Edge' (type: network_service", line)
        self.assertIn("record a relationship from the consuming component, or rely on the reference architecture", line)
        self.assertNotIn("'Fx Component'", line)
        self.assertNotIn("'Fx Data'", line)

    def test_placement_ignores_components_and_unresolvable_refs(self) -> None:
        self.put("engineering", _obj(COMP, "product_component", "Fx Component"))
        self.put("engineering", _obj(DATA, "data_component", "Fx Data"))
        self.put_pattern([COMP, DATA, "01M7C497N1-MSDW"])
        _, out = self.run_validate()
        self.assertEqual([], self.rule_lines(out, PLACEMENT), out)

    def test_placement_violation_is_grandfathered_by_baseline(self) -> None:
        self.put("shared", _obj(RUNTIME, "runtime_service", "Fx Runtime"))
        self.put_pattern([RUNTIME])
        code, out = self.run_validate()
        self.assertEqual(1, len(self.rule_lines(out, PLACEMENT)), out)
        self.run_validate("--write-baseline")
        entries = yaml.safe_load((self.ws / ".draft" / "validation-baseline.yaml").read_text())["entries"]
        self.assertEqual([(PLACEMENT, SDP)], [(e["rule"], e["uid"]) for e in entries])
        _, out = self.run_validate()
        self.assertEqual([], self.rule_lines(out, PLACEMENT), out)
        self.assertTrue(self.baseline_lines(out, PLACEMENT), out)
        # Touching the pattern makes the violation bind again.
        self.put(
            "engineering",
            _obj(
                SDP,
                "software_deployment_pattern",
                "Fx Pattern Renamed",
                serviceGroups=[{"name": "Group One", "deployableObjects": [{"ref": RUNTIME}]}],
            ),
        )
        _, out = self.run_validate()
        self.assertEqual(1, len(self.rule_lines(out, PLACEMENT)), out)

    # AC33
    def put_relationship(self, source: str, target: str) -> None:
        self.put(
            "engineering",
            _obj(REL, "relationship", "Fx Flow", source=source, target=target, label="calls", catalogStatus="stub"),
        )

    def test_relationship_to_shared_services_object_fires_unless_instance(self) -> None:
        self.workspace_config({"catalogFolders": ["engineering", "shared-services"]})
        self.put("engineering", _obj(COMP, "product_component", "Fx Component"))
        self.put("shared-services", _obj(EXT, "runtime_service", "Fx Idp"))
        self.put_relationship(COMP, EXT)
        _, out = self.run_validate()
        lines = self.rule_lines(out, DEFINITION)
        self.assertEqual(1, len(lines), out)
        self.assertIn("a definition carries no flows", lines[0])
        self.assertIn("record the relationship on the component or instance", lines[0])
        self.assertIn("serviceRole: instance", lines[0])
        self.put("shared-services", _obj(EXT, "runtime_service", "Fx Idp", serviceRole="instance"))
        _, out = self.run_validate()
        self.assertEqual([], self.rule_lines(out, DEFINITION), out)

    def test_relationship_sourced_by_a_definition_fires(self) -> None:
        self.workspace_config({"catalogFolders": ["engineering", "shared-services"]})
        self.put("engineering", _obj(COMP, "product_component", "Fx Component"))
        self.put("shared-services", _obj(EXT, "network_service", "Fx Edge"))
        self.put_relationship(EXT, COMP)
        _, out = self.run_validate()
        lines = self.rule_lines(out, DEFINITION)
        self.assertEqual(1, len(lines), out)
        self.assertIn("source 'Fx Edge' (type: network_service", lines[0])

    def test_explicit_service_role_definition_outside_folder_fires(self) -> None:
        self.workspace_config({"catalogFolders": ["engineering", "shared-services"]})
        self.put("engineering", _obj(COMP, "product_component", "Fx Component"))
        self.put("engineering", _obj(EXT, "host", "Fx Host", serviceRole="definition"))
        self.put_relationship(COMP, EXT)
        _, out = self.run_validate()
        self.assertEqual(1, len(self.rule_lines(out, DEFINITION)), out)

    def test_no_service_definitions_folder_means_every_object_is_an_instance(self) -> None:
        self.put("engineering", _obj(COMP, "product_component", "Fx Component"))
        self.put("shared-services", _obj(EXT, "runtime_service", "Fx Idp"))
        self.put_relationship(COMP, EXT)
        _, out = self.run_validate()
        self.assertEqual([], self.rule_lines(out, DEFINITION), out)

    def test_service_definitions_folder_override_is_honoured(self) -> None:
        self.workspace_config({"catalogFolders": ["engineering", "shared-services", "platform"], "serviceDefinitionsFolder": "catalog/platform"})
        self.put("engineering", _obj(COMP, "product_component", "Fx Component"))
        self.put("shared-services", _obj(EXT, "runtime_service", "Fx Idp"))
        self.put("platform", _obj(STORE, "data_store_service", "Fx Store"))
        self.put_relationship(COMP, EXT)
        _, out = self.run_validate()
        self.assertEqual([], self.rule_lines(out, DEFINITION), out)
        self.put_relationship(COMP, STORE)
        _, out = self.run_validate()
        self.assertEqual(1, len(self.rule_lines(out, DEFINITION)), out)

    def test_definition_endpoint_violation_is_grandfathered_by_baseline(self) -> None:
        self.workspace_config({"catalogFolders": ["engineering", "shared-services"]})
        self.put("engineering", _obj(COMP, "product_component", "Fx Component"))
        self.put("shared-services", _obj(EXT, "runtime_service", "Fx Idp"))
        self.put_relationship(COMP, EXT)
        self.run_validate("--write-baseline")
        _, out = self.run_validate()
        self.assertEqual([], self.rule_lines(out, DEFINITION), out)
        self.assertTrue(self.baseline_lines(out, DEFINITION), out)


class FixtureBaselineTests(unittest.TestCase):
    def run_ws(self, workspace: Path, *flags: str) -> Tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, str(VALIDATE), "--workspace", str(workspace), *flags],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout + proc.stderr

    def test_fixture_workspace_violations_are_baseline_warnings(self) -> None:
        code, out = self.run_ws(REPO_ROOT / "tests" / "fixtures" / "diagram_workspace")
        self.assertIn("baseline: ", out)
        errors = [l for l in out.splitlines() if l.startswith("- ") and not l.startswith("- baseline:")]
        self.assertFalse([l for l in errors if "[sdp-placement-types]" in l or "[relationship-definition-endpoint]" in l])
        self.assertTrue([l for l in out.splitlines() if l.startswith("- baseline:") and "[sdp-placement-types]" in l])
        for rule in ("sdp-placement-types", "relationship-definition-endpoint"):
            self.assertTrue([l for l in out.splitlines() if l.startswith("- baseline:") and f"[{rule}]" in l], rule)
        self.assertNotIn("stale baseline entry", out)
        # The fixture deliberately leaves gaps (a placed entry without diagramTier, data components
        # without runsOn) that the diagram tests rely on, so the run exits 1 for those reasons only.
        self.assertEqual(1, code)

    def test_examples_workspace_exits_zero(self) -> None:
        code, out = self.run_ws(REPO_ROOT / "examples", "-q")
        self.assertEqual(0, code, out)


if __name__ == "__main__":
    unittest.main()
