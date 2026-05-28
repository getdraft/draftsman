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
| framework/docs/company-onboarding.md | Company onboarding tutorial for implementing DRAFT in a private workspace. |
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
| framework/tools/validate.py | Executable validation for schemas, Requirement Groups, capabilities, and references. |
| framework/tools/apply_vocabulary_proposals.py | Materializes Draftsman vocabulary_proposal files into reviewable company vocabulary entries. |
| framework/tools/repair_uids.py | Explicit repair utility that adds or replaces generated object UIDs and rewrites object references. |
| framework/tools/generate_browser.py | Static GitHub Pages browser generator. |
| install-draft-table.sh | Experimental local tooling installer retained for post-v1.0 work. |

## Framework Docs

| Path | Title | Summary |
|---|---|---|
| framework/docs/capabilities.md | Capabilities | A Capability is a first-class framework object that names an architecture |
| framework/docs/company-onboarding.md | Company Onboarding | This guide is the clean first-run path for a company adopting DRAFT. It keeps |
| framework/docs/company-vocabulary.md | Company Vocabulary | Company vocabulary lists are optional governed lists in `.draft/workspace.yaml`. |
| framework/docs/decision-records.md | Decision Records | Decision Records are first-class records for known risks, |
| framework/docs/delivery-models.md | Delivery Models | Delivery models explain how a deployable service is operated. They apply to |
| framework/docs/drafting-sessions.md | Drafting Sessions | A Drafting Session is a machine-readable record of partial architecture work. |
| framework/docs/draftsman-ai-configuration.md | Draftsman AI Guidance | DRAFT does not include a built-in AI runtime. The Draftsman is an external AI |
| framework/docs/draftsman.md | Draftsman Instructions | The Draftsman is an AI architecture-authoring agent for DRAFT. It interviews the |
| framework/docs/exporters.md | DRAFT Exporters | DRAFT catalogs are authoritative YAML — the source of truth for architecture |
| framework/docs/how-to-add-objects.md | How To Add Objects | The fastest way to add a new object correctly is to decide what kind of thing you are modeling before you write YAML. |
| framework/docs/naming-conventions.md | Naming Conventions | DRAFT first-class objects use an opaque generated `uid` for machine identity and |
| framework/docs/object-types.md | DRAFT Object Types | DRAFT object types are split into deployable architecture and non-deployable |
| framework/docs/overview.md | Framework Overview | This page is the high-level object map for DRAFT. For the complete object type |
| framework/docs/reference-architectures.md | Reference Architectures | The DRAFT framework ships a set of baseline Reference Architectures in |
| framework/docs/requirement-groups.md | Requirement Groups | A Requirement Group is the unified DRAFT requirement model. It replaces the old |
| framework/docs/sdp-completion-interview.md | SDP Completion Interview | The SDP Completion Interview is a structured protocol for enriching an existing |
| framework/docs/security-and-compliance-controls.md | Security And Compliance Requirement Groups | DRAFT treats compliance as an explicitly activated authoring and validation layer. |
| framework/docs/setup-mode.md | Draftsman Setup Mode | Setup mode is the first-run Draftsman conversation for a company DRAFT |
| framework/docs/software-deployment-patterns.md | Software Deployment Patterns | A Software Deployment Pattern is a declaration that a specific product is intended |
| framework/docs/standards.md | Deployable Objects | DRAFT previously used the word "Standard" for reusable deployable building |
| framework/docs/technology-components.md | Technology Components | A Technology Component is a discrete vendor product object. It records one |
| framework/docs/user-manual.md | DRAFT User Manual | DRAFT is an AI-first, Git-native, repo-first framework for documenting governed architecture. It turns architecture c... |
| framework/docs/workspaces.md | Workspaces | For the full adoption sequence from installation through first drafting |
| framework/docs/yaml-schema-reference.md | YAML Schema Reference | This page is the quickest way to understand how to build a valid YAML object in |

## Schemas

| Path | Scope | Required Fields |
|---|---|---|
| framework/schemas/capability.schema.yaml | capability | schemaVersion, uid, type, name, description, catalogStatus, definitionOwner, domain, implementations |
| framework/schemas/data-component.schema.yaml | data_component | schemaVersion, uid, type, name, repoUrl, owner, runsOn, targetEngine, dataClassification, containsPII, catalogStatus, lifecycleStatus |
| framework/schemas/data-store-service.schema.yaml | data_store_service | schemaVersion, uid, type, name, deliveryModel, catalogStatus, lifecycleStatus |
| framework/schemas/decision-record.schema.yaml | decision_record | schemaVersion, uid, type, name, category, status, catalogStatus, lifecycleStatus |
| framework/schemas/domain.schema.yaml | domain | schemaVersion, uid, type, name, capabilities |
| framework/schemas/drafting-session.schema.yaml | drafting_session | schemaVersion, uid, type, name, catalogStatus, lifecycleStatus, sessionStatus, primaryObjectType, sourceArtifacts, generatedObjects, unresolvedQuestions |
| framework/schemas/edge-gateway-service.schema.yaml | edge_gateway_service | schemaVersion, uid, type, name, deliveryModel, catalogStatus, lifecycleStatus |
| framework/schemas/environment-tier.schema.yaml | environment_tier | schemaVersion, uid, type, name, tierId, purpose, availabilityExpectation, catalogStatus |
| framework/schemas/host.schema.yaml | host | schemaVersion, uid, type, name, catalogStatus, lifecycleStatus |
| framework/schemas/object-patch.schema.yaml | object_patch | schemaVersion, uid, type, name, target, patch, catalogStatus, lifecycleStatus |
| framework/schemas/product-component.schema.yaml | product_component | schemaVersion, uid, type, name, repoUrl, owner, classification, catalogStatus, lifecycleStatus |
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
| 01KQQ4Q026-NB1W | Application Performance Monitoring | capability |  | Tracing and performance analysis of application runtimes. | framework/configurations/capabilities/capability-apm.yaml |
| 01KQQ4Q026-MHJM | Authentication | capability |  | Identity and access authentication capability for users, services, administrators, or workloads. | framework/configurations/capabilities/capability-authentication.yaml |
| 01KQQ4Q026-7T2H | Backup Strategy | capability |  | Backup, restore, and recovery point capability for durable data stores. | framework/configurations/capabilities/capability-backup-strategy.yaml |
| 01KQQ4Q026-1HZP | Compute Platform | capability |  | Compute substrate or virtualized platform used to run Hosts. | framework/configurations/capabilities/capability-compute-platform.yaml |
| 01KQQ4Q026-9K8G | General Purpose Compute | capability |  | Provisioning and execution of arbitrary code on reusable compute substrates. | framework/configurations/capabilities/capability-compute.yaml |
| 01KQQ4Q026-GW5D | Container Orchestration | capability |  | Management of containerized workload lifecycles. | framework/configurations/capabilities/capability-container-orchestration.yaml |
| 01KQQ4Q026-H3B5 | Encryption At Rest | capability |  | Protection of persisted data through encryption or equivalent storage safeguards. | framework/configurations/capabilities/capability-encryption-at-rest.yaml |
| 01KQQ4Q026-98VD | Health and Welfare Monitoring | capability |  | Runtime health, uptime, metrics, and operational welfare visibility. | framework/configurations/capabilities/capability-health-welfare-monitoring.yaml |
| 01KQQ4Q026-D04B | Log Management | capability |  | Aggregation, retention, searchability, and forwarding of system or application logs. | framework/configurations/capabilities/capability-log-management.yaml |
| 01KQQ4Q026-QM2X | Operating System | capability |  | Supported operating system product used to define managed Hosts. | framework/configurations/capabilities/capability-operating-system.yaml |
| 01KQQ4Q026-BH6E | Patch Management | capability |  | Patch orchestration and update application capability for managed runtime components. | framework/configurations/capabilities/capability-patch-management.yaml |
| 01KQQ4Q026-S5J6 | Performance and Load Testing | capability |  | Capabilities to simulate load and measure system behavior under stress. | framework/configurations/capabilities/capability-performance-testing.yaml |
| 01KQQ4Q026-RTWC | Quality Gates | capability |  | Promotion criteria and automated checks required for lifecycle transitions. | framework/configurations/capabilities/capability-quality-gates.yaml |
| 01KQQ4Q026-DTJJ | Secrets Management | capability |  | Secure storage, rotation, and access mediation for secrets and authenticators. | framework/configurations/capabilities/capability-secrets-management.yaml |
| 01KQQ4Q026-JW52 | Security Monitoring | capability |  | Threat detection, intrusion detection, security event monitoring, and audit telemetry. | framework/configurations/capabilities/capability-security-monitoring.yaml |
| 01KQQ4Q026-3ZWJ | Serverless Function Runtime | capability |  | Event-driven, scale-to-zero compute runtime capability. | framework/configurations/capabilities/capability-serverless-runtime.yaml |
| 01KQQ4Q026-QC9S | Test Authoring | capability |  | Tools and frameworks used to author automated tests. | framework/configurations/capabilities/capability-test-authoring.yaml |
| 01KQQ4Q026-58Q3 | Test Execution and Automation | capability |  | Runtimes and orchestration services used to execute automated tests. | framework/configurations/capabilities/capability-test-execution.yaml |
| 01KQQ4Q027-DSDD | Appliance Delivery Requirement Group | requirement_group | appliance, requirement-group, definition | Structured requirements used when a Runtime, Data-at-Rest, or Edge/Gateway Service uses appliance delivery and the un... | framework/configurations/requirement-groups/requirement-group-appliance-delivery.yaml |
| 01KRWRRNM7-VJ5A | Data Component Requirement Group | requirement_group | data-component, requirement-group, definition | Built-in checklist for first-party data artifacts deployed onto Data Store Services. Establishes what must be known a... | framework/configurations/requirement-groups/requirement-group-data-component.yaml |
| 01KQQ4Q027-VBF0 | DataStoreService Requirement Group | requirement_group | service, dbms, requirement-group, definition | Additional DataStoreService checklist items extending the service behavior Requirement Group for durable data, recove... | framework/configurations/requirement-groups/requirement-group-data-store-service.yaml |
| 01KQQ4Q027-69VY | NIST Cybersecurity Framework Requirement Group | requirement_group | compliance, nist, starter-pack, requirement-group | Initial NIST Cybersecurity Framework (CSF) 2.0 requirement group scoped to the outcomes that can be meaningfully answ... | framework/configurations/requirement-groups/requirement-group-draft-nist-csf.yaml |
| 01KQQ4Q027-T3CA | Security and Security Compliance Requirement Group | requirement_group | compliance, controls, baseline, requirement-group | Baseline security and compliance requirement group bundled with DRAFT. Requirements are applied to matching object ty... | framework/configurations/requirement-groups/requirement-group-draft-security-compliance.yaml |
| 01KQQ4Q027-7JN2 | SOC 2 Requirement Group | requirement_group | compliance, soc2, starter-pack, requirement-group | Initial SOC 2 requirement group based on the AICPA Trust Services Criteria. These requirements use DRAFT applicabilit... | framework/configurations/requirement-groups/requirement-group-draft-soc2.yaml |
| 01KQQ4Q027-1GHC | TX-RAMP Requirement Group | requirement_group | compliance, tx-ramp, starter-pack, requirement-group | Starter TX-RAMP requirement group for DRAFT. This file is intended to map TX-RAMP control expectations onto the unifi... | framework/configurations/requirement-groups/requirement-group-draft-tx-ramp.yaml |
| 01KQQ4Q027-HHA4 | Drafting Session Requirement Group | requirement_group | drafting-session, requirement-group, intake | Structured checklist used to capture partial architecture-authoring sessions, generated outputs, and unresolved follo... | framework/configurations/requirement-groups/requirement-group-drafting-session.yaml |
| 01KSF4NHSP-8HPP | Engineering Quality Requirement Group | requirement_group | product-component, requirement-group, engineering, quality, optional | Optional checklist for ProductComponents covering build quality, test coverage, and performance validation practices.... | framework/configurations/requirement-groups/requirement-group-engineering-quality.yaml |
| 01KSF4NHSP-HCPX | Host Compute Profile Requirement Group | requirement_group | host, requirement-group, compute, optional | Optional checklist for Hosts covering compute type classification. Activated per workspace; does not fire automatically. | framework/configurations/requirement-groups/requirement-group-host-compute-profile.yaml |
| 01KQQ4Q027-THYN | Host Requirement Group | requirement_group | host, requirement-group, definition | Structured checklist of required questions and answers used to define a complete and correct Host. | framework/configurations/requirement-groups/requirement-group-host.yaml |
| 01KQQ4Q027-TPWG | PaaS Delivery Requirement Group | requirement_group | paas, requirement-group, definition | Structured requirements used when a Runtime, Data-at-Rest, or Edge/Gateway Service is vendor-managed inside the organ... | framework/configurations/requirement-groups/requirement-group-paas-delivery.yaml |
| 01KRWRRNM7-G642 | Product Component Requirement Group | requirement_group | product-component, requirement-group, definition | Built-in checklist for first-party code components deployed onto Runtime Services. Establishes what must be known abo... | framework/configurations/requirement-groups/requirement-group-product-component.yaml |
| 01KQQ4Q027-SS2K | Reference Architecture Requirement Group | requirement_group | reference-architecture, requirement-group, definition | Structured checklist of required questions and answers used to define a complete and correct Reference Architecture. | framework/configurations/requirement-groups/requirement-group-reference-architecture.yaml |
| 01KQQ4Q027-K5DR | Service Behavior Requirement Group | requirement_group | service, requirement-group, definition | Structured checklist of required questions and answers used to define complete and correct self-managed Runtime and E... | framework/configurations/requirement-groups/requirement-group-runtime-service.yaml |
| 01KQQ4Q027-FKRM | SaaS Delivery Requirement Group | requirement_group | saas, requirement-group, definition | Structured requirements used when a Runtime, Data-at-Rest, or Edge/Gateway Service is consumed as a vendor-managed ex... | framework/configurations/requirement-groups/requirement-group-saas-delivery.yaml |
| 01KSF29JTP-SRVE | Service Engineering Practices Requirement Group | requirement_group | service, requirement-group, engineering, optional | Optional checklist for self-managed Runtime and Edge/Gateway Services covering advanced observability and runtime pat... | framework/configurations/requirement-groups/requirement-group-service-engineering.yaml |
| 01KQQ4Q027-VK45 | Software Deployment Pattern Requirement Group | requirement_group | software-deployment-pattern, requirement-group, definition | Structured checklist of required questions and answers used to define a complete and correct software deployment patt... | framework/configurations/requirement-groups/requirement-group-software-deployment-pattern.yaml |
| 01KS8N4KR3-MTSA | Multi-Tenant SaaS | reference_architecture | reference-architecture, multi-tenant, saas | Deployment pattern for software-as-a-service products that serve multiple customer tenants from shared infrastructure... | framework/configurations/reference-architectures/ra-multi-tenant-saas.yaml |
| 01KS8N4KR4-SVED | Serverless Event-Driven | reference_architecture | reference-architecture, serverless, event-driven | Deployment pattern for event-driven applications using serverless compute runtimes. No persistent application-tier co... | framework/configurations/reference-architectures/ra-serverless-event-driven.yaml |
| 01KS8N4KR2-3TWA | Three-Tier Web Application | reference_architecture | reference-architecture, three-tier, web | Standard pattern for web-facing applications with a presentation tier (edge/gateway services), an application tier (r... | framework/configurations/reference-architectures/ra-three-tier-web.yaml |
| 01KQQ4Q027-ZTHF | Compute & Runtime | domain |  | Strategic domain covering application runtimes, serverless functions, and physical or virtual compute resources. | framework/configurations/domains/compute.yaml |
| 01KQQ4Q027-C213 | Observability & Monitoring | domain |  | Strategic domain covering logging, metrics, tracing, and health monitoring across infrastructure and application stacks. | framework/configurations/domains/observability.yaml |
| 01KQQ4Q027-SGHR | Testing & Quality | domain |  | Strategic domain covering all aspects of software testing, quality assurance, and release gates. | framework/configurations/domains/testing.yaml |

## Example Catalog Inventory

These are sample catalog objects used to validate and demonstrate the framework. Company-specific content belongs in a private company `catalog/` folder.

| UID | Name | Type | Tags | Description | Path |
|---|---|---|---|---|---|
| 01KQQ4Q025-MQ3F | CrowdStrike Falcon Agent | technology_component | technology-component, agent | Endpoint security agent installed locally on a host that requires communication with the CrowdStrike Falcon platform. | examples/catalog/technology-components/technology-agent-crowdstrike-falcon.yaml |
| 01KQQ4Q025-9N4R | Amazon EC2 Standard Compute Platform | technology_component | technology-component, compute-platform | Standard Amazon EC2 virtual machine substrate used for general-purpose host patterns. | examples/catalog/technology-components/technology-compute-amazon-ec2-standard.yaml |
| STCK00000F-TC0F | OpenStack Bare Metal Standard Compute Platform | technology_component | technology-component, compute-platform, bare-metal, openstack | Generic bare-metal x86_64 compute substrate used by the OpenStack example service-host patterns. | examples/catalog/technology-components/technology-compute-openstack-bare-metal-standard.yaml |
| 01KSF29JTP-8YRX | HAProxy 2.9 | technology_component | technology-component, load-balancer, haproxy, openstack | Open-source TCP/HTTP load balancer and proxy server. Provides high-availability request distribution, health checking... | examples/catalog/technology-components/technology-haproxy-29.yaml |
| STCK00000E-TC0E | MariaDB 10.11 | technology_component | technology-component, database, relational, mariadb, iaas | MariaDB 10.11 is the long-term support relational database used as the persistence backend for OpenStack services. Ea... | examples/catalog/technology-components/technology-mariadb-1011.yaml |
| STCK000009-TC09 | OpenStack Ceilometer | technology_component | technology-component, openstack, telemetry, monitoring, metering, iaas | OpenStack Ceilometer is the telemetry service for OpenStack. It collects metering and monitoring data from across the... | examples/catalog/technology-components/technology-openstack-ceilometer.yaml |
| STCK000005-TC05 | OpenStack Cinder | technology_component | technology-component, openstack, block-storage, iaas | OpenStack Cinder is the block storage service that provides persistent block volumes to Nova compute instances. It in... | examples/catalog/technology-components/technology-openstack-cinder.yaml |
| STCK000003-TC03 | OpenStack Glance | technology_component | technology-component, openstack, image, iaas | OpenStack Glance is the image service that stores and retrieves virtual machine disk images. It provides glance-api a... | examples/catalog/technology-components/technology-openstack-glance.yaml |
| STCK000008-TC08 | OpenStack Heat | technology_component | technology-component, openstack, orchestration, infrastructure-as-code, iaas | OpenStack Heat is the orchestration service for OpenStack. It implements a heat-api, heat-api-cfn (CloudFormation-com... | examples/catalog/technology-components/technology-openstack-heat.yaml |
| STCK000007-TC07 | OpenStack Horizon | technology_component | technology-component, openstack, dashboard, web-ui, iaas | OpenStack Horizon is the web-based dashboard for OpenStack services. It provides a self-service portal for tenants an... | examples/catalog/technology-components/technology-openstack-horizon.yaml |
| STCK00000A-TC0A | OpenStack Ironic | technology_component | technology-component, openstack, bare-metal, ironic, iaas | OpenStack Ironic is the bare metal provisioning service. It exposes ironic-api and uses ironic-conductor to manage ph... | examples/catalog/technology-components/technology-openstack-ironic.yaml |
| STCK000002-TC02 | OpenStack Keystone | technology_component | technology-component, openstack, identity, auth, iaas | OpenStack Keystone is the identity service providing authentication and authorization for all OpenStack services. It... | examples/catalog/technology-components/technology-openstack-keystone.yaml |
| STCK000004-TC04 | OpenStack Neutron | technology_component | technology-component, openstack, networking, sdn, iaas | OpenStack Neutron is the networking service providing software-defined networking capabilities to the OpenStack platf... | examples/catalog/technology-components/technology-openstack-neutron.yaml |
| STCK000001-TC01 | OpenStack Nova | technology_component | technology-component, openstack, compute, iaas | OpenStack Nova is the compute service responsible for managing and provisioning virtual machine instances. It include... | examples/catalog/technology-components/technology-openstack-nova.yaml |
| STCK00000C-TC0C | OpenStack Sahara | technology_component | technology-component, openstack, data-processing, hadoop, iaas | OpenStack Sahara is the data processing service that automates provisioning of Apache Hadoop and Spark clusters on Op... | examples/catalog/technology-components/technology-openstack-sahara.yaml |
| STCK000006-TC06 | OpenStack Swift | technology_component | technology-component, openstack, object-storage, iaas | OpenStack Swift is the object storage service providing highly durable, distributed storage for unstructured data. It... | examples/catalog/technology-components/technology-openstack-swift.yaml |
| STCK00000B-TC0B | OpenStack Trove | technology_component | technology-component, openstack, database-as-a-service, dbaas, iaas | OpenStack Trove is the database-as-a-service component. It provides trove-api, trove-conductor, and trove-taskmanager... | examples/catalog/technology-components/technology-openstack-trove.yaml |
| 01KQQ4Q025-3HXA | Ubuntu 22.04 LTS | technology_component | technology-component, operating-system | Canonical Ubuntu Server 22.04 LTS operating system product definition for Linux host patterns. | examples/catalog/technology-components/technology-os-canonical-ubuntu-2204.yaml |
| STCK00000D-TC0D | RabbitMQ 3.8 | technology_component | technology-component, messaging, amqp, rabbitmq, iaas | RabbitMQ is a widely deployed open-source message broker implementing AMQP. In OpenStack it serves as the shared mess... | examples/catalog/technology-components/technology-rabbitmq-38.yaml |
| 01KQQ4Q025-Z042 | nginx 1.26 | technology_component | technology-component, software | nginx web server software installed locally on a managed host and used without a required vendor platform interaction. | examples/catalog/technology-components/technology-software-nginx-126.yaml |
| STCK00000F-HS0F | OpenStack Linux Service Host | host | host, openstack, linux | General-purpose self-managed Linux host standard for the OpenStack example control-plane, data, and utility services.... | examples/catalog/hosts/host-openstack-linux-service-host.yaml |
| 01KQQ4Q025-1XDE | AWS Lambda Serverless Host | host | lambda, serverless | Serverless execution environment provided by AWS Lambda. The host is entirely AWS-managed and blackbox to the organiz... | examples/catalog/hosts/host-serverless-lambda.yaml |
| 01KQQ4Q025-T7B7 | AWS Lambda Runtime | runtime_service | serverless, lambda | AWS Lambda serverless execution environment. Runs organization-authored function code without requiring host manageme... | examples/catalog/runtime-services/runtime-service-aws-lambda-runtime.yaml |
| STCK000008-RS08 | Ceilometer Telemetry Service | runtime_service | runtime-service, openstack, telemetry, ceilometer, metering, iaas | Self-managed deployment of OpenStack Ceilometer providing metering and telemetry data collection across the OpenStack... | examples/catalog/runtime-services/runtime-service-ceilometer.yaml |
| STCK000005-RS05 | Cinder Block Storage Service | runtime_service | runtime-service, openstack, block-storage, cinder, iaas | Self-managed deployment of OpenStack Cinder providing persistent block storage volumes for compute instances. Runs ci... | examples/catalog/runtime-services/runtime-service-cinder.yaml |
| STCK000003-RS03 | Glance Image Service | runtime_service | runtime-service, openstack, image, glance, iaas | Self-managed deployment of OpenStack Glance providing virtual machine image storage and retrieval. Runs glance-api an... | examples/catalog/runtime-services/runtime-service-glance.yaml |
| STCK000007-RS07 | Heat Orchestration Service | runtime_service | runtime-service, openstack, orchestration, heat, iaas | Self-managed deployment of OpenStack Heat providing infrastructure orchestration via the Heat Orchestration Template... | examples/catalog/runtime-services/runtime-service-heat.yaml |
| STCK000006-RS06 | Horizon Dashboard | runtime_service | runtime-service, openstack, dashboard, horizon, web-ui, iaas | Self-managed deployment of OpenStack Horizon providing the web-based management dashboard for the OpenStack platform.... | examples/catalog/runtime-services/runtime-service-horizon.yaml |
| STCK000009-RS09 | Ironic Bare Metal Service | runtime_service | runtime-service, openstack, bare-metal, ironic, iaas | Self-managed deployment of OpenStack Ironic providing bare metal provisioning as a service. Runs ironic-api and ironi... | examples/catalog/runtime-services/runtime-service-ironic.yaml |
| STCK000002-RS02 | Keystone Identity Service | runtime_service | runtime-service, openstack, identity, auth, keystone, iaas | Self-managed deployment of OpenStack Keystone providing identity, authentication, and authorization services for all... | examples/catalog/runtime-services/runtime-service-keystone.yaml |
| STCK000004-RS04 | Neutron Networking Service | runtime_service | runtime-service, openstack, networking, neutron, sdn, iaas | Self-managed deployment of OpenStack Neutron providing software-defined networking for the OpenStack platform. Runs n... | examples/catalog/runtime-services/runtime-service-neutron.yaml |
| STCK000001-RS01 | Nova Compute Service | runtime_service | runtime-service, openstack, compute, nova, iaas | Self-managed deployment of OpenStack Nova providing virtual machine lifecycle management across the platform. Runs no... | examples/catalog/runtime-services/runtime-service-nova.yaml |
| STCK00000D-RS0D | RabbitMQ Message Broker Service | runtime_service | runtime-service, messaging, amqp, rabbitmq, iaas | Self-managed deployment of RabbitMQ serving as the shared AMQP message broker for the OpenStack control plane. Provid... | examples/catalog/runtime-services/runtime-service-rabbitmq.yaml |
| STCK00000B-RS0B | Sahara Data Processing Service | runtime_service | runtime-service, openstack, data-processing, sahara, hadoop, iaas | Self-managed deployment of OpenStack Sahara providing data processing cluster orchestration on OpenStack. Runs sahara... | examples/catalog/runtime-services/runtime-service-sahara.yaml |
| STCK00000C-RS0C | Swift Proxy Service | runtime_service | runtime-service, openstack, object-storage, swift, swift-proxy, iaas | Self-managed deployment of the OpenStack Swift proxy-server providing the API gateway for all object storage operatio... | examples/catalog/runtime-services/runtime-service-swift-proxy.yaml |
| STCK00000A-RS0A | Trove Database Service | runtime_service | runtime-service, openstack, database-as-a-service, trove, iaas | Self-managed deployment of OpenStack Trove providing database-as-a-service on top of the OpenStack compute platform.... | examples/catalog/runtime-services/runtime-service-trove.yaml |
| STCK000005-DAR5 | Cinder Database | data_store_service | data-at-rest, openstack, cinder, block-storage, database, mariadb, iaas | MariaDB database schema dedicated to OpenStack Cinder for persisting all block storage service state. Stores volume r... | examples/catalog/data-store-services/data-store-service-cinder-database.yaml |
| STCK000003-DAR3 | Glance Database | data_store_service | data-at-rest, openstack, glance, image, database, mariadb, iaas | MariaDB database schema dedicated to OpenStack Glance for persisting virtual machine image metadata. Stores image rec... | examples/catalog/data-store-services/data-store-service-glance-database.yaml |
| STCK000002-DAR2 | Keystone Database | data_store_service | data-at-rest, openstack, keystone, identity, database, mariadb, iaas | MariaDB database schema dedicated to OpenStack Keystone for persisting all identity service data. Stores users, group... | examples/catalog/data-store-services/data-store-service-keystone-database.yaml |
| STCK000004-DAR4 | Neutron Database | data_store_service | data-at-rest, openstack, neutron, networking, database, mariadb, iaas | MariaDB database schema dedicated to OpenStack Neutron for persisting all network service state. Stores virtual netwo... | examples/catalog/data-store-services/data-store-service-neutron-database.yaml |
| STCK000001-DAR1 | Nova Database | data_store_service | data-at-rest, openstack, nova, database, mariadb, iaas | MariaDB database schema dedicated to OpenStack Nova for persisting all compute service state. Stores instance records... | examples/catalog/data-store-services/data-store-service-nova-database.yaml |
| STCK000007-DAR7 | OpenStack Shared Database | data_store_service | data-at-rest, openstack, heat, ironic, trove, sahara, ceilometer, database, mariadb, iaas | Shared MariaDB database cluster hosting the schemas for OpenStack services that do not warrant dedicated database obj... | examples/catalog/data-store-services/data-store-service-openstack-shared-database.yaml |
| STCK000006-DAR6 | Swift Storage Cluster | data_store_service | data-at-rest, openstack, swift, object-storage, iaas | OpenStack Swift object storage cluster providing durable, distributed storage for unstructured data. Consists of mult... | examples/catalog/data-store-services/data-store-service-swift-storage-cluster.yaml |
| 01KSF29JTP-9HYA | OpenStack API Load Balancer | edge_gateway_service | edge-gateway-service, openstack, load-balancer, haproxy, iaas | HAProxy load balancer co-located on OpenStack controller nodes. Distributes inbound API and dashboard traffic across... | examples/catalog/edge-gateway-services/edge-gateway-service-openstack-api-lb.yaml |
| STCK000001-SDP1 | OpenStack IaaS Platform | software_deployment_pattern | software-deployment-pattern, openstack, iaas, cloud, platform | Full-stack self-managed OpenStack Infrastructure-as-a-Service deployment pattern covering the complete control plane... | examples/catalog/software-deployment-patterns/sdp-openstack-iaas-platform.yaml |
| 01KSE5V73Z-Q0A0 | OpenStack Ops Console | product_component | product-component, openstack, operations, internal-tooling | Internal web-based operations console for platform engineering teams. Surfaces real-time service health, quota utiliz... | examples/catalog/product-components/product-component-openstack-ops-console.yaml |
| 01KSE5V73Z-RTKZ | Platform Audit Schema | data_component | data-component, openstack, audit, compliance | Relational schema tracking platform-level audit events — control plane API calls, administrative actions, quota chang... | examples/catalog/data-components/data-component-platform-audit-schema.yaml |
| 01KSF29JTP-DRHA | HAProxy Load Balancer Operational Architecture | decision_record | decision-record, openstack, load-balancer, haproxy | Documents the operational architecture decisions for the OpenStack API Load Balancer (HAProxy) — covering authenticat... | examples/catalog/decision-records/dr-haproxy-lb-operational-architecture.yaml |
| 01KSE5V73Z-CRZV | No WAF Required — OpenStack Is Internal-Only | decision_record | decision-record, openstack, security, network-boundary | Documents the accepted decision that a Web Application Firewall (WAF) is not required for the OpenStack IaaS platform... | examples/catalog/decision-records/dr-openstack-no-waf-internal-only.yaml |
| 01KSE5V73Z-DRSC | OpenStack Ops Console — Secrets Injection via Platform Secret Store | decision_record | decision-record, openstack, secrets, product-component | Documents the decision to inject application secrets into the OpenStack Ops Console at deploy time via the platform s... | examples/catalog/decision-records/dr-ops-console-secrets-injection.yaml |
| 01KSF29JTP-SESS | Nova Compute Service — Availability and Scaling Architecture | drafting_session | drafting-session, openstack, nova, compute, availability | Open authoring session to resolve architecture questions about Nova compute service availability posture and horizont... | examples/catalog/sessions/session-nova-compute-runtime-service.yaml |
| 01KSE5V73Z-VATZ | OpenStack HAProxy Edge Gateway Service | drafting_session | drafting-session, openstack, edge-gateway, haproxy | Incomplete authoring session for the HAProxy load balancer edge gateway service object. HAProxy fronts the OpenStack... | examples/catalog/sessions/session-openstack-ha-proxy-edge-service.yaml |

## Content Folder Counts

| Folder | YAML Count |
|---|---|
| framework/configurations/capabilities | 19 |
| framework/configurations/requirement-groups | 18 |
| framework/configurations/reference-architectures | 3 |
| framework/configurations/domains | 3 |
| examples/catalog/technology-components | 20 |
| examples/catalog/hosts | 2 |
| examples/catalog/runtime-services | 14 |
| examples/catalog/data-store-services | 7 |
| examples/catalog/edge-gateway-services | 1 |
| examples/catalog/reference-architectures | 0 |
| examples/catalog/software-deployment-patterns | 1 |
| examples/catalog/product-components | 1 |
| examples/catalog/data-components | 1 |
| examples/catalog/decision-records | 3 |
| examples/catalog/sessions | 2 |

## Templates

| Path | Purpose |
|---|---|
| templates/capability.yaml.tmpl | Reusable YAML authoring template. |
| templates/data-store-service.yaml.tmpl | Reusable YAML authoring template. |
| templates/decision-record.yaml.tmpl | Reusable YAML authoring template. |
| templates/drafting-session.yaml.tmpl | Reusable YAML authoring template. |
| templates/edge-gateway-service.yaml.tmpl | Reusable YAML authoring template. |
| templates/host.yaml.tmpl | Reusable YAML authoring template. |
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
| templates/workspace/llms.txt.tmpl | Company DRAFT Workspace |

## Validation

- Validate the example workspace: `python3 framework/tools/validate.py`
- Validate a company workspace: `python3 framework/tools/validate.py --workspace /path/to/workspace`
- Validate from inside a company repo: `python3 .draft/framework/tools/validate.py --workspace .`
- Regenerate browser after YAML changes: `python3 framework/tools/generate_browser.py`
- Regenerate this index after framework or YAML changes: `python3 framework/tools/generate_ai_index.py`
