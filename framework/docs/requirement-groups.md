# RequirementGroups

## What A RequirementGroup Is

A RequirementGroup is the unified DRAFT requirement model. It replaces the old
RequirementGroup model and the separate RequirementGroups plus Control
Enforcement Profile model.

Every requirement is both:

- an authoring interview prompt for the Draftsman
- a validation rule for completed architecture objects

There is no translation layer between authoring and validation.

## Activation

RequirementGroups use one of two activation modes:

- `always`: base object-definition requirements that apply whenever the object
  type is in scope
- `workspace`: optional or compliance-driven requirement groups that a company
  explicitly activates in `.draft/workspace.yaml`

Workspace activation uses:

```yaml
requirements:
  activeRequirementGroups:
    - <soc2-requirement-group-uid>
  requireActiveRequirementGroupDisposition: false
```

The presence of a YAML file does not activate a workspace-mode group. Activation
is a build-time workspace decision.

## Applicability Scope

RequirementGroups can scope obligations by more than object type. Object type is
the intrinsic scope: a Host, RuntimeService, DataStoreService, NetworkService,
Capability, TechnologyComponent, DecisionRecord, ReferenceArchitecture, or
SoftwareDeploymentPattern has base questions that come from what it is.

Other obligations come from context. A service placed in a perimeter network
zone, exposed to partners, delivered as SaaS, processing regulated data, or
following a particular ReferenceArchitecture may have requirements that the
same intrinsic object would not have elsewhere. Those requirements should be
modeled through applicability conditions, SDP placement, capabilities, delivery
model, and followed ReferenceArchitectures rather than by creating a new object
type for the context.

ReferenceArchitectures are the companion to RequirementGroups for multi-object
answers. A RequirementGroup states the obligation; a ReferenceArchitecture can
show the approved composition of services, zones, relationships, and capabilities
that satisfies the obligation when one object cannot do so alone.

## Requirement Entries

A requirement entry includes:

- `id`
- `description`
- optional `relatedCapability`
- `requirementMode`
- `naAllowed`
- optional `applicability`
- `canBeSatisfiedBy`
- `minimumSatisfactions`
- `validAnswerTypes`

For external controls, DRAFT keeps the source control ID in
`externalControlId`. When a source control ID appears more than once, the DRAFT
requirement `id` is made unique while preserving `externalControlId`.

RequirementGroups can also declare `authority.shortName` for human citation.
The UID remains the machine reference, but generated UI and validation messages
use the short name to make controls readable:

- framework-native requirements render as `DRAFT Host / operating-system`
- framework-mapped external controls render as `SOC 2.CC7.security-monitoring`
- company-mapped external controls render as `CompanyPolicy.IAM.04`

Use `provider` for the organization that supplies the DRAFT mapping and
`authority` for the external or framework source that owns the requirement
language. For example, a company-owned policy mapping can have
`provider.name: Company Name` and `authority.shortName: CompanyPolicy`.

## Capability Demand

RequirementGroups are the demand signal for capabilities. When a requirement
expects an architecture capability such as authentication, logging, patching,
monitoring, encryption, or testing, it should name that capability with
`relatedCapability` or in a satisfaction mechanism criteria capability.

Approved Capability objects must be referenced by at least one RequirementGroup. Draft capabilities may exist before their requirement trace is finished,
but validation warns until the capability is tied back to a requirement.

## Object-Level Evidence

Architecture objects use:

- `requirementGroups` to record workspace-activated groups the object claims or
  explicitly addresses
- `requirementImplementations` to record `satisfied`, `not-compliant`, or
  `not-applicable` evidence for workspace-activated requirements

Always-on requirement groups are applied by object type. Workspace-mode groups
are applied only when activated and claimed by the object, or when strict
workspace disposition is enabled.

`internalComponents` entries are also evidence only when they map to an
applicable requirement. If an internal component is modeled for a reason that
does not directly satisfy an applicable requirement, the object must document
that reason in `architectureNotes` using `internalComponentRationales` or
`dependencyRationales`. External dependencies are modeled as standalone
`relationship` objects; use the `relationship` mechanism in requirement
groups to point to a relationship object where this object is the source
and the relationship carries the required capability.

## Draftsman Behavior

For every requirement with `relatedCapability`, the Draftsman resolves the
capability before asking the user. The Draftsman reads the capability owner,
then presents `preferred` implementations first and `existing-only` implementations
second as concrete multiple-choice options. The question should not be
open-ended unless the company has not mapped an implementation. If the
requirement does not use `relatedCapability`, the Draftsman should also inspect
the satisfaction mechanism criteria for a named `capability` and use the same
lookup.

The Draftsman may include "something else" as an exception path, but that path
is not an approved standard. If the user chooses it, the Draftsman drafts or
identifies the TechnologyComponent and records that the capability owner must
approve the lifecycle entry before it becomes acceptable use.

For SoftwareDeploymentPattern sessions, the Draftsman must also perform
composition closure. The SoftwareDeploymentPattern RequirementGroup governs
the root deployment pattern, but every referenced deployable object brings its
own RequirementGroups. A self-managed RuntimeService, DataStoreService,
or NetworkService must satisfy `DRAFT Service Behavior /
runtime-substrate` by referencing the Host Standard it runs on. If the Host is
unknown, the Draftsman asks from the workspace's approved Host Standards or
records the missing substrate as an unresolved DraftingSession question.
