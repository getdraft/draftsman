---
type: documentation
title: "How To Add Objects"
description: "The fastest way to add a new object correctly is to decide what kind of thing you are modeling before you write YAML."
tags:
  - draft
  - documentation
  - how_to_add_objects
timestamp: 2026-06-12T21:06:02-07:00
---
# How To Add Objects

## Start With The Right Question

The fastest way to add a new object correctly is to decide what kind of thing you are modeling before you write YAML.

Are you documenting:

- a vendor product
- a reusable architecture pattern
- a software deployment pattern
- an object-definition checklist

Many mistakes happen because engineers skip that decision and start writing fields immediately.

## AI-First Authoring Workflow

When an AI assistant is connected to this repo, it should start from
[AGENTS.md](../../AGENTS.md), then use [AI_INDEX.md](../../AI_INDEX.md) for
repository discovery.

When creating a new object, prefer the closest file in
[templates/](../../templates/) as a starting point, then replace placeholders
with real architecture facts and run validation. Template files use the
`.yaml.tmpl` extension so they are not treated as live catalog objects.

In a company workspace, generated architecture content belongs under
`catalog/`. Company configuration and extension content belongs under
`configurations/`. The selected framework version lives under
`.draft/framework/`. Edit company YAML directly, keep changes small and
reviewable, and run validation before treating the work as complete.

First-class objects use generated `uid` values for machine identity. Do not ask
humans to create semantic object IDs. Use names, aliases, and paths for human
conversation, and use the repair tool when validation reports a missing,
malformed, duplicate, or legacy identity:

```bash
python3 .draft/framework/tools/repair_uids.py --workspace .
```

## Dependency Rationale Rule

Every `internalComponents` entry must either directly satisfy an applicable
RequirementGroup requirement or have an explicit architectural decision
explaining why the dependency is modeled. Direct satisfaction means the entry
matches an applicable requirement's `canBeSatisfiedBy` mechanism, or a valid
`requirementImplementations` entry points at that mechanism.

External dependencies (outbound calls, data reads, platform integrations) are
modeled as standalone `relationship` objects in the catalog. Set `source` to
the calling object's UID and `target` to the receiving object's UID (or
`externalTarget` for systems with no catalog representation).

When an internal component is present for a reason outside the applicable
requirements, document the reason under:

- `architectureNotes.internalComponentRationales` for locally composed
  TechnologyComponents
- `architectureNotes.dependencyRationales` when one shared rationale is
  clearer than separate buckets

Use the component `ref`, `enabledBy`, role, or capability ID as the rationale
key. If the dependency is actually intended to satisfy a requirement, update the
entry with the matching capability or add valid `requirementImplementations`
evidence instead of adding rationale.

## Add A TechnologyComponent

1. Decide whether the object is an Operating System, Compute Platform, Software, or Agent TechnologyComponent.
2. Create the YAML file in `catalog/shared-services/technology-components/`.
3. Add or repair the generated `uid`.
4. Fill in the shared base fields: `uid`, `type`, `name`, `description`, `version`, `catalogStatus`, `owner`, and `tags`.
5. Fill in the required TechnologyComponent fields: `vendor`, `productName`, `productVersion`, and `classification`.
6. Add `capabilities` if the TechnologyComponent itself satisfies reusable host capabilities.
7. Add `configurations` if a named TechnologyComponent configuration satisfies reusable host capabilities.
8. Fill in any remaining TechnologyComponent-specific metadata such as vendor lifecycle and optional platform dependency.
9. If the TechnologyComponent is classified as `agent`, make sure any deployable object that uses it also documents the corresponding external interaction or an architectural decision exception under `architectureNotes.agentInteractionExceptions`.
10. Run validation.

TechnologyComponents should be specific. If you cannot name the product version clearly, you probably are not ready to create the object yet.

## Add A Host

1. Create the file under `catalog/shared-services/hosts/`, `catalog/shared-services/runtime-services/`, or `catalog/shared-services/data-store-services/`.
2. Reference the Operating System and Compute Platform TechnologyComponents explicitly.
3. Add any Agent TechnologyComponents or other internal components that physically live on the host.
4. Create relationship objects for identity, logging, security, monitoring, patching, or other platform dependencies.
5. Add `architectureNotes` when the host must answer a RequirementGroup or compliance question that is not expressed directly in the object, or when an internal component exists for a reason outside the applicable Host requirements.
6. Add `requirementGroups` only for RequirementGroups the host explicitly claims to
   satisfy, then add valid `requirementImplementations` for every applicable
   control in each declared profile.
7. Use generated UIDs when adding explicit `requirementGroups`.
8. Run validation.

## Add A RuntimeService

1. Create the file under `catalog/shared-services/hosts/`, `catalog/shared-services/runtime-services/`, or `catalog/shared-services/data-store-services/`.
2. Reference exactly one `host` and one `primaryTechnologyComponent`; the
   primary TechnologyComponent is the service's required function component,
   not an optional dependency that needs separate rationale.
3. Create relationship objects for service-level dependencies that go beyond the host baseline.
4. Document the decisions that describe scaling, health, secrets handling, and, for DataStoreServices, durability and protection.
   DataStoreServices must document backup strategy, backup platform, RTO,
   and RPO; create a relationship object pointing to a separate backup platform
   or use `architectureNotes.backup.platform` for provider-managed backups.
5. Use `architectureNotes` whenever the service must answer a RequirementGroup or compliance question that is not expressed directly in the object, or when an internal component exists for a reason outside the applicable service requirements.
6. Add `requirementGroups` only for RequirementGroups the service explicitly claims
   to satisfy, then add valid `requirementImplementations` for every applicable
   control in each declared profile.
7. Set `requirementGroups` to the correct RequirementGroup list.
8. Run validation.

## Add A ReferenceArchitecture

1. Create the file under `catalog/governance/reference-architectures/`.
2. Add or repair the generated `uid`; choose a clear human `name`.
3. Populate `serviceGroups` with the reusable building blocks that define the deployment pattern.
4. Set `diagramTier` on every deployable object entry and cluster related functionality into the right service group.
5. Add `architectureNotes` that explain what non-functional qualities the pattern is meant to deliver and how.
6. Make sure the file satisfies the ReferenceArchitecture RequirementGroup by documenting `patternType`, tiered service groups, and deployment-quality decisions.

A ReferenceArchitecture should be generic enough to guide many products, not just one.

## Add A SoftwareDeploymentPattern

1. Create the file under `catalog/engineering/software-deployment-patterns/`.
2. Add or repair the generated `uid`; choose a product-focused human `name`.
3. Add `businessContext.pillar` when the workspace declares business pillars in `.draft/workspace.yaml`.
4. Set `followsReferenceArchitecture` if the product aligns with an existing ReferenceArchitecture.
5. Define any `scalingUnits` needed to express replicable or shared deployment boundaries.
6. Build the manifest out through `serviceGroups`, then place ProductComponents, Hosts, RuntimeServices, DataStoreServices, and NetworkServices into the appropriate groups.
   ProductComponent is not a starting-point RequirementGroup object; use it here only when the SoftwareDeploymentPattern needs to express a distinct first-party runtime-behavior component deployed on a substrate.
7. Set `diagramTier` on every deployable object entry using one of `presentation`, `application`, `data`, or `utility`.
8. Use `intent` only when the architect is explicitly deviating from the ReferenceArchitecture or when no ReferenceArchitecture exists.
9. Add product-level `architectureNotes`, including availability requirement and data classification, so the SoftwareDeploymentPattern satisfies the SoftwareDeploymentPattern RequirementGroup.

## Add A DraftingSession

1. Create the file under `catalog/governance/sessions/`.
2. Add or repair the generated `uid`; choose a name that describes the drafting work.
3. Record the target object type in `primaryObjectType` and, if it already exists, `primaryObjectUid`.
4. Add the source material that informed the current work under `sourceArtifacts`.
5. Record the YAML objects that were created, proposed, or stubbed under `generatedObjects`.
6. Record every unresolved question explicitly, including the current best guess and impact when useful.
7. Add `nextSteps` so the session can be resumed later without re-reading the entire intake.
8. Run validation.

## Add A RequirementGroup

1. Create the file in `configurations/requirement-groups/` for company-owned
   requirements, or in `.draft/providers/<provider>/configurations/requirement-groups/`
   for a third-party pack.
2. Set `activation: always` for base object-definition requirements or
   `activation: workspace` for explicitly activated compliance or company
   requirements.
3. Define `appliesTo`.
4. Add requirements with `id`, `description`, `requirementMode`, `naAllowed`,
   `canBeSatisfiedBy`, `minimumSatisfactions`, and `validAnswerTypes`.
5. Use `relatedCapability` when the requirement should be grounded in approved
   company TechnologyComponent implementations.
6. Use `externalControlId` and `externalReference` when the requirement comes
   from an external control source.
7. Set `authority.shortName` when the group maps external or named framework
   controls so generated UI can cite labels like `SOC 2.CC7` or
   `CompanyPolicy.IAM.04` instead of raw requirement group UIDs.
8. Activate workspace-mode groups in `.draft/workspace.yaml` only when the
   company wants Draftsman and validation to use them for authoring.
9. Run validation.

## Add Object-Level Compliance Claims

1. Add `requirementGroups` only for the workspace-mode groups the artifact
   explicitly claims and that are active for the workspace.
2. Add one `requirementImplementations` entry for every requirement in each
   declared group that applies to the artifact's DRAFT scope.
3. Use `not-applicable` only when the requirement allows `N/A`.
4. Do not add `requirementImplementations` for groups the artifact has not
   declared.
5. Confirm every modeled internal component and external interaction either
   satisfies a claimed or always-on requirement, or has dependency rationale in
   `architectureNotes`.
6. Run validation.

Artifacts with no declared group are unclaimed inventory, not failed inventory.
They should not be selected as compliant off-the-shelf building blocks when a
solution requires a specific requirement group.

## Run The Tools

Validate locally:

```bash
python3 framework/tools/validate.py
```

Validate a company workspace:

```bash
python3 framework/tools/validate.py --workspace /path/to/company-draft-workspace
```

From inside a company repo, use the vendored framework copy:

```bash
python3 .draft/framework/tools/validate.py --workspace .
```

Regenerate the AI framework index after framework docs, schemas, RequirementGroups,
templates, or catalog YAML change:

```bash
python3 framework/tools/generate_ai_index.py
```

Regenerate the browser when needed:

```bash
python3 framework/tools/generate_browser.py
```

## What The GitHub Actions Workflows Do

- `validate-catalog.yml` runs on pushes and pull requests to make sure the YAML parses, base fields are valid, deployable objects satisfy their RequirementGroups, and ReferenceArchitecture/SoftwareDeploymentPattern objects satisfy their applicable RequirementGroup checks.
- `generate-browser.yml` runs on pushes to `main` that change YAML content and regenerates `docs/index.html` so the published browser stays synchronized with the source data.

## How To Advance `catalogStatus`

`catalogStatus` should be treated as a maturity progression, not as a cosmetic label.

- `stub` means the object exists but is skeletal — enough to be referenced, not enough to validate completely.
- `incomplete` means the structure and major fields are present but some required facts are still missing or unresolved.
- `complete` means the object is fully authored and all applicable RequirementGroup requirements are satisfied.

For deployable objects, `complete` means the applicable RequirementGroup requirements are satisfied. For every object type, it also means the description, ownership, lifecycle, and relationships are clear enough that another engineer could use the object without guessing what it means.

The catalog organizes folders by content role inside `catalog/` (`engineering/`, `shared-services/`, and `governance/`), with flat folders by object family inside those role layers. Do not create deeper custom nested folders; the YAML content already carries the object classification.
