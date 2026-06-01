---
description: Review company DRAFT catalog and content in a vendored workspace
argument-hint: "[object, domain, or area to review]"
allowed-tools: [Bash, Read, Glob, Grep, AskUserQuestion]
---

# /draft review

# === END FRONTMATTER ===

You are a DRAFT content reviewer for a **company workspace**. This verb reviews
the company's own catalog content — its objects, RequirementGroups, vocabulary,
and decision records — not the DRAFT framework itself. (To review the framework,
use `/draft review-framework`, an upstream-only verb.)

## Scope

Review the catalog content authored in this workspace for:

- **Completeness** — required fields populated, RequirementGroups satisfied,
  ownership and team assignments present.
- **Consistency** — naming conventions followed, vocabulary terms drawn from the
  workspace's declared lists, no contradictory or duplicate objects.
- **Clarity** — descriptions are meaningful to a reader who did not author them.
- **Governance** — governed fields use approved values; non-standard values are
  flagged for review rather than silently accepted.

## Procedure

1. Run validation first so structural problems surface before content judgement:
   follow the `validate` action (`draft-actions/validate.md`).
2. Read the workspace vocabulary lists (`.draft/workspace.yaml`) before judging
   any governed field. Treat answers outside approved choices as non-standard
   values that can be revisited or proposed for review.
3. Walk the catalog object by object, reporting findings grouped by severity
   (blocker / should-fix / nice-to-have) with a concrete fix for each.
4. Where a finding warrants tracked follow-up, note that it can be routed to a
   GitHub issue. The exact issue-creation workflow is defined in issue #51
   (shared Draft issue creation) and is not yet implemented — until then, list
   the findings for the user to act on.

## Notes

This verb is intended for vendored company workspaces. It is distinct from
`/draft review-framework`, which reviews the DRAFT framework for simplification
and adoption and is only meaningful in the upstream `getdraft/draftsman` repo.
