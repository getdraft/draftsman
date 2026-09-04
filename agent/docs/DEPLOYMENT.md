# Draftsman Agent Deployment & Integration Guide

This guide details how to provision, configure secrets, and deploy the unified **Draftsman Agent** across company agent factories (`hermes-gcp-factory`, `das-hermes-poc`), internal web environments (`web_ui`), chat platforms (Slack, Discord), and connected developer IDE workspaces.

---

## 1. Unified Identity & Execution Contexts

DRAFT defines a single canonical agent specification—**Draftsman** (`draftsman`)—which operates across two distinct execution contexts:

### A. Central Chat / Factory Deployment Mode (Slack, Discord, Web UI, Webhooks)
- **Deployment**: Factory-deployed singleton container running on AWS Fargate, GCP Cloud Run, or Kubernetes.
- **Scope**: **Strictly Read-Only Query & Guidance.** Answers architecture questions, searches ports, database engines, dependencies, generates C4 diagrams, and guides engineers to onboarding workflows.
- **Channels**: `web_ui` (Web chat page & `/health` endpoint), `slack`, `discord`, `github_webhooks`.
- **Identity & Security Model**: Uses `ANTHROPIC_API_KEY` for reasoning and reads pre-compiled `catalog_indexes.json` / `AI_INDEX.md`. Holds **zero write credentials** to private application code repositories.

### B. Connected Developer IDE / Workstation Mode (Cursor, Claude Code, Copilot, Antigravity, VS Code, CLI)
- **Deployment**: Connected AI coding assistants in developer IDEs loading DRAFT workspace rules (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.cursor/rules/draftsman.mdc`).
- **Scope**: **Authoring, Product Registration, Scaffolding, & Local Validation.**
- **Channels**: IDE Chat window & Terminal CLI.
- **Identity Model**: Runs locally under the developer's working copy and Git credentials. Edits `.draft/sdp.yaml`, runs local `validate.py`, and creates PRs under the developer's verified identity. Central catalog sync happens via **Pattern 2 Token Push**.

---

## 2. Secrets Requirements Matrix

Before deploying the factory agent container, provision credentials in your cloud secret manager (**Google Cloud Secret Manager** or **AWS Secrets Manager**):

| Integration | Secret Key | Required Scopes | Purpose |
| :--- | :--- | :--- | :--- |
| **LLM Engine** | `ANTHROPIC_API_KEY` | API Access | Core agent reasoning & query resolution |
| **Web UI** | N/A | None | Built-in web chat interface & `/health` endpoint |
| **Slack App** | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` | `chat:write`, `app_mentions:read`, `commands` | Optional Slack chat & slash command handling |
| **Discord Bot** | `DISCORD_BOT_TOKEN`, `DISCORD_APP_ID` | `bot`, `applications.commands`, `Send Messages` | Optional Discord channel interactions |

---

## 3. Infrastructure-as-Code (IaC) Provisioning

### A. GCP Cloud Run Deployment (`dsackr/hermes-gcp-factory`)

For GCP environments using OpenTofu (`tofu`):

```hcl
# main.tf / modules/hermes_agent/draftsman.tf

module "draftsman_agent" {
  source = "./modules/hermes_agent"

  agent_name   = "draftsman"
  gcp_project  = var.gcp_project_id
  gcp_region   = var.gcp_region
  
  # Secret Manager bindings
  secrets = {
    ANTHROPIC_API_KEY = "projects/${var.gcp_project_id}/secrets/draftsman-anthropic-key/versions/latest"
  }

  # Scale-to-zero runtime configuration
  min_instances   = 0
  max_instances   = 1
  cpu_limit       = "1"
  memory_limit    = "2Gi"
  timeout_seconds = 300
}
```

---

### B. AWS Fargate & ECS Deployment (AWS Cloud Infrastructure)

For AWS environments using Terraform:

```hcl
# draftsman-fargate.tf

resource "aws_ecs_task_definition" "draftsman" {
  family                   = "hermes-agent-draftsman"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.draftsman_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "draftsman-agent"
      image     = "${aws_ecr_repository.hermes.repository_url}:latest"
      essential = true
      environment = [
        { name = "HERMES_ENV", value = "prod" },
        { name = "WEB_UI_ENABLED", value = "true" }
      ]
      secrets = [
        { name = "ANTHROPIC_API_KEY", valueFrom = "${aws_secretsmanager_secret.draftsman.arn}:ANTHROPIC_API_KEY::" }
      ]
    }
  ])
}
```

---

## 4. Web UI Channel & Zero-Approval Deployment

The `web_ui` channel allows agent factories to deploy Draftsman on day one without waiting for Slack/Discord workspace admin bot approvals:

1. **Deployment**: Container serves a web interface at `/` and health check at `/health`.
2. **Internal Exposure**: Place the task behind an internal Application Load Balancer (ALB) or Cloud Run endpoint.
3. **Day One Readiness**: Engineers access Draftsman web chat immediately while chat platform approvals proceed in parallel.
