# YAML Schema Reference

This page is the quickest way to understand how to build a valid YAML object in
DRAFT.

The framework uses two sources of truth for YAML validation:

- `framework/schemas/` for the authoritative object contract of every
  first-class type
- `framework/tools/validate.py` for executable relationship, capability, and
  RequirementGroup checks

## Object Families

| Object type | Folder | Schema source | Notes |
|---|---|---|---|
| TechnologyComponent | `catalog/shared-services/technology-components/` | [technology-component.schema.yaml](../schemas/technology-component.schema.yaml) | Discrete vendor product with vendor facts, capability references, and optional configuration-level network bindings. Company adoption lives on capability implementation mappings, not top-level lifecycle status. |
| Host | `catalog/shared-services/hosts/` | [host.schema.yaml](../schemas/host.schema.yaml) | Operational platform built from an operating system, compute platform, and required host capabilities. |
| RuntimeService | `catalog/shared-services/runtime-services/` | [runtime-service.schema.yaml](../schemas/runtime-service.schema.yaml) | Reusable runtime behavior such as web, app, cache, worker, messaging, or serverless runtime. |
| DataStoreService | `catalog/shared-services/data-store-services/` | [data-store-service.schema.yaml](../schemas/data-store-service.schema.yaml) | Durable data behavior such as database, file, object, search, analytics, or storage. |
| NetworkService | `catalog/shared-services/network-services/` | [network-service.schema.yaml](../schemas/network-service.schema.yaml) | Network or traffic-control behavior such as routing, switching, segmentation, DNS, WAN transport, load balancing, ingress, WAF, firewalling, proxying, or traffic inspection. |
| ReferenceArchitecture | `catalog/governance/reference-architectures/` | [reference-architecture.schema.yaml](../schemas/reference-architecture.schema.yaml) | Reusable deployment pattern that SoftwareDeploymentPatterns can follow. |
| SoftwareDeploymentPattern | `catalog/engineering/software-deployment-patterns/` | [software-deployment-pattern.schema.yaml](../schemas/software-deployment-pattern.schema.yaml) | Intended product deployment architecture with service groups, deployable object references, business context, and topology metadata. |
| ProductComponent | `catalog/engineering/product-components/` | [product-component.schema.yaml](../schemas/product-component.schema.yaml) | First-party runtime behavior used inside a SoftwareDeploymentPattern, including internal process, API, dependency, and deployment variant details when needed. |
| DecisionRecord | `catalog/governance/decision-records/` | [decision-record.schema.yaml](../schemas/decision-record.schema.yaml) | Risk, decision, mitigation, or follow-up record. |
| DraftingSession | `catalog/governance/sessions/` | [drafting-session.schema.yaml](../schemas/drafting-session.schema.yaml) | Incomplete authoring state, generated objects, assumptions, and unresolved questions. |
| Capability | `configurations/capabilities/` | [capability.schema.yaml](../schemas/capability.schema.yaml) | First-class capability with a definition owner, optional company owner, and company-approved TechnologyComponent implementations. |
| RequirementGroup | `configurations/requirement-groups/` | [requirement-group.schema.yaml](../schemas/requirement-group.schema.yaml) | Unified authoring and validation requirements, including always-on definition requirements and workspace-activated compliance requirements. |
| Domain | `configurations/domains/` | [domain.schema.yaml](../schemas/domain.schema.yaml) | Names a strategy navigation area; capability membership is generated from each Capability object's `domain` field. |
| ObjectPatch | `configurations/object-patches/` | [object-patch.schema.yaml](../schemas/object-patch.schema.yaml) | Workspace overlay that deep-merges selected fields into a base framework object. |

PaaS, SaaS, appliance, and self-managed are `deliveryModel` values on RuntimeService, DataStoreService, and NetworkService objects. They are not
separate object types.

## Requirement And Capability Flow

When a requirement names `relatedCapability`, resolve:

1. RequirementGroup requirement
2. `relatedCapability`
3. capability object
4. company capability `owner`
5. capability `implementations`
6. recommended TechnologyComponent or configuration

Workspace-mode RequirementGroups are activated in `.draft/workspace.yaml` under
`requirements.activeRequirementGroups`.

## Practical Rule

If you are unsure how to build a YAML object correctly:

1. Open the relevant guide in `framework/docs/`.
2. Open the matching file in `framework/schemas/`.
3. Resolve applicable RequirementGroups and capabilities.
4. Run `python3 framework/tools/validate.py`.
