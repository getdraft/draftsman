# Draftsman Agent Deployment & Integration Guide

This guide details how to provision, configure secrets, and deploy the **Draftsman Agent** across company agent factories (`hermes-gcp-factory`, `das-hermes-poc`), chat platforms (Slack, Discord), and GitHub workspace repositories.

---

## 1. Secrets & Identity Requirements

Before deploying the agent container, provision the required credentials in your cloud secret manager (**Google Cloud Secret Manager** or **AWS Secrets Manager**):

### Required Credentials Matrix

| Platform / Integration | Secret Key | Required Scopes | Purpose |
| :--- | :--- | :--- | :--- |
| **GitHub Access** | `GITHUB_PAT` or `GITHUB_APP_KEY` | `repo`, `workflow`, `pull_requests:write` | Reading/writing DRAFT catalog YAML and opening PRs |
| **Slack App** *(AWS/Frontline)* | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` | `chat:write`, `app_mentions:read`, `commands` | Interactive chat & slash command handling |
| **Discord Bot** *(GCP/dsackr)* | `DISCORD_BOT_TOKEN`, `DISCORD_APP_ID` | `bot`, `applications.commands`, `Send Messages` | Discord channel interactions & diagrams |
| **User GitHub OAuth** | `GITHUB_OAUTH_CLIENT_ID`, `CLIENT_SECRET` | `repo` (User-delegated token) | Repository auto-discovery on behalf of users |

---

## 2. Infrastructure-as-Code (IaC) Provisioning

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
    DISCORD_BOT_TOKEN = "projects/${var.gcp_project_id}/secrets/draftsman-discord-token/versions/latest"
    GITHUB_PAT        = "projects/${var.gcp_project_id}/secrets/draftsman-github-pat/versions/latest"
  }

  # Scale-to-zero runtime configuration (Litestream SQLite safety)
  min_instances   = 0
  max_instances   = 1
  cpu_limit       = "1"
  memory_limit    = "2Gi"
  timeout_seconds = 300
}
```

Execution:
```bash
tofu init
tofu apply -target=module.draftsman_agent
```

---

### B. AWS Fargate & ECS Deployment (`das-hermes-poc` / Frontline)

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
        { name = "HERMES_ENV", value = "dev" },
        { name = "HERMES_SLACK_BOT_USER_ID", value = var.slack_bot_user_id }
      ]
      secrets = [
        { name = "SLACK_BOT_TOKEN", valueFrom = "${aws_secretsmanager_secret.draftsman.arn}:SLACK_BOT_TOKEN::" },
        { name = "GITHUB_PAT", valueFrom = "${aws_secretsmanager_secret.draftsman.arn}:GITHUB_PAT::" }
      ]
    }
  ])
}
```

---

## 3. User-Delegated GitHub OAuth & Repository Auto-Discovery

To enable Draftsman to inspect a developer's private codebase and auto-discover infrastructure dependencies:

1. **User Initiation:**
   - Engineer chats: `@Draftsman scan my repo company/payment-service and generate its DRAFT catalog entry.`
2. **OAuth Authorization Challenge:**
   - If Draftsman lacks user-delegated scope for that repository, it replies with a secure OAuth button:
     `[Connect GitHub Account via OAuth]`
3. **Auto-Discovery Execution:**
   - Once authorized, Draftsman clones the repository into an isolated memory sandbox using the user's short-lived OAuth token.
   - It inspects `Dockerfile`, `docker-compose.yml`, `main.tf`, `cdk.json`, `pom.xml`, `package.json`, or `requirements.txt`.
   - It automatically identifies runtimes (e.g. Java 17), datastores (PostgreSQL 14), queues (RabbitMQ/SQS), and ingress endpoints.
   - It constructs valid DRAFT catalog YAML files and opens a PR on the company `drafting-table` repository.
