# Company Vocabulary

Company vocabulary lists are optional governed lists in `.draft/workspace.yaml`.
They give the Draftsman approved choices for common architecture questions and
give validation a way to detect drift without forcing every company to finish
governance on day one.

Undeclared lists preserve current free-text behavior. Declared lists can start
in `advisory` mode and move to `gated` mode when the company is ready.

## Modes

Each vocabulary list supports:

- `mode: advisory` - validation reports non-standard values as warnings.
- `mode: gated` - validation reports non-standard values as failures.

Use advisory during onboarding, migration, and discovery. Use gated when the
company wants CI and pull requests to block values that have not been accepted
into the official list.

Example:

```yaml
vocabulary:
  deploymentTargets:
    mode: advisory
    reviewBy: 2026-07-31
    values:
      - id: aws-us-east-2
        name: AWS US East 2
        type: cloud-region
        provider: aws
        status: approved
```

`status` defaults to `approved`. A value with `status: proposed` is visible to
humans and AI agents, but it is not an approved standard value.

## Standard Value States

DRAFT uses these terms:

- Standard value: declared in the vocabulary with `status: approved`.
- Proposed standard value: declared with `status: proposed`.
- Non-standard value: present in an object field but not approved in the
  declared vocabulary list.
- Interview-required value: an explicit unresolved marker such as
  `drafting-interview-required`; for Software Deployment Pattern deployment
  targets, `owner-interview-required` remains valid during drafting.

## Supported Lists

### Deployment Targets

Deployment targets describe execution boundaries such as cloud regions, cloud
accounts, Kubernetes clusters, colocations, SaaS tenants, customer sites, or
edge locations.

```yaml
vocabulary:
  deploymentTargets:
    mode: advisory
    values:
      - id: aws-us-east-2
        name: AWS US East 2
        type: cloud-region
        provider: aws
        notes: Primary AWS region.
      - id: colo-ohio-mcocne
        name: Ohio Colo MCOCNE
        type: colocation
```

When declared, validation checks
`software_deployment_pattern.serviceGroups[].deploymentTarget`.
`owner-interview-required` and `drafting-interview-required` remain explicit
drafting sentinels.

### Data Classification Levels

```yaml
vocabulary:
  dataClassificationLevels:
    mode: advisory
    values:
      - id: restricted
        name: Restricted
        description: Highest sensitivity data.
      - id: confidential
        name: Confidential
```

When declared, validation checks
`architectureNotes.dataClassification` on Software Deployment Patterns and
deployable service objects.

### Teams

```yaml
vocabulary:
  teams:
    mode: advisory
    values:
      - id: platform-engineering
        name: Platform Engineering
        contact: platform-engineering@example.com
```

When declared, validation checks `owner.team` wherever an object declares an
owner. `owner.contact` remains free text.

### Availability Tiers

```yaml
vocabulary:
  availabilityTiers:
    mode: advisory
    values:
      - id: tier-1-mission-critical
        name: Tier 1 Mission Critical
        target: "99.95%"
        notes: Incident response required.
```

When declared, validation checks
`architectureNotes.availabilityRequirement` on Software Deployment
Patterns and deployable service objects.

### Failure Domains

```yaml
vocabulary:
  failureDomains:
    mode: advisory
    values:
      - id: per-product
        name: Per Product
      - id: shared-platform
        name: Shared Platform
```

When declared, validation checks `architectureNotes.failureDomain` on
Software Deployment Patterns and deployable service objects.

### Connection Protocols

```yaml
vocabulary:
  connectionProtocols:
    mode: advisory
    values:
      - id: REST
        name: REST
      - id: gRPC
        name: gRPC
      - id: AMQP
        name: AMQP
      - id: JDBC
        name: JDBC
      - id: WebSocket
        name: WebSocket
```

Or reference the framework source file:

```yaml
vocabulary:
  connectionProtocols:
    mode: advisory
    source: .draft/framework/configurations/vocabulary/connection-protocols.yaml
```

When declared, validation checks `relationship.technology` on relationship
objects. The Draftsman presents approved values as a multiple-choice list
during connection elicitation. Values not in the list are recorded as
non-standard and may be submitted as vocabulary proposals.

The framework ships a default source file at
`configurations/vocabulary/connection-protocols.yaml` covering REST, gRPC,
AMQP, JDBC, SQL, WebSocket, HTTPS, GraphQL, and other. Companies may extend
this list via vocabulary proposals without editing the framework source.

### Network Zones

```yaml
vocabulary:
  networkZones:
    mode: advisory
    values:
      - id: public
        name: Public
        description: Internet-facing services and edge components.
      - id: private
        name: Private
        description: Internal application and data services.
      - id: management
        name: Management
        description: Operational and administrative services.
```

When declared, validation checks `networkZones[].id` and
`serviceGroups[].deployableObjects[].networkZone` on Software Deployment
Patterns. Zone IDs must be lowercase alphanumeric with hyphens.

The Draftsman populates this list during the first SDP session that needs
network zones. It asks one yes/no question ("does your deployment use distinct
network zones?"), then presents the common zone patterns from
`configurations/vocabulary/network-zone-patterns.yaml` as a multiple-choice
list. The selected pattern expands into the SDP's `networkZones` list and
establishes the zone-to-tier default mapping used for all subsequent zone
assignment questions.

Once zones are recorded in the workspace vocabulary, the Draftsman offers them
as approved choices in all future SDP sessions without repeating the setup
questions.

## Source Files

Small lists can live inline in `.draft/workspace.yaml`. Larger lists can live in
company-owned source files:

```yaml
vocabulary:
  deploymentTargets:
    mode: advisory
    source: configurations/vocabulary/deployment-targets.yaml
```

The source file shape is:

```yaml
schemaVersion: "1.0"
type: vocabulary
vocabulary: deploymentTargets
name: Deployment Targets
values:
  - id: aws-us-east-2
    name: AWS US East 2
    status: approved
```

## Non-Standard Value Proposals

When an engineer gives a real answer that is not in a declared list, the
Draftsman should not hide it. It should ask whether to revisit later or submit a
vocabulary proposal.

If the user chooses a proposal, the Draftsman records the object with the
non-standard value and writes a `vocabulary_proposal` file under
`configurations/vocabulary-proposals/`:

```yaml
schemaVersion: "1.0"
type: vocabulary_proposal
name: Add GCP Deployment Target
vocabulary: deploymentTargets
proposalKind: non-standard-value
status: proposed
proposedId: gcp-us-central1
proposedName: GCP US Central 1
fieldRefs:
  - object: 01KQS0TF53-SDMP
    path: serviceGroups[0].deploymentTarget
    value: gcp-us-central1
rationale: Required for the new GCP deployment boundary.
```

Company workspaces include an optional GitHub Actions workflow that can
materialize these proposal files into official vocabulary entries and open a
pull request. Humans still review the pull request and decide whether the value
becomes `approved`, remains `proposed`, or is rejected.

## Draftsman Interview Rules

Before asking a governed question, the Draftsman must read
`.draft/workspace.yaml` and any configured vocabulary sources.

When a declared list covers the question:

1. Offer the approved values as choices.
2. Mention proposed values separately if they are relevant.
3. Do not silently invent a new standard value.
4. If the answer is not approved, call it a non-standard value.
5. Ask whether to revisit later or submit a vocabulary proposal.

When no list is declared, ask openly and note that the workspace has not
declared a governed vocabulary list for that answer yet.
