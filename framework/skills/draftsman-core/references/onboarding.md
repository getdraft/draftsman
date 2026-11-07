# Onboarding Playbook

When an engineer asks "How do I get my product into DRAFT?", "How do I create my SDP?", or "How do I set up DRAFT in my repo?", respond with this 4-step playbook. Do not write catalog or SDP YAML in the answer; the Author profile does that in the repository.

## Step 1: Connect your IDE AI assistant to `drafting-table`

Point your IDE AI assistant (Cursor, Claude Code, GitHub Copilot, Antigravity, VS Code) at your company's `drafting-table` repository. The assistant discovers the Draftsman rules through the instruction files the repository carries (for example `.cursor/rules/draftsman.mdc`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`).

## Step 2: Register your product in `drafting-table`

In your IDE, ask your AI assistant:

> `@Draftsman register my product [Product Name]`

The assistant scaffolds a `product_registration` file under `catalog/engineering/product-registrations/product-reg-[name].yaml` linking your product source repo URL (for example `https://github.com/company/absence-service`) and its `.draft/sdp.yaml` manifest path.

## Step 3: Initialize DRAFT in your product repository (`/draft init`)

Open your product code repository in your IDE and run:

> `/draft init`

Your local AI assistant inspects your `Dockerfile`, `docker-compose.yml`, `main.tf`, `pom.xml`, `package.json`, or `requirements.txt` to discover your runtimes, listening ports, and datastores, then scaffolds `.draft/sdp.yaml` and `.github/workflows/draft-sync.yml`. Anything it guesses is inferred, so confirm each value.

## Step 4: Author, validate and sync (least-privilege sync)

1. Edit `.draft/sdp.yaml` inside your product repo.
2. Validate locally: `python3 .draft/framework/tools/validate.py --workspace .`
3. Merge your pull request in your product repo. The GitHub Action syncs your `.draft/sdp.yaml` payload to `drafting-table` using an ephemeral token.
4. `drafting-table` holds zero read access to your private source code repo.
