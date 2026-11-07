---
description: Conversational entry point for Draftsman authoring — bootstraps the workspace, then starts or resumes a guided DraftingSession or ad hoc authoring
argument-hint: "[system, product, topic, or intent — leave empty to be asked]"
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion]
---

# /draft guide

This verb is delivered by the `draftsman-author` skill. It bootstraps the workspace, then starts or resumes a guided DraftingSession or handles ad hoc authoring.

1. Locate the skills directory with Glob (`**/skills/draftsman-core/SKILL.md`): `framework/skills/` in the upstream repository, `.draft/framework/skills/` in a company workspace.
2. Read `draftsman-core/SKILL.md`, then `draftsman-author/SKILL.md` in the same directory.
3. Follow `draftsman-author/SKILL.md` exactly, treating `$ARGUMENTS` as the request.
