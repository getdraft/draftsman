---
type: documentation
title: "DRAFT Object Types"
description: "DRAFT object types are split into deployable objects and non-deployable"
tags:
  - draft
  - documentation
  - object_types
timestamp: 2026-06-12T21:06:02-07:00
---
# DRAFT Object Types

## Purpose

DRAFT object types are split into deployable objects and non-deployable
framework content. Deployable objects describe software and infrastructure that can eventually
become automation inputs. Non-deployable objects guide, govern, remember, or
explain how deployable systems are drafted.

PaaS, SaaS, appliance, and self-managed are delivery models. They are not
separate object types.

Object types are requirement scopes. Choose an object type from the artifact's
intrinsic behavior, because that type controls the base RequirementGroups the
Draftsman applies. Deployment context such as network zone, external exposure,
delivery model, data classification, capability, or followed ReferenceArchitecture
can add requirements without changing the object's intrinsic type.

## Engineering Objects

Engineering objects represent first-party software components that are authored
by the engineering team and deployed inside or on top of Shared Services Objects.

| Object type | YAML `type` | What it represents | Relationship |
|---|---|---|---|
| ProductComponent | `product_component` | A first-party deployable runtime unit — API, worker, scheduler, or service — that runs on a RuntimeService or Host. Product teams may declare component-owned runtime ports and dependencies in `runtimeSpec`. | Uses `runsOn` to reference the RuntimeService or Host it is deployed on. |
| DataComponent | `data_component` | A first-party data schema, dataset, or storage unit that lives inside a DataStoreService. | Uses `runsOn` to reference the DataStoreService it is deployed on. |
| SoftwareDeploymentPattern | `software_deployment_pattern` | The intended assembly of deployable objects for a product or product capability. | Defines the deployable package shape that automation can target. |
| ProductRegistration | `product_registration` | Advertises the formal registration contract linking a product engineering repository to the central `drafting-table` catalog. | Points to the product source repo URL and its decentralized `.draft/sdp.yaml` manifest. |

## Shared Services Objects

Shared Services Objects are service definitions: reusable infrastructure
standards that the infrastructure team defines and owns (including DR, backups
and HA). A product team consumes a definition; it does not place it. A
SoftwareDeploymentPattern places only ProductComponents and DataComponents. It
consumes a definition through `substrate` on a service group (runtime or host),
through `runsOn` on a DataComponent (data store), and through the slots of the
ReferenceArchitecture it follows (edge services such as load balancer, firewall
and ingress). External services are not definitions placed in a pattern; they are
relationship targets drawn as External interactions. Relationships are recorded
on components and instances, never on a definition. Ratcheted validation rules
`sdp-placement-types` and `relationship-definition-endpoint` check these two
boundaries.

### Deciding `serviceRole` for a shared-services object

Service owners decide which of two things an object under `shared-services` is, and record it with `serviceRole` so the ratcheted rules read it the same way:

- **definition** (the default for the folder): a standard solution that each product deploys for itself. Test: if two products use it, do they get two separate deployments with their own data and lifecycle? Then it is a definition. Examples: a DBMS service standard, Aurora PostgreSQL, DynamoDB, a caching service, an application runtime, a per-product queue. Patterns reach it through `substrate` or a data component's `runsOn`; relationships never name it. Teams that today record relationships to a definition move that fact to a data component and `runsOn` the next time they touch the pattern.
- **instance**: one running service that every consumer shares as it is. Test: if two products use it, do they talk to the same endpoint, operated by someone else? Then it is an instance, which the pattern model calls an external service. Examples: the identity provider, the secrets store, central logging and monitoring, the API gateway or mesh, a shared message broker or document database cluster, a SaaS product. Patterns name it as a relationship target and the diagram draws it under External interactions.

When in doubt: a definition answers "what should I deploy?"; an instance answers "what do I call?". Set `serviceRole: instance` explicitly on every external service that lives in the definitions folder; leave definitions unmarked or mark them `definition`.

| Object type | YAML `type` | What it represents | Deployable role |
|---|---|---|---|
| TechnologyComponent | `technology_component` | A discrete vendor product, agent, operating system, compute platform, software package, or appliance product at a specific product/version level. | Deployed as an ingredient inside Hosts and service objects. |
| Host | `host` | An operational platform that combines an operating system, compute platform, and required host capabilities such as authentication, logging, monitoring, and patching. | Deploys the runtime substrate for self-managed services. |
| RuntimeService | `runtime_service` | Reusable runtime behavior such as web, app, cache, worker, messaging, or serverless runtime. | Deploys runtime behavior on a Host or through PaaS, SaaS, or appliance delivery. |
| DataStoreService | `data_store_service` | Durable data behavior such as database, file, object, search, analytics, or storage. | Deploys persistence behavior on a Host or through PaaS, SaaS, or appliance delivery. |
| NetworkService | `network_service` | Network or traffic-control behavior such as routing, switching, segmentation, DNS, WAN transport, load balancing, ingress, WAF, firewalling, proxying, or traffic inspection. | Deploys network and traffic-control behavior that other objects connect through or are protected by. |
| ReferenceArchitecture | `reference_architecture` | A reusable deployment approach that SoftwareDeploymentPatterns may follow. | Documents a canonical assembly pattern. |

## Governance Objects

| Object type | YAML `type` | What it does |
|---|---|---|
| Capability | `capability` | Names an ability required by architecture and records company-approved TechnologyComponents for satisfying that ability. |
| RequirementGroup | `requirement_group` | Groups requirements used by the Draftsman during interviews and by validation after authoring. |
| Domain | `domain` | Names a planning area such as compute, observability, identity, or data; membership is generated from `Capability.domain`. |
| DecisionRecord | `decision_record` | Records an architecture decision, risk, exception, or rationale. |
| DraftingSession | `drafting_session` | Stores interview memory, source material, assumptions, unresolved questions, and generated work while drafting. |
| ObjectPatch | `object_patch` | A workspace overlay that changes selected fields on a framework-owned object without copying the full object. |

## Delivery Models

`runtime_service`, `data_store_service`, and `network_service` include a
`deliveryModel` field:

- `self-managed` means the company operates the service on a Host.
- `paas` means a provider-managed platform delivers the service inside the
  company's cloud or infrastructure boundary.
- `saas` means a vendor-managed service may operate outside the company's
  infrastructure boundary.
- `appliance` means the service maps directly to a vendor appliance or
  appliance-like product and must carry service-like operating capability
  answers because there is no Host wrapper.

## Draftsman Rules

When drafting deployable architecture, the Draftsman must:

1. Choose the correct object type from the behavior being modeled first.
2. For first-party runtime code: use `product_component` with `runsOn` pointing
   to a `runtime_service` or `host`.
3. For first-party data schemas or datasets: use `data_component` with `runsOn`
   pointing to a `data_store_service`.
4. For infrastructure-level services: choose `runtime_service`,
   `data_store_service`, or `network_service`, then choose the delivery model.
5. Do not choose an object type from placement words such as edge, perimeter,
   public, internal, tenant, or partner. Those are contextual requirement scopes
   expressed through SDP network zones, service groups, relationships,
   capabilities, ReferenceArchitectures, and DecisionRecords.

For example:

- Amazon RDS PostgreSQL is a DataStoreService with `deliveryModel: paas`.
- Snowflake is a DataStoreService with `deliveryModel: saas`.
- F5 BIG-IP WAF is a NetworkService with `deliveryModel: appliance`.
- A company-owned Java API is a ProductComponent that uses `runsOn` to
  reference the RuntimeService or Host it runs on.
- A company-owned database schema is a DataComponent that uses `runsOn` to
  reference the DataStoreService it lives in.

## Deprecated Object Types

`edge_gateway_service` is deprecated and is no longer a supported object type.
Existing objects of that type require triage and migration to the object type
that matches their intrinsic behavior:

- runtime or execution behavior migrates to RuntimeService
- durable data or persistence behavior migrates to DataStoreService
- network, traffic-control, ingress, WAF, firewall, load-balancing, proxy, DNS,
  WAN, routing, switching, or segmentation behavior migrates to NetworkService
- operating substrate behavior migrates to Host

Do not migrate an object based only on the word "edge". Edge, perimeter, public
exposure, partner boundary, and tenant boundary are deployment context. They can
apply requirements to any service object through SDP placement, RequirementGroup
applicability, and ReferenceArchitecture conformance.
