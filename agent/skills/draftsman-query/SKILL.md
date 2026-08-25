---
name: draftsman-query
description: Interactive catalog discovery and deep architectural Q&A (exposed APIs, listening ports, network protocols, data lineage, dependencies).
---

# Draftsman Catalog Query & Q&A Skill

## Purpose
Enables the Draftsman Agent to answer precise natural-language architecture questions across the entire DRAFT catalog, including exposed APIs, listening ports, network boundaries, database linkages, and service dependency trees.

---

## Query Capabilities & Workflows

### 1. Exposed APIs & Endpoints ("Is there an API exposed for ProductA?")
- **Inspection Path:** Search `catalog/` for `product_component` or `software_deployment_pattern` matching `ProductA`.
- **Fields to Check:**
  - `edge_gateway_service` linked to the product (ALB, API Gateway, CloudFront).
  - `product_component.interfaces` or `api_spec` declarations.
  - `connection_protocols` and routing rules.
- **Answer Format:**
  - State whether an API exists, the entrypoint URL/host, authentication mechanism, and supported protocols (REST, GraphQL, gRPC, WebSockets).

### 2. Ports & Network Listeners ("What port does ServiceA listen on?")
- **Inspection Path:** Inspect `runtime_service`, `product_component`, or container profile configs.
- **Fields to Check:**
  - `container_ports` / `target_port` / `host_port`.
  - `network_zone_patterns` (e.g. `ingress_ports: [8080]`).
  - `connection_protocols` (HTTP/8080, HTTPS/443, gRPC/50051, Redis/6379, Postgres/5432).
- **Answer Format:**
  - Return exact port numbers, protocol, network zone (internal-only vs edge-exposed), and transport security (TLS/mTLS).

### 3. Data Storage & Lineage ("What databases does ServiceA write to?")
- **Inspection Path:** Trace `software_deployment_pattern` linkages between `product_component` and `data_store_service`.
- **Fields to Check:**
  - Linked `data_store_service` objects (RDS PostgreSQL, DynamoDB, Redis, S3).
  - Access patterns (Read-only, Read-Write, Event Stream).
- **Answer Format:**
  - List all data stores, technology versions, table/bucket identifiers, and access scopes.

### 4. Dependency & Reverse-Dependency Mapping ("Which services use Kafka?")
- **Inspection Path:** Perform reverse search across all `software_deployment_pattern` YAML files in `catalog/`.
- **Answer Format:**
  - Provide a summary table of consuming components, topic names, and delivery models.

---

## Example Q&A Responses

### Example 1: Listening Port Query
**User:** *"What port does the Absence Integration API listen on for Absence & Time?"*

**Draftsman Answer:**
> **Absence Integration API** (`product_component-absence-time-api-integration-service`):
> * **Container Listener Port:** `8080` (HTTP / REST)
> * **Ingress Gateway:** AWS ALB (`edge-gateway-service-absence-alb`), listening on **Port 443 (HTTPS)** with TLS 1.3 termination.
> * **Internal Network Zone:** `private-app-subnet` (restricted to internal VPC traffic).

### Example 2: Exposed API Query
**User:** *"Is there an API exposed for the APEX Interview Bot?"*

**Draftsman Answer:**
> Yes. The **APEX Interview Bot** exposes two interfaces:
> 1. **REST Ingest API:** Exposed via AWS API Gateway at `https://api.frontlineed.com/v1/apex/interviews` (Port 443 HTTPS, OAuth2 Bearer token).
> 2. **WebSocket Gateway:** Real-time audio stream listener at `wss://stream.frontlineed.com/apex/voice` (Port 443 WSS).
