---
description: Review an open PR for catalog correctness, or audit catalog content for quality and security compliance
argument-hint: "[PR number | security | compliance | satisfaction | artifact <name> | <path or object>]"
allowed-tools: [Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion]
---

# /draft review

`/draft review` covers three related scopes — all reviewing what exists rather
than authoring what is missing:

- **PR Review** — validate and assess catalog changes in an open pull request
- **Catalog Quality Review** — completeness, consistency, governance, and
  clarity across catalog content
- **Security & Compliance Audit** — RequirementGroup authoring, satisfaction
  design, posture review, and artifact compliance audit

## Step 1: Determine Scope

Read `$ARGUMENTS`.

- **No argument or `pr`** → PR Review (default). Jump to PR Review below.
- **A number** → treat as a PR number and jump directly to reviewing that PR.
- **`security`, `compliance`, `requirements`, `satisfaction`, `artifact`** (or
  the user has identified as a CISO, security architect, GRC, or risk role) →
  Security & Compliance Audit. Ask which sub-task: `requirements`, `satisfaction`,
  `review`, or `artifact [name]`.
- **Any other argument** → treat as a path, object name, or domain area and
  run a Catalog Quality Review on that scope.

---

## PR Review

Review the catalog changes in an open pull request for schema validity,
architecture correctness, vocabulary compliance, and ownership completeness.

### Step PR-1: Fetch Open PRs

If no PR number was given:

```bash
gh pr list --state open --limit 25 --json number,title,author,createdAt,files
```

If the command fails, report:
> Could not reach GitHub. Make sure `gh` is installed and authenticated
> (`gh auth status`), and that this repository has a GitHub remote.

Stop if the command returns an error. If the list is empty:
> No open pull requests found.

Present the PRs as a numbered table and ask which one to review:

```
  #   PR      Title                                     Author    Age
  ────────────────────────────────────────────────────────────────
  1   #47     add billing-api product component         alice     1d
  2   #45     update postgres standard to 16.x          bob       3d
  ...

Which PR would you like to review? Enter a number.
```

### Step PR-2: Fetch PR Details

```bash
gh pr view <number> --json number,title,body,author,baseRefName,headRefName,files,reviews,reviewRequests
gh pr diff <number>
```

Identify all changed catalog and configuration files (`.yaml` under `catalog/`
or `configurations/`). If no catalog files changed, report:
> PR #N changes no catalog or configuration files — nothing for DRAFT to review.

### Step PR-3: Validate Changed Files

Run the validator scoped to the changed files:

```bash
python3 .draft/framework/tools/validate.py --workspace .
```

Record all errors and warnings that touch the changed files. Do not surface
errors in unrelated files.

### Step PR-4: Architecture Review

Beyond schema validity, assess:

- **Ownership** — does every new or modified object have a resolved `owner.team`
  that exists in the workspace vocabulary?
- **Vocabulary compliance** — do governed fields use declared values? Flag
  non-standard values as proposals to review, not blockers.
- **Dependency completeness** — does the PR introduce references (e.g. `runsOn`,
  `host`, `primaryTechnologyComponent`) that point to catalog objects that do not
  exist yet?
- **Naming and consistency** — do new object names follow the conventions
  already in use across the catalog?
- **RequirementGroup coverage** — are any RequirementGroups now triggered by
  the new objects that the PR does not satisfy?

### Step PR-5: Present Findings

Group findings by severity and file. For each finding, state the field, the
issue, and a one-line fix:

```
catalog/engineering/product-components/billing-api.yaml
  ERROR    runsOn — references unknown UID 01ABC...XYZ
           → add the referenced RuntimeService to the catalog first, or
             correct the UID
  WARNING  owner.team — "payments" is not in the approved teams vocabulary
           → propose "payments" in configurations/vocabulary-proposals/ or
             use an existing approved team
```

End with a brief overall assessment:

> **Overall:** The PR is [ready to merge / needs minor fixes / has blockers].
> [1-2 sentence summary.]

### Step PR-6: Offer to Fix

Ask whether to fix any issues. If yes, follow the Draftsman role in
`.draft/framework/docs/draftsman.md`. Validate after each fix. Commit
fixes to the PR branch if the user confirms.

---

## Catalog Quality Review

Review the company's own catalog content for completeness, consistency,
clarity, and governance.

1. Run validation first: follow `draft-actions/validate.md`.
2. Read the workspace vocabulary lists (`.draft/workspace.yaml`) before judging
   any governed field.
3. Walk the catalog scope — the path, domain, or object named in `$ARGUMENTS`,
   or the full catalog if no scope was given.
4. Report findings grouped by severity (blocker / should-fix / nice-to-have)
   with a concrete fix for each.
5. If a finding is framework-owned rather than company-owned, follow
   **Upstream Framework Feedback Routing** from `draftsman.md`: recommend an
   upstream bug report, ask before creating it, sanitize company details.

Assess:

- **Completeness** — required fields populated, RequirementGroups satisfied,
  ownership and team assignments present
- **Consistency** — naming conventions followed, vocabulary terms drawn from
  declared lists, no contradictory or duplicate objects
- **Clarity** — descriptions are meaningful to a reader who did not author them
- **Governance** — governed fields use approved values; non-standard values are
  flagged for review

---

## Security & Compliance Audit

Security work must stay catalog-grounded. Use the approved vendored framework
copy for schemas, docs, and validation rules. Write company security
RequirementGroups, satisfaction evidence, relationships, DecisionRecords, and
audit follow-up only to company-owned workspace paths.

### Workspace Boundary

- Read `.draft/framework/**` as the approved framework copy.
- Read optional provider packs under `.draft/providers/*/configurations/`.
- Read and write security architecture content under `configurations/` and
  `catalog/`.
- Edit `.draft/workspace.yaml` only when the user explicitly asks to activate
  or change active RequirementGroups.
- Do not edit `.draft/framework/**` or `.draft/framework.lock`.

### Bootstrap

Read in order:

1. `AGENTS.md`
2. `.draft/framework/AI_INDEX.md`
3. `.draft/workspace.yaml`
4. `.draft/framework/docs/draftsman.md`
5. `.draft/framework/docs/security-and-compliance-controls.md`
6. `.draft/framework/docs/requirement-groups.md`
7. `.draft/framework/schemas/requirement-group.schema.yaml`
8. The schema for any artifact type being reviewed or audited

Identify active RequirementGroups from:

```yaml
requirements:
  activeRequirementGroups:
```

A RequirementGroup file is not active unless the workspace lists it there.

### Requirements Authoring

Use when the user wants to create, upload, import, or update security
RequirementGroups.

1. Accept source material from pasted text, uploaded documents, existing
   company policy, provider mappings, or security team instructions.
2. Extract control authority, provider, control IDs, scope, applicability,
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

Valid satisfaction mechanisms: `technologyComponent`,
`technologyComponentConfiguration`, `deploymentConfiguration`, `relationship`,
`internalComponent`, `decisionRecord`, `field`.

`notes` is a placeholder and must not be presented as completed
security evidence.

### Satisfaction Design

Use when requirements exist but the satisfaction model is unclear, weak,
missing, or too broad.

For each requirement:

1. Resolve `relatedCapability` or a capability named in mechanism criteria.
2. Resolve the effective Capability and its owner from workspace overlays.
3. Prefer `preferred` then `existing-only` TechnologyComponent implementations
   as concrete evidence choices.
4. Confirm the requirement has at least one valid mechanism.
5. Check that mechanism criteria are specific enough to be auditable.
6. Identify placeholders or weak evidence and propose the smallest
   RequirementGroup edits needed, then validate.

### Posture Review

Use when the user wants to understand current security posture across active
RequirementGroups.

1. Run the validator first.
2. Load active workspace RequirementGroups and any the user names explicitly.
3. For each in-scope artifact, inspect `requirementGroups` and
   `requirementImplementations`.
4. Explain whether each requirement is satisfied, not-applicable, not-compliant,
   unsatisfied, or weakly satisfied.
5. Cite object names, UIDs, file paths, requirement labels, and evidence fields.
6. Group findings by severity and remediation owner.

Do not present raw validator output. Translate it into plain findings with
concrete evidence and repair steps.

### Artifact Compliance Audit (`artifact [name]`)

Use when the user wants to audit a specific artifact or scoped set of
artifacts.

1. Resolve the artifact by UID, name, type, or path.
2. Read the artifact schema and all applicable active security RequirementGroups.
3. Evaluate actual evidence: direct fields, `requirementImplementations`,
   relationships, referenced TechnologyComponents and configurations,
   deployment configuration, internal components, and DecisionRecords.
4. Report: scope audited, summary posture, evidence accepted, gaps and weak
   evidence, severity (`critical`, `high`, `medium`, `low`), recommended
   remediation, and suggested follow-up artifacts.
5. Validate before finishing if any YAML changed.

---

## Output Rules

- Speak in plain governance terms, not raw YAML, unless the user asks for it.
- Preserve uncertainty as an explicit gap, assumption, or follow-up item.
- Do not claim compliance with an external authority. DRAFT records architecture
  evidence; the authority, auditor, or regulator decides compliance.
- Keep public issue recommendations sanitized and framework-owned.
- After writing any YAML changes, run:

```bash
python3 .draft/framework/tools/validate.py --workspace .
```
