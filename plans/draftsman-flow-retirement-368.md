# Draftsman #368: retire relationship flow and migrate legacy relationships to listeners

<!-- sdlc-plan-id: draftsman-flow-retirement-368 -->

## Plan: Draftsman #368: retire relationship flow and migrate legacy relationships to listeners

**Goal:** Every call in Dale's Draftsman reads one way: the caller is the source and the arrow lands on the listener it calls. The old flow values and free-text external targets keep working but are flagged, only when someone touches them, and a migration helper proposes the fixes as a reviewable patch so no workspace has a flag day.

**Target repo(s):** `getdraft/draftsman`

**Approval:** Dale's standing instruction "I want the backlog cleared", and his 2026-11-20 7:51 PM Phoenix go-ahead: "Write Plan B and build it directly, no approval stop needed." This plan follows the same direct path as Plans B and C of #341. Built outside the agentic SDLC because BeerCanLabs GitHub Actions billing blocks the fleet; draftsman CI is unaffected.

### In scope
- #368 items 1-5: deprecate `flow: inbound|bidirectional` and free-text `externalTarget`; the three ratcheted rules; listener-end arrowheads; the migration helper and `/draft migrate`; near-match prompting.
- The #368 adoption requirement (strangler migration), its compatibility and flag-on-touch tests, docs, templates, examples and the release note.

### Out of scope
- Removing `flow` or `externalTarget` from the schema (a later major version, after the ratchet drains).
- Migrating the bundled example catalog's existing `externalTarget` relationships: they are baselined and stay as legacy content that the migration helper can be shown on.
- Retiring `product_component.interfaces[]`, reconciling listener ports with definition ports, a "what calls this listener" view, per-environment bindings (#341 deferrals).

### Acceptance criteria
- flow: inbound and flow: bidirectional, and free-text externalTarget, are marked deprecated in the relationship schema, the relationship template, the object-type reference and the Draftsman docs, and still load, validate structurally and render. outbound is the documented default and only meaningful value. Removal is deferred to a later major version after the ratchet drains.
- Ratcheted rules relationship-flow-deprecated (flow is inbound or bidirectional), relationship-external-target-freetext (externalTarget is set where a system object and its listener could be referenced) and relationship-source-is-listener-side (an inbound relationship whose source looks like the listener side) are registered with fix guidance. The repo's example and fixture baselines are refreshed with validate.py --write-baseline so existing content stays green.
- Compatibility test: a workspace with v1.5.5-style content (bidirectional, inbound and externalTarget relationships), refreshed with validate.py --write-baseline, validates with exit code 0 and only baseline: warnings for these rules. Flag-on-touch test: editing one baselined relationship turns its violations into errors while untouched legacy relationships stay warnings.
- Diagrams: a relationship that names a targetListener draws a single arrowhead at the listener (target) end and none at the caller's end, with its flow overlay running caller to listener, whatever its legacy flow says. Relationships without a targetListener render exactly as today, so a framework update does not redraw existing diagrams (goldens unchanged); a mixed legacy and migrated workspace renders without contradictions; the changelog states the rule.
- Migration: framework/tools/migrate_relationships.py scans a workspace, or one object, SDP or folder, and writes a reviewable proposal report plus an optional unified-diff patch; it never edits catalog files. It proposes bidirectional -> outbound; inbound -> swapped source and target, or removal with a note for the listener's authenticationModel or description when the caller is an unknown external party; externalTarget -> an existing or new external system plus a listener through lookup-before-create (link_or_stub_listener), with a stub when the endpoint is unknown and a needs-input item when no port can be found; and it reports relationships that read like protection descriptions. A /draft migrate action routes to it.
- Near-match prompting: a draft_table.catalog helper lists listeners under the same owner and protocol whose port or path differs only by version or path, and the Draftsman docs and skills say to ask whether a near match is the same listener, never to link it silently.
- Docs, object-type reference, templates and examples are updated, including an example with two look-alike internal SFTP listeners on the same port under different owners and one external system whose listeners are reused by several callers; the CHANGELOG documents the deprecations and the adoption path.

### Story breakdown
1. **S1.1 Deprecation in schema, template and docs.** Files: `framework/schemas/relationship.schema.yaml`, `templates/relationship.yaml.tmpl`, `framework/docs/object-types.md`, `framework/docs/draftsman.md`, tests, `CHANGELOG.md`.
2. **S1.2 Ratcheted rules and refreshed baselines.** Files: `framework/tools/validate.py`, `examples/.draft/validation-baseline.yaml`, `tests/fixtures/**/.draft/validation-baseline.yaml`, `tests/test_validation.py` (or a new rules test), `CHANGELOG.md`.
3. **S1.3 Compatibility and flag-on-touch tests.** Files: a v1.5.5-style fixture workspace under `tests/fixtures/`, a new test module, `CHANGELOG.md`.
4. **S2.1 Single arrowhead at the listener end.** Files: `framework/tools/generate_diagram.py`, `tests/test_generate_diagram.py`, `framework/skills/draftsman-diagram/SKILL.md`, `CHANGELOG.md`.
5. **S2.2 Migration proposal helper.** Files: `framework/tools/migrate_relationships.py`, `tests/test_migrate_relationships.py`, `CHANGELOG.md`.
6. **S2.3 `/draft migrate` and near-match prompting.** Files: `framework/draft-actions/migrate.md`, `framework/commands/draft.md`, `draft_table/catalog.py`, `framework/docs/draftsman.md`, skills, tests, `CHANGELOG.md`.
7. **S2.4 Examples, docs and adoption note.** Files: `examples/catalog/**` (look-alike SFTP listeners, a reused external system), `framework/docs/object-types.md`, `framework/docs/how-to-add-objects.md`, `CHANGELOG.md`.

Stories run in order; each is one squash-merged PR that closes its story issue.

### Decisions made while planning
- **Warnings first, errors only on touch.** All three rules are ratcheted (D49): existing content becomes `baseline:` warnings after `validate.py --write-baseline`, and only new or edited relationships fail.
- **`relationship-source-is-listener-side` is a subset of `inbound`.** It fires only on `flow: inbound` relationships whose source owns listeners or whose target is an external party, so it never fails content that `relationship-flow-deprecated` does not already flag.
- **`relationship-external-target-freetext` fires whenever `externalTarget` is set.** The fix is a `system` object for the external party plus its listener; the migration helper proposes both.
- **Rendering changes only for relationships with a `targetListener`.** They draw one arrowhead at the listener end; everything else draws as today, so no rendering setting is needed and goldens stay unchanged.
- **The migration helper proposes, never applies.** It writes a report and an optional patch for `git apply` after review; per object, SDP or folder.
- **Example catalog stays legacy.** Its 12 `externalTarget` relationships are baselined, not migrated, and a new example shows the target model.
