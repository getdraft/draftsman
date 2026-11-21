# Draftsman #341 Plan B: exposure through reference-architecture edge slots and service-group overrides

<!-- sdlc-plan-id: draftsman-exposure-341-b -->

## Plan: Draftsman #341 Plan B: exposure through reference-architecture edge slots and service-group overrides

**Goal:** Dale gets one clear, validated answer to which network devices front a service group's incoming traffic. The infrastructure team records it once by filling a reference architecture's edge slots with standard network service definitions; a product team can override it per service group, or turn it off. Bad references are errors instead of silent warnings, and the renderer and browser read exposure from the same resolver. This plan does not redraw diagrams or add browser columns (Plan C).

**Target repo(s):** `getdraft/draftsman`

**Approval:** Dale, 2026-11-20 7:51 PM Phoenix: "Write Plan B and build it directly, no approval stop needed." Built outside the agentic SDLC because BeerCanLabs GitHub Actions billing blocks the fleet; draftsman CI is unaffected.

### In scope
- #341 E4 delta on current main: exposedThrough and fills must name network_service definitions, fills only on edge slots and satisfying the slot capability, enforced as validation errors (not ratcheted).
- One exposure resolver shared by the renderer and browser, with the precedence #341 states, plus docs and the release note.

### Out of scope
- Plan C: E3 docs/skills rewrite and E5 renderer and browser changes (attachment points, port labels, exposure routing, Listener column).
- #368 flow deprecation and relationship migration.
- Hostnames, IPs, security-group rules, certificates, health-check paths; per-environment bindings.

### Acceptance criteria
- Every serviceGroups[].exposedThrough value is none on its own, or a network_service definition uid (serviceRole definition, or an object in the workspace's service definitions folder), or a list of such uids in chain order. A network_service instance, a non-network_service object, an unknown uid, none inside a list, an empty list or a repeated uid fails validation. The rule is not ratcheted: the field is additive. Tests cover each case.
- A reference architecture fills only edge slots (firewall, web-application-firewall, load-balancer, api-gateway, ingress). fills must be a network_service definition uid, and when the slot names a capability the filling definition must satisfy it. Violations fail validation, not ratcheted. Tests cover a clean fill, a non-edge slot, a non-network_service, an instance, an unknown uid and a missing capability, including capability satisfied through a technology component.
- Exposure is resolved in one place: a group with exposedThrough uses it (none switches exposure off; uids give the chain in order); a group without it, in a pattern that follows a reference architecture with filled edge slots, gets the filled chain in edge-slot order; otherwise it is not exposed (a data-tier group is exposed only through exposedThrough). The renderer and browser use that resolver, generated assets are unchanged, docs and release notes describe the contract, and validate, unit tests, generated-asset and release-note checks pass.

### Already on main (context, not rework)
- `fills` on reference-architecture deployable object entries and `serviceGroup.exposedThrough` (string or list, or `none`) in the schemas, from #347 (v1.6.0).
- `validate_exposure_refs` warnings for values that are not network services, fills on non-edge slots and missing capabilities.
- The renderer's chain logic (`_slot_chain`, `_group_chain`) and the browser's `build_group_exposure`, which reads the renderer's model.

### Story breakdown
1. **S3.1 exposedThrough references network_service definitions.** Errors for instances, non-network services, unknown uids, `none` in a list, empty lists and repeated uids. Files: `framework/tools/validate.py`, `framework/schemas/software-deployment-pattern.schema.yaml`, `tests/test_validate_ownership.py`, `CHANGELOG.md`.
2. **S3.2 Filled edge slots are valid definitions that satisfy the slot.** Errors for non-edge slots, non-network services, instances, unknown uids and missing capabilities. Files: `framework/tools/validate.py`, `framework/schemas/reference-architecture.schema.yaml`, `tests/test_validate_ownership.py`, `CHANGELOG.md`.
3. **S3.3 One exposure resolver.** Extract the precedence into `framework/tools/exposure.py`, use it from the renderer and browser with unchanged output, document the contract, and pass every check. Files: `framework/tools/exposure.py`, `framework/tools/generate_diagram.py`, `framework/docs/software-deployment-patterns.md`, `framework/docs/reference-architectures.md`, `tests/test_exposure.py`, `CHANGELOG.md`.

Stories run in order; each is one squash-merged PR that closes its story issue.

### Decisions made while planning
- **Errors, not warnings.** #341 says the rules are "not ratcheted (additive)", so they apply immediately. They become validation failures, not ratcheted rules. The release notes call out the compatibility impact.
- **"Definition".** This uses the existing service-role contract (`serviceRole`, or the workspace's service definitions folder), the same one `relationship-definition-endpoint` uses.
- **Data-tier groups.** The existing renderer rule stays: a group whose deployable objects are all data components is exposed only through `exposedThrough`. #341 is silent on it; it came from the approved prototype.
