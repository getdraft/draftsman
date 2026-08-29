![DRAFT Logo](./draftlogo.png)

# Deployable Reference Architecture Framework Toolkit (DRAFT)

DRAFT enables **Enterprise-Grade Vibe Coding** — an architecture-as-code framework where product engineers describe what they want to build to an AI coding assistant, and the AI drafts standard, compliant architecture specifications (Software Deployment Patterns).

Speed and compliance are achieved together because product specifications can **only be assembled from company-approved shared services and reference architectures**.

> **The Core Vibe Coding Principle:** **AI drafts the architectural intent** (`.draft/sdp.yaml`); **the Composition Engine (`compose_iac.py`) composes the deterministic, audited infrastructure code** (`main.tf`). AI never generates free-form Terraform code directly; it stitches pre-approved, versioned platform modules.

---

## The DRAFT Operating Model

DRAFT operates via a decentralized Architecture-as-Code architecture:

1. **Decentralized Product Specs (Pattern 2)**:
   Product teams own their `.draft/sdp.yaml` pattern manifests directly in their application repositories. On pull request merge, a least-privilege GitHub Action automatically syncs the pattern payload to the central company `drafting-table` catalog using ephemeral tokens. `drafting-table` holds **zero read access** to private product source code repositories.

2. **Shared Services Composition Split**:
   Shared services in the catalog are explicitly split by `provisioningModel`:
   - **`deployable`**: Resolves to real, versioned, callable Infrastructure-as-Code (IaC) modules (`deployablePackage: { registry, source, version }`). These shared services compose end-to-end deployable pipelines.
   - **`reference-only`**: Legacy standards and "acceptable use" platforms without IaC modules. These satisfy `RequirementGroups` for compliance/audit purposes, but any pattern relying on them is capped at `catalogStatus: documentation` and cannot be marked `deployment-ready`.

3. **AI Pair Programming via Draftsman**:
   Engineers pair with AI coding assistants (Cursor, Claude Code, Copilot, Antigravity) running the `draftsman` agent locally, or query central architecture via the `draftsman` factory agent over Slack, Discord, or Web UI.

---

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

---

## How DRAFT Works

DRAFT v1.0+ is repo-first and Git-native:

1. **Vendor Framework**: A company creates a private `drafting-table` repo and vendors DRAFT under `.draft/framework/`.
2. **Register Products**: Engineering teams register product repositories in `catalog/engineering/product-registrations/`.
3. **Scaffold Local Repo (`/draft init`)**: Product teams run `/draft init` in their code repos to auto-discover runtimes and scaffold `.draft/sdp.yaml`.
4. **Local Validation**: Engineers validate architecture locally using `python3 .draft/framework/tools/validate.py --workspace .`.
5. **Pattern 2 Auto-Sync**: PR merges automatically sync the SDP payload to `drafting-table` via ephemeral GitHub App tokens.

---

## GitHub Activity Tracking

Use GitHub issues and pull requests as the shared activity log for DRAFT work.
Agents keep work tied to the relevant GitHub ticket or PR so progress, decisions, and handoffs are visible in the repository rather than only in chat.

Agent responsibility is determined by the real GitHub identity that performed the work: the issue assignee, PR author, commit author, review/comment author, and linked GitHub activity. Labels remain reserved for workflow, priority, area, type, or status metadata.

---

## Repository Layout

```text
agent/                  # Official Draftsman Agent specification, prompts, skills, and factory bindings
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
```

A company private DRAFT repo uses this layout:

```text
.draft/framework/      # Vendored DRAFT framework copy used by that company
.draft/providers/      # Optional third-party control packs
.draft/workspace.yaml  # Tracked workspace metadata
.draft/framework.lock  # Upstream source and synced framework commit
catalog/                # Company architecture content & product registrations
configurations/         # Company RequirementGroup, compliance, domain, and patch overlays
configurations/vocabulary/
                        # Optional company governed vocabulary source files
configurations/vocabulary-proposals/
                        # Draftsman proposals for non-standard values
configurations/object-patches/
                        # Patch objects for framework or catalog overrides
```

---

## Official Draftsman Agent Package & Deployment

`draftsman` includes a turn-key, official agent package located in [`agent/`](agent/) containing:
* **`agent/SOUL.md`**: Canonical persona, core identity, strict evidence discipline, and developer onboarding playbooks.
* **`agent/agent-spec.yaml`**: Universal runtime & resource specification.
* **`agent/skills/`**: Specialized agent skills (`draftsman`, `draftsman-engineer`, `draftsman-autodiscover`, `draftsman-diagram`, `draftsman-query`, `draftsman-standards`).
* **`agent/bindings/`**: Factory bindings for **Hermes Agent Factories** (`agent/bindings/hermes/agent.yaml`) and **GitHub Actions** (`agent/bindings/github-actions/draft-agent-gatekeeper.yml`).
* **`agent/docs/DEPLOYMENT.md`**: Deployment blueprints (GCP Cloud Run, AWS Fargate) and secret management.

---

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
- [Shared Services composition spec](framework/docs/SHARED_SERVICE_COMPOSITION_SPEC.md)
- [Composition roadmap](framework/docs/COMPOSITION_ROADMAP.md)
- [Engineering onboarding tutorial](framework/docs/engineering-onboarding.md)
- [Shared Services onboarding tutorial](framework/docs/shared-services-onboarding.md)
- [Company vocabulary](framework/docs/company-vocabulary.md)
- [DRAFT object types](framework/docs/object-types.md)
- [YAML schema reference](framework/docs/yaml-schema-reference.md)
- [Authoring templates](templates/)

---

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

Regenerate the static browser, browser assets, user manual, and AI index after changes:

```bash
python3 framework/tools/generate_browser.py
python3 framework/tools/generate_ai_index.py
```

Run the framework unit tests:

```bash
python3 -m unittest discover -s tests
```

---

## Compliance Claims

Workspace-mode RequirementGroups can be supplied by the DRAFT framework, third-party providers, or the company workspace. The company activates the groups it architects against in `.draft/workspace.yaml`.

Architecture artifacts declare compliance explicitly with `requirementGroups`. When a workspace-mode group is declared, every applicable requirement from that group must have a valid `requirementImplementations` entry before the object can be approved.

Artifacts without a declared group are unclaimed inventory. They are not labeled non-compliant, but they should not be treated as compliant off-the-shelf building blocks for solutions that require that requirement group.

---

## License

Copyright 2026 Dale Sackrider. Licensed under the [Apache License, Version 2.0](LICENSE).
