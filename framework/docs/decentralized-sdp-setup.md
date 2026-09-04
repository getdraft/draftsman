---
type: documentation
title: "Decentralized SDPs & Product Registration"
description: "How product engineering teams house SoftwareDeploymentPatterns in their own repos and register with drafting-table."
tags:
  - draft
  - documentation
  - sdp
  - decentralization
  - product_registration
timestamp: 2026-08-26T00:00:00-04:00
---

# Decentralized SoftwareDeploymentPatterns & Product Registration

## Architectural Overview

DRAFT 1.0 establishes a clean line of demarcation across three content groups:

1. **Product Architecture (Product Engineering Teams)**: Housed inside individual product repositories (`.draft/sdp.yaml`) and registered centrally via `ProductRegistration` objects in `drafting-table`.
2. **Shared Services & Infrastructure (Internal Provider Teams)**: Housed inside individual provider repositories (`.draft/catalog/`) with explicit IaC module pointers (`deployablePackage: { registry, source, version, modulePath }`) and registered centrally in `drafting-table`.
3. **External Provider Hooks (Third-Party SaaS/PaaS)**: Governed under `.draft/providers/` and SaaS/PaaS delivery models.

## Product Registration Contract

An engineering team registers their product with the central `drafting-table` workspace by adding a `product_registration` YAML file under `catalog/engineering/product-registrations/product-reg-<name>.yaml`:

```yaml
schemaVersion: '1.0'
uid: PRODREG01-ABSENCE
type: product_registration
name: Absence Management
catalogStatus: complete
owner:
  team: product-absence-time
  contact: absence-team@example.com
businessContext:
  pillar: business-pillar.people-solutions
  productFamily: Absence & Time
repository:
  provider: github
  url: https://github.com/company/absence-service
  defaultBranch: main
sdpManifest:
  mode: git
  path: .draft/sdp.yaml
```

## Product Repo Manifest (`.draft/sdp.yaml`)

Inside the product code repository, the team maintains `.draft/sdp.yaml`:

```yaml
schemaVersion: '1.0'
uid: SDP0000001-ABSENCE
type: software_deployment_pattern
name: Absence Management Production Deployment
catalogStatus: complete
lifecycleStatus: preferred
followsReferenceArchitecture: RA0000001-1234
businessContext:
  pillar: business-pillar.people-solutions
  productFamily: Absence & Time
serviceGroups:
  - name: Application Services
    deploymentTarget: aws-us-east-1
    substrate: RS0000001-EKS
    deployableObjects:
      - ref: PC0000001-API
        diagramTier: application
```

## Event-Driven Least-Privilege Synchronization

When an engineering team merges a PR updating `.draft/sdp.yaml`:

1. The product repo's GitHub Action (`.github/workflows/draft-sync.yml`) requests an ephemeral token (valid 60 minutes) targeting **only** `drafting-table`.
2. It pushes the `.draft/sdp.yaml` payload to `drafting-table` via GitHub REST API `repository_dispatch`.
3. Central `drafting-table` runs `validate.py`, updates `.draft/external_sdps/`, and regenerates `catalog_indexes.json` and `AI_INDEX.md`.

`drafting-table` holds **zero read credentials for product repositories**, ensuring complete source code isolation.

## Dual AI Agent Modes

* **Query & Guidance Mode (Slack / Discord / Web UI)**: Strictly read-only. Queries pre-compiled `catalog_indexes.json` to answer questions about architecture, ports, DB engines, and dependencies. Directs engineers to native IDE tools for authoring.
* **Authoring & Execution Mode (IDE / CLI)**: Interactively scaffolds `.draft/sdp.yaml`, runs validation, and helps engineers edit product architecture directly inside their code repos.
