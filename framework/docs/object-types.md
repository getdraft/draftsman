# DRAFT Object Types

## Purpose

DRAFT object types are split into deployable architecture and non-deployable
framework content. Deployable objects describe architecture that can eventually
become automation inputs. Non-deployable objects guide, govern, remember, or
explain how deployable architecture is drafted.

PaaS, SaaS, appliance, and self-managed are delivery models. They are not
separate object types.

## Engineering Objects

Engineering objects represent first-party software components that are authored
by the engineering team and deployed inside or on top of Architecture Objects.

| Object type | YAML `type` | What it represents | Relationship |
|---|---|---|---|
| ProductComponent | `product_component` | A first-party deployable runtime unit — API, worker, scheduler, or service — that runs on a RuntimeService, Host, or Edge/Gateway Service. | Uses `runsOn` to reference the RuntimeService, Host, or EdgeGatewayService it is deployed on. |
| DataComponent | `data_component` | A first-party data schema, dataset, or storage unit that lives inside a DataStoreService. | Uses `runsOn` to reference the DataStoreService it is deployed on. |
| Software Deployment Pattern | `software_deployment_pattern` | The intended assembly of deployable objects for a product or product capability. | Defines the deployable package shape that automation can target. |

## Architecture Objects

Architecture Objects are reusable infrastructure-level deployable objects that
engineering objects run on or connect to.

| Object type | YAML `type` | What it represents | Deployable role |
|---|---|---|---|
| Technology Component | `technology_component` | A discrete vendor product, agent, operating system, compute platform, software package, or appliance product at a specific product/version level. | Deployed as an ingredient inside Hosts and service objects. |
| Host | `host` | An operational platform that combines an operating system, compute platform, and required host capabilities such as authentication, logging, monitoring, and patching. | Deploys the runtime substrate for self-managed services. |
| Runtime Service | `runtime_service` | Reusable runtime behavior such as web, app, cache, worker, messaging, or serverless runtime. | Deploys runtime behavior on a Host or through PaaS, SaaS, or appliance delivery. |
| DataStoreService | `data_store_service` | Durable data behavior such as database, file, object, search, analytics, or storage. | Deploys persistence behavior on a Host or through PaaS, SaaS, or appliance delivery. |
| Edge/Gateway Service | `edge_gateway_service` | Boundary behavior such as WAF, firewall, API gateway, load balancer, ingress, proxy, or traffic inspection. | Deploys traffic control behavior at a product or network boundary. |
| Network Service | `network_service` | Non-perimeter network fabric infrastructure such as switches, routers, SDN controllers, and WAN appliances that create or manage network topology. | Deploys network fabric infrastructure that other objects connect through. |
| Reference Architecture | `reference_architecture` | A reusable deployment approach that Software Deployment Patterns may follow. | Documents a canonical assembly pattern. |

## Non-Deployable Architecture Objects

| Object type | YAML `type` | What it does |
|---|---|---|
| Capability | `capability` | Names an ability required by architecture and records company-approved Technology Components for satisfying that ability. |
| Requirement Group | `requirement_group` | Groups requirements used by the Draftsman during interviews and by validation after authoring. |
| Domain | `domain` | Groups capabilities into a planning area such as compute, observability, identity, or data. |
| Decision Record | `decision_record` | Records an architecture decision, risk, exception, or rationale. |
| Drafting Session | `drafting_session` | Stores interview memory, source material, assumptions, unresolved questions, and generated work while drafting. |
| Object Patch | `object_patch` | A workspace overlay that changes selected fields on a framework-owned object without copying the full object. |

## Delivery Models

`runtime_service`, `data_store_service`, and `edge_gateway_service` include a
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
   to a `runtime_service`, `host`, or `edge_gateway_service`.
3. For first-party data schemas or datasets: use `data_component` with `runsOn`
   pointing to a `data_store_service`.
4. For infrastructure-level services: choose `runtime_service`,
   `data_store_service`, or `edge_gateway_service`, then choose the delivery model.

For example:

- Amazon RDS PostgreSQL is a DataStoreService with `deliveryModel: paas`.
- Snowflake is a DataStoreService with `deliveryModel: saas`.
- F5 BIG-IP WAF is an Edge/Gateway Service with `deliveryModel: appliance`.
- A company-owned Java API is a ProductComponent that uses `runsOn` to
  reference the RuntimeService or Host it runs on.
- A company-owned database schema is a DataComponent that uses `runsOn` to
  reference the DataStoreService it lives in.
