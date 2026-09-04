# Deployable Shared Services Composition Specification

## Executive Overview

DRAFT enables **Enterprise-Grade Vibe Coding** by turning static architecture specifications into composable, standard, and compliant application infrastructure.

> **Core Principle:** **AI drafts the architectural intent** (`.draft/sdp.yaml`); **the Composition Engine (`compose_iac.py`) composes the deterministic infrastructure code** (`main.tf`). AI never generates free-form Terraform directly; it stitches pre-approved, versioned platform modules.

---

## 1. Shared Service Provisioning Models

Every shared service object in the catalog (`host`, `runtime_service`, `data_store_service`, `network_service`, `ai_gateway`) declares a `provisioningModel`:

### A. `deployable`
- **Definition**: A company-approved shared service backed by a versioned, test-verified IaC module or package repository.
- **Contract**: Must declare a `deployablePackage` block:
  ```yaml
  provisioningModel: deployable
  deployablePackage:
    registry: github              # e.g., github, artifactory, terraform-registry
    source: internal-org/terraform-aws-dynamodb
    version: v2.4.0
    modulePath: modules/encrypted-table
  ```
- **Capability**: Enables products to be automatically composed and deployed end-to-end. SDPs composed entirely of `deployable` shared services can reach `catalogStatus: complete` and be certified as `deployment-ready`.

### B. `reference-only`
- **Definition**: Legacy technology standards, SaaS platforms, or "acceptable use" platforms that have no automated IaC provisioning modules or repos.
- **Contract**: Does not contain a `deployablePackage`.
- **Capability**: Satisfies `RequirementGroups` for compliance, audit, and governance documentation. However, any SDP that relies on a `reference-only` shared service is **automatically capped at `catalogStatus: documentation`** (or `incomplete`/`stub`) by `framework/tools/validate.py` and cannot be marked `deployment-ready`.

---

## 2. Automated Manifest Synchronization & Composition Resolution Flow

DRAFT reuses the existing **Automated Manifest Synchronization** architecture (`.draft/sdp.yaml` + GitHub token push):

```text
 ┌─────────────────────────────────────────┐         ┌──────────────────────────────────────────┐
 │  PRODUCT CODE REPO (.draft/sdp.yaml)   │         │  CENTRAL DRAFTING-TABLE CATALOG          │
 └────────────────────┬────────────────────┘         └────────────────────┬─────────────────────┘
                      │                                                   │
                      │ 1. Local Draftsman Session                        │
                      │    Resolves Shared Service UIDs                  │
                      ├───────────────────────────────────────────────────┤
                      │    Fetches `deployablePackage` Contracts ◄───────┤
                      │                                                   │
                      │ 2. Compose Engine (`compose_iac.py`)             │
                      │    Stitches IaC Modules into `main.tf`            │
                      │                                                   │
                      │ 3. Automated Token Push                           │
                      │    Syncs `.draft/sdp.yaml` to catalog ───────────►│
```

### Composition Resolution Steps

1. **Graph Traversal**: The composition engine inspects the product's `.draft/sdp.yaml` to identify all referenced `serviceGroups`, `substrates`, and `deployableObjects`.
2. **Package Extraction**: For each referenced shared service UID, `compose_iac.py` fetches the catalog object's `deployablePackage` metadata.
3. **Module Ingestion**: The engine pulls the declared versioned module (e.g. `github.com/internal-org/terraform-aws-dynamodb?ref=v2.4.0`).
4. **Variable Binding**: Input variables declared in the SDP (e.g. `replicaCount`, `autoscaling`, `instance`) are bound to the module's parameters.
5. **Output Generation**: Emits deterministic IaC manifests (e.g., `infra/generated/main.tf` or `infra/generated/helm-values.yaml`) directly into the product repository.

---

## 3. Environment & Landing Zone Abstraction `[Roadmap Phase 2]`

> **Note on Feature Availability:** The `EnvironmentProfile` schema and resolution engine described below is a **Roadmap Phase 2 Specification**. It defines the target contract for multi-environment landing zone resolution.

### The Problem

Application engineers should **never** specify cloud account numbers, subnet IDs, VPC CIDRs, or provider regions in their product architectural specifications (`.draft/sdp.yaml`). Hardcoding environment mechanics into product patterns creates drift, breaks portability across multi-cloud targets (AWS, GCP, Azure, VMware), and leaks operational secrets.

### The DevOps-Owned Solution: `EnvironmentProfile`

In DRAFT, environment resolution is split into two distinct ownership domains:

| Ownership Domain | Responsible Persona | Artifact | Contents |
| :--- | :--- | :--- | :--- |
| **Architectural Intent** | Product Engineer / AI | `.draft/sdp.yaml` | Service topology, scaling units, tier variants (e.g., `prod` vs `dev`), data classification, and quality targets. |
| **Infrastructure Landing Zone** | DevOps / Platform Team | `EnvironmentProfile` | Cloud provider accounts, subnet mappings, IAM execution roles, key management (KMS), and ingress routing. |

```yaml
# Example DevOps-Owned EnvironmentProfile (in drafting-table/configurations/environments/)
schemaVersion: '1.0'
type: environment_profile
uid: 01KQQ88Z02-ENV1
name: AWS Production Landing Zone
tierId: prod
provider: aws
region: us-east-1
parameters:
  vpcId: vpc-0a1b2c3d4e
  privateSubnets: ["subnet-1111", "subnet-2222"]
  kmsKeyArn: arn:aws:kms:us-east-1:123456789012:key/abc-123
  iamRolePrefix: prod-app-role-
```

---

## 4. Inter-Module Variable Binding & Input-Output Contracts

When multiple `deployable` modules are composed into a product's IaC (`main.tf`), the composition engine binds module outputs to module inputs using deterministic HCL references:

```hcl
# Generated by compose_iac.py in infra/generated/main.tf

module "rds_database" {
  source  = "github.com/company-infrastructure/terraform-aws-postgresql?ref=v3.2.0"
  db_name = "absence_db"
  # Environment parameters bound from EnvironmentProfile
  vpc_id          = var.landing_zone_vpc_id
  private_subnets = var.landing_zone_private_subnets
}

module "app_runtime" {
  source = "github.com/company-infrastructure/terraform-aws-eks-workload?ref=v1.8.0"
  # Output-to-Input dynamic binding
  database_endpoint = module.rds_database.endpoint
  database_secret_arn = module.rds_database.secret_arn
}
```

---

## 5. Application Credential & Secret Handoff Contract (`infra/outputs.json`)

To bridge composed infrastructure outputs (endpoints, database names, KMS keys, Secret ARNs) back into the application runtime code:

1. **`infra/outputs.json` Generation**: The composition engine configures `main.tf` to emit a standardized JSON manifest of operational outputs upon `tofu apply` / `terraform apply`.
2. **CI/CD Credential Handoff**: The application deployment pipeline reads `infra/outputs.json` and injects runtime environment variables (or Kubernetes Secret manifests) into the application container:
   ```json
   {
     "DATABASE_HOST": "absence-db.cluster-c123.us-east-1.rds.amazonaws.com",
     "DATABASE_PORT": 5432,
     "DATABASE_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:absence-db-pass"
   }
   ```
This enforces a clean separation: IaC owns infrastructure creation; CI/CD owns app configuration injection.
