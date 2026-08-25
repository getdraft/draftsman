---
name: draftsman-standards
description: Security requirements, compliance guardrails, approved technology standards, version lifecycle, and architectural exception processing.
---

# Draftsman Standards & Governance Q&A Skill

## Purpose
Enables the Draftsman Agent to answer questions regarding company technical standards, security requirements (`requirement_group`), approved technology components (`technology_component`), software version lifecycles, and architectural exception workflows (`vocabulary_proposal`).

---

## Query Workflows & Knowledge Categories

### 1. Security & Compliance Requirements ("Is CrowdStrike required on containers?")
- **Inspection Path:** Search `configurations/requirement-groups/` and `.draft/framework/configurations/requirement-groups/` (e.g. `requirement-group-host-compute-profile.yaml`, `requirement-group-draft-security-compliance.yaml`).
- **Fields to Check:**
  - `requirements` list, `description`, and `complianceControls`.
  - Endpoint protection, container host runtime security, host sensor mandates.
- **Answer Format:**
  - Quote the exact Requirement ID (e.g. `REQ-SEC-HOST-004`), describe the policy, state whether container host sensors vs container sidecars apply, and link to the relevant `requirement_group` file.

### 2. Approved Technology Standards ("What are the standard DB options for T-SQL?")
- **Inspection Path:** Search `catalog/` and `configurations/` for `technology_component` entries under the target domain (e.g. `data`, `database`, `t-sql`).
- **Fields to Check:**
  - Approved `technology_component` objects (e.g. `technology-ms-sql-server-2022.yaml`, `technology-rds-sql-server.yaml`).
  - Approved delivery models (PaaS, Managed Cloud, Self-Hosted HA).
- **Answer Format:**
  - List approved Technology Components, supported major versions, deployment options, and link to their catalog files.

### 3. Version Lifecycle & Deprecated Technologies ("Can we use MS SQL 2016?")
- **Inspection Path:** Check `technology_component` lifecycle status (`approved`, `deprecated`, `end-of-life`, `prohibited`).
- **Logic:**
  - If a version is `deprecated` or `end-of-life` (e.g. SQL Server 2016), inform the user that it is unapproved for new deployments and recommend approved alternatives (e.g. SQL Server 2022).
- **Answer Format:**
  - Direct status answer + clear rationale + approved upgrade alternative.

### 4. Unapproved Technology & Exception Guidance ("Is BobsBBQ v2 allowed or do we need an exception?")
- **Inspection Path:** Query catalog for `BobsBBQ`.
- **Logic:**
  - If the requested technology or tool is NOT in the approved catalog, inform the user that it is **unapproved / non-standard**.
  - Explain the architectural exception workflow:
    1. Draftsman creates a `vocabulary_proposal` file in `configurations/vocabulary-proposals/`.
    2. Opens a PR against the company DRAFT repository for Enterprise Architecture review.
    3. Reviewers evaluate security, operational fit, and compliance before merging.

---

## Example Responses

### Example 1: Security Requirement Query
**User:** *"Is there a requirement for CrowdStrike on containers?"*

**Draftsman Answer:**
> Yes. Under **RequirementGroup: Host & Compute Profile** (`requirement-group-host-compute-profile.yaml`):
> * **Requirement ID:** `REQ-SEC-CONTAINER-003` (Container Host Protection)
> * **Policy:** All container host nodes (EC2/K8s nodes) must run the **CrowdStrike Falcon Host Sensor**. For serverless/ephemeral containers (AWS Fargate), the **Falcon Container Sensor** sidecar/image entitlement must be verified before deployment.

### Example 2: Approved DB Technology Query
**User:** *"What are the standard DB options for T-SQL?"*

**Draftsman Answer:**
> The approved T-SQL database options in the company catalog are:
> 1. **AWS RDS for SQL Server 2022 (PaaS)** — [`technology-rds-sqlserver-2022.yaml`](file:///catalog/...) *(Recommended for cloud workloads)*
> 2. **MS SQL Server 2022 Enterprise High Availability (Self-Managed)** — [`technology-ms-sqlserver-2022-ha.yaml`](file:///catalog/...)

### Example 3: Unapproved Technology Exception Query
**User:** *"Is BobsBBQ v2 allowed in our infrastructure or do we need an exception?"*

**Draftsman Answer:**
> **BobsBBQ v2** is currently **unapproved** — it does not exist in the company's approved Technology Component catalog.
> 
> To use it, we must submit an **Architectural Exception**:
> 1. I can draft a `vocabulary_proposal` for `BobsBBQ v2` in `configurations/vocabulary-proposals/bobsbbq-v2.yaml`.
> 2. I will submit a PR to your company's DRAFT workspace repo for Architecture Review.
> 
> Would you like me to draft that proposal PR now?
