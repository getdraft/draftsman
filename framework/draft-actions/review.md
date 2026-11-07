---
description: Review an open PR for catalog correctness, or audit catalog content for quality and security compliance
argument-hint: "[PR number | security | compliance | satisfaction | artifact <name> | <path or object>]"
allowed-tools: [Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion]
---

# /draft review

This verb is delivered by the `draftsman-review` skill. It reviews an open pull request for catalog correctness, or audits catalog content for quality and security compliance.

1. Find the skills directory: `.draft/framework/skills/` if it exists (company workspace), otherwise `framework/skills/` (upstream repository). Do not use `.claude/skills/`; that is a generated copy.
2. Read `draftsman-core/SKILL.md` in that directory, then `draftsman-review/SKILL.md` in the same directory.
3. Follow `draftsman-review/SKILL.md` exactly, treating `$ARGUMENTS` as the request.
