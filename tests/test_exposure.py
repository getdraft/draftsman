"""E4 S3.3: one exposure resolver (framework/tools/exposure.py) for the renderer and the browser."""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "framework" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import exposure  # noqa: E402
import generate_browser as gb  # noqa: E402
import generate_diagram as gd  # noqa: E402
import validate  # noqa: E402
from generate_c4 import load_catalog  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "diagram_workspace"
EXAMPLES = REPO_ROOT / "examples"


def obj(uid: str, typ: str, **extra: Any) -> Dict[str, Any]:
    return {"uid": uid, "type": typ, "name": uid, **extra}


class ResolverPrecedenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog: Dict[str, Dict[str, Any]] = {
            o["uid"]: o
            for o in (
                obj("FW", "network_service"),
                obj("LB", "network_service"),
                obj("ING", "network_service"),
                obj("WEB", "product_component"),
                obj("DB", "data_component"),
                obj("RT", "runtime_service"),
            )
        }

    def ra(self, *entries: Dict[str, Any]) -> Dict[str, Any]:
        ra = obj("RA", "reference_architecture", serviceGroups=[{"name": "edge", "deployableObjects": list(entries)}])
        self.catalog["RA"] = ra
        return ra

    def test_slot_chain_uses_edge_slot_order_and_skips_bad_fills(self) -> None:
        ra = self.ra(
            {"slot": "ingress", "fills": "ING"},
            {"slot": "load-balancer", "fills": "LB"},
            {"slot": "firewall", "fills": "FW"},
            {"slot": "firewall", "fills": "FW"},  # repeat
            {"slot": "database", "fills": "LB"},  # not an edge slot
            {"slot": "api-gateway", "fills": "WEB"},  # not a network_service
            {"slot": "web-application-firewall"},  # unfilled
        )
        self.assertEqual(exposure.slot_chain(ra, self.catalog), ["FW", "LB", "ING"])

    def test_slot_chain_without_reference_architecture(self) -> None:
        self.assertEqual(exposure.slot_chain(None, self.catalog), [])
        self.assertEqual(exposure.pattern_slot_chain({"followsReferenceArchitecture": "MISSING"}, self.catalog), [])

    def test_none_switches_exposure_off(self) -> None:
        self.assertEqual(exposure.group_chain("none", ["WEB"], self.catalog, ["LB"]), [])

    def test_explicit_chain_wins_and_keeps_order(self) -> None:
        self.assertEqual(exposure.group_chain("FW", ["WEB"], self.catalog, ["LB"]), ["FW"])
        self.assertEqual(exposure.group_chain(["LB", "FW"], ["WEB"], self.catalog, ["ING"]), ["LB", "FW"])

    def test_explicit_chain_drops_non_network_services_and_repeats(self) -> None:
        self.assertEqual(exposure.group_chain(["FW", "WEB", "FW", "MISSING", 3], ["WEB"], self.catalog, []), ["FW"])

    def test_explicit_chain_exposes_a_data_tier(self) -> None:
        self.assertEqual(exposure.group_chain("FW", ["DB"], self.catalog, ["LB"]), ["FW"])

    def test_default_is_the_slot_chain_except_for_a_data_tier(self) -> None:
        self.assertEqual(exposure.group_chain(None, ["WEB", "DB"], self.catalog, ["FW", "LB"]), ["FW", "LB"])
        self.assertEqual(exposure.group_chain(None, ["DB"], self.catalog, ["FW", "LB"]), [])
        self.assertEqual(exposure.group_chain(None, [], self.catalog, ["LB"]), ["LB"])
        self.assertEqual(exposure.group_chain([], ["WEB"], self.catalog, ["LB"]), ["LB"])  # empty list: no override

    def test_resolve_pattern_exposure_by_group_index(self) -> None:
        self.ra({"slot": "load-balancer", "fills": "LB"})
        sdp = obj("SDP", "software_deployment_pattern", followsReferenceArchitecture="RA", serviceGroups=[
            {"name": "web", "deployableObjects": [{"ref": "WEB"}]},
            "not a group",
            {"name": "data", "deployableObjects": [{"ref": "DB"}, {"ref": "UNKNOWN"}]},
            {"name": "off", "exposedThrough": "none", "deployableObjects": [{"ref": "WEB"}]},
            {"name": "own", "exposedThrough": ["FW", "LB"], "deployableObjects": [{"ref": "WEB"}]},
        ])
        self.assertEqual(exposure.resolve_pattern_exposure(sdp, self.catalog), [["LB"], [], [], [], ["FW", "LB"]])


class OneResolverTests(unittest.TestCase):
    def test_renderer_and_validator_share_edge_slots(self) -> None:
        self.assertIs(gd.EDGE_SLOTS, exposure.EDGE_SLOTS)
        self.assertIs(validate.EDGE_SLOTS, exposure.EDGE_SLOTS)

    def test_renderer_delegates_precedence_to_the_resolver(self) -> None:
        for name in ("_slot_chain", "_group_chain"):
            source = inspect.getsource(getattr(gd.Model, name))
            self.assertRegex(source, r"exposure\.(pattern_slot_chain|group_chain)\(", name)
            self.assertNotIn("EDGE_SLOTS", source, name)

    def assert_parity(self, catalog: Dict[str, Dict[str, Any]], sdp: Dict[str, Any]) -> int:
        expected = exposure.resolve_pattern_exposure(sdp, catalog)
        groups = [g for g in sdp.get("serviceGroups") or [] if isinstance(g, dict)]
        expected_by_group = [chain for chain, g in zip(expected, sdp.get("serviceGroups") or []) if isinstance(g, dict)]
        containers = gd.build_diagram_model(catalog, sdp, False).containers
        self.assertEqual(len(containers), len(groups))
        browser = gb.build_group_exposure(sdp, catalog)
        exposed = 0
        for container, chain, row in zip(containers, expected_by_group, browser):
            if not container.drawn:
                continue
            self.assertEqual(container.exposed_through, chain, container.group)
            names = [str(catalog.get(u, {}).get("name") or u) for u in chain]
            self.assertEqual(row["devices"], names, container.group)
            exposed += bool(chain)
        return exposed

    def test_fixture_renderer_browser_and_resolver_agree(self) -> None:
        catalog = load_catalog(FIXTURE)
        exposed = self.assert_parity(catalog, catalog["FXSDP00001-0001"])
        self.assertGreater(exposed, 0)

    def test_examples_renderer_browser_and_resolver_agree(self) -> None:
        catalog = load_catalog(EXAMPLES)
        patterns = [o for o in catalog.values() if o.get("type") == "software_deployment_pattern"]
        self.assertTrue(patterns)
        for sdp in patterns:
            with self.subTest(sdp=sdp.get("uid")):
                try:
                    gd.build_diagram_model(catalog, sdp, False)
                except ValueError:
                    continue
                self.assert_parity(catalog, sdp)


if __name__ == "__main__":
    unittest.main()
