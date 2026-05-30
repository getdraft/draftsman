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

Every AI agent, human maintainer, and automation workflow must classify a
framework change before committing it. Use this decision tree in order:

1. If the change alters schemas, RequirementGroups, Capability definitions,
   domain definitions, object contracts, or validation behavior, use the next
   pre-1.0 minor release: `0.(MINOR+1).0`.
2. If the change alters generated browser behavior, generated browser assets,
   framework docs, templates, DRAFT Table code, install scripts, packaging,
   release governance, or AI-facing guidance without changing the object
   contract, use the next patch release: `0.MINOR.(PATCH+1)`.
3. If the change only regenerates derived files such as `AI_INDEX.md` or
   `docs/index.html` from already-versioned source changes, use the version
   required by the source change.
4. If the change has no framework behavior, documentation, asset, generated UI,
   schema, validation, packaging, or AI-facing effect, it does not require a
   framework release.

An AI agent must not leave release-impacting framework changes only under an
`Unreleased` changelog entry when preparing a commit to `main`. It must update
`draft-framework.yaml` and create a numbered `CHANGELOG.md` entry in the same
commit or change set.

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
