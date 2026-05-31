# SDP Completion Interview

## Purpose

The SDP Completion Interview is a structured protocol for enriching an existing
SoftwareDeploymentPattern that passes schema validation but is architecturally
incomplete — missing deployable objects, connections, external interactions,
data-flow decisions, or tier-variant details.

Use this protocol when a user asks to "complete an SDP", "fill in the gaps", or
"review an existing SDP for completeness."

## When To Use This Protocol

Run the SDP Completion Interview when the target SDP passes `validate.py` but
scores below the completeness rubric threshold described in Phase 0. Common
incomplete conditions:

- No `serviceGroups` or service groups with no `deployableObjects`
- `deployableObjects` entries with no `diagramTier`
- No relationship objects with this SDP's deployed objects as source
- No `architectureNotes.dataClassification` or availability declaration
- No `architectureNotes.failureDomain`
- No `tierVariants` when environment tiers are declared in the workspace
- Service groups with unresolved placeholder deployment targets such as `owner-interview-required` or `drafting-interview-required`

Do not run this protocol for a net-new SDP with no content yet — use the
standard Draftsman SDP session from `draftsman.md` instead.

## Completeness Rubric

Score the SDP on ten dimensions before beginning the interview. Report the
score and gap list to the user before asking any questions.

| Dimension | ID | Complete when |
|---|---|---|
| Service groups | SG | At least one `serviceGroup` with a name and `deploymentTarget` |
| Deployable objects | DO | Every service group has at least one entry with a resolved catalog `ref` and `diagramTier` |
| Network zones | NZ | `networkZones` declared, or an explicit architectural decision that no zone segmentation applies |
| Connections | CN | At least one relationship object where both source and target are deployed in this SDP, or an explicit architectural decision that no cross-service connections exist |
| External interactions | EI | At least one relationship object where source is deployed in this SDP and target is external or in a different catalog object |
| Data classification | DC | `architectureNotes.dataClassification` present |
| Availability | AV | `architectureNotes.availability` present |
| Failure domain | FD | `architectureNotes.failureDomain` present |
| Deployment targets resolved | DT | No `deploymentTarget` entries contain placeholder values such as `owner-interview-required` |
| Requirement implementations | RA | `requirementImplementations` list present and non-empty for all active workspace RequirementGroups the SDP claims |

Dimensions SG through DT use a binary score: 0 (missing or placeholder) or
1 (present and resolved). Dimension RA uses a binary score: 0 if the SDP
claims `requirementGroups` but has no `requirementImplementations`, 1 if all
claimed groups have at least one implementation entry.

A score of 10/10 is the completion target. Present the score as:

> **[SDP name] — Completeness: 6/10**
>
> Gaps: CN (no connections declared), EI (no external interactions), DC (no
> data classification), FD (no failure domain)
>
> I'll work through each gap with you. We can skip any item and record it in
> the DraftingSession instead.

## Phase 0 — Intake

Before asking any question, do the following:

1. Read the full SDP YAML, including all nested `serviceGroups`,
   `deployableObjects`, and `architectureNotes`.
2. Score all ten dimensions.
3. List the gaps.
4. Read `.draft/workspace.yaml` and `configurations/vocabulary/` for approved
   deployment targets, network zones, team names, data classifications, failure
   domains, and connection protocols.
5. Read the environment-tier objects in `configurations/environment-tiers/` if
   they exist.
6. Present the score and gap list to the user.
7. Ask whether to proceed in order or focus on a specific gap first.

Do not ask for any architecture facts in Phase 0. The only output is the rubric
report and the navigation question.

## Phase 1 — Service Groups and Deployable Objects (gap: SG or DO)

Run this phase if the SG or DO dimension scored 0.

### Step 1.1 — Confirm service group structure

Read the existing `serviceGroups` block. If service groups are already named,
present them and ask the user to confirm they are still accurate before
continuing. If no service groups exist, ask:

> What are the major deployment groups in [SDP name]? For example: "API
> cluster", "batch workers", "admin UI", "data tier". You can name one group
> to start.

Capture each group name and ask whether there are others before moving on.

### Step 1.2 — Deployable objects per group

For each service group with missing `deployableObjects`, present the group name
and ask:

> What runs inside [group name]? I'll look up catalog options — just give me
> the component or service name and I'll match it.

Search the catalog for matching ProductComponents, RuntimeServices,
DataStoreServices, and NetworkServices. Present the top matches as
a numbered list. If an exact match exists, confirm it. If multiple plausible
matches exist, ask the user to choose.

For each resolved catalog object:

1. Set `diagramTier` based on the object type:
   - ProductComponent → infer from component role (API = application, UI =
     presentation, worker = application)
   - DataStoreService → data
   - NetworkService → presentation or utility
   - RuntimeService → utility
   - Ask the user to confirm or correct the inferred tier.
2. If the catalog object has no entry yet, note that you will draft it and
   continue.

### Step 1.3 — Deployment targets for new service groups

For each service group that has no `deploymentTarget` or has a placeholder
value, read the workspace vocabulary for deployment targets. Present the
approved choices as a numbered list. If the workspace has declared environment
tiers with `parameterSurface` entries, note that the target should match an
approved tier's execution context.

Do not invent a region or account value. If the user cannot name the target
today, record `owner-interview-required` as a temporary placeholder and note
it as an open DraftingSession item.

## Phase 2 — External Interactions (gap: EI)

Run this phase if the EI dimension scored 0, or if new service groups were
added in Phase 1 that may have their own external dependencies.

### Step 2.1 — Platform dependencies

Ask one question per platform category. Present each as a yes/no:

> Does [SDP name] send logs to a centralized logging platform? (yes / no)
>
> Does it report application metrics or traces to a monitoring or APM
> platform? (yes / no)
>
> Does it authenticate users or service tokens through an identity platform
> such as Okta, Azure AD, or a custom IdP? (yes / no)
>
> Does it call any shared internal platform — for example a message bus,
> secrets manager, or feature-flag service? (yes / no)

For each **yes**, search the catalog for the deployable object that represents
that platform (RuntimeService, DataStoreService, or NetworkService
with a matching `deliveryModel`). If found, create a relationship object with
`source` set to the dependent service and `target` set to the platform UID.
If not found and the user can name the platform, draft the appropriate service
object first, then create the relationship.

Record each confirmed external dependency as a relationship object in the catalog.

### Step 2.2 — Third-party APIs and data feeds

Ask:

> Does [SDP name] call any third-party APIs or receive data feeds from outside
> your organization? For example: payment processors, geolocation services,
> SMS/email gateways, state agency data feeds. (yes / no)

For each **yes**, ask the user to name the vendor or service. Check whether a
TechnologyComponent or NetworkService already models it. If yes, create
a relationship object with `source` set to the calling service and `target` set
to the catalog UID. If not, create a relationship object using `externalTarget`
with the vendor name, and note that a catalog object should be created later.

Stop after three external dependency questions per round. If more may exist,
record in the DraftingSession that external-dependency elicitation is
incomplete.

## Phase 3 — Network Zones and Connections (gaps: NZ and CN)

Run the **Network Zone and Connection Elicitation** procedure from
`draftsman.md` verbatim for the NZ and CN gaps. That procedure is the
authoritative source; do not redefine it here.

Before running the procedure, check whether `networkZones` is already declared
on the SDP. If zones are already present and the CN dimension is the only gap,
skip Phase 1 and Phase 2 of the elicitation procedure and go directly to
Phase 3 (connection elicitation) of that procedure.

If both NZ and CN scored 0, run the full elicitation from Phase 1.

Record the same-tier connection deferral note in the DraftingSession
regardless of whether connections were fully elicited.

## Phase 4 — Architectural Decisions (gaps: DC, AV, FD)

Run this phase if any of DC, AV, or FD scored 0.

### Step 4.1 — Data classification (gap: DC)

Read the workspace `configurations/vocabulary/` for declared data
classification values. Present the approved values:

> What is the highest data classification that [SDP name] stores or
> processes?
>
> [list approved classification values]

If the user's answer is not in the approved list, call it non-standard and ask
whether to submit a vocabulary proposal or use a temporary label. Record the
answer in `architectureNotes.dataClassification`.

If the SDP processes personally identifiable information (PII), confirm whether
any `data_component` objects are modeled for those data stores.

### Step 4.2 — Availability requirement (gap: AV)

Read the workspace `configurations/vocabulary/` for declared availability
values. If environment tiers are declared and the SDP already lists tier
variants, infer the availability requirement from the highest-tier
`availabilityExpectation`. Confirm rather than ask from scratch:

> Based on the Production tier, I'd set availability to
> [tier availabilityExpectation value]. Is that accurate, or does this product
> have a different stated SLA?

Record the answer in `architectureNotes.availability`.

### Step 4.3 — Failure domain (gap: FD)

Ask:

> What is the failure domain for [SDP name]? This is the blast-radius
> boundary — for example, a single AWS region, a single Kubernetes cluster,
> a single customer tenant, or a single availability zone.

Present workspace vocabulary choices if declared. If no list exists, accept a
plain-language answer and record it in
`architectureNotes.failureDomain`.

## Phase 5 — Tier Variants (gap: DT or per-tier architectural deltas)

Run this phase if:

- The workspace declares environment tiers in
  `configurations/environment-tiers/`
- AND the SDP has no `tierVariants` block, OR has tier variants with
  placeholder deployment targets

For each declared environment tier, ask:

> For [tier name] (e.g. Production), what is the deployment target — the AWS
> account, cluster, or execution context this service group lands in?

Present the tier's `parameterSurface` as context so the user knows what values
are expected. Do not ask for the raw parameter values; ask only for the
architectural deployment target label.

For each tier with a known scale difference from the default, ask one question:

> In [tier name], does [service group] run with a different replica count or
> autoscaling configuration than the default?
>
> A) Same as default
> B) Different — I'll tell you the range

If the user chooses B, capture `min` and `max` replica counts and set
`autoscaling.enabled: true`. Record the values in the tier variant's
`serviceGroupVariants`.

Stop after two tier-variant questions per phase turn. Continue remaining tiers
in the next exchange or DraftingSession.

## Phase 6 — Requirement Implementations (gap: RA)

Run this phase if the SDP claims `requirementGroups` but the RA dimension
scored 0.

For each claimed RequirementGroup, follow the **Requirement And Capability
Lookup** procedure from `draftsman.md`. Do not re-derive implementation
evidence you already collected in earlier phases of this interview — map
what was gathered to `requirementImplementations` entries first.

Ask follow-up questions only for obligations that no earlier phase covered.
Keep questions catalog-grounded: cite the requirement label and present
approved capability implementations as choices.

Record any requirement that cannot be closed today as `not-applicable` with a
rationale, or leave it open in the DraftingSession.

## Phase 7 — Session Close

After all targeted phases are complete:

1. Re-score the SDP against the completeness rubric.
2. Report the updated score.
3. List any items still open.
4. Write or update the DraftingSession object for this SDP:
   - record all open items as questions with `status: open`
   - record all deferred elicitation areas (same-tier connections,
     incomplete external-interaction review, unresolved deployment targets)
   - record the updated rubric score and date as a session note
5. Tell the user the next steps: what can be addressed in the next
   session, and what requires input from another team or system.

Do not ask the user to confirm every YAML field. Write the YAML behind the
scenes and present a plain-language summary of what changed.

## Sequencing Rules

- Run phases in the order listed (0 → 1 → 2 → 3 → 4 → 5 → 6 → 7) by
  default.
- Skip any phase whose dimensions all scored 1 at intake.
- If the user asks to focus on a specific gap, jump to that phase and return
  to sequence after it completes.
- Never run more than three focused questions per conversational turn.
  Offer to continue in the next turn or defer to the DraftingSession.
- Never ask for port numbers, raw UIDs, YAML keys, or internal framework
  terminology. Translate everything into plain deployment language.
- Preserve unresolved items in the DraftingSession rather than forcing the
  user to answer everything in one session.
