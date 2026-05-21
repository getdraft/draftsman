# Changelog

All notable DRAFT Framework changes are recorded here. Every release requires
notes, including patch releases.

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
  source-aware labels such as `Roper.CC.03.2.3` and
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
  `NIST CSF.PR.AA`, `TX-RAMP.AC-2`, or `Roper.CC.04.4.1`.
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
  appeared without showing whether they came from Roper, SOC 2, DRAFT Security,
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
