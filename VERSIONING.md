# DRAFT Versioning

DRAFT uses semantic version numbers for the framework, but the compatibility
promise changes before and after `1.0.0`.

The current framework version is recorded in `draft-framework.yaml`. DRAFT Table
has its own package version in `pyproject.toml`.

## Before 1.0.0

DRAFT is currently in pre-1.0 framework formation mode.

Version format:

```text
0.MINOR.PATCH
```

Rules:

- `0.MINOR.0` may include object model changes, schema changes, renamed
  concepts, validation changes, and migration work.
- `0.MINOR.0` may break existing workspaces, but the compatibility impact and
  migration steps must be documented in `CHANGELOG.md`.
- `0.MINOR.PATCH` is reserved for fixes, documentation corrections, generated UI
  corrections, validator bug fixes, packaging fixes, and small non-breaking
  cleanup.
- Patch releases must not intentionally change the object contract.
- Every release, including patch releases, requires release notes.
- Every object, schema, RequirementGroup, compliance, or validation contract
  change requires a compatibility statement.

## AI Release Decision Procedure

### In a Pull Request (normal workflow)

AI agents and human contributors submitting PRs must:

1. Add a `## Unreleased` section at the top of `CHANGELOG.md` with all five
   required subsections (`Compatibility Impact`, `Added`, `Changed`, `Fixed`,
   `Migration Notes`). Every section must be meaningful — no placeholders.
2. Do **not** touch `draft-framework.yaml`. Version promotion is automated.
3. The `promote-release` GitHub Actions workflow fires on merge to `main`,
   detects the `Unreleased` section, computes the correct next version
   (patch or minor based on changed files), replaces the `## Unreleased`
   header with `## X.Y.Z - date`, bumps `draft-framework.yaml`, and
   regenerates `AI_INDEX.md` in a follow-up commit.

The bump type is determined automatically by the promote workflow:

- Any file under `framework/schemas/`, `framework/configurations/capabilities/`,
  `framework/configurations/domains/`, `framework/configurations/requirement-groups/`,
  or `framework/tools/validate.py` → **minor** (`0.MINOR+1.0`).
- Everything else → **patch** (`0.MINOR.PATCH+1`).

### Classifying your change (for reference)

Use this to predict the bump type your PR will receive:

1. Schema, RequirementGroup, Capability, domain, or validation-behavior change → minor.
2. Docs, templates, browser assets, AI-facing guidance, install scripts,
   packaging, or release governance change → patch.
3. Derived-file-only regeneration (e.g. `AI_INDEX.md` from already-committed
   source changes) → same as the source change.
4. No governed files changed → no release entry needed.

### Direct commits to `main` (exceptional, pre-1.0 only)

If committing directly to `main`, either use `## Unreleased` (the promote
workflow handles the rest) or include a fully numbered `CHANGELOG.md` entry
and bump `draft-framework.yaml` in the same commit.

## At 1.0.0

`1.0.0` declares the first stable DRAFT compatibility baseline.

After `1.0.0`:

- `MAJOR` means existing valid company workspaces may require migration.
- `MINOR` means new capability with backward compatibility.
- `PATCH` means fixes only, with no intended behavior or contract change.

If updating the framework can make a previously valid company workspace fail
validation without the company opting into a stricter mode, that is a breaking
change. Before `1.0.0`, it belongs in a `0.MINOR.0` release. After `1.0.0`, it
requires a `MAJOR` release.

## Required Release Notes

Every numbered release entry in `CHANGELOG.md` must include:

- `Compatibility Impact`
- `Added`
- `Changed`
- `Fixed`
- `Migration Notes`

`Compatibility Impact` must say whether migration is required. `Migration
Notes` must say what a company workspace owner should do after refreshing the
framework. If no migration is required, say that explicitly.

Pull requests or direct commits that change governed framework files but do not
advance `draft-framework.yaml` are allowed only for exploratory branches that
are not ready to merge. They must put the same quality of notes under
`Unreleased`. Before merging or committing to `main`, move those notes into the
numbered release entry and advance `draft-framework.yaml`.

## Automated Enforcement

`.github/workflows/validate-catalog.yml` runs
`python3 framework/tools/check_release_notes.py --base "$BASE_SHA" --head "$GITHUB_SHA"`
on pushes to `main` and on pull requests.

The checker enforces these rules when a base ref is available:

- release-impacting framework changes must update `CHANGELOG.md`
- release-impacting framework changes must advance `draft-framework.yaml`
- pre-1.0 contract changes must use the next `0.MINOR.0`
- pre-1.0 non-contract framework changes must use the next patch release
- patch releases must not include schema, RequirementGroup, Capability, domain,
  or validation contract changes
- every numbered release must include meaningful `Compatibility Impact`,
  `Added`, `Changed`, `Fixed`, and `Migration Notes` sections

## Main Branch Rules

Before `1.0.0`, direct commits to `main` are allowed, but release-note checks
still run in CI so missing notes are visible immediately.

After `1.0.0`, changes to `main` should be made through pull requests only.
GitHub branch protection should require:

- a pull request before merging
- passing validation and release-note checks
- at least one approving review
- no unresolved conversations

Branch protection is the GitHub enforcement point for "PR only"; CI enforces
the repository-local release-note and compatibility rules.
