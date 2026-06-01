![DRAFT Logo](./draftlogo.png)

# Deployable Reference Architecture Framework Toolkit (DRAFT)

DRAFT is a repo-based architecture framework for turning architecture
conversations into governed, reviewable source files. It gives an AI assistant
schemas, prompts, templates, validation rules, and generated browser views so
the assistant can help build a durable architecture catalog instead of producing
one-off diagrams or documents.

The goal is simple: a company should be able to point its preferred AI tool at a
private DRAFT repo and have that AI act as the Draftsman, asking guided
questions, writing valid YAML, running validation, and preparing reviewable Git
changes.

This repository is the upstream framework. Company architecture content belongs
in a private company DRAFT repo that vendors this framework under
`.draft/framework/`.

## Start With This Prompt

Copy this into your preferred AI tool:

```text
I want to get started with DRAFT.

Use the DRAFT framework repository https://github.com/getdraft/draftsman.
Read and follow the repository bootstrap instructions, starting with AGENTS.md.
Use the repo-defined Draftsman workflow instead of inventing your own.

If I want to adopt DRAFT for a company, do not write company architecture
content into the upstream framework repo. Help me select or create the correct
company DRAFT workspace first, then continue from that repo.

If you cannot connect to the repo, inspect its files, or write changes back to
it, stop and tell me exactly what I need to enable for a fully functional
Draftsman session.

Otherwise, begin the next useful onboarding step.
```

## How DRAFT Works

DRAFT v1.0 is repo-first. It does not require a DRAFT app, hosted service,
local daemon, or DRAFT-specific CLI.

1. Create a private company DRAFT repo.
2. Vendor a reviewed framework copy under `.draft/framework/`.
3. Add the root AI bootstrap files from `templates/workspace/`.
4. Connect the AI tool the company already uses, such as ChatGPT, Claude,
   Gemini, Copilot, Codex, or another code-capable assistant.
5. Ask the AI to act as the Draftsman and follow `AGENTS.md`.
6. Review all changes as ordinary Git diffs and pull requests.

The Draftsman conversation is the intended authoring experience, but it happens
through the AI tool connected to the repo. The framework supplies the prompts,
schemas, templates, docs, validation tools, generated browser, and GitHub
Actions workflows that make that AI behavior deterministic and reviewable.

For a new company workspace, ask the connected AI to start setup mode. Setup
mode walks the enterprise architecture team through the minimum steps needed to
make the repo useful while keeping the user aware of the current step, next
step, remaining work, and revisit-later items.

The local DRAFT Table app and `draft-table` CLI are retained in the repository
as an experimental prototype, but they are not part of the v1.0 launch path.
Future releases may revive them as optional convenience tooling after the
repo-first workflow is stable.

## Repository Layout

```text
framework/              # Core schemas, tools, docs, and base configurations
framework/browser/      # Static browser shell, CSS, JavaScript, and theme assets
framework/configurations/
                        # Base capabilities, RequirementGroups, and domains
examples/catalog/       # Sample content used to validate and demo the framework
templates/              # Object and company repo templates
docs/index.html         # Generated static browser for the example workspace
docs/assets/            # Generated browser data plus copied browser assets
docs/user-manual.html   # Generated DRAFT user manual
docs/company-vocabulary.html
                        # Generated company vocabulary guide
draft_table/            # Experimental local app prototype; post-v1.0
```

A company private DRAFT repo should use this shape:

```text
.draft/framework/      # Vendored DRAFT framework copy used by that company
.draft/providers/      # Optional third-party control packs
.draft/workspace.yaml  # Tracked workspace metadata
.draft/framework.lock  # Upstream source and synced framework commit
catalog/                # Company architecture content
configurations/         # Company RequirementGroup, compliance, domain, and patch overlays
configurations/vocabulary/
                        # Optional company governed vocabulary source files
configurations/vocabulary-proposals/
                        # Draftsman proposals for non-standard values
configurations/object-patches/
                        # Patch objects for framework or catalog overrides
```

The effective model is resolved by reading `.draft/framework/configurations/`
first, then optional `.draft/providers/*/configurations/`, then workspace
configuration overlays, then workspace catalog content. The public repo is an
update source, not a runtime dependency for a company's Draftsman.

### Framework Update Workflow

New company workspaces include an optional GitHub Actions workflow at
`.github/workflows/draft-framework-update.yml`. The workflow checks for newer
DRAFT Framework versions, falls back to upstream `main` when version tags are
missing or stale, creates an update branch, refreshes the vendored
`.draft/framework/` copy, updates `.draft/framework.lock`, validates the
workspace, and opens a pull request.

If validation succeeds, the PR is titled as a normal framework update. If
validation fails, the workflow still opens the PR but marks it blocked so the
company can repair catalog or configuration issues on that branch. Companies can
disable this behavior by disabling the workflow in GitHub Actions or deleting
the workflow file.

New company workspaces also include an optional vocabulary proposal workflow at
`.github/workflows/draft-vocabulary-proposals.yml`. When the Draftsman captures
a real answer that is not an approved vocabulary value, it can write a
`vocabulary_proposal` file; the workflow can turn that into a review pull
request against the official company vocabulary list.

### AI Tool Boundary

DRAFT does not store AI credentials. The connected AI tool and Git provider own
authentication. If the AI environment has Git and GitHub access through the
user's credentials, it may branch, commit, push, and open pull requests. If it
does not, it should prepare local changes and give exact review steps.

## Start Here

### Framework Basics

- [Framework overview](framework/docs/overview.md)
- [Framework versioning](VERSIONING.md)
- [Release checklist](RELEASE.md)
- [Changelog](CHANGELOG.md)
- [AI agent bootstrap](AGENTS.md)
- [AI framework index](AI_INDEX.md)
- [User manual](framework/docs/user-manual.md)
- [Draftsman instructions for AI](framework/docs/draftsman.md)
- [Draftsman setup mode](framework/docs/setup-mode.md)
- [Draftsman AI guidance](framework/docs/draftsman-ai-configuration.md)
- [Engineering onboarding tutorial](framework/docs/engineering-onboarding.md)
- [Shared Services onboarding tutorial](framework/docs/shared-services-onboarding.md)
- [Draft Admins onboarding tutorial](framework/docs/draft-admins-onboarding.md)
- [Company vocabulary](framework/docs/company-vocabulary.md)
- [DRAFT object types](framework/docs/object-types.md)
- [YAML schema reference](framework/docs/yaml-schema-reference.md)
- [Naming conventions](framework/docs/naming-conventions.md)
- [How to add objects](framework/docs/how-to-add-objects.md)
- [Workspace model](framework/docs/workspaces.md)
- [Authoring templates](templates/)

### Deployable Architecture Content

- [Deployable objects](framework/docs/standards.md)
- [Delivery models](framework/docs/delivery-models.md)
- [ProductComponent schema](framework/schemas/product-component.schema.yaml)
- [ReferenceArchitectures](framework/docs/reference-architectures.md)
- [SoftwareDeploymentPatterns](framework/docs/software-deployment-patterns.md)

### Supporting Model Objects

- [TechnologyComponents](framework/docs/technology-components.md)
- [DecisionRecords](framework/docs/decision-records.md)
- [DraftingSessions](framework/docs/drafting-sessions.md)
- [Capabilities](framework/docs/capabilities.md)

### Extensible Framework Content

- [RequirementGroups](framework/docs/requirement-groups.md)
- [RequirementGroups and Compliance](framework/docs/security-and-compliance-controls.md)

## Validate And Generate

Install the only runtime dependency used by the framework tools:

```bash
python3 -m pip install pyyaml
```

Validate the framework base configuration and example catalog:

```bash
python3 framework/tools/validate.py
```

Validate a company repo from the upstream checkout:

```bash
python3 framework/tools/validate.py --workspace /path/to/company-draft-workspace
```

Inside a company repo, validate against the vendored framework copy:

```bash
python3 .draft/framework/tools/validate.py --workspace .
```

Regenerate the static browser, browser assets, user manual, and AI index after
YAML, docs, schema, browser, or template changes:

```bash
python3 framework/tools/generate_browser.py
python3 framework/tools/generate_ai_index.py
```

Run the framework unit tests:

```bash
python3 -m unittest discover -s tests
```

Check release-note and version metadata:

```bash
python3 framework/tools/check_release_notes.py
```

## Compliance Claims

Workspace-mode RequirementGroups can be supplied by the DRAFT framework,
third-party providers, or the company workspace. The company activates the
groups it architects against in `.draft/workspace.yaml`.

Architecture artifacts declare compliance explicitly with
`requirementGroups`. When a workspace-mode group is declared, every applicable
requirement from that group must have a valid `requirementImplementations`
entry before the object can be approved.

Artifacts without a declared group are unclaimed inventory. They are not
labeled non-compliant, but they should not be treated as compliant
off-the-shelf building blocks for solutions that require that requirement group.
If `requireActiveRequirementGroupDisposition` is enabled in the workspace, validation
also requires every in-scope object to record disposition against every active
group.

## Catalog Browsing

The generated static browser is published at:

[https://dsackr.github.io/draft-framework/](https://dsackr.github.io/draft-framework/)

GitHub Pages is read-only. `docs/index.html` is a generated shell. The browser
data is written to `docs/assets/browser-data.js`, and framework-owned CSS,
JavaScript, and default theme assets are copied from `framework/browser/`.
The same generator renders `framework/docs/user-manual.md` to
`docs/user-manual.html`.

## License

Copyright 2026 Dale Sackrider. Licensed under the [Apache License, Version 2.0](LICENSE).
