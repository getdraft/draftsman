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


TI = "relationship-target-interface"
COMP2 = "01M7C497N2-MSDX"
RUNTIME_I = "01M7C497N3-MSDY"


class TargetInterfaceRuleTests(unittest.TestCase):
    """AC2: relationship-target-interface, one case per branch."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name)
        (self.ws / "catalog" / "engineering").mkdir(parents=True)

    def put(self, obj: Dict[str, Any]) -> None:
        (self.ws / "catalog" / "engineering" / (str(obj["uid"]) + ".yaml")).write_text(
            yaml.safe_dump(obj, sort_keys=True), encoding="utf-8"
        )

    def target(self, typ: str, uid: str = COMP2, **extra: Any) -> None:
        self.put(_obj(COMP, "product_component", "Fx Caller"))
        self.put(_obj(uid, typ, "Fx Target", **extra))

    def rel(self, target: Optional[str] = COMP2, **extra: Any) -> None:
        fields: Dict[str, Any] = {"source": COMP, "label": "calls", "catalogStatus": "stub"}
        if target:
            fields["target"] = target
        fields.update(extra)
        self.put(_obj(REL, "relationship", "Fx Flow", **fields))

    def run_validate(self, *flags: str) -> Tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, str(VALIDATE), "--workspace", str(self.ws), *flags],
            capture_output=True, text=True, check=False,
        )
        return proc.returncode, proc.stdout + proc.stderr

    @staticmethod
    def lines(out: str) -> Dict[str, List[str]]:
        """Rule lines split into errors, warnings and baselined warnings."""
        result: Dict[str, List[str]] = {"error": [], "warning": [], "baseline": []}
        section = ""
        for line in out.splitlines():
            if line.startswith("Validation failures"):
                section = "error"
            elif line.startswith("Validation warnings"):
                section = "warning"
            elif line.startswith("- ") and TI in line:
                key = "baseline" if line.startswith("- baseline:") else section
                result[key].append(line)
        return result

    IFACES = [{"name": "api", "protocol": "REST"}, {"name": "admin", "protocol": "REST"}]

    # ratcheted branch
    def test_product_component_without_target_interface_is_a_ratcheted_error(self) -> None:
        self.target("product_component", interfaces=self.IFACES)
        self.rel()
        code, out = self.run_validate()
        found = self.lines(out)["error"]
        self.assertEqual(1, len(found), out)
        for text in ("Fx Flow", "Fx Target", "without a targetInterface", "api, admin", f"[{TI}]"):
            self.assertIn(text, found[0])
        self.assertEqual(1, code)

    def test_product_component_with_named_interface_is_clean(self) -> None:
        self.target("product_component", interfaces=self.IFACES)
        self.rel(targetInterface="admin")
        _, out = self.run_validate()
        self.assertEqual({"error": [], "warning": [], "baseline": []}, self.lines(out), out)

    def test_ratcheted_error_is_baselined_then_binds_again_when_touched(self) -> None:
        self.target("product_component", interfaces=self.IFACES)
        self.rel()
        self.run_validate("--write-baseline")
        entries = yaml.safe_load((self.ws / ".draft" / "validation-baseline.yaml").read_text())["entries"]
        self.assertEqual([(TI, REL)], [(e["rule"], e["uid"]) for e in entries])
        _, out = self.run_validate()
        found = self.lines(out)
        self.assertEqual([], found["error"], out)
        self.assertEqual(1, len(found["baseline"]), out)
        self.rel(notes="touched")
        code, out = self.run_validate()
        self.assertEqual(1, len(self.lines(out)["error"]), out)
        self.assertEqual(1, code)
        # Fixing the relationship leaves a stale baseline entry as a warning.
        self.rel(targetInterface="api")
        _, out = self.run_validate()
        self.assertIn("stale baseline entry", out)
        self.assertEqual([], self.lines(out)["error"], out)

    def test_no_baseline_flag_makes_it_an_error_again(self) -> None:
        self.target("product_component", interfaces=self.IFACES)
        self.rel()
        self.run_validate("--write-baseline")
        code, out = self.run_validate("--no-baseline")
        self.assertEqual(1, len(self.lines(out)["error"]), out)
        self.assertEqual(1, code)

    # exemptions
    def test_data_component_target_needs_no_target_interface(self) -> None:
        self.target("data_component")
        self.rel()
        _, out = self.run_validate()
        self.assertEqual({"error": [], "warning": [], "baseline": []}, self.lines(out), out)

    def test_external_target_and_instance_target_need_no_target_interface(self) -> None:
        self.target("runtime_service", uid=RUNTIME_I)
        self.rel(target=RUNTIME_I)
        _, out = self.run_validate()
        self.assertEqual({"error": [], "warning": [], "baseline": []}, self.lines(out), out)
        self.rel(target=None, externalTarget="Fx External")
        _, out = self.run_validate()
        self.assertEqual({"error": [], "warning": [], "baseline": []}, self.lines(out), out)

    def test_derived_relationship_is_exempt(self) -> None:
        self.put(_obj(COMP, "product_component", "Fx Caller", runtimeSpec={"dependencies": [{"ref": COMP2, "interface": "api"}]}))
        self.put(_obj(COMP2, "product_component", "Fx Target", interfaces=self.IFACES))
        _, out = self.run_validate()
        self.assertEqual({"error": [], "warning": [], "baseline": []}, self.lines(out), out)
        sys.path.insert(0, str(VALIDATE.parent))
        try:
            import validate as v  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        catalog = {COMP2: _obj(COMP2, "product_component", "Fx Target", interfaces=self.IFACES)}
        derived = _obj(REL, "relationship", "d", source=COMP, target=COMP2, _derived=True, targetInterface="nope")
        self.assertEqual([], list(v._check_relationship_target_interface(derived, catalog, {})))
        failures: List[str] = []
        warnings: List[str] = []
        v.validate_target_interface(derived, Path("x.yaml"), catalog, failures, warnings)
        self.assertEqual(([], []), (failures, warnings))

    # unratcheted errors
    def assert_missing_surface_error(self, out: str, code: int, shown: str) -> None:
        found = self.lines(out)
        self.assertEqual(1, len(found["error"]), out)
        for text in ("Fx Flow", "Fx Target", "'ghost'", shown):
            self.assertIn(text, found["error"][0])
        self.assertNotIn(f"[{TI}]", found["error"][0])
        self.assertEqual(1, code)

    def test_missing_name_on_product_component_is_an_unratcheted_error(self) -> None:
        self.target("product_component", interfaces=self.IFACES)
        self.rel(targetInterface="ghost")
        code, out = self.run_validate()
        self.assert_missing_surface_error(out, code, "api, admin")
        self.run_validate("--write-baseline")
        code, out = self.run_validate()
        self.assertEqual(1, len(self.lines(out)["error"]), out)

    def test_missing_name_on_data_component_with_interfaces_is_an_error(self) -> None:
        self.target("data_component", interfaces=[{"name": "sql", "protocol": "SQL"}])
        self.rel(targetInterface="ghost")
        code, out = self.run_validate()
        self.assert_missing_surface_error(out, code, "sql")

    def test_data_component_without_interfaces_accepts_only_data(self) -> None:
        self.target("data_component")
        self.rel(targetInterface="data")
        _, out = self.run_validate()
        self.assertEqual({"error": [], "warning": [], "baseline": []}, self.lines(out), out)
        self.rel(targetInterface="ghost")
        code, out = self.run_validate()
        self.assert_missing_surface_error(out, code, "data")

    def test_other_target_with_interfaces_lacking_the_name_is_an_error(self) -> None:
        self.target("runtime_service", uid=RUNTIME_I, interfaces=[{"name": "http", "protocol": "HTTP"}])
        self.rel(target=RUNTIME_I, targetInterface="ghost")
        code, out = self.run_validate()
        self.assert_missing_surface_error(out, code, "http")

    # warnings
    def test_target_interface_on_target_without_interfaces_list_is_a_warning(self) -> None:
        self.target("runtime_service", uid=RUNTIME_I)
        self.rel(target=RUNTIME_I, targetInterface="http")
        _, out = self.run_validate()
        found = self.lines(out)
        self.assertEqual([], found["error"], out)
        self.assertEqual(1, len(found["warning"]), out)
        for text in ("Fx Flow", "Fx Target", "'http'"):
            self.assertIn(text, found["warning"][0])

    def test_target_interface_on_external_target_is_a_warning(self) -> None:
        self.put(_obj(COMP, "product_component", "Fx Caller"))
        self.rel(target=None, externalTarget="Fx External", targetInterface="api")
        _, out = self.run_validate()
        found = self.lines(out)
        self.assertEqual([], found["error"], out)
        self.assertEqual(1, len(found["warning"]), out)
        for text in ("Fx Flow", "Fx External", "'api'"):
            self.assertIn(text, found["warning"][0])


NS1 = "01M7C497N4-MSDZ"
NS2 = "01M7C497N5-MSE0"
CAP = "01M7C497N6-MSE1"
RA = "01M7C497N7-MSE2"
SDP2 = "01M7C497N8-MSE3"


def _validator():
    sys.path.insert(0, str(VALIDATE.parent))
    try:
        import validate as v  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    return v


class ExposureWarningTests(unittest.TestCase):
    """AC3: exposedThrough, fills and protocol-family warnings (never errors, never ratcheted)."""

    def setUp(self) -> None:
        self.v = _validator()
        self.catalog = {
            NS1: _obj(NS1, "network_service", "Fx Firewall", capabilities=[CAP]),
            NS2: _obj(NS2, "network_service", "Fx Plain Device"),
            COMP: _obj(COMP, "product_component", "Fx Component"),
        }

    def exposure(self, obj: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        self.v.validate_exposure_refs(obj, Path("x.yaml"), self.catalog, out)
        return out

    def sdp(self, exposed: Any) -> Dict[str, Any]:
        return _obj(SDP2, "software_deployment_pattern", "Fx Pattern", serviceGroups=[{"name": "web", "exposedThrough": exposed}])

    def ra(self, **entry: Any) -> Dict[str, Any]:
        return _obj(RA, "reference_architecture", "Fx Ra", serviceGroups=[{"name": "edge", "deployableObjects": [entry]}])

    # exposedThrough
    def test_exposed_through_valid_forms_are_clean(self) -> None:
        for value in ("none", NS1, [NS1, NS2]):
            self.assertEqual([], self.exposure(self.sdp(value)), value)

    def test_exposed_through_unknown_uid_warns_with_value(self) -> None:
        found = self.exposure(self.sdp("01M7C497ZZ-MSEZ"))
        self.assertEqual(1, len(found), found)
        self.assertIn("exposedThrough value '01M7C497ZZ-MSEZ'", found[0])

    def test_exposed_through_wrong_type_and_list_member_warn(self) -> None:
        self.assertIn(f"'{COMP}'", self.exposure(self.sdp(COMP))[0])
        found = self.exposure(self.sdp([NS1, COMP, "none"]))
        self.assertEqual(2, len(found), found)

    # fills
    def test_fills_clean_when_edge_slot_network_service_and_capability(self) -> None:
        self.assertEqual([], self.exposure(self.ra(slot="firewall", fills=NS1, capability=CAP)))

    def test_fills_without_capability_on_entry_gives_no_capability_warning(self) -> None:
        self.assertEqual([], self.exposure(self.ra(slot="ingress", fills=NS2)))

    def test_fills_target_not_network_service_warns(self) -> None:
        found = self.exposure(self.ra(slot="firewall", fills=COMP))
        self.assertEqual(1, len(found), found)
        self.assertIn(f"fills '{COMP}' must be the uid of a network_service", found[0])

    def test_fills_on_non_edge_slot_warns_with_slot_name(self) -> None:
        found = self.exposure(self.ra(slot="database", fills=NS1))
        self.assertEqual(1, len(found), found)
        self.assertIn("slot 'database'", found[0])

    def test_fills_definition_lacking_capability_warns(self) -> None:
        found = self.exposure(self.ra(slot="load-balancer", fills=NS2, capability=CAP))
        self.assertEqual(1, len(found), found)
        for text in ("Fx Plain Device", CAP, "load-balancer"):
            self.assertIn(text, found[0])

    def test_fills_capability_satisfied_through_technology_component(self) -> None:
        self.catalog[NS2]["technologyComponent"] = "01M7C497N9-MSE4"
        self.catalog["01M7C497N9-MSE4"] = _obj("01M7C497N9-MSE4", "technology_component", "Fx Tech", capabilities=[CAP])
        self.assertEqual([], self.exposure(self.ra(slot="firewall", fills=NS2, capability=CAP)))

    # protocol family
    def family_warnings(self, technology: str, protocol: Optional[str], derived: bool = False, **target: Any) -> List[str]:
        iface = [{"name": "api", "protocol": protocol}] if protocol else []
        catalog = {COMP2: _obj(COMP2, "product_component", "Fx Target", interfaces=iface, **target)}
        rel = _obj(REL, "relationship", "Fx Flow", source=COMP, target=COMP2, technology=technology, targetInterface="api")
        if derived:
            rel["_derived"] = True
        out: List[str] = []
        self.v.validate_protocol_family(rel, Path("x.yaml"), catalog, out)
        return out

    def test_family_mismatch_names_both_protocols_and_families(self) -> None:
        found = self.family_warnings("REST", "gRPC")
        self.assertEqual(1, len(found), found)
        for text in ("Fx Flow", "'REST'", "'gRPC'", "web", "grpc"):
            self.assertIn(text, found[0])

    def test_same_family_is_clean(self) -> None:
        self.assertEqual([], self.family_warnings("HTTPS/REST", "GraphQL"))

    def test_unknown_family_on_either_side_is_clean(self) -> None:
        self.assertEqual([], self.family_warnings("AWS SDK (GetSecretValue)", "gRPC"))
        self.assertEqual([], self.family_warnings("REST", "Carrier Pigeon"))

    def test_derived_relationship_never_warns(self) -> None:
        self.assertEqual([], self.family_warnings("REST", "gRPC", derived=True))

    def test_data_component_implicit_surface_uses_target_engine(self) -> None:
        catalog = {COMP2: _obj(COMP2, "data_component", "Fx Data", targetEngine="postgresql")}
        rel = _obj(REL, "relationship", "Fx Flow", source=COMP, target=COMP2, technology="REST", targetInterface="data")
        out: List[str] = []
        self.v.validate_protocol_family(rel, Path("x.yaml"), catalog, out)
        self.assertEqual(1, len(out), out)
        self.assertIn("postgresql", out[0])

    def test_end_to_end_workspace_reports_warnings_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "catalog" / "engineering").mkdir(parents=True)
            docs = [
                _obj(COMP, "product_component", "Fx Caller"),
                _obj(COMP2, "product_component", "Fx Target", interfaces=[{"name": "api", "protocol": "gRPC"}]),
                _obj(REL, "relationship", "Fx Flow", source=COMP, target=COMP2, label="calls", catalogStatus="stub",
                     technology="REST", targetInterface="api"),
                _obj(NS1, "network_service", "Fx Firewall"),
                _obj(RA, "reference_architecture", "Fx Ra", serviceGroups=[
                    {"name": "edge", "deployableObjects": [{"slot": "database", "fills": COMP}]}]),
                _obj(SDP2, "software_deployment_pattern", "Fx Pattern", serviceGroups=[
                    {"name": "web", "exposedThrough": "01M7C497ZZ-MSEZ"}]),
            ]
            for doc in docs:
                (ws / "catalog" / "engineering" / (str(doc["uid"]) + ".yaml")).write_text(yaml.safe_dump(doc), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(VALIDATE), "--workspace", str(ws)], capture_output=True, text=True, check=False)
            out = proc.stdout + proc.stderr
            warn = out.split("Validation warnings", 1)[-1] if "Validation warnings" in out else ""
            for text in ("does not match interface 'api'", "exposedThrough value '01M7C497ZZ-MSEZ'", ".fills 'COMP'".replace("COMP", COMP), "slot 'database'"):
                self.assertIn(text, warn, out)
            self.assertFalse([l for l in out.split("Validation warnings")[0].splitlines() if "exposedThrough" in l or ".fills" in l], out)


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
        self.assertTrue([l for l in out.splitlines() if l.startswith("- baseline:") and "[relationship-target-interface]" in l])
        self.assertFalse([l for l in errors if "[relationship-target-interface]" in l])
        self.assertNotIn("stale baseline entry", out)
        # The fixture deliberately leaves gaps (a placed entry without diagramTier, data components
        # without runsOn) that the diagram tests rely on, so the run exits 1 for those reasons only.
        self.assertEqual(1, code)

    def test_write_baseline_round_trip_records_fixture_target_interface_violations(self) -> None:
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "ws"
            shutil.copytree(REPO_ROOT / "tests" / "fixtures" / "diagram_workspace", copy)
            (copy / ".draft" / "validation-baseline.yaml").unlink()
            _, out = self.run_ws(copy, "--no-baseline")
            before = [l for l in out.splitlines() if l.startswith("- ") and "[relationship-target-interface]" in l]
            self.assertTrue(before)
            self.run_ws(copy, "--write-baseline")
            entries = yaml.safe_load((copy / ".draft" / "validation-baseline.yaml").read_text())["entries"]
            recorded = [e for e in entries if e["rule"] == "relationship-target-interface"]
            self.assertEqual(len(before), len(recorded))
            _, out = self.run_ws(copy)
            self.assertFalse(
                [l for l in out.splitlines() if l.startswith("- ") and not l.startswith("- baseline:") and "[relationship-target-interface]" in l]
            )

    def test_examples_workspace_exits_zero(self) -> None:
        code, out = self.run_ws(REPO_ROOT / "examples", "-q")
        self.assertEqual(0, code, out)


if __name__ == "__main__":
    unittest.main()
