---
type: documentation
title: "Shared Services Onboarding Guide"
description: "As a Shared Services representative, you are accountable for the **shared-services layer** of the architecture catalog."
tags:
  - draft
  - documentation
  - shared_services_onboarding
timestamp: 2026-06-12T21:06:02-07:00
---
# Shared Services Onboarding Guide

> **Audience:** Platform Engineers, Infrastructure Leads, Security Architects, and Database Administrators.
> This guide is a quick tutorial to help infrastructure and platform teams onboard and document reusable technical standards in a DRAFT workspace.

---

## 1. Overview of the Shared Services Layer

As a Shared Services representative, you are accountable for the **shared-services layer** of the architecture catalog. You define the approved infrastructure platforms, database systems, networks, and third-party vendor software that Engineering product teams reference in their application models.

The Shared Services layer comprises five core object types authored in provider repositories (`.draft/catalog/`) and synced to `drafting-table`:
1. **TechnologyComponent** (`technology-components/`): Represents a discrete vendor product or release (e.g. Ubuntu 22.04 LTS, PostgreSQL 15, HAProxy 2.9).
2. **Host** (`hosts/`): Represents a standard operating platform combining an operating system, compute substrate, and base capabilities.
3. **RuntimeService** (`runtime-services/`): Represents a reusable execution runtime (e.g. AWS Lambda runtime, OpenStack Horizon, Nginx app runtime).
4. **DataStoreService** (`data-store-services/`): Represents a reusable database or storage platform (e.g. a shared PostgreSQL instance, Amazon S3 bucket tier).
5. **NetworkService** (`network-services/`): Represents standard network and traffic-control standards (e.g. WAF profiles, shared load balancers).

```text
<provider-repo>/.draft/catalog/
  technology-components/  ← Standard vendor products, OS types, software releases
  hosts/                  ← Reusable virtual/physical servers and substrates
  runtime-services/       ← Container runtimes, serverless runtimes, app runtimes
  data-store-services/    ← Shared database systems and cloud storage platforms
  network-services/       ← Corporate load balancers, DNS setups, WAF engines
```

---

## 2. Choosing a Provisioning Model: `deployable` vs `reference-only`

When publishing a shared service (`Host`, `RuntimeService`, `DataStoreService`, `NetworkService`, `AIGateway`), you must declare its `provisioningModel`:

### Path A: `provisioningModel: deployable` (Recommended for Modern Building Blocks)
Use this path when your platform team maintains a versioned Infrastructure-as-Code (IaC) module or automated package repository (Terraform, OpenTofu, Helm, CloudFormation).

* **Requirement**: You must specify a `deployablePackage` block:
  ```yaml
  provisioningModel: deployable
  deployablePackage:
    registry: github
    source: company-infrastructure/terraform-aws-postgresql
    version: v3.2.0
    modulePath: modules/encrypted-rds
  ```
* **Impact**: Engineering product patterns (SDPs) that compose `deployable` shared services can be automatically built into executable IaC pipelines and reach `catalogStatus: complete` / `deployment-ready`.

### Path B: `provisioningModel: reference-only` (For Legacy Tech & SaaS Platforms)
Use this path for legacy technology standards, SaaS platforms, or manual infrastructure platforms that do not have an automated IaC module repository.

* **Requirement**: Omit `deployablePackage` or explicitly set `provisioningModel: reference-only`.
* **Impact**: `reference-only` objects still satisfy `RequirementGroups` for compliance, audit, and security controls. However, any Product SDP that relies on a `reference-only` shared service **is capped at `catalogStatus: documentation`** and cannot reach `deployment-ready` until an IaC module is published.

---

## 3. Modeling Infrastructure & Software Standards

To document a reusable platform standard correctly, follow the step-by-step modeling sequence:

### Step 1: Create a TechnologyComponent
Before you can define a virtual host or runtime service, model the vendor products that compose them in `catalog/shared-services/technology-components/`:
* Define a unique `uid` (your AI Draftsman will generate this).
* Set the `vendor`, `productName`, and `productVersion` parameters.
* Specify `classification` (e.g., `operating-system`, `compute-platform`, `software`, or `agent`).
* Map `capabilities` to document which architectural functions this product satisfies out-of-the-box.

### Step 2: Model the Reusable Substrate or Host
Author a `Host` YAML file in `catalog/shared-services/hosts/`:
* Set `provisioningModel: deployable` (with `deployablePackage`) if an IaC template exists, or `reference-only` if manual.
* Reference the exact `operatingSystemComponent` and `computePlatformComponent` UIDs.
* Declare standard platform agents in `internalComponents`.
* Set `requirementGroups` to map the Host to standard workspace security profiles.

### Step 3: Define Shared Runtimes & Data Stores
Author a `RuntimeService` or `DataStoreService` YAML file:
* Declare `provisioningModel: deployable` or `reference-only`.
* Reference the `host` substrate.
* Define `deliveryModel` (`saas`, `paas`, `appliance`, or `self-managed`).
* For `DataStoreService` entries, explicitly document data protection features (backup strategies, RTO, RPO).

---

## 4. Platform Mapping & Capability Governance

* **Bridging Capabilities to Tech**: Platform leads maintain capability mapping overlays in `configurations/object-patches/` mapping core capabilities to approved TechnologyComponents.
* **Progressive Onboarding**: Start new profiles with `catalogStatus: stub` or `catalogStatus: incomplete`.
* **Automated Code Validation**: Run `python3 .draft/framework/tools/validate.py --workspace .` before opening pull requests.
