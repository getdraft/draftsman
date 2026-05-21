from __future__ import annotations

import tempfile
import textwrap
import unittest
import subprocess
import sys
from pathlib import Path

from draft_table.paths import REPO_ROOT
from draft_table.repo import ensure_workspace_layout
from draft_table.validation import build_validate_command, validate_workspace


class ValidationTests(unittest.TestCase):
    def test_build_validate_command_targets_framework_tool(self) -> None:
        command = build_validate_command(REPO_ROOT / "examples")

        self.assertIn("framework/tools/validate.py", command[1])
        self.assertEqual(command[-2], "--workspace")
        self.assertEqual(Path(command[-1]), REPO_ROOT / "examples")

    def test_validate_examples_workspace(self) -> None:
        result = validate_workspace(REPO_ROOT / "examples")

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertIn("Validated", result.stdout)

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
                    catalogStatus: draft
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
                    catalogStatus: draft
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
        self.assertIn("Satisfy Company Control / company-required-field", result.stdout)

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
                    catalogStatus: approved
                    lifecycleStatus: candidate
                    architecturalDecisions:
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
                    catalogStatus: draft
                    lifecycleStatus: candidate
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            pattern_dir = workspace / "catalog" / "software-deployment-patterns"
            pattern_dir.mkdir(parents=True, exist_ok=True)
            (pattern_dir / "software-deployment-pattern-host-ref.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    uid: 01KQS0TF53-SDMP
                    type: software_deployment_pattern
                    name: Host Ref Pattern
                    catalogStatus: draft
                    lifecycleStatus: candidate
                    architecturalDecisions:
                      noApplicablePattern: Test fixture.
                      deploymentTargets: Test target.
                      availabilityRequirement: Test availability.
                      dataClassification: Test data.
                      failureDomain: Test failure domain.
                      noPatternDeviations: Test fixture.
                      noAdditionalInteractions: Test fixture.
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
                    catalogStatus: draft
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
                          - mechanism: architecturalDecision
                            key: missingDecision
                        minimumSatisfactions: 1
                        validAnswerTypes:
                          - architecturalDecision
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
                    catalogStatus: approved
                    lifecycleStatus: existing-only
                    requirementGroups:
                      - requirement-group.company-control
                    architecturalDecisions:
                      companyEvidence: Provided by explicit object-level evidence.
                    requirementImplementations:
                      - requirementGroup: requirement-group.company-control
                        requirementId: company-required-field
                        status: satisfied
                        mechanism: architecturalDecision
                        key: companyEvidence
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)

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
                catalogStatus: draft
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
                catalogStatus: approved
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
        rationale_kind: str = "external",
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
                    catalogStatus: draft
                    capabilities:
                    {capability_lines}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

        if include_rationale and rationale_kind == "internal":
            decisions = (
                "internalComponentRationales:\n"
                "  01KQS0TF60-STVW: Included as optional application performance telemetry for runtimes deployed on this host standard."
            )
        elif include_rationale:
            decisions = (
                "externalInteractionRationales:\n"
                "  Dynatrace Platform: Included as optional application performance telemetry for runtimes deployed on this host standard."
            )
        else:
            decisions = "lifecycleRationale: Test approved host fixture."
        decision_lines = textwrap.indent(decisions, "  ")
        apm_interaction = (
            """  - name: Dynatrace Platform
    enabledBy: 01KQS0TF60-STVW
    capabilities:
      - 01KQQ4Q026-NB1W
"""
            if include_apm_interaction
            else ""
        )
        (host_dir / "host-test-complete.yaml").write_text(
            f"""schemaVersion: "1.0"
uid: 01KQS0TF60-XYZ1
type: host
name: Test Complete Host
catalogStatus: approved
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
externalInteractions:
  - name: Identity Platform
    capabilities:
      - 01KQQ4Q026-MHJM
  - name: Logging Platform
    capabilities:
      - 01KQQ4Q026-D04B
  - name: Health Monitoring Platform
    capabilities:
      - 01KQQ4Q026-98VD
  - name: Security Monitoring Platform
    enabledBy: 01KQS0TF60-JKMX
    capabilities:
      - 01KQQ4Q026-JW52
  - name: Patch Management Platform
    enabledBy: 01KQS0TF60-NPQR
    capabilities:
      - 01KQQ4Q026-BH6E
{apm_interaction.rstrip()}
architecturalDecisions:
{decision_lines}
requirementGroups:
  - 01KQQ4Q027-THYN
""",
            encoding="utf-8",
        )

    def test_appliance_delivery_satisfies_service_like_capabilities_directly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            catalog = workspace / "catalog" / "edge-gateway-services"
            catalog.mkdir(parents=True)
            (workspace / "configurations").mkdir()
            (catalog / "edge-gateway-service-aws-alb.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: edge-gateway.aws-alb
                    type: edge_gateway_service
                    name: AWS Application Load Balancer
                    deliveryModel: appliance
                    vendor: Amazon Web Services
                    productName: Application Load Balancer
                    productVersion: managed
                    classification: software
                    catalogStatus: draft
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
                    externalInteractions:
                      - name: Centralized logging
                        capabilities:
                          - capability.log-management
                    networkPlacement: public-facing
                    patchingOwner: aws-managed
                    complianceCerts: []
                    architecturalDecisions:
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

    def test_external_interaction_ref_must_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            host_dir = workspace / "catalog" / "hosts"
            host_dir.mkdir(parents=True)
            (workspace / "configurations").mkdir()
            (host_dir / "host-test.yaml").write_text(
                textwrap.dedent(
                    """
                    schemaVersion: "1.0"
                    id: host.test
                    type: host
                    name: Test Host
                    catalogStatus: stub
                    lifecycleStatus: existing-only
                    externalInteractions:
                      - name: Missing Logging Service
                        ref: service.missing.logging
                        capabilities:
                          - capability.log-management
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            self._repair_workspace_uids(workspace)

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("externalInteractions[0].ref references unknown object", result.stdout)

    def test_unrequired_host_external_interaction_requires_architectural_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_complete_host_with_extra_apm_interaction(workspace, include_rationale=False)

            result = validate_workspace(workspace)

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("externalInteractionRationales['Dynatrace Platform']", result.stdout)
        self.assertIn("does not directly satisfy any applicable requirement", result.stdout)

    def test_unrequired_host_external_interaction_with_architectural_decision_validates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            ensure_workspace_layout(workspace)
            self._write_complete_host_with_extra_apm_interaction(workspace, include_rationale=True)

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotIn("does not directly satisfy any applicable requirement", result.stdout)

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
                    catalogStatus: draft
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
                    catalogStatus: draft
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
                    catalogStatus: approved
                    lifecycleStatus: preferred
                    host: 01KQS0TF61-HST1
                    primaryTechnologyComponent: 01KQS0TF61-DBMS
                    internalComponents:
                      - ref: 01KQS0TF61-HST1
                        role: host
                      - ref: 01KQS0TF61-DBMS
                        role: function
                    architecturalDecisions:
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
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotIn("internalComponentRationales['01KQS0TF61-DBMS']", result.stdout)
        self.assertNotIn("does not directly satisfy any applicable requirement", result.stdout)

    def test_backup_platform_external_interaction_satisfies_data_store_requirement(self) -> None:
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
                    uid: 01KQS0TF62-DBMS
                    type: technology_component
                    name: Test DBMS
                    vendor: Test Vendor
                    productName: Test DBMS
                    productVersion: "1"
                    classification: software
                    catalogStatus: draft
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
                    catalogStatus: draft
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
                    catalogStatus: approved
                    lifecycleStatus: preferred
                    host: 01KQS0TF62-HST1
                    primaryTechnologyComponent: 01KQS0TF62-DBMS
                    internalComponents:
                      - ref: 01KQS0TF62-HST1
                        role: host
                      - ref: 01KQS0TF62-DBMS
                        role: function
                    externalInteractions:
                      - name: Test Backup Vault
                        capabilities:
                          - 01KQQ4Q026-7T2H
                    architecturalDecisions:
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
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = validate_workspace(workspace)

        self.assertTrue(result.ok, result.stdout + result.stderr)
        self.assertNotIn("externalInteractionRationales['Test Backup Vault']", result.stdout)
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
                    catalogStatus: draft
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
                    catalogStatus: draft
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
                    catalogStatus: draft
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
                    catalogStatus: draft
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
                    catalogStatus: draft
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
                    catalogStatus: draft
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
                    catalogStatus: draft
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
                    catalogStatus: draft
                    lifecycleStatus: candidate
                    internalComponents:
                      - ref: 01KQS0TF66-RBMQ
                        role: broker-client
                        configuration: amqp-listener
                    architecturalDecisions:
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
                    catalogStatus: draft
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
                    catalogStatus: draft
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
                    catalogStatus: draft
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
                    catalogStatus: draft
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
                    catalogStatus: approved
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
                    catalogStatus: draft
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
                    catalogStatus: draft
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

    def test_capability_implementation_ref_must_be_technology_component(self) -> None:
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
                    deliveryModel: self-managed
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
                    catalogStatus: draft
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

        self.assertFalse(result.ok, result.stdout + result.stderr)
        self.assertIn("capability lifecycle applies only to discrete vendor product versions", result.stdout)

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

    def _write_sdp_with_deployment_target(self, workspace: Path, deployment_target: str) -> None:
        pattern_dir = workspace / "catalog" / "software-deployment-patterns"
        pattern_dir.mkdir(parents=True, exist_ok=True)
        (pattern_dir / "software-deployment-pattern-vocabulary.yaml").write_text(
            textwrap.dedent(
                f"""
                schemaVersion: "1.0"
                uid: 01KQS0TF70-SDMP
                type: software_deployment_pattern
                name: Vocabulary Test Pattern
                catalogStatus: draft
                lifecycleStatus: candidate
                architecturalDecisions:
                  noApplicablePattern: Test fixture.
                  deploymentTargets: Test target.
                  availabilityRequirement: Test availability.
                  dataClassification: Test data.
                  failureDomain: Test failure domain.
                  noPatternDeviations: Test fixture.
                  noAdditionalInteractions: Test fixture.
                serviceGroups:
                  - name: Application Tier
                    deploymentTarget: {deployment_target}
                    deployableObjects: []
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
