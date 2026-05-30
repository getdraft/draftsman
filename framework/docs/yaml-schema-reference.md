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
| TechnologyComponent | `catalog/technology-components/` | [technology-component.schema.yaml](../schemas/technology-component.schema.yaml) | Discrete vendor product with vendor facts, capability references, and optional configuration-level network bindings. Company adoption lives on capability implementation mappings, not top-level lifecycle status. |
| Host | `catalog/hosts/` | [host.schema.yaml](../schemas/host.schema.yaml) | Operational platform built from an operating system, compute platform, and required host capabilities. |
| RuntimeService | `catalog/runtime-services/` | [runtime-service.schema.yaml](../schemas/runtime-service.schema.yaml) | Reusable runtime behavior such as web, app, cache, worker, messaging, or serverless runtime. |
| DataStoreService | `catalog/data-store-services/` | [data-store-service.schema.yaml](../schemas/data-store-service.schema.yaml) | Durable data behavior such as database, file, object, search, analytics, or storage. |
| EdgeGatewayService | `catalog/edge-gateway-services/` | [edge-gateway-service.schema.yaml](../schemas/edge-gateway-service.schema.yaml) | Boundary behavior such as WAF, firewall, API gateway, load balancer, ingress, proxy, or traffic inspection. |
| ReferenceArchitecture | `catalog/reference-architectures/` | [reference-architecture.schema.yaml](../schemas/reference-architecture.schema.yaml) | Reusable deployment pattern that SoftwareDeploymentPatterns can follow. |
| SoftwareDeploymentPattern | `catalog/software-deployment-patterns/` | [software-deployment-pattern.schema.yaml](../schemas/software-deployment-pattern.schema.yaml) | Intended product deployment architecture with service groups, deployable object references, business context, and topology metadata. |
| Product Service | `catalog/product-services/` | [product-service.schema.yaml](../schemas/product-service.schema.yaml) | First-party runtime behavior used inside a SoftwareDeploymentPattern, including internal process, API, dependency, and deployment variant details when needed. |
| DecisionRecord | `catalog/decision-records/` | [decision-record.schema.yaml](../schemas/decision-record.schema.yaml) | Risk, decision, mitigation, or follow-up record. |
| DraftingSession | `catalog/sessions/` | [drafting-session.schema.yaml](../schemas/drafting-session.schema.yaml) | Incomplete authoring state, generated objects, assumptions, and unresolved questions. |
| Capability | `configurations/capabilities/` | [capability.schema.yaml](../schemas/capability.schema.yaml) | First-class capability with a definition owner, optional company owner, and company-approved TechnologyComponent implementations. |
| RequirementGroup | `configurations/requirement-groups/` | [requirement-group.schema.yaml](../schemas/requirement-group.schema.yaml) | Unified authoring and validation requirements, including always-on definition requirements and workspace-activated compliance requirements. |
| Domain | `configurations/domains/` | [domain.schema.yaml](../schemas/domain.schema.yaml) | Groups capability UIDs for strategy navigation. |
| ObjectPatch | `configurations/object-patches/` | [object-patch.schema.yaml](../schemas/object-patch.schema.yaml) | Workspace overlay that deep-merges selected fields into a base framework object. |

PaaS, SaaS, appliance, and self-managed are `deliveryModel` values on RuntimeService, DataStoreService, and EdgeGatewayService objects. They are not
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
