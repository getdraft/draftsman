# Authoring guide

## Conversational flow

1. Bootstrap by reading `AGENTS.md`, `.draft/framework/AI_INDEX.md` and `.draft/workspace.yaml`.
2. Assess the workspace. If `.draft/workspace.yaml` lacks `workspace.name`, `workspace.displayName` or `workspace.companyName`, or `catalog/` has only placeholders, read `.draft/framework/docs/setup-mode.md`.
3. With a topic: look in `catalog/governance/sessions/` for a session whose `uid` or `name` matches (case-insensitive). Load it, start a new DraftingSession for a concrete system or product, or answer a one-off request directly without a session file.
4. Without a topic: list the existing sessions and ask what the user wants to draft or update.
5. For an existing session: summarise what is known and what is open, then ask whether to continue or start fresh.
6. For a new session: confirm the topic, read `.draft/framework/docs/drafting-sessions.md`, and ask at most three questions at a time.
7. Do the work under the Draftsman role in `.draft/framework/docs/draftsman.md`. Record open questions, assumptions and next steps in the session file so the work can be resumed. Save it before you stop.
8. If authoring reveals a reusable framework bug, schema gap or missing template, follow the Upstream Framework Feedback Routing procedure in `.draft/framework/docs/draftsman.md` before creating any public issue, and only with the user's approval.

## Repository scan mapping

Everything below is inference from file contents. Mark it as inferred and ask the user to confirm.

| Found in the repository | DRAFT object type | Field |
| :--- | :--- | :--- |
| `FROM python:3.11-slim` | `product_component` | `runtimeEnvironment: Python 3.11` |
| `aws_sqs_queue.fifo` | `runtime_service` | `technologyComponent: technology-aws-sqs` |
| `aws_db_instance` (postgres) | `data_store_service` | `technologyComponent: technology-aws-rds-postgresql` |
| `aws_lb_listener` (port 443) | `edge_gateway_service` | `technologyComponent: technology-aws-alb` |

Files worth reading: `Dockerfile`, `docker-compose.yml`, Kubernetes manifests, `*.tf`, `cdk.json`, `package.json`, `pom.xml`, `build.gradle`, `requirements.txt`, `Cargo.toml`, `application.yml`, `appsettings.json`, `.env.example`.

Never copy a secret value from a configuration file into the catalog.

## Committing the work

If git and a remote are available and the user agrees: create `draft/<feature-name>`, stage `catalog/` and `configurations/`, commit with `feat(draft): add <feature-name> architecture catalog entries`, push, and open a pull request that states the validation result. Otherwise report the changed files and stop.
