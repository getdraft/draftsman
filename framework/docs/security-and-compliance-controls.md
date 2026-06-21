---
type: documentation
title: "Security And Compliance RequirementGroups"
description: "DRAFT treats compliance as an explicitly activated authoring and validation layer."
tags:
  - draft
  - documentation
  - security_and_compliance_controls
timestamp: 2026-06-12T21:06:02-07:00
---
# Security And Compliance RequirementGroups

## What This Layer Does

DRAFT treats compliance as an explicitly activated authoring and validation layer.
The layer is implemented with `requirement_group` objects using
`activation: workspace`.

The presence of a requirement group YAML file does not make it active. A company
activates the groups it architects against in `.draft/workspace.yaml`:

```yaml
requirements:
  activeRequirementGroups:
    - <soc2-requirement-group-uid>
    - <company-requirement-group-uid>
  requireActiveRequirementGroupDisposition: false
```

`requireActiveRequirementGroupDisposition: false` allows existing inventory to
migrate incrementally. Draftsman still asks active-group questions for new and
updated objects. Setting it to `true` makes validation require every approved
in-scope object to record disposition for every active workspace-mode group.

## Provider And Authority

A workspace-mode RequirementGroup may be authored by the framework, a company,
or a third-party provider. Use `provider` to identify who authored the DRAFT
mapping and `authority` to identify the external source or program.

Use `name`, `provider`, and `authority` to explain what the group represents.
The generated `uid` is only the stable machine reference used by
`activeRequirementGroups`, `requirementGroups`, and `requirementImplementations`.

The framework maintains its included DRAFT-provided mappings as starter
architecture aids. It does not claim that using them makes a company compliant
with SOC 2, NIST CSF, TX-RAMP, or any external program. The authority remains
the auditor, regulator, control owner, or company compliance program.

## Security Review Command

Use `/draft audit` when a CISO, security architect, security engineering
lead, compliance/GRC owner, or delegated risk owner wants to manage security
controls or audit architecture evidence.

The command supports these scopes:

- `/draft audit requirements` creates or updates company security
  RequirementGroups under `configurations/requirement-groups/`.
- `/draft audit satisfaction` defines or repairs the satisfaction mechanisms
  for each requirement.
- `/draft audit review` reviews current RequirementGroups and explains which
  catalog artifacts satisfy, fail, or weakly satisfy them.
- `/draft audit artifact [name]` audits a selected artifact, UID, path, or
  scoped set of artifacts against active security RequirementGroups.

Normal command work writes company controls and evidence to `configurations/`
and `catalog/`. It reads `.draft/framework/**` and optional provider packs, but
does not edit `.draft/framework/**` or `.draft/framework.lock` unless the user
is explicitly maintaining the framework itself.

Security RequirementGroups should prefer concrete evidence over prose. Valid
satisfaction mechanisms are `technologyComponent`,
`technologyComponentConfiguration`, `deploymentConfiguration`, `relationship`,
`internalComponent`, `decisionRecord`, and `field`. `architectureNotes` may
preserve rationale, but it is not completed evidence for an active security
requirement.

## Object-Level Evidence

Objects use `requirementGroups` to claim a workspace-mode group and
`requirementImplementations` to record evidence:

- `satisfied`: the object has a valid answer for the requirement
- `not-applicable`: the requirement permits N/A and the object records that disposition
- `not-compliant`: the gap is known and must remain visible until fixed

When a requirement has `relatedCapability`, the Draftsman resolves the capability
object, reads the company capability owner, and recommends `preferred` or
`existing-only` TechnologyComponent implementations as concrete choices before
asking the user. If `relatedCapability` is absent but a satisfaction mechanism
criteria names a capability, the Draftsman uses that capability for the same
lookup. This means compliance questions are grounded in the same capability
model as base object-definition questions.

Compliance interviews should cite the resolved requirement label and then offer
the company's current acceptable-use options. "Something else" is an exception
path that creates or identifies a candidate TechnologyComponent for capability
owner review; it is not treated as compliant evidence until the requirement can
be satisfied by an approved implementation or another valid mechanism.

## Overlap With Base Requirements

Workspace-mode control requirements often overlap with always-on base
requirements. This is intentional. A base requirement establishes that an
architecture object is complete and supportable; a control requirement
establishes that the object has a specific compliance disposition.

The requirements stay separate even when they share the same
`relatedCapability`. The Draftsman should ask once by capability, reuse the
same evidence where valid, and record each active control requirement's
disposition independently. The stricter requirement determines what additional
facts must be gathered. For example, base log management may only need the
logging destination, while a control requirement may also need retention,
review, alerting, or evidence-protection details.

Marking a control requirement `not-applicable` does not make the matching base
requirement disappear. It only records the disposition for that specific
workspace-mode requirement.

## Browser Behavior

The GitHub Pages browser is read-only. It shows RequirementGroups as framework
content and shows declared requirement groups on object detail pages. It does
not provide a runtime compliance display filter or selector. Activation is a
build-time workspace configuration decision in `.draft/workspace.yaml`.
