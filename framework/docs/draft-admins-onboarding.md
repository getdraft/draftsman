---
type: documentation
title: "Draft Admins Onboarding Guide"
description: "As a Draft Admin, you own the DRAFT **platform configuration** and **governance layers** inside the repository."
tags:
  - draft
  - documentation
  - draft_admins_onboarding
timestamp: 2026-06-12T21:06:02-07:00
---
# Draft Admins Onboarding Guide

> **Audience:** Workspace Administrators, Enterprise Architects, and Devops Leads.
> This guide is a step-by-step tutorial to help Draft Admins bootstrap, configure, secure, and maintain a DRAFT company workspace repository.

---

## 1. Overview of the Draft Admin Layer

As a Draft Admin, you own the DRAFT **platform configuration** and **governance layers** inside the repository. You do not typically model product services or hosts. Instead, you bootstrap the workspace itself, manage the business taxonomy, declare compliance/security RequirementGroups, and curate the authoritative team registry.

The Draft Admin layer comprises the configuration folders and workspace metadata:
1. **`.draft/workspace.yaml`**: The single source of truth for workspace identity, business pillars, and vocabulary policies.
2. **`configurations/vocabulary/`**: Gated vocabulary files defining approved lists (e.g. approved clouds, severity lists, team registries).
3. **`configurations/requirement-groups/`**: Local security, compliance, or quality standards (e.g., SOC2, NIST, corporate engineering gates).
4. **`configurations/object-patches/`**: Deep-merge overlays that configure company-specific attributes on base framework objects.

```text
.draft/workspace.yaml          ← Workspace config, business taxonomy, vocabulary policies
configurations/
  vocabulary/                 ← Gated list values (teams, severities, clouds)
  requirement-groups/         ← Local corporate compliance & engineering checks
  object-patches/             ← Deep-merge overrides for capabilities and standards
```

For ongoing operating standards, ticketing, routing, and Pull Request reviews, refer directly to the central [Draft Operations Guide](operations-guide.md).

---

## 2. Bootstrapping a New Workspace Repository

DRAFT is repo-first and Git-ops native. To bootstrap a brand-new DRAFT company workspace:

### Step 1: Create a Private Company Git Repository
Create an empty private repository in your company's version control system (e.g. GitHub or GitLab).

### Step 2: Vendor the DRAFT Framework
Copy the DRAFT framework files into your repository. The framework files belong in `.draft/framework/` to allow easy upstream refreshes.
```text
.draft/framework/       ← The vendored copy of this upstream repository
```

### Step 3: Seed Root Workspace Templates
Copy the workspace bootstrap templates from `.draft/framework/templates/workspace/` into your repository root. Remove the `.tmpl` suffix from all files:
* `.gitignore`
* `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` (AI Bootstrap contracts)
* `CODEOWNERS`
* `README.md`
* `.draft/workspace.yaml` (Workspace configuration baseline)
* `catalog/` & `configurations/` (Directories containing role-based nested `.gitkeep` files)

### Step 4: Configure Workspace Identity
Edit `.draft/workspace.yaml` in your repository root and fill in your enterprise metadata:
```yaml
workspace:
  name: acme-architecture
  displayName: Acme Architecture Catalog
  companyName: Acme Corp
repository:
  provider: github
  owner: acme-org
  name: draft-workspace
  defaultBranch: main
```

Commit these files and push to your default branch.

---

## 3. Starting Setup Mode

Once your private repo is pushed, connect your preferred AI coding tool to the repository root. Copy the prompt from your workspace `README.md` or ask:

```text
I need a draftsman. Enter Draftsman setup mode for this company DRAFT workspace.
```

Your AI assistant will immediately assume the **Draftsman** role, read your bootstrap configurations, and guide you through a conversational first-run interview (confirming your business pillars, team registry, and assigning company owners to core capability domains).

---

## 4. Platform Maintenance & Admin Responsibilities

As a Draft Admin, you are accountable for the workspace's ongoing operational health. Maintain the catalog using three automated tools:

### 1. The Schema & Reference Validator
Run the validator to check that all YAML catalog and configuration files parse, cross-reference UIDs cleanly, and satisfy activated RequirementGroups:
```bash
python3 framework/tools/validate.py
```
*Note:* In a company repo, run it at the workspace root: `python3 .draft/framework/tools/validate.py`.

### 2. The Browser Generator
Run the browser compiler to regenerate the static, searchable GitHub Pages browser shell (`docs/index.html`):
```bash
python3 framework/tools/generate_browser.py
```

### 3. The AI Framework Indexer
Run the AI framework indexer whenever schemas, docs, templates, or catalog layouts change to keep the AI bootstrap map (`AI_INDEX.md`) completely current:
```bash
python3 framework/tools/generate_ai_index.py
```

### Ongoing Governance Workflows
* **Vocabulary Promotion**: Developers will submit new technology or team vocabulary requests as files under `configurations/vocabulary-proposals/`. Review these proposals periodically and merge approved values into the gated active lists under `configurations/vocabulary/`.
* **Advisory Triage**: Monitor the workspace's `needs-routing` ticket queue. Review issues where `owner.team` is missing or ambiguous, resolve the correct team assignment, and route the tickets to the proper team backlogs.
* **CODEOWNERS Refresh**: Ensure that `generate_codeowners.py` is run to rebuild the `.github/CODEOWNERS` file whenever vocabulary teams, folder structures, or file ownership targets are modified in the catalog.

For detailed guidelines on issue ticketing, lifecycle states, standard dispositions, and CODEOWNERS review routing, see the [Draft Operations Guide](operations-guide.md).
