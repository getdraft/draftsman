# ReferenceArchitectures

## Framework and Community RAs

The DRAFT framework ships a set of baseline ReferenceArchitectures in
`framework/configurations/reference-architectures/`. These are vendored into
company workspaces alongside requirement groups and capability definitions. Like
compliance requirement group starter packs (SOC 2, NIST CSF, TX-RAMP), they are
opt-in: an SDP adopts an RA by declaring `followsReferenceArchitecture`, and a
company is not required to use any particular framework RA.

| RA | UID | Use when |
|---|---|---|
| Two-Tier Client/Data | `8Q79XMD460-MQ5A` | A client, static site, or low-code front end talks directly to a managed data service without a separately operated application tier. |
| Three-Tier Web Application | `01KS8N4KR2-3TWA` | The deployment serves web or API traffic to external users through a presentation, application, and data tier. |
| Serverless Event-Driven | `01KS8N4KR4-SVED` | The deployment has no persistent compute tier; all logic executes in response to events, API calls, or scheduled triggers. |
| Containerized Microservices | `BX3H6KC1J1-P765` | Independently deployable services run on a governed container orchestration platform with explicit service-to-service controls. |
| Event-Driven Integration | `GM7YJ3ZSA0-WHSN` | Producers and consumers coordinate through asynchronous queues, streams, event buses, or pub/sub topics. |
| Strangler Migration | `R10A3TXM3E-RFC3` | A legacy system and replacement services coexist while traffic or data responsibility moves incrementally. |
| Multi-Tenant SaaS | `01KS8N4KR3-MTSA` | The product serves multiple customer tenants from shared infrastructure with explicit isolation requirements. |

Companies may author their own RAs in `configurations/reference-architectures/`
inside the company workspace. These are private to the workspace and not vendored
upstream.

Companies may also contribute reusable RAs back to the DRAFT community library.
The contribution path is the same as for compliance requirement group starter
packs: generalize the RA by replacing company-specific UIDs with `objectType` and
`capability` slot declarations, remove internal names, then submit a pull
request.

## Capability Slot Model

Framework and community ReferenceArchitectures should describe **capability
slots**, not company-specific catalog objects. A slot is a role that the target
SoftwareDeploymentPattern must address, such as:

- API Gateway or WAF at the presentation boundary
- Serverless Function Runtime or Application Runtime for compute
- Data Persistence, Object Storage, Messaging, or Caching for state and integration
- Service Mesh, Traffic Management, Log Management, APM, or Health Monitoring for operations

Each `serviceGroups[].deployableObjects[]` entry may use:

- `objectType` — the kind of service-layer object required (`runtime_service`,
  `data_store_service`, `network_service`, etc.).
- `capability` — the Capability UID the selected service object must provide.
- `diagramTier` — where the slot lands in the SDP diagram (`presentation`,
  `application`, `data`, or `utility`).
- `ref` — an optional concrete catalog object UID, normally used only in company
  workspaces where the RA deliberately pins to an approved service object.

For portable starter RAs, prefer `objectType` + `capability` and omit `ref`.
This lets the framework say "this pattern needs an API Gateway" while each
company decides which `NetworkService` object satisfies the API Gateway
capability.

Example slot:

```yaml
serviceGroups:
- name: Ingestion
  deployableObjects:
  - objectType: network_service
    capability: 01KT0V5MCV-3A6F   # API Gateway
    diagramTier: presentation
    notes: API gateway or event boundary for inbound requests.
```

## Populating Slots From A Company Catalog

When drafting an SDP that follows an RA, the Draftsman should resolve each slot
against the effective catalog:

1. Find service objects of the requested `objectType` whose `capabilities` list
   contains the requested `capability`.
2. Prefer objects with `lifecycleStatus: preferred`; fall back to
   `existing-only` only when needed and call out the gap.
3. Never propose `deprecated` or `retired` objects for new SDP work.
4. If no service object exists for an infrastructure-layer slot, scaffold a
   placeholder service object with `catalogStatus: stub` and the appropriate
   Shared Services owner role instead of making the engineering-owned SDP deploy
   a raw `TechnologyComponent`.

This keeps role ownership separated: Engineering owns the product SDP and
ProductComponents; Shared Services owns reusable runtime, data, network, and
operations service objects.

## What A ReferenceArchitecture Is

A ReferenceArchitecture is a deployment pattern. It tells application
teams which reusable building blocks and pattern-level decisions they should
adopt when they need a supported set of non-functional outcomes such as high
availability, recoverability, security posture, or scaling behavior.

ReferenceArchitectures sit beside RequirementGroups in governance. A
RequirementGroup defines the obligation and acceptable evidence; a
ReferenceArchitecture shows a reusable compliant arrangement when the answer
requires multiple objects, relationships, zones, or capabilities. For example,
a perimeter-zone web requirement may require traffic to pass through an approved
WAF NetworkService before it reaches a RuntimeService. That cannot be proven by
one field on the RuntimeService; it is a pattern and relationship question.

If an engineer asks, "what deployment pattern should I adopt so my application
gets the right operational qualities here," the answer belongs in a ReferenceArchitecture. If
the engineer asks, "what does a specific product actually deploy today," the
answer belongs in a SoftwareDeploymentPattern.

## YAML Shape

ReferenceArchitectures are validated by
[`framework/tools/validate.py`](../tools/validate.py) and the ReferenceArchitecture RequirementGroup.

At minimum, a ReferenceArchitecture YAML should include:

- `uid`
- `type: reference_architecture`
- `name`
- `catalogStatus`
- `lifecycleStatus`
- `serviceGroups`

Most ReferenceArchitectures also include `description`, `patternType`,
`applicableDefinitionChecklist`, `architectureNotes`, and `constraints`.

## Lifecycle Policy

The `lifecycleStatus` on a ReferenceArchitecture describes the company's
position on using that deployment pattern:

- `preferred` for cloud-forward or target-state patterns that should be used for
  new architecture
- `candidate` for patterns being evaluated before they become preferred
- `existing-only` for legacy patterns that remain supported for existing systems
- `deprecated` for patterns that should be migrated away from
- `retired` for patterns being actively retired

A ReferenceArchitecture that includes a TechnologyComponent whose
`vendorLifecycle.extendedSupportEnd` date has passed must be marked
`deprecated`. The validator follows the pattern's concrete `ref` entries through
the referenced deployable objects to the underlying TechnologyComponents and
enforces this rule.

A ReferenceArchitecture that includes a TechnologyComponent whose
`vendorLifecycle.mainstreamSupportEnd` date has passed but whose
`extendedSupportEnd` date has not passed is in extended support. The default
position for these patterns is `deprecated`. A company may mark the pattern
`existing-only` while extended support is active, but it must document that exception
in `architectureNotes.lifecycleRationale`. Extended-support TechnologyComponents must not appear in a `preferred` ReferenceArchitecture.

## What `serviceGroups` Means

The core field in a ReferenceArchitecture is `serviceGroups`. Each group clusters the required
services that work together in the deployment pattern. Inside each group, the
pattern declares:

- the deployable object slots that must exist
- the capabilities those slots must provide
- the `diagramTier` each deployable object belongs to
- any group-local interactions or notes that matter to the pattern

This does more than list ingredients. It shows how the pattern is meant to be
assembled using the same tiered service-group grammar the SoftwareDeploymentPattern uses later.

## Why A ReferenceArchitecture Is Never A Node In A SoftwareDeploymentPattern Diagram

A ReferenceArchitecture is not a deployed thing. It is a deployment-pattern declaration.

A SoftwareDeploymentPattern may reference a ReferenceArchitecture UID in
`followsReferenceArchitecture`, but that field is metadata about conformance,
not a deployed runtime element. The visual question for a SoftwareDeploymentPattern is "what deployable objects are deployed here?" The guidance question is "which
ReferenceArchitecture does this solution claim to follow?"

## Why ReferenceArchitectures Matter

ReferenceArchitectures create shared vocabulary and deployment guidance across engineering teams.

- Infrastructure teams can see which deployment patterns are supported.
- Product teams can see which reusable components and pattern decisions they are expected to adopt.
- Architecture can make non-functional expectations explicit instead of relying on oral tradition.

A ReferenceArchitecture makes it possible to say, "this is the standard deployment pattern the
framework recognizes for this class of workload."

## FAQ

### What is the difference between a ReferenceArchitecture and a SoftwareDeploymentPattern?

A ReferenceArchitecture is generic and a SoftwareDeploymentPattern is specific. A ReferenceArchitecture says what reusable building
blocks and pattern-level decisions should be adopted to achieve a supported
deployment posture. A SoftwareDeploymentPattern says which building blocks a specific product
actually deploys.

### Can a product deviate from its ReferenceArchitecture?

Yes, but that should be treated as an explicit exception rather than invisible drift. If a product cannot follow the pattern, engineers should either document the exception clearly in the SoftwareDeploymentPattern, propose a new ReferenceArchitecture, or revise the existing ReferenceArchitecture.

### Who owns ReferenceArchitectures?

ReferenceArchitectures are architecture-owned artifacts, usually written in
collaboration with infrastructure, product, database, security, and platform
teams so that they reflect both desired deployable objects and actual
supportable patterns.
