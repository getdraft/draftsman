---
name: draftsman-maturity
description: Use when an agent scaffolds or changes a code repository and must meet DRAFT engineering maturity standards (MATURITY.md, KPF.md, test mapping, DRAFT registration) before opening a pull request. Needs the Author profile.
---

# Draftsman Engineering Maturity

Load `draftsman-core` first. This skill needs the **Author profile**. It applies to any engineering agent that creates or modifies a repository, not only to the Draftsman.

## New repository onboarding

When you bootstrap or scaffold a repository:

1. **Root `MATURITY.md`.** Vendor the DRAFT `MATURITY.md` template into the repository root and declare the target maturity level in section 1 (default: L1 Baseline).
2. **`AGENTS.md` pointer.** Create `AGENTS.md` as the agent bootstrap file, pointing to `MATURITY.md` and `KPF.md`.
3. **`KPF.md`.** Document every user-facing or service-facing capability with a stable ID (for example `KPF-APP-001`), a description, a severity (Sev1 or Sev2) and the automated tests mapped to it.
4. **Register in DRAFT.** Create `.draft/sdp.yaml` declaring the software deployment pattern, and register the repository URL and SDP path in your DRAFT workspace under `catalog/engineering/product-registrations/`.

## Pull request pre-flight

Before you open a pull request or declare a task complete, verify each item and say which you could not verify:

- [ ] `KPF.md` records any new or changed product functionality with its test references.
- [ ] Every touched Sev1 or Sev2 KPF has at least one passing automated test.
- [ ] No gate suppressions were added (`# nosec`, `--no-verify`, `continue-on-error: true`).
- [ ] No hardcoded secrets; credentials come from a secret manager or environment variables.
- [ ] Database schema changes use expand-and-contract so they are backward compatible and decoupled from code deploys.
- [ ] Infrastructure changes are expressed as code (OpenTofu or Terraform modules), with no manual steps.
- [ ] `python3 .draft/framework/tools/validate.py --workspace .` reports 0 errors.

## Requirement group enforcement

Check the work against `requirement-group-engineering-maturity.yaml` in your DRAFT workspace:

- `req-expand-contract-migrations`: backward-compatible schema migrations.
- `req-zero-manual-infrastructure`: infrastructure is fully expressed as code.
- `req-no-gate-suppressions`: no build or lint suppressions.
- `req-synthetic-test-data`: no production personal data or credentials in test fixtures.
- `req-rollback-mechanism`: automated zero-downtime rollback.

If you cannot read that file, say so; do not assume what it requires beyond the five names above.
