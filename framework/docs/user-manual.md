# DRAFT User Manual

DRAFT is an AI-first, Git-native, repo-first framework for documenting governed architecture. It turns architecture conversations into structured YAML that lives in an ordinary Git repository, validates like code, and is reviewed in pull requests — with no DRAFT app, no hosted service, and no separate CLI.

---

## Part 1 — Why & What {#part-1}

### 1.1 What DRAFT replaces {#what-draft-replaces}

Most teams document architecture in Confluence pages, PowerPoint decks, or shared diagrams. Those artifacts go stale the moment the code changes, live outside the review process, and can't be queried or validated. DRAFT replaces them with YAML objects that live in the same repository as the work they describe.

### 1.2 What DRAFT actually is {#what-draft-is}

DRAFT is a framework for describing architecture as structured objects that can be validated, reviewed, searched, and eventually used as automation input. It separates four concerns:

| Concern | Where It Lives | Purpose |
|---|---|---|
| Framework rules | `.draft/framework/` in company workspaces, `framework/` upstream | Schemas, base capabilities, Requirement Groups, docs, and tools. |
| Company architecture | `catalog/` | Hosts, services, ProductComponents, DataComponents, Software Deployment Patterns, and other architecture inventory. |
| Company extensions | `configurations/` | Capability mappings, object patches, company Requirement Groups, and local domains. |
| Generated views | `docs/` | Static HTML, browser assets, and browser data generated from YAML and Markdown source. |

Framework files are not normal authoring targets inside a company workspace. Update them only through an explicit framework refresh or framework change. Architecture content belongs in the company workspace.

DRAFT object model — architecture objects, governance objects, and their core relationships:

![DRAFT object model UML class diagram](assets/draft-object-model.svg)

### 1.3 Who benefits {#who-benefits}

DRAFT is written for three audiences who work together on every PR:

**Engineers** connect the AI tool they already use to the repository and describe what they ship. The Draftsman handles schema details. Engineers review YAML diffs, not documentation tickets.

**Security and compliance teams** get requirement evidence recorded at authoring time, not assembled after an audit. Requirement Groups ask mandatory questions; objects cannot be marked approved until the evidence is present.

**Architects** maintain a governed catalog of real deployments instead of diagrams that diverge from reality. The catalog browser gives a searchable, versioned view of the whole estate.

---

## Part 2 — The Draftsman Experience {#part-2}

### 2.1 What authoring feels like {#authoring-feel}

DRAFT authoring is a conversation. An engineer opens a PR, the AI assistant connected to the repository acts as the Draftsman, and the two of them work through what the product deploys, what it depends on, and what requirements it satisfies. The output is YAML. The review is a normal pull request diff.

There is no DRAFT web application to log into. There is no catalog portal to maintain separately. The catalog is the repository.

### 2.2 The authoring loop {#authoring-loop}

Follow this loop for most changes:

1. Search the browser and YAML for an existing object.
2. Choose the correct object type before writing fields.
3. Start from the closest template or nearby approved object.
4. Fill in required schema fields.
5. Add relationships to existing objects by UID.
6. Add Requirement Group evidence or architectural decisions.
7. Run validation.
8. Regenerate the browser and manual.
9. Review source and generated diffs.

Use `rg` or the browser search before adding new objects. Duplicate objects make requirement validation harder.

### 2.3 Review as code {#review-as-code}

The YAML diff and the generated browser diff are reviewed together. The browser diff shows whether the catalog view changed in an expected way. The YAML diff shows the authoritative source of truth. Neither replaces the other.

Do not hand-edit `docs/index.html`, `docs/assets/`, or `docs/user-manual.html`. They are generated outputs. Regenerate and commit them with the source changes when the repo expects generated docs to be committed.

### 2.4 The role of the AI {#role-of-ai}

DRAFT is AI-first, but AI behavior depends on the tool being used. An AI assistant can act as the Draftsman only when it has repository access, can read the bootstrap files, and has permission to write changes.

The bootstrap chain is:

1. root `AGENTS.md`
2. framework `AGENTS.md`
3. `framework/docs/draftsman.md`
4. `AI_INDEX.md`
5. schemas, templates, capabilities, Requirement Groups, and nearby catalog examples

AI assistants should:

- read the bootstrap before authoring
- ask for a company workspace before creating company content when connected only to the upstream framework repo
- avoid editing vendored `.draft/framework/**` files during normal company authoring
- use generated UIDs instead of inventing semantic IDs
- prefer existing approved capability mappings before proposing new components
- run validation and regenerate docs when changing source content

If an AI assistant is connected only to the upstream framework repo and the user asks to create company architecture content, the assistant should ask for the company-specific DRAFT workspace before writing content.

---

## Part 3 — The Model {#part-3}

### 3a · Objects {#part-3a}

#### 3a.1 The object model {#object-model}

DRAFT objects are YAML documents with generated opaque UIDs. Do not ask humans to create semantic IDs. Use human-readable `name`, `aliases`, and file paths for conversation, and use the repair tool when validation reports missing or malformed UIDs.

```bash
python .draft/framework/tools/repair_uids.py --workspace .
```

Use the object model diagram as the quickest reference for how the major object types relate to each other.

![DRAFT object model UML class diagram](assets/draft-object-model.svg)

#### 3a.2 Engineering objects {#engineering-objects}

Engineering objects represent first-party software components authored by the
engineering team. They are deployed inside or on top of Architecture Objects.

| Object Type | Use It For |
|---|---|
| ProductComponent | A first-party deployable runtime unit — API, worker, scheduler, or service — that uses `runsOn` to reference the RuntimeService, Host, or EdgeGatewayService it is deployed on. |
| DataComponent | A first-party data schema, dataset, or storage unit that uses `runsOn` to reference the DataStoreService it is deployed on. |
| Software Deployment Pattern | The intended assembly of deployable objects for a product or product capability. |

#### 3a.3 Architecture objects {#architecture-objects}

Architecture Objects are reusable infrastructure-level services that Engineering
Objects run on or connect to.

| Object Type | Use It For |
|---|---|
| Technology Component | A governed vendor product, operating system, compute platform, agent, appliance product, software package, or product/version building block. |
| Host | An operational platform that combines compute, operating system, and required host capabilities. |
| Runtime Service | Reusable runtime behavior such as web, app, cache, worker, messaging, or serverless runtime. |
| DataStoreService | Durable data behavior such as database, file, object, search, analytics, or storage. |
| Edge/Gateway Service | Boundary behavior such as WAF, firewall, API gateway, load balancer, ingress, proxy, or traffic inspection. |
| Reference Architecture | A reusable deployment approach that Software Deployment Patterns may follow. |

Technology Components are governed building blocks. They are deployed as ingredients inside hosts and services, but they are not usually the service boundary you review on their own.

#### 3a.4 Governance objects {#governance-objects}

| Object Type | Use It For |
|---|---|
| Capability | A reusable architecture need such as authentication, backup strategy, log management, operating system, or patch management. |
| Requirement Group | A requirement set that asks questions, defines acceptable evidence, and validates object completeness. |
| Domain | A strategy grouping for related capabilities. |
| Decision Record | A record of a known risk, accepted decision, mitigation, or follow-up. |
| Drafting Session | A machine-readable work-in-progress record for partial authoring sessions. |
| Object Patch | A workspace overlay that deep-merges selected company fields into a framework-owned object. |

#### 3a.5 Repository ownership {#repo-ownership}

Use this decision table before editing:

| Need | Edit |
|---|---|
| Add or update company architecture inventory | `catalog/` |
| Map a framework capability to company-approved Technology Components | `configurations/object-patches/` or company-owned `configurations/capabilities/` |
| Add a company Requirement Group | `configurations/requirement-groups/` |
| Adjust selected fields on a framework object without copying it | `configurations/object-patches/` |
| Change schema, validation, tools, or framework documentation | upstream framework repo |
| Change the static browser output | source YAML, Markdown, or generator code, then regenerate |
| Change company browser colors or branding | company-owned `configurations/browser/theme.css` |

#### 3a.6 Modeling Technology Components {#modeling-technology-components}

Create a Technology Component when you need to govern a specific product, product family, product version, operating system, compute platform, agent, appliance, or software package.

A Technology Component should usually include:

- `vendor`
- `productName`
- `productVersion`
- `classification`
- lifecycle facts about the vendor product
- capabilities the component can satisfy
- named `configurations` when different approved variants matter

Use top-level `capabilities` when the product generally satisfies a capability. Use configuration-level capabilities when only a named variant satisfies the capability.

**Network Bindings.** Technology Component configurations can include `networkBindings` for known ports, protocols, and traffic direction. Use this for component-level facts such as a database engine listening on TCP 1433 or a message broker listening on AMQP 5672.

```yaml
configurations:
  - id: default-listener
    name: Default listener
    networkBindings:
      - port: 1433
        protocol: TCP
        direction: inbound
        description: Default SQL Server listener.
```

When a host or service consumes a specific configuration, reference it from the internal component entry:

```yaml
internalComponents:
  - ref: 01ABCDEFGH-1234
    role: database engine
    configuration: default-listener
```

#### 3a.7 Modeling Hosts and Services {#modeling-hosts-services}

Hosts describe operational platforms. A useful Host normally references operating system and compute Technology Components, then documents required host capabilities such as monitoring, logging, patching, identity integration, backup, and security tooling.

Runtime Service, DataStoreService, and Edge/Gateway Service objects describe reusable behavior delivered through a delivery model:

- `self-managed`
- `paas`
- `saas`
- `appliance`

For Runtime, DataStoreService, and Edge/Gateway Services, the primary Technology Component is the main functional component. Do not add a separate dependency rationale for the primary component when it is the object core.

DataStoreServices should document backup strategy, backup platform, RTO, and RPO. Use an external interaction for a separate backup platform, or use `architectureNotes.backup.platform` when the backup capability is provider-managed inside the service.

#### 3a.8 Modeling ProductComponents {#modeling-product-components}

A ProductComponent represents a first-party deployable runtime unit — an API, worker, scheduler, conductor, or service binary — authored by the engineering team.

At minimum, a ProductComponent needs:

- `schemaVersion`
- `uid`
- `type: product_component`
- `name`
- `runsOn` — referencing the RuntimeService, Host, or EdgeGatewayService it is deployed on
- `catalogStatus`
- `lifecycleStatus`

Use ProductComponent fields to document:

- internal components consumed by the product
- external interactions the product depends on
- deployment configurations such as single-tenant, multi-tenant, embedded, or standalone variants
- architectural decisions that explain requirements or non-obvious dependencies

Don't elevate static assets, build scripts, or simple product configuration to ProductComponent. The boundary is first-party runtime behavior that a Software Deployment Pattern needs to communicate.

#### 3a.9 Modeling DataComponents {#modeling-data-components}

A DataComponent represents a first-party data schema, dataset, or storage unit that lives inside a DataStoreService.

At minimum, a DataComponent needs:

- `schemaVersion`
- `uid`
- `type: data_component`
- `name`
- `runsOn` — referencing the DataStoreService it is deployed on
- `catalogStatus`
- `lifecycleStatus`

Use DataComponent fields to document:

- internal components (Technology Components) used inside the data layer
- external interactions the data layer depends on
- architectural decisions about data classification, retention, or encryption

#### 3a.10 Modeling Software Deployment Patterns {#modeling-sdps}

A Software Deployment Pattern is the product-level assembly. It answers what a product deploys and how those objects relate.

A good Software Deployment Pattern includes:

- product or capability name
- service groups
- deployment targets
- deployable object references
- network zone assignments for presentation, application, data, or utility placement
- source repository provenance when the pattern is generated from repository discovery
- decisions or assumptions that explain uncertain boundaries

Don't stop when the Software Deployment Pattern validates. Walk the full object graph and make sure every referenced Host, Service, ProductComponent, DataComponent, Technology Component, and dependency is valid enough for review.

---

### 3b · Requirements-based definitions {#part-3b}

#### 3b.1 Capabilities and Requirement Groups {#capabilities-requirement-groups}

Capabilities describe what an architecture must be able to do. Requirement Groups describe which questions must be answered and which mechanisms can satisfy them.

Requirement Groups can be:

- always-on for matching object types
- workspace-mode groups activated in `.draft/workspace.yaml`
- company or compliance groups declared by specific objects in `requirementGroups`

An object that declares a Requirement Group must provide valid `requirementImplementations` for the applicable requirements before it can be treated as approved for that group.

When validation says a requirement is missing, either add the evidence that directly satisfies it or record an explicit disposition such as `not-applicable` or `not-compliant` when the schema and Requirement Group allow it.

#### 3b.2 Acceptable evidence {#acceptable-evidence}

Requirements can be satisfied by mechanisms such as:

- a Technology Component
- a named Technology Component configuration
- an internal component
- an external interaction
- a deployment configuration
- a field value
- an architectural decision

#### 3b.3 Dependency rationale rule {#dependency-rationale}

Every `internalComponents` entry and `externalInteractions` entry must either directly satisfy an applicable requirement or have an architectural decision explaining why it is modeled.

Use these machine-readable buckets:

- `architectureNotes.externalInteractionRationales`
- `architectureNotes.internalComponentRationales`
- `architectureNotes.dependencyRationales`

Use stable keys such as the interaction name, component `ref`, `enabledBy`, role, or capability ID.

```yaml
architectureNotes:
  externalInteractionRationales:
    Dynatrace Platform: Dynatrace is modeled because the local agent sends telemetry to the platform; it does not satisfy the host health monitoring requirement by itself.
```

If the dependency is intended to satisfy a requirement, add the matching capability or `requirementImplementations` evidence instead of adding rationale.

#### 3b.4 Agent rule {#agent-rule}

Agent Technology Components have an additional rule: any deployable object that includes an agent must document the corresponding external interaction for the agent's platform or record an exception under `architectureNotes.agentInteractionExceptions`.

---

## Part 4 — Setup {#part-4}

### 4.1 Repository layout {#repo-layout}

| Concern | Where It Lives | Purpose |
|---|---|---|
| Framework rules | `.draft/framework/` in company workspaces, `framework/` upstream | Schemas, base capabilities, Requirement Groups, docs, and tools. |
| Company architecture | `catalog/` | Hosts, services, ProductComponents, DataComponents, Software Deployment Patterns, and other architecture inventory. |
| Company extensions | `configurations/` | Capability mappings, object patches, company Requirement Groups, and local domains. |
| Generated views | `docs/` | Static HTML, browser assets, and browser data generated from YAML and Markdown source. |

### 4.2 Start setup mode {#setup-mode}

Setup mode is the Draftsman first-run path for making a company workspace useful without overwhelming architects, engineers, or product teams.

Start it by asking the AI assistant connected to the company repo:

```text
start setup mode
```

Setup mode keeps the conversation oriented around:

- current step
- next step
- remaining setup work
- revisit-later decisions
- one focused question, or at most three questions when choices are needed

The minimum useful setup is:

1. private company repo selected and `.draft/framework/` present
2. business taxonomy defined enough for navigation
3. first company vocabulary lists declared in advisory mode, or queued for later
4. initial active Requirement Groups selected
5. capability owners identified for mapped capabilities
6. acceptable-use Technology Components seeded for common standards
7. baseline deployable standards started
8. one real product, system, repository, diagram, or document selected for the first Drafting Session

The Draftsman should record uncertainty as assumptions, unresolved questions, or Drafting Session next steps instead of forcing complete answers during setup.

### 4.3 Commands {#commands}

**Company workspace:**

```bash
python .draft/framework/tools/validate.py --workspace .
python .draft/framework/tools/generate_browser.py --workspace . --output docs/index.html
```

**Framework repository:**

```bash
python framework/tools/validate.py
python framework/tools/generate_browser.py
python framework/tools/generate_ai_index.py
```

The browser generator writes `docs/index.html` and, by default, writes this manual to `docs/user-manual.html`.

### 4.4 Validation {#validation}

Run validation before treating a change as ready.

**Company workspace:**

```bash
python .draft/framework/tools/validate.py --workspace .
```

**Framework repository:**

```bash
python framework/tools/validate.py
```

Common failure categories:

| Failure | Usual Fix |
|---|---|
| Missing required field | Add the field required by the object schema. |
| Unknown reference | Use an existing UID or add the referenced object. |
| Invalid lifecycle or status | Use the enum values from the schema. |
| Missing requirement evidence | Add valid `requirementImplementations` or a supported disposition. |
| Unexplained dependency | Add requirement evidence or a dependency rationale. |
| Agent without platform interaction | Add the external interaction or an agent interaction exception. |
| UID issue | Run `repair_uids.py` and review the diff. |

Warnings are still useful. A warning usually means the object can be parsed but is incomplete, ambiguous, or not ready for review.

### 4.5 Regenerate the browser and manual {#regenerate}

The static browser and manual are generated from YAML source and framework metadata.

**Company workspace:**

```bash
python .draft/framework/tools/generate_browser.py --workspace . --output docs/index.html
```

**Framework repository:**

```bash
python framework/tools/generate_browser.py
```

The browser shell, CSS, JavaScript, and default theme live in the framework under `browser/`. Generated catalog data is written separately to `docs/assets/browser-data.js`, which keeps content diffs separate from display framework changes.

Use `--refresh-shell` to force-overwrite all browser shell assets from the framework source when pulling a framework design update.

GitHub Actions workflows typically regenerate derived docs on pushes that change YAML, framework docs, templates, the browser generator, AI bootstrap files, or README content. Check the local `.github/workflows/` files for the exact path filters in a given repo.

#### Map presets {#map-presets}

The Deployment Targets view renders an interactive world map. A workspace can configure which map view opens by default and users can switch between presets with the toggle buttons in the view header.

Available presets:

| Preset ID | Label | When to use |
|---|---|---|
| `world` | 🌐 World | Organizations with global or multi-continent deployments (default) |
| `north-america` | 🌎 N. America | Organizations whose infrastructure is entirely in North America |
| `europe` | 🌍 Europe | Organizations whose infrastructure is primarily in Europe |
| `asia` | 🌏 Asia | Organizations whose infrastructure is primarily in Asia-Pacific |

To set the default for a workspace, add a `browser` section to `workspace.yaml`:

```yaml
browser:
  defaultMapView: north-america   # or 'world' (the default when this key is absent)
```

The generator validates the value and falls back to `world` for unrecognized preset IDs. Users can always switch presets at any time using the toggle; the choice resets to the workspace default the next time the view is entered.

### 4.6 Theme the browser {#theme}

Company workspaces can add `configurations/browser/theme.css` to override stable CSS variables without editing `.draft/framework/**`. The generator copies that file to `docs/assets/workspace-theme.css` after the default browser stylesheet, so company theme values win through normal CSS cascade.

```css
:root {
  --accent: #005eb8;
  --accent-strong: #003b71;
  --accent-soft: rgba(0, 94, 184, 0.12);
  --blue: #0072ce;
}
```

### 4.7 Review checklist {#review-checklist}

Before merging a DRAFT change, check:

- the object type is correct
- no duplicate object already exists
- required schema fields are present
- references point to real objects
- Technology Components are specific enough to govern
- ProductComponents represent first-party runtime behavior and use `runsOn` to reference a RuntimeService, Host, or EdgeGatewayService
- DataComponents represent first-party data schemas or datasets and use `runsOn` to reference a DataStoreService
- Requirement Groups and implementations are coherent
- internal components and external interactions either satisfy requirements or have rationale
- generated docs were regenerated from source
- framework files were changed only when the change is intentionally a framework change

### 4.8 Troubleshooting {#troubleshooting}

**Browser does not show a new object.** Verify the file is under a discovered folder such as `catalog/hosts/`, `catalog/runtime-services/`, `catalog/data-store-services/`, `catalog/product-components/`, or `configurations/capabilities/`, and confirm the YAML has a valid `uid`.

**Validation cannot find framework objects in a company workspace.** Confirm the vendored framework exists at `.draft/framework/` and run validation with `--workspace .`.

**AI assistant starts editing framework files in a company repo.** Stop and redirect it to the company-owned `catalog/` or `configurations/` paths unless the task is explicitly a framework refresh.

**Generated file looks stale.** Rerun the generator locally and check whether the repo's workflow also stages that generated file.
