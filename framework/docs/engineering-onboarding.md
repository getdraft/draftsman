# Engineering Onboarding Guide

> **Audience:** Product Developers, Tech Leads, and Software Architects.
> This guide is a quick tutorial to help product teams onboard and document their first application architecture in a DRAFT workspace.

---

## 1. Overview of the Engineering Layer

As an Engineering representative, you are accountable for the **engineering layer** of the architecture catalog. You own the software and data structures that define your product's boundaries. 

The Engineering layer comprises three core object types inside `catalog/engineering/`:
1. **ProductComponent** (`product-components/`): Represents a distinct, first-party runtime behavior (e.g. a microservice, web app, backend process, or job) that you deploy on a substrate.
2. **DataComponent** (`data-components/`): Represents a first-party data asset, table, collection, or database schema.
3. **SoftwareDeploymentPattern** (`software-deployment-patterns/`): Declares the complete, intended product deployment architecture (representing how your ProductComponents, DataComponents, and third-party services are grouped and organized).

```text
catalog/engineering/
  product-components/            ← Microservices, APIs, Background Workers
  data-components/               ← Database schemas, Datasets, PII assets
  software-deployment-patterns/  ← Product deployment diagrams and layouts
```

For ongoing operating standards, ticketing, routing, and Pull Request reviews, refer directly to the central [Draft Operations Guide](operations-guide.md).

---

## 2. Your First Action: Connect Your AI Assistant

DRAFT is Git-native and repo-first. You do not need to install local CLI tools. You interact with DRAFT using the AI assistant connected to your repository workspace. 

Copy the prompt below and paste it into your AI assistant chat window to start a session:

```text
I need a draftsman. Open a drafting session to document my new product service.
```

Your AI assistant will immediately assume the **Draftsman** role, read your workspace configuration, and guide you through the process step-by-step.

---

## 3. Modeling Your Software

To document a service or application correctly, follow the three-tiered modeling sequence:

### Step 1: Create a ProductComponent
For every microservice or runtime process, author a `ProductComponent` YAML file in `catalog/engineering/product-components/`:
* Define a unique `uid` (your AI Draftsman will generate this).
* Set `repoUrl` pointing to your service repository.
* Specify `classification` (e.g., `service`, `web-application`, `background-worker`).
* Declare network boundaries (`networkBindings`) and configuration dependencies.
* Use `runtimeSpec.ports` for service-owned listener or egress port metadata, and `runtimeSpec.dependencies` for simple runtime dependencies the component consumes without asking Shared Services to edit the underlying RuntimeService.
* **Important:** Link the component to your team ID by setting the `owner.team` property (e.g., `owner.team: billing-team`).

### Step 2: Create a DataComponent (If your service owns data)
If your service owns a database table, queue, or dataset, author a `DataComponent` YAML file in `catalog/engineering/data-components/`:
* Specify the `targetEngine` (e.g. `postgres`, `dynamodb`).
* Declare data governance markers: set `dataClassification` (e.g., `internal`, `confidential`) and `containsPII` (`true`/`false`).
* Bind it to the host or service it runs on using the `runsOn` reference.

### Step 3: Define Your SoftwareDeploymentPattern (SDP)
The SDP is your product's "architectural blueprint." It binds your ProductComponents and DataComponents together:
* Place the file in `catalog/engineering/software-deployment-patterns/`.
* Group your components and databases into logical deployment tiers using `serviceGroups` (e.g., `presentation`, `application`, `data`).
* Declare which `ReferenceArchitecture` your pattern aligns with using the `followsReferenceArchitecture` property (e.g., `ra-three-tier-web`).

---

## 4. Operational Best Practices

* **Active Ownership:** Every engineering file you create **must** have your team ID mapped under `owner.team` matching the approved workspace team registry. Missing team mappings will trigger validation failures on complete objects.
* **Incremental Drafting:** When starting a new design, set `catalogStatus: stub` or `catalogStatus: incomplete`. The validator will output warnings for incomplete evidence but will allow you to merge skeletal files so they are visible.
* **Resolve Gaps Programmatically:** Run `/draft validate` in your AI chat window to check your local changes before opening a pull request. The validator will analyze your schemas, cross-references, and platform dependencies, highlighting exact repair steps if warnings or errors are found.
* **Justify Exceptions Cleanly:** If your product deviates from standard platform rules (e.g. running a non-standard database), add clear architectural reasoning inside the object's `architectureNotes` field. The Draftsman will read these notes and use them to satisfy platform RequirementGroup compliance checks automatically during reviews.

For detailed guidelines on issue ticketing, lifecycle states, standard dispositions, and CODEOWNERS review routing, see the [Draft Operations Guide](operations-guide.md).
