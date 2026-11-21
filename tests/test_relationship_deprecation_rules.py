"""#368 S1.2: ratcheted rules for deprecated relationship fields."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "framework" / "tools"))

import validate  # noqa: E402

RULES = ("relationship-flow-deprecated", "relationship-external-target-freetext", "relationship-source-is-listener-side")


def rel(uid: str = "R0000000AA-0001", **fields: object) -> dict:
    return {"uid": uid, "type": "relationship", "name": f"rel {uid}", "source": "SRC", "target": "TGT", **fields}


def run(rule: str, obj: dict, catalog: dict | None = None) -> list[str]:
    return list(validate.RATCHET_RULES[rule](obj, catalog or {}, {}))


class RegistrationTests(unittest.TestCase):
    def test_rules_are_registered_as_ratcheted(self) -> None:
        for rule in RULES:
            self.assertIn(rule, validate.RATCHET_RULES)


class FlowDeprecatedTests(unittest.TestCase):
    def test_fires_on_inbound_and_bidirectional(self) -> None:
        (bi,) = run("relationship-flow-deprecated", rel(flow="bidirectional"))
        self.assertIn("deprecated flow 'bidirectional'", bi)
        self.assertIn("direction synchronous", bi)
        (inbound,) = run("relationship-flow-deprecated", rel(flow=" Inbound "))
        self.assertIn("deprecated flow 'inbound'", inbound)
        self.assertIn("make the caller the source", inbound)

    def test_quiet_otherwise(self) -> None:
        for obj in (rel(), rel(flow="outbound"), rel(flow="sideways"), rel(flow=None),
                    rel(flow="inbound", _derived=True), {"uid": "X", "type": "product_component", "flow": "inbound"}):
            self.assertEqual(run("relationship-flow-deprecated", obj), [], obj)


class ExternalTargetFreetextTests(unittest.TestCase):
    def test_fires_when_external_target_is_set(self) -> None:
        obj = rel(target=None, externalTarget=" LDAP Directory ")
        (message,) = run("relationship-external-target-freetext", obj)
        self.assertIn("free-text externalTarget 'LDAP Directory'", message)
        self.assertIn("system object with a listener", message)
        self.assertEqual(len(run("relationship-external-target-freetext", rel(externalTarget="Stripe"))), 1)

    def test_quiet_otherwise(self) -> None:
        for obj in (rel(), rel(externalTarget=""), rel(externalTarget="  "), rel(externalTarget="X", _derived=True)):
            self.assertEqual(run("relationship-external-target-freetext", obj), [], obj)


class SourceIsListenerSideTests(unittest.TestCase):
    catalog = {
        "LIS": {"uid": "LIS", "type": "listener", "owner": {"kind": "product_component", "ref": "SRC"}},
        "TGT": {"uid": "TGT", "type": "product_component"},
        "SYS": {"uid": "SYS", "type": "system"},
    }

    def test_inbound_from_a_listener_owner(self) -> None:
        (message,) = run("relationship-source-is-listener-side", rel(flow="inbound"), self.catalog)
        self.assertIn("its source owns a listener", message)
        self.assertIn("swap source and target", message)

    def test_inbound_from_outside_parties(self) -> None:
        (free,) = run("relationship-source-is-listener-side", rel(flow="inbound", source="OTHER", target=None, externalTarget="Internet"), self.catalog)
        self.assertIn("free-text outside party", free)
        (system,) = run("relationship-source-is-listener-side", rel(flow="inbound", source="OTHER", target="SYS"), self.catalog)
        self.assertIn("an external system", system)
        (both,) = run("relationship-source-is-listener-side", rel(flow="inbound", target="SYS"), self.catalog)
        self.assertIn("its source owns a listener and its target is an external system", both)

    def test_only_on_inbound(self) -> None:
        for flow in (None, "outbound", "bidirectional"):
            self.assertEqual(run("relationship-source-is-listener-side", rel(flow=flow, target="SYS"), self.catalog), [], flow)
        # inbound between two internal objects where the source owns no listener: no heuristic hit
        self.assertEqual(run("relationship-source-is-listener-side", rel(flow="inbound", source="OTHER"), self.catalog), [])
        self.assertEqual(run("relationship-source-is-listener-side", rel(flow="inbound", _derived=True), self.catalog), [])

    def test_never_fires_without_flow_deprecated(self) -> None:
        cases = [rel(flow=f, source=s, target=t) for f in (None, "outbound", "inbound", "bidirectional")
                 for s in ("SRC", "OTHER") for t in ("TGT", "SYS")]
        for obj in cases:
            if run("relationship-source-is-listener-side", obj, self.catalog):
                self.assertTrue(run("relationship-flow-deprecated", obj, self.catalog), obj)


class BaselineTests(unittest.TestCase):
    def entries(self, workspace: Path) -> list[dict]:
        return yaml.safe_load((workspace / ".draft" / "validation-baseline.yaml").read_text(encoding="utf-8"))["entries"]

    def test_example_external_targets_are_baselined(self) -> None:
        recorded = {e["uid"] for e in self.entries(REPO_ROOT / "examples") if e["rule"] == "relationship-external-target-freetext"}
        self.assertEqual(len(recorded), 12)

    def test_fixture_legacy_flows_are_baselined(self) -> None:
        rules = [e["rule"] for e in self.entries(REPO_ROOT / "tests" / "fixtures" / "diagram_workspace")]
        self.assertEqual(rules.count("relationship-flow-deprecated"), 55)
        self.assertEqual(rules.count("relationship-external-target-freetext"), 1)


if __name__ == "__main__":
    unittest.main()
