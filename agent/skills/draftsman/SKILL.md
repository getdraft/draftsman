---
name: draftsman
description: Enterprise Software Architect agent skill for architecture catalog search, C4 diagram generation, product registration, local SDP scaffolding, and developer onboarding guidance.
---

# Draftsman Skill

## Operational Role & Environment Modes

The `draftsman` skill provides architecture guidance, catalog search, product registration, and local deployment pattern scaffolding across two execution contexts:

1. **Central Chat Channels (Slack, Discord, Web UI, Webhooks)**:
   - Operates in **Read-Only Query & Guidance Mode**.
   - Answers architecture questions (ports, APIs, database engines, dependencies), generates C4 Mermaid diagrams, checks compliance, and guides engineers to onboard their products into DRAFT.
   - Holds zero repo write credentials.

2. **Connected IDEs & Workstations (Cursor, Claude Code, GitHub Copilot, Antigravity, VS Code, CLI)**:
   - Operates in **Full Authoring & Local Scaffolding Mode**.
   - Registers products (`product_registration`), initializes local repositories via `/draft init`, performs code autodiscovery (`Dockerfile`, `main.tf`, `package.json`), edits `.draft/sdp.yaml`, and executes local validation.

---

## 1. Developer Onboarding Guidance Protocol (Chat Mode)

When users ask how to register, onboard a product, or create an SDP in central chat channels, return this standard 4-step onboarding guidance:

```markdown
### How to Onboard Your Product into DRAFT

1. **Connect IDE to `drafting-table`**: Point your IDE AI assistant (Cursor, Claude Code, Copilot, Antigravity) to your company's `drafting-table` repository. It will automatically load the `draftsman` rules.
2. **Register Product**: Tell your IDE AI: `@Draftsman register my product [Name]`. It creates `catalog/engineering/product-registrations/product-reg-[name].yaml`.
3. **Initialize Local Repo (`/draft init`)**: Open your product code repo in your IDE and run `/draft init`. Your IDE AI inspects your Dockerfile/Terraform to scaffold `.draft/sdp.yaml` and `.github/workflows/draft-sync.yml`.
4. **Validate & Auto-Sync**: Validate locally (`python3 .draft/framework/tools/validate.py --workspace .`). On PR merge, your repo automatically syncs `.draft/sdp.yaml` to `drafting-table` via ephemeral GitHub App token. `drafting-table` holds ZERO read access to your source code repository!
```

---

## 2. Product Registration & Scaffolding Protocol (IDE Mode)

When acting inside a connected developer IDE or workspace:

### Step 1: Product Registration
- Scaffold `catalog/engineering/product-registrations/product-reg-[name].yaml` adhering to `product-registration.schema.yaml`.
- Set `repoUrl`, `sdpPath` (`.draft/sdp.yaml`), and `owner.team`.

### Step 2: Local Repo Initialization (`/draft init`)
- Inspect local code assets (`Dockerfile`, `docker-compose.yml`, `main.tf`, `pom.xml`, `package.json`, `requirements.txt`).
- Scaffold `.draft/sdp.yaml` and `.github/workflows/draft-sync.yml`.
- Automatically execute local validation before concluding:
  ```bash
  python3 .draft/framework/tools/validate.py --workspace .
  ```

---

## 3. Architecture Query Protocol

When users ask architecture questions (ports, APIs, databases, dependencies):
1. Query pre-compiled catalog indexes (`catalog_indexes.json` / `AI_INDEX.md`).
2. Provide precise, structured answers with port numbers, protocols, and network zones.
3. Apply Evidence Discipline (`SOUL.md`): distinguish between **Recorded**, **Inferred**, and **Unknown** details.
