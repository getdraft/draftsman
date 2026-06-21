---
description: Unified DRAFT command family — run a verb (guide, review, update) or show the verb list
argument-hint: "[verb] (e.g. guide, review, update; empty shows the list)"
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

Map `VERB` to an action file. Action files live in a `draft-actions/` directory.
Locate them with Glob (`**/draft-actions/<file>`) so routing works whether the
framework sits at the repo root (`framework/draft-actions/`, upstream) or is
vendored under `.draft/framework/draft-actions/` (company workspace).

| Verb | Action file | Purpose |
|---|---|---|
| `guide` | `draft-actions/guide.md` | Bootstrap, then start or resume a guided DraftingSession or ad hoc authoring. |
| `review` | `draft-actions/review.md` | Review an open PR for catalog correctness, or audit catalog content for quality and security compliance. |
| `update` | `draft-actions/update.md` | Check for framework updates and guide a safe upgrade. |
| `validate` | `draft-actions/validate.md` | Validate the DRAFT catalog and report fixes. *(Internal — called by `guide` and `review`. Works as a standalone verb but is not in the help table.)* |

Once you have matched the verb, **read that action file and follow it exactly**,
treating `REST` as the action's `$ARGUMENTS`.

### Upstream-only verb

One additional verb is available only in the upstream `getdraft/draftsman`
repository. It is **not** vendored into company workspaces and must not appear
in company workspace help output:

| Verb | Action file | Purpose |
|---|---|---|
| `review-framework` | `upstream/review-framework.md` | Expert consultant review of the DRAFT framework itself. |

To route `review-framework`, locate the file with Glob (`upstream/review-framework.md`)
from the repository root. If the file is not found, tell the user this verb is
not available in this workspace.

If any verb reveals a likely reusable framework bug or feature request while
running in a vendored company workspace, follow **Upstream Framework Feedback
Routing** in `draftsman.md`: explain the framework-owned finding, recommend an
upstream report, ask before creating a public issue, use the appropriate public
issue template, and sanitize company details.

If `VERB` does not match any row, tell the user it is not a known verb and then
**Show the verb list**.

## Show the verb list

Output **only** this table — no preamble, setup guides, or extra notes:

| Command | Who runs it | Purpose |
|---|---|---|
| `/draft help` | Everyone | Show this list. |
| `/draft guide` | Engineering & Shared Services | Bootstrap and start or resume guided catalog authoring. |
| `/draft review` | Everyone | Review an open PR for catalog correctness, or audit catalog content for quality and security compliance. |
| `/draft update` | Draft Admins | Check for DRAFT framework updates and guide a safe upgrade. |

End with one line: `Run /draft <verb> to start, e.g. /draft guide.`
