---
type: documentation
title: "SoftwareDeploymentPatterns"
description: "A SoftwareDeploymentPattern is a declaration that a specific product is intended"
tags:
  - draft
  - documentation
  - software_deployment_patterns
timestamp: 2026-06-12T21:06:02-07:00
---
# SoftwareDeploymentPatterns

## What A SoftwareDeploymentPattern Is

A SoftwareDeploymentPattern is a declaration that a specific product is intended
to be distributed and deployed according to a particular pattern.

Unlike a ReferenceArchitecture, which is generic, a SoftwareDeploymentPattern
is tied to a named product. It answers the question “what does this product
deploy?” rather than “what does this class of solution usually require?”

## What A SoftwareDeploymentPattern Contains

The defining structure in a SoftwareDeploymentPattern is no longer a flat deployment list. A SoftwareDeploymentPattern is
organized around:

- `scalingUnits`
- `serviceGroups`
- `businessContext`
- `notes`
- `decisionRecords`

Each service group contains deployable object references. Inter-service
dependencies are modeled as standalone relationship objects in
`catalog/relationships/`, not as inline fields on the service group.

Within those service groups, the primary visual objects in the topology are the
deployed object entries themselves.

Each of those entries must declare `diagramTier` as one of:

- `presentation`
- `application`
- `data`
- `utility`

`diagramTier` is the band a component sits in on the generated diagrams. The
renderer should not guess service placement from names or references when the
manifest can state the intended architecture directly.

`scalingUnits` is optional. Use it only when a set of service groups truly
shares a scaling boundary. If a service group does not participate in a scaling
unit, model it directly rather than forcing it into a placeholder group.

## YAML Shape

The canonical schema notes for SoftwareDeploymentPatterns live in [software-deployment-pattern.schema.yaml](../schemas/software-deployment-pattern.schema.yaml).

At minimum, a SoftwareDeploymentPattern includes:

- `uid`
- `type: software_deployment_pattern`
- `name`
- `catalogStatus`
- `lifecycleStatus`

The main SoftwareDeploymentPattern structure is:

- optional `followsReferenceArchitecture`
- optional `businessContext`
- optional `notes`
- optional `scalingUnits`
- optional `serviceGroups`
- optional `decisionRecords`

Each scaling unit includes:

- `name`
- `type`
- optional `instanceCount`
- optional `notes`

Each service group includes:

- `name`
- `deploymentTarget`
- optional `scalingUnit`
- optional `deployableObjects` (ProductComponents and DataComponents only; a runtime or host goes in `substrate`, a data store in the DataComponent's `runsOn`)
Each deployable object entry should declare:

- `ref`
- optional `diagramTier`
- optional `riskRef`
- optional `notes`

## Business Context

SoftwareDeploymentPatterns may include `businessContext` so a company can
quickly see which business pillar, portfolio, or product family a pattern
belongs to. This is intentionally workspace-owned. The framework defines the
field and validation behavior, but the company declares the actual taxonomy in
`.draft/workspace.yaml`.

Example:

```yaml
businessContext:
  ownerNode: team.absence-time
  pillar: business-pillar.human-capital-management
  additionalPillars:
    - business-pillar.student-management
  productFamily: Absence & Time
  notes: Primary ownership follows the HCM portfolio; student-management impact
    exists through district-facing attendance workflows.
```

If `.draft/workspace.yaml` defines `businessTaxonomy.pillars` or a business hierarchy (inline or federated), validation checks that `businessContext.pillar` (if declared) uses a declared pillar ID or a node in the hierarchy of type `pillar`.

If the workspace requires a business pillar (via `businessTaxonomy.requireSoftwareDeploymentPatternPillar: true`), every SoftwareDeploymentPattern must satisfy the pillar requirement. This can be satisfied in two ways:
1. Setting `businessContext.pillar` directly to a valid pillar ID.
2. Setting `businessContext.ownerNode` pointing to a node in the business hierarchy (inline or federated) that has a node of type `pillar` in its lineage path.

## What `followsReferenceArchitecture` Means

The `followsReferenceArchitecture` field tells the reader which ReferenceArchitecture the deployment claims to follow.

This field is metadata only. It is useful because it says whether the product is aligned to a recognized pattern, but it is not itself a deployed object and should not be rendered as a node in a deployment diagram.

If no suitable ReferenceArchitecture exists yet, that gap should be made
explicit through an architectural decision entry rather than hidden.

## RequirementGroup Expectations

The SoftwareDeploymentPattern RequirementGroup is the deployment-reality checklist. It requires the architect to
document:

- the selected ReferenceArchitecture, or why no applicable ReferenceArchitecture exists
- the deployed service-group structure
- the deployment boundary or execution context used by those service groups
- the product availability requirement
- any product-specific interactions beyond the component deployable object baseline
- the governing data classification
- the deployment-level failure domain
- any intentional deviations from the selected ReferenceArchitecture, or an explicit statement
  that none exist

The SoftwareDeploymentPattern checklist is only the root checklist. DRAFT
drafting must also close the composition graph below it. Every deployable object
referenced by a service group brings its own RequirementGroups. A
self-managed RuntimeService, DataStoreService, or NetworkService
must identify the Host Standard that provides its execution substrate. If the
Draftsman does not know whether a service is self-managed, PaaS, SaaS,
or appliance, that delivery model is the next architecture question.

## RA-Guided Drafting

ReferenceArchitectures are used as pattern guidance for the Draftsman. The
Draftsman should infer the likely deployment shape, search for candidate
ReferenceArchitectures, and explain the closest match in plain language. The
user should not be expected to know or name the ReferenceArchitecture UID.

If no ReferenceArchitecture covers the shape, the Draftsman should continue
drafting the SoftwareDeploymentPattern as a candidate and record the missing
ReferenceArchitecture as a gap. It should not invent a ReferenceArchitecture
match or proceed as if the pattern is approved.

## Composition Closure

Composition closure means every deployable object referenced by the SoftwareDeploymentPattern is resolved enough to make deployment intent explicit.

For each service group, the Draftsman should:

1. Identify the deployable objects.
2. Resolve whether each object already exists in the catalog.
3. Classify the delivery model for each service object.
4. For self-managed service objects, select or ask for the Host Standard.
5. For PaaS, SaaS, or appliance objects, record why no
   self-managed Host is required.
6. Record unresolved substrate choices in a DraftingSession rather than
   assuming a platform.

## Current State Versus Deployed Topology

Deployed object entries describe the target topology. They should not be used
as a shorthand way to restate current production state. Current state
capabilities belong in DecisionRecords and notes.

## Structure Rules

`serviceGroup` is the primary structural and visual container. It answers what
role a cluster of deployed components plays in the product.

`deploymentTarget` is metadata on the service group. It answers what deployment
boundary or execution context matters for understanding ownership, isolation,
and operational responsibility.

A deployment target is not inherently a cloud region and it is not necessarily
a fixed approved-list value. The right answer depends on the architecture. It
may be an AWS account, Kubernetes cluster, namespace, data center, customer
site, SaaS tenant context, environment boundary, per-customer deployment model,
or another execution context that explains how the service group is operated.
Only ask for a specific geographic region when the source material names one
or an active company/control requirement makes region part of the architecture
answer.

If `.draft/workspace.yaml` declares `vocabulary.deploymentTargets`, validation
checks `serviceGroups[].deploymentTarget` against that list. In `advisory` mode,
non-standard values produce warnings; in `gated` mode, they produce failures.
`owner-interview-required` remains a valid drafting sentinel for unknown
deployment targets, and `drafting-interview-required` can be used as the
general interview-required sentinel.

`diagramTier` places deployed objects into one of four bands:

- `presentation`
- `application`
- `data`
- `utility`

`scalingUnit` is secondary and optional. It should be used only when a set of
service groups truly scales together. It is not a generic visual container.

If two services share a deployment target but play different roles, they should
still live in different service groups. Do not use deployment targets as group
names. Good group names describe function, such as `Web Edge Services`,
`Application Services`, or `Data Services`.

When the deployment boundary is not known, do not substitute a guessed cloud
region or generic placeholder. Preserve the uncertainty through the normal
drafting workflow and revisit it with the accountable owner.

Inter-service dependencies are modeled as relationship objects in
`catalog/relationships/`, not as inline fields inside the SDP. A relationship
object carries a `source` UID, a `target` UID (or `externalTarget` for systems
with no catalog object), a `label`, `technology`, and optional `capabilities`
that the validator uses as requirement evidence. The generated diagrams draw
relationship objects whose both endpoints are deployed in the same SDP as
connection edges, and the pattern detail page shows them in its Connections
section.

## Interfaces, Listeners And The Edge Device Chain

Who a component talks to is recorded by the team that owns the thing being
described. The split is by altitude and by owner.

| Owner | Records | Where |
|---|---|---|
| Product team | `interfaces` (name, protocol, optional path, authentication model) | On a `product_component`, and optionally on a `data_component` |
| Product team | `targetInterface` | On a `relationship`: the interface of the target it uses |
| Infrastructure team | `listeners` (name, protocol, port) | On `runtime_service`, `data_store_service`, `network_service` and `host` definitions |
| Infrastructure team | `fills` | On a reference architecture deployable object entry whose `slot` is an edge slot: the `network_service` that fills it |
| Product team (exception) | `exposedThrough` | On a service group: a different device chain, a list of `network_service` uids in order, or `none` |

The ratcheted rule `relationship-target-interface` requires a relationship whose
target is a product component to carry a `targetInterface` that names one of its
`interfaces`. Existing relationships are baselined in
`.draft/validation-baseline.yaml`; one you change must be fixed. Data component
targets and `externalTarget` are exempt. A data component without `interfaces`
has one implicit surface named `data`. A relationship derived from a
`runtimeSpec.dependencies[]` entry cannot carry `targetInterface`; its
`interface` string is used when it equals an interface name of the target, and
otherwise only as a protocol hint. A `targetInterface` that names a surface the
target does not have is an error and is never baselined. Where the target has no
`interfaces` list to check against (a definition, or an `externalTarget`) it is
a warning.

### What each view shows

- **Application view.** One entrance on the top edge of a box per Listener
  object it owns (`owner.ref`), ordered by port, then protocol, then endpoint
  path, then uid; an edge enters through the listener its `targetListener` names
  (a runtime dependency's `interface` may name one too). A box that owns no
  Listener objects keeps one entrance per declared interface, in declared order,
  and an edge enters through the interface its `targetInterface` names. Either
  way an edge naming no entrance of its target enters the first. The
  Deployment view uses the same entrances. The Application view never shows a
  port and never shows a device.
- **Deployment view.** Each connection is labelled with the resolved port chain.
  The target's port comes from the component's own inbound `runtimeSpec.ports`
  entry, then the listener of its substrate (a data component uses the listener
  of the store it `runsOn`), matched to the interface's protocol family, and
  failing a match the substrate's single listener. Each device hop contributes its
  listener matching the protocol family, else its single listener, else no port.
  Examples: `SQL 5432`, `gRPC 8092` (a gRPC interface served by a port recorded
  as `HTTP/2` prints the interface's word), `https 443 → http 8080`; device
  listeners print as recorded. The line reads the chain alone when no technology
  is recorded or it equals the chain's first protocol word (case-insensitive),
  else `technology · chain` (`PostgreSQL wire protocol · SQL 5432`).
  A relationship whose `technology` and target interface protocol are in
  different families is a warning.

### The edge device chain

A group is exposed when it sets `exposedThrough`, or when it has no override and
the pattern follows a reference architecture that fills edge slots. The edge
slots are `firewall`, `web-application-firewall`, `load-balancer`, `api-gateway`
and `ingress`, drawn in that order. They are not all protective: a firewall or
web application firewall meets a protection requirement, a load balancer an
availability or performance requirement, an ingress or gateway a routing
requirement. They appear in the deployment view, never the application view,
because the group has a north door and those requirements apply to it.

- The chain is drawn at the top of the exposed group's own container, whether or
  not any drawn connection enters it. No caller or arrow is drawn for it; the
  device is there because the group is exposed.
- A connection whose source is outside the deployment target (unplaced, in the
  outside lane, or in another target) enters through the target group's chain;
  the label lists each hop's port and the callout adds `via <device>`.
- Same-deployment-target traffic never takes the hop.
- A data tier (all data components) is not exposed by the slot default;
  `exposedThrough: none` draws nothing.

`exposedThrough` is either the literal `none` on its own, a network_service
definition uid, or a list of such uids in chain order. Validation fails (it is
not ratcheted) on an unknown uid, a non-network_service, a network_service
instance (`serviceRole: instance`, or outside the service definitions folder
when the workspace names one), `none` inside a list, an empty list, or a uid
listed twice.

`fills` on a reference architecture entry is checked the same way: it must sit
on one of the five edge slots and name a network_service definition, and when
the entry names a `capability` the definition (or its technology component)
must provide it. Each violation fails validation; none is ratcheted.

The precedence above (`exposedThrough: none`, then an explicit chain, then the
reference architecture's filled edge slots except for a data tier) is resolved
in one place, `framework/tools/exposure.py`. The deployment diagram and the
browser's exposure column both read it, so they always agree. The resolver is
lenient: it leaves out values that are not network services, so a pattern that
fails validation still renders.

To fix a deployment page that lacks a port or a device: declare `listeners` on
the definition; fill the slot with `fills` on the reference architecture entry
(or set `exposedThrough`); and name the target interface on the relationship.

### Deliberately not recorded

Hostnames, IP addresses, environment endpoints, security-group rules,
certificates and health checks are runbook and infrastructure-code material.
DRAFT has no field for them.

## How The Detail Page Should Read

The pattern detail page opens with an Application section and a Deployment
section, each carrying a generated figure from the pattern's diagram page. The
Application figure is the logical view: components and data components in
`presentation`, `application`, `data` and `utility` bands. The Deployment figure
is the deployment view: service groups and network-zone lanes under their
deployment targets. Both show all connections by default; hovering, focusing or
pinning a box brings its connections forward while the others fade. Each section
has a Fit width / Actual size toggle (fit by default, actual size scrolls) and an
Open full page link to the standalone diagram page. A pattern with no generated
diagram page shows a one-sentence note instead. The Service Groups rows show each group's exposure (the device names, or `not exposed`), and the Connections table has an Interface column. The sections below them (Service
Groups, Decisions, Connections, Tier Variants, Metadata) carry the recorded
detail. The figures are service-first placement views.

- `serviceGroup` is the primary container because it answers what a set of
  deployed components does.
- `deploymentTarget` stays visible as metadata on that group.
- `diagramTier` places deployed objects into the
  `presentation`, `application`, `data`, or `utility` band.
- `scalingUnit` is secondary and optional. It should be treated as an overlay
  or highlight concept that answers which services scale together, not as the
  primary layout primitive.

That means one deployment target can host multiple service groups, and each
group can still place its runtime components into different bands. Scaling
units can be highlighted across multiple groups without taking over the base
layout.

## Long-Term Placement

The v1 catalog contains example SoftwareDeploymentPatterns in this central repository because the framework needs real examples.

Long term, that is not the target operating model. Product-specific SoftwareDeploymentPatterns belong closest to the product that owns them, which usually
means the product repository. The central catalog should define reusable
building blocks and reference patterns. Product repos should eventually own the
declarations that map those deployable objects to live product estates.

## Partial SoftwareDeploymentPattern Drafting

When a SoftwareDeploymentPattern interview is incomplete, do not force every unresolved note into the
SoftwareDeploymentPattern itself. Use a DraftingSession to hold:

- source pages and interview context
- provisional assumptions that let the SoftwareDeploymentPattern validate
- unresolved questions that still need answers
- next steps for the follow-up pass

That lets the SoftwareDeploymentPattern stay deployable and reviewable while the open questions remain
easy to revisit later.

## FAQ

### Does every product need a SoftwareDeploymentPattern?

In the long run, yes, if the product has meaningful architecture that needs to be reviewed, supported, or governed. A missing SoftwareDeploymentPattern should usually be treated as a gap to close, not as proof that the framework does not apply.

### What if my product does not fit any existing ReferenceArchitecture?

Do not force the product into an obviously wrong pattern. Treat that as a signal. Either the product is a legitimate exception that needs to be documented clearly, or the catalog is missing a ReferenceArchitecture that should exist.

## Migrating Inline Connections to Relationship Objects

Earlier versions of DRAFT allowed service-to-service connections to be declared
inline inside `serviceGroup.connections`. That field has been removed. The
validator will now fail any SDP that still contains inline connections.

For each inline connection entry, create a relationship file in
`catalog/relationships/` following this shape:

```yaml
schemaVersion: '1.0'
uid: <generated>
type: relationship
name: <source-name> calls <target-name>
catalogStatus: complete
source: <from-uid>
target: <to-uid>
label: calls
technology: <protocol>        # was: connection.protocol
direction: synchronous        # synchronous / asynchronous / event
flow: outbound
```

Then remove the `connections` list from the service group. The browser and
validator both resolve relationship objects automatically — no reference back
to the SDP is needed on the relationship file itself.
