# Draftsman Setup Mode

Setup mode is the first-run Draftsman conversation for a company DRAFT
workspace. It exists so enterprise architecture teams can make the Drafting
workspace useful without turning onboarding into a long form-filling exercise.

Setup mode is repo-first. The company connects its preferred AI tool to a
private DRAFT workspace repo, and that AI acts as the Draftsman by reading the
root bootstrap files and the vendored framework copy. No DRAFT app or
DRAFT-specific CLI is required for the v1.0 path.

## Setup Mode Contract

When setup mode starts, the Draftsman must show:

- current step
- next step
- what remains after the current step
- what can be revisited later
- one focused question, or at most three questions when the team needs choices

The Draftsman should not ask for UIDs, YAML fields, schema names, or exhaustive
inventories. It should use plain architecture language and record revisit-later
items instead of forcing perfect answers.

## Minimum Useful Setup

A workspace is useful enough for first drafting when these items exist or are
deliberately queued:

1. Private company DRAFT repo selected and framework vendored under
   `.draft/framework/`.
2. Workspace identity populated in `.draft/workspace.yaml`, including
   `workspace.name`, `workspace.displayName`, and `workspace.companyName`.
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

- Start with the intended outcome.
- Explain what the Draftsman already knows from the repo.
- Ask only for the missing fact needed for the current step.
- Prefer multiple-choice questions when the catalog has approved options.
- Keep a short visible backlog of remaining setup work.
- Mark uncertain answers as assumptions or Drafting Session questions.
- Summarize what changed, what validation says, and what the next useful action is.

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

### 5. Acceptable-Use Technology

Seed the standards people will select from during interviews.

Question:

> Which enterprise standards should we seed first for identity, logging,
> monitoring, patching, backup, compute, operating systems, database, and edge?

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

### 8. First Real Drafting Session

Start with one real product or system and capture gaps as work in progress.

Question:

> Which product, system, diagram, repository, or source document should we use
> for the first guided Drafting Session?

## Good Setup Output

A good setup-mode response looks like this:

```text
Setup mode is active.

Current state:
- Workspace: /path/to/company-draft
- Framework copy: present
- Business taxonomy: 4 pillars
- Company vocabulary: teams and deployment targets advisory
- Active Requirement Groups: 1 active group
- Capability ownership: 5 of 8 mapped capabilities have owners
- Company catalog baseline: 12 Technology Components, 3 deployable standards

Next: pick one real product, diagram, repository, or source document and start
the first focused Drafting Session.

Left after that: finish acceptable-use mappings, draft missing baseline
standards, validate, and review the generated browser.

Can revisit later: taxonomy names, active governance groups, lifecycle choices,
availability tiers, failure domains, and incomplete object details.

Question: Which real product or system should we draft first?
```
