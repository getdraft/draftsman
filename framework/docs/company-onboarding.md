# Company Onboarding

This guide is the clean first-run path for a company adopting DRAFT. It keeps
setup small enough for an enterprise architecture team to finish the first
useful pass, then lets the Draftsman capture the rest as follow-up work.

The goal is not to complete every architecture standard on day one. The goal is
to create a governed workspace where the Draftsman can interview users, reuse
approved choices, write valid DRAFT objects behind the scenes, and keep the
team aware of what is next.

## What Good Looks Like

After initial onboarding, the company should have:

- a private company DRAFT repo
- a vendored framework copy under `.draft/framework/`
- a root `README.md` with a copy/paste Draftsman start prompt
- tracked workspace metadata in `.draft/workspace.yaml`
- a small business taxonomy for catalog navigation
- advisory company vocabulary lists for the first governed choices
- one or more active RequirementGroups for new drafting work
- owners for the first mapped capabilities
- a starter acceptable-use technology baseline
- a few reusable deployable standards
- one real DraftingSession started from a product, system, repository,
  document, or diagram
- validation passing, or clear DraftingSession gaps for remaining work

## Repo-First Setup

DRAFT v1.0 does not require a DRAFT application or DRAFT-specific CLI. A
company starts by creating a private repo, vendoring the reviewed framework copy
under `.draft/framework/`, adding the root AI bootstrap files, and connecting
the AI tool the team already uses.

Once the AI is connected to the company repo, copy the prompt from the
workspace `README.md` or ask:

```text
I want a Draftsman session for this company DRAFT workspace.
```

The Draftsman should read `AGENTS.md`, `.draft/workspace.yaml`, the vendored
framework docs, schemas, and configuration before asking setup questions.

## Step 1: Create The Company Repo

Create a private company DRAFT repo. Treat it as source code: changes are
reviewed, validated, committed, and pushed through normal Git workflow.

At minimum, the repo should contain:

- `.draft/framework/` with the reviewed framework copy
- `.draft/workspace.yaml`
- `.draft/framework.lock`
- `README.md` with the first-run Draftsman prompt
- root AI bootstrap files such as `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`,
  `llms.txt`, and `.github/copilot-instructions.md`
- `catalog/`
- `configurations/`
- `docs/` for generated browser output

Use `templates/workspace/` from the framework as the source for the root
`README.md`, AI bootstrap, and workflow files. The connected AI can help copy
the templates, remove `.tmpl` suffixes, fill in company placeholders, and open
the initial workspace setup pull request.

Set `workspace.displayName` and `workspace.companyName` in
`.draft/workspace.yaml` before rendering templates when the company wants the
README and AI bootstrap files to use a friendly name instead of the repo name:

```yaml
workspace:
  name: acme-draft
  displayName: Acme DRAFT Workspace
  companyName: Acme
```

Also set `repository.provider`, `repository.owner`, `repository.name`, and
`repository.defaultBranch` before rendering templates when the company wants
the generated README prompt to tell an AI exactly which repo to connect to.

## Step 2: Start Setup Mode

In the connected AI tool, ask:

```text
I want a Draftsman session for this company DRAFT workspace.
```

The Draftsman should respond concisely with:

- current workspace state, in a sentence or two
- the next setup step
- one focused question

It should record anything to revisit as DraftingSession next steps rather than
displaying a running backlog of remaining work.

If the selected repo is the upstream framework repo instead of a company
workspace, the Draftsman must stop and ask for the company-specific repo path
before writing architecture content.

## Step 3: Define Business Navigation

Add enough business taxonomy to `.draft/workspace.yaml` for users to browse the
catalog by product area or business pillar.

Good first question:

```text
What are the first 3-7 business pillars or product groupings people should use
to find architecture?
```

Do not spend weeks perfecting taxonomy. Setup mode only needs the first useful
shape. Names can be revisited later.

## Step 4: Declare First Company Vocabulary Lists

Declare only the vocabulary lists the team is ready to govern. Start in
`advisory` mode so validation warns about non-standard values without blocking
the first useful drafting sessions.

Good first question:

```text
Which lists do we already know well enough to offer as choices: deployment
targets, data classifications, team identifiers, availability tiers, or failure
domains?
```

The highest-value starter lists are usually `teams` and `deploymentTargets`.
Data classification and availability tiers can follow when the enterprise
architecture or security team has accepted names. Move a list to `gated` only
when the company wants pull requests to fail on non-standard values.

If an engineer gives a real value that is not in a declared list, the Draftsman
should call it a non-standard value and ask whether to revisit later or submit a
vocabulary proposal for review.

## Step 5: Pick The Initial Governance Baseline

Activate the RequirementGroups that should guide new drafting work:

```yaml
requirements:
  activeRequirementGroups:
    - <requirement-group-uid>
  requireActiveRequirementGroupDisposition: false
```

Use `requireActiveRequirementGroupDisposition: false` while migrating existing
inventory. Set it to `true` only when the company is ready for validation to
require every in-scope object to record disposition against every active group.

Good first question:

```text
Which governance baseline should new objects address first: DRAFT-only,
SOC 2, TX-RAMP, NIST CSF, or a company-specific group?
```

## Step 6: Seed Acceptable-Use Technology

TechnologyComponents are vendor products, platforms, tools, runtimes, agents,
operating systems, and product versions. Capabilities describe reusable needs
such as authentication, logging, monitoring, patching, backup, compute, and
database.

The first useful baseline should map common capabilities to the TechnologyComponents the company already uses. Each mapped capability needs a company
owner who can approve lifecycle choices such as `preferred`, `existing-only`,
`candidate`, `deprecated`, and `retired`.

Good first question:

```text
Which enterprise standards should we seed first for identity, logging,
monitoring, patching, backup, compute, operating systems, database, and network?
```

## Step 7: Draft Baseline Deployable Standards

Draft reusable deployable objects in this order when possible:

1. TechnologyComponents for known products and versions
2. Hosts for operating system plus compute platform combinations
3. RuntimeServices for web, app, worker, messaging, cache, or runtime behavior
4. DataStoreServices for database, file, object, analytics, and storage
5. NetworkServices for WAF, firewall, load balancer, ingress, proxy, or
   API gateway behavior
6. ProductComponents for first-party runtime behavior
7. SoftwareDeploymentPatterns for complete product deployment shapes

Choose object type by behavior first. Then choose delivery model:

- `self-managed`
- `paas`
- `saas`
- `appliance`

PaaS, SaaS, and appliance are delivery models, not object types.

Good first question:

```text
Which common deployable standard should we draft first: Host, RuntimeService,
DataStoreService, or NetworkService?
```

## Step 8: Start The First Real DraftingSession

The first drafting session should be a guided conversation, not a YAML editing
exercise. Start with a real product, system, diagram, repository, or source
document.

The Draftsman should:

1. identify the product or system being described
2. extract observed components and deployment facts
3. separate observations from assumptions
4. search existing TechnologyComponents and deployable objects before creating
   new ones
5. identify applicable RequirementGroups from object type, delivery model, and
   workspace governance
6. ask focused follow-up questions for missing required facts
7. create or update DRAFT objects behind the scenes
8. run validation before presenting completed work

Unresolved facts should be stored in a DraftingSession, not hidden in prose.

Good first question:

```text
Which product, system, diagram, repository, or source document should we use
for the first guided DraftingSession?
```

## Step 9: Validate, Review, And Publish

Validation is the contract between conversation and source.

Run:

```bash
python3 .draft/framework/tools/validate.py --workspace .
```

Regenerate the browser:

```bash
python3 .draft/framework/tools/generate_browser.py --workspace . --output docs/index.html
```

Review the Git diff. Commit source YAML and generated browser output together
when the browser is published from the repo.

## Guided Conversation Rules

Every setup or drafting session should keep users oriented:

- state the intended outcome
- say what the repo already tells the Draftsman
- ask only for missing facts needed for the current step
- prefer multiple-choice questions when approved catalog options exist
- ask at most three questions at a time
- keep the live conversation focused on the current step; do not display a
  running backlog of remaining or revisit-later work
- record uncertainty as assumptions, unresolved questions, or DraftingSession
  next steps
- validate before claiming work is complete

Architects, engineers, and product teams should not receive the same interview.
Architects can handle governance and patterns. Engineers can answer concrete
runtime, dependency, platform, and operational questions. Product teams can
answer ownership, system boundaries, and user-facing capability questions.

## Keep The Framework Current

Framework updates are explicit. A company refreshes `.draft/framework/`,
reviews the diff, validates, and commits the update in the private repo.

Manual update:

```bash
git checkout -b draft/framework-refresh
# Replace .draft/framework/ with the reviewed framework version.
python3 .draft/framework/tools/validate.py --workspace .
```

Optional GitHub Actions can automate update branches and pull requests, but the
company still reviews the result before merging.
