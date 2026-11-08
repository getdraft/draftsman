---
description: Conversational entry point for Draftsman authoring — bootstraps the workspace, then starts or resumes a guided DraftingSession or ad hoc authoring
argument-hint: "[system, product, topic, or intent — leave empty to be asked]"
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion]
---

# /draft guide

This verb is delivered by the `draftsman-author` skill. It bootstraps the workspace, then starts or resumes a guided DraftingSession or handles ad hoc authoring.

1. Find the skills directory: `.draft/framework/skills/` if it exists (company workspace), otherwise `framework/skills/` (upstream repository). Do not use `.claude/skills/`; that is a generated copy.
2. Read `draftsman-core/SKILL.md` in that directory, then `draftsman-author/SKILL.md` in the same directory.
3. Follow `draftsman-author/SKILL.md` exactly, treating `$ARGUMENTS` as the request.
