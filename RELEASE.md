# Release Checklist

Use this checklist whenever DRAFT Framework changes are promoted as a numbered
release.

## Classify The Change

- Current version in `draft-framework.yaml`:
- New version:
- Release phase: pre-1.0 or stable
- Compatibility impact: no migration, optional migration, or required migration
- Object/schema/validation contract changed: yes or no

Use the versioning decision procedure in `VERSIONING.md`:

- Pre-1.0 contract change: next `0.MINOR.0`.
- Pre-1.0 non-contract framework change: next `0.MINOR.PATCH`.
- Generated browser asset, generated UI, docs, templates, release governance,
  packaging, install, or AI guidance change: patch release.
- Derived-file-only regeneration follows the version selected for the source
  change.

## Update Release Files

- Update `draft-framework.yaml`.
- Update `CHANGELOG.md` with a numbered release entry.
- Include `Compatibility Impact`, `Added`, `Changed`, `Fixed`, and
  `Migration Notes`.
- Move any applicable notes out of `Unreleased`.
- If a change is not ready for a version bump, document it under `Unreleased`
  using the same section names only on an exploratory branch. Before committing
  or merging to `main`, assign a numbered version.
- For pre-1.0 breaking changes, use `0.MINOR.0` and document migration steps.
- For stable breaking changes after `1.0.0`, use a new major version.

## Validate

Run:

```bash
python3 framework/tools/validate.py
python3 -m unittest discover -s tests
python3 framework/tools/check_release_notes.py
python3 framework/tools/generate_ai_index.py
git diff --exit-code AI_INDEX.md
```

If browser-visible YAML, docs, schemas, or templates changed, also run:

```bash
python3 framework/tools/generate_browser.py
git diff --exit-code docs/index.html
```

## Publish

All changes reach `main` through a pull request. Direct pushes to `main` are
blocked by branch protection (see below), including for repository admins and
automated tools acting under an admin identity. This applies pre-1.0 as well as
after `1.0.0`.

When creating a release tag, use `vX.Y.Z` and verify it matches
`draft-framework.yaml`.

## Branch Protection On `main`

`main` is protected so that no contract change can land without passing the
release gate. The enforced rules are:

- **Pull request required before merge** — no direct pushes to `main`.
- **Required status check: `validate`** — the `validate` job in the
  `Validate Catalog` workflow (`.github/workflows/validate-catalog.yml`). It
  runs `validate.py`, the unit tests, `check_release_notes.py`, and the AI-index
  drift check. A PR cannot merge until this check passes.
- **Branches must be up to date before merging** (`strict`) — a PR is re-tested
  against the current tip of `main`, so a change cannot slip the gate by being
  based on an older `main`.
- **Enforced for administrators** — admins and tools pushing under an admin
  identity cannot bypass the rules.
- **Force pushes and branch deletion disabled.**

> **Caveat — do not rename the `validate` job.** The required status check is
> matched by the context name `validate`. If the job in
> `validate-catalog.yml` is renamed, update the required-check context in the
> branch protection settings at the same time, or pull requests will wait
> forever on a check that never reports.

To inspect or change the policy:

```bash
gh api repos/getdraft/draftsman/branches/main/protection
```

Relaxing `enforce_admins` to `false` would restore an admin emergency-push
lane; doing so reopens the path that previously let a schema change reach `main`
without a changelog entry, so prefer keeping it enabled.
