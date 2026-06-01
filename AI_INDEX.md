# AI Framework Index

This generated file gives AI assistants a fast map of the DRAFT framework checkout.
It is intentionally framework-first: this upstream repository is a reusable template,
not a complete company architecture catalog. Organization-specific architecture content
belongs in private company DRAFT repos that vendor this framework under `.draft/framework/`.

Regenerate with:

```bash
python3 framework/tools/generate_ai_index.py
```

## Draftsman Bootstrap

When a user says "I need a draftsman", the AI should immediately assume the
Draftsman role defined in `framework/docs/draftsman.md`, then use this index,
the selected framework schemas/configurations, provider packs, and workspace YAML to guide the conversation and edits.

## Framework Entrypoints

| Path | Purpose |
|---|---|
| AGENTS.md | Canonical AI bootstrap instructions for this repository. |
| draft-framework.yaml | Machine-readable DRAFT Framework version and compatibility manifest. |
| ROADMAP.md | v1.0 readiness roadmap and canonical MVP work items. |
| VERSIONING.md | Framework semantic versioning and compatibility policy. |
| CHANGELOG.md | Required release notes for every framework release. |
| RELEASE.md | Release checklist for version, changelog, validation, and publishing steps. |
| pyproject.toml | Python packaging metadata for experimental post-v1.0 local tooling. |
| draft_table | Experimental local DRAFT Table app prototype; not required for the v1.0 repo-first workflow. |
| framework/browser | Static browser shell, CSS, JavaScript, and default theme assets copied by generate_browser.py. |
| security.md | Credential and local security boundary notes for optional local tooling. |
| framework/docs/draftsman.md | Draftsman role, intent routing, and authoring rules. |
| framework/docs/setup-mode.md | Draftsman first-run setup mode and guided interview cadence. |
| framework/docs/engineering-onboarding.md | Targeted onboarding tutorial for product engineering teams. |
| framework/docs/shared-services-onboarding.md | Targeted onboarding tutorial for platform/shared services teams. |
| framework/docs/draft-admins-onboarding.md | Targeted onboarding tutorial for workspace administrators. |
| framework/docs/company-vocabulary.md | Optional company vocabulary lists, advisory/gated validation, and proposal flow. |
| framework/docs/overview.md | Framework concepts and object family overview. |
| framework/docs/object-types.md | User-facing DRAFT object type taxonomy and deployable/non-deployable distinction. |
| framework/docs/delivery-models.md | Delivery model meanings for self-managed, PaaS, SaaS, and appliance services. |
| framework/docs/yaml-schema-reference.md | Quick map from object families to schemas. |
| framework/docs/how-to-add-objects.md | Practical object authoring workflow. |
| framework/docs/workspaces.md | Private workspace layout and source-based workflow. |
| framework/docs/requirement-groups.md | Unified requirement group authoring and validation behavior. |
| framework/docs/capabilities.md | Capability object model and implementation lookup behavior. |
| framework/docs/drafting-sessions.md | How to persist incomplete authoring work. |
| framework/tools/validate.py | Executable validation for schemas, RequirementGroups, capabilities, and references. |
| framework/tools/apply_vocabulary_proposals.py | Materializes Draftsman vocabulary_proposal files into reviewable company vocabulary entries. |
| framework/tools/repair_uids.py | Explicit repair utility that adds or replaces generated object UIDs and rewrites object references. |
| framework/tools/generate_browser.py | Static GitHub Pages browser generator. |
| framework/tools/migrations/0.36.1/migrate_to_nested_catalog.py | Automated utility to migrate flat catalog directories under catalog/ to role-nested paths. |
| install-draft-table.sh | Experimental local tooling installer retained for post-v1.0 work. |

## Framework Docs

| Path | Title | Summary |
|---|---|---|
| framework/docs/capabilities.md | Capabilities | A Capability is a first-class framework object that names an architecture |
| framework/docs/company-vocabulary.md | Company Vocabulary | Company vocabulary lists are optional governed lists in `.draft/workspace.yaml`. |
| framework/docs/decision-records.md | DecisionRecords | DecisionRecords are first-class records for known risks, |
| framework/docs/delivery-models.md | Delivery Models | Delivery models explain how a deployable service is operated. They apply to |
| framework/docs/design-principles.md | Design Principles | DRAFT is opinionated. These principles explain the reasoning behind the |
| framework/docs/draft-admins-onboarding.md | Draft Admins Onboarding Guide | > **Audience:** Workspace Administrators, Enterprise Architects, and Devops Leads. |
| framework/docs/drafting-sessions.md | DraftingSessions | A DraftingSession is a machine-readable record of partial architecture work. |
| framework/docs/draftsman-ai-configuration.md | Draftsman AI Guidance | DRAFT does not include a built-in AI runtime. The Draftsman is an external AI |
| framework/docs/draftsman.md | Draftsman Instructions | The Draftsman is an AI architecture-authoring agent for DRAFT. It interviews the |
| framework/docs/engineering-onboarding.md | Engineering Onboarding Guide | > **Audience:** Product Developers, Tech Leads, and Software Architects. |
| framework/docs/exporters.md | DRAFT Exporters | DRAFT catalogs are authoritative YAML — the source of truth for architecture |
| framework/docs/how-to-add-objects.md | How To Add Objects | The fastest way to add a new object correctly is to decide what kind of thing you are modeling before you write YAML. |
| framework/docs/naming-conventions.md | Naming Conventions | When a DRAFT object type is referred to by name in prose, headings, schema |
| framework/docs/object-types.md | DRAFT Object Types | DRAFT object types are split into deployable architecture and non-deployable |
| framework/docs/operations-guide.md | Draft Operations Guide | > **Audience:** Draft Admins, Shared Services, and Engineering Representatives. |
| framework/docs/overview.md | Framework Overview | This page is the high-level object map for DRAFT. For the complete object type |
| framework/docs/reference-architectures.md | ReferenceArchitectures | The DRAFT framework ships a set of baseline ReferenceArchitectures in |
| framework/docs/requirement-groups.md | RequirementGroups | A RequirementGroup is the unified DRAFT requirement model. It replaces the old |
| framework/docs/roles-and-layers.md | Roles and Layers | DRAFT recognizes three roles. Each role owns a different layer of the catalog |
| framework/docs/sdp-completion-interview.md | SDP Completion Interview | The SDP Completion Interview is a structured protocol for enriching an existing |
| framework/docs/security-and-compliance-controls.md | Security And Compliance RequirementGroups | DRAFT treats compliance as an explicitly activated authoring and validation layer. |
| framework/docs/setup-mode.md | Draftsman Setup Mode | > **Audience: Draft Admins only.** |
| framework/docs/shared-services-onboarding.md | Shared Services Onboarding Guide | > **Audience:** Platform Engineers, Infrastructure Leads, Security Architects, and Database Administrators. |
| framework/docs/software-deployment-patterns.md | SoftwareDeploymentPatterns | A SoftwareDeploymentPattern is a declaration that a specific product is intended |
| framework/docs/standards.md | Deployable Objects | DRAFT previously used the word "Standard" for reusable deployable building |
| framework/docs/technology-components.md | TechnologyComponents | A TechnologyComponent is a discrete vendor product object. It records one |
| framework/docs/ticketing.md | Ticketing and Issue Creation Workflow | > **Audience:** Draft Admins, Shared Services, and Engineering Representatives. |
| framework/docs/user-manual.md | DRAFT User Manual | DRAFT is an AI-first, Git-native, repo-first framework for documenting governed architecture. It turns architecture c... |
| framework/docs/workspaces.md | Workspaces | For the full adoption sequence from installation through first drafting sessions, see the role-specific onboarding tu... |
| framework/docs/yaml-schema-reference.md | YAML Schema Reference | This page is the quickest way to understand how to build a valid YAML object in |

## Schemas

| Path | Scope | Required Fields |
|---|---|---|
| framework/schemas/capability.schema.yaml | capability | schemaVersion, uid, type, name, description, catalogStatus, definitionOwner, domain, implementations |
| framework/schemas/data-component.schema.yaml | data_component | schemaVersion, uid, type, name, repoUrl, owner, runsOn, targetEngine, dataClassification, containsPII, catalogStatus |
| framework/schemas/data-store-service.schema.yaml | data_store_service | schemaVersion, uid, type, name, deliveryModel, catalogStatus, lifecycleStatus |
| framework/schemas/decision-record.schema.yaml | decision_record | schemaVersion, uid, type, name, category, status, catalogStatus, lifecycleStatus |
| framework/schemas/deployment-target.schema.yaml | deployment_target | schemaVersion, uid, type, name, environmentTier, targetProvider, parameters, catalogStatus |
| framework/schemas/domain.schema.yaml | domain | schemaVersion, uid, type, name, capabilities |
| framework/schemas/drafting-session.schema.yaml | drafting_session | schemaVersion, uid, type, name, catalogStatus, lifecycleStatus, sessionStatus, primaryObjectType, sourceArtifacts, generatedObjects, unresolvedQuestions |
| framework/schemas/environment-tier.schema.yaml | environment_tier | schemaVersion, uid, type, name, tierId, purpose, availabilityExpectation, catalogStatus |
| framework/schemas/host.schema.yaml | host | schemaVersion, uid, type, name, catalogStatus, lifecycleStatus |
| framework/schemas/network-service.schema.yaml | network_service | schemaVersion, uid, type, name, deliveryModel, catalogStatus, lifecycleStatus |
| framework/schemas/object-patch.schema.yaml | object_patch | schemaVersion, uid, type, name, target, patch, catalogStatus, lifecycleStatus |
| framework/schemas/product-component.schema.yaml | product_component | schemaVersion, uid, type, name, repoUrl, owner, classification, catalogStatus |
| framework/schemas/reference-architecture.schema.yaml | reference_architecture | schemaVersion, uid, type, name, catalogStatus, lifecycleStatus |
| framework/schemas/relationship.schema.yaml | relationship | schemaVersion, uid, type, name, source, label, catalogStatus |
| framework/schemas/requirement-group.schema.yaml | requirement_group | schemaVersion, uid, type, name, description, catalogStatus, activation, appliesTo, requirements |
| framework/schemas/runtime-service.schema.yaml | runtime_service | schemaVersion, uid, type, name, deliveryModel, catalogStatus, lifecycleStatus |
| framework/schemas/software-deployment-pattern.schema.yaml | software_deployment_pattern | schemaVersion, uid, type, name, catalogStatus, lifecycleStatus |
| framework/schemas/system.schema.yaml | system | schemaVersion, uid, type, name, catalogStatus, lifecycleStatus |
| framework/schemas/technology-component.schema.yaml | technology_component | schemaVersion, uid, type, name, vendor, productName, productVersion, classification, catalogStatus |

## Base Configurations

These YAML files are framework-owned base configurations. Company workspaces add third-party packs under `.draft/providers/` and company behavior through their private `configurations/` folder while keeping the vendored framework copy under `.draft/framework/` refreshable.

| UID | Name | Type | Tags | Description | Path |
|---|---|---|---|---|---|
| 01KQQ4Q026-4JR6 | Access Control Model | capability |  | Authorization model that controls access to a service or data platform. | framework/configurations/capabilities/capability-access-control-model.yaml |
| 01KT0XNZEY-A7GK | Analytics | capability |  | Operational and business data is processed and analyzed to produce insight through a managed analytics platform. | framework/configurations/capabilities/capability-analytics.yaml |
| 01KT0V5MCV-3A6F | API Gateway | capability |  | Inbound API traffic is routed, authenticated, rate-limited, and transformed at a managed entry point in front of back... | framework/configurations/capabilities/capability-api-gateway.yaml |
| 01KQQ4Q026-NB1W | Application Performance Monitoring | capability |  | Tracing and performance analysis of application runtimes. | framework/configurations/capabilities/capability-apm.yaml |
| 01KT0V5MCV-RZV0 | Application Runtime | capability |  | First-party application code executes on a managed runtime that provides the process, web, or worker execution enviro... | framework/configurations/capabilities/capability-application-runtime.yaml |
| 01KT0XNZEY-7HWQ | Artifact Management | capability |  | Build outputs, packages, images, and dependencies are stored, versioned, and served from a managed artifact repository. | framework/configurations/capabilities/capability-artifact-management.yaml |
| 01KQQ4Q026-MHJM | Authentication | capability |  | Identity and access authentication capability for users, services, administrators, or workloads. | framework/configurations/capabilities/capability-authentication.yaml |
| 01KT0V5MCV-ECR4 | Caching | capability |  | Frequently accessed data is stored in a fast, ephemeral tier to reduce latency and load on the system of record. | framework/configurations/capabilities/capability-caching.yaml |
| 01KT0V5MCV-HZ37 | CDN | capability |  | Static and cacheable content is distributed and served from edge locations close to consumers to reduce latency and o... | framework/configurations/capabilities/capability-cdn.yaml |
| 01KT0XNZEY-RVTG | Certificate Management | capability |  | Digital certificates are issued, distributed, renewed, and revoked through a managed certificate or PKI service. | framework/configurations/capabilities/capability-certificate-management.yaml |
| 01KT0XNZEY-Q2TF | CI/CD Pipeline | capability |  | Source code is automatically built, tested, and promoted through environments by an automated continuous integration... | framework/configurations/capabilities/capability-cicd-pipeline.yaml |
| 01KQQ4Q026-1HZP | Compute Platform | capability |  | Compute substrate or virtualized platform used to run Hosts. | framework/configurations/capabilities/capability-compute-platform.yaml |
| 01KT0XNZEY-35Y2 | Configuration Management | capability |  | System and application configuration is declared, applied, and reconciled across environments through a managed confi... | framework/configurations/capabilities/capability-configuration-management.yaml |
| 01KQQ4Q026-GW5D | Container Orchestration | capability |  | Management of containerized workload lifecycles. | framework/configurations/capabilities/capability-container-orchestration.yaml |
| 01KT0XNZEY-DENJ | Data Integration | capability |  | Data is moved, transformed, and synchronized between systems through a managed integration or ETL platform. | framework/configurations/capabilities/capability-data-integration.yaml |
| 01KT0V5MCV-VD0Y | Data Persistence | capability |  | Structured application data is durably stored, queried, and managed in a database or persistence platform. | framework/configurations/capabilities/capability-data-persistence.yaml |
| 01KQQ4Q026-7T2H | Data Resilience | capability |  | Resilience of data against loss or corruption through backup, restore, replication, and recovery capabilities. | framework/configurations/capabilities/capability-data-resilience.yaml |
| 01KT0V5MCV-GJBH | DNS | capability |  | Names are resolved to network addresses through authoritative and recursive domain name resolution. | framework/configurations/capabilities/capability-dns.yaml |
| 01KT0XNZEY-KPTW | Email Delivery | capability |  | Outbound and transactional email is accepted, routed, and delivered to recipients through a managed mail delivery ser... | framework/configurations/capabilities/capability-email-delivery.yaml |
| 01KQQ4Q026-H3B5 | Encryption At Rest | capability |  | Protection of persisted data through encryption or equivalent storage safeguards. | framework/configurations/capabilities/capability-encryption-at-rest.yaml |
| 01KT0V5MCV-924J | File Storage | capability |  | Files are durably stored and accessed through a shared file system or file storage interface. | framework/configurations/capabilities/capability-file-storage.yaml |
| 01KT0XNZEY-K1J3 | File Transfer | capability |  | Files are exchanged between systems or partners reliably and securely through a managed file transfer service. | framework/configurations/capabilities/capability-file-transfer.yaml |
| 01KQQ4Q026-98VD | Health and Welfare Monitoring | capability |  | Runtime health, uptime, metrics, and operational welfare visibility. | framework/configurations/capabilities/capability-health-welfare-monitoring.yaml |
| 01KQQ4Q026-D04B | Log Management | capability |  | Aggregation, retention, searchability, and forwarding of system or application logs. | framework/configurations/capabilities/capability-log-management.yaml |
| 01KT0V5MCV-KT72 | Messaging | capability |  | Asynchronous messages and events are accepted, queued, and delivered between producers and consumers. | framework/configurations/capabilities/capability-messaging.yaml |
| 01KSWVZSZ5-Q6HW | Network Connectivity | capability |  | Hosts and services can reach each other across the network fabric through approved switching and routing infrastructure. | framework/configurations/capabilities/capability-network-connectivity.yaml |
| 01KSWVZSZ5-1RTH | Network Segmentation | capability |  | Traffic between network zones is isolated and controlled by policy through VLANs, micro-segmentation, or software-def... | framework/configurations/capabilities/capability-network-segmentation.yaml |
| 01KT0V5MCV-E9TN | Object Storage | capability |  | Unstructured objects and blobs are durably stored and retrieved through an object storage interface. | framework/configurations/capabilities/capability-object-storage.yaml |
| 01KQQ4Q026-QM2X | Operating System | capability |  | Supported operating system product used to define managed Hosts. | framework/configurations/capabilities/capability-operating-system.yaml |
| 01KQQ4Q026-BH6E | Patch Management | capability |  | Patch orchestration and update application capability for managed runtime components. | framework/configurations/capabilities/capability-patch-management.yaml |
| 01KQQ4Q026-S5J6 | Performance and Load Testing | capability |  | Capabilities to simulate load and measure system behavior under stress. | framework/configurations/capabilities/capability-performance-testing.yaml |
| 01KQQ4Q026-RTWC | Quality Gates | capability |  | Promotion criteria and automated checks required for lifecycle transitions. | framework/configurations/capabilities/capability-quality-gates.yaml |
| 01KT0XNZEY-70Y6 | Reporting | capability |  | Curated metrics and datasets are presented to consumers through managed reports and dashboards. | framework/configurations/capabilities/capability-reporting.yaml |
| 01KQQ4Q026-DTJJ | Secrets Management | capability |  | Secure storage, rotation, and access mediation for secrets and authenticators. | framework/configurations/capabilities/capability-secrets-management.yaml |
| 01KQQ4Q026-JW52 | Security Monitoring | capability |  | Threat detection, intrusion detection, security event monitoring, and audit telemetry. | framework/configurations/capabilities/capability-security-monitoring.yaml |
| 01KQQ4Q026-3ZWJ | Serverless Function Runtime | capability |  | Event-driven, scale-to-zero compute runtime capability. | framework/configurations/capabilities/capability-serverless-runtime.yaml |
| 01KT0V5MCV-RM8M | Service Mesh | capability |  | Service-to-service traffic is routed, secured, and observed through a dedicated connectivity and policy layer. | framework/configurations/capabilities/capability-service-mesh.yaml |
| 01KQQ4Q026-QC9S | Test Authoring | capability |  | Tools and frameworks used to author automated tests. | framework/configurations/capabilities/capability-test-authoring.yaml |
| 01KQQ4Q026-58Q3 | Test Execution and Automation | capability |  | Runtimes and orchestration services used to execute automated tests. | framework/configurations/capabilities/capability-test-execution.yaml |
| 01KSWVZSZ5-M0FR | Traffic Management | capability |  | Application and network traffic is distributed, shaped, and controlled across services and infrastructure through app... | framework/configurations/capabilities/capability-traffic-management.yaml |
| 01KT0V5MCV-Z079 | WAF | capability |  | Inbound web traffic is inspected and filtered against application-layer threats through managed rule sets before reac... | framework/configurations/capabilities/capability-waf.yaml |
| 01KSWVZSZ5-26F1 | WAN Connectivity | capability |  | Sites, data centers, and cloud environments are interconnected reliably through approved wide area network technology. | framework/configurations/capabilities/capability-wan-connectivity.yaml |
| 01KQQ4Q027-DSDD | Appliance Delivery RequirementGroup | requirement_group | appliance, requirement-group, definition | Structured requirements used when a Runtime, Data Store, or NetworkService uses appliance delivery and the underlying... | framework/configurations/requirement-groups/requirement-group-appliance-delivery.yaml |
| 01KRWRRNM7-VJ5A | DataComponent RequirementGroup | requirement_group | data-component, requirement-group, definition | Built-in checklist for first-party data artifacts deployed onto DataStoreServices. Establishes what must be known abo... | framework/configurations/requirement-groups/requirement-group-data-component.yaml |
| 01KQQ4Q027-VBF0 | DataStoreService RequirementGroup | requirement_group | service, dbms, requirement-group, definition | Additional DataStoreService checklist items extending the service behavior RequirementGroup for durable data, recover... | framework/configurations/requirement-groups/requirement-group-data-store-service.yaml |
| 01KQQ4Q027-69VY | NIST Cybersecurity Framework RequirementGroup | requirement_group | compliance, nist, starter-pack, requirement-group | Initial NIST Cybersecurity Framework (CSF) 2.0 requirement group scoped to the outcomes that can be meaningfully answ... | framework/configurations/requirement-groups/requirement-group-draft-nist-csf.yaml |
| 01KQQ4Q027-T3CA | Security and Security Compliance RequirementGroup | requirement_group | compliance, controls, baseline, requirement-group | Baseline security and compliance requirement group bundled with DRAFT. Requirements are applied to matching object ty... | framework/configurations/requirement-groups/requirement-group-draft-security-compliance.yaml |
| 01KQQ4Q027-7JN2 | SOC 2 RequirementGroup | requirement_group | compliance, soc2, starter-pack, requirement-group | Initial SOC 2 requirement group based on the AICPA Trust Services Criteria. These requirements use DRAFT applicabilit... | framework/configurations/requirement-groups/requirement-group-draft-soc2.yaml |
| 01KQQ4Q027-1GHC | TX-RAMP RequirementGroup | requirement_group | compliance, tx-ramp, starter-pack, requirement-group | Starter TX-RAMP requirement group for DRAFT. This file is intended to map TX-RAMP control expectations onto the unifi... | framework/configurations/requirement-groups/requirement-group-draft-tx-ramp.yaml |
| 01KQQ4Q027-HHA4 | DraftingSession RequirementGroup | requirement_group | drafting-session, requirement-group, intake | Structured checklist used to capture partial architecture-authoring sessions, generated outputs, and unresolved follo... | framework/configurations/requirement-groups/requirement-group-drafting-session.yaml |
| 01KSF4NHSP-8HPP | Engineering Quality RequirementGroup | requirement_group | product-component, requirement-group, engineering, quality, optional | Optional checklist for ProductComponents covering build quality, test coverage, and performance validation practices.... | framework/configurations/requirement-groups/requirement-group-engineering-quality.yaml |
| 01KSF4NHSP-HCPX | Host Compute Profile RequirementGroup | requirement_group | host, requirement-group, compute, optional | Optional checklist for Hosts covering compute type classification. Activated per workspace; does not fire automatically. | framework/configurations/requirement-groups/requirement-group-host-compute-profile.yaml |
| 01KQQ4Q027-THYN | Host RequirementGroup | requirement_group | host, requirement-group, definition | Structured checklist of required questions and answers used to define a complete and correct Host. | framework/configurations/requirement-groups/requirement-group-host.yaml |
| 01KSWVZSZ5-B146 | NetworkService RequirementGroup | requirement_group | network, requirement-group, definition | Base requirements for NetworkService objects covering network function declaration, topology definition, and protocol... | framework/configurations/requirement-groups/requirement-group-network-service.yaml |
| 01KQQ4Q027-TPWG | PaaS Delivery RequirementGroup | requirement_group | paas, requirement-group, definition | Structured requirements used when a Runtime, Data Store, or NetworkService is vendor-managed inside the organization'... | framework/configurations/requirement-groups/requirement-group-paas-delivery.yaml |
| 01KRWRRNM7-G642 | ProductComponent RequirementGroup | requirement_group | product-component, requirement-group, definition | Built-in checklist for first-party code components deployed onto RuntimeServices. Establishes what must be known abou... | framework/configurations/requirement-groups/requirement-group-product-component.yaml |
| 01KQQ4Q027-SS2K | ReferenceArchitecture RequirementGroup | requirement_group | reference-architecture, requirement-group, definition | Structured checklist of required questions and answers used to define a complete and correct ReferenceArchitecture. | framework/configurations/requirement-groups/requirement-group-reference-architecture.yaml |
| 01KQQ4Q027-K5DR | Service Behavior RequirementGroup | requirement_group | service, requirement-group, definition | Structured checklist of required questions and answers used to define complete and correct self-managed Runtime and N... | framework/configurations/requirement-groups/requirement-group-runtime-service.yaml |
| 01KQQ4Q027-FKRM | SaaS Delivery RequirementGroup | requirement_group | saas, requirement-group, definition | Structured requirements used when a Runtime, Data Store, or NetworkService is consumed as a vendor-managed external s... | framework/configurations/requirement-groups/requirement-group-saas-delivery.yaml |
| 01KT0VM061-CRN7 | Service Capability RequirementGroup | requirement_group | service, capability, requirement-group, definition | Self-declared capability requirements for shared service objects. When a RuntimeService, DataStoreService, or Network... | framework/configurations/requirement-groups/requirement-group-service-capability.yaml |
| 01KSF29JTP-SRVE | Service Engineering Practices RequirementGroup | requirement_group | service, requirement-group, engineering, optional | Optional checklist for self-managed Runtime and NetworkServices covering advanced observability and runtime patterns.... | framework/configurations/requirement-groups/requirement-group-service-engineering.yaml |
| 01KQQ4Q027-VK45 | SoftwareDeploymentPattern RequirementGroup | requirement_group | software-deployment-pattern, requirement-group, definition | Structured checklist of required questions and answers used to define a complete and correct software deployment patt... | framework/configurations/requirement-groups/requirement-group-software-deployment-pattern.yaml |
| 01KS8N4KR3-MTSA | Multi-Tenant SaaS | reference_architecture | reference-architecture, multi-tenant, saas | Deployment pattern for software-as-a-service products that serve multiple customer tenants from shared infrastructure... | framework/configurations/reference-architectures/ra-multi-tenant-saas.yaml |
| 01KS8N4KR4-SVED | Serverless Event-Driven | reference_architecture | reference-architecture, serverless, event-driven | Deployment pattern for event-driven applications using serverless compute runtimes. No persistent application-tier co... | framework/configurations/reference-architectures/ra-serverless-event-driven.yaml |
| 01KS8N4KR2-3TWA | Three-Tier Web Application | reference_architecture | reference-architecture, three-tier, web | Standard pattern for web-facing applications with a presentation tier (network services), an application tier (runtim... | framework/configurations/reference-architectures/ra-three-tier-web.yaml |
| 01KT0XNZEY-HGZZ | Analytics | domain |  | Strategic domain covering analytical processing and reporting over operational and business data. Capabilities in thi... | framework/configurations/domains/analytics.yaml |
| 01KQQ4Q027-ZTHF | Compute & Runtime | domain |  | Strategic domain covering application runtimes, serverless functions, and physical or virtual compute resources. | framework/configurations/domains/compute.yaml |
| 01KSWVZSZ5-QHKZ | Data | domain |  | Strategic domain covering data protection and resilience. Capabilities in this domain are governed by the data and st... | framework/configurations/domains/data.yaml |
| 01KSWVZSZ5-71PY | Identity & Access Management | domain |  | Strategic domain covering authentication and authorization. Capabilities in this domain are governed by the IAM team,... | framework/configurations/domains/identity.yaml |
| 01KT0XNZEY-QY0Y | Integration | domain |  | Strategic domain covering the movement of messages, files, and data between systems. Capabilities in this domain are... | framework/configurations/domains/integration.yaml |
| 01KSWVZSZ5-4WKE | Network | domain |  | Strategic domain covering network fabric infrastructure, connectivity, and segmentation. Capabilities in this domain... | framework/configurations/domains/network.yaml |
| 01KQQ4Q027-C213 | Observability & Monitoring | domain |  | Strategic domain covering logging, metrics, tracing, and health monitoring across infrastructure and application stacks. | framework/configurations/domains/observability.yaml |
| 01KSWVZSZ5-GY67 | Security | domain |  | Strategic domain covering threat detection, security event monitoring, and secure credential management. Capabilities... | framework/configurations/domains/security.yaml |
| 01KT0XNZEY-GXYR | Software Delivery | domain |  | Strategic domain covering the build, integration, packaging, and configuration pipeline that delivers software into r... | framework/configurations/domains/software-delivery.yaml |
| 01KQQ4Q027-SGHR | Testing & Quality | domain |  | Strategic domain covering all aspects of software testing, quality assurance, and release gates. | framework/configurations/domains/testing.yaml |

## Example Catalog Inventory

These are sample catalog objects used to validate and demonstrate the framework. Company-specific content belongs in a private company `catalog/` folder.

| UID | Name | Type | Tags | Description | Path |
|---|---|---|---|---|---|
| 01KSE5V73Z-Q0A0 | OpenStack Ops Console | product_component | product-component, openstack, operations, internal-tooling | Internal web-based operations console for platform engineering teams. Surfaces real-time service health, quota utiliz... | examples/catalog/engineering/product-components/product-component-openstack-ops-console.yaml |
| 01KSE5V73Z-RTKZ | Platform Audit Schema | data_component | data-component, openstack, audit, compliance | Relational schema tracking platform-level audit events — control plane API calls, administrative actions, quota chang... | examples/catalog/engineering/data-components/data-component-platform-audit-schema.yaml |
| STCK000001-SDP1 | OpenStack IaaS Platform | software_deployment_pattern | software-deployment-pattern, openstack, iaas, cloud, platform | Full-stack self-managed OpenStack Infrastructure-as-a-Service deployment pattern covering the complete control plane... | examples/catalog/engineering/software-deployment-patterns/sdp-openstack-iaas-platform.yaml |
| STCK00000F-HS0F | OpenStack Linux Service Host | host | host, openstack, linux | General-purpose self-managed Linux host standard for the OpenStack example control-plane, data, and utility services.... | examples/catalog/shared-services/hosts/host-openstack-linux-service-host.yaml |
| 01KQQ4Q025-1XDE | AWS Lambda Serverless Host | host | lambda, serverless | Serverless execution environment provided by AWS Lambda. The host is entirely AWS-managed and blackbox to the organiz... | examples/catalog/shared-services/hosts/host-serverless-lambda.yaml |
| 01KQQ4Q025-T7B7 | AWS Lambda Runtime | runtime_service | serverless, lambda | AWS Lambda serverless execution environment. Runs organization-authored function code without requiring host manageme... | examples/catalog/shared-services/runtime-services/runtime-service-aws-lambda-runtime.yaml |
| STCK000008-RS08 | Ceilometer Telemetry Service | runtime_service | runtime-service, openstack, telemetry, ceilometer, metering, iaas | Self-managed deployment of OpenStack Ceilometer providing metering and telemetry data collection across the OpenStack... | examples/catalog/shared-services/runtime-services/runtime-service-ceilometer.yaml |
| STCK000005-RS05 | Cinder Block Storage Service | runtime_service | runtime-service, openstack, block-storage, cinder, iaas | Self-managed deployment of OpenStack Cinder providing persistent block storage volumes for compute instances. Runs ci... | examples/catalog/shared-services/runtime-services/runtime-service-cinder.yaml |
| STCK000003-RS03 | Glance Image Service | runtime_service | runtime-service, openstack, image, glance, iaas | Self-managed deployment of OpenStack Glance providing virtual machine image storage and retrieval. Runs glance-api an... | examples/catalog/shared-services/runtime-services/runtime-service-glance.yaml |
| STCK000007-RS07 | Heat Orchestration Service | runtime_service | runtime-service, openstack, orchestration, heat, iaas | Self-managed deployment of OpenStack Heat providing infrastructure orchestration via the Heat Orchestration Template... | examples/catalog/shared-services/runtime-services/runtime-service-heat.yaml |
| STCK000006-RS06 | Horizon Dashboard | runtime_service | runtime-service, openstack, dashboard, horizon, web-ui, iaas | Self-managed deployment of OpenStack Horizon providing the web-based management dashboard for the OpenStack platform.... | examples/catalog/shared-services/runtime-services/runtime-service-horizon.yaml |
| STCK000009-RS09 | Ironic Bare Metal Service | runtime_service | runtime-service, openstack, bare-metal, ironic, iaas | Self-managed deployment of OpenStack Ironic providing bare metal provisioning as a service. Runs ironic-api and ironi... | examples/catalog/shared-services/runtime-services/runtime-service-ironic.yaml |
| STCK000002-RS02 | Keystone Identity Service | runtime_service | runtime-service, openstack, identity, auth, keystone, iaas | Self-managed deployment of OpenStack Keystone providing identity, authentication, and authorization services for all... | examples/catalog/shared-services/runtime-services/runtime-service-keystone.yaml |
| STCK000004-RS04 | Neutron Networking Service | runtime_service | runtime-service, openstack, networking, neutron, sdn, iaas | Self-managed deployment of OpenStack Neutron providing software-defined networking for the OpenStack platform. Runs n... | examples/catalog/shared-services/runtime-services/runtime-service-neutron.yaml |
| STCK000001-RS01 | Nova Compute Service | runtime_service | runtime-service, openstack, compute, nova, iaas | Self-managed deployment of OpenStack Nova providing virtual machine lifecycle management across the platform. Runs no... | examples/catalog/shared-services/runtime-services/runtime-service-nova.yaml |
| STCK00000D-RS0D | RabbitMQ Message Broker Service | runtime_service | runtime-service, messaging, amqp, rabbitmq, iaas | Self-managed deployment of RabbitMQ serving as the shared AMQP message broker for the OpenStack control plane. Provid... | examples/catalog/shared-services/runtime-services/runtime-service-rabbitmq.yaml |
| STCK00000B-RS0B | Sahara Data Processing Service | runtime_service | runtime-service, openstack, data-processing, sahara, hadoop, iaas | Self-managed deployment of OpenStack Sahara providing data processing cluster orchestration on OpenStack. Runs sahara... | examples/catalog/shared-services/runtime-services/runtime-service-sahara.yaml |
| STCK00000C-RS0C | Swift Proxy Service | runtime_service | runtime-service, openstack, object-storage, swift, swift-proxy, iaas | Self-managed deployment of the OpenStack Swift proxy-server providing the API gateway for all object storage operatio... | examples/catalog/shared-services/runtime-services/runtime-service-swift-proxy.yaml |
| STCK00000A-RS0A | Trove Database Service | runtime_service | runtime-service, openstack, database-as-a-service, trove, iaas | Self-managed deployment of OpenStack Trove providing database-as-a-service on top of the OpenStack compute platform.... | examples/catalog/shared-services/runtime-services/runtime-service-trove.yaml |
| STCK000005-DAR5 | Cinder Database | data_store_service | data-at-rest, openstack, cinder, block-storage, database, mariadb, iaas | MariaDB database schema dedicated to OpenStack Cinder for persisting all block storage service state. Stores volume r... | examples/catalog/shared-services/data-store-services/data-store-service-cinder-database.yaml |
| STCK000003-DAR3 | Glance Database | data_store_service | data-at-rest, openstack, glance, image, database, mariadb, iaas | MariaDB database schema dedicated to OpenStack Glance for persisting virtual machine image metadata. Stores image rec... | examples/catalog/shared-services/data-store-services/data-store-service-glance-database.yaml |
| STCK000002-DAR2 | Keystone Database | data_store_service | data-at-rest, openstack, keystone, identity, database, mariadb, iaas | MariaDB database schema dedicated to OpenStack Keystone for persisting all identity service data. Stores users, group... | examples/catalog/shared-services/data-store-services/data-store-service-keystone-database.yaml |
| STCK000004-DAR4 | Neutron Database | data_store_service | data-at-rest, openstack, neutron, networking, database, mariadb, iaas | MariaDB database schema dedicated to OpenStack Neutron for persisting all network service state. Stores virtual netwo... | examples/catalog/shared-services/data-store-services/data-store-service-neutron-database.yaml |
| STCK000001-DAR1 | Nova Database | data_store_service | data-at-rest, openstack, nova, database, mariadb, iaas | MariaDB database schema dedicated to OpenStack Nova for persisting all compute service state. Stores instance records... | examples/catalog/shared-services/data-store-services/data-store-service-nova-database.yaml |
| STCK000007-DAR7 | OpenStack Shared Database | data_store_service | data-at-rest, openstack, heat, ironic, trove, sahara, ceilometer, database, mariadb, iaas | Shared MariaDB database cluster hosting the schemas for OpenStack services that do not warrant dedicated database obj... | examples/catalog/shared-services/data-store-services/data-store-service-openstack-shared-database.yaml |
| STCK000006-DAR6 | Swift Storage Cluster | data_store_service | data-at-rest, openstack, swift, object-storage, iaas | OpenStack Swift object storage cluster providing durable, distributed storage for unstructured data. Consists of mult... | examples/catalog/shared-services/data-store-services/data-store-service-swift-storage-cluster.yaml |
| 01KSF29JTP-9HYA | OpenStack API Load Balancer | network_service | network-service, openstack, load-balancer, haproxy, iaas | HAProxy load balancer co-located on OpenStack controller nodes. Distributes inbound API and dashboard traffic across... | examples/catalog/shared-services/network-services/network-service-openstack-api-lb.yaml |
| 01KQQ4Q025-MQ3F | CrowdStrike Falcon Agent | technology_component | technology-component, agent | Endpoint security agent installed locally on a host that requires communication with the CrowdStrike Falcon platform. | examples/catalog/shared-services/technology-components/technology-agent-crowdstrike-falcon.yaml |
| 01KQQ4Q025-9N4R | Amazon EC2 Standard Compute Platform | technology_component | technology-component, compute-platform | Standard Amazon EC2 virtual machine substrate used for general-purpose host patterns. | examples/catalog/shared-services/technology-components/technology-compute-amazon-ec2-standard.yaml |
| STCK00000F-TC0F | OpenStack Bare Metal Standard Compute Platform | technology_component | technology-component, compute-platform, bare-metal, openstack | Generic bare-metal x86_64 compute substrate used by the OpenStack example service-host patterns. | examples/catalog/shared-services/technology-components/technology-compute-openstack-bare-metal-standard.yaml |
| 01KSF29JTP-8YRX | HAProxy 2.9 | technology_component | technology-component, load-balancer, haproxy, openstack | Open-source TCP/HTTP load balancer and proxy server. Provides high-availability request distribution, health checking... | examples/catalog/shared-services/technology-components/technology-haproxy-29.yaml |
| STCK00000E-TC0E | MariaDB 10.11 | technology_component | technology-component, database, relational, mariadb, iaas | MariaDB 10.11 is the long-term support relational database used as the persistence backend for OpenStack services. Ea... | examples/catalog/shared-services/technology-components/technology-mariadb-1011.yaml |
| STCK000009-TC09 | OpenStack Ceilometer | technology_component | technology-component, openstack, telemetry, monitoring, metering, iaas | OpenStack Ceilometer is the telemetry service for OpenStack. It collects metering and monitoring data from across the... | examples/catalog/shared-services/technology-components/technology-openstack-ceilometer.yaml |
| STCK000005-TC05 | OpenStack Cinder | technology_component | technology-component, openstack, block-storage, iaas | OpenStack Cinder is the block storage service that provides persistent block volumes to Nova compute instances. It in... | examples/catalog/shared-services/technology-components/technology-openstack-cinder.yaml |
| STCK000003-TC03 | OpenStack Glance | technology_component | technology-component, openstack, image, iaas | OpenStack Glance is the image service that stores and retrieves virtual machine disk images. It provides glance-api a... | examples/catalog/shared-services/technology-components/technology-openstack-glance.yaml |
| STCK000008-TC08 | OpenStack Heat | technology_component | technology-component, openstack, orchestration, infrastructure-as-code, iaas | OpenStack Heat is the orchestration service for OpenStack. It implements a heat-api, heat-api-cfn (CloudFormation-com... | examples/catalog/shared-services/technology-components/technology-openstack-heat.yaml |
| STCK000007-TC07 | OpenStack Horizon | technology_component | technology-component, openstack, dashboard, web-ui, iaas | OpenStack Horizon is the web-based dashboard for OpenStack services. It provides a self-service portal for tenants an... | examples/catalog/shared-services/technology-components/technology-openstack-horizon.yaml |
| STCK00000A-TC0A | OpenStack Ironic | technology_component | technology-component, openstack, bare-metal, ironic, iaas | OpenStack Ironic is the bare metal provisioning service. It exposes ironic-api and uses ironic-conductor to manage ph... | examples/catalog/shared-services/technology-components/technology-openstack-ironic.yaml |
| STCK000002-TC02 | OpenStack Keystone | technology_component | technology-component, openstack, identity, auth, iaas | OpenStack Keystone is the identity service providing authentication and authorization for all OpenStack services. It... | examples/catalog/shared-services/technology-components/technology-openstack-keystone.yaml |
| STCK000004-TC04 | OpenStack Neutron | technology_component | technology-component, openstack, networking, sdn, iaas | OpenStack Neutron is the networking service providing software-defined networking capabilities to the OpenStack platf... | examples/catalog/shared-services/technology-components/technology-openstack-neutron.yaml |
| STCK000001-TC01 | OpenStack Nova | technology_component | technology-component, openstack, compute, iaas | OpenStack Nova is the compute service responsible for managing and provisioning virtual machine instances. It include... | examples/catalog/shared-services/technology-components/technology-openstack-nova.yaml |
| STCK00000C-TC0C | OpenStack Sahara | technology_component | technology-component, openstack, data-processing, hadoop, iaas | OpenStack Sahara is the data processing service that automates provisioning of Apache Hadoop and Spark clusters on Op... | examples/catalog/shared-services/technology-components/technology-openstack-sahara.yaml |
| STCK000006-TC06 | OpenStack Swift | technology_component | technology-component, openstack, object-storage, iaas | OpenStack Swift is the object storage service providing highly durable, distributed storage for unstructured data. It... | examples/catalog/shared-services/technology-components/technology-openstack-swift.yaml |
| STCK00000B-TC0B | OpenStack Trove | technology_component | technology-component, openstack, database-as-a-service, dbaas, iaas | OpenStack Trove is the database-as-a-service component. It provides trove-api, trove-conductor, and trove-taskmanager... | examples/catalog/shared-services/technology-components/technology-openstack-trove.yaml |
| 01KQQ4Q025-3HXA | Ubuntu 22.04 LTS | technology_component | technology-component, operating-system | Canonical Ubuntu Server 22.04 LTS operating system product definition for Linux host patterns. | examples/catalog/shared-services/technology-components/technology-os-canonical-ubuntu-2204.yaml |
| STCK00000D-TC0D | RabbitMQ 3.8 | technology_component | technology-component, messaging, amqp, rabbitmq, iaas | RabbitMQ is a widely deployed open-source message broker implementing AMQP. In OpenStack it serves as the shared mess... | examples/catalog/shared-services/technology-components/technology-rabbitmq-38.yaml |
| 01KQQ4Q025-Z042 | nginx 1.26 | technology_component | technology-component, software | nginx web server software installed locally on a managed host and used without a required vendor platform interaction. | examples/catalog/shared-services/technology-components/technology-software-nginx-126.yaml |
| 01KT1340FJ-DCHY | Cinder Database — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-data-store-service-cinder-database-compliance.yaml |
| 01KT11AQV3-ZZFE | Cinder Database — Data Protection and Recovery | decision_record | decision-record, example, data-protection |  | examples/catalog/governance/decision-records/dr-data-store-service-cinder-database-data-protection.yaml |
| 01KT11AQV3-N9NA | Cinder Database — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-data-store-service-cinder-database-identity.yaml |
| 01KT11AQV4-8S2X | Cinder Database — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-data-store-service-cinder-database-observability.yaml |
| 01KT11AQV5-MX8S | Cinder Database — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-data-store-service-cinder-database-resilience.yaml |
| 01KT1340FS-YFWW | Glance Database — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-data-store-service-glance-database-compliance.yaml |
| 01KT11AQVB-JJ2A | Glance Database — Data Protection and Recovery | decision_record | decision-record, example, data-protection |  | examples/catalog/governance/decision-records/dr-data-store-service-glance-database-data-protection.yaml |
| 01KT11AQVB-P0P0 | Glance Database — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-data-store-service-glance-database-identity.yaml |
| 01KT11AQVC-0TX0 | Glance Database — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-data-store-service-glance-database-observability.yaml |
| 01KT11AQVC-DJ9N | Glance Database — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-data-store-service-glance-database-resilience.yaml |
| 01KT1340G0-WH5D | Keystone Database — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-data-store-service-keystone-database-compliance.yaml |
| 01KT11AQVK-CPM7 | Keystone Database — Data Protection and Recovery | decision_record | decision-record, example, data-protection |  | examples/catalog/governance/decision-records/dr-data-store-service-keystone-database-data-protection.yaml |
| 01KT11AQVK-J9EM | Keystone Database — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-data-store-service-keystone-database-identity.yaml |
| 01KT11AQVM-2QCT | Keystone Database — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-data-store-service-keystone-database-observability.yaml |
| 01KT11AQVM-ZT9D | Keystone Database — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-data-store-service-keystone-database-resilience.yaml |
| 01KT1340G7-96A6 | Neutron Database — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-data-store-service-neutron-database-compliance.yaml |
| 01KT11AQVV-Z2T4 | Neutron Database — Data Protection and Recovery | decision_record | decision-record, example, data-protection |  | examples/catalog/governance/decision-records/dr-data-store-service-neutron-database-data-protection.yaml |
| 01KT11AQVV-6KZ4 | Neutron Database — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-data-store-service-neutron-database-identity.yaml |
| 01KT11AQVW-T2VG | Neutron Database — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-data-store-service-neutron-database-observability.yaml |
| 01KT11AQVW-1SKV | Neutron Database — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-data-store-service-neutron-database-resilience.yaml |
| 01KT1340GE-P0S5 | Nova Database — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-data-store-service-nova-database-compliance.yaml |
| 01KT11AQW3-DJNQ | Nova Database — Data Protection and Recovery | decision_record | decision-record, example, data-protection |  | examples/catalog/governance/decision-records/dr-data-store-service-nova-database-data-protection.yaml |
| 01KT11AQW3-WP1H | Nova Database — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-data-store-service-nova-database-identity.yaml |
| 01KT11AQW4-VW0R | Nova Database — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-data-store-service-nova-database-observability.yaml |
| 01KT11AQW5-K8YK | Nova Database — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-data-store-service-nova-database-resilience.yaml |
| 01KT1340GP-RX87 | OpenStack Shared Database — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-data-store-service-openstack-shared-database-compliance.yaml |
| 01KT11AQWB-FHD0 | OpenStack Shared Database — Data Protection and Recovery | decision_record | decision-record, example, data-protection |  | examples/catalog/governance/decision-records/dr-data-store-service-openstack-shared-database-data-protection.yaml |
| 01KT11AQWC-H4MK | OpenStack Shared Database — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-data-store-service-openstack-shared-database-identity.yaml |
| 01KT11AQWD-ZVQ5 | OpenStack Shared Database — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-data-store-service-openstack-shared-database-observability.yaml |
| 01KT11AQWD-PTMK | OpenStack Shared Database — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-data-store-service-openstack-shared-database-resilience.yaml |
| 01KT1340GX-CTWE | Swift Storage Cluster — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-data-store-service-swift-storage-cluster-compliance.yaml |
| 01KT11AQWN-F03H | Swift Storage Cluster — Data Protection and Recovery | decision_record | decision-record, example, data-protection |  | examples/catalog/governance/decision-records/dr-data-store-service-swift-storage-cluster-data-protection.yaml |
| 01KT11AQWN-14QQ | Swift Storage Cluster — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-data-store-service-swift-storage-cluster-identity.yaml |
| 01KT11AQWP-3JMV | Swift Storage Cluster — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-data-store-service-swift-storage-cluster-observability.yaml |
| 01KT11AQWP-H4E9 | Swift Storage Cluster — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-data-store-service-swift-storage-cluster-resilience.yaml |
| 01KSF29JTP-DRHA | HAProxy Load Balancer Operational Architecture | decision_record | decision-record, openstack, load-balancer, haproxy | Documents the operational architecture decisions for the OpenStack API Load Balancer (HAProxy) — covering authenticat... | examples/catalog/governance/decision-records/dr-haproxy-lb-operational-architecture.yaml |
| 01KT1340H3-0YCF | OpenStack Linux Service Host — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-host-openstack-linux-service-host-compliance.yaml |
| 01KT1340H6-X3T5 | AWS Lambda Serverless Host — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-host-serverless-lambda-compliance.yaml |
| 01KT1340HB-QMCP | OpenStack API Load Balancer — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-network-service-openstack-api-lb-compliance.yaml |
| 01KT11AQWW-N860 | OpenStack API Load Balancer — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-network-service-openstack-api-lb-identity.yaml |
| 01KT11AQWX-AYHX | OpenStack API Load Balancer — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-network-service-openstack-api-lb-observability.yaml |
| 01KT11AQWX-A5ZZ | OpenStack API Load Balancer — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-network-service-openstack-api-lb-resilience.yaml |
| 01KSE5V73Z-CRZV | No WAF Required — OpenStack Is Internal-Only | decision_record | decision-record, openstack, security, network-boundary | Documents the accepted decision that a Web Application Firewall (WAF) is not required for the OpenStack IaaS platform... | examples/catalog/governance/decision-records/dr-openstack-no-waf-internal-only.yaml |
| 01KSE5V73Z-DRSC | OpenStack Ops Console — Secrets Injection via Platform Secret Store | decision_record | decision-record, openstack, secrets, product-component | Documents the decision to inject application secrets into the OpenStack Ops Console at deploy time via the platform s... | examples/catalog/governance/decision-records/dr-ops-console-secrets-injection.yaml |
| 01KT1340EW-5H7Z | OpenStack Ops Console — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-product-component-openstack-ops-console-compliance.yaml |
| 01KT1340HF-1HG3 | AWS Lambda Runtime — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-aws-lambda-runtime-compliance.yaml |
| 01KT11AQX1-55F1 | AWS Lambda Runtime — Deployment Topology and Qualities | decision_record | decision-record, example, deployment |  | examples/catalog/governance/decision-records/dr-runtime-service-aws-lambda-runtime-deployment.yaml |
| 01KT11AQX2-STQ4 | AWS Lambda Runtime — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-aws-lambda-runtime-resilience.yaml |
| 01KT1340HM-7YN8 | Ceilometer Telemetry Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-ceilometer-compliance.yaml |
| 01KT11AQX6-62RD | Ceilometer Telemetry Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-ceilometer-identity.yaml |
| 01KT11AQX7-VE65 | Ceilometer Telemetry Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-ceilometer-observability.yaml |
| 01KT11AQX7-D8DJ | Ceilometer Telemetry Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-ceilometer-resilience.yaml |
| 01KT1340HS-J28V | Cinder Block Storage Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-cinder-compliance.yaml |
| 01KT11AQXC-6R7S | Cinder Block Storage Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-cinder-identity.yaml |
| 01KT11AQXD-B9P8 | Cinder Block Storage Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-cinder-observability.yaml |
| 01KT11AQXD-TNJD | Cinder Block Storage Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-cinder-resilience.yaml |
| 01KT1340HY-JXVV | Glance Image Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-glance-compliance.yaml |
| 01KT11AQXJ-3EGS | Glance Image Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-glance-identity.yaml |
| 01KT11AQXJ-ZCQY | Glance Image Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-glance-observability.yaml |
| 01KT11AQXK-D7DK | Glance Image Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-glance-resilience.yaml |
| 01KT1340J3-DG67 | Heat Orchestration Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-heat-compliance.yaml |
| 01KT11AQXR-G520 | Heat Orchestration Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-heat-identity.yaml |
| 01KT11AQXR-81H4 | Heat Orchestration Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-heat-observability.yaml |
| 01KT11AQXS-VYQS | Heat Orchestration Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-heat-resilience.yaml |
| 01KT1340J8-PZ32 | Horizon Dashboard — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-horizon-compliance.yaml |
| 01KT11AQXY-M0EQ | Horizon Dashboard — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-horizon-identity.yaml |
| 01KT11AQXZ-366K | Horizon Dashboard — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-horizon-observability.yaml |
| 01KT11AQXZ-JXXF | Horizon Dashboard — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-horizon-resilience.yaml |
| 01KT1340JE-4KAZ | Ironic Bare Metal Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-ironic-compliance.yaml |
| 01KT11AQY5-C04Q | Ironic Bare Metal Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-ironic-identity.yaml |
| 01KT11AQY5-32MF | Ironic Bare Metal Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-ironic-observability.yaml |
| 01KT11AQY6-1YA5 | Ironic Bare Metal Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-ironic-resilience.yaml |
| 01KT1340JK-8CW9 | Keystone Identity Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-keystone-compliance.yaml |
| 01KT11AQYB-GWXS | Keystone Identity Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-keystone-identity.yaml |
| 01KT11AQYC-JKP6 | Keystone Identity Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-keystone-observability.yaml |
| 01KT11AQYC-6CFA | Keystone Identity Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-keystone-resilience.yaml |
| 01KT1340JR-74JD | Neutron Networking Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-neutron-compliance.yaml |
| 01KT11AQYH-025V | Neutron Networking Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-neutron-identity.yaml |
| 01KT11AQYJ-M3WD | Neutron Networking Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-neutron-observability.yaml |
| 01KT11AQYJ-T3PZ | Neutron Networking Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-neutron-resilience.yaml |
| 01KT1340JX-5M7H | Nova Compute Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-nova-compliance.yaml |
| 01KT11AQYR-V7XY | Nova Compute Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-nova-identity.yaml |
| 01KT11AQYS-VDGH | Nova Compute Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-nova-observability.yaml |
| 01KT11AQYS-V8M7 | Nova Compute Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-nova-resilience.yaml |
| 01KT1340K3-G22W | RabbitMQ Message Broker Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-rabbitmq-compliance.yaml |
| 01KT11AQYZ-W72G | RabbitMQ Message Broker Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-rabbitmq-identity.yaml |
| 01KT11AQYZ-CFP1 | RabbitMQ Message Broker Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-rabbitmq-observability.yaml |
| 01KT11AQZ0-V8KX | RabbitMQ Message Broker Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-rabbitmq-resilience.yaml |
| 01KT1340K8-SMX8 | Sahara Data Processing Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-sahara-compliance.yaml |
| 01KT11AQZ5-FA35 | Sahara Data Processing Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-sahara-identity.yaml |
| 01KT11AQZ5-W13D | Sahara Data Processing Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-sahara-observability.yaml |
| 01KT11AQZ6-JNHZ | Sahara Data Processing Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-sahara-resilience.yaml |
| 01KT1340KD-WQET | Swift Proxy Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-swift-proxy-compliance.yaml |
| 01KT11AQZB-3D1W | Swift Proxy Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-swift-proxy-identity.yaml |
| 01KT11AQZC-5TA3 | Swift Proxy Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-swift-proxy-observability.yaml |
| 01KT11AQZC-0QJN | Swift Proxy Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-swift-proxy-resilience.yaml |
| 01KT1340KJ-VHKK | Trove Database Service — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-runtime-service-trove-compliance.yaml |
| 01KT11AQZJ-QYX8 | Trove Database Service — Identity, Access, and Secrets | decision_record | decision-record, example, identity |  | examples/catalog/governance/decision-records/dr-runtime-service-trove-identity.yaml |
| 01KT11AQZK-6FXW | Trove Database Service — Observability and Logging | decision_record | decision-record, example, observability |  | examples/catalog/governance/decision-records/dr-runtime-service-trove-observability.yaml |
| 01KT11AQZK-PETM | Trove Database Service — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-runtime-service-trove-resilience.yaml |
| 01KT1340F7-WNNX | OpenStack IaaS Platform — Security and Compliance decisions | decision_record | decision-record, example, compliance |  | examples/catalog/governance/decision-records/dr-sdp-openstack-iaas-platform-compliance.yaml |
| 01KT11AQTR-KH1S | OpenStack IaaS Platform — Data Protection and Recovery | decision_record | decision-record, example, data-protection |  | examples/catalog/governance/decision-records/dr-sdp-openstack-iaas-platform-data-protection.yaml |
| 01KT11AQTR-VD4S | OpenStack IaaS Platform — Deployment Topology and Qualities | decision_record | decision-record, example, deployment |  | examples/catalog/governance/decision-records/dr-sdp-openstack-iaas-platform-deployment.yaml |
| 01KT11AQTS-24FW | OpenStack IaaS Platform — External and Inter-Service Connections | decision_record | decision-record, example, integration |  | examples/catalog/governance/decision-records/dr-sdp-openstack-iaas-platform-integration.yaml |
| 01KT11AQTT-P9SW | OpenStack IaaS Platform — Resilience and Availability | decision_record | decision-record, example, resilience |  | examples/catalog/governance/decision-records/dr-sdp-openstack-iaas-platform-resilience.yaml |
| 01KSF29JTP-SESS | Nova Compute Service — Availability and Scaling Architecture | drafting_session | drafting-session, openstack, nova, compute, availability | Open authoring session to resolve architecture questions about Nova compute service availability posture and horizont... | examples/catalog/governance/sessions/session-nova-compute-runtime-service.yaml |
| 01KSE5V73Z-VATZ | OpenStack HAProxy NetworkService | drafting_session | drafting-session, openstack, network-service, haproxy | Incomplete authoring session for the HAProxy load balancer NetworkService. HAProxy fronts the OpenStack public networ... | examples/catalog/governance/sessions/session-openstack-ha-proxy-network-service.yaml |
| 01KSKQNTCH-RVA5 | API Load Balancer → Keystone Identity | relationship |  | HAProxy distributes inbound HTTPS identity and authentication requests across keystone-api instances running on contr... | examples/catalog/governance/relationships/relationship-api-lb-proxies-keystone.yaml |
| 01KSKQNTCH-M6JX | API Load Balancer → Neutron Networking | relationship |  | HAProxy distributes inbound HTTPS networking API requests across neutron-server instances running on controller nodes... | examples/catalog/governance/relationships/relationship-api-lb-proxies-neutron.yaml |
| 01KSKQNTCH-QHJC | API Load Balancer → Nova Compute | relationship |  | HAProxy distributes inbound HTTPS compute API requests across nova-api instances running on controller nodes. TLS is... | examples/catalog/governance/relationships/relationship-api-lb-proxies-nova.yaml |
| 01KSKWFZZX-NE4F | AWS Lambda Runtime → Amazon CloudWatch Metrics | relationship |  |  | examples/catalog/governance/relationships/relationship-aws-lambda-runtime-calls-amazon-cloudwatch-metrics.yaml |
| 01KSKWFZZX-34KP | AWS Lambda Runtime → AWS IAM | relationship |  |  | examples/catalog/governance/relationships/relationship-aws-lambda-runtime-calls-aws-iam.yaml |
| 01KSKWFZZX-JWP6 | AWS Lambda Runtime → Amazon CloudWatch Logs | relationship |  |  | examples/catalog/governance/relationships/relationship-aws-lambda-runtime-sends-events-to-amazon-cloudwatch-logs.yaml |
| 01KSKWFZZW-ZEKF | AWS Lambda Serverless Host → AWS Lambda Service | relationship |  |  | examples/catalog/governance/relationships/relationship-aws-lambda-serverless-host-calls-aws-lambda-service.yaml |
| 01KSKWFZZY-FS6X | Ceilometer Telemetry Service → Keystone Identity | relationship |  |  | examples/catalog/governance/relationships/relationship-ceilometer-telemetry-service-calls-keystone-identity.yaml |
| 01KSKWFZZY-501S | Ceilometer Telemetry Service → RabbitMQ Message Broker | relationship |  |  | examples/catalog/governance/relationships/relationship-ceilometer-telemetry-service-sends-events-to-rabbitmq-message-broker.yaml |
| 01KSKCDR01-KST1 | Cinder Block Storage → Keystone Identity | relationship |  | Cinder validates every incoming API request by verifying the caller's Keystone token. Cinder's service account is reg... | examples/catalog/governance/relationships/relationship-cinder-calls-keystone.yaml |
| 01KSKCDR01-RMQ1 | Cinder Block Storage → RabbitMQ Message Broker | relationship |  | Cinder uses RabbitMQ AMQP messaging for communication between cinder-api, cinder-scheduler, and cinder-volume subcomp... | examples/catalog/governance/relationships/relationship-cinder-calls-rabbitmq.yaml |
| 01KSKWFZZS-1SZX | Cinder Database → Backup Service | relationship |  |  | examples/catalog/governance/relationships/relationship-cinder-database-calls-backup-service.yaml |
| 01KSKCDR01-DAR5 | Cinder Block Storage → Cinder Database | relationship |  | Cinder persists all volume state to the Cinder MariaDB schema including volume records, snapshots, volume type defini... | examples/catalog/governance/relationships/relationship-cinder-reads-cinder-database.yaml |
| 01KSKWFZZS-73X6 | Glance Database → Backup Service | relationship |  |  | examples/catalog/governance/relationships/relationship-glance-database-calls-backup-service.yaml |
| 01KSKWG000-9Q1R | Glance Image Service → Glance Database | relationship |  |  | examples/catalog/governance/relationships/relationship-glance-image-service-calls-glance-database.yaml |
| 01KSKWG000-G0N1 | Glance Image Service → Keystone Identity | relationship |  |  | examples/catalog/governance/relationships/relationship-glance-image-service-calls-keystone-identity.yaml |
| 01KSKWG001-4ENK | Glance Image Service → Swift Object Storage | relationship |  |  | examples/catalog/governance/relationships/relationship-glance-image-service-calls-swift-object-storage.yaml |
| 01KSKWG002-BKKF | Heat Orchestration Service → Heat Database | relationship |  |  | examples/catalog/governance/relationships/relationship-heat-orchestration-service-calls-heat-database.yaml |
| 01KSKWG001-WJHM | Heat Orchestration Service → Keystone Identity | relationship |  |  | examples/catalog/governance/relationships/relationship-heat-orchestration-service-calls-keystone-identity.yaml |
| 01KSKWG002-5JSY | Heat Orchestration Service → RabbitMQ Message Broker | relationship |  |  | examples/catalog/governance/relationships/relationship-heat-orchestration-service-calls-rabbitmq-message-broker.yaml |
| 01KSKWG005-5P08 | Horizon Dashboard → Cinder Block Storage | relationship |  |  | examples/catalog/governance/relationships/relationship-horizon-dashboard-calls-cinder-block-storage.yaml |
| 01KSKWG004-C8QW | Horizon Dashboard → Glance Image Service | relationship |  |  | examples/catalog/governance/relationships/relationship-horizon-dashboard-calls-glance-image-service.yaml |
| 01KSKWG005-P4TK | Horizon Dashboard → Heat Orchestration | relationship |  |  | examples/catalog/governance/relationships/relationship-horizon-dashboard-calls-heat-orchestration.yaml |
| 01KSKWG003-9EKX | Horizon Dashboard → Keystone Identity | relationship |  |  | examples/catalog/governance/relationships/relationship-horizon-dashboard-calls-keystone-identity.yaml |
| 01KSKWG004-0E34 | Horizon Dashboard → Neutron Networking | relationship |  |  | examples/catalog/governance/relationships/relationship-horizon-dashboard-calls-neutron-networking.yaml |
| 01KSKWG003-G3Q2 | Horizon Dashboard → Nova Compute Service | relationship |  |  | examples/catalog/governance/relationships/relationship-horizon-dashboard-calls-nova-compute-service.yaml |
| 01KSKWG006-9TPR | Ironic Bare Metal Service → Ironic Database | relationship |  |  | examples/catalog/governance/relationships/relationship-ironic-bare-metal-service-calls-ironic-database.yaml |
| 01KSKWG005-PQGD | Ironic Bare Metal Service → Keystone Identity | relationship |  |  | examples/catalog/governance/relationships/relationship-ironic-bare-metal-service-calls-keystone-identity.yaml |
| 01KSKWG007-6VBX | Ironic Bare Metal Service → Nova Compute Service | relationship |  |  | examples/catalog/governance/relationships/relationship-ironic-bare-metal-service-calls-nova-compute-service.yaml |
| 01KSKWG006-8HH7 | Ironic Bare Metal Service → RabbitMQ Message Broker | relationship |  |  | examples/catalog/governance/relationships/relationship-ironic-bare-metal-service-calls-rabbitmq-message-broker.yaml |
| 01KSKWFZZT-1511 | Keystone Database → Backup Service | relationship |  |  | examples/catalog/governance/relationships/relationship-keystone-database-calls-backup-service.yaml |
| 01KSKWG008-3RQB | Keystone Identity Service → LDAP Directory | relationship |  |  | examples/catalog/governance/relationships/relationship-keystone-identity-service-calls-ldap-directory.yaml |
| 01KSKKS001-DAR2 | Keystone Identity → Keystone Database | relationship |  | Keystone persists all identity data to the Keystone MariaDB schema including users, projects, roles, role assignments... | examples/catalog/governance/relationships/relationship-keystone-reads-keystone-database.yaml |
| 01KSKNTN01-KST1 | Neutron Networking → Keystone Identity | relationship |  | Neutron validates every incoming API request by verifying the caller's Keystone token. Neutron's service account is r... | examples/catalog/governance/relationships/relationship-neutron-calls-keystone.yaml |
| 01KSKNTN01-RMQ1 | Neutron Networking → RabbitMQ Message Broker | relationship |  | Neutron uses RabbitMQ AMQP messaging for communication between neutron-server and neutron-agent subcomponents includi... | examples/catalog/governance/relationships/relationship-neutron-calls-rabbitmq.yaml |
| 01KSKWFZZT-R5CF | Neutron Database → Backup Service | relationship |  |  | examples/catalog/governance/relationships/relationship-neutron-database-calls-backup-service.yaml |
| 01KSKNTN01-DAR4 | Neutron Networking → Neutron Database | relationship |  | Neutron persists all network state to the Neutron MariaDB schema including networks, subnets, ports, routers, securit... | examples/catalog/governance/relationships/relationship-neutron-reads-neutron-database.yaml |
| 01KSKN0V01-CDR1 | Nova Compute → Cinder Block Storage | relationship |  | Nova calls Cinder APIs to attach and detach persistent block volumes to running instances. Volume attachment is initi... | examples/catalog/governance/relationships/relationship-nova-calls-cinder.yaml |
| 01KSKN0V01-KST1 | Nova Compute → Keystone Identity | relationship |  | Nova validates every incoming API request by verifying the caller's Keystone token. Nova service-to-service calls use... | examples/catalog/governance/relationships/relationship-nova-calls-keystone.yaml |
| 01KSKN0V01-RMQ1 | Nova Compute → RabbitMQ Message Broker | relationship |  | Nova uses RabbitMQ AMQP messaging for all inter-subcomponent communication including scheduling requests from nova-ap... | examples/catalog/governance/relationships/relationship-nova-calls-rabbitmq.yaml |
| 01KSKWG00B-1Z27 | Nova Compute Service → Glance Image Service | relationship |  |  | examples/catalog/governance/relationships/relationship-nova-compute-service-calls-glance-image-service.yaml |
| 01KSKWFZZT-JW98 | Nova Database → Backup Service | relationship |  |  | examples/catalog/governance/relationships/relationship-nova-database-calls-backup-service.yaml |
| 01KSKN0V01-NTN1 | Nova Compute → Neutron Networking | relationship |  | Nova calls Neutron APIs to create, attach, and detach virtual network interfaces during instance provisioning and del... | examples/catalog/governance/relationships/relationship-nova-provisions-neutron.yaml |
| 01KSK0C6DP-5GFZ | Nova Compute → Nova Database | relationship |  | Nova Compute reads and writes scheduling, instance, and host state to the Nova Database. | examples/catalog/governance/relationships/relationship-nova-reads-nova-database.yaml |
| 01KSKWFZZV-A346 | OpenStack Shared Database → Backup Service | relationship |  |  | examples/catalog/governance/relationships/relationship-openstack-shared-database-calls-backup-service.yaml |
| 01KSKWG00D-2AYJ | RabbitMQ Message Broker Service → Keystone Identity | relationship |  |  | examples/catalog/governance/relationships/relationship-rabbitmq-message-broker-service-calls-keystone-identity.yaml |
| 01KSKWG00D-V0KN | Sahara Data Processing Service → Keystone Identity | relationship |  |  | examples/catalog/governance/relationships/relationship-sahara-data-processing-service-calls-keystone-identity.yaml |
| 01KSKWG00E-56JG | Sahara Data Processing Service → Sahara Database | relationship |  |  | examples/catalog/governance/relationships/relationship-sahara-data-processing-service-calls-sahara-database.yaml |
| 01KSKWG00E-NC3H | Swift Proxy Service → Keystone Identity | relationship |  |  | examples/catalog/governance/relationships/relationship-swift-proxy-service-calls-keystone-identity.yaml |
| 01KSKWG00F-87Z3 | Swift Proxy Service → Swift Storage Cluster | relationship |  |  | examples/catalog/governance/relationships/relationship-swift-proxy-service-calls-swift-storage-cluster.yaml |
| 01KSKWFZZW-2BN8 | Swift Storage Cluster → Backup Service | relationship |  |  | examples/catalog/governance/relationships/relationship-swift-storage-cluster-calls-backup-service.yaml |
| 01KSKWG00F-XS1H | Trove Database Service → Keystone Identity | relationship |  |  | examples/catalog/governance/relationships/relationship-trove-database-service-calls-keystone-identity.yaml |
| 01KSKWG00F-PV05 | Trove Database Service → RabbitMQ Message Broker | relationship |  |  | examples/catalog/governance/relationships/relationship-trove-database-service-calls-rabbitmq-message-broker.yaml |
| 01KSKWG00G-07D0 | Trove Database Service → Trove Database | relationship |  |  | examples/catalog/governance/relationships/relationship-trove-database-service-calls-trove-database.yaml |
| 01KSK1FMGV-JMTP | OpenStack Compute Platform | system | openstack, iaas, infrastructure | Core OpenStack compute, networking, and storage services that together deliver IaaS capabilities to tenant workloads. | examples/catalog/governance/systems/system-openstack-compute.yaml |

## Content Folder Counts

| Folder | YAML Count |
|---|---|
| framework/configurations/capabilities | 42 |
| framework/configurations/requirement-groups | 20 |
| framework/configurations/reference-architectures | 3 |
| framework/configurations/domains | 10 |
| examples/catalog/engineering/product-components | 1 |
| examples/catalog/engineering/data-components | 1 |
| examples/catalog/engineering/software-deployment-patterns | 1 |
| examples/catalog/shared-services/hosts | 2 |
| examples/catalog/shared-services/runtime-services | 14 |
| examples/catalog/shared-services/data-store-services | 7 |
| examples/catalog/shared-services/network-services | 1 |
| examples/catalog/shared-services/technology-components | 20 |
| examples/catalog/governance/decision-records | 105 |
| examples/catalog/governance/sessions | 2 |
| examples/catalog/governance/relationships | 54 |
| examples/catalog/governance/systems | 1 |
| examples/catalog/governance/reference-architectures | 0 |

## Templates

| Path | Purpose |
|---|---|
| templates/capability.yaml.tmpl | Reusable YAML authoring template. |
| templates/data-store-service.yaml.tmpl | Reusable YAML authoring template. |
| templates/decision-record.yaml.tmpl | Reusable YAML authoring template. |
| templates/deployment-target.yaml.tmpl | Reusable YAML authoring template. |
| templates/drafting-session.yaml.tmpl | Reusable YAML authoring template. |
| templates/host.yaml.tmpl | Reusable YAML authoring template. |
| templates/network-service.yaml.tmpl | Reusable YAML authoring template. |
| templates/object-patch.yaml.tmpl | Reusable YAML authoring template. |
| templates/reference-architecture.yaml.tmpl | Reusable YAML authoring template. |
| templates/requirement-group.yaml.tmpl | Reusable YAML authoring template. |
| templates/runtime-service.yaml.tmpl | Reusable YAML authoring template. |
| templates/software-deployment-pattern.yaml.tmpl | Reusable YAML authoring template. |
| templates/technology-component.yaml.tmpl | Reusable YAML authoring template. |
| templates/workspace/.cursor/rules/draftsman.mdc.tmpl | Reusable YAML authoring template. |
| templates/workspace/.draft/framework.lock.tmpl | Reusable YAML authoring template. |
| templates/workspace/.draft/workspace.yaml.tmpl | Reusable YAML authoring template. |
| templates/workspace/.github/copilot-instructions.md.tmpl | Copilot Instructions |
| templates/workspace/.github/workflows/draft-framework-update.yml.tmpl | Reusable YAML authoring template. |
| templates/workspace/.github/workflows/draft-vocabulary-proposals.yml.tmpl | DRAFT Vocabulary Proposal PRs |
| templates/workspace/.github/workflows/generate-browser.yml.tmpl | Reusable YAML authoring template. |
| templates/workspace/.gitignore.tmpl | Reusable YAML authoring template. |
| templates/workspace/.windsurfrules.tmpl | DRAFT Draftsman |
| templates/workspace/AGENTS.md.tmpl | AI Agent Instructions |
| templates/workspace/CLAUDE.md.tmpl | Claude Instructions |
| templates/workspace/CODEOWNERS.tmpl | DRAFT Workspace — CODEOWNERS |
| templates/workspace/GEMINI.md.tmpl | Gemini Instructions |
| templates/workspace/README.md.tmpl | Company DRAFT Workspace |
| templates/workspace/configurations/object-patches/capability-ownership-compute-runtime.yaml.tmpl | Capability Ownership — Compute & Runtime Domain |
| templates/workspace/configurations/object-patches/capability-ownership-data-engineering-quality.yaml.tmpl | Capability Ownership — Data & Engineering Quality Domains |
| templates/workspace/configurations/object-patches/capability-ownership-observability.yaml.tmpl | Capability Ownership — Observability & Monitoring Domain |
| templates/workspace/configurations/object-patches/capability-ownership-security-identity.yaml.tmpl | Capability Ownership — Security & Identity Domain |
| templates/workspace/llms.txt.tmpl | Company DRAFT Workspace |

## Validation

- Validate the example workspace: `python3 framework/tools/validate.py`
- Validate a company workspace: `python3 framework/tools/validate.py --workspace /path/to/workspace`
- Validate from inside a company repo: `python3 .draft/framework/tools/validate.py --workspace .`
- Regenerate browser after YAML changes: `python3 framework/tools/generate_browser.py`
- Regenerate this index after framework or YAML changes: `python3 framework/tools/generate_ai_index.py`
