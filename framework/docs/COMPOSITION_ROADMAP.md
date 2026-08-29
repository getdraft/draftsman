# DRAFT Framework Architecture Composition Roadmap

## Overview

This roadmap defines the implementation specifications for follow-on DRAFT framework capabilities. These items build upon the `provisioningModel: deployable | reference-only` split to achieve full automated IaC composition for enterprise-grade vibe coding.

---

## Phase 1: `compose_iac.py` Composition Engine

### Objective
Build a lightweight, hermetic Python utility (`framework/tools/compose_iac.py`) that reads a product's `.draft/sdp.yaml`, resolves all referenced `deployable` shared services, and generates executable IaC manifests and application output contracts.

### CLI Contract
```bash
python3 .draft/framework/tools/compose_iac.py \
  --workspace . \
  --sdp .draft/sdp.yaml \
  --tier prod \
  --output-dir infra/generated/
```

### Functional Requirements
1. **Dependency Resolution**: Traverses `serviceGroups`, `substrates`, and `deployableObjects` in the target SDP.
2. **Package Extraction**: Reads `deployablePackage` metadata (`registry`, `source`, `version`, `modulePath`) for each referenced shared service.
3. **Template Stitching**: Emits clean HCL (`main.tf`, `variables.tf`, `outputs.tf`) or Helm `values.yaml` referencing official module sources.
4. **App Config Handoff Contract**: Generates `infra/outputs.json` mapping composed infrastructure outputs (endpoints, database names, KMS keys, Secret ARNs) so CI/CD pipelines can inject them into application containers.
5. **Validation Gate**: Refuses execution if any referenced shared service has `provisioningModel: reference-only`.

---

## Phase 2: `EnvironmentProfile` Schema & Resolution Engine

### Objective
Formalize the DevOps-owned infrastructure abstraction separating developer SDP intent from cloud landing zone configuration.

### Schema Contract (`environment-profile.schema.yaml`)
```yaml
schemaVersion: '1.0'
type: environment_profile
requiredFields: [schemaVersion, uid, type, name, tierId, provider]
optionalFields: [region, networkPlacement, parameters, iamExecutionRole, tags]
```

### Resolution Logic
- **Ownership**: Authored exclusively by DevOps/Platform Engineering under `configurations/environments/` in `drafting-table`.
- **Match Strategy**: When `--tier <tier_id>` is specified during composition, `compose_iac.py` matches `<tier_id>` against `environment_profile.tierId` and populates infrastructure parameters (VPC IDs, KMS keys, subnets, IAM role prefixes).

---

## Phase 3: Standardized CI/CD Pipeline Templates

### Objective
Provide turnkey GitHub Actions templates (`templates/github/sdp-cicd-pipeline.yml.tmpl`) enforcing automated validation, plan, test, and promotion.

### Pipeline Lifecycle Stages

```text
 ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │1. DRAFT-     │───►│2. IAC PLAN   │───►│3. DEV APPLY  │───►│4. TEST &     │───►│5. PROMOTE    │
 │   VALIDATE   │    │   (OPEN-TOFU)│    │   (DEV ENV)  │    │   BUILD      │    │   STAGE/PROD │
 └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

1. **`draft-validate`**: Executes `python3 .draft/framework/tools/validate.py --workspace .`.
2. **`iac-plan`**: Runs `compose_iac.py` and `tofu plan` to generate IaC execution diffs.
3. **`dev-apply`**: Applies plan to ephemeral development environment.
4. **`test-build`**: Reads `infra/outputs.json` to inject environment variables and execute integration test suites.
5. **`promote-stage` / `promote-prod`**: Promotes approved pattern payloads to higher tiers via GitHub environment approvals.

---

## Phase 4: Catalog Migration Strategy

### Objective
Migrate existing enterprise shared service entries from legacy unclassified objects to explicit `deployable` vs `reference-only` status.

### Execution Plan
1. **Automated Baseline**: Run `framework/tools/migrate_shared_services_provisioning_model.py` across company catalog repos (`drafting-table`).
2. **Platform Audit**: Platform teams review migrated objects:
   - Shared services with existing IaC modules are updated to `provisioningModel: deployable` with `deployablePackage` references.
   - Legacy platforms remain `provisioningModel: reference-only`.
3. **Pattern Recalibration**: Update dependent SDP `catalogStatus` fields to align with validator caps.

---

## Phase 5: Governance & `lifecycleStatus` Gating

### Objective
Enforce policy rules governing which components can be recommended by Draftsman AI agents during vibe coding sessions.

### Rules
1. **`preferred` Lifecycle Gate**: Only shared services with `provisioningModel: deployable` may be marked `lifecycleStatus: preferred`.
2. **AI Recommendation Prioritization**: Draftsman AI agent (`draftsman`) is instructed to select `deployable` shared services by default when assisting product engineers.
3. **Reference-Only Exception Approval**: Selecting a `reference-only` shared service requires an explicit `decision_record` explaining the deviation.

---

## Phase 6: Versioning, Drift Policy & Mass Upgrade Tooling

### Objective
Prevent breaking changes and infrastructure drift when shared service IaC modules are updated by platform teams.

### Policy Rules & Tooling
1. **Strict Versioning**: `deployablePackage.version` must use semantic versioning or exact git tag references (`v1.2.3`). Unpinned branch pointers (`main`, `latest`) are forbidden by validation.
2. **Automated Mass Upgrades**: Provide a framework utility (`framework/tools/upgrade_modules.py`) that Platform teams use to automatically search all product repositories and submit upgrade PRs when a shared service module releases a patch or major version update.
