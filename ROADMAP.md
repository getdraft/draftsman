# DRAFT v1.0 Readiness Roadmap

This roadmap tracked the MVP work needed to move DRAFT from a credible
architecture catalog framework to a version 1.0 deployable architecture
platform.

The v1.0 goal was narrow and concrete: a Draftsman conversation should produce
a complete, compliant, reviewable architecture graph that can be translated
into a deployment plan without hiding operational or security gaps.

v1.0 is repo-first. It will not launch with a required DRAFT app, hosted
service, or DRAFT-specific CLI. A company should be able to connect its
preferred AI tool to a company DRAFT repo and have that AI become the
Draftsman by reading the repo bootstrap files and vendored framework copy.

## Status: All Tracked Issues Closed

The `v1.0` GitHub milestone is **100% complete**: all three canonical work
items (issues #3, #4, and #5) are closed and merged into `main`. This file is
kept as the historical record of that work and the rationale behind each
issue's resolution; GitHub Issues remain the source of truth for execution
detail, discussion, and ownership.

Cutting an actual `1.0.0` release (tagging, updating `draft-framework.yaml`,
and applying the post-1.0 versioning and branch-protection rules in
[VERSIONING.md](VERSIONING.md)) is a separate decision from milestone
completion and is intentionally not made by this roadmap file. That decision
belongs to the project maintainer.

## Tracking Model

Track execution in GitHub with:

- milestone: `v1.0`
- core labels: `v1.0`, `mvp`
- area labels: `deployment`, `automation`, `catalog`, `compliance`,
  `draftsman`

## Issue #3: v1.0: executable deployment contract — Closed (PR #95)

Problem:

DRAFT captured deployable architecture facts, but deployable was still mostly
a semantic promise. The framework needed one explicit path from approved DRAFT
objects to a generated deployment plan.

Resolution:

Delivered a machine-readable deployment target and environment binding
contract, deployment manifest generation from an approved
SoftwareDeploymentPattern and its closed deployable object graph, a dry-run
adapter path, graph-gating against unresolved DraftingSession questions and
invalid or non-compliant references, secrets represented only as references,
and validator coverage and documentation for the contract.

## Issue #4: v1.0: complete golden reference workspace — Closed (PR #24)

Problem:

The framework had strong schemas, RequirementGroups, and validation logic, but
the example catalog did not yet prove a complete product deployment path with
compliance evidence.

Resolution:

Shipped a golden workspace covering TechnologyComponents, Host, RuntimeService,
DataStoreService, NetworkService, ProductComponent, ReferenceArchitecture,
SoftwareDeploymentPattern, DecisionRecord, and DraftingSession examples, with
an activated compliance RequirementGroup, recorded `requirementImplementations`
evidence, acceptable-use TechnologyComponent mappings through capabilities, a
clean validation run, a regenerated browser, and documentation on using the
golden workspace as a regression target for v1.0 changes.

## Issue #5: v1.0: deterministic Draftsman production workflow — Closed (PR #26)

Problem:

Production authoring depended on general-purpose AI tools connected to a repo.
The framework needed enough bootstrap instructions, templates, examples,
validation, and PR workflow guidance for those tools to behave as a
deterministic Draftsman without a DRAFT-specific app.

Resolution:

Delivered an advisory pre-write review step (`preview_proposals` plus the Pre-
Write Review documentation), a validation-failure-to-repair-step mapping
(Validation Repair Procedures), source provenance recording on generated and
materially updated artifacts, and resumable DraftingSession state
(`resumptionContext`) with a documented resume procedure. Test coverage was
added for the pre-write gate and the Reference Architecture constraint
enforcement that the work also touched.

Two items from the issue's original acceptance criteria were deliberately
descoped rather than carried forward as follow-up work, based on the merged
PR's own resolution rationale:

- A fully structured (non-YAML) proposal data model and a dedicated
  schema-aware review-card UI were not built. DRAFT's repo-first, no-required-
  app design (above) makes a document-level advisory review — what shipped —
  the appropriate mechanism rather than purpose-built tooling.
- Pre-write validation was implemented and then deliberately reverted from a
  hard blocking gate to an advisory check, because stub and incomplete
  objects are expected to have validation gaps; enforcement happens at the
  `complete` catalog-status boundary, not at write time. Blocking writes of
  incomplete work would have prevented legitimately parking a session
  mid-draft.

## Future Enhancements: DRAFT Table And CLI

The local DRAFT Table app and `draft-table` CLI are useful prototypes, but they
are not part of the v1.0 launch promise. Keep them available for experiments,
but do not make onboarding, authoring, or validation depend on them.

Future work may revive the app as optional convenience tooling for:

- guided source upload and document extraction
- visual proposal review cards
- local validation repair loops
- local provider configuration and diagnostics
- commit and pull request helpers
- framework refresh helpers

Until then, the canonical workflow is the repo plus the user's chosen AI tool.
