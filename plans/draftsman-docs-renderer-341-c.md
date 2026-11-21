# Draftsman #341 Plan C: listener docs and skills, and listener-aware diagrams and browser

<!-- sdlc-plan-id: draftsman-docs-renderer-341-c -->

## Plan: Draftsman #341 Plan C: listener docs and skills, and listener-aware diagrams and browser

**Goal:** Dale's Draftsman explains, in its docs and in the skills agents load, exactly how to find or create the listener a call lands on without duplicates or guesses. The diagrams and the browser then show those listeners: each call enters the listener it names in the Application view, the Deployment view prints that listener's port, and the browser lists a Listener for every connection and the listeners each component owns.

**Target repo(s):** `getdraft/draftsman`

**Approval:** Dale's standing instruction "I want the backlog cleared", and his 2026-11-20 7:51 PM Phoenix go-ahead: "Write Plan B and build it directly, no approval stop needed." Plan C follows the same direct path. Built outside the agentic SDLC because BeerCanLabs GitHub Actions billing blocks the fleet; draftsman CI is unaffected.

### In scope
- #341 E3: Draftsman docs and skills for the listener model, targetListener and lookup-before-create.
- #341 E5 delta on current main: Application-view attachment points per owned listener, Deployment-view port from the targetListener, and the browser's Listener column and owned-listener list.
- Marking Plans A and B complete in their plan files.

### Out of scope
- #368 flow deprecation, arrowheads and relationship migration; near-match prompting.
- Reconciling listener ports with definition ports; retiring `product_component.interfaces[]`; a derived "what calls this listener" view.
- Hostnames, IPs, security-group rules, certificates, health-check paths; per-environment bindings.

### Acceptance criteria
- The Draftsman docs describe the listener object and the lookup-before-create procedure #341 specifies: resolve the owner, normalize the identity key (owner + protocol + port + endpoint; lowercase protocol, default ports filled in, host dropped, path parameters templated), then link an exact match silently or create a stub listener (catalogStatus: stub) and link it; an ambiguous owner or key is listed and asked, never guessed; a later authored listener upgrades the stub in place; a vendor-owned stub needs a company-internal relationship owner before it leaves stub; the SDP completeness gate blocks calls to internally owned stubs. object-types, how-to-add-objects, draftsman and relationship docs say every relationship names a targetListener. A docs test pins the procedure's key statements and the release note is added.
- The Draftsman skills (draftsman-core, draftsman-author and draftsman-query, plus the draftsman-diagram notes) carry the same lookup-before-create procedure and targetListener rule, point to the draft_table.catalog helpers (lookup_listener, create_listener_stub), and never tell an agent to guess an owner or invent a port. Skill validation, vendored-skill projection and a skills test pass, and the release note is added.
- Application view: a box that owns listener objects gets one attachment point per owned listener on its top edge, in a stable declared order, and a relationship with targetListener attaches to that listener's point. Boxes without listener objects keep today's per-interface entrances. Labels are unchanged and no port is shown. Output for catalogs without listener objects is byte-identical (goldens unchanged); new tests cover order, attachment and determinism.
- Deployment view: a relationship's far-end technology line takes the port of the listener its targetListener names (SQL 5432, gRPC 8092), ahead of today's port resolution; through an exposed group's edge chain the hop ports still precede it (https 443 → http 8080 via <device>), and same-deployment-target traffic never takes the hop. Output for catalogs without listener objects is unchanged; tests cover the listener port, the chain and the fallback.
- Browser: the Connections table gains a Listener column (the targetListener's name with protocol, port and endpoint, or blank), and a component, data component or external system detail page lists the listener objects it owns (protocol, port, endpoint, authenticationModel, catalogStatus). Existing columns stay; generated assets for the bundled examples change only by the new empty column; docs, the diagram skill and the release note are updated, and every check passes.

### Already on main (context, not rework)
- Listener objects, `targetListener`, the ratcheted `relationship-target-listener` rule, stubs, `draft_table.catalog` lookup helpers and the SDP completeness gate (Plan A, #372 and #373).
- Exposure validation and the shared resolver `framework/tools/exposure.py` (Plan B, #400).
- Renderer and browser work for the older interface design (#348-#352): per-interface entrances in both views, port chains and deployment labels, edge device chain drawing and routing (`via <device>`, same-target traffic never hops), the label-overlap fix (AC9 entrance rows), browser exposure and the Interface column.

### Story breakdown
1. **S4.1 Listener docs: lookup-before-create.** Files: `framework/docs/draftsman.md`, `framework/docs/object-types.md`, `framework/docs/how-to-add-objects.md`, `tests/test_listener_docs.py`, `CHANGELOG.md`.
2. **S4.2 Listener skills.** Files: `framework/skills/draftsman-core/`, `framework/skills/draftsman-author/`, `framework/skills/draftsman-query/SKILL.md`, `framework/skills/draftsman-diagram/SKILL.md`, `tests/test_listener_docs.py`, `CHANGELOG.md`.
3. **S5.1 Attachment points per listener.** Files: `framework/tools/generate_diagram.py`, `tests/test_generate_diagram.py`, `CHANGELOG.md`.
4. **S5.2 Deployment port from targetListener.** Files: `framework/tools/generate_diagram.py`, `tests/test_generate_diagram.py`, `CHANGELOG.md`.
5. **S5.3 Browser Listener column and owned listeners.** Files: `framework/tools/generate_browser.py`, browser assets, `tests/test_generate_browser.py`, `framework/docs/software-deployment-patterns.md`, `framework/skills/draftsman-diagram/SKILL.md`, `CHANGELOG.md`.

Stories run in order; each is one squash-merged PR that closes its story issue.

### Decisions made while planning
- **Two epics, matching #341.** E3 (docs and skills) and E5 (renderer and browser) stay separate epics under one plan.
- **Listener order.** Listener objects live in their own files, so "ordered as declared" is made deterministic: an owner's listeners are ordered by port, then protocol, then normalized endpoint, then uid.
- **Fallback.** A target with no listener objects keeps its per-interface entrances and today's port resolution, so existing catalogs render exactly as before.
- **Both views.** Listener attachment points replace interface entrances in both views, as the interface entrances do today; ports still appear only in the Deployment view.
- **Exposure routing and the overlap fix are done.** They shipped in #350 and #351 and need no new story.
