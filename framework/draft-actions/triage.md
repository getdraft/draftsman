---
description: Pull open GitHub issues and work through selected ones
argument-hint: "[filter: bugs | features | docs | all]"
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep]
---

# /draft triage

Pull open GitHub issues for this repository, present them as a selection
table, and work through whichever the user picks.

## Step 1: Fetch Open Issues

Issues are pre-loaded at command start:

```
!`gh issue list --state open --limit 50 --json number,title,labels,createdAt,assignees 2>&1`
```

If the output contains an error (no GitHub CLI, not authenticated, no remote),
report:

> Could not reach GitHub. Make sure `gh` is installed and authenticated
> (`gh auth status`), and that this repository has a GitHub remote.

Stop if the output is an error.

If the output is an empty array (`[]`):

> No open issues found. The backlog is clear.

Stop.

## Step 2: Apply Filter

If `$ARGUMENTS` is provided and matches a valid filter, apply it:

| Filter | Applies to |
|---|---|
| `bugs` | Issues labelled `bug` or whose title contains fix/broken/wrong/error |
| `features` | Issues labelled `enhancement`, `feature`, or `feat` |
| `docs` | Issues labelled `documentation` or `docs` |
| `all` | All open issues (default when no argument given) |

If `$ARGUMENTS` is not provided, use `all`.

## Step 3: Present Issue Table

Display all matching issues as a numbered table:

```
  #   Issue   Title                                             Labels        Age
  ──────────────────────────────────────────────────────────────────────────────
  1   #42     SaaS delivery field keys mismatch                bug           2d
  2   #41     Add /update-framework command                    enhancement   5d
  3   #3      v1.0: executable deployment contract             v1.0, mvp     12d
  ...

Which issue would you like to work on? Enter a number, a range (e.g. 1-3),
multiple numbers (e.g. 1,3), or "all".
```

## Step 4: Read Selected Issues

For each selected issue, fetch the full detail:

```bash
gh issue view <number> --json number,title,body,labels,comments,assignees,state
```

Read the full body and any comments. Identify the issue type:

- **Bug** — something in the framework behaves incorrectly or produces
  contradictory results
- **Feature** — a new capability or object type is being requested
- **Documentation** — a doc is missing, wrong, or unclear
- **Question** — clarification needed; may not require a code or doc change
- **Chore** — maintenance task (version bump, cleanup, regeneration)

Present a brief summary to the user before acting:

> **Issue #N — [title]**
> Type: Bug / Feature / Documentation / Question / Chore
>
> [2-3 sentence summary of what the issue is asking for]
>
> How would you like to handle this?
> A) Work on it now
> B) Skip to the next issue
> C) Close as won't fix — I'll explain why

## Step 5: Work on the Issue

### If "Work on it now":

**Create a branch:**

```bash
git checkout -b fix/issue-N-short-description     # for bugs
git checkout -b feat/issue-N-short-description    # for features
git checkout -b docs/issue-N-short-description    # for documentation
```

**Investigate and implement:**

- For **bugs**: read the affected files, identify the root cause, implement
  the fix, validate with `python3 framework/tools/validate.py --workspace .`
  if the fix touches schemas, requirement groups, or catalog content.
- For **features**: discuss scope with the user before writing anything.
  Confirm the approach, then implement. If the feature is large, offer to
  stub it and open a draft PR.
- For **documentation**: locate the affected doc, make the change, check
  for any related files that need the same update.
- For **chores**: complete the task and confirm with the user before
  committing.

**Commit the work:**

Use a commit message that references the issue:

```
fix: [description] — closes #N
feat: [description] — closes #N
docs: [description] — closes #N
```

**Open a pull request:**

```bash
gh pr create \
  --title "[short description] — closes #N" \
  --body "$(cat <<'BODY'
## Summary
[what was changed and why]

## Issue
Closes #N

## Validation
[pass / warnings / not applicable]
BODY
)"
```

After the PR is opened, report the PR URL to the user.

### If "Close as won't fix":

Ask the user for the reason, then close the issue with a comment:

```bash
gh issue close <number> --comment "<reason>"
```

## Step 6: Continue or Stop

After each issue is handled, if there are more selected issues remaining:

> Issue #N handled. Next: **Issue #M — [title]**. Continue?

If the user says yes, proceed to the next issue. If no, stop and summarise:

> Session complete. Handled N issues: X worked on, Y skipped, Z closed.
