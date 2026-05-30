---
description: List all available DRAFT commands and describe their purposes in a concise table
argument-hint: ""
allowed-tools: [Read, Glob, Grep, Bash]
---

# /draft-help Command

When this command is run, detect all commands in `framework/commands/` and output **only** a clean markdown table of available commands, the role who runs each, and their purpose. 

Do not output any additional setup guides, intro explanations, or symlink instructions.

| Command | Role | Purpose |
|---|---|---|
| `/draft-help` | All Users | List all available DRAFT commands and describe their purposes in a concise table. |
| `/draftsman` | Engineers & Tech Admins | Activate the Draftsman for architecture catalog authoring or workspace setup. |
| `/draft-session` | Engineers & Tech Admins | Start or resume a guided DraftingSession for a system, component, or product. |
| `/draft-validate` | All Users | Validate the DRAFT catalog and report issues with detailed fix guidance. |
| `/validate-catalog` | All Users | Compatibility alias for `/draft-validate` used by older workspaces. |
| `/draft-triage` | Framework Contributors | Pull open GitHub issues and work through selected ones interactively. |
| `/draft-updateframework` | Draft Admins | Check for DRAFT framework updates and guide a safe upgrade. |
| `/draft-review` | Framework Maintainers | Expert consultant review of the DRAFT framework for simplification and adoption. |
