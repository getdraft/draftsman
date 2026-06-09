from __future__ import annotations

import importlib.util
import tempfile
import textwrap
import unittest
from pathlib import Path

from draft_table.repo import ensure_workspace_layout
from draft_table.validation import validate_workspace

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_generate_browser_module():
    module_path = REPO_ROOT / "framework" / "tools" / "generate_browser.py"
    spec = importlib.util.spec_from_file_location("generate_browser", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DomainCapabilityIndexTests(unittest.TestCase):
    def test_browser_payload_derives_domain_capabilities_from_capability_domain(self) -> None:
        generate_browser = load_generate_browser_module()
        domain_uid = "01KT8FTZW9-TC79"
        capability_uid = "01KT8FV073-9A2B"
        registry = {
            domain_uid: {
                "schemaVersion": "1.0",
                "uid": domain_uid,
                "type": "domain",
                "name": "Derived Domain",
                "description": "Domain intentionally has no capabilities list.",
            },
            capability_uid: {
                "schemaVersion": "1.0",
                "uid": capability_uid,
                "type": "capability",
                "name": "Derived Capability",
                "description": "Capability owns the domain edge.",
                "catalogStatus": "complete",
                "definitionOwner": {"provider": "test"},
                "domain": domain_uid,
                "implementations": [],
            },
        }

        payload = generate_browser.build_browser_payload(registry, REPO_ROOT / "examples")

        self.assertEqual(payload["indexes"]["domainCapabilities"][domain_uid], [capability_uid])
        domain_object = payload["lookup"][domain_uid]
        self.assertEqual(domain_object["capabilities"], [capability_uid])
        self.assertEqual(payload["indexes"]["capabilityDomain"][capability_uid], domain_uid)


    def test_browser_payload_derives_owner_contact_from_team_vocabulary(self) -> None:
        generate_browser = load_generate_browser_module()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            (workspace / ".draft" / "workspace.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    workspace:
                      name: owner-contact-browser
                    vocabulary:
                      teams:
                        mode: advisory
                        values:
                          - id: platform
                            name: Platform
                            contact: platform@example.com
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            registry = {
                "01KT8OWNER-0001": {
                    "schemaVersion": "1.0",
                    "uid": "01KT8OWNER-0001",
                    "type": "product_component",
                    "name": "Contact Test Service",
                    "owner": {"team": "platform"},
                    "catalogStatus": "complete",
                    "lifecycleStatus": "existing-only",
                }
            }

            payload = generate_browser.build_browser_payload(registry, workspace)

        owner = payload["lookup"]["01KT8OWNER-0001"]["owner"]
        self.assertEqual(owner["contact"], "platform@example.com")
        self.assertIn('"contact": "platform@example.com"', payload["lookup"]["01KT8OWNER-0001"]["detail"])

    def test_domain_without_authored_capabilities_validates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            domain_dir = workspace / "configurations" / "domains"
            domain_dir.mkdir(parents=True, exist_ok=True)
            (domain_dir / "domain-derived.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KT8FTZW9-TC79
                    type: domain
                    name: Derived Domain
                    description: Capability membership is derived from capability.domain.
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
