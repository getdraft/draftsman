---
description: Scoped, question-driven audit of company catalog content — general catalog review or security/compliance RequirementGroup audit
argument-hint: "[object, domain, or area] | requirements | satisfaction | review | artifact [name]"
allowed-tools: [Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion]
---

# /draft audit

You are running the Draftsman audit workflow for a **company workspace**.
`/draft audit` covers two related but distinct scopes:

- **General Catalog Review** — completeness, consistency, clarity, and
  governance across the company's own catalog content.
- **Security & Compliance Audit** — security RequirementGroup authoring,
  satisfaction design, posture review, and artifact compliance audit, for
  CISOs, security architects, security engineering leads, compliance/GRC
  owners, and risk owners delegated by Draft Admins.

Both scopes review the company's own catalog content, not the DRAFT framework
itself. (To review the framework, use `/draft review-framework`, an
upstream-only verb.)

## Step 1: Determine Scope

Read `$ARGUMENTS`.

- No arguments: ask which audit is wanted — a general catalog review, or a
  security/compliance audit — and offer at most three focused choices.
- If the argument names a security or compliance term (`security`,
  `compliance`, `requirement`, `control`, `GRC`, or `audit <artifact>`), or the
  user has identified as a CISO, security, compliance, or risk role, route to
  **Security & Compliance Audit** below and ask which sub-task: `requirements`,
  `satisfaction`, `review`, or `artifact [name]`.
- Otherwise, treat the argument as the object, domain, or area to review under
  **General Catalog Review**.

## General Catalog Review

Review the catalog content authored in this workspace for:

- **Completeness** — required fields populated, RequirementGroups satisfied,
  ownership and team assignments present.
- **Consistency** — naming conventions followed, vocabulary terms drawn from
  the workspace's declared lists, no contradictory or duplicate objects.
- **Clarity** — descriptions are meaningful to a reader who did not author
  them.
- **Governance** — governed fields use approved values; non-standard values
  are flagged for review rather than silently accepted.

Procedure:

1. Run validation first so structural problems surface before content
   judgement: follow the `validate` action (`draft-actions/validate.md`).
2. Read the workspace vocabulary lists (`.draft/workspace.yaml`) before judging
   any governed field. Treat answers outside approved choices as non-standard
   values that can be revisited or proposed for review.
3. Walk the catalog object by object, reporting findings grouped by severity
   (blocker / should-fix / nice-to-have) with a concrete fix for each.
4. Where a finding warrants tracked follow-up, note that it can be routed to a
   GitHub issue. The exact issue-creation workflow is defined in issue #51
   (shared Draft issue creation) and is not yet implemented — until then, list
   the findings for the user to act on.
5. If a finding is framework-owned rather than company-owned — for example a
   missing reusable RequirementGroup pattern, schema gap, unclear command
   behavior, or validator defect — follow **Upstream Framework Feedback
   Routing** from the Draftsman role. Recommend a public upstream bug report or
   feature request, ask before creating it, and sanitize company details.

## Security & Compliance Audit

Security work must stay catalog-grounded. Use the approved vendored framework
copy for schemas, docs, and validation rules, then write company security
RequirementGroups, satisfaction evidence, relationships, DecisionRecords, and
audit follow-up only to company-owned workspace paths.

### Workspace Boundary

In a company workspace:

- Read `.draft/framework/**` as the approved framework copy.
- Read optional provider packs under `.draft/providers/*/configurations/`.
- Read and write normal security architecture content under `configurations/`
  and `catalog/`.
- Edit `.draft/workspace.yaml` only when the user explicitly asks to activate
  or change active RequirementGroups.
- Do not edit `.draft/framework/**` or `.draft/framework.lock` during normal
  security review or authoring.

If the selected repository is the upstream DRAFT framework repository and the
user is asking for company security content, ask for the company-specific
DRAFT repo path before authoring that content. The upstream repo is only for
reusable framework changes, starter RequirementGroups, schemas, docs, tools,
and templates.

If security work reveals a reusable framework bug, missing framework pattern,
schema gap, unclear command behavior, or validation defect, follow **Upstream
Framework Feedback Routing** in `draftsman.md`: recommend an upstream public
bug report or feature request, ask before creating it, use the correct issue
template, and sanitize company details.

### Bootstrap

Read these files in order, resolving paths from the current workspace:

1. `AGENTS.md`
2. `.draft/framework/AI_INDEX.md`
3. `.draft/workspace.yaml`
4. `.draft/framework/docs/draftsman.md`
5. `.draft/framework/docs/security-and-compliance-controls.md`
6. `.draft/framework/docs/requirement-groups.md`
7. `.draft/framework/schemas/requirement-group.schema.yaml`
8. Any schema for the artifact type being reviewed or audited

Resolve the effective model in this order:

1. `.draft/framework/configurations/`
2. `.draft/providers/*/configurations/`
3. `configurations/`
4. `catalog/`

Identify active workspace RequirementGroups from:

```yaml
requirements:
  activeRequirementGroups:
```

Remember: a RequirementGroup YAML file is not active unless the workspace
lists it there.

### Requirements Authoring

Use this mode when the user wants to create, upload, import, or update
security RequirementGroups.

1. Accept source material from pasted text, uploaded documents, existing
   company policy, provider mappings, or security team instructions.
2. Extract the control authority, provider, control IDs, scope, applicability,
   evidence expectations, and expected dispositions.
3. Search existing RequirementGroups before creating a new one.
4. Create or update company-owned RequirementGroup YAML under
   `configurations/requirement-groups/`.
5. Use `activation: workspace` for company security and compliance controls.
6. Set `appliesTo` narrowly enough that the validator and Draftsman ask the
   right artifacts for evidence.
7. Define concrete `canBeSatisfiedBy` mechanisms for each requirement.
8. Ask before activating the group in `.draft/workspace.yaml`.
9. Validate after any YAML changes.

Valid satisfaction mechanisms are:

- `technologyComponent`
- `technologyComponentConfiguration`
- `deploymentConfiguration`
- `relationship`
- `internalComponent`
- `decisionRecord`
- `field`

`architectureNotes` may preserve rationale or temporary context, but it is a
placeholder and must not be presented as completed security evidence.

### Satisfaction Design

Use this mode when requirements exist but the satisfaction model is unclear,
weak, missing, or too broad.

For each requirement:

1. Resolve `relatedCapability`, or a capability named in mechanism criteria.
2. Resolve the effective Capability and its owner from workspace overlays
   first.
3. Prefer `preferred` and then `existing-only` TechnologyComponent
   implementations as concrete evidence choices.
4. Confirm the requirement has at least one valid mechanism from the supported
   list.
5. Check that mechanism criteria are specific enough to be auditable.
6. Identify placeholders or weak evidence:
   - generic fields with no exact expected key or value
   - `architectureNotes` used as evidence
   - relationship mechanisms with no target class or capability criteria
   - DecisionRecords with no referenceable decision key, control, or
     capability
   - not-applicable dispositions with no rationale when rationale is required
7. Propose the smallest RequirementGroup edits needed, then validate.

### Requirement Satisfaction Review

Use this mode when the user wants to understand current security posture
across RequirementGroups and requirements.

1. Run the validator first by following `draft-actions/validate.md`.
2. Load active workspace RequirementGroups and any security RequirementGroups
   the user names explicitly.
3. For each in-scope artifact, inspect `requirementGroups` and
   `requirementImplementations`.
4. Explain whether each requirement is:
   - satisfied with concrete evidence
   - not-applicable with a valid rationale
   - not-compliant and visible as a known gap
   - unsatisfied or incorrectly satisfied
   - weakly satisfied and needing better evidence
5. Cite object names, UIDs, file paths, requirement labels, and evidence
   fields.
6. Group findings by severity and remediation owner when the owner can be
   resolved from catalog metadata.

Do not present raw validator output. Translate it into CISO-friendly findings
with concrete evidence and repair steps.

### Artifact Compliance Audit (`artifact [name]`)

Use this mode when the user wants to audit a selected artifact or scoped set
of artifacts.

1. Resolve the artifact by UID, name, type, or path. If ambiguous, ask a
   focused clarification.
2. Read the artifact schema and all applicable active security
   RequirementGroups.
3. Determine applicability from `appliesTo`, artifact type, delivery model,
   and any requirement-specific criteria.
4. Evaluate actual evidence on the artifact and related objects:
   - direct fields
   - `requirementImplementations`
   - relationships
   - referenced TechnologyComponents and configurations
   - deployment configuration
   - internal components
   - DecisionRecords
5. Report:
   - scope audited
   - summary posture
   - evidence accepted
   - gaps and weak evidence
   - severity (`critical`, `high`, `medium`, `low`)
   - recommended remediation
   - suggested follow-up artifacts, such as DecisionRecords, GitHub issues, or
     DraftingSession items
6. Validate before finishing if any YAML changed.

## Output Rules

- Speak in plain governance terms, not raw YAML, unless the user asks for the
  YAML.
- Preserve uncertainty as an explicit gap, assumption, or follow-up item.
- Do not claim compliance with an external authority. DRAFT records
  architecture evidence; the authority, auditor, regulator, or company control
  owner decides compliance.
- Keep public issue recommendations sanitized and framework-owned.
- When writing changes, run:

```bash
python3 .draft/framework/tools/validate.py --workspace .
```

If working in the upstream framework repository for framework maintenance,
run:

```bash
python3 framework/tools/validate.py
```
