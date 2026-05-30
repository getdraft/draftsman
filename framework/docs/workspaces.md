# Workspaces

For the full adoption sequence from installation through first drafting
sessions, see [Company Onboarding Tutorial](company-onboarding.md).

## Operating Model

DRAFT separates the upstream framework from private company implementation
content. A company workspace vendors a reviewed framework copy into its own
repo so normal Draftsman use is private, deterministic, and reviewable.

The upstream framework repo owns:

- `framework/schemas/` for object contracts
- `framework/configurations/` for base capabilities, RequirementGroups, domains,
  and object-patchable configuration
- `framework/tools/` for validation and generation
- `templates/` for object and company repo templates
- `examples/catalog/` for demonstration content only
- `docs/index.html` for the generated static GitHub Pages browser

A company private DRAFT repo owns:

- `.draft/framework/` for the vendored framework copy used by that company
- `.draft/providers/` for optional third-party DRAFT requirement packs
- `.draft/workspace.yaml` for tracked workspace metadata
- `.draft/framework.lock` for the reviewed upstream framework source and synced commit
- `README.md` with a copy/paste Draftsman start prompt for connected AI tools
- `catalog/` for architecture content
- `configurations/` for company capability mappings, RequirementGroups, and object patches

The workspace metadata should include a stable machine name and a human-readable
label. Workspace templates use these values to make first-run README and AI
bootstrap files specific to the adopting company:

```yaml
workspace:
  name: acme-draft
  displayName: Acme DRAFT Workspace
  companyName: Acme
```

If `displayName` is not present during first-time scaffolding, the framework
uses a readable version of the repo or workspace directory name.

The effective model is resolved in this order:

1. vendored framework base configuration from `.draft/framework/configurations/`
2. optional third-party provider configurations from `.draft/providers/*/configurations/`
3. workspace configuration overlays
4. workspace catalog content

The public `getdraft/draftsman` repository is an update source, not a
runtime dependency for company drafting. The connected AI reads the vendored
copy in `.draft/framework/` during normal Draftsman work. A company chooses
when to refresh that copy, reviews the resulting Git diff, validates the
workspace, and commits the framework refresh in its private repo.

Company overrides should be represented as `object_patch` YAML when the goal is
to alter a base framework object without editing the vendored framework copy.
Patch files live under `configurations/object-patches/`.

Workspace requirement activation lives in `.draft/workspace.yaml`, not in the
presence of YAML files. A framework, provider, or company may publish many
workspace-mode RequirementGroups, but the company must explicitly activate the
groups it architects against:

```yaml
requirements:
  activeRequirementGroups:
    - <soc2-requirement-group-uid>
    - <company-requirement-group-uid>
  requireActiveRequirementGroupDisposition: false
```

`requireActiveRequirementGroupDisposition: false` allows existing inventory to migrate
incrementally. Draftsman still uses active groups for new and updated
objects. Setting it to `true` makes validation require every in-scope object to
record disposition against every active group.

Framework base capability files ship with empty `implementations` and a
`definitionOwner`. Company workspaces own the capability `owner` and the mapping
from capability to approved TechnologyComponents by adding capability overlays
or object patches under `configurations/`. Validation requires `owner.team` in
the effective capability whenever implementations are assigned.

The distinction matters:

- `definitionOwner` says who maintains the capability definition and vocabulary.
- `owner` says which company team can approve lifecycle disposition for vendor
  products that satisfy the capability.
- `implementations` list only TechnologyComponents, because lifecycle
  disposition applies to a discrete vendor product and version.

## Business Taxonomy

Companies can declare their own business pillars, portfolios, or product
groupings in `.draft/workspace.yaml`. The framework does not ship company
business taxonomy values; it only validates and renders the workspace values
when SoftwareDeploymentPatterns reference them.

Example:

```yaml
businessTaxonomy:
  requireSoftwareDeploymentPatternPillar: true
  pillars:
    - id: business-pillar.human-capital-management
      name: Human Capital Management
      owner:
        team: hcm-product
        contact: hcm-product@example.com
    - id: business-pillar.student-management
      name: Student Management
    - id: business-pillar.business-operations
      name: Business Operations
```

SoftwareDeploymentPatterns reference those values through
`businessContext.pillar`. Use `businessContext.additionalPillars` only when a
pattern materially spans more than one business pillar; the primary `pillar`
drives browser grouping.

## Company Vocabulary

Companies can declare optional governed vocabulary lists in
`.draft/workspace.yaml`. These lists give the Draftsman multiple-choice answers
for common architecture questions and give validation a controlled way to catch
typos, drift, and values that have not been accepted as standards.

Supported lists are:

- `deploymentTargets`
- `dataClassificationLevels`
- `teams`
- `availabilityTiers`
- `failureDomains`

Each declared list has a `mode`:

- `advisory` reports non-standard values as warnings.
- `gated` reports non-standard values as failures.

Undeclared lists preserve existing free-text behavior. This lets a company
start with the highest-value list, usually `teams` or `deploymentTargets`, and
add the rest gradually.

Example:

```yaml
vocabulary:
  deploymentTargets:
    mode: advisory
    source: configurations/vocabulary/deployment-targets.yaml
  teams:
    mode: advisory
    values:
      - id: platform-engineering
        name: Platform Engineering
        contact: platform-engineering@example.com
```

Small lists can live inline under `values`. Larger lists can live in
`configurations/vocabulary/*.yaml` source files:

```yaml
schemaVersion: "1.0"
type: vocabulary
vocabulary: deploymentTargets
name: Deployment Targets
values:
  - id: aws-us-east-2
    name: AWS US East 2
    type: cloud-region
    provider: aws
    status: approved
```

Validation only enforces lists that are declared in `.draft/workspace.yaml`.
For declared lists, validation checks the relevant fields and reports the field
path, found value, and approved values. A real answer that is not approved is a
non-standard value. The Draftsman should ask whether to revisit it later or
submit a `vocabulary_proposal` for review.

See [Company Vocabulary](company-vocabulary.md) for the complete model,
proposal file shape, and Draftsman interview behavior.

## Authoring Workflow

The default workspace workflow is source based:

1. Create or update YAML in `catalog/` or `configurations/`.
2. Use the matching template from `.draft/templates/` when creating a new object.
3. Read the relevant schema and RequirementGroup before filling in fields.
4. Preserve unresolved facts in `catalog/sessions/` as DraftingSessions.
5. Run `python3 .draft/framework/tools/validate.py --workspace /path/to/workspace`.
6. Review and commit the workspace changes through normal Git workflow.

Direct YAML files are the source of truth. Generated files such as
`docs/index.html` and `AI_INDEX.md` are derived from source content.

## Catalog Browsing

The Architecture browser is generated by
`framework/tools/generate_browser.py`. In this upstream framework repository it
renders `framework/configurations/` plus `examples/catalog/` into
`docs/index.html` for GitHub Pages.

For a company repo, generate a browser from that workspace explicitly:

```bash
python3 .draft/framework/tools/generate_browser.py \
  --workspace /path/to/company-draft-workspace \
  --output /path/to/output/index.html
```

The generated browser is read-only. Catalog changes are made in YAML and then
validated.

The browser's Acceptable Use Technology view is generated from the effective
Capability model. It groups TechnologyComponent lifecycle mappings by domain,
shows which capability each product satisfies, and lists the company capability
owner/contact for change requests.

## Framework Updates

Framework updates are explicit. The workspace records the upstream source and
synced commit in `.draft/framework.lock`, while the actual framework files live
under `.draft/framework/`.

The normal refresh flow is:

1. Choose a reviewed upstream tag, commit, or internal framework mirror.
2. Open a branch in the company repo.
3. Replace `.draft/framework/` with that reviewed framework version.
4. Update `.draft/framework.lock` with the synced source, commit, and version.
5. Validate the workspace against the refreshed framework.
6. Review and commit the `.draft/framework/` and `.draft/framework.lock`
   changes through a normal pull request.

Company-specific changes should remain in top-level `configurations/` as
overlays or object patches. Avoid editing `.draft/framework/` directly unless
the intent is to maintain an internal fork of the framework.

New workspaces also include an optional GitHub Actions workflow at
`.github/workflows/draft-framework-update.yml`. The workflow checks for a newer
DRAFT Framework version tag, opens an update branch, refreshes
`.draft/framework/`, updates `.draft/framework.lock`, and validates the
workspace.

When validation passes, the workflow opens a normal update pull request. When
validation fails, it opens the pull request anyway with a blocked title and the
validation output in the body. The branch remains available for the company or
the Draftsman to repair catalog and configuration issues against the new
framework version. Disable the workflow in GitHub Actions or delete the file if
the company wants to manage framework updates manually.

## Deployable Architecture Direction

The end goal is deployable architecture. Catalog objects should capture facts
that can later inform pipeline and infrastructure automation:

- Hosts, RuntimeServices, DataStoreServices, EdgeGatewayServices, and
  Product Services describe reusable deployable building blocks.
- ReferenceArchitectures describe deployable patterns.
- SoftwareDeploymentPatterns describe product deployment reality.
- Capabilities describe architecture outcomes, company decision owners, and
  approved TechnologyComponent implementations.
- RequirementGroups describe required authoring and compliance answers.
- Future automation mappings can translate approved objects into pipeline and
  IaC inputs.

When an AI agent has a choice between vague narrative and structured deployable
facts, it should choose structured deployable facts and preserve missing details
as validation gaps or drafting-session questions.
