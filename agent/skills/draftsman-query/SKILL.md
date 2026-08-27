---
name: draftsman-query
description: Interactive catalog discovery, architectural Q&A (exposed APIs, listening ports, network protocols, data lineage, dependencies), and developer onboarding guidance.
---

# Draftsman Catalog Query & Q&A Skill

## Purpose
Enables the Draftsman Agent to answer precise natural-language architecture questions across the entire DRAFT catalog (exposed APIs, listening ports, network boundaries, database linkages, service dependency trees) and guide developers on onboarding their products into DRAFT.

---

## Answering Rules

These bind every workflow below. `SOUL.md` § Evidence Discipline is the full statement; this is what it means when you are answering a query.

1. **Read fields, not names.** A value is recorded only if you read it from a named field. A name that looks structured — `A → B`, `service-x-prod` — is prose that resembles data. Using it is inference, and inference is labelled.
2. **Absent field, absent answer.** If `technology`, `port`, `protocol` or `label` is not present, the answer is "the index does not carry it". Never fill the gap with a category you inferred from the object's name.
3. **Say what your index cannot see.** Answer about *your index*, never about *the catalog*. You are reading a projection and cannot enumerate what it dropped.
4. **Qualify every count.** Report how a number was obtained — "14 objects whose name matched `platform msvc`" — and never call a substring-matched result complete.

---

## Query Capabilities & Workflows

### 1. Developer Onboarding Guidance ("How do I get my product into DRAFT?")
- **Response Protocol:**
  - Instruct the developer to connect their local IDE AI tool (Cursor, Claude Code, Copilot, Antigravity) to `drafting-table`.
  - Explain product registration via `product_registration` contract (`catalog/engineering/product-registrations/`).
  - Explain local repo initialization via `/draft init` to scaffold `.draft/sdp.yaml` and `.github/workflows/draft-sync.yml`.
  - Highlight Pattern 2 Least-Privilege sync (ephemeral token push, zero source code access).

### 2. Exposed APIs & Endpoints ("Is there an API exposed for ProductA?")
- **Inspection Path:** Search `catalog_indexes.json` for `product_component` or `software_deployment_pattern` matching `ProductA`.
- **Fields to Check:**
  - `edge_gateway_service` linked to the product (ALB, API Gateway, CloudFront).
  - `product_component.interfaces` or `api_spec` declarations.
  - `connection_protocols` and routing rules.

### 3. Ports & Network Listeners ("What port does ServiceA listen on?")
- **Inspection Path:** Inspect `runtime_service`, `product_component`, or container profile configs.
- **Fields to Check:**
  - Container listener ports (e.g. 8080, 5432, 6379).
  - Ingress gateway ports (e.g. 443 HTTPS).
  - Network zone (internal-only vs edge-exposed).

### 4. Data Storage & Lineage ("What databases does ServiceA write to?")
- **Inspection Path:** Trace `software_deployment_pattern` linkages between `product_component` and `data_store_service`.

### 5. Dependency & Reverse-Dependency Mapping ("Which services use Kafka?")
- **Inspection Path:** Perform reverse search across all `software_deployment_pattern` objects in the catalog index.
