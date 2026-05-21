# Framework Overview

This page is the high-level object map for DRAFT. For the complete object type
contract, see [DRAFT Object Types](object-types.md).

For a step-by-step company adoption path, see
[Company Onboarding Tutorial](company-onboarding.md).

If an AI assistant is using this repo directly to author content, start with
[Draftsman instructions](draftsman.md).

## Engineering Objects

Engineering objects represent first-party software components authored by the
engineering team. They are deployed inside or on top of Architecture Objects.

| Object Type | Purpose |
|---|---|
| ProductComponent | A first-party deployable runtime unit — API, worker, scheduler, or service — that uses `runsOn` to reference the RuntimeService, Host, or EdgeGatewayService it is deployed on. |
| DataComponent | A first-party data schema, dataset, or storage unit that uses `runsOn` to reference the DataStoreService it is deployed on. |
| Software Deployment Pattern | The intended assembly of deployable objects for a product or product capability. |

## Architecture Objects

Architecture objects are reusable infrastructure-level services that engineering
objects run on or connect to.

| Object Type | Purpose |
|---|---|
| Technology Component | A discrete vendor product, agent, operating system, compute platform, software package, or appliance product at a specific product/version level. |
| Host | An operational platform that combines an operating system, compute platform, and required host capabilities. |
| Runtime Service | Reusable runtime behavior such as web, app, cache, worker, messaging, or serverless runtime. |
| DataStoreService | Durable data behavior such as database, file, object, search, analytics, or storage. |
| Edge/Gateway Service | Boundary behavior such as WAF, firewall, API gateway, load balancer, ingress, proxy, or traffic inspection. |
| Reference Architecture | A reusable deployment approach that Software Deployment Patterns may follow. |

## Non-Deployable Architecture

| Object Type | Purpose |
|---|---|
| Capability | A first-class architecture capability such as authentication, log management, operating system, or patch management. Frameworks and providers define the vocabulary; company capability owners approve Technology Component implementations. |
| Requirement Group | The unified requirement model for DRAFT. Always-on groups define required questions for object completeness. Workspace-mode groups represent explicitly activated compliance or company requirements. |
| Domain | A strategy grouping for related capabilities, used by the Draftsman to navigate from requirement to capability to approved implementation. |
| Decision Record | A record of a known risk, accepted decision, mitigation path, or follow-up attached to architecture content. |
| Drafting Session | A machine-readable work-in-progress record that captures partial authoring state, generated objects, assumptions, and unresolved follow-up questions. |
| Object Patch | A workspace overlay that changes selected fields on a framework-owned object without copying the full object. |

## Delivery Models

PaaS, SaaS, appliance, and self-managed describe how a Runtime Service,
DataStoreService, or Edge/Gateway Service is delivered. They are not
separate object types.
