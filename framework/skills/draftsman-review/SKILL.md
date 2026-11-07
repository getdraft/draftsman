---
name: draftsman-review
description: Use when someone asks to review an open pull request that changes catalog files, audit catalog quality, or run a security and compliance audit (requirements, satisfaction, posture, artifact compliance). Needs the Author profile, with read-only use of git hosting tools.
---

# Draftsman Review

Load `draftsman-core` first. This skill needs the **Author profile** because it runs the validator and may fix findings. Review what exists; do not author what is missing unless the user asks. Apply Evidence Discipline: report only what the diff, the validator output or a file you opened shows.

The verbatim procedure for every step below is in `references/steps.md`. Follow that file; the lines here are the map.

## Step 1: Determine scope

Pick a scope from the argument or the request: a PR number or none means PR Review; `security`, `compliance`, `requirements`, `satisfaction` or `artifact` (or a security, GRC or risk role) means Security and Compliance Audit; anything else is a path, object or domain for Catalog Quality Review.

## PR Review

- **Step PR-1, fetch open PRs:** list open pull requests and ask which to review; stop with a clear message if the git host tool is unavailable.
- **Step PR-2, fetch PR details:** read the PR metadata and diff and identify changed catalog and configuration YAML.
- **Step PR-3, validate changed files:** run the validator and keep only errors and warnings that touch changed files.
- **Step PR-4, architecture review:** check ownership, vocabulary compliance, dependency completeness, naming consistency and RequirementGroup coverage.
- **Step PR-5, present findings:** group by severity and file, give the field, the issue and a one-line fix, then an overall assessment.
- **Step PR-6, offer to fix:** if the user agrees, fix under the Draftsman role, validate after each fix, and commit to the PR branch only with confirmation.

## Catalog Quality Review

Review completeness, consistency, clarity and governance of a named scope; the checks and report shape are in the Catalog Quality Review section of `references/steps.md`.

## Security and Compliance Audit

Keep it catalog-grounded: read the vendored framework copy for schemas and rules, and write security content only to company-owned `configurations/` and `catalog/` paths. Never edit `.draft/framework/**` or `.draft/framework.lock`.

- **Workspace boundary:** which paths you may read and write; `.draft/workspace.yaml` changes only when the user explicitly asks to activate or change requirement groups.
- **Bootstrap:** read the listed framework docs and schemas in order, and identify the active RequirementGroups (a group is not active unless the workspace lists it).
- **Requirements authoring:** turn source material (policy text, control lists, provider mappings) into company RequirementGroup YAML with narrow `appliesTo` and concrete satisfaction mechanisms; ask before activating it.
- **Satisfaction design:** for each requirement, resolve the capability, check it has a valid and auditable mechanism, and propose the smallest edits for weak or placeholder evidence.
- **Posture review:** run the validator, then explain each requirement as satisfied, not-applicable, not-compliant, unsatisfied or weakly satisfied, citing names, UIDs, paths and evidence fields.
- **Artifact compliance audit:** resolve one artifact, evaluate its actual evidence against the active groups, and report scope, posture, accepted evidence, gaps, severity and remediation.

## Output rules

Follow the output rules in `references/steps.md` for every scope. In short: use plain governance language, keep uncertainty visible as a gap or assumption, never claim compliance with an external authority (DRAFT records architecture evidence; the authority decides), and validate after any YAML change.

## References

- `references/steps.md`: the full, verbatim step bodies.
