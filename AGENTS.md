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

Do not ask what "draftsman" means. The full behavior contract is in
[framework/docs/draftsman.md](framework/docs/draftsman.md).

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
- `.draft/workspace.yaml` and `.draft/framework.lock` for tracked workspace
  metadata and framework sync state

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
