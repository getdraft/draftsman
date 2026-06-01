# Draft Operations and Governance Guide

> **Audience:** Draft Admins, Shared Services, and Engineering Representatives.
> This guide defines the governance, ticketing, team ownership, and review workflows for a DRAFT workspace.
> It establishes the authoritative team registry model, team routing semantics, and programmatic CODEOWNERS generation.

DRAFT workspaces are Git-native and governed by code review. To ensure that every architectural decision and catalog object is maintained by the correct people, DRAFT implements an **authoritative team registry** and **automated CODEOWNERS generation**.

---

## 1. The Authoritative Team Registry

A company's team registry is governed as a vocabulary list (`vocabulary.teams`) inside the workspace metadata. It acts as the single source of truth for all team definitions, team handles, and path ownership. 

Rather than maintaining separate lists of teams for Slack, Jira, GitHub CODEOWNERS, and catalog `owner.team` fields, everything is mapped here.

### Schema Specification

The team registry lives in `.draft/workspace.yaml` (or configuration vocabulary overlays under `configurations/vocabulary/`):

```yaml
vocabulary:
  teams:
    mode: gated
    values:
      - id: database-services
        name: Database Services
        status: approved
        contact: database-services@example.com
        githubTeam: "@my-org/database-services"
        draftRoles:
          - shared-services
        codeowners:
          paths:
            - catalog/shared-services/data-store-services/
```

### Team Fields:

* `id` — **Required.** Stable, lowercase, hyphen-separated key used by `owner.team` fields.
* `name` — **Required.** Human-readable display name.
* `status` — **Required.** Maturity status: `approved` or `proposed`.
* `contact` — **Required.** Fallback human contact (email address, Slack link, or distribution list).
* `githubTeam` — **Required.** Exact GitHub team handle. **Must include the `@org/` prefix** (e.g. `@my-org/database-services`).
* `draftRoles` — **Required.** List of DRAFT roles this team is active under. Valid roles are: `engineering`, `shared-services`, `draft-admins`.
* `codeowners.paths` — **Optional.** Specialized catalog paths this team explicitly owns for CODEOWNERS generation.

---

## 2. Programmatic Ownership Resolution

Catalog artifacts declare their owner team using a structured `owner` block:

```yaml
owner:
  team: database-services
```

When validating, triaging, or creating GitHub issues, the Draftsman resolves ownership programmatically:

```text
artifact owner.team
-> vocabulary.teams[owner.team]
-> vocabulary.teams[owner.team].githubTeam
-> GitHub team mention and generated CODEOWNERS entry
```

This ensures there is never a conflict between who owns a file in the catalog and who is assigned the GitHub issue or CODEOWNERS review request. Both are derived directly from the team registry.

---

## 3. Automated CODEOWNERS Generation

To maintain Git-native governance, the DRAFT workspace CODEOWNERS file is programmatically generated from the team registry and artifact ownership. It should not be modified manually.

### The Generation Model

CODEOWNERS generation follows a two-tier strategy:

1. **Broad Role/Folder Fallbacks:** Establishes catch-all owners for major folders. This protects new or unmapped files during a pull request, as GitHub evaluates CODEOWNERS from the base branch (where per-file rules for a new file do not exist yet).
2. **Per-File Artifact Ownership:** Generates precise per-file rules for existing artifacts based on their resolved `owner.team`. This is the steady-state governance mechanism.

### Default Path Conventions:

* **draft-admins** (Governance files):
  - `.draft/`
  - `.github/`
  - `configurations/`
* **shared-services** (Infrastructure standards):
  - `catalog/shared-services/hosts/`
  - `catalog/shared-services/runtime-services/`
  - `catalog/shared-services/data-store-services/`
  - `catalog/shared-services/network-services/`
  - `catalog/shared-services/technology-components/`
* **engineering** (Product boundaries):
  - `catalog/engineering/product-components/`
  - `catalog/engineering/data-components/`
  - `catalog/engineering/software-deployment-patterns/`

### Example Generated CODEOWNERS Output:

```text
# ==============================================================================
# GENERATED FILE — DO NOT EDIT MANUALLY
# Rebuild with: python3 .draft/framework/tools/generate_codeowners.py
# ==============================================================================

# Broad Role/Folder Fallbacks
.draft/                      @my-org/draft-admins
.github/                     @my-org/draft-admins
configurations/              @my-org/draft-admins
catalog/shared-services/     @my-org/shared-services-review
catalog/engineering/         @my-org/engineering-architecture-review

# Per-File Catalog Artifact Ownership
catalog/shared-services/data-store-services/postgres-standard.yaml @my-org/database-services
catalog/shared-services/network-services/waf-standard.yaml          @my-org/network-services
catalog/engineering/product-components/billing-api.yaml              @my-org/billing-team
```

---

## 4. Fallback Teams Configuration

Workspace administrators configure role fallbacks in `.draft/workspace.yaml` under the `routing` configuration block. Fallback values must reference a valid team ID from the team registry:

```yaml
routing:
  fallbackTeams:
    default: draft-admins
    engineering: engineering-architecture-review
    shared-services: shared-services-review
    draft-admins: draft-admins
```

### Fallback Triage Logic:
* If a new file is added to `catalog/shared-services/` but does not yet have an `owner.team` assigned, review is routed to `@my-org/shared-services-review`.
* If a file is added to `catalog/engineering/` but has no owner, it is routed to `@my-org/engineering-architecture-review`.
* If a role fallback is not configured, the default fallback (`draft-admins`) is applied.

---

## 5. Validation and Missing Ownership

DRAFT requires active ownership for stable and complete catalog entries. The validator strictly enforces ownership presence against artifact maturity:

### Validation Rules:
* **Warning (Ownership Needed):** If `owner.team` is missing and the artifact `catalogStatus` is `stub` or `incomplete`, the validator reports a warning. This supports the progressive onboarding principle (capturing incomplete state first).
* **Failure (Blocker):** If `owner.team` is missing and the artifact `catalogStatus` is `complete`, the validator reports a strict failure. No completed artifact is allowed in the catalog without a designated owner team.

### Fallback Issue Routing:
If an issue must be created for a validator failure where `owner.team` is missing or unresolved:
1. The issue is assigned to the workspace's configured administration fallback (`@my-org/draft-admins`).
2. The metadata block sets `needsRouting: true` and `routingReason: "owner.team missing or unresolved"`.
3. The conditional `needs-routing` label is applied to the GitHub issue.
4. The Draft Admins triage queue reviews the issue and manually assigns the accountable team.

---

## 6. PR Governance and Review Etiquette

1. **Multi-Team Reviews:** If a pull request modifies artifacts owned by multiple engineering or infrastructure groups, GitHub will automatically request reviews from each team.
2. **PR Splitting:** To avoid multi-team coordination bottlenecks, authors are encouraged to keep PRs small and split them along ownership boundaries.
3. **Commit Cleanliness:** Always run `python3 framework/tools/validate.py` before opening a pull request to ensure that all team mappings are valid and resolve cleanly.
