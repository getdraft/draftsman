from __future__ import annotations

import re
import shutil
import tempfile
import textwrap
import unittest
import subprocess
import sys
from pathlib import Path

from draft_table.paths import REPO_ROOT
from draft_table.repo import ensure_workspace_layout
from draft_table.validation import build_validate_command, validate_workspace


def grandfather_ratcheted_violations(workspace: Path) -> None:
    # Older-style fixtures place infrastructure in a pattern; the ratcheted ownership
    # rules (D49 to D51) would flag them, so record them in a baseline first.
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "framework" / "tools" / "validate.py"), "--workspace", str(workspace), "--write-baseline", "--quiet"],
        capture_output=True,
        text=True,
        check=False,
    )


class ValidationTests(unittest.TestCase):
    def _write_decision_records_for_sdp(self, workspace: Path, indent: int = 20) -> str:
        dr_dir = workspace / "catalog" / "decision-records"
        dr_dir.mkdir(parents=True, exist_ok=True)
        
        drs = {
            "dr.no-pattern": ("01HQ000001-DR01", "noApplicablePattern"),
            "dr.targets": ("01HQ000001-DR02", "deploymentTargets"),
            "dr.avail": ("01HQ000001-DR03", "availabilityRequirement"),
            "dr.data": ("01HQ000001-DR04", "dataClassification"),
            "dr.failure": ("01HQ000001-DR05", "failureDomain"),
            "dr.deviations": ("01HQ000001-DR06", "noPatternDeviations"),
            "dr.interactions": ("01HQ000001-DR07", "noAdditionalInteractions"),
            "dr.connections": ("01HQ000001-DR08", "noCrossBoundaryConnections"),
        }
        
        for name, (uid, key) in drs.items():
            (dr_dir / f"{name}.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: "{uid}"
                    type: decision_record
                    name: Decision for {key}
                    category: decision
                    status: accepted
                    catalogStatus: complete
                    lifecycleStatus: preferred
                    decisionRationale: "Rationale."
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
        
        lines = [
            "decisionRecords:",
            "  - ref: \"01HQ000001-DR01\"",
            "    key: noApplicablePattern",
            "  - ref: \"01HQ000001-DR02\"",
            "    key: deploymentTargets",
            "  - ref: \"01HQ000001-DR03\"",
            "    key: availabilityRequirement",
            "  - ref: \"01HQ000001-DR04\"",
            "    key: dataClassification",
            "  - ref: \"01HQ000001-DR05\"",
            "    key: failureDomain",
            "  - ref: \"01HQ000001-DR06\"",
            "    key: noPatternDeviations",
            "  - ref: \"01HQ000001-DR07\"",
            "    key: noAdditionalInteractions",
            "  - ref: \"01HQ000001-DR08\"",
            "    key: noCrossBoundaryConnections",
        ]
        return "\n".join(" " * indent + line for line in lines)

    def test_build_validate_command_targets_framework_tool(self) -> None:
        command = build_validate_command(REPO_ROOT / "examples")

        self.assertIn("framework/tools/validate.py", command[1])
        self.assertEqual(command[-2], "--workspace")
        self.assertEqual(Path(command[-1]), REPO_ROOT / "examples")

    def test_validate_examples_workspace(self) -> None:
        result = validate_workspace(REPO_ROOT / "examples")

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertIn("Validated", result.stdout)

    def test_edge_gateway_service_has_no_compatibility_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            catalog = workspace / "catalog" / "edge-gateway-services"
            catalog.mkdir(parents=True, exist_ok=True)
            (catalog / "edge-gateway-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF70-EDGE
                    type: edge_gateway_service
                    name: Retired Edge Gateway
                    deliveryModel: appliance
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("no schema found for type 'edge_gateway_service'", result.stdout)

    def test_missing_uid_reports_suggested_value_and_repair_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            component_dir = workspace / "catalog" / "technology-components"
            component_dir.mkdir(parents=True, exist_ok=True)
            (component_dir / "technology-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    type: technology_component
                    name: Test Technology
                    vendor: Test Vendor
                    productName: Test Product
                    productVersion: "1"
                    classification: software
                    catalogStatus: incomplete
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("Add required field 'uid' with generated value", result.stdout)
        self.assertIn("repair_uids.py", result.stdout)
        self.assertIn("--file catalog/technology-components/technology-test.yaml --uid", result.stdout)

    def test_malformed_uid_reports_suggested_value_and_repair_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            component_dir = workspace / "catalog" / "technology-components"
            component_dir.mkdir(parents=True, exist_ok=True)
            (component_dir / "technology-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: test-technology
                    type: technology_component
                    name: Test Technology
                    vendor: Test Vendor
                    productName: Test Product
                    productVersion: "1"
                    classification: software
                    catalogStatus: incomplete
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("Replace malformed uid 'test-technology' with generated value", result.stdout)
        self.assertIn("repair_uids.py", result.stdout)
        self.assertIn("--file catalog/technology-components/technology-test.yaml --uid", result.stdout)

    def test_build_validate_command_prefers_vendored_framework(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)

            command = build_validate_command(workspace)

        self.assertIn(".draft/framework/tools/validate.py", command[1])

    def test_validate_workspace_uses_vendored_framework(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)

    def test_workspace_capability_duplicate_native_name_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            capability_dir = workspace / "configurations" / "capabilities"
            capability_dir.mkdir(parents=True, exist_ok=True)
            (capability_dir / "capability-local-waf.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KT55KGQ2-96B8
                    type: capability
                    name: waf
                    description: Local WAF capability that predates the native framework WAF capability.
                    catalogStatus: incomplete
                    definitionOwner:
                      provider: local-workspace
                      team: platform
                    domain: 01KSWVZSZ5-4WKE
                    implementations: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertIn("duplicates native capability 'WAF'", result.stdout)
        self.assertIn("01KT55KGQ2-96B8", result.stdout)
        self.assertIn("01KT0V5MCV-Z079", result.stdout)

    def test_workspace_duplicate_name_warn_suppressed_by_native_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            patch_dir = workspace / "configurations" / "object-patches"
            patch_dir.mkdir(parents=True, exist_ok=True)
            (patch_dir / "patch-native-waf-alias.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KT55KHMT-FZT3
                    type: object_patch
                    name: Alias Native WAF
                    target: 01KT0V5MCV-Z079
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    patch:
                      aliases:
                        - WAF
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            capability_dir = workspace / "configurations" / "capabilities"
            capability_dir.mkdir(parents=True, exist_ok=True)
            (capability_dir / "capability-local-waf.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KT55KGQ2-96B8
                    type: capability
                    name: WAF
                    description: Local WAF capability intentionally preserved as an alias of the native object.
                    catalogStatus: incomplete
                    definitionOwner:
                      provider: local-workspace
                      team: platform
                    domain: 01KSWVZSZ5-4WKE
                    implementations: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotIn("duplicates native capability 'WAF'", result.stdout)

    def test_workspace_domain_duplicate_native_name_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            domain_dir = workspace / "configurations" / "domains"
            domain_dir.mkdir(parents=True, exist_ok=True)
            (domain_dir / "domain-local-compute.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KT55KH5Y-9N8F
                    type: domain
                    name: Compute & Runtime
                    description: Local compute domain that predates the native framework domain.
                    capabilities: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertIn("duplicates native domain 'Compute & Runtime'", result.stdout)
        self.assertIn("01KT55KH5Y-9N8F", result.stdout)
        self.assertIn("01KQQ4Q027-ZTHF", result.stdout)

    def test_active_requirement_group_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            (workspace / ".draft" / "workspace.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    workspace:
                      name: bad-compliance-config
                    framework:
                      source: https://github.com/getdraft/draftsman.git
                      vendoredPath: .draft/framework
                      updatePolicy: explicit
                    paths:
                      catalog: catalog
                      configurations: configurations
                    requirements:
                      activeRequirementGroups:
                        - requirement-group.missing
                      requireActiveRequirementGroupDisposition: false
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("was not found", result.stdout)

    def test_active_requirement_group_is_incremental_when_disposition_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)
            self._repair_workspace_uids(workspace)

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)

    def test_active_requirement_group_is_enforced_when_disposition_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=True)
            self._repair_workspace_uids(workspace)

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("Requirement not satisfied: Company Control / company-required-field", result.stdout)

    def test_self_managed_runtime_service_requires_host_substrate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            service_dir = workspace / "catalog" / "runtime-services"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "runtime-service-missing-host.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF51-ABCD
                    type: runtime_service
                    name: Missing Host Runtime
                    deliveryModel: self-managed
                    catalogStatus: complete
                    lifecycleStatus: candidate
                    notes:
                      serviceAuthentication: Uses centralized identity.
                      secretsManagement: Uses managed secrets injection.
                      serviceLogging: Emits logs to the central logging platform.
                      healthWelfareMonitoring: Exposes health telemetry.
                      availabilityModel: Single-instance candidate service.
                      scalabilityModel: Horizontal scaling not yet approved.
                      recoverabilityModel: Recreated from deployment automation.
                      failureDomain: Single service instance.
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("DRAFT Service Behavior / runtime-substrate", result.stdout)
        self.assertIn("field(host)", result.stdout)

    def test_software_deployment_pattern_rejects_direct_host_refs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            host_dir = workspace / "catalog" / "hosts"
            host_dir.mkdir(parents=True, exist_ok=True)
            (host_dir / "host-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF52-HOST
                    type: host
                    name: Test Host
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            pattern_dir = workspace / "catalog" / "software-deployment-patterns"
            pattern_dir.mkdir(parents=True, exist_ok=True)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            (pattern_dir / "software-deployment-pattern-host-ref.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: 01KQS0TF53-SDMP
                    type: software_deployment_pattern
                    name: Host Ref Pattern
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
{dr_yaml}
                    serviceGroups:
                      - name: Application Tier
                        deploymentTarget: Test target
                        deployableObjects:
                          - ref: 01KQS0TF52-HOST
                            diagramTier: application
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("references host '01KQS0TF52-HOST' directly", result.stdout)

    def test_requirement_implementation_evidence_satisfies_declared_workspace_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)
            (workspace / "configurations" / "requirement-groups" / "requirement-group-company-control.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: requirement-group.company-control
                    type: requirement_group
                    name: Company Control
                    description: Workspace-mode control group used by validation tests.
                    catalogStatus: incomplete
                    owner:
                      team: test
                    activation: workspace
                    appliesTo:
                      - product_component
                    requirements:
                      - id: company-required-field
                        description: Product services must provide company evidence.
                        rationale: Test requirement for workspace-mode evidence.
                        requirementMode: mandatory
                        naAllowed: false
                        canBeSatisfiedBy:
                          - mechanism: field
                            key: notes.companyEvidence
                        minimumSatisfactions: 1
                        validAnswerTypes:
                          - field
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (workspace / "catalog" / "product-components" / "product-service-test-app.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: product-service.test.app
                    type: product_component
                    name: Test App
                    repoUrl: https://github.com/test/test-app
                    owner:
                      team: test
                    classification: api-service
                    runtimeRequirement: Node 20
                    runsOn: host.test
                    catalogStatus: complete
                    lifecycleStatus: existing-only
                    requirementGroups:
                      - requirement-group.company-control
                    notes:
                      companyEvidence: Provided by explicit object-level evidence.
                    requirementImplementations:
                      - requirementGroup: requirement-group.company-control
                        requirementId: company-required-field
                        status: satisfied
                        mechanism: field
                        key: notes.companyEvidence
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)


    def test_decision_record_implementation_requires_matching_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)

            dr_dir = workspace / "catalog" / "decision-records"
            dr_dir.mkdir(parents=True, exist_ok=True)
            (dr_dir / "dr-wrong-key.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: dr.wrong-key
                    type: decision_record
                    name: Wrong Key Decision
                    category: decision
                    status: accepted
                    catalogStatus: complete
                    lifecycleStatus: preferred
                    decisionRationale: Captures a different decision topic.
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            (workspace / "catalog" / "product-components" / "product-service-test-app.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: product-service.test.app
                    type: product_component
                    name: Test App
                    repoUrl: https://github.com/test/test-app
                    owner:
                      team: test
                    classification: api-service
                    runtimeRequirement: Node 20
                    runsOn: host.test
                    catalogStatus: complete
                    lifecycleStatus: existing-only
                    requirementGroups:
                      - requirement-group.company-control
                    decisionRecords:
                      - ref: dr.wrong-key
                        key: unrelatedDecision
                    requirementImplementations:
                      - requirementGroup: requirement-group.company-control
                        requirementId: company-required-field
                        status: satisfied
                        mechanism: decisionRecord
                        key: notes.companyEvidence
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("company-required-field", result.stdout)

    def _write_workspace_requirement_fixture(self, workspace: Path, require_disposition: bool) -> None:
        (workspace / ".draft" / "workspace.yaml").write_text(
            textwrap.dedent(
                f"""
                schemaVersion: "1.0"
                workspace:
                  name: incremental-compliance-config
                framework:
                  source: https://github.com/getdraft/draftsman.git
                  vendoredPath: .draft/framework
                  updatePolicy: explicit
                paths:
                  catalog: catalog
                  configurations: configurations
                requirements:
                  activeRequirementGroups:
                    - requirement-group.company-control
                  requireActiveRequirementGroupDisposition: {str(require_disposition).lower()}
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        group_dir = workspace / "configurations" / "requirement-groups"
        group_dir.mkdir(parents=True, exist_ok=True)
        (group_dir / "requirement-group-company-control.yaml").write_text(
            textwrap.dedent(
                """
                schemaVersion: "1.0"
                id: requirement-group.company-control
                type: requirement_group
                name: Company Control
                description: Workspace-mode control group used by validation tests.
                catalogStatus: incomplete
                owner:
                  team: test
                activation: workspace
                appliesTo:
                  - product_component
                requirements:
                  - id: company-required-field
                    description: Product services must provide the company required field when disposition is required.
                    rationale: Test requirement for workspace-mode enforcement.
                    requirementMode: mandatory
                    naAllowed: false
                    canBeSatisfiedBy:
                      - mechanism: field
                        key: companyRequiredField
                    minimumSatisfactions: 1
                    validAnswerTypes:
                      - field
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        host_dir = workspace / "catalog" / "hosts"
        host_dir.mkdir(parents=True, exist_ok=True)
        (host_dir / "host-test.yaml").write_text(
            textwrap.dedent(
                """
                schemaVersion: "1.0"
                id: host.test
                type: host
                name: Test Host
                catalogStatus: stub
                lifecycleStatus: existing-only
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        product_dir = workspace / "catalog" / "product-components"
        product_dir.mkdir(parents=True, exist_ok=True)
        (product_dir / "product-service-test-app.yaml").write_text(
            textwrap.dedent(
                """
                schemaVersion: "1.0"
                id: product-service.test.app
                type: product_component
                name: Test App
                repoUrl: https://github.com/test/test-app
                owner:
                  team: test
                classification: api-service
                runtimeRequirement: Node 20
                runsOn: host.test
                catalogStatus: complete
                lifecycleStatus: existing-only
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def _repair_workspace_uids(self, workspace: Path) -> None:
        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "framework" / "tools" / "repair_uids.py"),
                "--workspace",
                str(workspace),
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def _write_complete_host_with_extra_apm_interaction(
        self,
        workspace: Path,
        include_rationale: bool,
        rationale_kind: str = "internal",
        include_apm_interaction: bool = True,
        apm_classification: str = "agent",
    ) -> None:
        tech_dir = workspace / "catalog" / "technology-components"
        host_dir = workspace / "catalog" / "hosts"
        tech_dir.mkdir(parents=True, exist_ok=True)
        host_dir.mkdir(parents=True, exist_ok=True)
        components = {
            "technology-os-test.yaml": (
                "01KQS0TF60-ABCD",
                "Test Operating System",
                "operating-system",
                ["01KQQ4Q026-QM2X"],
            ),
            "technology-compute-test.yaml": (
                "01KQS0TF60-EFGH",
                "Test Compute Platform",
                "compute-platform",
                ["01KQQ4Q026-1HZP"],
            ),
            "technology-security-agent-test.yaml": (
                "01KQS0TF60-JKMX",
                "Test Security Agent",
                "agent",
                ["01KQQ4Q026-JW52"],
            ),
            "technology-patch-agent-test.yaml": (
                "01KQS0TF60-NPQR",
                "Test Patch Agent",
                "agent",
                ["01KQQ4Q026-BH6E"],
            ),
            "technology-apm-agent-test.yaml": (
                "01KQS0TF60-STVW",
                "Test APM Agent",
                apm_classification,
                ["01KQQ4Q026-NB1W"],
            ),
        }
        for filename, (uid, name, classification, capabilities) in components.items():
            capability_lines = "\n".join(f"  - {capability}" for capability in capabilities)
            (tech_dir / filename).write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: {uid}
                    type: technology_component
                    name: {name}
                    vendor: Test Vendor
                    productName: {name}
                    productVersion: "1"
                    classification: {classification}
                    catalogStatus: incomplete
                    capabilities:
                    {capability_lines}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

        base_notes = textwrap.dedent(
            """\
            authenticationApproach: Federated via enterprise identity platform.
            loggingApproach: Log forwarding to centralized logging platform.
            healthWelfareMonitoringApproach: Host telemetry shipped to monitoring platform.
            agentInteractionExceptions:
              01KQS0TF60-JKMX: Security agent platform interaction is implicit in enterprise security posture.
              01KQS0TF60-NPQR: Patch agent platform interaction is implicit in enterprise patch management posture.\
            """
        )
        if include_rationale:
            extra_note = (
                "internalComponentRationales:\n"
                "  01KQS0TF60-STVW: Included as optional application performance telemetry for runtimes deployed on this host standard."
            )
        else:
            extra_note = "lifecycleRationale: Test approved host fixture."
        all_notes = base_notes + "\n" + extra_note
        decision_lines = textwrap.indent(all_notes, "  ")
        decision_dir = workspace / "catalog" / "decision-records"
        decision_dir.mkdir(parents=True, exist_ok=True)
        (decision_dir / "dr-test-host-operations.yaml").write_text(
            textwrap.dedent(
                """\
                schemaVersion: "1.0"
                uid: 01KQS0TF60-DR01
                type: decision_record
                name: Test Complete Host — operations decisions
                category: decision
                status: accepted
                catalogStatus: complete
                lifecycleStatus: preferred
                decisionRationale: >-
                  Authentication is federated via the enterprise identity platform, logs are forwarded to
                  the centralized logging platform, and host telemetry is shipped to the monitoring platform.
                """
            ),
            encoding="utf-8",
        )
        (host_dir / "host-test-complete.yaml").write_text(
            f"""schemaVersion: "1.0"
uid: 01KQS0TF60-XYZ1
type: host
name: Test Complete Host
catalogStatus: complete
lifecycleStatus: preferred
category: host
operatingSystemComponent: 01KQS0TF60-ABCD
computePlatformComponent: 01KQS0TF60-EFGH
internalComponents:
  - ref: 01KQS0TF60-ABCD
    role: os
  - ref: 01KQS0TF60-EFGH
    role: hardware
  - ref: 01KQS0TF60-JKMX
    role: agent
  - ref: 01KQS0TF60-NPQR
    role: agent
  - ref: 01KQS0TF60-STVW
    role: agent
notes:
{decision_lines}
decisionRecords:
  - ref: 01KQS0TF60-DR01
    key: authenticationApproach
  - ref: 01KQS0TF60-DR01
    key: loggingApproach
  - ref: 01KQS0TF60-DR01
    key: healthWelfareMonitoringApproach
requirementGroups:
  - 01KQQ4Q027-THYN
""",
            encoding="utf-8",
        )

    def test_appliance_delivery_satisfies_service_like_capabilities_directly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            catalog = workspace / "catalog" / "network-services"
            catalog.mkdir(parents=True)
            (workspace / "configurations").mkdir()
            (catalog / "network-service-aws-alb.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: network-service.aws-alb
                    type: network_service
                    name: AWS Application Load Balancer
                    deliveryModel: appliance
                    vendor: Amazon Web Services
                    productName: Application Load Balancer
                    productVersion: managed
                    classification: software
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    capabilities:
                      - capability.compute
                    configurations:
                      - id: enterprise-access
                        name: Enterprise Access
                        description: SAML-authenticated administrative access.
                        capabilities:
                          - capability.authentication
                      - id: managed-health
                        name: Managed Health Visibility
                        description: Publishes target and appliance health.
                        capabilities:
                          - capability.health-welfare-monitoring
                    networkPlacement: public-facing
                    patchingOwner: aws-managed
                    complianceCerts: []
                    notes:
                      resilienceModel: Managed multi-AZ control plane.
                      configurableSurface: Listeners, rules, certificates, and target groups.
                      failureDomain: Shared ingress dependency for the protected application path.
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)

    def test_unrequired_host_internal_component_requires_architectural_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_complete_host_with_extra_apm_interaction(
                workspace,
                include_rationale=False,
                include_apm_interaction=False,
                apm_classification="software",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("internalComponentRationales['01KQS0TF60-STVW']", result.stdout)
        self.assertIn("does not directly satisfy any applicable requirement", result.stdout)

    def test_unrequired_host_internal_component_with_architectural_decision_validates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_complete_host_with_extra_apm_interaction(
                workspace,
                include_rationale=True,
                rationale_kind="internal",
                include_apm_interaction=False,
                apm_classification="software",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotIn("does not directly satisfy any applicable requirement", result.stdout)

    def _write_data_service_decision_record(self, decision_dir: Path, uid: str = "01KQS0TF61-DR01") -> None:
        decision_dir.mkdir(parents=True, exist_ok=True)
        (decision_dir / f"dr-{uid}.yaml").write_text(
            textwrap.dedent(
                f"""
                schemaVersion: "1.0"
                uid: {uid}
                type: decision_record
                name: Test Data Service — operations decisions
                category: decision
                status: accepted
                catalogStatus: complete
                lifecycleStatus: preferred
                decisionRationale: >-
                  Records the authentication, secrets, logging, monitoring, resilience, backup, encryption,
                  and access-control decisions for the Test Data Service.
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def test_primary_technology_component_internal_component_validates_without_rationale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            tech_dir = workspace / "catalog" / "technology-components"
            host_dir = workspace / "catalog" / "hosts"
            data_dir = workspace / "catalog" / "data-store-services"
            tech_dir.mkdir(parents=True, exist_ok=True)
            host_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            (tech_dir / "technology-db-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF61-DBMS
                    type: technology_component
                    name: Test DBMS
                    vendor: Test Vendor
                    productName: Test DBMS
                    productVersion: "1"
                    classification: software
                    catalogStatus: incomplete
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (host_dir / "host-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF61-HST1
                    type: host
                    name: Test Host
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (data_dir / "database-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF61-DATA
                    type: data_store_service
                    name: Test Data Service
                    deliveryModel: self-managed
                    catalogStatus: complete
                    lifecycleStatus: preferred
                    host: 01KQS0TF61-HST1
                    primaryTechnologyComponent: 01KQS0TF61-DBMS
                    internalComponents:
                      - ref: 01KQS0TF61-HST1
                        role: host
                      - ref: 01KQS0TF61-DBMS
                        role: function
                    notes:
                      serviceAuthentication: Uses centralized identity.
                      secretsManagement: Uses managed secrets injection.
                      serviceLogging: Emits logs to the central logging platform.
                      healthWelfareMonitoring: Exposes health telemetry.
                      availabilityModel: Single-instance candidate service.
                      scalabilityModel: Vertical scale.
                      recoverabilityModel: Recreated from deployment automation.
                      failureDomain: Single database service instance.
                      backup:
                        strategy: Daily full backup.
                        platform: Test backup vault.
                        rto: 4h
                        rpo: 24h
                      ha:
                        mechanism: none
                      encryption:
                        atRest: encrypted storage
                      accessControl:
                        model: Role-based access.
                    decisionRecords:
                      - ref: 01KQS0TF61-DR01
                        key: serviceAuthentication
                      - ref: 01KQS0TF61-DR01
                        key: secretsManagement
                      - ref: 01KQS0TF61-DR01
                        key: serviceLogging
                      - ref: 01KQS0TF61-DR01
                        key: healthWelfareMonitoring
                      - ref: 01KQS0TF61-DR01
                        key: availabilityModel
                      - ref: 01KQS0TF61-DR01
                        key: scalabilityModel
                      - ref: 01KQS0TF61-DR01
                        key: recoverabilityModel
                      - ref: 01KQS0TF61-DR01
                        key: failureDomain
                      - ref: 01KQS0TF61-DR01
                        key: backup.strategy
                      - ref: 01KQS0TF61-DR01
                        key: backup.platform
                      - ref: 01KQS0TF61-DR01
                        key: backup.rto
                      - ref: 01KQS0TF61-DR01
                        key: backup.rpo
                      - ref: 01KQS0TF61-DR01
                        key: ha.mechanism
                      - ref: 01KQS0TF61-DR01
                        key: encryption.atRest
                      - ref: 01KQS0TF61-DR01
                        key: accessControl.model
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._write_data_service_decision_record(data_dir.parent / "decision-records")

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotIn("internalComponentRationales['01KQS0TF61-DBMS']", result.stdout)
        self.assertNotIn("does not directly satisfy any applicable requirement", result.stdout)

    def test_backup_platform_relationship_satisfies_data_store_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            tech_dir = workspace / "catalog" / "technology-components"
            host_dir = workspace / "catalog" / "hosts"
            data_dir = workspace / "catalog" / "data-store-services"
            rel_dir = workspace / "catalog" / "relationships"
            tech_dir.mkdir(parents=True, exist_ok=True)
            host_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            rel_dir.mkdir(parents=True, exist_ok=True)
            (tech_dir / "technology-db-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF62-DBMS
                    type: technology_component
                    name: Test DBMS
                    vendor: Test Vendor
                    productName: Test DBMS
                    productVersion: "1"
                    classification: software
                    catalogStatus: incomplete
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (host_dir / "host-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF62-HST1
                    type: host
                    name: Test Host
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (data_dir / "database-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF62-DATA
                    type: data_store_service
                    name: Test Data Service
                    deliveryModel: self-managed
                    catalogStatus: complete
                    lifecycleStatus: preferred
                    host: 01KQS0TF62-HST1
                    primaryTechnologyComponent: 01KQS0TF62-DBMS
                    internalComponents:
                      - ref: 01KQS0TF62-HST1
                        role: host
                      - ref: 01KQS0TF62-DBMS
                        role: function
                    notes:
                      serviceAuthentication: Uses centralized identity.
                      secretsManagement: Uses managed secrets injection.
                      serviceLogging: Emits logs to the central logging platform.
                      healthWelfareMonitoring: Exposes health telemetry.
                      availabilityModel: Single-instance candidate service.
                      scalabilityModel: Vertical scale.
                      recoverabilityModel: Recreated from deployment automation.
                      failureDomain: Single database service instance.
                      backup:
                        strategy: Daily full backup.
                        rto: 4h
                        rpo: 24h
                      ha:
                        mechanism: none
                      encryption:
                        atRest: encrypted storage
                      accessControl:
                        model: Role-based access.
                    decisionRecords:
                      - ref: 01KQS0TF62-DR01
                        key: serviceAuthentication
                      - ref: 01KQS0TF62-DR01
                        key: secretsManagement
                      - ref: 01KQS0TF62-DR01
                        key: serviceLogging
                      - ref: 01KQS0TF62-DR01
                        key: healthWelfareMonitoring
                      - ref: 01KQS0TF62-DR01
                        key: availabilityModel
                      - ref: 01KQS0TF62-DR01
                        key: scalabilityModel
                      - ref: 01KQS0TF62-DR01
                        key: recoverabilityModel
                      - ref: 01KQS0TF62-DR01
                        key: failureDomain
                      - ref: 01KQS0TF62-DR01
                        key: backup.strategy
                      - ref: 01KQS0TF62-DR01
                        key: backup.rto
                      - ref: 01KQS0TF62-DR01
                        key: backup.rpo
                      - ref: 01KQS0TF62-DR01
                        key: ha.mechanism
                      - ref: 01KQS0TF62-DR01
                        key: encryption.atRest
                      - ref: 01KQS0TF62-DR01
                        key: accessControl.model
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._write_data_service_decision_record(
                data_dir.parent / "decision-records", uid="01KQS0TF62-DR01"
            )
            system_dir = workspace / "catalog" / "systems"
            listener_dir = workspace / "catalog" / "listeners"
            system_dir.mkdir(parents=True, exist_ok=True)
            listener_dir.mkdir(parents=True, exist_ok=True)
            (system_dir / "system-backup-vault.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF62-SYS1
                    type: system
                    name: Test Backup Vault
                    catalogStatus: stub
                    lifecycleStatus: existing-only
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (listener_dir / "listener-backup-vault.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF62-BKP1
                    type: listener
                    name: Test Backup Vault listener
                    owner:
                      kind: external_system
                      ref: 01KQS0TF62-SYS1
                    protocol: HTTPS
                    port: 443
                    endpoint: /
                    authenticationModel: iam
                    catalogStatus: stub
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (rel_dir / "rel-backup-vault.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF62-RR1A
                    type: relationship
                    name: Test Data Service to Test Backup Vault
                    catalogStatus: stub
                    source: 01KQS0TF62-DATA
                    externalTarget: Test Backup Vault
                    targetListener: 01KQS0TF62-BKP1
                    label: backs up to
                    direction: synchronous
                    capabilities:
                      - 01KQQ4Q026-7T2H
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotIn("does not directly satisfy any applicable requirement", result.stdout)

    def test_technology_component_configuration_accepts_network_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            tech_dir = workspace / "catalog" / "technology-components"
            tech_dir.mkdir(parents=True, exist_ok=True)
            (tech_dir / "technology-rabbitmq.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF63-RBMQ
                    type: technology_component
                    name: RabbitMQ 3.13
                    vendor: Broadcom
                    productName: RabbitMQ
                    productVersion: "3.13"
                    classification: software
                    catalogStatus: incomplete
                    configurations:
                      - id: amqp-listener
                        name: AMQP Listener
                        description: Standard AMQP listener configuration.
                        capabilities:
                          - 01KQQ4Q026-D04B
                        networkBindings:
                          - port: 5672
                            protocol: AMQP
                            direction: inbound
                            description: AMQP client listener.
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)

    def test_technology_component_network_binding_validates_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            tech_dir = workspace / "catalog" / "technology-components"
            tech_dir.mkdir(parents=True, exist_ok=True)
            (tech_dir / "technology-rabbitmq.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF64-RBMQ
                    type: technology_component
                    name: RabbitMQ 3.13
                    vendor: Broadcom
                    productName: RabbitMQ
                    productVersion: "3.13"
                    classification: software
                    catalogStatus: incomplete
                    configurations:
                      - id: amqp-listener
                        name: AMQP Listener
                        description: Standard AMQP listener configuration.
                        capabilities:
                          - 01KQQ4Q026-D04B
                        networkBindings:
                          - port: "5672"
                            protocol: AMQP
                            direction: sideways
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("Change field 'port' to type int", result.stdout)
        self.assertIn("Set direction to one of", result.stdout)

    def test_internal_component_configuration_must_exist_on_referenced_technology_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            tech_dir = workspace / "catalog" / "technology-components"
            host_dir = workspace / "catalog" / "hosts"
            product_dir = workspace / "catalog" / "product-components"
            tech_dir.mkdir(parents=True, exist_ok=True)
            host_dir.mkdir(parents=True, exist_ok=True)
            product_dir.mkdir(parents=True, exist_ok=True)
            (tech_dir / "technology-rabbitmq.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF65-RBMQ
                    type: technology_component
                    name: RabbitMQ 3.13
                    vendor: Broadcom
                    productName: RabbitMQ
                    productVersion: "3.13"
                    classification: software
                    catalogStatus: incomplete
                    configurations:
                      - id: amqp-listener
                        name: AMQP Listener
                        description: Standard AMQP listener configuration.
                        capabilities:
                          - 01KQQ4Q026-D04B
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (host_dir / "host-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF65-HST1
                    type: host
                    name: Test Host
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (product_dir / "product-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF65-PRDS
                    type: product_component
                    name: Messaging API
                    repoUrl: https://github.com/test/messaging-api
                    owner:
                      team: test
                    classification: api-service
                    runsOn: 01KQS0TF65-HST1
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    internalComponents:
                      - ref: 01KQS0TF65-RBMQ
                        role: broker-client
                        configuration: missing-listener
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("internalComponents[0].configuration references unknown configuration 'missing-listener'", result.stdout)

    def test_product_component_accepts_configured_components(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            tech_dir = workspace / "catalog" / "technology-components"
            host_dir = workspace / "catalog" / "hosts"
            product_dir = workspace / "catalog" / "product-components"
            tech_dir.mkdir(parents=True, exist_ok=True)
            host_dir.mkdir(parents=True, exist_ok=True)
            product_dir.mkdir(parents=True, exist_ok=True)
            (tech_dir / "technology-rabbitmq.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF66-RBMQ
                    type: technology_component
                    name: RabbitMQ 3.13
                    vendor: Broadcom
                    productName: RabbitMQ
                    productVersion: "3.13"
                    classification: software
                    catalogStatus: incomplete
                    configurations:
                      - id: amqp-listener
                        name: AMQP Listener
                        description: Standard AMQP listener configuration.
                        capabilities:
                          - 01KQQ4Q026-D04B
                        networkBindings:
                          - port: 5672
                            protocol: AMQP
                            direction: inbound
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (host_dir / "host-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF66-HST1
                    type: host
                    name: Test Host
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (product_dir / "product-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF66-PRDS
                    type: product_component
                    name: Messaging API
                    repoUrl: https://github.com/test/messaging-api
                    owner:
                      team: test
                    classification: api-service
                    runsOn: 01KQS0TF66-HST1
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    internalComponents:
                      - ref: 01KQS0TF66-RBMQ
                        role: broker-client
                        configuration: amqp-listener
                    notes:
                      internalComponentRationales:
                        01KQS0TF66-RBMQ: Required broker client dependency for queue-mediated message publishing.
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotIn("unknown configuration", result.stdout)
        self.assertNotIn("unknown configuration", result.stdout)

    def test_product_component_endpoint_protocol_validates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            host_dir = workspace / "catalog" / "hosts"
            product_dir = workspace / "catalog" / "product-components"
            host_dir.mkdir(parents=True, exist_ok=True)
            product_dir.mkdir(parents=True, exist_ok=True)
            (host_dir / "host-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF67-HST1
                    type: host
                    name: Test Host
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (product_dir / "product-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF67-PRDS
                    type: product_component
                    name: Messaging API
                    repoUrl: https://github.com/test/messaging-api
                    owner:
                      team: test
                    classification: api-service
                    runsOn: 01KQS0TF67-HST1
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    interfaces:
                      - name: Invalid API
                        protocol: SOAP
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("Set protocol to one of", result.stdout)

    def test_product_component_runtime_spec_validates_ports_and_dependency_refs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            host_dir = workspace / "catalog" / "hosts"
            product_dir = workspace / "catalog" / "product-components"
            host_dir.mkdir(parents=True, exist_ok=True)
            product_dir.mkdir(parents=True, exist_ok=True)
            (host_dir / "host-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KTS0TF92-HST1
                    type: host
                    name: Test Host
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (product_dir / "product-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KTS0TF92-PRDS
                    type: product_component
                    name: Messaging API
                    repoUrl: https://github.com/test/messaging-api
                    owner:
                      team: test
                    classification: api-service
                    runsOn: 01KTS0TF92-HST1
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    runtimeSpec:
                      ports:
                        - number: 8080
                          protocol: HTTP
                          name: web
                      dependencies:
                        - ref: 01KTS0TF92-HST1
                          purpose: loads external configuration files
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)

    def test_product_component_runtime_spec_rejects_bad_port_and_unknown_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            host_dir = workspace / "catalog" / "hosts"
            product_dir = workspace / "catalog" / "product-components"
            host_dir.mkdir(parents=True, exist_ok=True)
            product_dir.mkdir(parents=True, exist_ok=True)
            (host_dir / "host-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KTS0TF93-HST1
                    type: host
                    name: Test Host
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (product_dir / "product-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KTS0TF93-PRDS
                    type: product_component
                    name: Messaging API
                    repoUrl: https://github.com/test/messaging-api
                    owner:
                      team: test
                    classification: api-service
                    runsOn: 01KTS0TF93-HST1
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    runtimeSpec:
                      ports:
                        - number: "8080"
                          protocol: HTTP
                          name: web
                      dependencies:
                        - ref: 01KTS0TF93-NONE
                          purpose: loads external configuration files
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("runtimeSpec: ports[0]: Change field 'number' to type int", result.stdout)
        self.assertIn("runtimeSpec.dependencies[0].ref references unknown object '01KTS0TF93-NONE'", result.stdout)

    def test_product_component_dependency_without_rationale_fails_when_approved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            tech_dir = workspace / "catalog" / "technology-components"
            host_dir = workspace / "catalog" / "hosts"
            product_dir = workspace / "catalog" / "product-components"
            tech_dir.mkdir(parents=True, exist_ok=True)
            host_dir.mkdir(parents=True, exist_ok=True)
            product_dir.mkdir(parents=True, exist_ok=True)
            (tech_dir / "technology-rabbitmq.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF68-RBMQ
                    type: technology_component
                    name: RabbitMQ 3.13
                    vendor: Broadcom
                    productName: RabbitMQ
                    productVersion: "3.13"
                    classification: software
                    catalogStatus: incomplete
                    configurations:
                      - id: amqp-listener
                        name: AMQP Listener
                        description: Standard AMQP listener configuration.
                        capabilities:
                          - 01KQQ4Q026-D04B
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (host_dir / "host-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF68-HST1
                    type: host
                    name: Test Host
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (product_dir / "product-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF68-PRDS
                    type: product_component
                    name: Messaging API
                    repoUrl: https://github.com/test/messaging-api
                    owner:
                      team: test
                    classification: api-service
                    runsOn: 01KQS0TF68-HST1
                    catalogStatus: complete
                    lifecycleStatus: candidate
                    internalComponents:
                      - ref: 01KQS0TF68-RBMQ
                        role: broker-client
                        configuration: amqp-listener
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("internalComponentRationales['01KQS0TF68-RBMQ']", result.stdout)
        self.assertIn("does not directly satisfy any applicable requirement", result.stdout)

    def test_capability_implementation_requires_company_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            patch_dir = workspace / "configurations" / "object-patches"
            tech_dir = workspace / "catalog" / "technology-components"
            patch_dir.mkdir(parents=True)
            tech_dir.mkdir(parents=True)
            (tech_dir / "technology-agent-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: technology.agent.test
                    type: technology_component
                    name: Test Agent
                    vendor: Test Vendor
                    productName: Test Agent
                    productVersion: "1"
                    classification: agent
                    catalogStatus: incomplete
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (patch_dir / "patch-security-monitoring.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: patch.test.security-monitoring
                    type: object_patch
                    name: Test Security Monitoring Implementation
                    target: capability.security-monitoring
                    catalogStatus: incomplete
                    lifecycleStatus: existing-only
                    patch:
                      implementations:
                        - ref: technology.agent.test
                          lifecycleStatus: preferred
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("Add owner.team before assigning capability implementations", result.stdout)

    def test_capability_implementation_ref_allows_shared_services(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            patch_dir = workspace / "configurations" / "object-patches"
            service_dir = workspace / "catalog" / "runtime-services"
            patch_dir.mkdir(parents=True)
            service_dir.mkdir(parents=True)
            (service_dir / "service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: service.test
                    type: runtime_service
                    deliveryModel: saas
                    vendor: Amazon Web Services
                    productName: RDS
                    productVersion: Postgresql-15
                    name: Test Service
                    catalogStatus: stub
                    lifecycleStatus: existing-only
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (patch_dir / "patch-security-monitoring.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: patch.test.security-monitoring
                    type: object_patch
                    name: Test Security Monitoring Implementation
                    target: capability.security-monitoring
                    catalogStatus: incomplete
                    lifecycleStatus: existing-only
                    patch:
                      owner:
                        team: security-engineering
                      implementations:
                        - ref: service.test
                          lifecycleStatus: preferred
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)

    def test_capability_implementation_ref_rejects_invalid_types(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            patch_dir = workspace / "configurations" / "object-patches"
            system_dir = workspace / "catalog" / "systems"
            patch_dir.mkdir(parents=True)
            system_dir.mkdir(parents=True)
            (system_dir / "system-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: system.test
                    type: system
                    name: Test System
                    catalogStatus: stub
                    lifecycleStatus: existing-only
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (patch_dir / "patch-security-monitoring.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: patch.test.security-monitoring
                    type: object_patch
                    name: Test Security Monitoring Implementation
                    target: capability.security-monitoring
                    catalogStatus: incomplete
                    lifecycleStatus: existing-only
                    patch:
                      owner:
                        team: security-engineering
                      implementations:
                        - ref: system.test
                          lifecycleStatus: preferred
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("capability lifecycle applies only to discrete vendor product versions or shared enterprise services", result.stdout)

    def test_advisory_vocabulary_reports_non_standard_value_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_vocabulary_workspace(workspace, mode="advisory")
            self._write_sdp_with_deployment_target(workspace, deployment_target="gcp-us-central1")

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertIn("uses a non-standard value", result.stdout)
        self.assertIn("serviceGroups[0].deploymentTarget", result.stdout)

    def test_gated_vocabulary_reports_non_standard_value_as_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_vocabulary_workspace(workspace, mode="gated")
            self._write_sdp_with_deployment_target(workspace, deployment_target="gcp-us-central1")

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("uses a non-standard value", result.stdout)
        self.assertIn("Approved values: aws-us-east-2", result.stdout)

    def test_apply_vocabulary_proposals_creates_review_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            proposal_dir = workspace / "configurations" / "vocabulary-proposals"
            proposal_dir.mkdir(parents=True, exist_ok=True)
            (proposal_dir / "gcp-us-central1.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    type: vocabulary_proposal
                    name: Add GCP US Central 1
                    vocabulary: deploymentTargets
                    proposalKind: non-standard-value
                    status: proposed
                    proposedId: gcp-us-central1
                    proposedName: GCP US Central 1
                    entry:
                      type: cloud-region
                      provider: gcp
                    fieldRefs:
                      - object: 01KQS0TF70-SDMP
                        path: serviceGroups[0].deploymentTarget
                        value: gcp-us-central1
                    rationale: Required by the proposed GCP deployment boundary.
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "framework" / "tools" / "apply_vocabulary_proposals.py"),
                    "--workspace",
                    str(workspace),
                ],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            created = workspace / "configurations" / "vocabulary" / "deployment-targets.yaml"
            created_text = created.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("gcp-us-central1", created_text)
        self.assertIn("status: proposed", created_text)

    def test_ra_constraint_violation_fails_sdp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            ra_dir = workspace / "configurations" / "reference-architectures"
            ra_dir.mkdir(parents=True, exist_ok=True)
            (ra_dir / "ra-test-constraint.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF71-RAXC
                    type: reference_architecture
                    name: Test Constraint RA
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    constraints:
                      - id: presentation-requires-network-service
                        description: Presentation tier needs a network service.
                        when:
                          anyServiceGroup:
                            diagramTier: presentation
                        require:
                          - objectType: network_service
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            runtime_dir = workspace / "catalog" / "runtime-services"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "runtime-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF71-RSRV
                    type: runtime_service
                    name: Test RuntimeService
                    deliveryModel: paas
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            (sdp_dir / "sdp-ra-constraint-violation.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: 01KQS0TF71-SDPV
                    type: software_deployment_pattern
                    name: Test RA Constraint Violation
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    followsReferenceArchitecture: 01KQS0TF71-RAXC
{dr_yaml}
                    serviceGroups:
                      - name: Presentation Tier
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF71-RSRV
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("presentation-requires-network-service", result.stdout)
        self.assertIn("RA constraint", result.stdout)
        self.assertIn("network_service", result.stdout)

    def test_ra_constraint_satisfied_passes_sdp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            ra_dir = workspace / "configurations" / "reference-architectures"
            ra_dir.mkdir(parents=True, exist_ok=True)
            (ra_dir / "ra-test-constraint.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF72-RAXC
                    type: reference_architecture
                    name: Test Constraint RA
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    constraints:
                      - id: presentation-requires-network-service
                        description: Presentation tier needs a network service.
                        when:
                          anyServiceGroup:
                            diagramTier: presentation
                        require:
                          - objectType: network_service
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            network_dir = workspace / "catalog" / "network-services"
            network_dir.mkdir(parents=True, exist_ok=True)
            (network_dir / "network-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF72-EGWS
                    type: network_service
                    name: Test NetworkService
                    deliveryModel: appliance
                    vendor: Test Vendor
                    productName: Test Gateway
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            runtime_dir = workspace / "catalog" / "runtime-services"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "runtime-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF72-RSRV
                    type: runtime_service
                    name: Test RuntimeService
                    deliveryModel: paas
                    vendor: Test Vendor
                    productName: Test Runtime
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            (sdp_dir / "sdp-ra-constraint-satisfied.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: 01KQS0TF72-SDPS
                    type: software_deployment_pattern
                    name: Test RA Constraint Satisfied
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    followsReferenceArchitecture: 01KQS0TF72-RAXC
{dr_yaml}
                    serviceGroups:
                      - name: Presentation Tier
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF72-EGWS
                            diagramTier: presentation
                          - ref: 01KQS0TF72-RSRV
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotIn("presentation-requires-network-service", result.stdout)

    def test_ra_capability_constraint_satisfied_by_capability_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            cap_dir = workspace / "configurations" / "capabilities"
            cap_dir.mkdir(parents=True, exist_ok=True)
            (cap_dir / "capability-test-ingress.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF73-CAP0
                    type: capability
                    name: Test Ingress Capability
                    description: Test capability for reference architecture slots.
                    catalogStatus: incomplete
                    owner:
                      team: test-architecture
                    definitionOwner:
                      provider: test
                    domain: 01KQQ4Q027-ZTHF
                    implementations:
                      - ref: 01KQS0TF73-EGWS
                        lifecycleStatus: preferred
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            ra_dir = workspace / "configurations" / "reference-architectures"
            ra_dir.mkdir(parents=True, exist_ok=True)
            (ra_dir / "ra-test-capability-constraint.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF73-RAXC
                    type: reference_architecture
                    name: Test Capability Constraint RA
                    patternType: capability-test
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    applicableDefinitionChecklist:
                      - Ingress capability slot is filled.
                    serviceGroups:
                      - name: Presentation Tier
                        deployableObjects:
                          - slot: ingress
                            capability: 01KQS0TF73-CAP0
                            objectType: network_service
                            diagramTier: presentation
                    notes:
                      patternRationale: Test capability slots.
                    constraints:
                      - id: ingress-capability-required
                        description: Presentation tier needs an ingress capability.
                        require:
                          - capability: 01KQS0TF73-CAP0
                            objectType: network_service
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            network_dir = workspace / "catalog" / "network-services"
            network_dir.mkdir(parents=True, exist_ok=True)
            (network_dir / "network-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF73-EGWS
                    type: network_service
                    name: Test NetworkService
                    deliveryModel: appliance
                    vendor: Test Vendor
                    productName: Test Gateway
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            (sdp_dir / "sdp-ra-capability-satisfied.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: 01KQS0TF73-SDPS
                    type: software_deployment_pattern
                    name: Test RA Capability Constraint Satisfied
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    followsReferenceArchitecture: 01KQS0TF73-RAXC
{dr_yaml}
                    serviceGroups:
                      - name: Presentation Tier
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF73-EGWS
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotIn("ingress-capability-required", result.stdout)

    def test_ra_capability_constraint_reports_missing_capability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            cap_dir = workspace / "configurations" / "capabilities"
            cap_dir.mkdir(parents=True, exist_ok=True)
            (cap_dir / "capability-test-ingress.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF74-CAP0
                    type: capability
                    name: Test Ingress Capability
                    description: Test capability for reference architecture slots.
                    catalogStatus: incomplete
                    owner:
                      team: test-architecture
                    definitionOwner:
                      provider: test
                    domain: 01KQQ4Q027-ZTHF
                    implementations: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            ra_dir = workspace / "configurations" / "reference-architectures"
            ra_dir.mkdir(parents=True, exist_ok=True)
            (ra_dir / "ra-test-capability-constraint.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF74-RAXC
                    type: reference_architecture
                    name: Test Capability Constraint RA
                    patternType: capability-test
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    applicableDefinitionChecklist:
                      - Ingress capability slot is filled.
                    serviceGroups:
                      - name: Presentation Tier
                        deployableObjects:
                          - slot: ingress
                            capability: 01KQS0TF74-CAP0
                            objectType: network_service
                            diagramTier: presentation
                    notes:
                      patternRationale: Test capability slots.
                    constraints:
                      - id: ingress-capability-required
                        description: Presentation tier needs an ingress capability.
                        require:
                          - capability: 01KQS0TF74-CAP0
                            objectType: network_service
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            network_dir = workspace / "catalog" / "network-services"
            network_dir.mkdir(parents=True, exist_ok=True)
            (network_dir / "network-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF74-EGWS
                    type: network_service
                    name: Test NetworkService
                    deliveryModel: appliance
                    vendor: Test Vendor
                    productName: Test Gateway
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            (sdp_dir / "sdp-ra-capability-violation.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: 01KQS0TF74-SDPV
                    type: software_deployment_pattern
                    name: Test RA Capability Constraint Violation
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    followsReferenceArchitecture: 01KQS0TF74-RAXC
{dr_yaml}
                    serviceGroups:
                      - name: Presentation Tier
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF74-EGWS
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("ingress-capability-required", result.stdout)
        self.assertIn("capability '01KQS0TF74-CAP0'", result.stdout)

    def test_ra_slot_validation_fails_when_unsatisfied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            cap_dir = workspace / "configurations" / "capabilities"
            cap_dir.mkdir(parents=True, exist_ok=True)
            (cap_dir / "capability-test-slot.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF75-CAP0
                    type: capability
                    name: Test Slot Capability
                    description: Test capability for slot validation.
                    catalogStatus: incomplete
                    owner:
                      team: test-architecture
                    definitionOwner:
                      provider: test
                    domain: 01KQQ4Q027-ZTHF
                    implementations: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            ra_dir = workspace / "configurations" / "reference-architectures"
            ra_dir.mkdir(parents=True, exist_ok=True)
            (ra_dir / "ra-test-slots.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF75-RAXC
                    type: reference_architecture
                    name: Test Slots RA
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    serviceGroups:
                      - name: Presentation Tier
                        deployableObjects:
                          - slot: test-slot
                            capability: 01KQS0TF75-CAP0
                            objectType: network_service
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            network_dir = workspace / "catalog" / "network-services"
            network_dir.mkdir(parents=True, exist_ok=True)
            (network_dir / "network-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF75-EGWS
                    type: network_service
                    name: Test NetworkService
                    deliveryModel: appliance
                    vendor: Test Vendor
                    productName: Test Gateway
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            (sdp_dir / "sdp-ra-slot-violation.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: 01KQS0TF75-SDPV
                    type: software_deployment_pattern
                    name: Test RA Slot Violation
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    followsReferenceArchitecture: 01KQS0TF75-RAXC
{dr_yaml}
                    serviceGroups:
                      - name: Presentation Tier
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF75-EGWS
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("RA capability slot 'test-slot' unsatisfied", result.stdout)
        self.assertIn("no deployable object satisfies capability '01KQS0TF75-CAP0'", result.stdout)

    def test_ra_slot_validation_passes_when_bypassed_by_decision_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            cap_dir = workspace / "configurations" / "capabilities"
            cap_dir.mkdir(parents=True, exist_ok=True)
            (cap_dir / "capability-test-slot.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF76-CAP0
                    type: capability
                    name: Test Slot Capability
                    description: Test capability for slot validation.
                    catalogStatus: incomplete
                    owner:
                      team: test-architecture
                    definitionOwner:
                      provider: test
                    domain: 01KQQ4Q027-ZTHF
                    implementations: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            ra_dir = workspace / "configurations" / "reference-architectures"
            ra_dir.mkdir(parents=True, exist_ok=True)
            (ra_dir / "ra-test-slots.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF76-RAXC
                    type: reference_architecture
                    name: Test Slots RA
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    serviceGroups:
                      - name: Presentation Tier
                        deployableObjects:
                          - slot: test-slot
                            capability: 01KQS0TF76-CAP0
                            objectType: network_service
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            network_dir = workspace / "catalog" / "network-services"
            network_dir.mkdir(parents=True, exist_ok=True)
            (network_dir / "network-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF76-EGWS
                    type: network_service
                    name: Test NetworkService
                    deliveryModel: appliance
                    vendor: Test Vendor
                    productName: Test Gateway
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            dr_dir = workspace / "catalog" / "decision-records"
            dr_dir.mkdir(parents=True, exist_ok=True)
            (dr_dir / "dr-test-bypass.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: "01KQS0TF76-DRBP"
                    type: decision_record
                    name: Test Bypass Decision Record
                    category: decision
                    status: accepted
                    catalogStatus: complete
                    lifecycleStatus: preferred
                    decisionRationale: "Rationale."
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            dr_yaml += "\n" + " " * 22 + '- ref: "01KQS0TF76-DRBP"\n' + " " * 24 + 'key: test-slot'
            (sdp_dir / "sdp-ra-slot-bypassed.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: 01KQS0TF76-SDPV
                    type: software_deployment_pattern
                    name: Test RA Slot Bypassed
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    followsReferenceArchitecture: 01KQS0TF76-RAXC
{dr_yaml}
                    serviceGroups:
                      - name: Presentation Tier
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF76-EGWS
                            diagramTier: presentation
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)

    def test_ra_multiple_architectures_satisfied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            
            ra_dir = workspace / "configurations" / "reference-architectures"
            ra_dir.mkdir(parents=True, exist_ok=True)
            (ra_dir / "ra-test-1.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF77-RAX1
                    type: reference_architecture
                    name: Test RA 1
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    constraints:
                      - id: presentation-requires-network-service
                        description: Presentation tier needs a network service.
                        require:
                          - objectType: network_service
                            diagramTier: presentation
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            (ra_dir / "ra-test-2.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF77-RAX2
                    type: reference_architecture
                    name: Test RA 2
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    constraints:
                      - id: presentation-requires-runtime-service
                        description: Presentation tier needs a runtime service.
                        require:
                          - objectType: runtime_service
                            diagramTier: presentation
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            network_dir = workspace / "catalog" / "network-services"
            network_dir.mkdir(parents=True, exist_ok=True)
            (network_dir / "network-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF77-EGWS
                    type: network_service
                    name: Test NetworkService
                    deliveryModel: appliance
                    vendor: Test Vendor
                    productName: Test Gateway
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            runtime_dir = workspace / "catalog" / "runtime-services"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "runtime-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF77-RSRV
                    type: runtime_service
                    name: Test RuntimeService
                    deliveryModel: paas
                    vendor: Test Vendor
                    productName: Test Runtime
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            
            (sdp_dir / "sdp-ra-multiple-satisfied.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: 01KQS0TF77-SDPS
                    type: software_deployment_pattern
                    name: Test RA Multiple Satisfied
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    followsReferenceArchitecture:
                      - 01KQS0TF77-RAX1
                      - 01KQS0TF77-RAX2
{dr_yaml}
                    serviceGroups:
                      - name: Presentation Tier
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF77-EGWS
                            diagramTier: presentation
                          - ref: 01KQS0TF77-RSRV
                            diagramTier: presentation
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)
            
        self.assertTrue(result.ok, result.stdout + result.stderr)

    def test_ra_multiple_architectures_violated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            
            ra_dir = workspace / "configurations" / "reference-architectures"
            ra_dir.mkdir(parents=True, exist_ok=True)
            (ra_dir / "ra-test-1.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF78-RAX1
                    type: reference_architecture
                    name: Test RA 1
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    constraints:
                      - id: presentation-requires-network-service
                        description: Presentation tier needs a network service.
                        require:
                          - objectType: network_service
                            diagramTier: presentation
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            (ra_dir / "ra-test-2.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF78-RAX2
                    type: reference_architecture
                    name: Test RA 2
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    constraints:
                      - id: presentation-requires-runtime-service
                        description: Presentation tier needs a runtime service.
                        require:
                          - objectType: runtime_service
                            diagramTier: presentation
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            runtime_dir = workspace / "catalog" / "runtime-services"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "runtime-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF78-RSRV
                    type: runtime_service
                    name: Test RuntimeService
                    deliveryModel: paas
                    vendor: Test Vendor
                    productName: Test Runtime
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            
            (sdp_dir / "sdp-ra-multiple-violated.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: 01KQS0TF78-SDPV
                    type: software_deployment_pattern
                    name: Test RA Multiple Violated
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    followsReferenceArchitecture:
                      - 01KQS0TF78-RAX1
                      - 01KQS0TF78-RAX2
{dr_yaml}
                    serviceGroups:
                      - name: Presentation Tier
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF78-RSRV
                            diagramTier: presentation
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            result = validate_workspace(workspace)
            
        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("presentation-requires-network-service", result.stdout)
        self.assertNotIn("presentation-requires-runtime-service", result.stdout)

    def test_ra_relationship_constraint_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            
            ra_dir = workspace / "configurations" / "reference-architectures"
            ra_dir.mkdir(parents=True, exist_ok=True)
            
            (ra_dir / "ra-test-rel-req.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF79-RAXR
                    type: reference_architecture
                    name: Test Rel Required RA
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    constraints:
                      - id: presentation-to-application-required
                        description: Presentation tier must connect to application tier.
                        requireRelationships:
                          - source:
                              diagramTier: presentation
                            target:
                              diagramTier: application
                            allowed: true
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            runtime_dir = workspace / "catalog" / "runtime-services"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "service-pres.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF79-RSRP
                    type: runtime_service
                    name: Presentation Service
                    deliveryModel: paas
                    vendor: Test Vendor
                    productName: Test Presentation
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            (runtime_dir / "service-app.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF79-RSRA
                    type: runtime_service
                    name: Application Service
                    deliveryModel: paas
                    vendor: Test Vendor
                    productName: Test Application
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            
            (sdp_dir / "sdp-rel-missing.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: 01KQS0TF79-SDPM
                    type: software_deployment_pattern
                    name: Test Rel Missing SDP
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    followsReferenceArchitecture: 01KQS0TF79-RAXR
{dr_yaml}
                    serviceGroups:
                      - name: Pres Group
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF79-RSRP
                            diagramTier: presentation
                      - name: App Group
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF79-RSRA
                            diagramTier: application
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            grandfather_ratcheted_violations(workspace)
            result1 = validate_workspace(workspace)
            self.assertFalse(result1.ok, result1.stdout + result1.stderr)
            self.assertIn("presentation-to-application-required", result1.stdout)
            self.assertIn("required relationship", result1.stdout)
            
            rel_dir = workspace / "catalog" / "relationships"
            rel_dir.mkdir(parents=True, exist_ok=True)
            (rel_dir / "rel-pres-to-app.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF79-RRK1
                    type: relationship
                    name: Presentation to Application
                    catalogStatus: stub
                    source: 01KQS0TF79-RSRP
                    target: 01KQS0TF79-RSRA
                    label: routes to
                    direction: synchronous
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            grandfather_ratcheted_violations(workspace)
            result2 = validate_workspace(workspace)
            self.assertTrue(result2.ok, result2.stdout + result2.stderr)

    def test_ra_relationship_constraint_forbidden(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            
            ra_dir = workspace / "configurations" / "reference-architectures"
            ra_dir.mkdir(parents=True, exist_ok=True)
            
            (ra_dir / "ra-test-rel-forbidden.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF80-RAXF
                    type: reference_architecture
                    name: Test Rel Forbidden RA
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    constraints:
                      - id: presentation-to-data-forbidden
                        description: Presentation tier must not connect to data tier directly.
                        requireRelationships:
                          - source:
                              diagramTier: presentation
                            target:
                              diagramTier: data
                            allowed: false
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            runtime_dir = workspace / "catalog" / "runtime-services"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "service-pres.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF80-RSRP
                    type: runtime_service
                    name: Presentation Service
                    deliveryModel: paas
                    vendor: Test Vendor
                    productName: Test Presentation
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            (runtime_dir / "service-data.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF80-RSRD
                    type: runtime_service
                    name: Data Service
                    deliveryModel: paas
                    vendor: Test Vendor
                    productName: Test Data
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            
            (sdp_dir / "sdp-rel-forbidden-ok.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: 01KQS0TF80-SDPX
                    type: software_deployment_pattern
                    name: Test Rel Forbidden OK SDP
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    followsReferenceArchitecture: 01KQS0TF80-RAXF
{dr_yaml}
                    serviceGroups:
                      - name: Pres Group
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF80-RSRP
                            diagramTier: presentation
                      - name: Data Group
                        deploymentTarget: test-env
                        deployableObjects:
                          - ref: 01KQS0TF80-RSRD
                            diagramTier: data
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            grandfather_ratcheted_violations(workspace)
            result1 = validate_workspace(workspace)
            self.assertTrue(result1.ok, result1.stdout + result1.stderr)
            
            rel_dir = workspace / "catalog" / "relationships"
            rel_dir.mkdir(parents=True, exist_ok=True)
            (rel_dir / "rel-pres-to-data.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF80-RRK2
                    type: relationship
                    name: Presentation to Data
                    catalogStatus: stub
                    source: 01KQS0TF80-RSRP
                    target: 01KQS0TF80-RSRD
                    label: direct data access
                    direction: synchronous
                    """
                ).strip() + "\n",
                encoding="utf-8",
            )
            
            grandfather_ratcheted_violations(workspace)
            result2 = validate_workspace(workspace)
            self.assertFalse(result2.ok, result2.stdout + result2.stderr)
            self.assertIn("presentation-to-data-forbidden", result2.stdout)
            self.assertIn("forbidden relationship", result2.stdout)

    def _write_vocabulary_workspace(self, workspace: Path, mode: str) -> None:
        (workspace / ".draft" / "workspace.yaml").write_text(
            textwrap.dedent(
                f"""
                schemaVersion: "1.0"
                workspace:
                  name: vocabulary-test
                framework:
                  source: https://github.com/getdraft/draftsman.git
                  vendoredPath: .draft/framework
                  updatePolicy: explicit
                paths:
                  catalog: catalog
                  configurations: configurations
                requirements:
                  activeRequirementGroups: []
                  requireActiveRequirementGroupDisposition: false
                vocabulary:
                  deploymentTargets:
                    mode: {mode}
                    values:
                      - id: aws-us-east-2
                        name: AWS US East 2
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def _write_owner_contact_vocabulary_workspace(self, workspace: Path) -> None:
        (workspace / ".draft" / "workspace.yaml").write_text(
            textwrap.dedent(
                """
                schemaVersion: "1.0"
                workspace:
                  name: owner-contact-test
                framework:
                  source: https://github.com/getdraft/draftsman.git
                  vendoredPath: .draft/framework
                  updatePolicy: explicit
                paths:
                  catalog: catalog
                  configurations: configurations
                requirements:
                  activeRequirementGroups: []
                  requireActiveRequirementGroupDisposition: false
                vocabulary:
                  teams:
                    mode: advisory
                    values:
                      - id: platform-engineering
                        name: Platform Engineering
                        contact: platform-engineering@example.com
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def _write_component_with_owner(self, workspace: Path, owner_extra: str = "") -> None:
        component_dir = workspace / "catalog" / "technology-components"
        component_dir.mkdir(parents=True, exist_ok=True)
        (component_dir / "technology-component-owner.yaml").write_text(
            textwrap.dedent(
                f"""
                schemaVersion: "1.0"
                uid: 01KTP8ADD1-407A
                type: technology_component
                name: Owner Contact Component
                vendor: Example
                productName: Example Product
                productVersion: "1"
                classification: software
                catalogStatus: incomplete
                lifecycleStatus: candidate
                owner:
                  team: platform-engineering
{owner_extra}
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def test_owner_contact_can_be_omitted_when_team_vocabulary_has_contact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_owner_contact_vocabulary_workspace(workspace)
            self._write_component_with_owner(workspace)

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotIn("owner.contact", result.stdout)

    def test_owner_contact_drift_warns_against_team_vocabulary_contact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_owner_contact_vocabulary_workspace(workspace)
            self._write_component_with_owner(workspace, "                  contact: old-platform@example.com")

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertIn("owner.contact 'old-platform@example.com' differs from teams vocabulary contact", result.stdout)
        self.assertIn("platform-engineering@example.com", result.stdout)

    def _write_sdp_with_deployment_target(self, workspace: Path, deployment_target: str) -> None:
        pattern_dir = workspace / "catalog" / "software-deployment-patterns"
        pattern_dir.mkdir(parents=True, exist_ok=True)
        dr_yaml = self._write_decision_records_for_sdp(workspace, indent=16)
        (pattern_dir / "software-deployment-pattern-vocabulary.yaml").write_text(
            textwrap.dedent(
                f"""
                schemaVersion: "1.0"
                uid: 01KQS0TF70-SDMP
                type: software_deployment_pattern
                name: Vocabulary Test Pattern
                catalogStatus: incomplete
                lifecycleStatus: candidate
{dr_yaml}
                serviceGroups:
                  - name: Application Tier
                    deploymentTarget: {deployment_target}
                    deployableObjects: []
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def test_validate_quiet_argument_suppresses_pass_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)
            self._repair_workspace_uids(workspace)

            # Standard run
            standard_cmd = build_validate_command(workspace, REPO_ROOT)
            standard_result = subprocess.run(
                standard_cmd,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertIn("PASS ", standard_result.stdout)

            # Quiet run
            quiet_cmd = build_validate_command(workspace, REPO_ROOT) + ["--quiet"]
            quiet_result = subprocess.run(
                quiet_cmd,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotIn("PASS ", quiet_result.stdout)
            self.assertIn("Validated ", quiet_result.stdout)

    def test_sdp_deployable_object_intent_is_ignored(self) -> None:
        for intent in ("standalone", "sa", "ha", "xyz"):
            with self.subTest(intent=intent), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                ensure_workspace_layout(workspace)
                runtime_dir = workspace / "catalog" / "runtime-services"
                runtime_dir.mkdir(parents=True, exist_ok=True)
                (runtime_dir / "runtime-service-test.yaml").write_text(
                    textwrap.dedent(
                        """
                        schemaVersion: "1.0"
                        uid: 01KQS0TF73-RSRV
                        type: runtime_service
                        name: Test RuntimeService
                        deliveryModel: paas
                        vendor: Test Vendor
                        productName: Test Runtime
                        productVersion: "1.0"
                        catalogStatus: incomplete
                        lifecycleStatus: candidate
                        """
                    ).strip()
                    + "\n",
                    encoding="utf-8",
                )
                sdp_dir = workspace / "catalog" / "software-deployment-patterns"
                sdp_dir.mkdir(parents=True, exist_ok=True)
                dr_yaml = self._write_decision_records_for_sdp(workspace, indent=24)
                (sdp_dir / "sdp-tier-test.yaml").write_text(
                    textwrap.dedent(
                        f"""
                        schemaVersion: "1.0"
                        uid: 01KQS0TF73-SDPN
                        type: software_deployment_pattern
                        name: Test Tier Pattern
                        catalogStatus: incomplete
                        lifecycleStatus: candidate
{dr_yaml}
                        serviceGroups:
                          - name: Application Tier
                            deploymentTarget: test-env
                            deployableObjects:
                              - ref: 01KQS0TF73-RSRV
                                diagramTier: application
                                intent: {intent}
                        """
                    ).strip()
                    + "\n",
                    encoding="utf-8",
                )

                grandfather_ratcheted_violations(workspace)
                result = validate_workspace(workspace)

                self.assertTrue(result.ok, result.stdout + result.stderr)
                self.assertNotRegex(result.stdout + result.stderr, r"\bintent\b")

    def test_reference_architecture_deployable_object_intent_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            ra_dir = workspace / "configurations" / "reference-architectures"
            ra_dir.mkdir(parents=True, exist_ok=True)
            (ra_dir / "ra-tier-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF73-RAMN
                    type: reference_architecture
                    name: Test Tier RA
                    catalogStatus: incomplete
                    lifecycleStatus: preferred
                    patternType: standard
                    applicableDefinitionChecklist:
                      - Runtime service sits in the application tier.
                    serviceGroups:
                      - name: Application Tier
                        deployableObjects:
                          - objectType: runtime_service
                            diagramTier: application
                            intent: xyz
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotRegex(result.stdout + result.stderr, r"\bintent\b")

    def test_validate_secrets_scanner_blocks_plaintext_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)

            # Write a component with a plaintext password leak
            component_dir = workspace / "catalog" / "technology-components"
            component_dir.mkdir(parents=True, exist_ok=True)
            (component_dir / "technology-component-leak.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: technology.leak
                    type: technology_component
                    classification: software
                    name: Leaking Component
                    catalogStatus: stub
                    lifecycleStatus: candidate
                    owner:
                      team: platform-engineering
                    configurations:
                      - id: default
                        name: Default Config
                        description: Plaintext leak
                        parameters:
                          db_password: "my-plain-password"
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)

            cmd = build_validate_command(workspace, REPO_ROOT)
            result = subprocess.run(
                cmd,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Plaintext secret leaked in field", result.stdout)

    def test_validate_deployment_ready_checks_completeness_and_dependency_graph(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)

            # 1. Create a SoftwareDeploymentPattern (complete status)
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            (sdp_dir / "sdp-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KSF9T6YZ-A1B2
                    type: software_deployment_pattern
                    name: Test SDP
                    catalogStatus: complete
                    lifecycleStatus: existing-only
                    patternType: SaaS
                    serviceGroups: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            # 2. Create a DeploymentTarget (incomplete status)
            target_dir = workspace / "configurations" / "deployment-targets"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "target-dev.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KSHG87WX-C3D4
                    type: deployment_target
                    name: Dev Target
                    environmentTier: dev
                    targetProvider: aws
                    parameters:
                      region: us-east-1
                    catalogStatus: incomplete
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)

            # 3. Check deployment readiness for SDP (which should fail because the target is incomplete)
            cmd = build_validate_command(workspace, REPO_ROOT) + ["--deployment-ready", "01KSF9T6YZ-A1B2", "01KSHG87WX-C3D4"]
            result = subprocess.run(
                cmd,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("has catalogStatus 'incomplete' instead of 'complete'", result.stdout)

    def test_requirement_group_list_inheritance_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            shutil.copytree(
                REPO_ROOT / "providers" / "owasp-asvs",
                workspace / ".draft" / "providers" / "owasp-asvs",
            )
            (workspace / ".draft" / "workspace.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    workspace:
                      name: asvs-list-inheritance
                    requirements:
                      activeRequirementGroups:
                        - 01KQQ4Q027-ASV2
                      requireActiveRequirementGroupDisposition: true
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            product_dir = workspace / "catalog" / "product-components"
            product_dir.mkdir(parents=True, exist_ok=True)
            (product_dir / "product-service-test-app.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KT55KGQ2-ASV2
                    type: product_component
                    name: Test App
                    repoUrl: https://github.com/test/test-app
                    owner:
                      team: test
                    classification: api-service
                    runtimeRequirement: Node 20
                    catalogStatus: complete
                    lifecycleStatus: existing-only
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("ASVS L2.V1.1", result.stdout)
        self.assertIn("ASVS L2.V1.2", result.stdout)
        self.assertNotIn("TypeError", result.stderr)

    def test_stale_and_invalid_requirement_implementations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)

            # Write a requirement group
            (workspace / "configurations" / "requirement-groups" / "requirement-group-company-control.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: requirement-group.company-control
                    type: requirement_group
                    name: Company Control
                    description: Workspace-mode control group.
                    catalogStatus: incomplete
                    owner:
                      team: test
                    activation: workspace
                    appliesTo:
                      - product_component
                    requirements:
                      - id: company-required-field
                        description: Product services must provide company evidence.
                        rationale: Test requirement.
                        requirementMode: mandatory
                        naAllowed: false
                        canBeSatisfiedBy:
                          - mechanism: field
                            key: notes.companyEvidence
                        minimumSatisfactions: 1
                        validAnswerTypes:
                          - field
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            # 1. Stale / Non-existent requirementGroup UID
            (workspace / "catalog" / "product-components" / "product-service-test-app.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: product-service.test.app
                    type: product_component
                    name: Test App
                    repoUrl: https://github.com/test/test-app
                    owner:
                      team: test
                    classification: api-service
                    runtimeRequirement: Node 20
                    runsOn: host.test
                    catalogStatus: complete
                    lifecycleStatus: existing-only
                    requirementGroups:
                      - requirement-group.company-control
                    notes:
                      companyEvidence: Provided.
                    requirementImplementations:
                      - requirementGroup: requirement-group.non-existent-group
                        requirementId: company-required-field
                        status: satisfied
                        mechanism: field
                        key: notes.companyEvidence
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)
            result = validate_workspace(workspace)
            self.assertFalse(result.ok, result.stdout + result.stderr)
            self.assertIn("Set requirementGroup to an existing requirement_group UID", result.stdout)

            # 2. Stale / Non-existent requirementId
            (workspace / "catalog" / "product-components" / "product-service-test-app.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: product-service.test.app
                    type: product_component
                    name: Test App
                    repoUrl: https://github.com/test/test-app
                    owner:
                      team: test
                    classification: api-service
                    runtimeRequirement: Node 20
                    runsOn: host.test
                    catalogStatus: complete
                    lifecycleStatus: existing-only
                    requirementGroups:
                      - requirement-group.company-control
                    notes:
                      companyEvidence: Provided.
                    requirementImplementations:
                      - requirementGroup: requirement-group.company-control
                        requirementId: non-existent-requirement-id
                        status: satisfied
                        mechanism: field
                        key: notes.companyEvidence
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)
            result = validate_workspace(workspace)
            self.assertFalse(result.ok, result.stdout + result.stderr)
            self.assertIn("Set requirementId to an applicable requirement in", result.stdout)

    def test_hierarchical_business_taxonomy_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)

            (workspace / ".draft" / "workspace.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    workspace:
                      name: test-hierarchy-workspace
                    framework:
                      source: https://github.com/getdraft/draftsman.git
                      vendoredPath: .draft/framework
                      updatePolicy: explicit
                    paths:
                      catalog: catalog
                      configurations: configurations
                    businessTaxonomy:
                      requireSoftwareDeploymentPatternPillar: true
                      hierarchy:
                        - id: org.product-dev
                          name: Product Development
                          type: business_unit
                          children:
                            - id: division.hcm
                              name: Human Capital Management
                              type: pillar
                              children:
                                - id: team.absence-time
                                  name: Absence & Time Team
                                  type: team
                    requirements:
                      activeRequirementGroups: []
                      requireActiveRequirementGroupDisposition: false
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            # Write a valid runtime service for references
            runtime_dir = workspace / "catalog" / "runtime-services"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "runtime-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: runtime-service.test
                    type: runtime_service
                    name: Test Runtime Service
                    deliveryModel: paas
                    vendor: "Test Vendor"
                    productName: "Test Product"
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            # 1. Valid ownerNode referencing team.absence-time (which has a pillar division.hcm in its lineage)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            (workspace / "catalog" / "software-deployment-patterns" / "sdp-test-service.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    id: sdp.test-service
                    type: software_deployment_pattern
                    name: Test Service Pattern
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    businessContext:
                      ownerNode: team.absence-time
{dr_yaml}
                    serviceGroups:
                      - name: App Tier
                        deploymentTarget: Test target
                        deployableObjects:
                          - ref: runtime-service.test
                            diagramTier: application
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)
            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)
            self.assertTrue(result.ok, result.stdout + result.stderr)

            # 2. Invalid ownerNode that doesn't exist
            (workspace / "catalog" / "software-deployment-patterns" / "sdp-test-service.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    id: sdp.test-service
                    type: software_deployment_pattern
                    name: Test Service Pattern
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    businessContext:
                      ownerNode: team.does-not-exist
{dr_yaml}
                    serviceGroups:
                      - name: App Tier
                        deploymentTarget: Test target
                        deployableObjects:
                          - ref: runtime-service.test
                            diagramTier: application
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)
            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)
            self.assertFalse(result.ok, result.stdout + result.stderr)
            self.assertIn("Replace businessContext.ownerNode 'team.does-not-exist' with a declared hierarchy node id", result.stdout)

            # 3. ownerNode pointing to a node without a pillar in its lineage (e.g. root business_unit)
            (workspace / "catalog" / "software-deployment-patterns" / "sdp-test-service.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    id: sdp.test-service
                    type: software_deployment_pattern
                    name: Test Service Pattern
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    businessContext:
                      ownerNode: org.product-dev
{dr_yaml}
                    serviceGroups:
                      - name: App Tier
                        deploymentTarget: Test target
                        deployableObjects:
                          - ref: runtime-service.test
                            diagramTier: application
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)
            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)
            self.assertFalse(result.ok, result.stdout + result.stderr)
            self.assertIn("pointing to a node with a pillar in its lineage", result.stdout)

    def test_software_deployment_pattern_with_decision_records_satisfaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)

            # Write a valid runtime service
            runtime_dir = workspace / "catalog" / "runtime-services"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "runtime-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: runtime-service.test
                    type: runtime_service
                    name: Test Runtime Service
                    deliveryModel: paas
                    vendor: "Test Vendor"
                    productName: "Test Product"
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            # Write dummy decision records to satisfy requirements
            dr_dir = workspace / "catalog" / "decision-records"
            dr_dir.mkdir(parents=True, exist_ok=True)
            
            def write_dr(dr_id: str, name: str):
                (dr_dir / f"{dr_id}.yaml").write_text(
                    textwrap.dedent(
                        f"""
                        schemaVersion: "1.0"
                        id: {dr_id}
                        type: decision_record
                        name: {name}
                        category: decision
                        status: accepted
                        catalogStatus: complete
                        lifecycleStatus: preferred
                        decisionRationale: "Rationale."
                        """
                    ).strip()
                    + "\n",
                    encoding="utf-8",
                )

            write_dr("dr.no-pattern", "No Pattern Decision")
            write_dr("dr.targets", "Targets Decision")
            write_dr("dr.avail", "Availability Decision")
            write_dr("dr.data", "Data Classification Decision")
            write_dr("dr.failure", "Failure Domain Decision")
            write_dr("dr.deviations", "Deviations Decision")
            write_dr("dr.interactions", "Interactions Decision")

            # Write the SDP with decisionRecords referencing the above DRs (and NO notes)
            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            (sdp_dir / "sdp-test-service.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: sdp.test-service
                    type: software_deployment_pattern
                    name: Test Service Pattern
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    decisionRecords:
                      - ref: dr.no-pattern
                        key: noApplicablePattern
                      - ref: dr.targets
                        key: deploymentTargets
                      - ref: dr.avail
                        key: availabilityRequirement
                      - ref: dr.data
                        key: dataClassification
                      - ref: dr.failure
                        key: failureDomain
                      - ref: dr.deviations
                        key: noPatternDeviations
                      - ref: dr.interactions
                        key: noAdditionalInteractions
                    serviceGroups:
                      - name: App Tier
                        deploymentTarget: Test target
                        deployableObjects:
                          - ref: runtime-service.test
                            diagramTier: application
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)
            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)
            self.assertTrue(result.ok, result.stdout + result.stderr)

    def test_software_deployment_pattern_architecture_notes_do_not_satisfy_decision_record_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)

            runtime_dir = workspace / "catalog" / "runtime-services"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "runtime-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: runtime-service.test
                    type: runtime_service
                    name: Test Runtime Service
                    deliveryModel: paas
                    vendor: "Test Vendor"
                    productName: "Test Product"
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            sdp_dir = workspace / "catalog" / "software-deployment-patterns"
            sdp_dir.mkdir(parents=True, exist_ok=True)
            (sdp_dir / "sdp-test-service.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: sdp.test-service
                    type: software_deployment_pattern
                    name: Test Service Pattern
                    catalogStatus: complete
                    lifecycleStatus: candidate
                    notes:
                      noApplicablePattern: "No reference architecture applies."
                      deploymentTargets: "Runs in the test target."
                      availabilityRequirement: "Best-effort availability is acceptable."
                      dataClassification: "Internal test data only."
                      failureDomain: "Single test failure domain."
                      noPatternDeviations: "No deviations."
                      noAdditionalInteractions: "No additional interactions."
                    serviceGroups:
                      - name: App Tier
                        deploymentTarget: Test target
                        deployableObjects:
                          - ref: runtime-service.test
                            diagramTier: application
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            self._repair_workspace_uids(workspace)
            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("decisionRecord reference for key 'noApplicablePattern'", result.stdout)
        self.assertIn("decisionRecord reference for key 'deploymentTargets'", result.stdout)
        self.assertIn("decisionRecord reference for key 'availabilityRequirement'", result.stdout)
        self.assertIn("decisionRecord reference for key 'dataClassification'", result.stdout)
        self.assertIn("decisionRecord reference for key 'failureDomain'", result.stdout)
        self.assertIn("decisionRecord reference for key 'externalDependencies' or 'noAdditionalInteractions'", result.stdout)
        self.assertIn("decisionRecord reference for key 'patternDeviations' or 'noPatternDeviations'", result.stdout)

    def test_federated_business_unit_taxonomy_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)

            (workspace / ".draft" / "workspace.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    workspace:
                      name: test-federated-hierarchy-workspace
                    framework:
                      source: https://github.com/getdraft/draftsman.git
                      vendoredPath: .draft/framework
                      updatePolicy: explicit
                    paths:
                      catalog: catalog
                      configurations: configurations
                    businessTaxonomy:
                      requireSoftwareDeploymentPatternPillar: true
                      businessUnits:
                        - id: bu.hr
                          name: Human Resources
                        - id: bu.finance
                          name: Finance
                    requirements:
                      activeRequirementGroups: []
                      requireActiveRequirementGroupDisposition: false
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            # Write a valid runtime service for references
            runtime_dir = workspace / "catalog" / "runtime-services"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "runtime-service-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: runtime-service.test
                    type: runtime_service
                    name: Test Runtime Service
                    deliveryModel: paas
                    vendor: "Test Vendor"
                    productName: "Test Product"
                    productVersion: "1.0"
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            # Write a valid business unit hierarchy file under catalog/business-unit-hierarchies/
            bu_hierarchy_dir = workspace / "catalog" / "business-unit-hierarchies"
            bu_hierarchy_dir.mkdir(parents=True, exist_ok=True)
            (bu_hierarchy_dir / "hr-hierarchy.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: abcdefghij-1234
                    type: business_unit_hierarchy
                    name: HR Hierarchy
                    businessUnit: bu.hr
                    catalogStatus: complete
                    hierarchy:
                      - id: division.hcm
                        name: Human Capital Management
                        type: pillar
                        children:
                          - id: team.absence-time
                            name: Absence & Time Team
                            type: team
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            # 1. Valid ownerNode referencing team.absence-time (which has division.hcm [type: pillar] in its lineage)
            dr_yaml = self._write_decision_records_for_sdp(workspace, indent=20)
            (workspace / "catalog" / "software-deployment-patterns" / "sdp-test-service.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    id: sdp.test-service
                    type: software_deployment_pattern
                    name: Test Service Pattern
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    businessContext:
                      ownerNode: team.absence-time
{dr_yaml}
                    serviceGroups:
                      - name: App Tier
                        deploymentTarget: Test target
                        deployableObjects:
                          - ref: runtime-service.test
                            diagramTier: application
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)
            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)
            self.assertTrue(result.ok, result.stdout + result.stderr)

            # 2. Invalid ownerNode that doesn't exist
            (workspace / "catalog" / "software-deployment-patterns" / "sdp-test-service.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    id: sdp.test-service
                    type: software_deployment_pattern
                    name: Test Service Pattern
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    businessContext:
                      ownerNode: team.does-not-exist
{dr_yaml}
                    serviceGroups:
                      - name: App Tier
                        deploymentTarget: Test target
                        deployableObjects:
                          - ref: runtime-service.test
                            diagramTier: application
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)
            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)
            self.assertFalse(result.ok, result.stdout + result.stderr)
            self.assertIn("Replace businessContext.ownerNode 'team.does-not-exist' with a declared hierarchy node id", result.stdout)

            # 3. ownerNode pointing to a node without a pillar in its lineage (e.g. root business_unit bu.hr)
            (workspace / "catalog" / "software-deployment-patterns" / "sdp-test-service.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    id: sdp.test-service
                    type: software_deployment_pattern
                    name: Test Service Pattern
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    businessContext:
                      ownerNode: bu.hr
{dr_yaml}
                    serviceGroups:
                      - name: App Tier
                        deploymentTarget: Test target
                        deployableObjects:
                          - ref: runtime-service.test
                            diagramTier: application
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)
            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)
            self.assertFalse(result.ok, result.stdout + result.stderr)
            self.assertIn("pointing to a node with a pillar in its lineage", result.stdout)

            # 4. Invalid businessUnit reference in hierarchy file
            (bu_hierarchy_dir / "hr-hierarchy.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: abcdefghij-1234
                    type: business_unit_hierarchy
                    name: HR Hierarchy
                    businessUnit: bu.invalid-bu
                    catalogStatus: complete
                    hierarchy:
                      - id: division.hcm
                        name: Human Capital Management
                        type: pillar
                        children:
                          - id: team.absence-time
                            name: Absence & Time Team
                            type: team
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (workspace / "catalog" / "software-deployment-patterns" / "sdp-test-service.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    id: sdp.test-service
                    type: software_deployment_pattern
                    name: Test Service Pattern
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    businessContext:
                      ownerNode: team.absence-time
{dr_yaml}
                    serviceGroups:
                      - name: App Tier
                        deploymentTarget: Test target
                        deployableObjects:
                          - ref: runtime-service.test
                            diagramTier: application
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)
            grandfather_ratcheted_violations(workspace)
            result = validate_workspace(workspace)
            self.assertFalse(result.ok, result.stdout + result.stderr)
            self.assertIn("Replace businessUnit 'bu.invalid-bu' with a business unit declared in .draft/workspace.yaml", result.stdout)

    def test_validate_capability_ownership_patches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_workspace_requirement_fixture(workspace, require_disposition=False)

            # Remove scaffolded object-patch templates to ensure none are present initially
            patches_dir = workspace / "configurations" / "object-patches"
            if patches_dir.exists():
                for f in patches_dir.glob("*.yaml"):
                    f.unlink()

            # Write a capability with zero implementations
            cap_dir = workspace / "configurations" / "capabilities"
            cap_dir.mkdir(parents=True, exist_ok=True)
            (cap_dir / "cap-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQQ4Q026-CAPP
                    type: capability
                    name: Test Capability
                    domain: 01KQQ4Q026-DMMN
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    implementations: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            
            # Write the domain
            dom_dir = workspace / "configurations" / "domains"
            dom_dir.mkdir(parents=True, exist_ok=True)
            (dom_dir / "dom-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQQ4Q026-DMMN
                    type: domain
                    name: Test Domain
                    catalogStatus: incomplete
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            # Validate. Since there is a capability with zero implementations and no patches,
            # we expect a validation warning.
            result = validate_workspace(workspace)
            self.assertIn("No active capability-ownership object patches found", result.stdout)

            # Write a capability-ownership object patch targeting the capability
            patches_dir = workspace / "configurations" / "object-patches"
            patches_dir.mkdir(parents=True, exist_ok=True)
            (patches_dir / "capability-ownership-patch.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQQ4Q026-PATC
                    type: object_patch
                    target: 01KQQ4Q026-CAPP
                    patch:
                      owner:
                        team: "Test Team"
                      implementations: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            # Validate again. Now the patch is present, so the warning should go away.
            result = validate_workspace(workspace)
            self.assertNotIn("No active capability-ownership object patches found", result.stdout)


class InterfaceExposureFieldTests(unittest.TestCase):
    """AC1 (S1): the new optional fields validate and reject wrong types."""

    EXAMPLES = REPO_ROOT / "examples"

    def _copy_examples(self) -> Path:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        workspace = directory / "ws"
        shutil.copytree(self.EXAMPLES, workspace)
        return workspace

    @staticmethod
    def _edit(workspace: Path, pattern: str, mutate) -> None:
        import yaml

        matches = sorted(workspace.glob(pattern))
        assert matches, pattern
        path = matches[0]
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    def _add_every_field(self, workspace: Path, bad: bool = False) -> None:
        port = "5432" if bad else 5432
        listener = lambda proto: [{"name": "l", "protocol": proto, "port": port, "description": "d"}]
        for pattern, proto in (
            ("catalog/shared-services/runtime-services/runtime-service-cinder.yaml", "HTTPS"),
            ("catalog/shared-services/data-store-services/*.yaml", "SQL"),
            ("catalog/shared-services/network-services/network-service-openstack-api-lb.yaml", "TCP"),
            ("catalog/shared-services/hosts/host-serverless-lambda.yaml", "UDP"),
        ):
            self._edit(workspace, pattern, lambda d, proto=proto: d.__setitem__("listeners", listener(proto)))
        self._edit(
            workspace,
            "catalog/engineering/data-components/*.yaml",
            lambda d: d.__setitem__("interfaces", [{"name": "data", "protocol": "SQL", "path": "audit", "authenticationModel": "iam", "description": "d"}]),
        )
        self._edit(
            workspace,
            "catalog/governance/relationships/relationship-horizon-dashboard-calls-cinder-block-storage.yaml",
            lambda d: d.__setitem__("targetInterface", "api"),
        )

        def groups(d):
            g = d["serviceGroups"]
            g[0]["exposedThrough"] = "01KSF29JTP-9HYA"
            if len(g) > 1:
                g[1]["exposedThrough"] = ["01KSF29JTP-9HYA", "01KSF29JTP-9HYA"]
            if len(g) > 2:
                g[2]["exposedThrough"] = "none"

        self._edit(workspace, "catalog/engineering/software-deployment-patterns/*.yaml", groups)

    def test_every_new_field_passes(self) -> None:
        workspace = self._copy_examples()
        self._add_every_field(workspace)
        grandfather_ratcheted_violations(workspace)  # edited groups change the baselined hashes
        result = validate_workspace(workspace)
        self.assertTrue(result.ok, result.stdout)
        for field in ("listeners", "interfaces", "targetInterface", "exposedThrough"):
            self.assertNotIn(f"'{field}'", result.stdout.replace("[warning]", ""), result.stdout)
        self.assertNotIn("to type", result.stdout)

    def test_listener_port_string_fails_with_type_error(self) -> None:
        workspace = self._copy_examples()
        self._add_every_field(workspace, bad=True)
        grandfather_ratcheted_violations(workspace)
        result = validate_workspace(workspace)
        self.assertFalse(result.ok, result.stdout)
        self.assertIn("Change field 'port' to type int", result.stdout)

    def _section_failures(self, schema_file: str, section: str | None, node: dict) -> list[str]:
        import sys
        import yaml

        sys.path.insert(0, str(REPO_ROOT / "framework" / "tools"))
        import validate as validate_module

        root = yaml.safe_load((REPO_ROOT / "framework" / "schemas" / schema_file).read_text(encoding="utf-8"))
        schema = root[section] if section else root
        failures: list[str] = []
        validate_module.validate_schema_section(node, schema, "ctx", failures, root, [])
        return failures

    def test_listener_in_all_four_definition_schemas(self) -> None:
        for schema_file in ("runtime-service", "data-store-service", "network-service", "host"):
            good = {"name": "sql", "protocol": "SQL", "port": 5432}
            self.assertEqual(self._section_failures(f"{schema_file}.schema.yaml", "listener", good), [], schema_file)
            for protocol in ("HTTP", "HTTPS", "TCP", "UDP", "Kafka"):
                self.assertEqual(self._section_failures(f"{schema_file}.schema.yaml", "listener", {**good, "protocol": protocol}), [])
            bad = self._section_failures(f"{schema_file}.schema.yaml", "listener", {**good, "port": "5432"})
            self.assertTrue(any("Change field 'port' to type int" in f for f in bad), bad)
            self.assertTrue(self._section_failures(f"{schema_file}.schema.yaml", "listener", {**good, "protocol": "FTP"}))

    def test_interface_protocol_enum_in_both_component_schemas(self) -> None:
        for schema_file in ("product-component", "data-component"):
            for protocol in ("REST", "SQL", "Redis", "Kafka", "SQS", "SNS", "S3", "DynamoDB", "other"):
                node = {"name": "n", "protocol": protocol}
                self.assertEqual(self._section_failures(f"{schema_file}.schema.yaml", "interface", node), [], (schema_file, protocol))
            self.assertTrue(self._section_failures(f"{schema_file}.schema.yaml", "interface", {"name": "n", "protocol": "FTP"}))

    def test_fills_type(self) -> None:
        self.assertEqual(self._section_failures("reference-architecture.schema.yaml", "deployableObjectEntry", {"slot": "ingress", "fills": "01KSF29JTP-9HYA"}), [])
        bad = self._section_failures("reference-architecture.schema.yaml", "deployableObjectEntry", {"slot": "ingress", "fills": 3})
        self.assertTrue(any("Change field 'fills' to type str" in f for f in bad), bad)

    def test_exposed_through_shapes(self) -> None:
        base = {"name": "g", "deploymentTarget": "t"}
        for value in ("01KSF29JTP-9HYA", ["01KSF29JTP-9HYA", "01KSF29JTP-9HYB"], "none"):
            self.assertEqual(self._section_failures("software-deployment-pattern.schema.yaml", "serviceGroup", {**base, "exposedThrough": value}), [], value)
        self.assertTrue(self._section_failures("software-deployment-pattern.schema.yaml", "serviceGroup", {**base, "exposedThrough": 3}))

    def test_target_interface_type(self) -> None:
        self.assertEqual(self._section_failures("relationship.schema.yaml", None, {"uid": "01KSF29JTP-9HYA", "type": "relationship", "name": "r", "source": "01KSF29JTP-9HYA", "target": "01KSF29JTP-9HYB", "targetInterface": "api", "label": "calls", "catalogStatus": "complete", "schemaVersion": "1.0"}), [])
        bad = self._section_failures("relationship.schema.yaml", None, {"targetInterface": 3})
        self.assertTrue(any("Change field 'targetInterface' to type str" in f for f in bad), bad)


class ProtocolFamiliesTests(unittest.TestCase):
    def test_protocol_families_table(self) -> None:
        import sys

        sys.path.insert(0, str(REPO_ROOT / "framework" / "tools"))
        from protocol_families import family

        expected = {
            "web": ["HTTP", "REST", "HTTPS", "GraphQL", "WebSocket"],
            "grpc": ["gRPC", "HTTP/2"],
            "sql": ["SQL", "PostgreSQL", "MySQL", "MSSQL", "TDS", "Oracle", "SQLite", "MariaDB"],
            "redis": ["Redis"],
            "amqp": ["AMQP"],
            "kafka": ["Kafka"],
            "sqs": ["SQS"],
            "sns": ["SNS"],
            "dynamodb": ["DynamoDB"],
            "s3": ["S3"],
            "snowflake": ["Snowflake"],
            "bigquery": ["BigQuery"],
            "mongodb": ["MongoDB"],
            "other": ["other"],
        }
        for fam, names in expected.items():
            for name in names:
                self.assertEqual(family(name), fam, name)
                self.assertEqual(family(name.upper()), fam, name)
        self.assertEqual(family("PostgreSQL wire protocol"), "sql")
        self.assertEqual(family("HTTPS/REST"), "web")
        self.assertEqual(family("HTTP/2"), "grpc")
        self.assertIsNone(family("AWS SDK (GetSecretValue)"))
        self.assertNotEqual(family("Kafka"), family("AMQP"))
        self.assertEqual(family("HTTP"), family("REST"))
        self.assertEqual(family("HTTP"), family("HTTPS"))
        self.assertIsNone(family(""))

    def test_validate_imports_protocol_families(self) -> None:
        source = (REPO_ROOT / "framework" / "tools" / "validate.py").read_text(encoding="utf-8")
        self.assertRegex(source, r"(?m)^from protocol_families import family\b")
        self.assertNotRegex(source, r"(?m)^[A-Z_]*PROTOCOL[A-Z_]*\s*(:[^=]+)?=")
        self.assertNotIn('"postgresql"', source)


class IntentRemovalDocsTests(unittest.TestCase):
    """Templates, docs, example and changelog no longer mention the intent field."""

    FIELD = re.compile(r"intent:|`intent`")

    def _read(self, rel: str) -> str:
        return (REPO_ROOT / rel).read_text(encoding="utf-8")

    def test_templates_have_no_intent_key(self) -> None:
        for rel in (
            "templates/software-deployment-pattern.yaml.tmpl",
            "templates/reference-architecture.yaml.tmpl",
        ):
            self.assertNotRegex(self._read(rel), r"(?m)^\s*intent:", rel)

    def test_openstack_example_has_no_intent_line(self) -> None:
        rel = "examples/catalog/engineering/software-deployment-patterns/sdp-openstack-iaas-platform.yaml"
        self.assertNotRegex(self._read(rel), r"(?m)^\s*intent:")

    def test_docs_have_no_intent_field_reference(self) -> None:
        for rel in (
            "framework/docs/how-to-add-objects.md",
            "framework/docs/software-deployment-patterns.md",
        ):
            self.assertIsNone(self.FIELD.search(self._read(rel)), rel)

    def test_changelog_has_unreleased_above_newest_version(self) -> None:
        # promote-release turns `## Unreleased` into the numbered section on every
        # release, so right after a promotion main has no Unreleased section and
        # that is correct. When the section exists it must sit above the newest
        # version and carry the five headings in order; when it does not, the
        # newest version's section is checked for the headings instead.
        text = self._read("CHANGELOG.md")
        newest = re.search(r"(?m)^## \d+\.\d+\.\d+", text)
        self.assertIsNotNone(newest)
        heading = re.search(r"(?m)^## Unreleased\s*$", text)  # the heading, not a mention in a bullet
        if heading:
            unreleased = heading.start()
            self.assertLess(unreleased, newest.start())
            section = text[unreleased : newest.start()]
        else:
            following = re.search(r"(?m)^## \d+\.\d+\.\d+", text[newest.end():])
            end = newest.end() + following.start() if following else len(text)
            section = text[newest.start() : end]
        positions = [
            section.find(f"### {name}")
            for name in ("Compatibility Impact", "Added", "Changed", "Fixed", "Migration Notes")
        ]
        self.assertTrue(all(p >= 0 for p in positions), positions)
        self.assertEqual(positions, sorted(positions))


class ListenerIdentityTests(unittest.TestCase):
    OWNER = {"kind": "external_system", "ref": "01KQS0TF60-SYS1"}

    def _validate_module(self):
        sys.path.insert(0, str(REPO_ROOT / "framework" / "tools"))
        import validate

        return validate

    def _listener(self, **fields: object) -> dict:
        base = {"type": "listener", "owner": dict(self.OWNER), "protocol": "HTTPS", "port": 443, "endpoint": "/orders/{id}"}
        base.update(fields)
        return base

    def test_default_port_matches_explicit_port(self) -> None:
        v = self._validate_module()
        self.assertEqual(v.listener_identity(self._listener(port=None)), v.listener_identity(self._listener()))
        self.assertEqual(v.listener_identity(self._listener(protocol="HTTP", port=None))[3], 80)

    def test_templated_path_parameters_and_trailing_slash_normalize(self) -> None:
        v = self._validate_module()
        base = v.listener_identity(self._listener())
        self.assertEqual(v.listener_identity(self._listener(endpoint="/orders/{orderId}")), base)
        self.assertEqual(v.listener_identity(self._listener(endpoint="/orders/:id/")), base)

    def test_host_is_lowercased_out_of_identity_and_never_persisted(self) -> None:
        v = self._validate_module()
        base = v.listener_identity(self._listener())
        other = v.listener_identity(self._listener(endpoint="https://API.Example.COM/orders/{id}"))
        self.assertEqual(other, base)
        self.assertNotIn("example", "".join(str(part) for part in other).lower())

    def test_query_or_fragment_ending_authority_does_not_yield_path(self) -> None:
        v = self._validate_module()
        self.assertEqual(v.normalize_listener_endpoint("https://host?x=/a/b"), "/")
        self.assertEqual(v.normalize_listener_endpoint("https://host#/a/b"), "/")
        self.assertEqual(v.normalize_listener_endpoint("https://host/orders?x=/a/b"), "/orders")

    def test_embedded_scheme_in_path_is_not_treated_as_host(self) -> None:
        v = self._validate_module()
        embedded = v.listener_identity(self._listener(endpoint="/proxy/http://x/{id}"))
        # Repeated slashes in the path still collapse, but the prefix is kept so this
        # does not fall out as a scheme/host pair (which would be "/{}" or "/x/{}").
        self.assertEqual(embedded[-1], "/proxy/http:/x/{}")
        self.assertNotEqual(embedded, v.listener_identity(self._listener(endpoint="/x/{id}")))
        self.assertNotEqual(embedded, v.listener_identity(self._listener(endpoint="http://x/{id}")))

    def test_query_and_fragment_are_dropped_from_endpoint(self) -> None:
        v = self._validate_module()
        base = v.listener_identity(self._listener())
        self.assertEqual(v.listener_identity(self._listener(endpoint="/orders/{id}?a=1")), base)
        self.assertEqual(v.listener_identity(self._listener(endpoint="/orders/{id}#frag")), base)
        self.assertEqual(v.listener_identity(self._listener(endpoint="/orders/{id}?a=1#frag")), base)

    def test_protocol_is_case_insensitive(self) -> None:
        v = self._validate_module()
        self.assertEqual(v.listener_identity(self._listener(protocol="https")), v.listener_identity(self._listener()))

    def test_distinct_owners_never_collapse(self) -> None:
        v = self._validate_module()
        base = v.listener_identity(self._listener())
        other_ref = self._listener(owner={"kind": "external_system", "ref": "01KQS0TF60-SYS2"})
        other_kind = self._listener(owner={"kind": "product_component", "ref": "01KQS0TF60-SYS1"})
        self.assertNotEqual(v.listener_identity(other_ref), base)
        self.assertNotEqual(v.listener_identity(other_kind), base)

    def test_port_and_literal_segments_distinguish_listeners(self) -> None:
        v = self._validate_module()
        base = v.listener_identity(self._listener())
        self.assertNotEqual(v.listener_identity(self._listener(port=8443)), base)
        self.assertNotEqual(v.listener_identity(self._listener(endpoint="/invoices/{id}")), base)

    def test_identity_is_none_without_port_or_default(self) -> None:
        v = self._validate_module()
        self.assertIsNone(v.listener_identity(self._listener(protocol="Kafka", port=None)))
        self.assertIsNone(v.listener_identity(self._listener(owner="not-a-dict")))


class ListenerCatalogTests(unittest.TestCase):
    SYSTEM_UID = "01KQS0TF60-SYS1"
    LISTENER_UID = "01KQS0TF61-AB12"

    def _validate(self, owner_kind: str, owner_ref: str, **overrides: object):
        fields = {"protocol": "HTTPS", "port": 443, "endpoint": "/orders/v1", "authenticationModel": "oauth"}
        fields.update(overrides)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            system_dir = workspace / "catalog" / "systems"
            system_dir.mkdir(parents=True, exist_ok=True)
            (system_dir / "system-test.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: {self.SYSTEM_UID}
                    type: system
                    name: Orders System
                    catalogStatus: complete
                    lifecycleStatus: preferred
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            listener_dir = workspace / "catalog" / "listeners"
            listener_dir.mkdir(parents=True, exist_ok=True)
            (listener_dir / "listener-test.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: {self.LISTENER_UID}
                    type: listener
                    name: Orders API listener
                    owner:
                      kind: {owner_kind}
                      ref: {owner_ref}
                    protocol: {fields['protocol']}
                    port: {fields['port']}
                    endpoint: {fields['endpoint']}
                    authenticationModel: {fields['authenticationModel']}
                    catalogStatus: stub
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            return validate_workspace(workspace)

    def test_valid_listener_owned_by_external_system_is_accepted(self) -> None:
        result = self._validate("external_system", self.SYSTEM_UID)
        self.assertTrue(result.ok, result.stdout + result.stderr)

    def test_owner_ref_naming_no_catalog_object_is_rejected(self) -> None:
        result = self._validate("external_system", "01KQS0TF62-NONE")
        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("owner.ref '01KQS0TF62-NONE' names no catalog object", result.stdout)

    def test_owner_ref_of_different_type_is_rejected(self) -> None:
        result = self._validate("product_component", self.SYSTEM_UID)
        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("is a system object, not a product_component", result.stdout)

    def test_invalid_listener_protocol_is_rejected(self) -> None:
        result = self._validate("external_system", self.SYSTEM_UID, protocol="FTP")
        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("Set protocol to one of", result.stdout)

    def test_listener_with_no_authentication_is_accepted_by_schema(self) -> None:
        result = self._validate("external_system", self.SYSTEM_UID, authenticationModel="none")
        self.assertTrue(result.ok, result.stdout + result.stderr)

    def test_listener_protocol_enum_and_auth_none_are_settled(self) -> None:
        import sys

        import yaml

        sys.path.insert(0, str(REPO_ROOT / "framework" / "tools"))
        from protocol_families import family

        schema = yaml.safe_load((REPO_ROOT / "framework" / "schemas" / "listener.schema.yaml").read_text(encoding="utf-8"))
        protocols = set(schema["enumFields"]["protocol"])
        for protocol in ("REST", "gRPC", "GraphQL", "WebSocket", "AMQP", "SQL", "Redis", "Kafka", "SQS", "SNS", "S3", "other"):
            self.assertIn(protocol, protocols)
        self.assertIn("none", schema["enumFields"]["authenticationModel"])
        self.assertNotIn("gRPC-web", protocols)
        self.assertEqual(family("gRPC-web"), "grpc")
        self.assertIn("gRPC-web", schema["fieldDescriptions"]["protocol"])


class ListenerProtectionRequirementTests(unittest.TestCase):
    """S2.1: mandatory interface-protection on listeners is satisfied by authenticationModel; TBD is not, none is."""

    SECURITY_GROUP = "01KQQ4Q027-T3CA"
    SYSTEM_UID = "01KQS0TF70-SYS2"
    LISTENER_UID = "01KQS0TF71-AB13"

    def _validate(self, authentication_model: str, catalog_status: str = "complete", activate: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            if activate:
                workspace_yaml = workspace / ".draft" / "workspace.yaml"
                import yaml

                config = yaml.safe_load(workspace_yaml.read_text(encoding="utf-8")) or {}
                requirements = config.setdefault("requirements", {})
                requirements["activeRequirementGroups"] = [self.SECURITY_GROUP]
                requirements["requireActiveRequirementGroupDisposition"] = True
                workspace_yaml.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
            system_dir = workspace / "catalog" / "systems"
            system_dir.mkdir(parents=True, exist_ok=True)
            (system_dir / "system-test.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: {self.SYSTEM_UID}
                    type: system
                    name: Payments System
                    catalogStatus: complete
                    lifecycleStatus: preferred
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            listener_dir = workspace / "catalog" / "listeners"
            listener_dir.mkdir(parents=True, exist_ok=True)
            (listener_dir / "listener-test.yaml").write_text(
                textwrap.dedent(
                    f"""
                    schemaVersion: "1.0"
                    uid: {self.LISTENER_UID}
                    type: listener
                    name: Payments API listener
                    owner:
                      kind: external_system
                      ref: {self.SYSTEM_UID}
                    protocol: HTTPS
                    port: 443
                    endpoint: /payments/v1
                    authenticationModel: '{authentication_model}'
                    catalogStatus: {catalog_status}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            return validate_workspace(workspace)

    @staticmethod
    def _section(output: str, header: str) -> str:
        if header not in output:
            return ""
        text = output.split(header, 1)[1]
        for stop in ("Validation failures:", "Validation warnings:"):
            if stop != header and stop in text:
                text = text.split(stop, 1)[0]
        return text

    def _protection_lines(self, output: str, header: str) -> list[str]:
        return [
            line
            for line in self._section(output, header).splitlines()
            if "listener-test.yaml" in line and "interface-protection" in line
        ]

    def test_recorded_authentication_model_satisfies_protection(self) -> None:
        result = self._validate("oauth")
        output = result.stdout + result.stderr
        self.assertTrue(result.ok, output)
        self.assertEqual([], self._protection_lines(output, "Validation failures:"))
        self.assertEqual([], self._protection_lines(output, "Validation warnings:"))

    def test_none_satisfies_protection(self) -> None:
        result = self._validate("none")
        output = result.stdout + result.stderr
        self.assertEqual([], self._protection_lines(output, "Validation failures:"))
        self.assertEqual([], self._protection_lines(output, "Validation warnings:"))

    def test_tbd_does_not_satisfy_protection_on_complete_listener(self) -> None:
        result = self._validate("TBD")
        output = result.stdout + result.stderr
        self.assertFalse(result.ok, output)
        lines = self._protection_lines(output, "Validation failures:")
        self.assertEqual(1, len(lines), output)
        self.assertIn("Requirement not satisfied", lines[0])
        self.assertIn("field(authenticationModel set, not TBD)", lines[0])

    def test_tbd_on_stub_listener_warns_without_failing(self) -> None:
        result = self._validate("TBD", catalog_status="stub")
        output = result.stdout + result.stderr
        self.assertTrue(result.ok, output)
        self.assertEqual([], self._protection_lines(output, "Validation failures:"))
        self.assertEqual(1, len(self._protection_lines(output, "Validation warnings:")), output)

    def test_inactive_security_group_does_not_check_listeners(self) -> None:
        result = self._validate("TBD", activate=False)
        output = result.stdout + result.stderr
        self.assertTrue(result.ok, output)
        self.assertNotIn("interface-protection", output)

    def test_interface_protection_requirement_is_mandatory_on_listeners(self) -> None:
        import yaml

        group = yaml.safe_load(
            (
                REPO_ROOT / "framework" / "configurations" / "requirement-groups"
                / "requirement-group-draft-security-compliance.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertIn("listener", group["appliesTo"])
        requirement = next(r for r in group["requirements"] if r["id"] == "interface-protection")
        self.assertEqual(["listener"], requirement["appliesTo"])
        self.assertEqual("mandatory", requirement["requirementMode"])
        self.assertIs(False, requirement["naAllowed"])
        self.assertEqual(
            [{"mechanism": "field", "key": "authenticationModel", "notIn": ["TBD"]}],
            requirement["canBeSatisfiedBy"],
        )


class FieldMechanismNotInTests(unittest.TestCase):
    def setUp(self) -> None:
        import sys

        sys.path.insert(0, str(REPO_ROOT / "framework" / "tools"))
        import validate

        self.validate = validate
        self.mechanism = {"mechanism": "field", "key": "authenticationModel", "notIn": ["TBD"]}

    def test_not_in_value_never_satisfies(self) -> None:
        satisfied = self.validate.mechanism_satisfied
        self.assertFalse(satisfied({"authenticationModel": "TBD"}, self.mechanism, {}))
        self.assertFalse(satisfied({}, self.mechanism, {}))
        self.assertFalse(satisfied({"authenticationModel": ""}, self.mechanism, {}))
        self.assertTrue(satisfied({"authenticationModel": "none"}, self.mechanism, {}))
        self.assertTrue(satisfied({"authenticationModel": "iam"}, self.mechanism, {}))

    def test_field_implementation_pointing_at_excluded_value_does_not_satisfy(self) -> None:
        requirement = {
            "id": "interface-protection",
            "requirementMode": "mandatory",
            "naAllowed": False,
            "canBeSatisfiedBy": [self.mechanism],
            "validAnswerTypes": ["field"],
        }
        implementation = {
            "requirementGroup": "group-x",
            "requirementId": "interface-protection",
            "status": "satisfied",
            "mechanism": "field",
            "key": "authenticationModel",
        }
        obj = {"type": "listener", "uid": "01KQS0TF72-AB14", "authenticationModel": "TBD",
               "requirementImplementations": [implementation]}
        ok, _ = self.validate.validate_requirement(obj, requirement, "group-x", {})
        self.assertFalse(ok)
        obj["authenticationModel"] = "none"
        ok, _ = self.validate.validate_requirement(obj, requirement, "group-x", {})
        self.assertTrue(ok)

    def test_not_in_must_be_a_list_on_a_field_mechanism(self) -> None:
        group = {
            "uid": "01KQS0TF73-RG01",
            "type": "requirement_group",
            "name": "Shape group",
            "activation": "workspace",
            "appliesTo": ["listener"],
            "requirements": [
                {
                    "id": "bad-not-in",
                    "requirementMode": "mandatory",
                    "naAllowed": False,
                    "canBeSatisfiedBy": [{"mechanism": "field", "key": "authenticationModel", "notIn": "TBD"}],
                    "validAnswerTypes": ["field"],
                },
                {
                    "id": "not-in-off-field",
                    "requirementMode": "mandatory",
                    "naAllowed": False,
                    "canBeSatisfiedBy": [{"mechanism": "decisionRecord", "notIn": ["TBD"]}],
                    "validAnswerTypes": ["decisionRecord"],
                },
            ],
        }
        failures: list[str] = []
        self.validate.validate_requirement_group(group, Path("group.yaml"), set(), failures)
        not_in = [f for f in failures if "notIn" in f]
        self.assertEqual(2, len(not_in), failures)
        self.assertNotIn("Replace invalid appliesTo values", " ".join(failures))


if __name__ == "__main__":
    unittest.main()
