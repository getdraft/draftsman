---
name: draftsman-update
description: Use when a Draft Admin wants to check for a newer DRAFT framework version and upgrade the vendored copy safely through a branch, validation and a pull request. Needs the Author profile.
---

# Draftsman Update

Load `draftsman-core` first. This skill needs the **Author profile** and changes the vendored framework copy, so it is for Draft Admins only. Stop if the user is not one.

The verbatim procedure for every step below is in `references/steps.md`. Follow that file; the lines here are the map. This skill needs git and network access to the framework source; if you do not have them, say so and stop.

- **Step 1, confirm role:** confirm the user is a Draft Admin for this workspace; if not, stop and direct them to the Draft Admins.
- **Step 2, read current state:** read `.draft/framework.lock` and report the current version, commit and source.
- **Step 3, check for updates:** list upstream tags, compare with the lock, show the changelog link, and stop if there is nothing newer or the user declines.
- **Step 4, create an update branch:** create `draft/framework-update-<version>` and confirm it exists.
- **Step 5, replace the vendored framework:** fetch the target ref into a temporary clone, replace `.draft/framework`, record the commit, and remove the clone.
- **Step 6, update the lock file:** write the new version, ref and commit to `.draft/framework.lock`.
- **Step 7, run validation:** run the validator; the clean, new-errors and abandon paths are each spelled out in `references/steps.md`.
- **Step 8, post-update notes:** after the PR merges, remind Draft Admins about the one-time `/draft` command link and to review the CHANGELOG for new setup steps.

After the framework copy is replaced, rerun `python3 .draft/framework/tools/setup_ide.py` so the projected skills in `.claude/skills/` and the skill index in `AGENTS.md` match the new framework, then run `python3 .draft/framework/tools/validate_skills.py --workspace .` to confirm they are fresh.

## References

- `references/steps.md`: the full, verbatim step bodies.
