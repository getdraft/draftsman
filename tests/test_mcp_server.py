"""The optional MCP adapter's tools, called with data rather than only started.

A handshake check proves the server starts and lists tools. That is a different claim
from the tools returning anything: `query_architecture` read an `objects` key the index generator
never produced, so every query returned nothing, and `check_compliance` answered "compliant" for
any input without consulting the catalog.

Those are both invisible to a handshake check, so the assertions here are on results.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from framework.tools.indexes import build_catalog_indexes

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER = REPO_ROOT / "framework" / "tools" / "mcp_server.py"

# Small by design: two objects, one fully satisfied and one not, so a verdict that ignores the
# catalog cannot pass by luck.
FIXTURE = {
    "objects": [
        {"uid": "svc-1", "name": "Absence Service", "type": "runtime_service", "catalogStatus": "complete"},
        {"uid": "svc-2", "name": "Payments Service", "type": "runtime_service", "catalogStatus": "incomplete"},
    ],
    "requirementImplementations": {
        "rows": [
            {"object": "svc-1", "requirementId": "authentication", "status": "satisfied"},
            {"object": "svc-1", "requirementId": "logging", "status": "satisfied"},
            {"object": "svc-2", "requirementId": "authentication", "status": "satisfied"},
            {"object": "svc-2", "requirementId": "encryption", "status": "gap"},
        ]
    },
}


def call_tool(index: dict, name: str, arguments: dict) -> dict:
    """Run one tool against an index, over the same stdio transport an agent would use."""
    with tempfile.TemporaryDirectory() as tmp:
        index_path = Path(tmp) / "catalog_indexes.json"
        index_path.write_text(json.dumps(index), encoding="utf-8")
        env = {
            **os.environ,
            "DRAFT_WORKSPACE_MODE": "read_only",
            "DRAFT_CATALOG_INDEX_PATH": str(index_path),
        }
        proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env,
        )
        try:
            for message in (
                {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "tests", "version": "1"}}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": name, "arguments": arguments}},
            ):
                proc.stdin.write(json.dumps(message) + "\n")
                proc.stdin.flush()
                response = json.loads(proc.stdout.readline())
        finally:
            proc.terminate()
    return json.loads(response["result"]["content"][0]["text"])


class ObjectIndexTests(unittest.TestCase):
    def test_the_generator_emits_the_objects_the_query_tool_reads(self) -> None:
        """The defect this fixes: the server read `objects` and nothing produced it."""
        registry = {
            "svc-1": {"uid": "svc-1", "type": "runtime_service", "name": "Absence Service",
                      "catalogStatus": "complete"},
        }

        indexes = build_catalog_indexes(registry)

        self.assertIn("objects", indexes)
        self.assertEqual(indexes["objects"][0]["name"], "Absence Service")

    def test_objects_without_an_id_are_skipped(self) -> None:
        indexes = build_catalog_indexes({"broken": {"type": "capability", "name": "No id"}})

        self.assertEqual(indexes["objects"], [])


class QueryTests(unittest.TestCase):
    def test_a_query_returns_matches(self) -> None:
        result = call_tool(FIXTURE, "query_architecture", {"query": "absence"})

        self.assertEqual(result["match_count"], 1)
        self.assertEqual(result["results"][0]["uid"], "svc-1")

    def test_a_query_can_match_on_type(self) -> None:
        self.assertEqual(call_tool(FIXTURE, "query_architecture", {"query": "runtime_service"})["match_count"], 2)

    def test_an_unmatched_query_returns_nothing(self) -> None:
        self.assertEqual(call_tool(FIXTURE, "query_architecture", {"query": "zzz"})["match_count"], 0)


class ComplianceTests(unittest.TestCase):
    def test_a_fully_satisfied_object_is_compliant(self) -> None:
        result = call_tool(FIXTURE, "check_compliance", {"product_name": "Absence Service"})

        self.assertEqual(result["complianceStatus"], "compliant")
        self.assertEqual(result["satisfiedRequirements"], ["authentication", "logging"])

    def test_an_object_with_a_gap_is_not_compliant(self) -> None:
        """The assertion that matters. A hardcoded "compliant" passes every test that only checks
        the call succeeded, and this is the one it cannot pass."""
        result = call_tool(FIXTURE, "check_compliance", {"product_name": "Payments Service"})

        self.assertEqual(result["complianceStatus"], "non_compliant")
        self.assertEqual(result["unsatisfiedRequirements"], ["encryption"])

    def test_an_unknown_product_is_unknown_not_compliant(self) -> None:
        result = call_tool(FIXTURE, "check_compliance", {"product_name": "Nonexistent Service"})

        self.assertEqual(result["complianceStatus"], "unknown")
        self.assertIn("catalog index", result["reason"])

    def test_a_known_object_with_nothing_assessed_is_unknown(self) -> None:
        index = {"objects": [{"uid": "svc-3", "name": "Quiet Service", "type": "runtime_service"}],
                 "requirementImplementations": {"rows": []}}

        result = call_tool(index, "check_compliance", {"product_name": "Quiet Service"})

        self.assertEqual(result["complianceStatus"], "unknown")


class DiagramTests(unittest.TestCase):
    def test_a_diagram_is_not_drawn_for_something_absent(self) -> None:
        result = call_tool(FIXTURE, "get_c4_diagram", {"product_name": "Nonexistent Service"})

        self.assertIn("error", result)

    def test_c4_diagram_renders_topology_from_relationships(self) -> None:
        index = {
            "objects": [
                {"uid": "svc-1", "name": "Absence Service", "type": "runtime_service"},
                {"uid": "svc-2", "name": "Payments Service", "type": "runtime_service"},
                {"uid": "rel-1", "name": "Absence -> Payments", "type": "relationship", "source": "svc-1", "target": "svc-2", "label": "calls", "technology": "HTTPS/REST"},
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "catalog_indexes.json"
            index_path.write_text(json.dumps(index), encoding="utf-8")
            env = {
                **os.environ,
                "DRAFT_WORKSPACE_MODE": "read_only",
                "DRAFT_CATALOG_INDEX_PATH": str(index_path),
            }
            proc = subprocess.Popen(
                [sys.executable, str(SERVER)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=env,
            )
            try:
                for message in (
                    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                "clientInfo": {"name": "tests", "version": "1"}}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                     "params": {"name": "get_c4_diagram", "arguments": {"product_name": "Absence Service"}}},
                ):
                    proc.stdin.write(json.dumps(message) + "\n")
                    proc.stdin.flush()
                    response = json.loads(proc.stdout.readline())
            finally:
                proc.terminate()
        
        output_text = response["result"]["content"][0]["text"]
        self.assertIn("Payments Service", output_text)
        self.assertIn("calls via HTTPS/REST", output_text)
        self.assertIn("```mermaid", output_text)


class AmbiguousNameTests(unittest.TestCase):
    def test_a_fragment_matching_several_objects_is_unknown_not_a_verdict(self) -> None:
        index = {
            "objects": [
                {"uid": "a", "name": "Payments Service", "type": "runtime_service", "catalogStatus": "complete"},
                {"uid": "b", "name": "Payments Gateway", "type": "edge_gateway_service", "catalogStatus": "complete"},
            ],
            "requirementImplementations": {"rows": [{"object": "a", "requirementId": "r", "status": "satisfied"}]},
        }

        result = call_tool(index, "check_compliance", {"product_name": "payments"})

        self.assertEqual(result["complianceStatus"], "unknown")

    def test_an_exact_name_still_resolves_when_a_fragment_would_not(self) -> None:
        index = {
            "objects": [
                {"uid": "a", "name": "Payments Service", "type": "runtime_service", "catalogStatus": "complete"},
                {"uid": "b", "name": "Payments Gateway", "type": "edge_gateway_service", "catalogStatus": "complete"},
            ],
            "requirementImplementations": {"rows": [{"object": "a", "requirementId": "r", "status": "satisfied"}]},
        }

        result = call_tool(index, "check_compliance", {"product_name": "Payments Service"})

        self.assertEqual(result["complianceStatus"], "compliant")


class IndexLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("mcp_server_under_test", SERVER)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def test_the_token_goes_only_to_https_github_hosts(self) -> None:
        allowed = self.mod.token_allowed_for
        for url in (
            "https://raw.githubusercontent.com/org/repo/main/draft-indexes.json",
            "https://api.github.com/repos/org/repo/contents/x.json",
            "https://github.com/org/repo/raw/main/x.json",
        ):
            self.assertTrue(allowed(url), url)
        for url in (
            "https://evil.example.com/github/x.json",
            "https://github.com.evil.example.com/x.json",
            "https://evilgithub.com/x.json",
            "http://raw.githubusercontent.com/x.json",
            "https://example.com/?u=github.com",
            "not a url",
        ):
            self.assertFalse(allowed(url), url)

    def test_no_index_found_is_an_empty_index_not_a_crash(self) -> None:
        saved = {k: os.environ.pop(k, None) for k in ("DRAFT_CATALOG_INDEX_URL", "DRAFT_CATALOG_INDEX_PATH")}
        cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)
                self.assertEqual(self.mod.load_catalog_index(), {"objects": []})
        finally:
            os.chdir(cwd)
            for key, value in saved.items():
                if value is not None:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
