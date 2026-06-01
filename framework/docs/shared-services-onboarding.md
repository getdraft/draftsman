# Shared Services Onboarding Guide

> **Audience:** Platform Engineers, Infrastructure Leads, Security Architects, and Database Administrators.
> This guide is a quick tutorial to help infrastructure and platform teams onboard and document reusable technical standards in a DRAFT workspace.

---

## 1. Overview of the Shared Services Layer

As a Shared Services representative, you are accountable for the **shared-services layer** of the architecture catalog. You define the approved infrastructure platforms, database systems, networks, and third-party vendor software that Engineering product teams reference in their application models.

The Shared Services layer comprises five core object types inside `catalog/shared-services/`:
1. **TechnologyComponent** (`technology-components/`): Represents a discrete vendor product or release (e.g. Ubuntu 22.04 LTS, PostgreSQL 15, HAProxy 2.9).
2. **Host** (`hosts/`): Represents a standard operating platform combining an operating system, compute substrate, and base capabilities.
3. **RuntimeService** (`runtime-services/`): Represents a reusable execution runtime (e.g. AWS Lambda runtime, OpenStack Horizon, Nginx app runtime).
4. **DataStoreService** (`data-store-services/`): Represents a reusable database or storage platform (e.g. a shared PostgreSQL instance, Amazon S3 bucket tier).
5. **NetworkService** (`network-services/`): Represents standard network and traffic-control standards (e.g. WAF profiles, shared load balancers).

```text
catalog/shared-services/
  technology-components/  ← Standard vendor products, OS types, software releases
  hosts/                  ← Reusable virtual/physical servers and substrates
  runtime-services/       ← Container runtimes, serverless runtimes, app runtimes
  data-store-services/    ← Shared database systems and cloud storage platforms
  network-services/       ← Corporate load balancers, DNS setups, WAF engines
```

For ongoing operating standards, ticketing, routing, and Pull Request reviews, refer directly to the central [Draft Operations Guide](operations-guide.md).

---

## 2. Your First Action: Connect Your AI Assistant

DRAFT is Git-native and repo-first. You do not need to install local CLI tools. You interact with DRAFT using the AI assistant connected to your repository workspace. 

Copy the prompt below and paste it into your AI assistant chat window to start a session:

```text
I need a draftsman. Open a drafting session to document our new shared database standard.
```

Your AI assistant will immediately assume the **Draftsman** role, read your workspace configuration, and guide you through the process step-by-step.

---

## 3. Modeling Infrastructure & Software Standards

To document a reusable platform standard correctly, follow the step-by-step modeling sequence:

### Step 1: Create a TechnologyComponent
Before you can define a virtual host or runtime service, you must model the vendor products that compose them. Author a `TechnologyComponent` YAML file in `catalog/shared-services/technology-components/`:
* Define a unique `uid` (your AI Draftsman will generate this).
* Set the `vendor`, `productName`, and `productVersion` parameters.
* Specify `classification` (e.g., `operating-system`, `compute-platform`, `software`, or `agent`).
* Map `capabilities` to document which architectural functions this product satisfies out-of-the-box (e.g. satisfy `secrets-management` or `apm`).

### Step 2: Model the Reusable Substrate or Host
If your team provisions standard VM images or server profiles, author a `Host` YAML file in `catalog/shared-services/hosts/`:
* Reference the exact `operatingSystemComponent` and `computePlatformComponent` UIDs you defined in Step 1.
* Declare standard platform agents (e.g. monitoring agents, security software) in `agentComponents`.
* Set `requirementGroups` to map the Host to standard workspace security profiles (e.g. `requirement-group-host`).
* **Important:** Link the component to your team ID by setting the `owner.team` property (e.g. `owner.team: database-services`).

### Step 3: Define Shared Runtimes & Data Stores
Model the actual execution environments that Engineering product teams will deploy their code onto. Author a `RuntimeService` or `DataStoreService` YAML file in their respective subfolders:
* Reference the `host` substrate defined in Step 2.
* Define `deliveryModel` (`saas`, `paas`, `appliance`, or `self-managed`) to capture who operates the platform.
* For `DataStoreService` entries, explicitly document the data protection features (e.g. backup strategies, RTO, and RPO expectations).

---

## 4. Platform Mapping & Capability Governance

* **Bridging Capabilities to Tech**: As a Shared Services lead, you are responsible for keeping DRAFT's capability mapping current. In your company configuration overlay (`configurations/object-patches/`), you will author deep-merge patches mapping core platform capabilities (such as APM or Secrets Management) to your approved, active TechnologyComponents. This is what enables Engineering teams' ProductComponents to validate cleanly when they reference standard substrates.
* **Progressive Onboarding**: When creating new infrastructure profiles, start with `catalogStatus: stub` or `catalogStatus: incomplete`. This allows you to check in skeletal drafts without failing validation, letting your AI Draftsman help you enrich them later.
* **Automated Code Validation**: Run `/draft validate` in your AI chat window before opening any pull request to verify that all cross-references between hosts, substrates, and technologies are completely intact and resolve cleanly.

For detailed guidelines on issue ticketing, lifecycle states, standard dispositions, and CODEOWNERS review routing, see the [Draft Operations Guide](operations-guide.md).
