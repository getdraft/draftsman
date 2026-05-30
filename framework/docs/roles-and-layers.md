# Roles and Layers

## The Three Roles

DRAFT recognizes three roles. Each role owns a different layer of the catalog
and interacts with the Draftsman differently.

| Role | What they own | How they start |
|---|---|---|
| **Draft Admin** | Workspace configuration — vocabulary lists, RequirementGroups, business taxonomy, governance rules | Run setup mode once to configure the workspace |
| **Technology Admin** | Shared infrastructure — Hosts, RuntimeServices, DataStoreServices, EdgeGatewayServices, TechnologyComponents | Regular Draftsman session; author reusable building blocks |
| **Engineer** | Product content — ProductComponents, DataComponents, SDPs | Regular Draftsman session; describe their service and the Draftsman handles the rest |

Engineers and Technology Admins never use setup mode. They connect their AI
tool to a workspace the Draft Admin has already configured and start a regular
Draftsman session.

## The Three Layers

The catalog is organized in three layers that compose from bottom to top.

```
┌─────────────────────────────────────────────────────┐
│  PRODUCT LAYER  (per product, owned by engineers)   │
│  SDP · ProductComponent · DataComponent             │
│  "What does this specific product deploy?"          │
├─────────────────────────────────────────────────────┤
│  INFRASTRUCTURE LAYER  (shared, owned by tech admins│
│  Host · RuntimeService · DataStoreService           │
│  EdgeGatewayService · TechnologyComponent           │
│  "What platforms and products do we run on?"        │
├─────────────────────────────────────────────────────┤
│  GOVERNANCE LAYER  (workspace-wide, owned by admins)│
│  Capability · RequirementGroup · Domain             │
│  ReferenceArchitecture · Vocabulary                 │
│  "What are our standards and obligations?"          │
└─────────────────────────────────────────────────────┘
```

## Why This Model Scales

Infrastructure objects are authored **once** and referenced by **many**
engineering objects. This is the core reuse mechanism.

A company running fifty microservices on Kubernetes does not create fifty
Hosts or fifty RuntimeServices. They create one EKS Host standard and one
Kubernetes RuntimeService. Each of the fifty ProductComponents references
those shared objects through `runsOn`. Each SDP references the shared
RuntimeService through `substrate`.

The total catalog size for fifty services on a shared platform is roughly:

- 1 Host (EKS cluster standard)
- 1 RuntimeService (Kubernetes deployment)
- 2–4 TechnologyComponents (OS, compute, runtime)
- 1 ReferenceArchitecture (shared deployment pattern)
- 5–10 SDPs (one per distinct deployment pattern, shared across related services)
- 50 ProductComponents (one per service)

Approximately 60–70 objects, not hundreds. The infrastructure layer stays
small because it represents standards, not instances.

## What Each Role Does in Practice

### Draft Admin

Runs setup mode once when the workspace is first created. After that, their
ongoing work is governance maintenance:

- Declaring and updating vocabulary lists
- Activating RequirementGroups for new compliance obligations
- Reviewing vocabulary proposals submitted by engineers
- Maintaining business taxonomy as the company evolves
- Updating capability owner assignments when teams change

### Technology Admin

Authors and maintains the shared infrastructure layer. Their work unlocks
engineering work — engineers cannot reference a Host that does not exist.
Technology Admins typically work ahead of engineering onboarding:

- Authoring Host standards for each compute platform the company uses
- Authoring RuntimeService objects for each deployment pattern
- Authoring DataStoreService objects for each database platform
- Authoring TechnologyComponent objects for vendor products
- Mapping capability owners and approved implementations

When a Technology Admin stubs a new object, engineers can reference it
immediately. The stub becomes `incomplete` and then `complete` as the
Technology Admin adds the required architecture facts.

### Engineer

Authors product content. The Draftsman handles object resolution, reuse
lookup, and YAML authoring. An engineer's session looks like:

1. Describe the service in plain language
2. Answer focused questions about runtime, dependencies, and ownership
3. The Draftsman finds existing infrastructure objects to reference, stubs
   any that are missing, and creates the ProductComponent and SDP
4. Review the pull request the Draftsman opens

Engineers never need to know what a Host or TechnologyComponent is. They
answer "what runs this service?" and the Draftsman resolves the catalog object.

## Implications for AI Agents

When the Draftsman connects to a workspace, it should determine the user's role
from context before asking any questions. Role determines which layer the session
will touch, what questions are appropriate, and what prior catalog content to
search.

An engineer asking "I want to document my service" should never be asked about
capability owners, vocabulary governance, or Host Standards by name. The
Draftsman resolves those from the catalog and only surfaces them if they are
missing and the engineer is the right person to answer.

See [Session Routing](draftsman.md#session-routing) for how the Draftsman
detects workspace state and routes to the correct mode.
