# Draftsman Setup Mode

> **Audience: Draft Admins only.**
> Setup mode is for the person standing up and configuring a DRAFT workspace
> for their company. Engineers and Technology Admins do not use setup mode —
> they connect their AI tool to an already-configured workspace and start a
> regular Draftsman session. If you are an engineer wanting to document a
> service, see [Draftsman Instructions](draftsman.md) instead.

Setup mode is the first-run Draftsman conversation for a company DRAFT
workspace. It exists so enterprise architecture teams can make the Drafting
workspace useful without turning onboarding into a long form-filling exercise.

Setup mode is repo-first. The company connects its preferred AI tool to a
private DRAFT workspace repo, and that AI acts as the Draftsman by reading the
root bootstrap files and the vendored framework copy. No DRAFT app or
DRAFT-specific CLI is required for the v1.0 path.

## Setup Mode Contract

When setup mode starts, the Draftsman must keep the onboarding conversational, concise, and focused. Avoid presenting heavy system summaries, checklists of "what is next/remaining," or excessive manual documentation during active setup steps. Keep the current step clear but extremely brief, and focus on the immediate question.

The Draftsman should:
- State the current theme/step briefly (e.g., "Step 2: Business Navigation").
- Ask one focused question at a time (or at most three clear choices if a selection is required).
- Avoid displaying long status headers, backlogs of remaining steps, or lists of revisit-later tasks.
- Translate all camelCase schema/YAML fields into clear, capitalized, user-friendly labels (e.g., use "Data Classification Levels" instead of `dataClassificationLevels`, and "Deployment Targets" instead of `deploymentTargets`). Do not expose raw camelCase fields or technical schema keys directly to the user.
- When asking about a governed vocabulary or taxonomy choice, provide 1–2 simple sentences explaining *why* you are asking and *how* that choice affects the architecture catalog (e.g., how it will group services, drive validation, or enable search filters) rather than assuming the user already knows.
- Never ask for UIDs, YAML fields, schema names, or exhaustive inventories. It should use plain architecture language and record revisit-later items instead of forcing perfect answers.

## Minimum Useful Setup

A workspace is useful enough for first drafting when these items exist or are
deliberately queued:

1. Private company DRAFT repo selected and framework vendored under
   `.draft/framework/`.
2. Workspace identity populated in `.draft/workspace.yaml`, including
   `workspace.name`, `workspace.displayName`, and `workspace.companyName`.
2b. [Optional] DRAFT Discovery options offered to accelerate onboarding setup.
3. Business taxonomy defined well enough for catalog navigation.
4. First company vocabulary lists declared in advisory mode, or deliberately
   queued for later.
5. Initial active Requirement Groups selected.
6. Capability owners identified for the first mapped capabilities.
7. Acceptable-use Technology Components seeded for the most common standards.
8. Baseline deployable objects started for common Host, Runtime Service,
   DataStoreService, and Edge/Gateway patterns.
9. One real product, system, diagram, repository, or source document selected
   for the first guided Drafting Session.

Setup mode should stop once the team can draft and validate one real system. It
should not wait until every platform, capability, or compliance interpretation
is complete.

## Conversation Cadence

Every setup or drafting session should feel like a guided conversation:

- Start with the intended outcome in 1-2 brief sentences.
- Explain what the Draftsman already knows from the repo concisely.
- Ask only for the missing fact needed for the current step.
- Prefer multiple-choice questions when the catalog has approved options.
- Avoid displaying walls of text or lists of remaining/revisit-later steps during active onboarding.
- Mark uncertain answers as assumptions or Drafting Session questions behind the scenes.
- Summarize only the immediate, key change and validation status in 1-2 brief sentences.

Audience matters. Architects can answer governance, lifecycle, and pattern
questions. Engineers can answer runtime, dependency, port, platform, and
operational questions. Product teams can answer product ownership, system
boundaries, customer-facing capability, and release-context questions.

## Recommended Setup Sequence

### 1. Workspace Readiness

Confirm the company repo, workspace identity, framework copy, provider, and
validation command. Before rendering workspace templates, capture the identity
values that make the generated README and AI bootstrap files company-specific.

Questions:

> Which private company DRAFT repo should we use for architecture content?

> What company name should DRAFT use in generated prompts and bootstrap files?

> What should the workspace display name be, for example "Acme DRAFT
> Workspace"?

Record the repo metadata in `.draft/workspace.yaml` before rendering templates:
provider, owner, repo name, and default branch. The generated README prompt
should tell the AI exactly which repo to connect to.

### 1b. [Optional] Discovery Integration

After workspace readiness is established (basic questions like repo path, company name, and workspace name are answered), present Discovery Mode as an optional value-add accelerator to automate the subsequent onboarding setup. Position it strictly as an option, never as a requirement. 

If the user declines, proceed directly to **Step 2: Business Navigation**.

If they are interested, offer the following discovery methods:
- **Atlassian Rovo (Semantic Discovery)**: The Draftsman provides a copy-paste prompt for their enterprise Rovo agent to scan Confluence spaces, Jira projects, and JSM databases for pillars, teams, and active services.
- **FinOps & Cloud Billing (Operational Discovery)**: Ingesting read-only static cost or infrastructure reports (such as AWS Cost and Usage Reports or CloudHealth spreadsheets) to identify actual running server and database substrates.
- **IaC Snapshot (Structure Discovery)**: Ingesting read-only Terraform `.tfstate` snapshots or CloudFormation templates to map deployed components.

Question:

> Would you like to use DRAFT Discovery Mode to automatically scan and import your engineering taxonomy, business pillars, and active services (via Atlassian Rovo, CloudHealth billing reports, or Terraform state)? If yes, which method would you like to explore first? If no, we can configure them manually.

### 2. Business Navigation

Define enough business taxonomy for people to browse the catalog.

Question:

> What are the first 3-7 business pillars or product groupings people should
> use to find architecture?

### 3. Company Vocabulary

Declare the first controlled lists the Draftsman should use for
multiple-choice questions. Start in advisory mode.

Question:

> Which lists do we already know well enough to offer as choices: deployment
> targets, data classifications, team identifiers, availability tiers, or
> failure domains?

### 4. Governance Baseline

Choose the first active Requirement Groups. Start narrow if the company is
migrating an existing inventory.

Question:

> Which governance baseline should new objects address first: DRAFT-only,
> SOC 2, TX-RAMP, NIST CSF, or a company-specific group?

### 5. Domain Standard Ownership

DRAFT ships with 19 capability definitions covering the core technology
architecture domains every company must govern — Authentication, Log Management,
Patch Management, Secrets Management, and so on. These are the equivalent of
enterprise domain standards. Each one needs a designated owner at your company:
the team with authority to say "this is our approved tool for this domain."

Without owners, the Draftsman cannot present governance-grounded choices during
interviews. With owners, engineers get pre-approved multiple-choice answers
instead of open-ended questions.

For each domain below, identify which team at your company owns it. Then for
each owned domain, name the approved Technology Component (if known) — the
Draftsman will create the component and map the capability implementation.

**Compute & Runtime** — Operating System, Compute Platform, Container
Orchestration, Serverless Runtime, Patch Management, General Purpose Compute

**Security & Identity** — Authentication, Access Control Model, Secrets
Management, Security Monitoring, Encryption At Rest

**Observability** — Log Management, Health & Welfare Monitoring, Application
Performance Monitoring

**Data** — Backup Strategy

**Engineering Quality** — Quality Gates, Test Authoring, Test Execution,
Performance Testing

Questions:

> For each domain group, which team is the owner — the team that approves
> which products are used?

> For each domain your team owns today, what is the currently approved or
> preferred product?

The Draftsman will generate one object-patch file per capability in
`configurations/object-patches/`, setting `owner` and creating approved
Technology Component implementations. Domains with no known owner are patched
with `owner: TBD` so the gap is visible in the catalog immediately.

### 6. Baseline Deployable Standards

Create enough reusable deployable objects that product drafting can choose
standards instead of inventing everything.

Question:

> Which common deployable standard should we draft first: Host, Runtime
> Service, DataStoreService, or Edge/Gateway Service?

### 7. IDE Integration

DRAFT is AI-agnostic. The Draftsman role can be fulfilled by any capable AI
assistant. This step wires DRAFT's built-in workflow commands into whichever
IDE the team uses so `/draftsman`, `/draft-session`, and `/validate-catalog`
are available as first-class invocable commands rather than role-activation
phrases.

Ask the team which AI IDE(s) they use and follow the relevant sub-steps. More
than one can be configured; they do not conflict.

#### 7a. Claude Code

Run once from the workspace root:

```bash
mkdir -p .claude/commands
ln -sf ../../.draft/framework/commands/draftsman.md .claude/commands/draftsman.md
ln -sf ../../.draft/framework/commands/draft-session.md .claude/commands/draft-session.md
ln -sf ../../.draft/framework/commands/validate-catalog.md .claude/commands/validate-catalog.md
```

On Windows (PowerShell as Administrator, or with Developer Mode enabled):

```powershell
New-Item -ItemType Directory -Force -Path .claude\commands
New-Item -ItemType SymbolicLink -Path .claude\commands\draftsman.md `
  -Target ..\..\draft\framework\commands\draftsman.md -Force
New-Item -ItemType SymbolicLink -Path .claude\commands\draft-session.md `
  -Target ..\..\draft\framework\commands\draft-session.md -Force
New-Item -ItemType SymbolicLink -Path .claude\commands\validate-catalog.md `
  -Target ..\..\draft\framework\commands\validate-catalog.md -Force
```

The symlinks follow the vendored framework copy, so updating the framework
automatically updates command behavior without re-linking. Re-run this step
if a framework update adds new commands.

#### 7b. Cursor

Copy the ready-made Cursor rules file into the workspace:

```bash
mkdir -p .cursor/rules
cp .draft/framework/integrations/cursor/draftsman.mdc .cursor/rules/draftsman.mdc
```

After a framework update, re-copy if the integration file has changed.

#### 7c. Windsurf

Copy the ready-made Windsurf rules file into the workspace root:

```bash
cp .draft/framework/integrations/windsurf/draftsman.md .windsurfrules
```

If `.windsurfrules` already exists, append the content instead of overwriting.
After a framework update, re-copy if the integration file has changed.

#### 7d. GitHub Copilot

The workspace bootstrap generates `.github/copilot-instructions.md` with
Draftsman activation already included. If the file exists and was edited
manually, add the following block:

```markdown
When the user invokes `/draftsman`, `/draft-session`, or `/validate-catalog`,
read the corresponding file from `.draft/framework/commands/` and follow its
instructions exactly.
```

#### 7e. Gemini CLI and OpenAI Codex

`GEMINI.md` and `AGENTS.md` are generated by the workspace bootstrap with
command invocation already included. No additional setup is required for
these tools.

#### 7f. Other / generic AI tools

Any AI assistant that can read files in the workspace can act as a Draftsman.
Point the AI at `AGENTS.md` as the bootstrap entry point — it includes
command invocation guidance. The command files themselves are plain markdown
that any AI can read and follow without IDE-specific registration.

This step is optional for workspaces that prefer role-activation phrases, but
is recommended for teams who want a consistent, discoverable workflow across
all AI tools.

### 8. GitHub Governance

Enable branch protection and CODEOWNERS so every catalog change is reviewed by
the right team before it reaches main. This step wires the three DRAFT roles
(Draft Admin, Technology Admin, Engineer) to GitHub Teams.

#### 8a. CODEOWNERS file

A `CODEOWNERS.tmpl` template is shipped with the framework. If `.github/CODEOWNERS`
does not yet exist, generate it from the template and fill in your GitHub org
slug and team handles:

```bash
cp .draft/framework/templates/workspace/CODEOWNERS.tmpl .github/CODEOWNERS
```

Edit `.github/CODEOWNERS`:
- Replace `YOUR-ORG` with your GitHub organization slug.
- Set the team handle for `draft-admins` (the team that governs the workspace).
- Set the team handle for `technology-admins` (the team that owns the shared
  technology catalog — runtime services, hosts, technology components, edge
  gateway services, data store services).
- Add one line per engineering team for their catalog path:
  `catalog/engineering/[team-slug]/   @YOUR-ORG/[github-team-slug]`

Questions:

> What is your GitHub organization slug?

> Which GitHub team should be the Draft Admin (governs workspace config,
> vocabulary, and requirement groups)?

> Which GitHub team should be the Technology Admin (owns the shared technology
> catalog)?

> Which engineering teams need CODEOWNERS lines, and what are their GitHub team
> slugs?

#### 8b. Branch protection

Enable branch protection on `main` so pull request review is required before
merging. Run this once using the GitHub CLI (requires admin access to the repo):

```bash
gh api repos/YOUR-ORG/YOUR-REPO/branches/main/protection \
  --method PUT \
  --field required_status_checks=null \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null
```

Or enable it manually in the repository Settings → Branches → Branch protection
rules → Require a pull request before merging.

Once branch protection is active, the Draftsman will automatically create a
branch for each session and open a pull request at the end. CODEOWNERS routes
that PR to the correct reviewers without any additional configuration.

### 9. First Real Drafting Session

Start with one real product or system and capture gaps as work in progress.

Question:

> Which product, system, diagram, repository, or source document should we use
> for the first guided Drafting Session?

## Good Setup Output

A good setup-mode response is conversational, concise, and focused. It avoids checklists of remaining work and explains the context of vocabulary/taxonomy choices in a human-friendly way:

```text
Setup mode is active.

We've successfully verified your workspace at `/path/to/company-draft` and confirmed your base governance configurations are loaded.

Before we begin drafting your first service, we need to map your Business Pillars. These pillars represent the primary business divisions (like Core Infrastructure or Retail Operations) and will organize your architecture catalog so engineers can easily find and filter the services they need.

Question: What are the first 3 to 7 Business Pillars or product groupings used at your company?
```
