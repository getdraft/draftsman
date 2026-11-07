---
description: Check for DRAFT framework updates and guide a safe upgrade through branch, validate, and PR
argument-hint: ""
allowed-tools: [Bash, Read, Write, Edit]
---

# /draft update

This verb is delivered by the `draftsman-update` skill. It checks for DRAFT framework updates and guides a safe upgrade. Draft Admins only.

1. Locate the skills directory with Glob (`**/skills/draftsman-core/SKILL.md`): `framework/skills/` in the upstream repository, `.draft/framework/skills/` in a company workspace.
2. Read `draftsman-core/SKILL.md`, then `draftsman-update/SKILL.md` in the same directory.
3. Follow `draftsman-update/SKILL.md` exactly, treating `$ARGUMENTS` as the request.
