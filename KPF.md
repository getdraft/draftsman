# Key Product Functionalities (KPF) — Draftsman Framework

**Source of truth for product functionality & test mappings.**

| KPF ID | Name | Description | Severity | Mapped Tests | Status |
|---|---|---|---|---|---|
| `KPF-DFT-001` | Workspace Schema Validation | CLI and library tool (`validate.py`) to validate DRAFT catalog schemas, UIDs, and requirement groups. | Sev1 | `tests/test_validation.py` | Active |
| `KPF-DFT-002` | Framework Package Synchronization | Framework sync engine (`repo.py`, `/draft update`, `draft-framework-update.yml`) to vendor upstream releases. | Sev1 | `tests/test_repo.py`, `tests/test_draftsman.py` | Active |
| `KPF-DFT-003` | OpenTofu / IaC Composition Engine | IaC composition script (`compose_iac.py`) translating `.draft/sdp.yaml` to runnable OpenTofu code. | Sev1 | `tests/test_tooling_correctness.py` | Active |
| `KPF-DFT-004` | Optional MCP Adapter | Optional MCP server (`framework/tools/mcp_server.py`) whose tools answer from the catalog index and never from fixed text. | Sev2 | `tests/test_mcp_server.py` | Active |
