# Draftsman #341 Plan A: name every called endpoint and prevent incomplete internal architecture designs

Submitted in https://github.com/BeerCanLabs/bcl-projects/issues/2.

<!-- sdlc-plan-submission v1 -->
<!-- sdlc-plan-id: draftsman-listener-foundation-341-a -->

## Plan: Draftsman #341 Plan A: name every called endpoint and prevent incomplete internal architecture designs

**Goal:** Dale gets a reusable catalog entry for each endpoint that a system calls, instead of an ambiguous line between boxes. Calls identify the exact listener they use; unknown endpoints can be recorded as stubs without duplicates. Draftsman then prevents an internal deployment design from being marked complete while those details are still missing, and requires an explicit recorded decision when a listener has no authentication. This delivers the data model, authoring/lookup behavior and tested validation gates, not the updated diagrams or browser (Plan C) or exposure configuration (Plan B).

**Target repo(s):** `getdraft/draftsman`

### In scope
- Current #341 E1: first-class listener schema/object type, ownership, normalized identity key, enums, targetListener, runtime dependency listener references, ratcheted relationship-target-listener rule, technology/protocol warning, stubs and lookup-before-create.
- Current #341 E2: listener protection requirements, conditional DecisionRecord justification for authenticationModel none, and ratcheted SDP completeness gate.
- Automated regression tests and minimal authoring/help text needed for these capabilities, migration/baseline instructions for the changed rules, and the normal governed-change release note. Full Draftsman docs/skills rewrite is Plan C.

### Out of scope
- Plan B: E4 exposure/edge-slot fills, exposedThrough and related rules.
- Plan C: E3 full docs/skills rewrite plus E5 renderer and browser changes. Existing merged targetInterface/listeners-on-definition work is context, not the current requested listener model.
- #368 legacy flow deprecation, relationship/arrow migration and near-match prompting.
- Hostnames, IPs, security-group rules, environment endpoints, certificates and health-check paths; retiring product_component.interfaces; reconciling listener ports with definition ports; derived caller view.
- Automatic deployment, budget approval, or broad catalog migration. Stop at a costed, reviewed budget hold before coding.

### Acceptance criteria
- A listener is a first-class UID-addressable object owned by a component, data component or external system, with protocol, port, endpoint, authenticationModel, optional methods, description and catalogStatus (stub, incomplete, complete); validation tests cover valid and invalid fields/owners.
- Identity is owner + protocol + port + endpoint, normalized as #341 specifies (default ports and templated path parameters; lowercase host input but do not persist host). Planning explicitly resolves how host normalization is handled when host is not stored; distinct owners never collapse.
- The plan settles and documents the protocol enum extension (including SQL, Redis, Kafka, SQS, SNS, S3 and gRPC-web as needed); authenticationModel accepts none.
- Every relationship must reference a real listener via targetListener, including data/external targets; missing or invalid references fail the ratcheted relationship-target-listener rule on changed content. runtimeSpec.dependencies[].interface can resolve the same listener UID. Protocol/technology disagreement warns, not ratchets.
- Lookup-before-create resolves the owner and normalized exact key: existing listener is linked, missing listener creates and links a stub, and a later authored listener upgrades that stub without a duplicate UID. Ambiguous owners are returned for human choice, never guessed. A vendor-owned stub cannot leave stub without a company-internal relationship owner.
- Legacy product_component.interfaces remains; existing relationships stay green after validate.py --write-baseline until next changed. Tests cover baseline preservation, changed relationships, both internal/external targets, normalization, duplicate prevention and stub upgrade.
- Mandatory interface-protection applies to listeners and is satisfied by authenticationModel: TBD does not satisfy it, none does.
- Conditional interface-unprotected-justification uses existing applicability on the listener authenticationModel equals none; only a committed DecisionRecord satisfies it and naAllowed is false. Tests reject missing, draft and N/A justifications and accept a committed decision.
- The SDP completeness gate names and blocks any internally owned stub listener called by that pattern. External-vendor stubs do not block completion. Tests cover dependency traversal, several calls and mixed internal/external ownership.
- The gate is ratcheted when the SDP or its dependent objects change; a framework upgrade alone does not retroactively fail unchanged content. Tests distinguish unchanged baseline from changed SDP/dependencies.
- Upstream defines the mechanism, not which unauthenticated exceptions a company accepts; exception policy remains in company requirement groups. validate, unit tests, generated-asset checks and release-note checks pass on the final changes.

### Details
Source of truth: https://github.com/getdraft/draftsman/issues/341 (current body, rewritten 2026-11-18). This is Plan A of Dale's approved three-plan split: A = E1 + E2, B = E4, C = E3 + E5 after the foundations.

What Dale gets: a trustworthy, reusable catalog of the endpoints his systems call, plus a check that stops an incomplete internal design from claiming it is complete. He can capture an unknown external endpoint now and finish it later without duplicate objects; internal unknowns must be resolved before completion. Unauthenticated endpoints require a recorded decision, not a silent default. This plan alone does not redraw the diagrams or add the Listener browser column.

Planning must inspect current main: PR #366 already shipped the older targetInterface/interfaces/definition-listeners model. #341's rewritten listener-object contract supersedes that proposal. Identify compatibility and migration decisions rather than assuming #366 implements E1/E2.

Produce a concrete story breakdown, acceptance evidence, dependencies and a cost/risk estimate. The hold must explain these deliverables in plain language with expected/P90 cost and a cap; nobody has approved spending. Stop at that hold. Do not submit any of Plans B or C from this intake.

Deploy handling is conservative: the config names existing deploy-pages.yml with requires_approval true; merge already triggers releases/Pages. There is no separate deploy pin to update. Ops must not invent one.

### Plan file (fleet plan format, status draft)
```json
{
  "id": "draftsman-listener-foundation-341-a",
  "title": "Draftsman #341 Plan A: name every called endpoint and prevent incomplete internal architecture designs",
  "status": "draft",
  "outcome": "Dale gets a reusable catalog entry for each endpoint that a system calls, instead of an ambiguous line between boxes. Calls identify the exact listener they use; unknown endpoints can be recorded as stubs without duplicates. Draftsman then prevents an internal deployment design from being marked complete while those details are still missing, and requires an explicit recorded decision when a listener has no authentication. This delivers the data model, authoring/lookup behavior and tested validation gates, not the updated diagrams or browser (Plan C) or exposure configuration (Plan B).",
  "target_repo": "getdraft/draftsman",
  "epics": [
    {
      "id": "E1",
      "title": "Listener catalog, exact targets, normalized lookup and stubs",
      "acceptance_criteria": [
        "A listener is a first-class UID-addressable object owned by a component, data component or external system, with protocol, port, endpoint, authenticationModel, optional methods, description and catalogStatus (stub, incomplete, complete); validation tests cover valid and invalid fields/owners.",
        "Identity is owner + protocol + port + endpoint, normalized as #341 specifies (default ports and templated path parameters; lowercase host input but do not persist host). Planning explicitly resolves how host normalization is handled when host is not stored; distinct owners never collapse.",
        "The plan settles and documents the protocol enum extension (including SQL, Redis, Kafka, SQS, SNS, S3 and gRPC-web as needed); authenticationModel accepts none.",
        "Every relationship must reference a real listener via targetListener, including data/external targets; missing or invalid references fail the ratcheted relationship-target-listener rule on changed content. runtimeSpec.dependencies[].interface can resolve the same listener UID. Protocol/technology disagreement warns, not ratchets.",
        "Lookup-before-create resolves the owner and normalized exact key: existing listener is linked, missing listener creates and links a stub, and a later authored listener upgrades that stub without a duplicate UID. Ambiguous owners are returned for human choice, never guessed. A vendor-owned stub cannot leave stub without a company-internal relationship owner.",
        "Legacy product_component.interfaces remains; existing relationships stay green after validate.py --write-baseline until next changed. Tests cover baseline preservation, changed relationships, both internal/external targets, normalization, duplicate prevention and stub upgrade."
      ],
      "deploy_point": false
    },
    {
      "id": "E2",
      "title": "Explicit listener protection and honest deployment-pattern completeness",
      "acceptance_criteria": [
        "Mandatory interface-protection applies to listeners and is satisfied by authenticationModel: TBD does not satisfy it, none does.",
        "Conditional interface-unprotected-justification uses existing applicability on the listener authenticationModel equals none; only a committed DecisionRecord satisfies it and naAllowed is false. Tests reject missing, draft and N/A justifications and accept a committed decision.",
        "The SDP completeness gate names and blocks any internally owned stub listener called by that pattern. External-vendor stubs do not block completion. Tests cover dependency traversal, several calls and mixed internal/external ownership.",
        "The gate is ratcheted when the SDP or its dependent objects change; a framework upgrade alone does not retroactively fail unchanged content. Tests distinguish unchanged baseline from changed SDP/dependencies.",
        "Upstream defines the mechanism, not which unauthenticated exceptions a company accepts; exception policy remains in company requirement groups. validate, unit tests, generated-asset checks and release-note checks pass on the final changes."
      ],
      "deploy_point": false
    }
  ],
  "risks": [
    "#341 was rewritten Nov 18 to supersede the earlier targetInterface proposal; main already contains #366 (v1.6.0) for that older design. Inspect current main and plan only the delta; do not rebuild already merged exposure/renderer work or silently retain the obsolete targetInterface contract.",
    "The current ops adapter assumes a separate pin repo. Draftsman releases on merge to its own main via Promote Release and Deploy to GitHub Pages; deployment remains human-gated and is not a budget approval.",
    "The owner/normalized-key and internal/external classification contracts must be explicit before story breakdown. Missing product decisions are questions, not permission to guess."
  ]
}
```

_Submitted to the SDLC conductor. It runs the plan gate, then the budget approval, then breaks the plan into stories._
<!-- /sdlc-plan-submission -->
