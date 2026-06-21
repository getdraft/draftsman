---
description: Unified DRAFT command family — run a verb (validate, guide, triage, …) or show the verb list
argument-hint: "[verb] (e.g. validate, guide, audit, triage, update; empty shows the list)"
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion]
---

# /draft Command

`/draft` is the single entry point for the DRAFT command family. The first word
of the argument is the **verb**; any remaining text is passed to that verb as its
own argument.

## Step 1: Parse the verb

Read `$ARGUMENTS`.

- Take the first whitespace-delimited token as `VERB` (lowercase it).
- Treat the rest of the string as `REST` (the verb's argument).

If `$ARGUMENTS` is empty, or `VERB` is `help`, go to **Show the verb list**.

## Step 2: Route the verb

Map `VERB` to an action file. Every action lives in a `draft-actions/`
directory. Locate it with Glob (`**/draft-actions/<file>`) so it resolves whether
the framework sits at the repo root (`framework/draft-actions/`, upstream) or is
vendored under `.draft/framework/draft-actions/` (company workspace).

| Verb | Action file | Purpose |
|---|---|---|
| `guide` | `draft-actions/guide.md` | Bootstrap, then start or resume a guided DraftingSession or ad hoc authoring. |
| `validate` | `draft-actions/validate.md` | Validate the DRAFT catalog and report fixes. |
| `audit` | `draft-actions/audit.md` | Run general catalog review or security RequirementGroup, satisfaction, posture, and artifact audit workflows. |
| `triage` | `draft-actions/triage.md` | Pull open GitHub issues and work through selected ones. |
| `review-framework` | `draft-actions/review-framework.md` | Upstream-only: review the DRAFT framework itself. |
| `update` | `draft-actions/update.md` | Check for framework updates and guide a safe upgrade. |

Once you have matched the verb, **read that action file and follow it exactly**,
treating `REST` as the action's `$ARGUMENTS`.

If any verb reveals a likely reusable framework bug or feature request while
running in a vendored company workspace, follow **Upstream Framework Feedback
Routing** in `draftsman.md`: explain the framework-owned finding, recommend an
upstream report, ask before creating a public issue, use the appropriate public
issue template, and sanitize company details.

If `VERB` does not match any row, tell the user it is not a known verb and then
**Show the verb list**.

## Show the verb list

Output **only** this table — no preamble, setup guides, or symlink notes:

| Verb | Who runs it | Purpose |
|---|---|---|
| `/draft help` | All Users | Show this list of DRAFT verbs. |
| `/draft guide` | Engineering & Shared Services | Bootstrap and start or resume guided catalog authoring. |
| `/draft validate` | All Users | Validate the DRAFT catalog and report issues with fix guidance. |
| `/draft audit` | Engineering, Security, GRC & Draft Admins | Run general catalog review or security RequirementGroup, satisfaction, review, and audit workflows. |
| `/draft triage` | Draft Admins | Pull open GitHub issues and work through selected ones. |
| `/draft update` | Draft Admins | Check for DRAFT framework updates and guide a safe upgrade. |

In the upstream `getdraft/draftsman` repository, one additional verb is available
for maintainers and is **not** documented in vendored company workspaces:

| Verb | Who runs it | Purpose |
|---|---|---|
| `/draft review-framework` | Framework Maintainers | Expert consultant review of the DRAFT framework for simplification and adoption. |

End with one line: `Run /draft <verb> to start, e.g. /draft validate.`
