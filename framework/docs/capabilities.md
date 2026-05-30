# Capabilities

## What A Capability Is

A Capability is a first-class framework object that names an architecture
outcome the Draftsman can reason about. Requirements can point to a capability,
and the Draftsman can then look up the company-approved TechnologyComponents
that implement it.

Capabilities use generated `uid` values like other first-class objects. Humans
should resolve them by name, alias, domain, or file path.

## Where Capabilities Live

Framework base capabilities live in:

```text
framework/configurations/capabilities/
```

Company workspaces add implementation mappings in:

```text
configurations/capabilities/
configurations/object-patches/
```

Framework base capability files intentionally ship with empty
`implementations` and a `definitionOwner`, not a company `owner`. The
definition owner maintains the capability vocabulary. The company owner is the
team accountable for deciding which vendor products may satisfy the capability.

When a workspace assigns any implementation lifecycle entries, the effective
capability must include `owner.team`. That owner is the decision authority for
moving TechnologyComponents through `candidate`, `preferred`, `existing-only`,
`deprecated`, and `retired`.

## Requirement Traceability

DRAFT is requirement-first. Requirements create demand for capabilities, and
capabilities provide the reusable vocabulary for satisfying that demand.

A Capability may be created as `stub` or `incomplete` while a RequirementGroup is
still being shaped. A Capability must not be marked `complete` until at least
one RequirementGroup requirement references it through `relatedCapability` or
a satisfaction mechanism criteria capability. The validator warns on incomplete
orphan capabilities and fails complete orphan capabilities.

This preserves a many-to-many model: one requirement can point to a capability,
and one capability can satisfy requirements in multiple groups. A capability
does not belong to exactly one RequirementGroup.

## Capability Lookup Procedure

When a requirement names `relatedCapability`, the Draftsman must use this lookup
procedure:

1. Resolve the RequirementGroup requirement.
2. Read `relatedCapability`.
3. Resolve the capability object from the effective model, checking workspace
   overlays before framework base.
4. Read `owner` to identify the company decision authority.
5. Read `implementations`.
6. Prefer implementations with `lifecycleStatus: preferred`, then `existing-only`.
7. Present the referenced TechnologyComponent or named configuration as a
   concrete interview choice.
8. If no implementation exists, ask which TechnologyComponent should satisfy
   the capability and flag that the capability owner must approve the lifecycle
   entry.

This keeps interviews grounded in the company's current acceptable-use
technology decisions.

When approved implementations exist, the Draftsman should ask a multiple-choice
question instead of an open-ended one. Candidate, deprecated, and retired
implementations are not default choices. "Something else" can be offered only as
an exception path that requires capability-owner review before it is accepted as
standard.

## Implementation Entries

Each implementation entry contains:

- `ref`: TechnologyComponent UID
- `lifecycleStatus`: company disposition for using that TechnologyComponent
- optional `configuration`: named TechnologyComponent configuration
- optional `notes`

The framework keeps vendor support facts on TechnologyComponents in
`vendorLifecycle`. Company adoption lives here, on the capability mapping.
Implementation entries must reference TechnologyComponents, not deployable
service objects or running systems, because lifecycle disposition is a decision
about a discrete vendor product and version. If a SaaS platform or managed
service is governed by the lifecycle program, model the vendor product as a
TechnologyComponent and compose the service-facing architecture separately as
a deployable object.

## Acceptable Use Technology View

The generated browser includes an Acceptable Use Technology view. It groups
capability implementation mappings by domain and shows the capability owner,
contact, lifecycle status, TechnologyComponent, vendor/product/version,
configuration, and notes. This is the human-readable technology lifecycle table
for a company workspace.

If a user wants a TechnologyComponent added, retired, or moved between
`candidate`, `preferred`, `existing-only`, `deprecated`, and `retired`, the capability
owner listed in that view is the contact for the change request.
