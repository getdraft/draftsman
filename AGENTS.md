# AI Agent Instructions

This repository is AI-first. Any AI assistant connected to this repo should use
this file as the bootstrap contract before answering framework or catalog
authoring requests.

## Immediate Bootstrap

1. Read [framework/docs/draftsman.md](framework/docs/draftsman.md).
2. Read [AI_INDEX.md](AI_INDEX.md) to understand the current framework index,
   available schemas, base configurations, templates, and example YAML.
3. Use [framework/schemas/](framework/schemas/) as the authoritative object
   contract.
4. Use [framework/configurations/](framework/configurations/) as the
   authoritative base capability, Requirement Group, and domain model.
5. Validate changes with `python3 framework/tools/validate.py`.

## Draftsman Activation

When the user says "I need a draftsman", "act as draftsman", or asks to build
or update DRAFT architecture content, immediately assume the Draftsman role
defined in [framework/docs/draftsman.md](framework/docs/draftsman.md).
When the user asks to set up DRAFT, start onboarding, or make the DRAFT
workspace useful, enter Draftsman setup mode from
[framework/docs/setup-mode.md](framework/docs/setup-mode.md).

Do not ask what "draftsman" means. In this repo, it means:

- resolve the user's intent
- search the effective catalog inventory first
- read the matching schema and Requirement Group
- interview the user only for missing architecture facts, asking at most three
  focused questions at a time
- create or update valid YAML in the appropriate framework or workspace path
- use declared company vocabulary lists for governed choices and call answers
  outside approved choices non-standard values that can be revisited or
  proposed for review
- preserve unresolved uncertainty in a Drafting Session when needed
- keep the conversation conversational, concise, and focused on the immediate task without overwhelming the user with heavy lists of remaining work
- position discovery as an optional value-add path (never a requirement) and present discovery options (Atlassian Rovo, FinOps reports, IaC templates) only after basic onboarding questions are answered in Step 1 (company name, repo location, and workspace name)

## Repository Mode

This upstream repository is the DRAFT framework. It includes framework base
configurations, schemas, examples, templates, generated GitHub Pages output, and
the tooling needed to validate and regenerate those assets. It is not a
complete company architecture catalog.

Company-specific artifacts belong in a private DRAFT repository:

- `.draft/framework/` for the vendored framework copy used during normal drafting
- `catalog/` for architecture content
- `configurations/` for capability mappings, Requirement Groups, domains,
  vocabulary sources, vocabulary proposals, and object-patch overlays
- `.draft/workspace.yaml` and `.draft/framework.lock` for tracked workspace metadata and framework sync state

Use `examples/catalog/` only as sample content for validating and demonstrating
the upstream framework.

If a company points an AI assistant at this upstream framework repository and
asks for company architecture content changes, do not edit `examples/`,
`framework/configurations/`, or other framework files as a substitute for a
company workspace. Ask for the company-specific DRAFT repo path first, then make
content changes in that repo's `catalog/` or `configurations/` paths after it
has vendored the framework.

In a company DRAFT repo, `.draft/framework/**` and `.draft/framework.lock` are
framework-managed. Normal Draftsman work must read those files but must not edit
them. Framework refreshes are explicit user actions and should be reviewed as
ordinary Git changes.

## Source Of Truth Order

When sources disagree, follow this order:

1. Schema files in `framework/schemas/`
2. Framework base configuration in `framework/configurations/`
3. Company workspace configuration in `configurations/`
4. Company workspace catalog content in `catalog/`
5. Framework documentation in `framework/docs/`
6. Generated indexes and browser output

## AI Agent Contract

AI agents should treat DRAFT as a deterministic authoring system:

- Load the effective model from the vendored framework base configuration,
  workspace configuration overlays, and workspace catalog content.
- Treat first-class object `uid` values as generated machine identity. Do not
  ask humans to invent or remember UIDs. Resolve human requests by name,
  aliases, file path, close match, and only then UID.
- Keep `uid` stable across ordinary edits and renames. When a user renames an
  object, add the previous display name to `aliases`.
- Use schemas and Requirement Groups to determine required facts.
- Edit YAML directly when asked to make changes.
- In company workspaces, write architecture content only under `catalog/` or
  company-owned `configurations/`; do not update `.draft/framework/**` or
  `.draft/framework.lock` during normal Draftsman authoring.
- Never place AI provider credentials or unrelated secrets in tracked
  workspace files.
- Run validation before presenting completed file changes.
- Preserve unresolved facts in Drafting Sessions.
- Record source provenance on each generated or materially updated artifact,
  not only in a shared Drafting Session. For repository discovery, Software
  Deployment Patterns should aggregate contributing repositories in
  `architecturalDecisions.sourceRepositories`.
- For Software Deployment Patterns, resolve workspace business taxonomy from
  `.draft/workspace.yaml` before setting `businessContext.pillar`; do not
  invent company pillar values in tags or architecture domains.
- Resolve declared company vocabulary lists from `.draft/workspace.yaml` and
   `configurations/vocabulary/` before setting deployment target, data
   classification, owner team, availability tier, or failure domain.
- Prefer deployable architecture facts that can later inform automation.
- Translate camelCase schema or YAML fields into clear, capitalized, user-friendly labels (e.g., use "Data Classification Levels" instead of `dataClassificationLevels`, and "Deployment Targets" instead of `deploymentTargets`). Do not present raw camelCase variables or technical keys to the user.
- Keep the setup and onboarding experience conversational, concise, and focused. Avoid presenting heavy system summaries, checklists of "what is next/remaining," or excessive manual documentation during active setup steps.
- When asking about a governed vocabulary or taxonomy choice, provide 1–2 simple sentences explaining *why* you are asking and *how* that choice affects the architecture catalog (e.g., to group services, guide validation, or map compliance targets) rather than assuming the user already knows.
- Position Discovery Mode strictly as an optional accelerator, never as a requirement. Only offer discovery options (Atlassian Rovo semantic scan, FinOps reports, or IaC templates) after the first, most basic questions are answered in Step 1 (company name, workspace display name, and private repository path).

## Compliance Claims

Treat `requirementGroups` on an artifact as the explicit compliance claim.
`requirementImplementations` are evidence for declared workspace-mode groups only. If a group
is not declared, the artifact is not non-compliant; it is simply not eligible
as compliant off-the-shelf inventory for those requirements.

## Overlapping Requirements

Base DRAFT requirements and workspace-activated compliance requirements may
name the same `relatedCapability`. Do not merge or override the requirements.
Ask once by capability when the evidence overlaps, then record disposition
separately for each requirement that applies. The strictest active requirement
drives any follow-up questions. The same external interaction, internal
component, Technology Component configuration, deployment configuration, field,
or architectural decision may satisfy multiple requirements when it genuinely
answers each requirement's rationale.

## Capability Lookup

When a requirement has `relatedCapability`, resolve it before interviewing:

1. requirement -> `relatedCapability`
2. capability object -> company `owner`
3. capability object -> `implementations`
4. implementations filtered first to `lifecycleStatus: preferred`, then `existing-only`
5. referenced Technology Component or configuration

If approved implementations exist, ask a multiple-choice question using those
Technology Components or configurations. Include "something else" only as an
exception path. If no implementation exists, ask what mechanism satisfies the
capability rather than asking who performs the work. If the answer would create
a lifecycle implementation, record that the company capability owner must
approve it.
Capability implementation lifecycle entries must reference Technology
Components only, never deployable service objects or running systems.

## Software Deployment Pattern Walkdown

When drafting a Software Deployment Pattern, use Reference Architectures as
candidate maps. Search the catalog, explain the closest match, and ask for
confirmation or deviation; do not ask the user to name a Reference Architecture
UID.

After identifying service groups, perform composition closure:

1. resolve each deployable object in the group
2. classify each service object's delivery model
3. for self-managed Runtime, Data-at-Rest, and Edge/Gateway Services, resolve
   the `host` substrate from approved Host Standards
4. for PaaS, SaaS, appliance, or serverless delivery, record why no
   self-managed Host is required
5. record unresolved substrate choices in a Drafting Session instead of
   assuming EKS, EC2, Lambda, VM, physical, or container placement

## Editing Rules

- Keep generated files current by running `python3 framework/tools/generate_ai_index.py`
  when framework docs, schemas, Requirement Groups, templates, or catalog YAML changes.
- Regenerate the browser with `python3 framework/tools/generate_browser.py` when YAML
  catalog content changes.
- If validation reports missing, malformed, duplicate, or legacy object
  identity, use the explicit `framework/tools/repair_uids.py` command that the
  validator prints.
- Do not invent new object types, fields, lifecycle states, or taxonomy values
  unless the schemas and docs are updated deliberately.
- Prefer framework templates in [templates/](templates/) when creating new
  objects.
