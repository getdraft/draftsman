from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from framework.tools.generate_browser import build_browser_payload
from framework.tools.generate_indexes import write_indexes
from framework.tools.indexes import build_catalog_indexes


class GeneratedIndexTests(unittest.TestCase):
    def test_domain_capability_index_uses_capability_domain(self) -> None:
        registry = {
            "dom-1": {
                "uid": "dom-1",
                "type": "domain",
                "name": "Security",
                "description": "Security domain",
                "capabilities": ["legacy-wrong-source"],
            },
            "cap-1": {
                "uid": "cap-1",
                "type": "capability",
                "name": "Identity",
                "description": "Identity capability",
                "domain": "dom-1",
                "owner": {"team": "Platform"},
                "implementations": [{"ref": "tech-1", "lifecycleStatus": "preferred"}],
            },
            "tech-1": {
                "uid": "tech-1",
                "type": "technology_component",
                "name": "SSO",
                "vendor": "Example",
            },
        }

        indexes = build_catalog_indexes(registry)

        domains = indexes["domainCapability"]["domains"]
        security_domain = next(domain for domain in domains if domain["id"] == "dom-1")
        self.assertEqual([capability["id"] for capability in security_domain["capabilities"]], ["cap-1"])
        self.assertEqual(security_domain["capabilities"][0]["implementations"][0]["ref"], "tech-1")

    def test_requirement_implementation_index_rows_are_canonical(self) -> None:
        registry = {
            "obj-1": {
                "uid": "obj-1",
                "type": "runtime_service",
                "name": "API",
                "requirementImplementations": [
                    {
                        "requirementGroup": "rg-1",
                        "requirementId": "REQ-1",
                        "status": "implemented",
                        "evidence": "design-doc",
                    }
                ],
            }
        }

        indexes = build_catalog_indexes(registry)

        self.assertEqual(
            indexes["requirementImplementations"]["rows"],
            [
                {
                    "object": "obj-1",
                    "requirementGroup": "rg-1",
                    "requirementId": "REQ-1",
                    "status": "implemented",
                    "evidence": "design-doc",
                    "notes": "",
                    "implementation": {
                        "requirementGroup": "rg-1",
                        "requirementId": "REQ-1",
                        "status": "implemented",
                        "evidence": "design-doc",
                    },
                }
            ],
        )

    def test_browser_payload_embeds_generated_indexes(self) -> None:
        registry = {
            "dom-1": {"uid": "dom-1", "type": "domain", "name": "Security"},
            "cap-1": {
                "uid": "cap-1",
                "type": "capability",
                "name": "Identity",
                "domain": "dom-1",
                "implementations": [],
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            payload = build_browser_payload(registry, Path(tmp))

        self.assertIn("indexes", payload)
        self.assertIn("domainCapability", payload["indexes"])
        self.assertEqual(payload["indexes"]["domainCapability"]["source"], "capability.domain")

    def test_generate_indexes_writer_creates_json_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "assets" / "draft-indexes.json"
            write_indexes({"domainCapability": {"domains": []}, "requirementImplementations": {"rows": []}}, output)
            self.assertTrue(output.exists())
            self.assertIn('"domainCapability"', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
