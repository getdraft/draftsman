# Changelog

All notable DRAFT Framework changes are recorded here. Every release requires
notes, including patch releases.

## 0.48.0 - 2026-06-04

Moves Domain capability membership to a generated read model derived from `Capability.domain`, eliminating the duplicated authored `domain.capabilities` edge.

### Compatibility Impact

- Domain objects no longer require an authored `capabilities` list. Existing Domain objects with `capabilities` still validate, but the field is deprecated and generated browser data derives membership from each Capability object's `domain` field.

### Added

- Added a shared domain-capability index builder for generated browser and future AI/search read models.
- Added browser payload indexes for `domainCapabilities`, `capabilityDomain`, and unassigned capabilities.
- Added regression tests proving Domain objects validate without authored capability lists and browser data derives the capability map from `capability.domain`.

### Changed

- Updated framework Domain configurations to remove duplicated authored `capabilities` lists.
- Updated browser Domain detail rendering to read the generated domain-capability index.
- Updated Domain schema and documentation to make `Capability.domain` the source of record for domain membership.

### Fixed

- Fixed Domain detail implementation link resolution to resolve lifecycle implementations from the capability being rendered, not the parent domain object.

### Migration Notes

- Remove `capabilities` from Domain YAML files. Ensure every Capability has a valid `domain` UID; generated assets will rebuild domain→capability navigation from those capability records.

## 0.47.0 - 2026-06-04

Rename all prose, headings, sidebar links, and documentation occurrences of "Architecture Objects" to "Shared Services Objects" or "Governance Objects" as appropriate, fully aligning the documentation and UI tiles with the three-role framework terminology.

### Compatibility Impact

- This release does not introduce any breaking changes to existing catalogs. All additions are backwards-compatible.

### Added

- Added "Engineering Objects" as a dedicated section in the DRAFT User Manual.

### Changed

- Updated DRAFT User Manual, Framework Overview, and DRAFT Object Types docs to replace "Architecture Objects" with "Shared Services Objects" or "Governance Objects".
- Renamed "architecture-objects" documentation links and IDs to "shared-services-objects" or "engineering-objects".
- Updated the browser "Teams" tile description to refer to "catalog objects" instead of "architecture objects".

### Fixed

- None.

### Migration Notes

- No migration steps are required.

## 0.46.0 - 2026-06-04

Adds a reusable compliance and verification integration for the OWASP Application Security Verification Standard (ASVS) v4.0.3, and updates the object model UML terminology to reflect "Shared Services".

### Compatibility Impact

- This release does not introduce any breaking changes to existing catalogs. All additions are backwards-compatible.

### Added

- Added an automated OWASP ASVS parser and RequirementGroup generator tool (`framework/tools/import_asvs.py`) to download and compile the standard.
- Bundled the standard OWASP ASVS v4.0.3 compliance pack as three modular, inheriting RequirementGroups: `asvs-l1` (Baseline), `asvs-l2` (Standard), and `asvs-l3` (Advanced).

### Changed

- Updated the DRAFT object model UML diagram and configurations to rename "Architecture Objects" to "Shared Services Objects", aligning with the three-role framework terminology.
- Updated the DRAFT User Manual section 1.1 "What DRAFT replaces" to describe DRAFT conceptually as the architecture diagram, deployment manifest, and audit evidence.

### Fixed

- None.

### Migration Notes

- No migration steps are required.

## 0.45.0 - 2026-06-02

Adds validator coverage for duplicate capability and domain names across native, provider, and workspace catalog layers.

### Compatibility Impact

- This release adds validation warnings only. Existing catalogs remain valid, but duplicate capability or domain names will now be reported so they can be reconciled before they appear as duplicate browser cards.

### Added

- Added validator warnings for duplicate capability and domain names across native, provider, and workspace objects.
- Added alias-aware suppression so intentional continuity aliases or object patches do not trigger duplicate-name warnings.
- Added regression tests covering duplicate capability warnings, duplicate domain warnings, and alias suppression.

### Changed

- None.

### Fixed

- Fixed a validator coverage gap where duplicate native/workspace capability or domain names could pass silently and later render as confusing duplicate browser entries.

### Migration Notes

- Existing catalogs do not require immediate migration. If validation reports a duplicate local capability or domain name, retire the local object and overlay the native object with an `object_patch`, or rename one of the objects.

## 0.44.1 - 2026-06-02

Clarifies GitHub activity ownership expectations for AI-assisted DRAFT work.

### Compatibility Impact

- This release does not introduce any breaking changes to existing catalogs. Documentation-only clarification.

### Added

- None.

### Changed

- Clarified that GitHub issues and pull requests are the shared activity log for DRAFT work.
- Clarified that agent responsibility should be tracked through real GitHub identities and activity rather than labels.

### Fixed

- None.

### Migration Notes

- No migration steps are required for this release. Existing objects and configurations remain valid.

## 0.44.0 - 2026-06-01

Introduces the DRAFT v1.0 deployment readiness validation contract, including environment target binding schemas, a template, automated secrets scanning, and a topological closed-graph completeness check.

### Compatibility Impact

- This release does not introduce any breaking changes to existing catalogs. All additions are backwards-compatible.

### Added

- Support for first-class environment target bindings via `DeploymentTarget` objects and its schema `framework/schemas/deployment-target.schema.yaml`.
- Added `templates/deployment-target.yaml.tmpl` for easy catalog onboarding and drafting of environment targets.
- Added `--deployment-ready <SDP_UID> <TARGET_UID>` command line option to `validate.py` to verify that a SoftwareDeploymentPattern is deployment-ready for a physical target environment.
- Implement a topological closed-dependency-graph validator for the `--deployment-ready` option, checking that every transitively referenced catalog object is fully mature and set to `catalogStatus: complete`.
- Added an automated, recursive plaintext secrets scanner in `validate.py` to scan all parsed configuration parameters and enforce the secure `secretReference` design pattern.
- Added comprehensive unit testing covering secrets scanner blocking and graph completeness validation.

### Changed

- None. This release introduces new schemas, templates, and validator verification steps only.

### Fixed

- None.

### Migration Notes

- No migration steps are required for this release. Existing objects and configurations remain valid.

## 0.43.0 - 2026-06-01

Adds quiet and summary-only modes to the validator command line tool, and clarifies requirement gap warning trace messages.

### Compatibility Impact

- This release does not introduce any breaking changes to existing catalogs. All additions are backwards-compatible.

### Added

- Support for `--quiet` / `-q`, `--summary-only`, and `--verbose` / `-v` command-line options in the `validate.py` validator script.
- Configured `--quiet` to suppress individual file PASS trace logs and validation warnings (only showing failures and final summary).
- Configured `--summary-only` to suppress individual pass/fail and errors/warnings detail, only outputting the high-level validation summary.
- Added comprehensive unit testing verifying `--quiet` option behavior.

### Changed

- Rephrased the standard unsatisfied requirement warning message from 'Satisfy [requirement] using ...' to 'Requirement not satisfied: [requirement]; satisfy using ...' to avoid confusion with trace logs of successful checks.

### Fixed

- None. This release introduces new command-line features and phrasing clarity only.

### Migration Notes

- No migration steps are required for this release. Existing objects and configurations remain valid.

## 0.42.0 - 2026-06-01

Expands capability satisfaction to support shared operational platform services, supports recursive system boundaries (subsystems), and resolves Acceptable Use view browser UI display bugs.

### Compatibility Impact

- This release does not introduce any breaking changes to existing catalogs. All additions are backwards-compatible.

### Added

- Support in schemas and validator for capability implementations to satisfy requirements by referencing shared operational services (`runtime_service`, `data_store_service`, `network_service`) in addition to local `technology_component` objects.
- Support in schemas and validator for `system` objects to recursively contain other `system` objects in their `containers` list to represent nested subsystems.

### Changed

- Framework schemas and browser rendering logic were updated to support the expanded capability satisfaction models and recursive system boundaries.

### Fixed

- Acceptable Use view in the browser now filters out and suppresses empty domain cards that contain no rows, reducing visual clutter.
- Acceptable Use capability drill-down in the browser now displays a clean human-readable `"Unresolved Component Reference"` label when the capability's implementation reference cannot be resolved, keeping the raw UID as a smaller subtitle.

### Migration Notes

- No migration steps are required for this release. Existing objects and configurations remain valid under the expanded schemas.

## 0.41.6 - 2026-06-01

Fixes manual framework update ref handling so bare semantic versions resolve to
the canonical `vX.Y.Z` release tags when those tags exist.

### Added

- A workflow-template guard that accepts manual `target_ref` values such as
  `0.41.6` or `refs/tags/0.41.6` and normalizes them to `v0.41.6` when that tag
  exists upstream.

### Changed

- Framework update docs now explicitly state that DRAFT release tags use
  `vX.Y.Z` and that bare `X.Y.Z` inputs are accepted as a convenience.

### Fixed

- Manual framework update runs no longer try only `refs/tags/X.Y.Z` when the
  upstream release tag is actually `refs/tags/vX.Y.Z`.

### Compatibility Impact

- None. This is an update workflow and documentation fix only.

### Migration Notes

Existing company workspaces should refresh their
`.github/workflows/draft-framework-update.yml` from the updated template to pick
up manual `target_ref` normalization.

## 0.41.5 - 2026-06-01

Removes remaining legacy role wording from command help and role-layer guidance
so the framework consistently uses Shared Services.

### Added

- None.

### Changed

- `/draft` help now lists `/draft author` and `/draft session` for Engineering
  and Shared Services.
- Reuse model and roles/layers docs now use Shared Services consistently.

### Fixed

- Removed stale legacy role names from current docs and prior changelog notes
  that could confuse vendored company workspace guidance.

### Compatibility Impact

- None. This is terminology and AI instruction guidance only.

### Migration Notes

Existing company workspaces should refresh their vendored framework copy to
pick up the corrected `/draft` help text.

## 0.41.4 - 2026-06-01

Adds a `/draft security` workflow for security RequirementGroup authoring,
satisfaction design, posture review, and artifact compliance audit in company
workspaces.

### Added

- `framework/draft-actions/security.md` for CISO, security architect,
  security engineering, compliance/GRC, and delegated risk owner workflows.
- `/draft security [requirements|satisfaction|review|audit]` dispatcher,
  command help, AI configuration, IDE integration, and workspace template
  guidance.

### Changed

- Draftsman security/compliance docs now describe the security review persona,
  workspace boundary, concrete satisfaction mechanisms, and placeholder
  evidence limits.

### Fixed

- None.

### Compatibility Impact

- None. This is command and AI instruction guidance only; no schema, object
  model, validator, or RequirementGroup contract changed.

### Migration Notes

Existing company workspaces should refresh their workspace bootstrap and IDE
integration files from the updated templates if they want `/draft security`
advertised in root AI instruction files.

## 0.41.3 - 2026-06-01

Updates the generated browser's Acceptable Use view so users can drill from
domains to capabilities to the TechnologyComponents mapped as acceptable-use
implementations, with lifecycle status visible at the point of technology
selection.

### Added

- Domain tile landing view for Acceptable Use.
- Capability tile drilldown for each domain.
- Capability detail view listing mapped TechnologyComponents, vendor/product
  details, configuration labels, implementation lifecycle, and component
  lifecycle.
- Hash state for deep links to Acceptable Use domain and capability drilldowns.

### Changed

- Acceptable Use now opens on domain tiles instead of a domain-section table.
- Generated browser shell assets refreshed for the updated Acceptable Use
  navigation.

### Fixed

- None.

### Compatibility Impact

- None. This is a browser/navigation enhancement over existing Domain,
  Capability, TechnologyComponent, and capability implementation data.

### Migration Notes

No catalog migration is required.

## 0.41.2 - 2026-06-01

Adds the upstream framework feedback path for company vendored workspaces so
assistants know when to recommend a public DRAFT framework bug report or feature
request instead of patching around framework-owned findings locally.

### Added

- Public GitHub issue forms for DRAFT framework bugs and reusable framework
  feature requests.
- Draftsman upstream feedback routing guidance covering safe public context,
  issue-template selection, confirmation before public issue creation, and
  confidentiality boundaries.

### Changed

- `/draft author`, `/draft session`, `/draft validate`, `/draft review`, and
  `/draft update` now point assistants to the upstream feedback routing path
  when a framework-owned bug or reusable feature request is discovered.
- Workspace bootstrap templates now tell company-connected assistants to
  recommend sanitized upstream reports for framework-owned issues.

### Fixed

- None.

### Compatibility Impact

- None. This is AI instruction, command guidance, and public issue-template work
  only; no schema, object model, RequirementGroup, or validator contract changed.

### Migration Notes

Existing company workspaces should refresh their workspace bootstrap files from
the updated templates if they want the upstream framework feedback guidance in
root AI instruction files.

## 0.41.1 - 2026-06-01

Fixes the vendored workspace framework updater when upstream tags are missing
or stale. The updater now compares the latest visible release tag with
upstream `main`'s `draft-framework.yaml` version and selects `main` when it is
newer, so company workspaces can still discover the current framework version.

### Added

- None.

### Changed

- `/draft update`, workspace documentation, and README guidance now describe
  the stale-tag fallback behavior.

### Fixed

- The generated DRAFT framework update workflow now falls back to upstream
  `main` when the latest visible semver tag is older than the version declared
  by `main`'s `draft-framework.yaml`.
- Main-based updates now link to the main changelog instead of a non-existent
  release tag URL.

### Compatibility Impact

- None. This is an updater and documentation fix only; no schema, object model,
  RequirementGroup, or validator contract changed.

### Migration Notes

Existing company workspaces should refresh their
`.github/workflows/draft-framework-update.yml` from the updated workspace
template if they want automatic stale-tag fallback behavior.

## 0.41.0 - 2026-06-01

Completes the `architectureNote`→DecisionRecord cleanup by applying the rule to the opt-in compliance packs and removing `architectureNote` from the satisfaction allowlist entirely (closes #74). With every shipped RequirementGroup now free of note-based satisfiers, `architectureNote` is no longer an accepted answer type anywhere — it is purely a drafting annotation.

### Added

- **Compliance example DecisionRecords**: 26 "Security and Compliance decisions" DecisionRecords (one per affected object) satisfying the re-activated Security & Security Compliance pack in the examples catalog.

### Changed

- **Compliance packs converted**: `requirement-group-draft-nist-csf.yaml`, `requirement-group-draft-soc2.yaml`, `requirement-group-draft-tx-ramp.yaml`, and `requirement-group-draft-security-compliance.yaml` had their `architectureNote` satisfiers (53) and `field`-into-`architectureNotes` satisfiers (19) replaced with `decisionRecord` (keyed by the former note key); `validAnswerTypes` recomputed.
- **`architectureNote` removed from `VALID_REQUIREMENT_ANSWER_TYPES`** — no RequirementGroup may declare it as a satisfaction mechanism.
- **Compliance re-activated in the examples workspace** (`Security & Security Compliance`), and the OpenStack SDP's compliance satisfactions restored via DecisionRecords.
- **Fixed a latent key-collision from #71**: runtime/data example objects referenced the Host requirement's `healthWelfareMonitoringApproach` key instead of the Service Behavior/DataStoreService `healthWelfareMonitoring` key; corrected so the health-welfare-monitoring requirement resolves under the re-activated compliance pack.
- Regenerated `AI_INDEX.md` for the new DecisionRecords.

### Fixed

- None.

### Compatibility Impact

- **Behavioral, for workspaces using the compliance packs.** A `complete` object that satisfied a compliance requirement via an inline note now requires a DecisionRecord (or concrete evidence). `stub`/`incomplete` objects only warn. No object model or schema field was removed.

### Migration Notes

Workspaces that activate the NIST CSF, SOC 2, TX-RAMP, or Security & Security Compliance packs should commit DecisionRecords for any control previously satisfied by an inline `architectureNote`, referencing them from the object's `decisionRecords` list with a `key` matching the control. `architectureNote` is no longer a valid `canBeSatisfiedBy`/`validAnswerTypes` mechanism in any RequirementGroup.

## 0.40.0 - 2026-06-01

Enforces the DRAFT principle that an `architectureNote` is a drafting placeholder, not a requirement satisfaction (closes #71). A note lets a DraftingSession continue when information or the right decision-maker is not yet available, but the requirement is met only when the decision is committed as a DecisionRecord (or satisfied by concrete implementation). Because requirement gaps already warn for `stub`/`incomplete` objects and fail only for `complete` ones, drafting is unaffected — only completion now requires a real answer. Scope is the always-on core RequirementGroups; the opt-in compliance packs are deferred to a follow-up.

### Added

- **`decisionRecord` satisfaction mechanism** is now usable for non-capability "document X" requirements via a top-level `key`, matched against an object's `decisionRecords` entry whose `key` (or `concern`) equals it. Capability-scoped decisions continue to match via `criteria.capability`.
- **Concern-grouped example DecisionRecords**: 76 DecisionRecords across 23 example objects (grouped by concern — identity/access, observability, resilience, data protection, deployment, integration) replace note-based satisfaction in the OpenStack demo catalog.

### Changed

- **`architectureNote` no longer satisfies a requirement** (`validate.py`: `mechanism_satisfied` and `implementation_resolves` return `False` for it). It remains a recognized answer type so deferred RequirementGroups still parse, but it never resolves a requirement.
- **Core RequirementGroups converted**: all `architectureNote` satisfiers (and `field`-into-`architectureNotes` satisfiers) in the 13 always-on RGs were replaced with `decisionRecord` (keyed by the former note key). The ReferenceArchitecture `deployment-qualities` requirement is now also satisfiable by the structured `applicableDefinitionChecklist` field.
- Regenerated `AI_INDEX.md` for the new DecisionRecords.

### Fixed

- None.

### Compatibility Impact

- **Behavioral.** A `complete` object that previously satisfied a requirement with an inline `architectureNote` now fails until the decision is committed as a DecisionRecord or satisfied by concrete evidence. `stub`/`incomplete` objects only warn, so in-progress drafting is unaffected. No object model or schema field was removed.

### Migration Notes

For each `complete` object that relied on notes, add a `decision_record` object and reference it from the object's `decisionRecords` list with a `key` matching the requirement (or satisfy the requirement with concrete evidence). The compliance packs (NIST CSF, SOC 2, TX-RAMP, Security & Security Compliance) still accept note-style satisfiers and were deactivated in the examples workspace for now; their cleanup and re-activation is tracked as a follow-up to #71.

## 0.39.0 - 2026-05-31

Phase 2 of the native capability vocabulary (follow-up to #66 via #70): promotes generic delivery, integration, analytics, and certificate-management outcomes into native DRAFT capabilities and traces them through the existing Service Capability RequirementGroup using the same conditional, self-declared pattern as Phase 1. Adds three new domains.

### Added

- **Three domains**: `Software Delivery`, `Integration`, `Analytics` (`framework/configurations/domains/`).
- **Nine native capabilities**: `CI/CD Pipeline`, `Artifact Management`, `Configuration Management` (Software Delivery); `Email Delivery`, `File Transfer`, `Data Integration` (Integration); `Analytics`, `Reporting` (Analytics); `Certificate Management` (Security). All ship `complete` with framework `definitionOwner` and empty `implementations`.
- **Nine conditional self-declared requirements** added to the Service Capability RequirementGroup, one per new capability, gated on `capabilities contains <uid>` and scoped via `appliesTo` (`runtime_service`, except File Transfer on `network_service`). Each traces its capability through `relatedCapability` and is satisfied by concrete technical evidence or a committed DecisionRecord — never a bare note.

### Changed

- Added `Certificate Management` to the Security domain's capability list and regenerated `AI_INDEX.md`.
- Extended the native-vs-company-local guidance in `framework/docs/capabilities.md` to cover the delivery, integration, and analytics outcomes.

### Fixed

- None.

### Compatibility Impact

- None for existing catalogs. The new requirements are conditional on a service self-declaring a native capability; no current object references the new capability UIDs, so nothing gains a new obligation.

### Migration Notes

No manual workspace migration is required. As with Phase 1, workspaces that created generic local capabilities for these outcomes should declare the native capability UID on the providing service over time. Remaining open design work (consumer-side demand for outcomes a ProductComponent *needs*, and a possible migration helper) stays tracked under #70; the framework-wide `architectureNote`-as-satisfier cleanup is tracked under #71.

## 0.38.0 - 2026-05-31

Begins promoting generic architecture outcomes into native DRAFT capability vocabulary (Phase 1: network, runtime, and data outcomes) so company workspaces stop reinventing them as local capabilities. New native capabilities are traced from a new always-on Service Capability RequirementGroup using conditional, self-declared requirements: a shared service declares the capability it provides in its `capabilities` list, and the matching requirement demands the service document how that capability is delivered. Requirements are conditional on the self-declaration, so existing objects gain no new obligations.

### Added

- **Eleven native capabilities**: `API Gateway`, `DNS`, `CDN`, `WAF` (Network domain); `Application Runtime`, `Service Mesh`, `Caching`, `Messaging` (Compute & Runtime domain); `Data Persistence`, `Object Storage`, `File Storage` (Data domain). All ship `complete` with framework `definitionOwner` and empty `implementations`.
- **Service Capability RequirementGroup** (`requirement-group-service-capability.yaml`, always-on, applies to `runtime_service`/`data_store_service`/`network_service` across all delivery models): one conditional self-declared requirement per native capability, gated on `capabilities contains <uid>` and scoped per requirement via `appliesTo`. Each requirement traces its capability through `relatedCapability` and is satisfiable by concrete technical evidence (a TechnologyComponent configuration/internal component, or a relationship to a providing service) **or** a committed DecisionRecord — never by a bare architecture note.
- **`decisionRecord` satisfaction mechanism** in `validate.py`: a requirement can now be satisfied by a committed DecisionRecord referenced from the object's `decisionRecords` list with a `capability` key matching the requirement's capability. Added to `VALID_REQUIREMENT_ANSWER_TYPES` and to both the auto-resolution (`mechanism_satisfied`) and object-implementation (`implementation_resolves`) paths. This makes the "decision instead of implementation" path a first-class, capability-specific way to resolve a requirement.
- **Native vs company-local capability guidance** in `framework/docs/capabilities.md`: when to use a native capability versus minting a company-local one, how native service capabilities are self-declared, and the rule that an inline `architectureNote` is a drafting placeholder that does not satisfy a requirement until it is committed as a DecisionRecord.

### Changed

- **Regenerated `AI_INDEX.md`** to register the eleven new capabilities and the new RequirementGroup.

### Fixed

- None.

### Compatibility Impact

- None for existing catalogs. The new requirements are conditional on a service self-declaring a native capability; no current object references the new capability UIDs, so nothing gains a new obligation. When a workspace migrates a generic local capability to its native equivalent (by declaring the native UID), the service is then asked to document delivery of that capability.

### Migration Notes

No manual workspace migration is required to upgrade. Workspaces that previously created generic local capabilities (caching, messaging, object storage, API gateway, etc.) should, over time, declare the native capability UID on the providing service instead, and reserve company-local capabilities for genuinely company-specific outcomes. Phase 2 (delivery, integration, analytics, and security/identity outcomes, plus a possible migration helper) is tracked as a follow-up to #66.

## 0.37.0 - 2026-05-31

Traces the four framework-native network capabilities (Network Connectivity, Network Segmentation, Traffic Management, WAN Connectivity) from the base NetworkService RequirementGroup so they resolve to a requirement demand signal, then promotes every traced framework-native capability out of `incomplete` so DRAFT no longer ships capabilities at provisional maturity. Previously the validator warned that the network capabilities were untraceable, forcing vendored company workspaces to invent artificial company-specific requirements just to satisfy traceability.

### Added

- None.

### Fixed

- **Untraced native network capabilities**: Added capability-keyed satisfaction mechanisms to the `network-function` requirement in `requirement-group-network-service.yaml`, referencing `01KSWVZSZ5-Q6HW` (Network Connectivity), `01KSWVZSZ5-1RTH` (Network Segmentation), `01KSWVZSZ5-M0FR` (Traffic Management), and `01KSWVZSZ5-26F1` (WAN Connectivity). A NetworkService can now declare its function either with the existing `networkFunction` field/architectureNote or by referencing a TechnologyComponent that provides one of the native network capabilities. `minimumSatisfactions` remains `1`, so existing NetworkService objects are unaffected.

### Changed

- **Native capabilities promoted to `complete`**: All eleven framework-native capabilities that were still labeled `catalogStatus: incomplete` are now `complete`, since each is traceable to a RequirementGroup demand signal and structurally identical to the capabilities already shipped as complete. Promoted: Network Connectivity, Network Segmentation, Traffic Management, WAN Connectivity (newly traceable via this release), plus Application Performance Monitoring, Container Orchestration, Performance and Load Testing, Quality Gates, Serverless Function Runtime, Test Authoring, and Test Execution and Automation (already traced). DRAFT no longer ships any capability at `incomplete`.

### Compatibility Impact

- None. The NetworkService change only broadens how the existing `network-function` requirement can be satisfied, and capability promotion is a definition-maturity label change with no new object obligations. Workspace-activated compliance RequirementGroups (TX-RAMP, NIST CSF, SOC 2) remain intentionally provisional and are unaffected.

### Migration Notes

No manual workspace migration is required. Vendored workspaces pick up the traceability fix and capability maturity on their next framework refresh.

## 0.36.3 - 2026-05-31

Replaces the monolithic company onboarding tutorial with three role-targeted onboarding guides aligned to the standardized DRAFT roles (Engineering, Shared Services, Draft Admins), reducing cross-role cognitive load and giving each audience a focused time-to-first-action path.

### Added

- **Engineering Onboarding Guide**: New tutorial at `framework/docs/engineering-onboarding.md` covering ProductComponents, DataComponents, and SoftwareDeploymentPatterns for product development teams.
- **Shared Services Onboarding Guide**: New tutorial at `framework/docs/shared-services-onboarding.md` covering TechnologyComponents, Hosts, RuntimeServices, DataStoreServices, and NetworkServices for platform/infrastructure teams.
- **Draft Admins Onboarding Guide**: New tutorial at `framework/docs/draft-admins-onboarding.md` covering workspace bootstrapping, vocabularies, RequirementGroups, and ongoing governance for workspace administrators.

### Changed

- **Onboarding references repointed**: Updated `README.md`, `framework/docs/overview.md`, `framework/docs/workspaces.md`, `framework/draft-actions/review-framework.md`, `llms.txt`, `AI_INDEX.md`, `framework/tools/generate_ai_index.py`, and `draft_table/draftsman.py` to reference the three role-specific guides. Each guide links to the central Draft Operations Guide for ongoing operating policies.

### Removed

- **Monolithic onboarding tutorial**: Deleted `framework/docs/company-onboarding.md`, now superseded by the three role-targeted guides.

### Fixed

- None.

### Compatibility Impact

- None. Documentation-only change.

### Migration Notes

No manual workspace migration is required.

## 0.36.2 - 2026-05-31

Creates the comprehensive DRAFT Operations Guide, consolidating all operational commands, registry configurations, ownership routing, generated CODEOWNERS behaviors, issue creation formats, standard label patterns, and issue lifecycles.

### Added

- **Draft Operations Guide**: Published a comprehensive governance and operations standard at `framework/docs/operations-guide.md` providing step-by-step guidance on commands, issue lifecycles, and standard dispositions.

### Changed

- **Operations Guide Location renamed**: Renamed the partial draft `framework/docs/operations.md` to `framework/docs/operations-guide.md` and registered the updated file in `AI_INDEX.md`.

### Fixed

- None.

### Compatibility Impact

- None. Standalone legacy command forms are officially deprecated in documentation in favor of the unified `/draft <verb>` command structures.

### Migration Notes

No manual workspace migration is required.

## 0.36.1 - 2026-05-31

Reorganizes catalog files from a flat folder structure under `catalog/` into role-specific subfolders (`engineering/`, `shared-services/`, `governance/`) to align with role terminology (Issue #53) and the team registry (Issue #54).

### Added

- **Nested Catalog Folders**: Reorganized workspace catalog templates in `templates/workspace/catalog/` and example catalog items in `examples/catalog/` into nested paths grouped by content role (`engineering/`, `shared-services/`, `governance/`).

### Changed

- **Backward-Compatible Folder Scanning**: Updated `framework/tools/generate_browser.py` and `draft_table/catalog.py` to scan both the old flat catalog folder names and the new role-nested folder names.
- **AI Index and Docs updated**: Updated `framework/tools/generate_ai_index.py` with nested example catalog folder paths, regenerated `AI_INDEX.md`, and updated path references in `draftsman.md`, `how-to-add-objects.md`, and `user-manual.md`.

### Fixed

- None.

### Compatibility Impact

- None. Both flat and role-nested folders are supported by the browser and CLI tools, ensuring 100% backward-compatibility for existing flat and new nested workspaces.

### Migration Notes

1. To transition an existing workspace to the new nested directory structure, create `catalog/engineering/`, `catalog/shared-services/`, and `catalog/governance/` folders.
2. Move product components, data components, and software deployment patterns under `engineering/`.
3. Move hosts, runtime services, data store services, network services, and technology components under `shared-services/`.
4. Move decision records, sessions, relationships, systems, and reference architectures under `governance/`.
5. Rerun `/draft validate` to verify the new organization structure.

## 0.36.0 - 2026-05-31

Establishes the authoritative team registry model, team routing semantics, and programmatic CODEOWNERS generation. Introduces strict validation rules requiring owner team assignment for complete catalog artifacts.

### Added

- **DRAFT Operations & Governance Guide**: added `framework/docs/operations.md` covering the schema definition for the authoritative team registry (`vocabulary.teams`), programmatic ownership resolution, default folder/role CODEOWNERS fallbacks, and the fallback team routing logic.
- **Strict Ownership Validation**: updated `framework/tools/validate.py` to enforce that `owner.team` must be defined for all first-class artifacts (warning for `stub` or `incomplete` catalogStatus, failure for `complete` status). Excluded framework-owned base files and unit test temporary directories.

### Changed

- **AI Index updated**: registered the operations guide in `AI_INDEX.md`.

### Fixed

- None.

### Compatibility Impact

This is a contract change. Complete catalog objects in existing workspaces that do not have `owner.team` assigned will now fail validation, and incomplete ones will generate warnings.

### Migration Notes

1. Run `/draft validate` to find all complete or incomplete catalog objects missing ownership.
2. In each workspace, update the objects to add a valid `owner.team` mapping that matches the company team vocabulary.
3. Generate the updated `CODEOWNERS` file from the team registry vocabulary if using automated generation.

## 0.35.2 - 2026-05-31

Adds the comprehensive specification for DRAFT's issue routing semantics, default labels, and accountable team resolution rules.

### Added

- **Issue Routing Semantics & Default Labels**: expanded `framework/docs/ticketing.md` to define DRAFT's minimal labeling strategy (`draft`, `needs-triage`, exact role, exact severity, and conditional `needs-routing` labels), role-specific ownership scopes, 3-tier team resolution sequence (Artifact, CODEOWNERS, Fallback), and downstream override configuration.

### Changed

- None.

### Fixed

- None.

### Compatibility Impact

None. This release adds documentation and specifications only.

### Migration Notes

No migration is required.

## 0.35.1 - 2026-05-31

Adds the comprehensive specification for DRAFT's shared issue creation and ticketing workflow.

### Added

- **Ticketing & Issue Creation Workflow**: added `framework/docs/ticketing.md` defining the issue body contract (human-readable sections + machine-readable YAML metadata), the deterministic duplicate detection mechanism, fallback routing when ownership is missing, and the interactive issue generation UX.

### Changed

- **AI Index updated**: registered the ticketing guide in `AI_INDEX.md`.

### Fixed

- None.

### Compatibility Impact

None. This release adds documentation only.

### Migration Notes

No migration is required.

## 0.35.0 - 2026-05-31

Collapses the legacy `/draft-*` slash commands into a single `/draft` command
family whose first argument is a verb, and adds a company-facing `/draft review`
verb distinct from the upstream-only `/draft review-framework`.

### Added

- **Unified `/draft` dispatcher**: added `framework/commands/draft.md` as the
  sole registered DRAFT command. `/draft` (or `/draft help`) prints the verb
  list; `/draft <verb>` routes the first argument to an action file under
  `framework/draft-actions/` and follows it.
- **`/draft review` verb**: added `framework/draft-actions/review.md` for
  reviewing company catalog/content in vendored workspaces, separate from the
  upstream-only framework review.

### Changed

- **Retired the `/draft-*` command surface**: the standalone `/draftsman`,
  `/draft-session`, `/draft-validate`, `/draft-triage`, `/draft-review`,
  `/draft-updateframework`, and `/draft-help` commands, plus the
  `/validate-catalog` alias, are removed. Their bodies now live as verbs:
  `author`, `session`, `validate`, `triage`, `review-framework`, `update`.
- **Action file headers**: updated each `framework/draft-actions/*.md` heading
  to its `/draft <verb>` name.
- **Claude Code command linking**: `.claude/commands/` now links a single
  `draft.md`; setup, update, and integration docs link only `/draft`.
- **Docs updated to verb syntax**: `draftsman-ai-configuration.md`,
  `setup-mode.md`, `framework/integrations/README.md`, the Cursor and Windsurf
  integration files, and `framework/draft-actions/update.md` now advertise the
  `/draft <verb>` form only.
- **Workspace templates updated**: `templates/workspace/AGENTS.md.tmpl`,
  `README.md.tmpl`, `GEMINI.md.tmpl`, `.windsurfrules.tmpl`,
  `.cursor/rules/draftsman.mdc.tmpl`, and
  `.github/copilot-instructions.md.tmpl` now generate the `/draft <verb>`
  command surface for new company workspaces.

### Fixed

- **Broken command symlinks**: removed the dangling `.claude/commands/draft-*`
  symlinks left pointing at the retired `framework/commands/draft-*.md` files.

### Compatibility Impact

This is a breaking change to the command surface. The legacy `/draft-*` commands
and `/validate-catalog` no longer resolve. Anyone with the old per-command
symlinks must re-link the single `/draft` command. There is no compatibility
shim — invoking an old command name will fail.

### Migration Notes

1. In each workspace using Claude Code, remove any old command symlinks and link
   the unified command:
   ```bash
   rm -f .claude/commands/draft-*.md .claude/commands/draftsman.md
   mkdir -p .claude/commands
   ln -sf ../../.draft/framework/commands/draft.md .claude/commands/draft.md
   ```
2. Replace any references to `/draftsman`, `/draft-session`, `/draft-validate`,
   `/draft-triage`, `/draft-review`, `/draft-updateframework`, `/draft-help`, or
   `/validate-catalog` in local docs or muscle memory with the corresponding
   `/draft <verb>` form (`author`, `session`, `validate`, `triage`,
   `review-framework`, `update`, `help`).

## 0.34.0 - 2026-05-31

Standardizes DRAFT role terminology around Engineering, Shared Services, and Draft Admins to clarify ownership layers rather than individual job titles.

### Added

- **Standardized role-based onboarding guides issue**: Filed issue #57 to track building role-specific onboarding guides for `Engineering`, `Shared Services`, and `Draft Admins`.

### Changed

- **Standardized roles in schemas**: Updated all 15 schemas to use the new standardized machine roles: `engineering` (was `engineer`), `shared-services` (was `technology-admin`), and `draft-admins` (was `draft-admin`) in their `defaultOwnerRole` values.
- **CODEOWNERS template updated**: Realigned `templates/workspace/CODEOWNERS.tmpl` to map the new standardized role-based layers and folder paths.
- **Role terminology standardized in docs**: Updated `roles-and-layers.md`, `draftsman.md`, `setup-mode.md`, and `overview.md` to use standard role terms: `Engineering`, `Shared Services`, and `Draft Admins`.
- **Draft Actions role updates**: Renamed framework command files and standard role checks in `review-framework.md` and `update.md`.

### Fixed

- **Singular/plural consistency**: Resolved inconsistent singular/plural references to role names in all documentation and action files.

### Compatibility Impact

Workspaces migrating to framework version `0.34.0` must update their `.github/CODEOWNERS` files and any custom configurations referencing old machine roles (`engineer`, `technology-admin`, `draft-admin`) to the new standardized machine names (`engineering`, `shared-services`, `draft-admins`).

### Migration Notes

1. Update your workspace `.github/CODEOWNERS` file based on the new `templates/workspace/CODEOWNERS.tmpl` structure.
2. If your workspace contains custom configurations, vocabularies, or object-patches that reference `ownerRole: engineer`, `ownerRole: technology-admin`, or `ownerRole: draft-admin`, update them to `engineering`, `shared-services`, or `draft-admins` respectively.

## 0.33.0 - 2026-05-31

Retires `EdgeGatewayService` as a supported object type, expands
`NetworkService` to cover intrinsic network and traffic-control behavior, and
codifies the object-type and RequirementGroup principles that decide when a
new object type is warranted.

### Added

- **Object types as requirement scopes**: added AI-facing guidance in
  `design-principles.md`, `object-types.md`, `requirement-groups.md`, and
  `draftsman.md` explaining that object types exist so the Draftsman can apply
  the right base requirements. Context such as network zone, exposure, delivery
  model, capability, data classification, or followed ReferenceArchitecture can
  add obligations without changing the object's intrinsic type.
- **ReferenceArchitecture and RequirementGroup governance relationship**:
  documented that RequirementGroups state obligations, while
  ReferenceArchitectures show approved multi-object compositions for satisfying
  obligations that no single service or component can answer alone.
- **NetworkService authoring template and migrated example**: added
  `templates/network-service.yaml.tmpl` and migrated the OpenStack HAProxy
  example from an edge gateway object to a `network_service` object with
  `networkFunction`, `networkTopology`, and `protocols` evidence.

### Changed

- **Removed `edge_gateway_service` from the object contract**: deleted the
  EdgeGatewayService schema, template, scaffold folder, example folder, and
  generated/browser references. RequirementGroups, ReferenceArchitectures,
  validation constants, C4/Backstage/browser generators, Draft Table labels,
  tests, and AI guidance now use `network_service` where the intrinsic behavior
  is network or traffic control.
- **Expanded NetworkService schema coverage**: NetworkService now carries the
  service-like fields needed by delivery-model RequirementGroups, including
  `host`, `primaryTechnologyComponent`, `internalComponents`,
  `deploymentConfigurations`, `configurations`, `vendorGovernance`,
  `authenticationModel`, `patchingOwner`, `architectureNotes`,
  `decisionRecords`, and requirement implementations.
- **Tightened hosting semantics**: ProductComponent `runsOn` and SDP
  `serviceGroup.substrate` now reference only a RuntimeService or Host.
  NetworkService participation is modeled through service groups,
  relationships, network zones, RequirementGroups, and ReferenceArchitecture
  conformance instead of being treated as a hosting substrate.
- **ReferenceArchitecture constraints use NetworkService**: the bundled
  three-tier, multi-tenant SaaS, and serverless ReferenceArchitectures now
  require `network_service` presentation-tier roles when their patterns need
  traffic control, WAF, API gateway, ingress, event ingress, or load-balancing
  composition.

### Fixed

- **Stale Product Service wording**: replaced remaining AI-facing documentation
  references to the retired Product Service name and nonexistent
  `product-service.schema.yaml` with ProductComponent terminology and schema
  links.
- **Generated and browser labels**: regenerated `AI_INDEX.md`, browser data,
  browser shell assets, the user manual, company vocabulary page, and the
  object model diagram so AI and browser discovery no longer surface
  EdgeGatewayService as an active object type.

### Compatibility Impact

Required migration for any workspace that contains `type: edge_gateway_service`
or files under `catalog/edge-gateway-services/`. No compatibility shim is kept
in this release. After refreshing the framework, those objects are unsupported
and will not validate as active catalog objects.

Existing EdgeGatewayService objects do not have a default replacement target.
Each one must be triaged and migrated to the object type that matches its
intrinsic behavior:

- runtime or execution behavior becomes RuntimeService
- durable data or persistence behavior becomes DataStoreService
- network, traffic-control, ingress, WAF, firewall, load-balancing, proxy, DNS,
  WAN, routing, switching, or segmentation behavior becomes NetworkService
- operating substrate behavior becomes Host

ProductComponents that previously used an EdgeGatewayService as `runsOn` must
be updated to reference the RuntimeService or Host they run on.
Network paths, WAFs, load balancers, gateways, and perimeter obligations should
be expressed through SDP placement, relationships, RequirementGroups,
DecisionRecords, and ReferenceArchitecture conformance.

### Migration Notes

1. Inventory `catalog/edge-gateway-services/` and all YAML with
   `type: edge_gateway_service`.
2. For each object, choose the target type from intrinsic behavior, not from
   placement words such as edge, perimeter, public, partner, or tenant.
3. Move each object into the correct catalog folder and update `type`. Preserve
   `uid` when the same architecture object is being reclassified rather than
   replaced.
4. For traffic-control objects migrated to `network_service`, fill in
   `networkFunction`, `networkTopology`, and `protocols`, then keep or add
   service evidence such as `host`, `primaryTechnologyComponent`,
   `internalComponents`, `architectureNotes`, and `decisionRecords` as
   applicable.
5. Update ReferenceArchitecture constraints, SDP service-group entries,
   relationships, RequirementGroup `appliesTo` scopes, templates, and generated
   browser output to use the migrated object types.
6. Run `python3 framework/tools/generate_ai_index.py`,
   `python3 framework/tools/generate_browser.py --workspace . --output docs/index.html`,
   and `python3 framework/tools/validate.py --workspace .` after migration.

## 0.32.3 - 2026-05-30

Clarifies DRAFT command integration across Codex, generic AI tools, and
IDE-specific bootstrap files, and resolves the validation command naming
mismatch without changing the architecture object contract.

### Added

- **`/validate-catalog` compatibility alias**: added
  `framework/commands/validate-catalog.md` so older workspace references and
  symlinks resolve to the canonical `/draft-validate` workflow instead of
  pointing at a missing command file.

### Changed

- **Canonical validation command guidance**: updated workspace templates,
  Cursor/Windsurf integrations, setup-mode docs, and AI configuration docs to
  advertise `/draft-validate` as the canonical validation command.
- **Codex and generic AI wording**: clarified that `AGENTS.md` provides
  command-phrase routing for tools such as OpenAI Codex and does not create
  native slash-command menu entries or autocomplete by itself.
- **Workspace command inventories**: aligned bootstrap command tables with the
  command files under `framework/commands/`, including help, triage,
  framework-update, and review commands.

### Fixed

- **Broken validation command references**: removed live bootstrap and
  integration references that routed `/validate-catalog` to a missing command
  file, while preserving the old command as an explicit alias.

### Compatibility Impact

No schema, RequirementGroup, capability, domain, validation-contract, or catalog
object change. Existing workspaces that still invoke `/validate-catalog`
continue to work through the compatibility alias; newly generated workspaces
advertise `/draft-validate`.

### Migration Notes

No action is required for existing workspaces. Workspace owners may refresh
generated bootstrap or IDE integration files if they want user-facing command
tables and guidance to show `/draft-validate` as the canonical name.

## 0.32.2 - 2026-05-30

Documents the branch-protection policy now enforced on `main`. This is a
release-governance/documentation change with no schema, code, or catalog
impact.

### Added

- **`Branch Protection On main` section in `RELEASE.md`**: records the enforced rules (pull request required, `validate` status check required, branches must be up to date before merge, enforced for admins, force-push and deletion disabled), the command to inspect the policy, and an explicit caveat that the required-check context is named `validate` and must be kept in sync if the workflow job is renamed.

### Changed

- **Corrected the `Publish` section of `RELEASE.md`**: it previously stated that direct commits to `main` are allowed before `1.0.0`. All changes now reach `main` through a pull request that passes the release gate, pre-1.0 included. This closes the policy gap that allowed a schema contract change to be pushed directly to `main` without a changelog entry (see `0.32.1`).

### Fixed

- None.

### Compatibility Impact

No framework behavior, schema, or catalog change. Affects contributor workflow only: changes to `main` must now go through a pull request whose `validate` check passes.

### Migration Notes

No action required for existing workspaces. Contributors should branch and open a pull request rather than pushing to `main`; the merge is blocked until the `validate` check passes and the branch is up to date.

## 0.32.1 - 2026-05-30

Release-note correction. Commit `de67d90` was pushed directly to `main`
(outside the normal branch + pull request flow) and relaxed two schema
required-field lists without its own changelog entry or version bump. That
change then shipped to users as part of `0.32.0` because the version bump in
the PascalCase release sat on top of it. This entry backfills the missing
release note so the contract change is traceable. No code or schema changes
ship in `0.32.1` itself.

### Added

- None.

### Changed

- **Documented the `lifecycleStatus` relaxation that shipped in `0.32.0`**: `lifecycleStatus` was moved from `requiredFields` to `optionalFields` in the `product_component` and `data_component` schemas to reduce first-party intake friction, implementing the High-severity review finding "Redundant lifecycleStatus on First-Party Code." This was live on `main` from commit `de67d90` but was absent from the `0.32.0` changelog; it is recorded here.

### Fixed

- **Closed the release-record gap** created when a schema contract change reached `main` without a changelog entry or independent version bump.

### Compatibility Impact

No new behavior in `0.32.1`. The underlying `0.32.0` schema relaxation is backward compatible: objects that already set `lifecycleStatus` on a `product_component` or `data_component` continue to validate unchanged, and new objects may now omit the field. No object that previously validated becomes invalid.

### Migration Notes

No action required. Workspaces that want to keep `lifecycleStatus` mandatory for first-party components can continue to set it on every object; the framework no longer forces it. Tooling or documentation that described `lifecycleStatus` as required for `product_component`/`data_component` should be updated to reflect that it is now optional.

## 0.32.0 - 2026-05-30

Standardizes how object types are *named in text* on a single PascalCase
convention across the entire framework — documentation, schema `aiHint`s,
requirement-group `name:` fields, validation messages, command files, the
browser template, workspace templates, and the DRAFT application strings. Before
this release the surface was inconsistent: the same row of `object-types.md`
could read `RuntimeService` and `Edge/Gateway Service` side by side, and stale
`Data-at-Rest Service` terminology survived in several files. This release also
folds the legacy `Data-at-Rest Service` label into `DataStoreService`.

### Added

- **`Object Type Names` section in `naming-conventions.md`**: documents the PascalCase display convention (`TechnologyComponent`, `RuntimeService`, `DataStoreService`, `EdgeGatewayService`, `NetworkService`, `ProductComponent`, `DataComponent`, `ReferenceArchitecture`, `SoftwareDeploymentPattern`, `RequirementGroup`, `DecisionRecord`, `DraftingSession`, `ObjectPatch`, and single-word `Host`/`Capability`/`Domain`), and states explicitly that machine identifiers (snake_case `type` values), schema filenames, and catalog folder names are unchanged.

### Changed

- **Uniform PascalCase object-type labels**: replaced spaced/slashed display forms (`Runtime Service`, `Data Store Service`, `Edge/Gateway Service`, `Technology Component`, `Network Service`, `Product Component`, `Data Component`, `Requirement Group`, `Decision Record`, `Drafting Session`, `Software Deployment Pattern`, `Reference Architecture`, `Object Patch`) with their PascalCase forms wherever they name an object type. This includes requirement-group `name:` fields (e.g. `Data Store Service Requirement Group` → `DataStoreService RequirementGroup`), which is why this is a `0.MINOR.0` contract release.
- **`Data-at-Rest Service` → `DataStoreService`**: removed the last remaining instances of the superseded label from live docs, templates, the application, and `llms.txt`.
- **Space/slash/hyphen-insensitive question routing**: `draft_table/draftsman.py` now recognizes both `Technology Component` and `TechnologyComponent` (and the other types) when answering local definition questions, so the new canonical spelling routes correctly.

### Fixed

- **Mixed casing inside single passages**: removed cases where one sentence or table row used both spaced and PascalCase forms of the same type name.

### Compatibility Impact

Display-name change to the contract surface: seven built-in requirement groups have a new `name:` value (the spaced "… Requirement Group" forms become "… RequirementGroup", and "Data Store Service Requirement Group" becomes "DataStoreService RequirementGroup"). The opaque `uid` of every requirement group is unchanged, and `activeRequirementGroups` in `.draft/workspace.yaml` references groups by `uid`, so activation is unaffected. No schema `type` value, schema filename, or catalog folder name changed, so existing catalog YAML continues to validate without edits.

### Migration Notes

No catalog edits are required. Workspaces that reference a built-in requirement group by display name in prose, dashboards, or external docs should update those references to the PascalCase form; workspaces that reference groups by `uid` (the supported mechanism) need no change. If a company workspace maintained its own copy of the old "Data-at-Rest Service" wording in local docs, update it to "DataStoreService" to match the refreshed framework vocabulary.

## 0.31.2 - 2026-05-30

Realigns the workspace template scaffold (`templates/workspace/`) with the
canonical catalog convention used by `examples/`, CODEOWNERS, the browser, and
`how-to-add-objects.md`. The scaffold had drifted: it used a legacy
"standards"/delivery-model folder taxonomy and still seeded directories for the
retired Control Enforcement Profile model.

### Added

- **Canonical catalog folders in the scaffold**: added `catalog/hosts/`, `catalog/runtime-services/`, `catalog/edge-gateway-services/`, `catalog/relationships/`, and `catalog/systems/` so a new workspace scaffolds the behavior-based folders the Draftsman, CODEOWNERS, and the browser actually use. (`catalog/network-services/` was added in 0.30.2.)

### Changed

- **Removed legacy/mismatched scaffold directories**: deleted `catalog/host-standards/`, `catalog/service-standards/`, `catalog/database-standards/`, `catalog/objects/`, `catalog/saas-services/`, and `catalog/appliance-components/`. The first three used the old "standards" naming (objects authored there were not routed by CODEOWNERS or rendered by the browser); `saas-services`/`appliance-components` scaffolded delivery models as if they were object types, contradicting `object-types.md`. The scaffold catalog tree now matches `examples/` (plus `network-services/`).
- **Removed retired-model configuration directories**: deleted `configurations/compliance-controls/`, `configurations/control-enforcement-profiles/`, `configurations/definition-checklists/`, `configurations/automation-targets/`, and `configurations/object-types/`. These have no live framework references and belong to the model that Requirement Groups replaced.

### Fixed

- None.

### Compatibility Impact

No breaking changes. Affects only the new-workspace scaffold under `templates/workspace/`; no schema, requirement group, or existing catalog content changed. The capability-ownership object-patch templates are retained.

### Migration Notes

No action required for existing workspaces. Workspaces scaffolded from an earlier template can delete the empty legacy directories (`catalog/*-standards/`, `catalog/saas-services/`, `catalog/appliance-components/`, `catalog/objects/`, and the retired `configurations/` dirs) and author against the behavior-based catalog folders; objects validate regardless of folder name, but only the canonical folders are routed by CODEOWNERS and rendered by the browser.

## 0.31.1 - 2026-05-30

Resolves a contradiction in the AI instruction surface about whether the
Draftsman should show the user a running backlog of remaining work.

### Added

- None.

### Changed

- **Reconciled conversation-cadence guidance**: `draft-session.md` and `company-onboarding.md` told the Draftsman to "keep a visible list of what is next / what is left / revisit-later items," while `setup-mode.md` and `draftsman.md` told it to avoid displaying backlogs and checklists. Reworded the two former files to the intended behavior — *record* open questions, assumptions, and next steps in the Drafting Session for resumability, but keep the live conversation focused on the current step without displaying a running backlog. The session-resumption summary in `draftsman.md` (a brief recap on resume) is unchanged.

### Fixed

- None.

### Compatibility Impact

No breaking changes. Documentation and command-guidance wording only; no schema, requirement group, or catalog content changed.

### Migration Notes

No action required. Workspaces that vendored an earlier framework copy will pick up the reconciled cadence guidance on their next framework refresh.

## 0.31.0 - 2026-05-30

Converges the human-readable name of the `data_store_service` object on **Data
Store Service**, matching its machine type (`data_store_service`) and catalog
folder (`catalog/data-store-services/`). The framework previously used the
deprecated "Data-at-Rest Service" term across ~14 docs and the delivery
requirement-group descriptions. Released as a minor because requirement-group
definitions (the contract surface) changed, though only their display names and
descriptions were edited.

### Added

- None.

### Changed

- **Standardized the data store object display name on "Data Store Service"**: replaced all "Data-at-Rest Service" occurrences across framework docs, the SaaS/PaaS/Appliance/Runtime/Data Store delivery requirement-group descriptions, and the browser user manual. Renamed the lone PascalCase outlier "DataStoreService Requirement Group" to "Data Store Service Requirement Group" to match the spaced RG-name convention. (The frozen `migrations/0.10.0/` script retains the old term intentionally.)

### Fixed

- **Broken schema link in `yaml-schema-reference.md`**: the data store row linked `data-at-rest-service.schema.yaml`, which does not exist; repointed to `data-store-service.schema.yaml`.
- **Wrong catalog folder in docs**: `how-to-add-objects.md` and `yaml-schema-reference.md` told authors to use `catalog/data-at-rest-services/`, but CODEOWNERS, the browser, and the scaffold all use `catalog/data-store-services/`. Authoring to the documented folder meant no review routing and no browser rendering. Corrected to `catalog/data-store-services/`.

### Compatibility Impact

No breaking changes. Documentation and display-name alignment only; no schema type, UID, requirement ID, or catalog object content changed. The machine identifiers (`data_store_service`, `data-store-service.schema.yaml`, `data-store-services/`) are unchanged.

### Migration Notes

No action required. The compact PascalCase object-type label "DataStoreService" (used alongside "RuntimeService", "EdgeGatewayService", etc.) was intentionally left as-is; the broader PascalCase-vs-spaced object-type label convention is tracked as a separate decision.

## 0.30.2 - 2026-05-30

Completes the 0.30.0 capability-domain restructure and network-infrastructure
work: the configuration, schema, and validator layers shipped in 0.30.0, but the
documentation and the catalog-folder plumbing for the new `network_service` type
were not updated to match.

### Added

- **`catalog/network-services/` is now a first-class catalog folder**: added to the workspace catalog scaffold (`templates/workspace/catalog/network-services/`), routed to technology-admins in `CODEOWNERS.tmpl`, and registered in `generate_browser.py` `CATALOG_FOLDERS` so `network_service` objects are scaffolded, review-routed, and rendered in the browser.

### Changed

- **Setup-mode and Draftsman docs now describe the 0.30.0 domain structure**: `setup-mode.md` Step 5 listed 19 capabilities under the pre-0.30 grouping (with the dropped General Purpose Compute, the renamed Backup Strategy, and a combined "Security & Identity"). Updated to the actual seven domains (Compute & Runtime, Identity & Access Management, Security, Data, Observability & Monitoring, Network, Testing & Quality) and 22 capabilities. Updated the matching "19 framework capabilities" count in `draftsman.md`.

### Fixed

- None.

### Compatibility Impact

No breaking changes. Documentation and workspace-template/tooling alignment only; no schema, requirement group, or catalog object content changed. The four network capabilities remain intentional `incomplete` stubs (advisory validation warnings) pending the requirement-mapping decision tracked in issue #36.

### Migration Notes

No action required for existing catalogs. Workspaces created before this release that author `network_service` objects can add a `catalog/network-services/` folder and a matching `CODEOWNERS` line to pick up review routing; existing objects validate regardless of folder name.

## 0.30.1 - 2026-05-30

### Added

- None.

### Changed

- None.

### Fixed

- **Vendored template paths corrected in docs**: Setup mode, the Draftsman role doc, and the workspaces doc referenced workspace templates at `.draft/framework/templates/...`, but the framework update flow vendors them to `.draft/templates/`. Updated the `CODEOWNERS.tmpl` copy command (`setup-mode.md`), the object-patch template path (`draftsman.md`), and the generic template reference (`workspaces.md`) so they point at the location the vendoring command actually produces. Without this fix, the setup-mode `cp` command for CODEOWNERS failed and the object-patch template lookup resolved to a nonexistent path in vendored company workspaces.

### Compatibility Impact

No breaking changes. Documentation-only fix; no schema, requirement group, or catalog content changed.

### Migration Notes

No action required for existing catalogs. Draft Admins who copied the previous `.draft/framework/templates/...` paths into local setup scripts or runbooks should update them to `.draft/templates/...` to match the location the framework update flow produces.

## 0.30.0 - 2026-05-30

### Added

- **Four new capability domains**: Security, Identity, Data, Network. Each domain is owned by the team that decides implementation selections.
- **Four new network capabilities**: Network Connectivity, Network Segmentation, Traffic Management, WAN Connectivity.
- **NetworkService object type** and schema: Represents non-perimeter network fabric infrastructure (switches, routers, SDN controllers, WAN appliances). Includes Network Service requirement group covering network function, topology definition, and protocol governance.

### Changed

- **Capability domain restructuring**: 
  - Move Authentication, Access Control Model to Identity domain
  - Move Security Monitoring, Secrets Management to Security domain
  - Move Encryption at Rest, Data Resilience to Data domain
  - Remove General Purpose Compute — no meaningful distinction from Compute Platform
  - Update all capability objects with new domain references
  - Fix domain `capabilities:` lists to match actual capability assignments

- **Appliance Delivery Requirement Group simplified**: Remove `network-placement` (placement belongs in SDPs/RAs) and `patching-ownership` (duplicate of `patch-update-model`).

- **Validator and object-type documentation** updated to recognize `network_service`.

### Fixed

- Removed example `patch-compute-implementations.yaml` which targeted deleted General Purpose Compute capability.
- Updated `requirement-group-host-compute-profile.yaml` to reference Compute Platform instead of deleted General Purpose Compute.

### Compatibility Impact

Breaking change: General Purpose Compute capability removed. Any workspace objects or requirement groups referencing it (UID `01KQQ4Q026-9K8G`) must be updated to use Compute Platform (`01KQQ4Q026-1HZP`).

### Migration Notes

1. If your workspace references General Purpose Compute capability, update to Compute Platform.
2. If you have custom capability domains, align with the new domain model: each domain is owned by the team that decides the HOW for implementations (Compute Platform owner = infrastructure team, Encryption at Rest owner = data team, etc.).

## 0.29.3 - 2026-05-29

### Added

- **`/issue-triage` slash command** (`framework/commands/issue-triage.md`): Fetches open GitHub issues, presents them as a numbered selection table with title, labels, and age, and works through whichever the user picks. Supports optional filters (`bugs`, `features`, `docs`, `all`). For each selected issue: summarises the issue type, offers to work on it, skip, or close as won't fix. Creates a branch, implements the fix, and opens a PR with the issue reference. Works in any repository with a GitHub remote and an authenticated `gh` CLI.

### Changed

- None.

### Fixed

- None.

### Compatibility Impact

No breaking changes.

### Migration Notes

None.

## 0.29.2 - 2026-05-29

### Added

- **`/framework-review` slash command** (`framework/commands/framework-review.md`): On-demand expert consultant review command for framework maintainers. Establishes an enterprise architect persona (TOGAF, COBIT, Zachman, data architecture), reads design-principles.md and roles-and-layers.md for DRAFT context, supports configurable scope (full, schemas, ai-instructions, requirement-groups, docs, onboarding), presents all findings as a numbered table before exploring any, and works through each finding interactively with implement/discuss/defer/drop disposition. Checks whether the framework has advanced 2+ minor versions since the last logged review and prompts the maintainer if so.

- **`framework/reviews/review-log.yaml`**: Structured log of framework review sessions. Each entry records date, framework version, scope, and per-finding outcomes using controlled vocabulary (`implemented`, `discussed`, `dropped`, `deferred`). Committed to git so review history is visible alongside code changes. Seeded with the first review session (0.28.5 → 0.29.1, 10 findings, full scope).

- **`/framework-review` symlink** added to `.claude/commands/` in this repo.

### Changed

- None.

### Fixed

- None.

### Compatibility Impact

No breaking changes.

### Migration Notes

None.

## 0.29.1 - 2026-05-29

### Added

- None.

### Changed

- None.

### Fixed

- **SaaS Delivery requirement group field keys now match `vendorGovernance` schema structure**: All five vendor governance fields (`dataLeavesInfrastructure`, `dataResidencyCommitment`, `dpaNotes`, `vendorSLA`, `incidentNotificationProcess`) were referenced as flat top-level keys in the requirement group but are nested under `vendorGovernance` in the schema. Updated all keys to use dotted paths (`vendorGovernance.fieldName`) that `resolve_field_path` already supports. Closes #35.

### Compatibility Impact

No breaking changes. SaaS service objects that previously placed fields at the top level to satisfy the requirement group (the only working workaround) will now need to move those fields under `vendorGovernance` to satisfy both the requirement group and the schema structure validator.

### Migration Notes

1. For any SaaS service objects using the workaround of top-level `dataLeavesInfrastructure`, `dataResidencyCommitment`, `dpaNotes`, `vendorSLA`, or `incidentNotificationProcess` fields: move them under a `vendorGovernance:` sub-object.

## 0.29.0 - 2026-05-29

### Added

- **Roles and Layers document** (`framework/docs/roles-and-layers.md`): New document explaining the three roles (Draft Admins, Shared Services, Engineering), the three catalog layers (Governance, Infrastructure, Product), and the reuse scale model. Clarifies that 50 services on a shared platform produces ~60 objects, not hundreds, because infrastructure objects are authored once and referenced by many.

- **Design Principles document** (`framework/docs/design-principles.md`): Seven principles explaining the reasoning behind DRAFT's opinions — reuse over invention, stubs as progress, binary governance, automation-first catalog, compliance as authoring, AI owns the YAML, and uncertainty as first-class. Linked from `overview.md`.

- **Capability domain ownership templates**: Four object-patch template files added to `templates/workspace/configurations/object-patches/` covering all 19 framework capabilities grouped by domain (Compute & Runtime, Security & Identity, Observability, Data & Engineering Quality). Each template contains stub patches targeting framework capability UIDs with `owner` and `implementations` placeholders. The Draftsman generates individual patch files from these during setup mode step 5.

- **Session routing rule in `draftsman.md`**: The Draftsman now determines the correct mode from workspace state (`.draft/workspace.yaml` presence and catalog content) rather than relying solely on user phrasing.

- **Reuse Model section in `draftsman.md`**: Explicit documentation that infrastructure objects are authored once and referenced by many engineering objects. "Creating duplicate infrastructure objects is always wrong" is now a stated rule.

### Changed

- **`externalInteraction` mechanism renamed to `relationship`** across all requirement groups, schemas, and the validator. Any workspace `requirementImplementations` entry using `mechanism: externalInteraction` must be updated to `mechanism: relationship`. The underlying validation logic is unchanged — the mechanism resolves against outbound relationship objects where source matches the object UID and the relationship carries the required capability.

- **`serviceGroup.connections` removed from the SDP schema**: The inline `serviceConnections` field and the `serviceConnection` sub-schema have been removed. The validator now fails (not warns) when a service group contains a `connections` list. Relationship objects in `catalog/relationships/` are the only supported connection model. The browser's `build_sdp_connections` function has been updated to source topology edges from relationship objects only.

- **`setup-mode.md` step 5 reframed as domain standard ownership**: The step now explicitly surfaces the 19 framework capabilities as domain standards requiring designated owners, grouped by domain. Unassigned owners are recorded as `TBD` so gaps are visible immediately.

- **`setup-mode.md` audience declaration added**: A prominent callout at the top clarifies that setup mode is for Draft Admins only. Engineering and Shared Services representatives connect to an already-configured workspace and start a regular Draftsman session.

- **`AGENTS.md` reduced from 187 to 70 lines**: Removed seven sections duplicated in `draftsman.md` — Source Of Truth Order, AI Agent Contract, Compliance Claims, Overlapping Requirements, Capability Lookup, SDP Walkdown, and the condensed Draftsman behavior summary. AGENTS.md now contains only what is needed before `draftsman.md` is read: bootstrap sequence, activation phrases, repository-mode structural facts, and editing rules.

- **Object model diagram updated**: The SDP box display fields now show `deploymentTargets · relationships` instead of `connections · deploymentTargets`.

### Fixed

- **Stale `catalogStatus` vocabulary in documentation**: Three documents (`capabilities.md`, `how-to-add-objects.md`, `sdp-completion-interview.md`) referenced an old status vocabulary (`stub/draft/approved`) instead of the current valid values (`stub/incomplete/complete`). All corrected.

- **`sdp-completion-interview.md` invalid `lifecycleStatus: draft` reference removed**: The incomplete conditions list referenced `lifecycleStatus: draft`, which is not a valid value. Replaced with plain-language description of unresolved placeholder deployment targets.

### Compatibility Impact

Two breaking changes:

1. **`mechanism: externalInteraction` in `requirementImplementations`** — any workspace object using this mechanism value will now fail schema validation. Rename to `mechanism: relationship`.

2. **`serviceGroup.connections`** — any SDP with inline `connections` entries will now fail validation (previously a warning). Migrate each entry to a relationship object file in `catalog/relationships/`.

### Migration Notes

1. **Rename `externalInteraction` to `relationship`** in any `requirementImplementations` entries across your workspace catalog. Search for `mechanism: externalInteraction` and replace with `mechanism: relationship`.

2. **Migrate inline `serviceGroup.connections` to relationship objects**: For each connection entry, create a file in `catalog/relationships/` with `type: relationship`, `source` set to the `from` UID, `target` set to the `to` UID, `technology` set to the protocol, and `label: calls`. Then remove the `connections` list from the service group. See the migration guide in `framework/docs/software-deployment-patterns.md`.

## 0.28.5 - 2026-05-28

### Added

- None.

### Changed

- **`externalInteractions` field fully removed**: The deprecated `externalInteractions` field (plural) is removed from all service, host, and SDP schemas, all framework configurations, all example catalog objects, all documentation, and the `migrate_interactions.py` tool (deleted). The `externalInteraction` mechanism name (singular) is retained in requirement groups and the validator — it now resolves against outbound `relationship` objects where the relationship carries the required capability. Closes #34.

- **`architectureNotes.externalInteractionRationales` renamed to `relationshipRationales`**: The machine-readable dependency rationale key inside `architectureNotes` has been renamed to match the relationship object model. All 22 affected example catalog objects updated.

- **Detail view now shows relationship objects**: The browser detail view for services and hosts renders outbound and inbound relationship data instead of the removed `externalInteractions` field.

### Fixed

- **`externalInteraction` mechanism satisfaction now resolves against relationship objects**: `implementation_resolves` in `validate.py` previously only checked the deprecated `externalInteractions` field, making it impossible to complete the migration without losing requirement coverage. It now checks relationship objects where `source == obj.uid` and the relationship carries the required capability. Closes #34.

### Compatibility Impact

Breaking change for workspaces that have not yet migrated `externalInteractions` to relationship objects: removing the field from schemas means those objects will fail schema validation. Run `migrate_interactions.py` before upgrading, or migrate manually. Workspaces already on relationship objects are unaffected.

### Migration Notes

1. **Migrate `externalInteractions` to relationship objects before upgrading**: Use the last available version of `migrate_interactions.py` (removed in this release) to generate relationship stubs, or create them manually. Each entry needs a `relationship` YAML file with `source`, `target` or `externalTarget`, `label`, `technology`, and `capabilities` (list of capability UIDs the relationship satisfies).

2. **Rename `architectureNotes.externalInteractionRationales` to `relationshipRationales`** in any workspace objects that use this key.

## 0.28.4 - 2026-05-28

### Added

- None.

### Changed

- **`owner` is now optional on `requirement_group`**: Framework-provided requirement groups are not owned by any company team; the field was moved from `requiredFields` to `optionalFields`. Company-authored requirement groups may still declare `owner` and are encouraged to do so for accountability. No existing valid objects are affected.

- **`capability` `aiHint` strengthened**: The schema hint now states both what a capability IS (a technology architecture outcome such as Data Persistence, Container Orchestration, CI/CD Pipeline) and what it IS NOT (a product name, business process, organizational unit, or business domain label). The distinction is called out explicitly for bulk-generation and migration contexts where product labels are most likely to be mistaken for capabilities. Closes #32.

- **`draftsman.md` capability migration guard added**: A paragraph immediately after the existing "do not add or approve a Capability" prohibition now spells out the technology-outcome vs. product-label distinction with migration-specific language. Closes #32.

### Fixed

- **Framework configuration files no longer carry placeholder `owner.team`**: All 21 framework-owned requirement group and reference architecture files had `owner.team: cloud-architecture`, a placeholder value that produced unresolvable vocabulary warnings in company workspaces with a governed teams list. The `owner` block has been removed from all affected files. The vocabulary warning was correct; the data was wrong. Closes #33.

- **SDP topology curvy lines restored**: `build_sdp_connections` now sources connections from `relationship` objects (introduced in 0.26.0) in addition to the deprecated `serviceGroups[].connections[]` field. SDPs that migrated to standalone relationship objects had empty `sdpConnections`, causing the SVG connection overlay to render nothing. Both sources are merged with deduplication; legacy connections are preserved for backward compatibility.

- **C4 diagram structure**: `generate_c4.py` now groups containers into `Boundary` blocks (Mermaid) and `group` blocks (Structurizr DSL) derived from the SDP service group names. Previously all containers were emitted in a flat list with no visual structure. Falls back to flat output when no SDP grouping can be found.

### Compatibility Impact

Schema change: `owner` moved from required to optional on `requirement_group`. No existing valid objects are affected — objects with `owner` set continue to validate normally; framework-provided objects that omit it now also validate normally. Workspaces that relied on the validator to enforce `owner` presence on requirement groups will no longer see that enforcement.

### Migration Notes

1. **No action required for existing requirement groups**: Objects with `owner` set are unaffected. The change only removes the hard requirement so framework-provided groups can omit the field.

2. **Remove placeholder `owner` blocks from framework-provided files if syncing manually**: Any workspace that vendored or forked framework configuration files should remove the `owner: {team: cloud-architecture, contact: ...}` block from framework requirement groups and reference architectures to eliminate vocabulary warnings.

## 0.28.1 - 2026-05-27

### Added

- None.

### Changed

- None.

### Fixed

- **`architectureNote` rejected as `requirementImplementations` mechanism**: `validate_requirement_implementations` now fails any implementation entry that sets `mechanism: architectureNote`. Inline notes are scratchpad, not evidence — proper mechanisms (`externalInteraction`, `technologyComponentConfiguration`, `field`, etc.) or a promoted `decision_record` are required. All 26 example catalog objects that carried `mechanism: architectureNote` implementation entries have been corrected: entries were removed (requirements remain automatically satisfied via `canBeSatisfiedBy` group scanning against `architectureNotes` keys) or replaced with valid mechanisms. The `validate_architectural_decisions` inline-notes suppression added in 0.28.0 is reverted — the warning is correct and should fire.

- **SDP `decisionRecords` reference added**: The `sdp-openstack-iaas-platform` object is `complete` and has inline `architectureNotes`; it now declares `decisionRecords: [{ref: 01KSE5V73Z-CRZV}]` to resolve the inline-notes promotion warning.

### Compatibility Impact

No schema changes. Behavioral change: `mechanism: architectureNote` in `requirementImplementations` is now a validation failure (was silently accepted in 0.28.0). Workspaces that authored implementation entries with `mechanism: architectureNote` must remove those entries or migrate to structural mechanism types.

### Migration Notes

1. **Remove `mechanism: architectureNote` from `requirementImplementations`**: Requirements that were documented with `mechanism: architectureNote` can be satisfied automatically — if the corresponding `architectureNotes` key is present on the object, the requirement group scanner resolves it via `canBeSatisfiedBy`. No manual implementation entry is needed.

2. **Promote inline decisions to `decision_record` objects** for complete objects that want to suppress the inline-notes warning without a `decisionRecords` reference.

## 0.28.0 - 2026-05-27

### Added

- **`decisionRecords` field on service, host, and product schemas**: `runtime_service`, `edge_gateway_service`, `data_store_service`, `host`, `product_component`, and `data_component` schemas now declare `decisionRecords` as an optional list field with `decisionRecordRef` collection schema. Objects of these types can now reference `decision_record` objects directly.

- **Decision records for HAProxy and Ops Console**: Two new `decision_record` objects added to the examples catalog — `dr-haproxy-lb-operational-architecture.yaml` (01KSF29JTP-DRHA) documenting HAProxy's pass-through auth, Ansible-managed secrets, and VIP failover decisions, and `dr-ops-console-secrets-injection.yaml` (01KSE5V73Z-DRSC) documenting the Ops Console's deploy-time secrets injection approach.

- **Open drafting session example**: `session-nova-compute-runtime-service.yaml` added to demonstrate an in-progress authoring session with unresolved questions about Nova scheduler election and conductor failover behavior.

- **Security compliance evidence across the examples catalog**: All 14 runtime services, 7 data-store-services, the edge gateway, the OpenStack host, and the Lambda host now carry `architectureNotes` keys that satisfy active `Security and Security Compliance Requirement Group` requirements, plus corresponding `requirementImplementations` entries.

### Changed

- **`architectureNotes` inline warning suppressed when requirement evidence is present**: `validate_architectural_decisions` no longer warns about inline `architectureNotes` when the object has `decisionRecords` references OR when any `requirementImplementations` entry uses `mechanism: architectureNote`. Objects whose notes serve as requirement satisfaction evidence are no longer prompted to promote those keys — doing so would remove the only satisfaction mechanism for those requirements. Closes #31.: `validate_architectural_decisions` no longer warns about inline `architectureNotes` on complete objects that already declare `decisionRecords` references. Objects that have promoted their narrative to decision records but retain minimal `architectureNotes` for requirement satisfaction are no longer flagged.

- **Examples workspace `requireActiveRequirementGroupDisposition` enabled**: The examples workspace now sets `requireActiveRequirementGroupDisposition: true`, requiring all objects to have explicit dispositions for every requirement in the active security compliance requirement group. The workspace validates with zero failures and zero warnings at 159 catalog objects.

### Fixed

- None.

### Compatibility Impact

No breaking changes. New `decisionRecords` field is optional on all affected schemas; existing objects require no changes.

### Migration Notes

1. **Add `decisionRecords` references** to any complete service, host, or product objects that have inline `architectureNotes` to suppress the inline-notes warning. The decision record content can be authored incrementally — the warning only fires when the object has neither inline decisions nor linked records.

2. **Add compliance `architectureNotes` keys** (e.g. `secrets_management`, `access_control_model`, `backup_strategy`) to objects that should satisfy active security compliance requirement groups. Existing camelCase `architectureNotes` keys (e.g. `secretsManagement`) are not automatically recognized by compliance requirements that use snake_case keys.

## 0.27.0 - 2026-05-27

### Added

- None.

### Changed

- **`architecturalDecisions` renamed to `architectureNotes`**: The inline scratchpad field for architectural context is renamed across all 67 files (schemas, validator, requirement groups, docs, examples, tests). The `architecturalDecision` mechanism type in requirement group `validAnswerTypes` and `canBeSatisfiedBy` entries is renamed to `architectureNote`.

### Fixed

- **Pre-existing test failures**: Added missing `Fixed` section to CHANGELOG 0.26.0 entry (required by `test_release_notes`). Fixed `test_ra_constraint_satisfied_passes_sdp` fixture objects to include vendor fields required by `conditionalRequired` when `deliveryModel` is `paas` or `appliance`.

## 0.26.0 - 2026-05-26

### Added

- **`defaultOwnerRole` schema field**: All 15 object-type schemas now declare `defaultOwnerRole` with a static mapping: `engineer` for `product_component`, `data_component`, and `software_deployment_pattern`; `technology-admin` for all service types, `host`, `technology_component`, `decision_record`, and `relationship`; `draft-admin` for `domain`, `capability`, `requirement_group`, `reference_architecture`, and `drafting_session`. Ownership is now schema-driven rather than per-object-authored.

- **`deprecatedFields` schema mechanism** (`validate.py`): Schemas may now list deprecated field names in a top-level `deprecatedFields` array. The validator emits a warning for any object that still has a value in a deprecated field. Service schemas declare `externalInteractions` as deprecated.

- **`dictSubSchemas` schema mechanism** (`validate.py`): Schemas may map dict-typed fields to named sub-schemas via a top-level `dictSubSchemas` mapping. The validator recursively validates dict field values against their sub-schema. Used for `vendorGovernance` in all three service schemas.

- **`vendorGovernance` sub-object** (runtime-service, data-store-service, edge-gateway-service schemas): Groups the vendor accountability fields `dataLeavesInfrastructure`, `dataResidencyCommitment`, `dpaNotes`, `vendorSLA`, and `incidentNotificationProcess` under a single sub-object. Applies only to objects with `deliveryModel: saas`, `paas`, or `appliance`.

- **`conditionalRequired` for vendor fields** (runtime-service, data-store-service, edge-gateway-service schemas): `vendor`, `productName`, and `productVersion` are now required when `deliveryModel` is one of `saas`, `paas`, or `appliance`.

- **`conditionalRequired` for relationship `target`** (relationship schema): `target` is now required only when `externalTarget` is not set. `externalTarget` (free-text external system name) and `flow` (outbound/inbound/bidirectional) added as optional fields.

- **`migrate_interactions.py`** (`framework/tools/`): New script that reads a workspace, finds objects with deprecated `externalInteractions` entries, and generates stub relationship YAML files. Entries with a `ref` to an existing catalog object get `target`; bare-name entries get `externalTarget`. Supports `--dry-run`.

- **`architecturalDecisions` promotion warning**: The validator now warns when a `catalogStatus: complete` object has inline `architecturalDecisions` content, recommending promotion to `decision_record` objects.

### Changed

- **`matches_conditions`** (`validate.py`): `conditionalRequired` condition values may now be lists; the condition matches when the field value is in the list. Previously only exact equality was supported.

- **`requirementGroups` field deprecated**: Removed from all object schema `optionalFields` lists. The validator now emits a warning (not a failure) when an object contains `requirementGroups`, directing authors to remove the field. Requirement groups are applied via workspace activation and `appliesTo` rules, not per-object claims.

- **`externalInteractions` and `connections` deprecated on service group objects** (`software_deployment_pattern` schema): The validator now warns when a service group still uses these fields. Use relationship objects to model topology instead.

- **Relationship validation** (`validate.py`): `validate_relationship` now validates `source` and `target` independently. Fails when neither `target` nor `externalTarget` is set; skips target catalog lookup when `externalTarget` is provided.

- **Draftsman guidance** (`framework/docs/draftsman.md`): Updated to direct authors toward relationship objects for all dependency modeling. Deprecated `externalInteractions` authoring guidance removed. Connection elicitation procedure updated to generate relationship objects instead of `serviceConnection` entries. Validator error table updated for relationship-related messages.

- **`validate_against_schema` and `validate_schema_section`** now accept an optional `warnings` list so schema-level deprecation warnings surface alongside custom validator warnings.

### Removed

- **`ownerRole` field**: Removed from `optionalFields` and `enumFields` on all object-type schemas. Use the schema-declared `defaultOwnerRole` instead.
- **`requirementGroups` field**: Removed from `optionalFields` on all object-type schemas. Objects that still have this field receive a deprecation warning.
- **Top-level vendor accountability fields** (`dataLeavesInfrastructure`, `dataResidencyCommitment`, `dpaNotes`, `vendorSLA`, `incidentNotificationProcess`): Removed from top-level `optionalFields` on service schemas. These fields now live inside the `vendorGovernance` sub-object. The validator warns when any of these are found at the top level.

### Fixed

- **`validate_requirement_implementations` workspace-group gate**: The validator previously rejected `requirementImplementations` entries pointing to a workspace-activated requirement group unless the object also declared that group in `requirementGroups`. Since `requirementGroups` is now deprecated and removed from schemas, any object with pre-existing `requirementImplementations` evidence would fail. The check now gates on the workspace's active group set rather than the deprecated per-object declaration.

### Compatibility Impact

**Pre-1.0 breaking changes** (allowed per the framework contract):

| Removed field | Schema type(s) | Replacement |
|---|---|---|
| `ownerRole` | All object types | Schema `defaultOwnerRole` (inferred, no authoring required) |
| `requirementGroups` | All standard object types | Workspace activation + schema `appliesTo` |
| `dataLeavesInfrastructure` (top-level) | runtime_service, data_store_service, edge_gateway_service | `vendorGovernance.dataLeavesInfrastructure` |
| `dataResidencyCommitment` (top-level) | runtime_service, data_store_service, edge_gateway_service | `vendorGovernance.dataResidencyCommitment` |
| `dpaNotes` (top-level) | runtime_service, data_store_service, edge_gateway_service | `vendorGovernance.dpaNotes` |
| `vendorSLA` (top-level) | runtime_service, data_store_service, edge_gateway_service | `vendorGovernance.vendorSLA` |
| `incidentNotificationProcess` (top-level) | runtime_service, data_store_service, edge_gateway_service | `vendorGovernance.incidentNotificationProcess` |
| `externalInteractions` | All service and host types (deprecated warning only) | `relationship` objects |
| `connections` | SDP serviceGroups (deprecated warning only) | `relationship` objects |

### Migration Notes

1. **Remove `ownerRole`** from any catalog objects that still declare it. The field is ignored but will generate an "unknown field" warning in future schema-aware tools.

2. **Remove `requirementGroups`** from any catalog objects that declare it. Run `validate.py` to identify files; each will show a deprecation warning.

3. **Move vendor accountability fields** into a `vendorGovernance:` sub-object on any service object with `deliveryModel: saas`, `paas`, or `appliance`.

4. **Convert `externalInteractions`** to relationship objects. Run `python3 framework/tools/migrate_interactions.py --workspace <path> --dry-run` to preview generated stubs, then without `--dry-run` to write them. Remove `externalInteractions` from each source object after verifying the relationship files.

5. **Convert SDP `serviceGroup.connections` and `serviceGroup.externalInteractions`** to relationship objects using the same migration script or manually.

## 0.25.2 - 2026-05-26

### Added

- **OpenStack relationship objects** (14 new files in `examples/catalog/relationships/`): Full inter-service dependency graph for the OpenStack IaaS example. Covers Nova→Keystone, Nova→Neutron, Nova→Cinder, Nova→RabbitMQ, Neutron→Keystone, Neutron→NeutronDB, Neutron→RabbitMQ, Cinder→Keystone, Cinder→CinderDB, Cinder→RabbitMQ, Keystone→KeystoneDB, and API LB→Nova/Neutron/Keystone. Each relationship includes protocol/technology and rationale notes.
- **Expanded OpenStack system boundary** (`examples/catalog/systems/system-openstack-compute.yaml`): Added RabbitMQ, Keystone Database, Cinder Database, and the API Load Balancer to the container list. The system now covers all 10 objects involved in the relationship graph.

### Changed

- **Browser Diagrams view tech label fix** (`framework/browser/draft-browser.js`): Resolved the `primaryTechnologyComponent` UID ref via `internalComponents[role='function']` → `objectLookup` lookup so Container nodes display the resolved technology component name (e.g. "OpenStack Nova") instead of the generic delivery model value ("self-managed").

### Fixed

No bug fixes.

### Compatibility Impact

No migration required. All changes are additive example content and a browser rendering improvement.

### Migration Notes

No migration required.

## 0.25.1 - 2026-05-26

### Added

- **Diagrams view** (`framework/browser/draft-browser.js`): New "Diagrams" sidebar entry (⌘K searchable) renders C4 L2 Container diagrams inline in the browser using Mermaid.js. One diagram per `system` object; falls back to a single diagram when no system objects are defined. Relationship edges are rendered as arrows between containers. External actors appear as `Person_Ext` / `System_Ext` nodes.
- **Mermaid.js CDN** (`framework/browser/index.template.html`): Mermaid v10 loaded via CDN with `defer`, consistent with all other browser dependencies. Rendering uses the async `mermaid.render()` API so the main thread is never blocked.

### Changed

No breaking changes. The Diagrams view is additive — browsers with no `system` or `relationship` objects show a single auto-generated diagram from all deployable containers.

### Fixed

No bug fixes.

### Compatibility Impact

No migration required.

### Migration Notes

No migration required. Pull the release and regenerate the browser to see C4 diagrams inline. Diagrams improve automatically as `system` and `relationship` objects are added to the catalog.

## 0.25.0 - 2026-05-26

### Added

- **`system` schema** (`framework/schemas/system.schema.yaml`): New object type for declaring named system boundaries. Groups deployable container objects and declares external actors (users, third-party systems). Enables C4 L1 Context scoping and Backstage System grouping. Fully additive — existing catalogs validate without modification.
- **System validation** (`framework/tools/validate.py`): `validate_system` checks that `containers[].ref` UIDs resolve to existing catalog objects and warns when a container ref points to a non-deployable type.
- **System browser support** (`framework/tools/generate_browser.py`): `systems` added to `CATALOG_FOLDERS` so system objects appear in list view and the reference graph automatically.
- **System example** (`examples/catalog/systems/system-openstack-compute.yaml`): OpenStack Compute Platform system grouping six deployable objects and three external actors.
- **Backstage exporter** (`framework/tools/generate_backstage.py`): Reads the DRAFT catalog and emits Backstage `catalog-info.yaml` entity files. Maps `domain`/`system` → `System`, service objects → `Component`, `technology_component` → `Resource`. Supports `--dry-run` and `--output`. Delivers value from existing objects with no relationship authoring required.
- **C4 exporter** (`framework/tools/generate_c4.py`): Reads DRAFT objects, `relationship` objects, and `system` objects and emits C4 L2 Container diagrams in Structurizr DSL and Mermaid C4 syntax. One diagram per `system` object; falls back to a single diagram when no system objects are defined. Gracefully handles catalogs with no relationship data. Supports `--format`, `--dry-run`, and `--output`.
- **Exporter documentation** (`framework/docs/exporters.md`): Usage guide for the Backstage and C4 exporters, object mapping tables, and a minimal template for writing custom catalog adapters.
- **AI_INDEX.md**: System schema row, exporter tool rows, and exporter docs row added.

### Changed

No breaking changes to existing object schemas or validation behavior.

### Fixed

No bug fixes.

### Compatibility Impact

No migration required. Existing catalogs validate without modification. System authoring is opt-in and additive.

### Migration Notes

No migration required. Companies can pull this release and immediately run `generate_backstage.py` against their existing catalog. C4 diagrams improve as relationship objects are authored incrementally.

## 0.24.0 - 2026-05-26

### Added

- **`relationship` schema** (`framework/schemas/relationship.schema.yaml`): New first-class object type for recording directed inter-object communication edges. Fields: `source` (UID), `target` (UID), `label` (verb phrase), optional `technology`, optional `direction` (`synchronous` / `asynchronous` / `event`). Relationship objects live in `catalog/relationships/`.
- **Relationship validation** (`framework/tools/validate.py`): `validate_relationship` function checks that `source` and `target` UIDs resolve to existing catalog objects. Dispatched for all `type: relationship` objects.
- **Browser topology view** (`framework/browser/draft-browser.js`): New "Topology" view in the sidebar nav renders a table of all relationship objects with linked source/target objects and technology/direction badges. Accessible via the ⇄ nav item and the command palette.
- **Browser topology data** (`framework/tools/generate_browser.py`): `topologyEdges` key added to the browser payload. `source` and `target` added to `REF_CONTAINER_KEYS` so the existing reference index tracks relationship endpoints. `relationships` added to `CATALOG_FOLDERS`.
- **Draftsman relationship authoring guidance** (`framework/docs/draftsman.md`): New "Relationship Authoring" section describes when and how to author relationship objects during drafting sessions.
- **Relationship example** (`examples/catalog/relationships/relationship-nova-reads-nova-database.yaml`): Nova Compute → Nova Database example demonstrating the schema.
- **AI_INDEX.md**: Relationship schema row added to the schemas table.

### Changed

No breaking changes to existing object schemas.

### Fixed

No bug fixes.

### Compatibility Impact

No migration required. Existing catalogs validate without modification. Relationship authoring is opt-in and additive.

### Migration Notes

No migration required. Companies can pull this release and begin authoring relationships incrementally via the Draftsman without touching existing catalog objects.

## 0.23.1 - 2026-05-25

### Added

- Apache 2.0 license (`LICENSE` file, copyright 2026 Dale Sackrider). Attribution is required for redistribution.

### Changed

No changes.

### Fixed

No bug fixes.

### Compatibility Impact

No breaking changes.

### Migration Notes

No migration required.

## 0.23.0 - 2026-05-25

### Added

No new features.

### Changed

- **`catalogStatus` enum renamed** (breaking): The three catalog maturity values
  have been renamed to remove ambiguity with review/approval processes and avoid
  collision with the word "draft" in the framework name.
  - `draft` → `incomplete`
  - `approved` → `complete`
  - `stub` is unchanged
  The internal validator function `approved_or_preferred_object` has been renamed
  to `complete_or_preferred_object`. All enforcement behavior is unchanged — hard
  failures fire when `catalogStatus: complete`, warnings when `incomplete` or
  `stub`.

### Fixed

No bug fixes.

### Compatibility Impact

Breaking change for all workspace YAML files that set `catalogStatus: draft` or
`catalogStatus: approved`. All framework-bundled configurations have been
migrated. Company workspaces must migrate before validating against this release.

### Migration Notes

Run the following commands from your company workspace root to migrate all YAML
files in one step:

```bash
find . -name "*.yaml" | xargs sed -i '' \
  's/catalogStatus: draft$/catalogStatus: incomplete/g; \
   s/catalogStatus: approved$/catalogStatus: complete/g'
```

Verify with `draft validate` after running.

## 0.22.0 - 2026-05-25

### Added

- **Draftsman pre-flight validation** (closes #5): Added
  `preview_proposals(session_id, proposal_ids)` method to `DraftsmanEngine`:
  copies the workspace to a temp directory, writes the selected proposals there,
  runs the validator, and returns the full result without touching the real
  workspace. Callers use this as an advisory pre-flight check before calling
  `apply_proposals`. `apply_proposals` continues to write files regardless of
  validation state — stub and incomplete objects are expected to have gaps.
- Added `resumptionContext` optional dict field to the Drafting Session schema
  (`framework/schemas/drafting-session.schema.yaml`): stores Draftsman-internal
  state (e.g. matched Reference Architecture UID, confirmed delivery models,
  scope decisions) so interrupted sessions can be resumed without re-asking
  answered questions.
- Added three new Draftsman doc sections to `framework/docs/draftsman.md`:
  - **Pre-Write Review**: protocol for showing a structured review card before
    writing YAML and holding batches that fail preview validation.
  - **Validation Repair Procedures**: table mapping common validator error
    patterns to specific repair steps.
  - **Resuming a Drafting Session**: how to reconstruct working context from a
    session YAML using `generatedObjects`, `unresolvedQuestions`, `nextSteps`,
    `assumptions`, and `resumptionContext`.
- Added tests: `test_apply_proposals_blocked_when_content_would_fail_validator`
  (pre-write gate), `test_ra_constraint_violation_fails_sdp` (RA constraint
  enforcement), `test_ra_constraint_satisfied_passes_sdp` (constraint satisfied
  passes).

### Changed

- Pre-write review is advisory, not a gate: `apply_proposals` writes files
  regardless of validation state. Stub and incomplete objects are expected to
  have gaps; enforcement happens at the `complete` catalogStatus boundary.

### Fixed

- `import shutil` and `import tempfile` added to `draft_table/draftsman.py` for
  the temp-workspace copy used by `preview_proposals`.

### Compatibility Impact

No breaking changes. `apply_proposals` behavior is unchanged — files are written
and validation runs after. `preview_proposals` is additive.

### Migration Notes

No migration required. The new `resumptionContext` field on `drafting_session`
is optional and backwards-compatible.

## 0.21.0 - 2026-05-25

### Added

- **RA constraint enforcement** (closes #21): Reference Architectures now support
  an optional `constraints` block. Each constraint declares a `when` condition
  (`anyServiceGroup.diagramTier` or `anyServiceGroup.objectType`) and a `require`
  list of object characteristics that must be present in every SDP that follows
  the RA. The validator evaluates constraints at `validate_software_deployment_pattern`
  time and reports failures for any violated constraint.
- Added `constraints` to the three baseline framework Reference Architectures:
  - **Three-Tier Web** (`01KS8N4KR2-3TWA`): `presentation-tier-requires-edge-gateway`
    and `data-tier-requires-data-store-service`.
  - **Multi-Tenant SaaS** (`01KS8N4KR3-MTSA`): `presentation-tier-requires-edge-gateway`
    and `saas-requires-utility-tier`.
  - **Serverless Event-Driven** (`01KS8N4KR4-SVED`): `ingestion-requires-edge-gateway`
    and `state-requires-data-store-service`.
- Added `constraints` to the Reference Architecture schema
  (`framework/schemas/reference-architecture.schema.yaml`) with full field
  documentation for `id`, `description`, `rationale`, `when`, `require`, `notes`.
- Added Draftsman guidance for proactive constraint checking during SDP authoring
  (`framework/docs/draftsman.md` — "RA Constraint Enforcement" section).

### Changed

- Added `01KSF29JTP-9HYA` (HAProxy OpenStack API Load Balancer, `edge_gateway_service`)
  to the OpenStack SDP's presentation tier service group, satisfying the new
  Three-Tier Web RA `presentation-tier-requires-edge-gateway` constraint.
- Resolved `session-openstack-ha-proxy-edge-service.yaml`: session closed, all
  unresolved questions answered, generated object confirmed as `01KSF29JTP-9HYA`.

## 0.20.0 - 2026-05-25

### Added

- Added `framework/configurations/requirement-groups/requirement-group-service-engineering.yaml`
  (`01KSF29JTP-SRVE`, `activation: workspace`): links the APM, Container
  Orchestration, and Serverless Runtime capabilities to the framework. Workspaces
  opt in via `activeRequirementGroups` in `.draft/workspace.yaml`.
- Added `framework/configurations/requirement-groups/requirement-group-engineering-quality.yaml`
  (`01KSF4NHSP-8HPP`, `activation: workspace`): links the Performance Testing,
  Quality Gates, Test Authoring, and Test Execution capabilities. Workspaces opt
  in to require product components to address build quality practices.
- Added `framework/configurations/requirement-groups/requirement-group-host-compute-profile.yaml`
  (`01KSF4NHSP-HCPX`, `activation: workspace`): links the General Purpose Compute
  capability. Workspaces opt in to require hosts to declare their compute type.
- Added `examples/catalog/technology-components/technology-haproxy-29.yaml`:
  HAProxy 2.9 Technology Component (`classification: software`) with
  Health/Welfare Monitoring capability.
- Added `examples/catalog/edge-gateway-services/edge-gateway-service-openstack-api-lb.yaml`:
  self-managed HAProxy load balancer for the OpenStack control plane, completing
  the edge/gateway service object type in the examples catalog.
- Completed requirement group coverage: all approved framework capabilities are
  now linked to at least one requirement group, eliminating the eight
  `capability-not-in-requirement-group` validator warnings.

### Changed

- Renamed all `data-at-rest-*.yaml` files in `examples/catalog/data-store-services/`
  to `data-store-service-*.yaml` to match the object type naming convention used
  by all other catalog file types.
- Completed `architecturalDecisions` and `externalInteractionRationales` on the
  remaining five data store services (Cinder, Glance, Keystone, Neutron, OpenStack
  Shared, Swift) and the Keystone and RabbitMQ runtime services to resolve all
  outstanding requirement group compliance gaps.

## 0.19.1 - 2026-05-24

### Added

- Added golden reference workspace built on the OpenStack IaaS Platform example
  catalog. Demonstrates how a real SDP adopts a framework RA, activates a
  requirement group, and carries requirement evidence.
- Added `examples/catalog/product-components/product-component-openstack-ops-console.yaml`:
  first-party `ProductComponent` example deploying onto the Horizon runtime service.
  Includes interfaces, network bindings, environment configuration, and
  `CC.SecurityCompliance.04.3.1.product_component` evidence.
- Added `examples/catalog/data-components/data-component-platform-audit-schema.yaml`:
  first-party `DataComponent` example with table definitions, a scheduled archive
  job, retention policy, and data classification declarations.
- Added `examples/catalog/decision-records/dr-openstack-no-waf-internal-only.yaml`:
  accepted decision record explaining why no WAF is required for the internal-only
  OpenStack deployment.
- Added `examples/catalog/sessions/session-openstack-ha-proxy-edge-service.yaml`:
  drafting session stub capturing unresolved questions about the HAProxy edge
  gateway service topology; demonstrates the session object model.
- Activated `01KQQ4Q027-T3CA` (Security and Security Compliance Requirement Group)
  in `examples/.draft/workspace.yaml`.

### Changed

- Updated `sdp-openstack-iaas-platform.yaml`: promoted `catalogStatus` to
  `approved`, added `followsReferenceArchitecture: 01KS8N4KR2-3TWA`, added
  `requirementGroups` and `requirementImplementations` for the three SDP-scoped
  security compliance requirements (10.1.1, 10.1.2, 00.2.1), and added
  `architecturalDecisions.deploymentTargets` and
  `architecturalDecisions.reference_architecture_conformance`.
- Updated `data-at-rest-nova-database.yaml`: added `access_control_model` and
  `backup.platform` to `architecturalDecisions`; added `requirementGroups` and
  `requirementImplementations` for four applicable security compliance requirements;
  added `externalInteractionRationales` for the Backup Service interaction.
- Updated `runtime-service-nova.yaml`: added `secrets_management` to
  `architecturalDecisions`; added `requirementGroups` and
  `requirementImplementations` for `CC.SecurityCompliance.04.3.1`.
- Removed obsolete empty placeholder directories: `examples/catalog/ards/`,
  `examples/catalog/sdms/`, `examples/catalog/saas-services/`.

## 0.19.0 - 2026-05-24

### Compatibility Impact

This release makes `ref` optional in Reference Architecture `deployableObjects`
entries and adds an `objectType` field. Existing RAs with `ref`-based entries
continue to validate unchanged. The change enables framework-level and community
RAs that declare expected object types without pinning to company-specific catalog
UIDs.

### Added

- Added `framework/configurations/reference-architectures/` directory. Framework
  RAs are vendored into company workspaces alongside requirement groups and
  capability definitions. Companies adopt them by referencing the RA UID in
  `followsReferenceArchitecture` on an SDP; adoption is opt-in.
- Added three baseline framework RAs: Three-Tier Web Application
  (`01KS8N4KR2-3TWA`), Multi-Tenant SaaS (`01KS8N4KR3-MTSA`), and Serverless
  Event-Driven (`01KS8N4KR4-SVED`). Each defines service group tiers, an
  `applicableDefinitionChecklist`, and `architecturalDecisions` capturing the
  key pattern rules.
- Added `objectType` optional field to the Reference Architecture schema's
  `deployableObjectEntry`. Accepts any standard deployable object type
  (`host`, `runtime_service`, `data_store_service`, `edge_gateway_service`,
  `product_component`, `data_component`). Framework and community RAs use
  `objectType` instead of `ref` so the pattern is not tied to a specific
  company catalog object.

### Changed

- Updated `generate_ai_index.py` to include
  `framework/configurations/reference-architectures/` in the framework
  configuration index so framework RAs appear in `AI_INDEX.md`.
- Updated `reference-architectures.md` to document the framework RA adoption
  model, the `objectType` field, and the community contribution path.

### Fixed

- Fixed validator error messages for service group deployable object entries to
  use `ref or objectType` as the entry label rather than always printing `ref`
  (which was `None` for type-only entries).

### Migration Notes

No migration required. Existing Reference Architectures with `ref`-based
`deployableObjects` entries continue to validate. The `ref` field remains
fully supported and preferred when a specific catalog object is the intended
target.

---

## 0.18.1 - 2026-05-24

### Compatibility Impact

No breaking changes. Vocabulary files gain UIDs; existing references by name
continue to work.

### Added

- Added `uid` field to `connection-protocols.yaml` and
  `network-zone-patterns.yaml` framework vocabulary objects so they are
  addressable by UID alongside their vocabulary name.
- Added `commands` and `integrations` to `FRAMEWORK_VENDOR_DIRS` in the
  installer so those directories are copied when vendoring the framework into
  a company workspace.
- Added `.windsurfrules` and `.cursor/rules/draftsman.mdc` to
  `WORKSPACE_TEMPLATE_FILES` so the Windsurf and Cursor IDE configs generated
  in 0.17.0 are actually deployed to new workspaces on first install.

### Changed

- Rewrote setup-mode and Draftsman AI instructions to keep onboarding
  conversational and focused. Replaced the status-dashboard pattern (current
  step / next step / remaining work / revisit-later lists) with a single-question
  cadence that explains context before asking.
- Draftsman now translates camelCase schema field names into clear, capitalized,
  user-friendly labels when presenting questions (e.g. "Deployment Targets"
  instead of `deploymentTargets`).
- Discovery Mode is now explicitly positioned as an optional accelerator in
  setup instructions, with a defined offer point after the first three basic
  workspace identity questions are answered.

### Fixed

- None.

### Migration Notes

No migration required.

---

## 0.18.0 - 2026-05-21

### Compatibility Impact

This release adds `ownerRole` as an optional enum field to eight catalog object
schemas. Existing objects without `ownerRole` continue to validate. New objects
created by the Draftsman will include `ownerRole` automatically. No migration
is required to unblock validation; migration is recommended to enable accurate
CODEOWNERS routing.

### Added

- Added `ownerRole` optional enum field (`engineer | technology-admin |
  draft-admin`) to `product_component`, `data_component`,
  `software_deployment_pattern`, `technology_component`, `runtime_service`,
  `host`, `edge_gateway_service`, and `data_store_service` schemas. The field
  makes catalog ownership machine-readable for CODEOWNERS routing and browser
  team views.
- Added `templates/workspace/CODEOWNERS.tmpl` workspace template mapping the
  three DRAFT roles to GitHub path patterns. Deployed to `.github/CODEOWNERS`
  on first framework install when the file does not already exist.
- Added Contribution Workflow section to `draftsman.md` documenting the
  branch-and-PR protocol: create a branch before writing catalog files, commit
  incrementally, open a PR at session end with `gh pr create`, and let
  CODEOWNERS route review automatically.
- Added GitHub Governance step (step 8) to `setup-mode.md` walking through
  CODEOWNERS configuration and branch protection setup using the GitHub CLI.

### Changed

- `draft-framework-update.yml.tmpl` now includes `CODEOWNERS.tmpl` in the
  workspace template copy list so new workspaces receive the file on first
  framework install.

### Fixed

- None.

### Migration Notes

Add `ownerRole` to existing catalog objects to enable accurate CODEOWNERS
routing. The correct value is determined by object type:

- `product_component`, `data_component`, `software_deployment_pattern` →
  `ownerRole: engineer`
- `runtime_service`, `host`, `technology_component`, `edge_gateway_service`,
  `data_store_service` → `ownerRole: technology-admin`
- `requirement_group`, `capability` → `ownerRole: draft-admin`

---

## 0.17.0 - 2026-05-21

### Compatibility Impact

This release renames the `decision_record` field `linkedSoftwareDeployment` to
`linkedObject`. Existing YAML files that use `linkedSoftwareDeployment` will
continue to pass validation (the old field is not flagged as an error), but the
browser cross-reference index will not follow the old field name. Migrate by
renaming the field to `linkedObject` in each affected decision record.

### Added

- Added `generate-browser.yml.tmpl` workflow template. Workspaces that apply
  a framework update will now receive a ready-made GitHub Actions workflow that
  regenerates `docs/index.html`, `docs/assets/`, and `docs/user-manual.html`
  on every push to `main` that touches a YAML file, browser asset, or
  framework tool. The workflow commits with `[skip ci]` to avoid feedback loops.
- Added `paths.catalogFolders` workspace configuration. Set this list in
  `.draft/workspace.yaml` under a `paths:` key to declare which subdirectory
  names inside `catalog/` the browser generator and cross-reference index should
  scan. When unset the framework's default folder list is used. This enables
  team-namespaced catalog structures such as `catalog/engineering/[team]/` and
  `catalog/infrastructure/` without any code changes.

### Changed

- Renamed `decision_record` optional field `linkedSoftwareDeployment` →
  `linkedObject`. The new field accepts the UID of any catalog object type,
  not just software deployment patterns. This allows a decision record to link
  directly to a `data_store_service`, `runtime_service`, `host`, or any other
  catalog object that is the subject of the recorded decision or risk.
- Updated `generate_browser.py` REF_CONTAINER_KEYS and rendering to use
  `linkedObject` in place of `linkedSoftwareDeployment`.

### Fixed

- `draft_table/catalog.py` REF_CONTAINER_KEYS updated to match the schema
  rename from `linkedSoftwareDeployment` to `linkedObject`.

### Migration Notes

Rename `linkedSoftwareDeployment` to `linkedObject` in every
`decision_record` YAML file. The value (a UID string) is unchanged.

## 0.16.3 - 2026-05-21

### Compatibility Impact

No migration required. This patch adds command discovery documentation; it does
not change schemas, validation behavior, or catalog object formats.

### Added

- Added Commands section to `README.md.tmpl` listing `/draftsman`,
  `/draft-session`, and `/validate-catalog` with human-readable descriptions
  and a fallback note for tools without slash command support.
- Added Available Commands section to `AGENTS.md.tmpl` so any AI reading
  the bootstrap file can surface the command table when users ask what they
  can do.

### Changed

- None.

### Fixed

- None.

### Migration Notes

- Existing workspaces: add a Commands section to `README.md` and an Available
  Commands section to `AGENTS.md` manually, following the new template content.

## 0.16.2 - 2026-05-21

### Compatibility Impact

No migration required. This patch adds multi-AI IDE integration support; it
does not change schemas, validation behavior, or catalog object formats.

### Added

- Added `framework/integrations/` directory with ready-to-use IDE integration
  files for Cursor (`cursor/draftsman.mdc`) and Windsurf (`windsurf/draftsman.md`).
- Added `framework/integrations/README.md` documenting the AI-agnostic model
  and how to add support for new IDEs.
- Added `.cursor/rules/draftsman.mdc.tmpl` workspace template for Cursor.
- Added `.windsurfrules.tmpl` workspace template for Windsurf.
- Updated workspace templates (`AGENTS.md`, `GEMINI.md`,
  `copilot-instructions.md`) to include command invocation guidance so any AI
  tool reading these files knows about `/draftsman`, `/draft-session`, and
  `/validate-catalog`.

### Changed

- Expanded setup-mode step 7 (IDE Integration) from Claude Code-only to a
  multi-IDE wizard covering Claude Code, Cursor, Windsurf, Copilot, Gemini
  CLI, and OpenAI Codex.
- Reframed `draftsman-ai-configuration.md` Slash Commands section as
  AI-Agnostic Design + Workflow Commands + IDE Integration to reflect that
  the framework is tool-neutral.

### Fixed

- None.

### Migration Notes

- Existing workspaces can continue unchanged.
- To enable commands in Cursor, copy `.draft/framework/integrations/cursor/draftsman.mdc`
  to `.cursor/rules/draftsman.mdc`.
- To enable commands in Windsurf, copy `.draft/framework/integrations/windsurf/draftsman.md`
  to `.windsurfrules` (or append if the file already exists).
- `AGENTS.md` and `GEMINI.md` in existing workspaces can be updated manually
  by adding the command invocation paragraph from the updated templates.

## 0.16.1 - 2026-05-21

### Compatibility Impact

No migration required. This patch adds AI-facing guidance and IDE slash
commands; it does not change schemas, validation behavior, or catalog object
formats.

### Added

- Added `framework/commands/` with three Claude Code slash commands:
  `/draftsman`, `/draft-session`, and `/validate-catalog`.
- Added setup-mode step 7 with linking instructions for wiring commands into
  `.claude/commands/` on macOS/Linux and Windows.
- Added Slash Commands section to `draftsman-ai-configuration.md`.

### Changed

- None.

### Fixed

- None.

### Migration Notes

- Existing workspaces can continue unchanged.
- To enable the slash commands, run the symlink step from setup-mode step 7 once
  at the workspace root after updating the vendored framework.

## 0.16.0 - 2026-05-21

### Compatibility Impact

This release retires the `product_service` object type and renames
`data_at_rest_service` to `data_store_service`. Both changes are breaking for
any catalog that uses these types. Existing `product_service` artifacts must be
deleted or converted; existing `data_at_rest_service` artifacts must have their
`type` field changed to `data_store_service` and their folder moved. Requirement
groups that reference either type must be updated to use `data_store_service` or
`software_deployment_pattern` as appropriate. No other object types are affected.

### Added

- Added `serviceGroup.substrate` optional field to the
  `software_deployment_pattern` schema. When set to the UID of a
  `runtime_service`, `host`, or `edge_gateway_service`, that runtime is rendered
  as the deployment container for the service group's `product_component` members
  in both the browser card view and the topology graph, eliminating the need to
  list the hosting runtime as a separate `deployableObjects` entry.
- Added `data_store_service` as the canonical object type for persistent data
  stores, replacing the retired `data_at_rest_service` type.
- Added new catalog scaffold directories: `catalog/data-store-services/`,
  `catalog/product-components/`, and `catalog/data-components/`.
- Added `data-store-service` requirement group covering compliance and
  availability requirements for persistent data stores.
- Added substrate compound-node rendering in the SDP topology graph (teal
  bordered compound node wrapping hosted `product_component` nodes).
- Added substrate bar UI in the SDP service-group card view showing the hosting
  runtime name and type.

### Changed

- Renamed object type `data_at_rest_service` → `data_store_service` throughout
  schemas, validation, browser generation, requirement groups, docs, and
  templates.
- Retired `product_service` object type. The SDP `serviceGroup` is now the
  canonical unit for grouping `product_component` objects within a deployment
  target and network zone. The `serviceGroup.substrate` field replaces the role
  `product_service` played as a hosting container.
- Changed `product_component.runsOn` from required to optional. When every SDP
  that references a `product_component` declares a `substrate`, `runsOn` may be
  omitted.
- Updated all built-in requirement groups to replace `product_service` scope
  references with `software_deployment_pattern` and `data_at_rest_service`
  references with `data_store_service`.
- Updated `validate.py` to recognize `data_store_service` and reject
  `data_at_rest_service` and `product_service` as unknown types.
- Updated `generate_browser.py` to scan `catalog/data-store-services/`,
  `catalog/product-components/`, and `catalog/data-components/` folders.
- Updated browser JS and CSS to render `product_component` and `data_component`
  type badges and substrate bars.
- Updated docs (`object-types.md`, `overview.md`, `user-manual.md`) to reflect
  the new object model.

### Fixed

- Fixed `validate.py` field-path resolution (`resolve_field_path()`) so the
  `field` mechanism correctly handles dotted paths (e.g. `owner.team`) and
  list-probe paths (e.g. `serviceGroups[].connections`).
- Fixed requirement-group rationale enforcement for `runtime_service` and
  `data_store_service` internal components: referencing a `product_component` or
  `data_component` no longer incorrectly demands an architectural rationale.
- Fixed `software-deployment-pattern.schema.yaml` where `deploymentTarget` was
  listed in both `requiredFields` and `optionalFields`; it is now correctly
  listed only in `requiredFields`.
- Fixed the example OpenStack IaaS SDP to include `diagramTier` on all
  deployable objects.

### Migration Notes

- **`data_at_rest_service` → `data_store_service`**: Change `type:
  data_at_rest_service` to `type: data_store_service` in every affected catalog
  file. Move files from `catalog/data-at-rest-services/` to
  `catalog/data-store-services/`. Update any requirement groups that reference
  the old type.
- **`product_service` retirement**: Delete any `product_service` catalog files.
  The deployment grouping they represented is now expressed via `serviceGroup`
  entries in the SDP that references those components. Add a `substrate` field to
  the relevant `serviceGroup` if you need to capture which runtime hosts the
  group.
- **`product_component.runsOn`**: If all SDPs referencing a component now use
  `serviceGroup.substrate`, the `runsOn` field may be removed from the component.
  It remains valid and may be kept for components that are referenced outside any
  SDP `serviceGroup.substrate` context.
- **Requirement groups**: Search for `product_service` and `data_at_rest_service`
  scope references and replace with `software_deployment_pattern` and
  `data_store_service` respectively.

## 0.13.16 - 2026-05-17

### Compatibility Impact

No migration is required. This patch fixes generated-doc output paths in
vendored workspaces; it does not change schemas, validation behavior, or
catalog object formats.

### Added

- None.

### Changed

- Changed vendored browser generation defaults so a company workspace writes
  generated docs to `docs/` instead of `.draft/docs/`.

### Fixed

- Fixed `framework/tools/generate_browser.py` so vendored workspaces no longer
  create stray generated output under `.draft/docs/`.

### Migration Notes

- Existing workspaces can continue unchanged.
- Refresh the vendored framework and regenerate browser docs to remove any
  previously created `.draft/docs/` output.

## 0.13.15 - 2026-05-17

### Compatibility Impact

No migration is required. This patch fixes vendored framework script execution;
it does not change schemas, validation behavior, or catalog object formats.

### Added

- None.

### Changed

- Changed vendored tool execution so direct script invocation resolves sibling
  helper modules without requiring a custom `PYTHONPATH`.

### Fixed

- Fixed `framework/tools/validate.py` in vendored workspaces so
  `python3 .draft/framework/tools/validate.py --workspace .` works normally.
- Fixed `framework/tools/repair_uids.py` in vendored workspaces so direct
  execution also resolves `uid_utils` correctly.

### Migration Notes

- Existing workspaces can continue unchanged.
- Refresh a vendored framework copy to pick up the script fix.

## 0.13.13 - 2026-05-15

## 0.13.14 - 2026-05-17

### Compatibility Impact

No migration is required. This patch improves framework browser navigation and
framework documentation; it does not change schemas, validation behavior, or
catalog object formats.

### Added

- Added an object-model UML diagram asset to the framework documentation and
  surfaced it from the user manual.
- Added markdown image rendering and default image styling for generated
  framework-owned documentation pages.
- Added executive browser drill-down views for teams, deployment patterns by
  business pillar, and built-in DRAFT configuration navigation.

### Changed

- Changed the Requirement Groups browser view to separate built-in DRAFT groups
  from company groups and to classify third-party compliance packs outside the
  built-in DRAFT bucket.
- Changed the Teams browser experience from a flat list into a drill-down flow
  from team to object type to object list.
- Changed the executive home view to present company configuration navigation
  under a Draftsman's Office section.

### Fixed

- Fixed stale non-clickable links in newer browser navigation views by routing
  those views through the shared object-link handler pattern.

### Migration Notes

- Existing workspaces can continue unchanged.
- Regenerate browser assets after vendoring this framework version to pick up
  the browser navigation changes.

### Compatibility Impact

No migration is required. This patch improves framework refresh ergonomics for
vendored workspaces; it does not change schemas, validation behavior, or
catalog object formats.

### Added

- Added browser shell drift warnings during normal browser generation runs so
  workspaces are told when `--refresh-shell` is available.
- Added browser shell refresh as a post-update step in the generated framework
  refresh workflow.

### Changed

- Changed the generated framework refresh workflow to vendor the
  `framework/browser` directory in addition to framework configurations, docs,
  schemas, and tools.
- Changed the generated framework refresh workflow commit step to include
  regenerated browser shell assets.

### Fixed

- Fixed generated framework refresh workflows that could update framework tools
  without also refreshing the installed browser shell assets that depend on
  them.

### Migration Notes

- Existing workspaces can continue unchanged.
- Existing workspaces can update `.github/workflows/draft-framework-update.yml`
  to pick up the new browser refresh behavior.

## 0.13.12 - 2026-05-15

### Compatibility Impact

No migration is required. This patch fixes browser requirement justification
resolution for field-backed internal components; it does not change schemas,
validation behavior, or catalog object formats.

### Added

- Added raw-detail fallback matching when browser dependency justification
  resolves field-backed internal component requirements.

### Changed

- Changed internal component requirement matching to evaluate both the browser's
  lightweight object record and the full parsed object detail payload.

### Fixed

- Fixed false `Justification Gap` messages for host operating system and
  compute platform components when those dependencies are satisfied by base
  framework field requirements.

### Migration Notes

- Existing workspaces can continue unchanged.
- Regenerate browser assets to pick up the corrected dependency justification
  rendering.

## 0.13.11 - 2026-05-15

### Compatibility Impact

No migration is required. This patch improves browser navigation and display
labels for modeled service dependencies; it does not change schemas,
validation behavior, or catalog object formats.

### Added

- Added clickable external interaction titles in the browser detail view when
  the interaction references another catalog object.

### Changed

- Changed service-facing dependency rendering so runtime service objects can be
  presented with cleaner human-readable names in adopting workspaces.

### Fixed

- Fixed detail views that showed referenced service dependencies as static text
  even when the browser could resolve them to another object page.

### Migration Notes

- Existing workspaces can continue unchanged.
- Workspaces can optionally regenerate their browser output to pick up the
  clickable external interaction behavior.

## 0.13.10 - 2026-05-15

### Compatibility Impact

No migration is required. This patch improves browser detail-view rendering for
 service and host dependencies; it does not change schemas, validation
 behavior, or catalog object formats.

### Added

- Added dependency justification rendering in the browser detail view so
  internal components and external interactions show the requirement they
  satisfy, or the architectural decision rationale when they do not satisfy a
  requirement directly.

### Changed

- Changed external interaction cards to show human-readable capability labels
  under the interaction title instead of raw capability IDs.
- Added an internal component summary list beneath the detail-view component
  diagram so dependency purpose is readable without inspecting the raw YAML.

### Fixed

- Fixed service and host detail views that previously exposed dependency UIDs
  and unstated purpose without showing the requirement or architectural
  decision that justified modeling the dependency.

### Migration Notes

- Existing workspaces can continue unchanged.
- Workspaces that already document
  `architecturalDecisions.externalInteractionRationales`,
  `internalComponentRationales`, or `dependencyRationales` will now see those
  rationales surfaced directly in the browser.

## 0.13.9 - 2026-05-15

### Compatibility Impact

No migration is required. This patch updates the vendored framework refresh
workflow template to point at the new upstream repository location; it does not
change schemas, validation behavior, or catalog object formats.

### Added

- Added the `getdraft/draftsman` repository URL to the workspace framework
  refresh workflow template.

### Changed

- Updated the generated `draft-framework-update.yml` workflow to use
  `https://github.com/getdraft/draftsman.git` as its default framework source.

### Fixed

- Fixed the stale framework refresh workflow default that still targeted the
  retired `dsackr/draft-framework` repository.

### Migration Notes

- Existing workspaces can update their checked-in
  `.github/workflows/draft-framework-update.yml` to pick up this fix before the
  next framework refresh.

## 0.13.8 - 2026-05-15

### Compatibility Impact

No migration is required. This patch updates the canonical upstream framework
repository location from `dsackr/draft-framework` to `getdraft/draftsman`; it
does not change schemas, validation behavior, or catalog object formats.

### Added

- Added the new `getdraft/draftsman` upstream repository URL to framework
  onboarding and workspace source references.

### Changed

- Updated the framework default source URL, installer defaults, workspace
  documentation, generated browser output, and test fixtures to use the new
  upstream repository location.

### Fixed

- Fixed stale upstream repository references that would otherwise point new or
  refreshed workspaces at the retired `dsackr/draft-framework` location.

### Migration Notes

- Existing workspaces should update their `framework.source` to
  `https://github.com/getdraft/draftsman.git` when they refresh framework
  metadata.

## 0.13.7 - 2026-05-15

### Compatibility Impact

No migration is required. This patch simplifies the upstream and workspace
bootstrap prompts only; it does not change schemas, validation behavior, or
catalog object formats.

### Added

- Added explicit upstream prompt language that tells the AI to help select or
  create the correct company DRAFT workspace before attempting company content
  authoring.

### Changed

- Simplified the upstream framework README prompt so it is a pure bootstrap
  handoff to `AGENTS.md` instead of duplicating Draftsman behavior.
- Updated the workspace README template to remove the assumption that the AI is
  already connected before the pasted prompt runs.

### Fixed

- Fixed the first-use framework prompt so it no longer front-loads unwanted
  repo status narration or canned session questions.

### Migration Notes

- Existing workspaces can continue unchanged.
- Existing company READMEs can refresh from the workspace template or apply the
  same wording locally.

## 0.13.6 - 2026-05-14

### Compatibility Impact

No migration is required. This patch simplifies the workspace README prompt and
removes obsolete local app commands; it does not change schemas, validation
behavior, or catalog object formats.

### Added

- Added explicit fallback prompt language telling the AI assistant to stop and
  provide actionable enablement steps when it cannot connect to the repo,
  inspect files, or write changes back.

### Changed

- Changed the workspace README prompt so it speaks directly to the AI
  assistant, tells it to read the repo bootstrap, and tells it to stop with
  actionable setup instructions when repo access is incomplete.
- Removed the obsolete `Local Commands` section from the workspace README
  template now that the `draft-table` app is not part of the launch path.

### Fixed

- Fixed the onboarding prompt duplication where the README repeated Draftsman
  instructions that should be loaded from the repo bootstrap instead.
- Fixed stale README guidance that still referenced the non-launch `draft-table`
  app workflow.

### Migration Notes

- Existing workspaces can continue unchanged.
- Existing company READMEs can refresh from the workspace template or apply the
  same prompt simplification locally.

## 0.13.5 - 2026-05-14

### Compatibility Impact

No migration is required. This patch clarifies how the first-run prompt names
the target workspace repository; it does not change schemas, validation
behavior, or catalog object formats.

### Added

- Added rendered repository references to the company workspace README prompt
  so copied prompts can tell an AI exactly which repo to connect to.

### Changed

- Updated workspace template rendering to derive repository slug and GitHub URL
  from `.draft/workspace.yaml` repository metadata.

### Fixed

- Fixed the onboarding prompt gap where a copied company README prompt could
  still be ambiguous about which repo the AI should use.

### Migration Notes

- Existing workspaces can continue unchanged.
- To get repo-specific prompts in existing workspaces, add `repository`
  metadata to `.draft/workspace.yaml` and refresh or update the workspace
  README.

## 0.13.4 - 2026-05-14

### Compatibility Impact

No migration is required. This patch clarifies the first-run workspace prompt
only; it does not change schemas, validation behavior, or catalog object
formats.

### Added

- Added prompt language telling a connected AI assistant to treat the current
  repository as the selected workspace and only ask for a repo path when it is
  not actually connected to that workspace.

### Changed

- Updated the company workspace README template so the first-run Draftsman
  prompt is explicit about using the currently connected repo.

### Fixed

- Fixed the easy-button onboarding prompt ambiguity where an engineer could be
  connected to the correct repo but still get asked to supply the repo path.

### Migration Notes

- Existing workspaces can continue unchanged.

## 0.13.3 - 2026-05-14

### Compatibility Impact

No migration is required. This patch adds a workspace README template and
refresh behavior for missing bootstrap files; it does not change schemas,
validation behavior, or catalog object formats.

### Added

- Added `templates/workspace/README.md.tmpl` with a copy/paste Draftsman
  session prompt for adopting company workspaces.
- Added workspace template substitutions for `workspace_name`,
  `workspace_label`, and `company_name` so first-time onboarding files can use
  the adopting company's name.

### Changed

- Updated workspace scaffolding and framework refresh helpers to create missing
  root workspace bootstrap files, including the README prompt, without
  overwriting existing company-owned files.
- Updated workspace templates to render company-specific README and AI
  bootstrap language from `.draft/workspace.yaml` or a readable repo-name
  fallback.
- Updated onboarding and workspace documentation to call out the README
  Draftsman start prompt.

### Fixed

- Fixed the adoption gap where a newly created company workspace could include
  AI bootstrap files but no obvious human-facing prompt for starting a
  Draftsman session.

### Migration Notes

- Existing workspaces can continue unchanged.
- To adopt the prompt in an existing workspace, copy
  `templates/workspace/README.md.tmpl` to the workspace root as `README.md` or
  merge the prompt into the existing workspace README.

## 0.13.2 - 2026-05-13

### Compatibility Impact

No migration is required. This patch improves first-run README guidance only;
it does not change schemas, validation behavior, or catalog object formats.

### Added

- Added a copy/paste Draftsman startup prompt for users connecting their
  preferred AI assistant to DRAFT for the first time.

### Changed

- Reworked the README opening to explain DRAFT as a repo-based architecture
  framework and to make the v1.0 repo-first path easier to follow.

### Fixed

- Removed duplicated repo-first onboarding language from the README.

### Migration Notes

- Existing workspaces can continue unchanged.

## 0.13.1 - 2026-05-13

### Compatibility Impact

No migration is required. This patch changes v1.0 onboarding guidance and
roadmap scope; it does not change schemas, validation behavior, or catalog
object formats.

### Added

- Added roadmap language that explicitly parks the DRAFT Table app and
  `draft-table` CLI as post-v1.0 future enhancements.

### Changed

- Changed onboarding, setup-mode, workspace, user manual, README, and AI
  bootstrap guidance to make the v1.0 path repo-first: a company connects its
  preferred AI tool to a DRAFT workspace repo and the AI follows the bootstrap
  files as the Draftsman.

### Fixed

- Fixed misleading first-run documentation that implied `draft-table onboard`,
  a local app, or a DRAFT-specific CLI was required for v1.0 adoption.

### Migration Notes

- Existing workspaces can continue unchanged.
- Companies adopting v1.0 should treat local DRAFT Table tooling as optional
  experimental tooling and rely on Git, pull requests, validation, and their
  chosen AI assistant for the canonical workflow.

## 0.13.0 - 2026-05-13

### Compatibility Impact

No migration is required for existing workspaces. Company vocabulary lists are
optional, and undeclared lists preserve the existing free-text behavior.

### Added

- Added optional workspace vocabulary declarations for deployment targets, data
  classification levels, team IDs, availability tiers, and failure domains.
- Added advisory and gated vocabulary validation modes.
- Added `vocabulary` and `vocabulary_proposal` YAML document support for
  company-owned vocabulary source files and non-standard value review flow.
- Added `framework/tools/apply_vocabulary_proposals.py` and a workspace GitHub
  Actions template that can open review pull requests for proposed standard
  values.
- Added the Company Vocabulary guide and browser navigation link.

### Changed

- Updated Draftsman, onboarding, setup-mode, workspace, Software Deployment
  Pattern, and AI bootstrap guidance to use declared vocabulary choices during
  interviews.
- Updated workspace scaffolding to create vocabulary folders and install the
  vocabulary proposal workflow template.

### Fixed

- Fixed the adoption gap where companies had no framework-supported way to
  move from free-text deployment targets, teams, availability tiers, data
  classifications, and failure domains toward governed choices.

### Migration Notes

- Existing workspaces can continue unchanged.
- To adopt vocabulary governance, declare one list at a time under
  `.draft/workspace.yaml`, start with `mode: advisory`, and move a list to
  `mode: gated` only when the company wants validation to block non-standard
  values.

## 0.12.6 - 2026-05-13

### Compatibility Impact

No workspace migration is required. This patch adds roadmap documentation and
AI discovery metadata without changing schemas, validation contracts, or stored
object formats.

### Added

- Added `ROADMAP.md` as the stable v1.0 readiness narrative for the executable
  deployment contract, golden reference workspace, and deterministic Draftsman
  workflow.

### Changed

- Updated AI discovery metadata so assistants can find the v1.0 roadmap from
  `AI_INDEX.md` and `llms.txt`.

### Fixed

- Fixed the missing repository-level roadmap for the existing v1.0 milestone
  and tracking issues.

### Migration Notes

- No migration is required.

## 0.12.5 - 2026-05-13

### Compatibility Impact

No workspace migration is required. This patch strengthens AI bootstrap and
Draftsman write-boundary guidance without changing DRAFT object schemas.

### Added

- Added company workspace AI bootstrap templates for `AGENTS.md`, `CLAUDE.md`,
  `GEMINI.md`, `llms.txt`, and `.github/copilot-instructions.md`.
- Added backend Draftsman proposal protection that rejects writes to
  `.draft/framework/**` and `.draft/framework.lock`.

### Changed

- Updated Draftsman guidance so company architecture content is not written
  into the upstream framework repo when no company workspace is selected.
- Updated the DRAFT Table Draftsman prompt to ask for a company-specific DRAFT
  repo before proposing content changes against the upstream framework repo.

### Fixed

- Fixed an AI-first gap where company repos could rely only on nested vendored
  framework instructions, which some AI tools do not load automatically from
  the repository root.

### Migration Notes

- Refresh the framework in company workspaces to pick up the new Draftsman
  guardrails and workspace bootstrap templates.
- Existing company repos can add root AI bootstrap files that point agents at
  `.draft/framework/` and prohibit normal Draftsman edits to vendored framework
  files.

## 0.12.4 - 2026-05-04

### Compatibility Impact

Self-managed Runtime Services, Data-at-Rest Services, and Edge/Gateway Services
now have an explicit service-behavior requirement to reference their Host
Standard. Existing draft objects without a host will receive validation
warnings; approved objects without a host will fail validation until the host
substrate is recorded.

### Added

- Added `DRAFT Service Behavior / runtime-substrate` to require self-managed
  services to identify the Host Standard that provides their execution
  substrate.
- Added RA-guided drafting and composition-closure guidance for Software
  Deployment Pattern interviews.

### Changed

- Updated Draftsman guidance so Reference Architectures are searched and
  proposed as drafting maps instead of being asked as a user-facing catalog
  form question.
- Updated the DRAFT Table Draftsman prompt to walk the deployable object graph
  after SDP topology discovery and avoid hidden substrate assumptions such as
  EKS, EC2, Lambda, VM, physical, or container placement.

### Fixed

- Fixed a gap where a Draftsman could complete a Software Deployment Pattern
  session without resolving the host/substrate choice for self-managed
  services.

### Migration Notes

- Refresh the framework and regenerate `docs/index.html`.
- For any self-managed service object that does not declare `host`, select the
  correct Host Standard or record the unresolved substrate in a Drafting
  Session before approving the object.

## 0.12.3 - 2026-05-04

### Compatibility Impact

No workspace migration is required. This patch strengthens Draftsman interview
guidance without changing schemas or stored object references.

### Added

- No new framework features in this patch release.

### Changed

- Updated Draftsman guidance so requirement-backed capability questions use
  company-approved `preferred` and `existing-only` implementations as concrete
  choices whenever they exist.
- Clarified that "something else" is an exception path requiring
  capability-owner review before a Technology Component becomes acceptable use.
- Updated the DRAFT Table Draftsman prompt to resolve capability criteria and
  ask catalog-grounded multiple-choice questions instead of defaulting to
  open-ended prompts.

### Fixed

- Fixed guidance that could allow a Draftsman to ask open-ended capability
  questions even when the effective catalog already contained approved
  standard choices.

### Migration Notes

- Refresh the framework and regenerate `docs/index.html` to pick up the
  updated Draftsman interview guidance.

## 0.12.2 - 2026-05-04

### Compatibility Impact

No workspace migration is required. This patch clarifies Software Deployment
Pattern deployment-target wording and Draftsman interview behavior without
changing schemas or stored object references.

### Added

- No new framework features in this patch release.

### Changed

- Changed the `deployment-targets` requirement to ask for a deployment boundary
  or execution context rather than a generic "where it runs" answer.
- Updated Software Deployment Pattern and Draftsman documentation to clarify
  that deployment targets are not inherently cloud regions or controlled-list
  answers unless an active company/control requirement makes them so.
- Updated Software Deployment Pattern and Reference Architecture templates to
  use deployment boundary/execution context language.

### Fixed

- Fixed the missing `deploymentTargets` validation message so it no longer
  implies a raw target field without the architectural boundary semantics.

### Migration Notes

- Refresh the framework and regenerate `docs/index.html` to pick up the
  clarified requirement wording and Draftsman guidance.

## 0.12.1 - 2026-05-04

### Compatibility Impact

No workspace migration is required. This patch only completes the
human-readable requirement label rollout in validation messages.

### Added

- No new framework features in this patch release.

### Changed

- Changed remaining requirement implementation validation messages to cite
  source-aware labels such as `SOC 2.CC7.security-monitoring` and
  `DRAFT Host / operating-system`.

### Fixed

- Fixed active requirement implementation gap messages that still displayed raw
  Requirement Group UIDs instead of the resolved authority/control label.

### Migration Notes

- Refresh the framework and regenerate `docs/index.html` to pick up the
  updated validation wording.

## 0.12.0 - 2026-05-04

### Compatibility Impact

No workspace migration is required. Requirement Group machine references remain
unchanged: objects still store `requirementGroup` as the group UID and
`requirementId` as the requirement-local ID. Generated UI and validation
messages now resolve those keys into human-readable requirement citations.

### Added

- Added `authority.shortName` guidance for Requirement Groups so external
  controls can render as labels such as `SOC 2.CC7.security-monitoring`,
  `NIST CSF.PR.AA`, `TX-RAMP.AC-2`, or `CompanyPolicy.IAM.04`.
- Added explicit DRAFT authority metadata to framework-native always-on
  Requirement Groups so they render as labels such as
  `DRAFT Host / operating-system`.
- Added Requirement Evidence detail tables to generated browser artifact pages
  when object-level requirement implementations are recorded.

### Changed

- Changed generated browser requirement cards, object Requirement Group badges,
  requirement evidence drill-downs, and artifact evidence tables to use
  source-aware requirement labels instead of raw Requirement Group UIDs or
  unsourced control IDs.
- Changed validation failure messages for unmet or not-compliant requirements
  to cite the resolved requirement label and source Requirement Group.
- Updated Draftsman and authoring documentation to tell AI agents to use
  sourced requirement labels in conversation.

### Fixed

- Fixed ambiguous requirement/control display where controls such as `CC.04.4.1`
  appeared without showing whether they came from SOC 2, DRAFT Security,
  or another activated Requirement Group.

### Migration Notes

- Refresh the framework and regenerate `docs/index.html` to pick up sourced
  requirement labels.
- Company-owned external control mappings should add `authority.shortName` to
  their Requirement Groups. Existing objects do not need their
  `requirementGroups` or `requirementImplementations` rewritten.

## 0.11.0 - 2026-05-04

### Compatibility Impact

Pre-1.0 validation behavior changed for Capability governance. Approved
Capabilities must now be traceable to at least one Requirement Group through a
requirement `relatedCapability` reference. Workspaces with approved
Capabilities that are not requirement-backed must either add requirement
coverage or downgrade those Capabilities to draft/stub until the demand signal
is defined.

### Added

- Added a company onboarding tutorial at `framework/docs/company-onboarding.md`
  that walks a new company through repository setup, vendored framework
  refresh, requirement activation, capability ownership, acceptable-use
  technology, first deployable objects, validation, and update readiness.
- Added a generated browser Onboarding page so the DRAFT Table UI can guide new
  users without leaving the local catalog browser.
- Added onboarding guidance to the Draftsman grounding context, `AI_INDEX.md`,
  and `llms.txt`.

### Changed

- Changed Capability validation so approved Capabilities must be requirement
  traceable while draft/stub Capabilities without requirement traceability emit
  actionable warnings.
- Changed eight framework base Capabilities that are not yet requirement-backed
  from approved to draft.
- Updated Capability, Requirement Group, Draftsman, workspace, and overview
  documentation to describe requirement-first traceability and company-owned
  implementation decisions.
- Changed the generated browser impact graph so Technology Components are not
  treated as lifecycle-filterable deployable object nodes.

### Fixed

- Fixed generated browser lifecycle filtering so Technology Components do not
  appear in deployable object lifecycle impact views.

### Migration Notes

- Run validation after refreshing the framework and review any Capability
  traceability warnings.
- For each workspace-owned Capability with `catalogStatus: approved`, add at
  least one Requirement Group requirement with `relatedCapability` pointing to
  that Capability, or downgrade the Capability to draft/stub until it is backed
  by a requirement.
- Regenerate `AI_INDEX.md` and `docs/index.html` after refreshing the
  framework.

## 0.10.0 - 2026-05-04

### Compatibility Impact

Breaking pre-1.0 object taxonomy migration required. Workspaces using legacy
Host Standard, Service Standard, Database Standard, PaaS Service Standard, SaaS
Service Standard, or Appliance Component object types must migrate to the new
deployable object taxonomy and regenerate derived browser/index output.

### Added

- Added first-class deployable object taxonomy documentation in
  `framework/docs/object-types.md`.
- Added `runtime_service`, `data_at_rest_service`, `edge_gateway_service`, and
  `host` schemas to replace legacy Standard-classification schemas.
- Added `deliveryModel` support for self-managed, PaaS, SaaS, and appliance
  delivery on service objects.
- Added a generated browser Object Types information page that explains
  deployable versus non-deployable architecture content.
- Added one-time `framework/tools/migrations/0.10.0/migrate_object_taxonomy.py`
  migration support for the pre-1.0 adopting workspace.

### Changed

- Replaced legacy Standard-classification object types with explicit deployable
  object types: Host, Runtime Service, Data-at-Rest Service, Edge/Gateway
  Service, Product Service, Technology Component, and Software Deployment
  Pattern.
- Changed Software Deployment Pattern and Reference Architecture service groups
  from `standards` plus `applianceComponents` to `deployableObjects`.
- Changed PaaS, SaaS, and appliance from separate object types into delivery
  models on Runtime Service, Data-at-Rest Service, and Edge/Gateway Service.
- Updated Draftsman guidance, templates, validation, DRAFT Table catalog
  discovery, generated browser rendering, and AI index generation for the new
  object taxonomy.

### Fixed

- Removed stale Standard-classification language from framework documentation
  and generated UI copy.
- Fixed service-group validation messages so they refer to deployable objects
  instead of standards.

### Migration Notes

- Run the 0.10.0 migration script against existing workspaces, then validate:
  `python3 .draft/framework/tools/migrations/0.10.0/migrate_object_taxonomy.py .`
- Regenerate `AI_INDEX.md` and `docs/index.html` after migration.
- Review service group entries after migration to confirm each
  `deployableObjects[].ref` points to the intended Host, Runtime Service,
  Data-at-Rest Service, Edge/Gateway Service, or Product Service.
- Review PaaS, SaaS, and appliance migrated services to confirm the selected
  object type matches the behavior first and `deliveryModel` matches how it is
  operated.

## 0.9.1 - 2026-05-03

### Compatibility Impact

No schema, validation, or catalog object compatibility impact. Existing
workspaces remain valid.

### Added

- Added subtle accent-tinted backgrounds to DRAFT Overview metric tiles so the
  generated browser overview has more visual hierarchy without changing object
  data.

### Changed

- Renamed the generated browser's visible "Executive View" label to "DRAFT
  Overview" while preserving the existing internal route state.

### Fixed

- No defect fixes in this patch release.

### Migration Notes

- Regenerate `docs/index.html` after refreshing the framework to pick up the
  updated generated browser labels and metric tile styling.

## 0.9.0 - 2026-05-03

### Compatibility Impact

Breaking pre-1.0 object identity migration required. First-class catalog and
configuration objects now use generated `uid` values instead of semantic
top-level `id` values. Existing workspaces must run UID repair and regenerate
derived browser/index output. Workspaces remain free to opt into
`businessTaxonomy.requireSoftwareDeploymentPatternPillar` separately.

### Added

- Added optional `businessContext` support to Software Deployment Patterns so
  company workspaces can identify the primary business pillar, additional
  pillars, and product family for a deployment pattern.
- Added workspace `businessTaxonomy.pillars` validation through
  `.draft/workspace.yaml`.
- Added generated browser grouping and badges for Software Deployment Patterns
  by workspace-defined business pillar.
- Added generated UID validation for first-class objects. Validation now
  reports missing, malformed, duplicate, and legacy top-level object identity
  with a suggested UID and an explicit repair command.
- Added `framework/tools/repair_uids.py` and `framework/tools/uid_utils.py` to
  generate object UIDs, remove legacy top-level `id`, rewrite exact object
  references, and migrate legacy Drafting Session UID field names.
- Added optional `aliases` to first-class object schemas so prior or alternate
  human-readable names can resolve to the same stable object.

### Changed

- Updated Draftsman and workspace documentation so company business taxonomy is
  resolved from `.draft/workspace.yaml`, not tags, capabilities, or Strategy
  Domains.
- Changed first-class object identity from semantic `id` to generated opaque
  `uid`. Human-facing object resolution should use name, aliases, path, close
  match, and only then UID.
- Changed object reference validation, object patching, browser generation, and
  AI index generation to use generated UIDs as the machine reference key.
- Changed Drafting Session object-reference fields from `primaryObjectId` and
  `proposedId` to `primaryObjectUid` and `proposedUid`.

### Fixed

- Fixed the Software Deployment Pattern browsing experience so product
  deployment patterns can be scanned by company portfolio ownership instead of
  only by object type.
- Fixed generated browser reference discovery so generated UID references are
  indexed without depending on semantic object prefixes.

### Migration Notes

- Run `python3 framework/tools/repair_uids.py --workspace examples` in the
  framework repo, or `python3 .draft/framework/tools/repair_uids.py --workspace
  .` from a company repo, to add generated `uid` values, remove legacy
  top-level `id`, and rewrite exact object references.
- Regenerate `AI_INDEX.md` and `docs/index.html` after UID repair.
- If validation reports a missing, malformed, duplicate, or legacy identity,
  run the exact repair command it prints; the command includes the suggested
  UID when repairing a single file.
- To use the business taxonomy feature, declare `businessTaxonomy.pillars` in
  `.draft/workspace.yaml`, then add `businessContext.pillar` to each Software
  Deployment Pattern. Set
  `businessTaxonomy.requireSoftwareDeploymentPatternPillar: true` only after the
  workspace is ready to enforce the field.

## 0.8.2 - 2026-05-03

### Compatibility Impact

No schema, validation, or catalog object compatibility impact. Existing
workspaces remain valid.

### Added

- Added generated browser rendering for Software Deployment Pattern source
  repositories when repository provenance is recorded on the object.

### Changed

- Updated Draftsman guidance so repository-discovered artifacts record
  provenance on each generated object, not only in a shared Drafting Session.

### Fixed

- Fixed generated browser rendering for nested architectural decision arrays so
  structured provenance entries do not appear as `[object Object]`.

### Migration Notes

No workspace data migration is required. Repository-discovered Software
Deployment Patterns can optionally add
`architecturalDecisions.sourceRepositories` to make per-pattern provenance
visible in the generated browser.

## 0.8.1 - 2026-05-03

### Compatibility Impact

No schema, validation, or catalog object compatibility impact. Existing
workspaces can continue using 0.8.0 content and only need to refresh generated
browser assets to receive the updated welcome-page branding.

### Added

- Added the transparent 512x512 `draft-logo.png` asset to the framework so
  generated browser pages can use the official DRAFT logo.
- Added automated version-bump enforcement to the release-note checker so
  release-impacting framework changes must advance `draft-framework.yaml`.

### Changed

- Changed the Executive View welcome hero to place the larger DRAFT logo beside
  the full title, descriptive text, and action area, and retitled the page
  `Welcome to the DRAFTing Table`.
- Documented the AI release decision procedure for choosing pre-1.0 minor
  versus patch releases consistently.

### Fixed

- Fixed framework release metadata so the generated browser branding change is
  recorded as patch release 0.8.1.
- Fixed the validation workflow label to make version-bump enforcement explicit
  in GitHub Actions.

### Migration Notes

No YAML or workspace data migration is required. Regenerate `docs/index.html`
or pull the updated vendored framework files to display the new welcome logo
layout in an existing workspace.

## 0.8.0 - 2026-05-03

### Compatibility Impact

Breaking pre-1.0 lifecycle vocabulary migration required. Workspaces must
replace the old lifecycle labels with the new plain-language labels across
catalog objects and capability implementation mappings: `pre-invest` becomes
`candidate`, `invest` becomes `preferred`, `maintain` becomes `existing-only`,
`disinvest` becomes `deprecated`, and `exit` becomes `retired`.

### Added

- Added an Executive View as the default generated browser landing page, with
  clickable metric tiles for controls addressed, Technology Components,
  Capabilities, Software Deployment Patterns, requirement definitions, and
  acceptable-use mappings.
- Added an Acceptable Use Technology browser view that groups Technology
  Component lifecycle mappings by domain and capability, including owner/contact
  information for change requests.

### Changed

- Renamed lifecycle vocabulary to plainer adopting-company language:
  `candidate`, `preferred`, `existing-only`, `deprecated`, and `retired`.
- Renamed the generated browser list navigation to Drafting Table so the
  executive landing page can hand users into the existing object browser.
- Documented Reference Architecture lifecycle policy: cloud-forward patterns are
  `preferred`, legacy supported patterns are `existing-only`, and patterns containing
  end-of-support Technology Components are `deprecated`. Patterns containing
  extended-support Technology Components default to `deprecated`, may be
  `existing-only` with explicit rationale, and must not be `preferred`.
- Increased Executive View metric and tile heading sizes so each collage tile
  carries equal visual weight.
- Fixed Executive View tile CSS so the shared large metric size is not
  overridden by paragraph styling.
- Documented the Acceptable Use Technology view as the generated human-readable
  table for company technology lifecycle mappings.
- Changed the Acceptable Use Technology table to group Technology Components
  under capability headers, with owner/contact shown on the capability header
  instead of repeated in every row.
- Changed the Acceptable Use Technology view to omit unmapped capabilities and
  empty domain groups so it remains a Technology Component list.
- Clarified Draftsman guidance for overlapping base and workspace-activated
  control requirements that share a capability.
- Added per-capability Technology Component counts to the Acceptable Use
  Technology browser view.

### Fixed

- Fixed generated browser payloads so Capability domain assignments are included
  in the Acceptable Use Technology view instead of appearing as unassigned.
- Fixed Reference Architecture and Software Deployment Pattern requirement
  evidence so `serviceGroups`, `patternType`, and `architecturalDecisions`
  fields satisfy the matching requirement group checks directly.
- Fixed requirement satisfaction for external interactions declared inside
  `serviceGroups`, so nested service group interactions count toward the same
  mechanisms as top-level interactions.
- Fixed Reference Architecture validation so patterns that include Technology
  Components past `vendorLifecycle.extendedSupportEnd` must be marked
  `deprecated`.
- Fixed Reference Architecture validation so patterns that include Technology
  Components past `vendorLifecycle.mainstreamSupportEnd` cannot be marked
  `preferred`; `existing-only` requires an explicit lifecycle rationale.

### Migration Notes

- Replace lifecycle labels in workspace YAML:
  `pre-invest` -> `candidate`, `invest` -> `preferred`,
  `maintain` -> `existing-only`, `disinvest` -> `deprecated`,
  and `exit` -> `retired`.
- Regenerate `docs/index.html` to publish the Acceptable Use Technology view for
  a framework or workspace browser.

## 0.7.0 - 2026-05-02

### Compatibility Impact

Breaking workspace migration is required for capability overlays that assign
Technology Component implementations. DRAFT is still pre-1.0, so breaking
object model changes are allowed in 0.MINOR.0 releases when documented with
migration notes.

Existing name-only external interactions remain valid, but shared platforms
should be modeled and referenced when known.

### Added

- Added validation that `externalInteractions[].ref` values point to existing
  catalog objects.
- Added `definitionOwner` to Capability objects so framework, provider, and
  company vocabulary ownership is separate from company implementation
  authority.
- Added validation requiring `owner.team` on the effective Capability whenever
  implementations are assigned.

### Changed

- Changed framework base Capabilities to carry `definitionOwner` only and leave
  company `owner` to workspace overlays.
- Clarified that Capability implementation lifecycle entries must reference
  Technology Components only, because lifecycle disposition applies to a
  discrete vendor product and version.
- Clarified that central logging and other shared enterprise platforms should be
  modeled as Standards or service classifications rather than left as permanent
  name-only external interactions.
- Updated Requirement Group examples and the host template to prefer resolved
  logging platform references.
- Updated the browser to distinguish Capability definition owner from company
  owner.

### Fixed

- Fixed workspace-mode Requirement Group validation so active groups remain
  incremental when `requireActiveRequirementGroupDisposition` is false, while
  still requiring explicit activation before an object can claim them.
- Fixed Requirement Group validation so resolving `requirementImplementations`
  satisfy the matching requirement evidence during workspace control validation.

### Migration Notes

- Refresh the vendored framework copy.
- Add `definitionOwner` to any workspace-owned Capability files.
- Add `patch.owner.team` or full `patch.owner` to object patches that assign
  Capability implementations.
- Keep Capability `implementations[].ref` pointed at Technology Components
  only. If a SaaS or managed service is lifecycle-governed, model the specific
  vendor product and version as a Technology Component and compose the
  service-facing Standard separately.
- Existing black-box external interactions can stay as drafting placeholders.
  When the target platform is known, add or reuse the modeled DRAFT object and
  set `externalInteractions[].ref`.

## 0.6.0 - 2026-05-01

### Compatibility Impact

Breaking workspace migration is required for pre-0.6.0 content that uses
Definition Checklists, Compliance Controls, Control Enforcement Profiles, or
top-level Technology Component `lifecycleStatus`. DRAFT is still pre-1.0, so
breaking object model changes are allowed in 0.MINOR.0 releases when documented
with migration notes.

### Added

- Added first-class `capability` objects in `framework/configurations/capabilities/`.
- Added unified `requirement_group` objects in
  `framework/configurations/requirement-groups/`.
- Added sample workspace capability implementation patches under
  `examples/configurations/object-patches/`.
- Added AI-first schema `aiHint` metadata and required-field descriptions.
- Added a DRAFT Table Guide tab that explains what DRAFT is, how to navigate the
  UI, what the core artifact families mean, and how content updates flow through
  Draftsman, validation, and Git.

### Changed

- Replaced Definition Checklists and Compliance Controls plus Control
  Enforcement Profiles with the unified Requirement Group model.
- Replaced workspace `compliance.activeControlEnforcementProfiles` with
  `requirements.activeRequirementGroups`.
- Replaced object-level `controlEnforcementProfiles` and
  `controlImplementations` with `requirementGroups` and
  `requirementImplementations`.
- Changed Technology Component `capabilities` to reference capability object IDs.
- Removed top-level Technology Component `lifecycleStatus`; company disposition
  now lives on capability implementation mappings.
- Updated the browser to remove the Compliance Build Profile selector and show
  Capabilities and Requirement Groups as framework content.
- Updated Draftsman guidance to use the named requirement-to-capability lookup
  chain before asking users open-ended questions.

### Fixed

- Improved validation failures so missing schema fields and requirement gaps are
  written as actionable instructions.

### Migration Notes

- Move any workspace Definition Checklist files to `requirement_group` objects
  under `configurations/requirement-groups/`.
- Move active compliance profile configuration to:
  `requirements.activeRequirementGroups`.
- Rename object evidence fields from `controlEnforcementProfiles` and
  `controlImplementations` to `requirementGroups` and
  `requirementImplementations`.
- Convert bare capability strings such as `log-management` to namespaced
  capability IDs such as `capability.log-management`.
- Move Technology Component adoption disposition into capability implementation
  mappings. Keep vendor support dates in Technology Component `vendorLifecycle`.
- Refresh the vendored framework copy and run
  `python3 .draft/framework/tools/validate.py --workspace .`.

## 0.5.0 - 2026-04-30

### Compatibility Impact

No workspace object migration is required. Company workspaces can adopt this
release by refreshing their vendored framework and adding the optional update
workflow.

### Added

- Added a default company-side GitHub Actions workflow template that checks for
  newer DRAFT Framework versions, opens an update branch and pull request,
  refreshes `.draft/framework/`, updates `.draft/framework.lock`, and records
  validation status.
- Added blocked update PR behavior for failed workspace validation so companies
  can repair migration issues on the update branch instead of losing the
  attempted framework update.

### Changed

- Updated DRAFT Table workspace bootstrap so new company workspaces receive the
  framework update workflow by default.
- Documented the company framework update notification and PR workflow.

### Fixed

- No fixes in this release.

### Migration Notes

- Existing company workspaces can copy
  `templates/workspace/.github/workflows/draft-framework-update.yml.tmpl` to
  `.github/workflows/draft-framework-update.yml`.
- The workflow is optional. Disable it in GitHub Actions or delete the workflow
  file if the company wants to manage framework updates manually.

## 0.4.0 - 2026-04-30

### Compatibility Impact

Breaking workspace migration may be required for workspaces created from earlier
pre-1.0 framework commits. This release is still in the pre-1.0 framework
formation phase, so object model changes are allowed when documented here.

### Added

- Added DRAFT Table as the local-first Draftsman web and CLI experience.
- Added company workspace bootstrapping with a vendored `.draft/framework/`
  copy and explicit framework refresh behavior.
- Added provider-scoped compliance controls and Control Enforcement Profiles.
- Added active compliance profile configuration in `.draft/workspace.yaml`.
- Added the current framework version manifest at `draft-framework.yaml`.

### Changed

- Renamed the primary DRAFT terminology around Technology Components,
  Appliance Components, Host Standards, Service Standards, Database Standards,
  Reference Architectures, Software Deployment Patterns, Definition Checklists,
  Decision Records, Compliance Controls, and Control Enforcement Profiles.
- Updated compliance activation so framework, third-party, and company control
  providers can coexist without filename or ownership ambiguity.
- Updated appliance component guidance so service-like required capabilities are
  captured directly on the appliance component.
- Updated Draftsman guidance so capability questions ask what satisfies the
  capability, not which organization team performs the work.

### Fixed

- Fixed DRAFT Table onboarding behavior for piped installers and local content
  repo creation.
- Fixed Draftsman chat route diagnostics and provider timeout surfacing.
- Fixed browser and DRAFT Table UI alignment with the GitHub Pages experience.

### Migration Notes

- Refresh the vendored framework copy in each company workspace through
  `draft-table framework refresh` or the equivalent repository process.
- Review object and file naming against the updated terminology before treating
  old workspace content as current.
- Update any references to framework-provided compliance profiles to the
  provider-scoped IDs such as `control-enforcement.draft-soc2`.
- Use `controlEnforcementProfiles` and `controlImplementations` to record active
  compliance disposition; `opted-out` has been replaced by `not-compliant`.
- Run validation after refresh with
  `python3 .draft/framework/tools/validate.py --workspace .`.
