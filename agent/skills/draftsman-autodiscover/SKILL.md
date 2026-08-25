---
name: draftsman-autodiscover
description: Autonomous repository code & infrastructure inspection via user-delegated GitHub OAuth to auto-generate DRAFT catalog entries.
---

# Draftsman Repository Auto-Discovery Skill

## Purpose
Enables the Draftsman Agent to inspect an engineer's private application repository using user-delegated GitHub OAuth permissions, parse its infrastructure-as-code and application configuration files, and automatically generate valid DRAFT architecture catalog entries.

---

## Workflow Steps

### 1. User-Delegated OAuth Check
When a user asks: *"Draftsman, scan my repo org/service-repo and create its DRAFT architecture"*:
1. Check if a valid, unexpired user-delegated GitHub OAuth token exists for that user.
2. If absent, present an interactive OAuth login link: `[Authorize Draftsman on GitHub]`.

### 2. Codebase Inspection & Parsing
Once authenticated with the user's token:
1. Clone or read the repository contents in a secure ephemeral sandbox.
2. Inspect key configuration & infrastructure files:
   - **Docker / Containers:** `Dockerfile`, `docker-compose.yml`, `Kubernetes manifests` (Helm / Kustomize).
   - **Infrastructure-as-Code:** `main.tf`, `*.tf`, `cdk.json`, `stack.ts`.
   - **Application Dependencies:** `package.json`, `pom.xml`, `build.gradle`, `requirements.txt`, `Cargo.toml`.
   - **Application Configs:** `application.yml`, `appsettings.json`, `.env.example`.

### 3. Feature Extraction Matrix

| Found In Codebase | Inferred DRAFT Object Type | Catalog Field Mapping |
| :--- | :--- | :--- |
| `FROM python:3.11-slim` | `product_component` | `runtimeEnvironment: Python 3.11` |
| `aws_sqs_queue.fifo` | `runtime_service` | `technologyComponent: technology-aws-sqs` |
| `aws_db_instance` (postgres) | `data_store_service` | `technologyComponent: technology-aws-rds-postgresql` |
| `aws_lb_listener` (port 443) | `edge_gateway_service` | `technologyComponent: technology-aws-alb` |

### 4. DRAFT Catalog & PR Generation
1. Construct valid DRAFT YAML files for `product_component`, `runtime_service`, `data_store_service`, `edge_gateway_service`, and `software_deployment_pattern`.
2. Run `validate.py --workspace .` to ensure zero schema errors.
3. Open a Pull Request on the company's private DRAFT workspace repo.
