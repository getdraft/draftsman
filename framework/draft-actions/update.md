---
description: Check for DRAFT framework updates and guide a safe upgrade through branch, validate, and PR
argument-hint: ""
allowed-tools: [Bash, Read, Write, Edit]
---

# /draft update

This verb is delivered by the `draftsman-update` skill. It checks for DRAFT framework updates and guides a safe upgrade. Draft Admins only.

1. Find the skills directory: `.draft/framework/skills/` if it exists (company workspace), otherwise `framework/skills/` (upstream repository). Do not use `.claude/skills/`; that is a generated copy.
2. Read `draftsman-core/SKILL.md` in that directory, then `draftsman-update/SKILL.md` in the same directory.
3. Follow `draftsman-update/SKILL.md` exactly, treating `$ARGUMENTS` as the request.
