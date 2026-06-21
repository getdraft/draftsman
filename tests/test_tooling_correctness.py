from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from framework.tools.generate_ai_index import markdown_summary
from framework.tools import generate_c4
from framework.tools.validate import scan_for_secrets


class SecretScanTests(unittest.TestCase):
    def test_plaintext_secret_beside_secret_reference_is_flagged(self) -> None:
        # A mapping that declares a secretReference must not become a hiding place
        # for a plaintext secret in a sibling key.
        failures: list[str] = []
        scan_for_secrets(
            {"config": {"secretReference": "vault://app/db", "db_password": "hunter2"}},
            Path("technology-component-x.yaml"),
            failures,
        )
        self.assertTrue(
            any("Plaintext secret leaked" in message for message in failures),
            failures,
        )

    def test_top_level_secret_reference_does_not_skip_whole_object(self) -> None:
        failures: list[str] = []
        scan_for_secrets(
            {"secretReference": "vault://app/token", "apiToken": "abc123"},
            Path("object.yaml"),
            failures,
        )
        self.assertTrue(any("Plaintext secret leaked" in message for message in failures), failures)

    def test_lone_secret_reference_is_not_flagged(self) -> None:
        # The approved indirection itself must remain valid.
        failures: list[str] = []
        scan_for_secrets(
            {"apiKey": {"secretReference": "vault://app/api-key"}},
            Path("object.yaml"),
            failures,
        )
        self.assertEqual(failures, [])


class MarkdownSummaryTests(unittest.TestCase):
    def _summary_for(self, text: str) -> str:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            path.write_text(text, encoding="utf-8")
            return markdown_summary(path)

    def test_uses_okf_frontmatter_description(self) -> None:
        summary = self._summary_for(
            "---\n"
            "type: documentation\n"
            'title: "Example"\n'
            'description: "Curated one-line description."\n'
            "tags:\n"
            "  - draft\n"
            "timestamp: 2026-01-01T00:00:00-00:00\n"
            "---\n"
            "# Example\n"
            "\n"
            "Body prose that should not win over the description.\n"
        )
        self.assertEqual(summary, "Curated one-line description.")

    def test_falls_back_to_body_prose_when_no_description(self) -> None:
        summary = self._summary_for(
            "---\n"
            "type: documentation\n"
            'title: "Example"\n'
            "---\n"
            "# Example\n"
            "\n"
            "First prose line.\n"
        )
        self.assertEqual(summary, "First prose line.")

    def test_plain_markdown_without_frontmatter(self) -> None:
        summary = self._summary_for("# Example\n\nFirst prose line.\n")
        self.assertEqual(summary, "First prose line.")


class GenerateC4Tests(unittest.TestCase):
    def test_handles_catalog_without_system_object(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            catalog = workspace / "catalog"
            catalog.mkdir(parents=True, exist_ok=True)
            (catalog / "a.yaml").write_text(
                'schemaVersion: "1.0"\n'
                "uid: 01TESTAAAA-0001\n"
                "type: product_component\n"
                "name: Component A\n"
                "description: A test component.\n",
                encoding="utf-8",
            )
            (catalog / "b.yaml").write_text(
                'schemaVersion: "1.0"\n'
                "uid: 01TESTAAAA-0002\n"
                "type: product_component\n"
                "name: Component B\n"
                "description: A test component.\n",
                encoding="utf-8",
            )
            (catalog / "rel.yaml").write_text(
                'schemaVersion: "1.0"\n'
                "uid: 01TESTAAAA-0003\n"
                "type: relationship\n"
                "name: A to B\n"
                "source: 01TESTAAAA-0001\n"
                "target: 01TESTAAAA-0002\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = generate_c4.main(
                    ["--workspace", str(workspace), "--format", "structurizr", "--dry-run"]
                )

            self.assertEqual(exit_code, 0)
            # The relationship between the two system-less containers is still rendered.
            self.assertIn("01TESTAAAA_0001", stdout.getvalue())
            self.assertIn("01TESTAAAA_0002", stdout.getvalue())


class DecisionRecordApprovalTests(unittest.TestCase):
    def test_open_record_passes_regardless_of_policy(self) -> None:
        obj = {
            "uid": "01TESTAAAA-0001",
            "type": "decision_record",
            "category": "risk",
            "status": "open",
        }
        failures: list[str] = []
        warnings: list[str] = []
        from framework.tools.validate import validate_decision_record
        validate_decision_record(
            obj,
            Path("dr.yaml"),
            catalog_by_id={},
            requirement_groups={},
            policy={"default": {"approver": "team:arb"}},
            failures=failures,
            warnings=warnings,
        )
        self.assertEqual(failures, [])

    def test_accepted_record_fails_without_approver_and_date(self) -> None:
        obj = {
            "uid": "01TESTAAAA-0001",
            "type": "decision_record",
            "category": "risk",
            "status": "accepted",
            "affectedComponent": "COMP-0001",
        }
        failures: list[str] = []
        warnings: list[str] = []
        from framework.tools.validate import validate_decision_record
        validate_decision_record(
            obj,
            Path("dr.yaml"),
            catalog_by_id={"COMP-0001": {"uid": "COMP-0001", "type": "product_component"}},
            requirement_groups={},
            policy={"default": {"approver": "team:arb"}},
            failures=failures,
            warnings=warnings,
        )
        self.assertTrue(any("requires an approver" in f for f in failures), failures)
        self.assertTrue(any("missing approvalDate" in f for f in failures), failures)

    def test_accepted_record_fails_without_scope(self) -> None:
        obj = {
            "uid": "01TESTAAAA-0001",
            "type": "decision_record",
            "category": "risk",
            "status": "accepted",
            "approver": "team:arb",
            "approvalDate": "2026-01-01",
        }
        failures: list[str] = []
        warnings: list[str] = []
        from framework.tools.validate import validate_decision_record
        validate_decision_record(
            obj,
            Path("dr.yaml"),
            catalog_by_id={},
            requirement_groups={},
            policy={"default": {"approver": "team:arb"}},
            failures=failures,
            warnings=warnings,
        )
        self.assertTrue(any("must declare an affectedComponent or linkedObject" in f for f in failures), failures)

    def test_accepted_record_fails_if_reused(self) -> None:
        obj = {
            "uid": "DR-0001",
            "type": "decision_record",
            "category": "risk",
            "status": "accepted",
            "affectedComponent": "COMP-0001",
            "approver": "team:arb",
            "approvalDate": "2026-01-01",
        }
        catalog = {
            "DR-0001": obj,
            "COMP-0001": {
                "uid": "COMP-0001",
                "type": "product_component",
                "requirementImplementations": [
                    {"requirementGroup": "RG-1", "requirementId": "REQ-1", "mechanism": "decisionRecord", "ref": "DR-0001"},
                ]
            },
            "COMP-0002": {
                "uid": "COMP-0002",
                "type": "product_component",
                "requirementImplementations": [
                    {"requirementGroup": "RG-1", "requirementId": "REQ-2", "mechanism": "decisionRecord", "ref": "DR-0001"},
                ]
            }
        }
        failures: list[str] = []
        warnings: list[str] = []
        from framework.tools.validate import validate_decision_record
        validate_decision_record(
            obj,
            Path("dr.yaml"),
            catalog_by_id=catalog,
            requirement_groups={},
            policy={"default": {"approver": "team:arb"}},
            failures=failures,
            warnings=warnings,
        )
        self.assertTrue(any("is reused across multiple requirement implementations" in f for f in failures), failures)

    def test_policy_category_rule_matching(self) -> None:
        obj = {
            "uid": "DR-0001",
            "type": "decision_record",
            "category": "risk",
            "status": "accepted",
            "affectedComponent": "COMP-0001",
            "approver": "team:security",
            "approvalDate": "2026-01-01",
        }
        policy = {
            "default": {"approver": "team:arb"},
            "rules": [
                {"match": {"category": "risk"}, "approver": "team:security"}
            ]
        }
        failures: list[str] = []
        warnings: list[str] = []
        from framework.tools.validate import validate_decision_record
        validate_decision_record(
            obj,
            Path("dr.yaml"),
            catalog_by_id={"COMP-0001": {"uid": "COMP-0001", "type": "product_component"}},
            requirement_groups={},
            policy=policy,
            failures=failures,
            warnings=warnings,
        )
        self.assertEqual(failures, [])

    def test_policy_requirement_rule_matching(self) -> None:
        obj = {
            "uid": "DR-0001",
            "type": "decision_record",
            "category": "decision",
            "status": "accepted",
            "affectedComponent": "COMP-0001",
            "approver": "team:data-gov",
            "approvalDate": "2026-01-01",
            "decisionRationale": "Rationale",
        }
        catalog = {
            "DR-0001": obj,
            "COMP-0001": {
                "uid": "COMP-0001",
                "type": "product_component",
                "requirementImplementations": [
                    {"requirementGroup": "RG-1", "requirementId": "data-classification", "mechanism": "decisionRecord", "ref": "DR-0001"},
                ]
            }
        }
        policy = {
            "default": {"approver": "team:arb"},
            "rules": [
                {"match": {"requirement": "data-classification"}, "approver": "team:data-gov"}
            ]
        }
        failures: list[str] = []
        warnings: list[str] = []
        from framework.tools.validate import validate_decision_record
        validate_decision_record(
            obj,
            Path("dr.yaml"),
            catalog_by_id=catalog,
            requirement_groups={},
            policy=policy,
            failures=failures,
            warnings=warnings,
        )
        self.assertEqual(failures, [])

    def test_policy_domain_rule_matching(self) -> None:
        obj = {
            "uid": "DR-0001",
            "type": "decision_record",
            "category": "decision",
            "status": "accepted",
            "affectedComponent": "COMP-0001",
            "approver": "team:security-grc",
            "approvalDate": "2026-01-01",
            "decisionRationale": "Rationale",
        }
        catalog = {
            "DR-0001": obj,
            "COMP-0001": {
                "uid": "COMP-0001",
                "type": "product_component",
                "requirementImplementations": [
                    {"requirementGroup": "RG-1", "requirementId": "REQ-1", "mechanism": "decisionRecord", "ref": "DR-0001"},
                ]
            },
            "CAP-1": {
                "uid": "CAP-1",
                "type": "capability",
                "domain": "security",
            }
        }
        requirement_groups = {
            "RG-1": {
                "uid": "RG-1",
                "type": "requirement_group",
                "requirements": [
                    {"uid": "REQ-1", "relatedCapability": "CAP-1"}
                ]
            }
        }
        policy = {
            "default": {"approver": "team:arb"},
            "rules": [
                {"match": {"domain": "security"}, "approver": "team:security-grc"}
            ]
        }
        failures: list[str] = []
        warnings: list[str] = []
        from framework.tools.validate import validate_decision_record
        validate_decision_record(
            obj,
            Path("dr.yaml"),
            catalog_by_id=catalog,
            requirement_groups=requirement_groups,
            policy=policy,
            failures=failures,
            warnings=warnings,
        )
        self.assertEqual(failures, [])

    def test_policy_affected_component_owner_matching(self) -> None:
        obj = {
            "uid": "DR-0001",
            "type": "decision_record",
            "category": "decision",
            "status": "accepted",
            "affectedComponent": "COMP-0001",
            "approver": "team:platform-engineering",
            "approvalDate": "2026-06-21",
            "decisionRationale": "Rationale",
        }
        catalog = {
            "DR-0001": obj,
            "COMP-0001": {
                "uid": "COMP-0001",
                "type": "product_component",
                "owner": {"team": "platform-engineering"},
            }
        }
        policy = {
            "default": {"approver": "team:arb"},
            "rules": [
                {"match": {"affectedComponentOwner": True}, "approver": "ownerTeam"}
            ]
        }
        failures: list[str] = []
        warnings: list[str] = []
        from framework.tools.validate import validate_decision_record
        validate_decision_record(
            obj,
            Path("dr.yaml"),
            catalog_by_id=catalog,
            requirement_groups={},
            policy=policy,
            failures=failures,
            warnings=warnings,
        )
        self.assertEqual(failures, [])

    def test_policy_enforcement_none(self) -> None:
        obj = {
            "uid": "DR-0001",
            "type": "decision_record",
            "category": "decision",
            "status": "accepted",
        }
        failures: list[str] = []
        warnings: list[str] = []
        from framework.tools.validate import validate_decision_record
        validate_decision_record(
            obj,
            Path("dr.yaml"),
            catalog_by_id={},
            requirement_groups={},
            policy={"enforcement": "none"},
            failures=failures,
            warnings=warnings,
        )
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
