---
description: Check for DRAFT framework updates and guide a safe upgrade through branch, validate, and PR
argument-hint: ""
allowed-tools: [Bash, Read, Write, Edit]
---

# /draft-updateframework Command

> **Draft Admins only.** This command modifies the vendored framework copy at
> `.draft/framework/` and updates `.draft/framework.lock`. It must not be run
> by Engineering or Shared Services representatives. Framework updates affect every Draftsman
> session and every validation run in this workspace — only Draft Admins
> should initiate them.

## Step 1: Confirm Role

Before doing anything else, confirm the user understands this action:

> This command checks for a newer DRAFT framework version and, if one is
> available, walks you through updating the vendored copy in `.draft/framework/`.
> It should only be run by Draft Admins. Are you a Draft Admins representative for this
> workspace?

If the user says no or is unsure, stop and direct them to Draft Admins.

## Step 2: Read Current State

Read `.draft/framework.lock` to establish the baseline:

- `framework.source` — the upstream repo URL
- `framework.version` — the currently vendored version
- `framework.syncedCommit` — the SHA the workspace is currently on
- `framework.syncedTag` — the tag if applicable

Report this to the user:

> Your workspace is currently on DRAFT framework version **X.Y.Z**
> (commit `abc1234`), sourced from `<source>`.

## Step 3: Check for Updates

Fetch the latest tags from the upstream source without modifying the workspace:

```bash
git ls-remote --tags <framework.source>
```

Parse the tag list to find the highest semantic version tag. Compare to
`framework.version` from the lock file.

If **no newer version is available**:

> Your workspace is already on the latest DRAFT framework version (X.Y.Z).
> No update is needed.

Stop here.

If a **newer version is available**, report it clearly:

> A newer DRAFT framework version is available: **A.B.C**
> (current: X.Y.Z)
>
> Before updating, review the DRAFT changelog at:
> `https://github.com/getdraft/draftsman/blob/main/CHANGELOG.md`
>
> Look for any breaking changes or migration notes in versions between
> X.Y.Z and A.B.C. Would you like to proceed with the update?

If the user declines, stop.

## Step 4: Create an Update Branch

```bash
git checkout -b draft/framework-update-A.B.C
```

Confirm the branch was created before continuing.

## Step 5: Replace the Vendored Framework

Download the new framework version and replace the vendored copy:

```bash
# Fetch the new version into a temporary location
git clone --depth 1 --branch vA.B.C <framework.source> /tmp/draft-framework-update

# Replace the vendored copy
rm -rf .draft/framework
cp -r /tmp/draft-framework-update/framework .draft/framework
cp -r /tmp/draft-framework-update/templates .draft/framework/../templates 2>/dev/null || true

# Clean up
rm -rf /tmp/draft-framework-update
```

Resolve the exact commit SHA of the new version:

```bash
git ls-remote <framework.source> refs/tags/vA.B.C
```

## Step 6: Update the Lock File

Update `.draft/framework.lock` with the new version details:

```yaml
framework:
  source: <unchanged>
  vendoredPath: .draft/framework
  updatePolicy: explicit
  syncedRef: vA.B.C
  version: A.B.C
  syncedTag: vA.B.C
  syncedCommit: <resolved-sha>
```

## Step 7: Run Validation

```bash
python3 .draft/framework/tools/validate.py --workspace .
```

Capture the full output. Categorize results as errors, warnings, or clean.

### If validation is clean (no errors):

> Validation passed with no errors after the framework update to A.B.C.
> There are N warnings — [summarize them briefly].
>
> The workspace is ready to merge. Would you like me to:
> A) Commit the update and open a pull request to main
> B) Commit the update and let you review before opening a PR

Proceed with the user's choice. The commit message should be:

```
chore: update DRAFT framework from X.Y.Z to A.B.C
```

The PR title should be:

```
chore: DRAFT framework update — X.Y.Z → A.B.C
```

The PR body must include:
- old version and new version
- link to the DRAFT changelog between those versions
- validation status (pass / warnings)
- any warnings that remain after the update
- a note that Draft Admins reviewed and approved the update

### If validation produces new errors:

Report each new error clearly using plain language — do not show raw validator
output. Group errors by the catalog file they affect:

> The framework update introduced N new validation errors that need to be
> resolved before this update can merge:
>
> **catalog/hosts/eks-host.yaml**
> — `log-management`: requirement now needs a relationship object; an
>    architecture note is no longer sufficient. Add a relationship to your
>    central logging service.
>
> **catalog/runtime-services/kubernetes.yaml**
> — `primary-technology-component`: required field is now mandatory in A.B.C.
>    Add a reference to the Kubernetes TechnologyComponent.

Then offer to fix them:

> Would you like me to work through each of these with you now, or would
> you prefer to address them manually and re-run validation when ready?

If the user wants to fix them now, work through each error using the Draftsman
role from `.draft/framework/docs/draftsman.md`. Re-run validation after each
fix to confirm progress.

Once all errors are resolved, return to the clean-validation path above and
offer to commit and open the PR.

### If the user wants to abandon the update:

```bash
git checkout main
git branch -D draft/framework-update-A.B.C
```

> The update branch has been removed. Your workspace is unchanged at X.Y.Z.

## Step 8: Post-Update Notes

After the PR is merged, remind Draft Admins:

> After merging, any engineers using Claude Code should re-run the symlink
> setup to pick up any new commands shipped with A.B.C:
>
> ```bash
> ln -sf ../../.draft/framework/commands/draft-help.md .claude/commands/draft-help.md
> ln -sf ../../.draft/framework/commands/draftsman.md .claude/commands/draftsman.md
> ln -sf ../../.draft/framework/commands/draft-session.md .claude/commands/draft-session.md
> ln -sf ../../.draft/framework/commands/draft-validate.md .claude/commands/draft-validate.md
> ln -sf ../../.draft/framework/commands/draft-updateframework.md .claude/commands/draft-updateframework.md
> ln -sf ../../.draft/framework/commands/draft-triage.md .claude/commands/draft-triage.md
> ln -sf ../../.draft/framework/commands/draft-review.md .claude/commands/draft-review.md
> ```
>
> Review the CHANGELOG for any new setup steps or configuration changes
> introduced in A.B.C.
