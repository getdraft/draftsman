---
type: documentation
title: "Decentralized SDPs & Product Registration"
description: "How product engineering teams keep SoftwareDeploymentPatterns in their own repos, register with drafting-table, and sync them through a tested, pull-request-based pipeline."
tags:
  - draft
  - documentation
  - sdp
  - decentralization
  - product_registration
timestamp: 2026-11-25T00:00:00-07:00
---

# Decentralized SoftwareDeploymentPatterns & Product Registration

## Architectural Overview

DRAFT 1.0 establishes a clean line of demarcation across three content groups:

1. **Product Content (Product Engineering)**: Housed inside individual product repositories (`.draft/sdp.yaml` and `.draft/catalog/`) and registered centrally via `ProductRegistration` objects in `drafting-table`.
2. **Shared Services & Infrastructure (Internal Providers)**: Housed centrally in `drafting-table` (`catalog/shared-services/`). Internal platform teams document hosts, runtimes, data stores, networks, and technology components here for product teams to consume.
3. **External Provider Hooks (Third-Party SaaS/PaaS)**: Governed under `.draft/providers/` and SaaS/PaaS delivery models.

The product repository is the source of truth for its own content. The central workspace keeps a cached copy, checks it, and publishes it through a pull request. `drafting-table` never holds credentials for product repositories.

## How a Sync Works

All of the logic lives in one tested tool, `framework/tools/sdp_sync.py`. The two workflow templates only call it.

1. A push to the product repository's default branch that changes `.draft/sdp.yaml` or `.draft/catalog/**` starts **Sync SDP to Central DRAFT Workspace** (`templates/github/product-repo-sync.yml.tmpl`).
2. `sdp_sync.py pack` collects `.draft/sdp.yaml` and every YAML file under `.draft/catalog/`, checks them, and attaches a GitHub Actions OIDC token addressed to the central workspace.
3. The workflow sends the payload to the central repository as a `repository_dispatch` event (`sdp_updated`), using a short-lived GitHub App token.
4. In `drafting-table`, **DRAFT Decentralized SDP Receiver** (`templates/github/drafting-table-receiver.yml.tmpl`) runs `sdp_sync.py receive`, which verifies the token and the payload and stores the files in the product's cache folder.
5. The receiver runs `validate.py`, regenerates the indexes, and `sdp_sync.py publish` opens or updates the product's pull request.
6. `sdp_sync.py report` records the outcome. Back in the product repository, `sdp_sync.py await-result` waits for that outcome and fails the product's run with the receiver's message if the sync was rejected or did not validate.

No step puts a payload value into shell text: values reach scripts only through environment variables and files, and template tests enforce it.

## One-Time Setup

### 1. Central workspace (`drafting-table`)

1. Copy `templates/github/drafting-table-receiver.yml.tmpl` to `.github/workflows/draft-sdp-receiver.yml`. The workspace must have the framework vendored at `.draft/framework/` (the receiver runs the tools from there).
2. In **Settings → Actions → General**, enable **Allow GitHub Actions to create and approve pull requests**. Without it, the publish step fails and the product run reports the failure.
3. Optional: to let syncs that only touch a product's cache merge themselves, enable **Allow auto-merge** (Settings → General) and set the repository variable `DRAFT_SYNC_AUTO_MERGE` to `true`. See [Pull requests and required checks](#pull-requests-and-required-checks) first.

### 2. GitHub App

Create (or reuse) one GitHub App for DRAFT sync:

* **Repository permissions:** *Contents: Read and write*. Nothing else. Contents write is what `repository_dispatch` requires; the same access lets the product run read its result from the central repository.
* **Install it on the central repository only.** It needs no access to any product repository.
* In each product repository (or once at the organization level), store the App's ID as the secret `DRAFT_APP_ID`, its private key as `DRAFT_APP_PRIVATE_KEY`, and the central repository's name (without the owner) as `DRAFT_CENTRAL_REPO_NAME`. The central repository must have the same owner as the product repository.

### 3. Product registration

A Draft Admin registers each product with a `product_registration` file under `catalog/engineering/product-registrations/product-reg-<name>.yaml`:

```yaml
schemaVersion: '1.0'
uid: 01M7EXMP01-PR01
type: product_registration
name: Absence Management
catalogStatus: complete
owner:
  team: product-absence-time
  contact: absence-team@example.com
businessContext:
  pillar: business-pillar.people-solutions
  productFamily: Absence & Time
repository:
  provider: github
  url: https://github.com/company/absence-service
  defaultBranch: main
  id: 123456789
  ownerId: 1234567
sdpManifest:
  mode: git
  path: .draft/sdp.yaml
```

* `repository.url` decides which repository may sync this product. Any common GitHub form works (`https://…`, `.git`, `git@github.com:…`); names compare case-insensitively. Exactly one registration may name a repository.
* `repository.defaultBranch` is **required**: only pushes to that branch can sync.
* `repository.id` is GitHub's permanent numeric repository id (the OIDC `repository_id` claim). It is optional. When it is set, `receive` rejects a token whose `repository_id` is missing or different, so a repository that was deleted and recreated with the same name cannot sync as this product. A renamed repository still syncs: update `repository.url` to the new name and leave `repository.id` as it was. When it is omitted, `receive` still accepts the name match and the accepted result carries a warning asking a Draft Admin to pin it. Write a positive integer or a decimal digit string with no leading zeros. Look it up with `gh api repos/OWNER/NAME --jq .id`. The receiver never writes this field. Copying the id out of a sync warning would trust whoever sent that sync, so look the id up for the repository you mean to register.
* `repository.ownerId` is GitHub's permanent numeric owner id (the OIDC `repository_owner_id` claim), from `gh api repos/OWNER/NAME --jq .owner.id`. It is optional and is checked only when set. It does not replace `repository.id`: a new repository in the same organization has a new repository id and the same owner id. The example numbers above are placeholders; replace them with the values GitHub returns, or omit both lines.

### 4. Product repository

1. Copy `templates/github/product-repo-sync.yml.tmpl` to `.github/workflows/draft-sync.yml`. Its job already has `permissions: id-token: write` (for the OIDC token) and `contents: read`.
2. Optional repository variables:
   * `DRAFT_FRAMEWORK_REF`: the framework tag the sender's tool is checked out at (default `main`). Pin it to the central workspace's framework version.
   * `DRAFT_SYNC_AWAIT_MINUTES`: how long the run waits for the central result (default 20).
3. Keep the product's SDP in `.draft/sdp.yaml` and its own objects in `.draft/catalog/`:

```yaml
schemaVersion: '1.0'
uid: 01M7EXMP03-SDP1
type: software_deployment_pattern
name: Absence Management Production Deployment
catalogStatus: complete
lifecycleStatus: preferred
businessContext:
  pillar: business-pillar.people-solutions
  productFamily: Absence & Time
serviceGroups:
  - name: Application Services
    deploymentTarget: aws-us-east-1
    deployableObjects:
      - ref: 01M7EXMP02-PC01
        diagramTier: application
```

## Tokens and Permissions

| Credential | Where | Permissions | Used for |
| --- | --- | --- | --- |
| GitHub App installation token | Product run | Contents: read and write, central repository only, about 60 minutes | Sending the `repository_dispatch` event; reading the result file |
| GitHub Actions OIDC token | Product run (`id-token: write`) | None: it is a signed statement of who is sending | Proving the sync comes from the registered repository's default branch |
| `GITHUB_TOKEN` | Central receiver run | `contents: write`, `pull-requests: write` | Pushing the `draft-sync/<product>` branch, opening its pull request, writing the result file |

**OIDC audience.** The sender asks for a token with audience `draft-sdp-sync:<central owner>/<central name>` (lowercase), and the receiver accepts only that audience, so a token minted for one central workspace cannot be used against another. The receiver verifies the token's RS256 signature against GitHub's published keys (`https://token.actions.githubusercontent.com/.well-known/jwks`) using the Python standard library, and checks the issuer, the audience, the expiry (60 seconds of clock skew allowed), that the token's `repository` is the payload's registered repository, that its `ref` is `refs/heads/<defaultBranch>`, and that its `ref` and `sha` match the payload's. When the registration sets `repository.id` or `repository.ownerId`, the token's `repository_id` or `repository_owner_id` must be that same number (an integer or a decimal digit string). The receiver run needs outbound HTTPS to `token.actions.githubusercontent.com` (GitHub-hosted runners have it).

## Payload Format

The `client_payload` of the `sdp_updated` event is a `draft-sdp-sync/1` object:

| Field | Meaning |
| --- | --- |
| `format` | `draft-sdp-sync/1` |
| `repository` | The product repository, `owner/name` |
| `commit` | The commit SHA that was synced |
| `ref` | The branch ref, `refs/heads/<defaultBranch>` |
| `action` | `upsert`, or `delete` when `.draft/sdp.yaml` no longer exists |
| `correlationId` | `<run id>-<run attempt>` of the product run; ties the central outcome back to it |
| `files` | Map of repository path to file text: `.draft/sdp.yaml` and `.draft/catalog/**/*.yaml` |
| `oidcToken` | The GitHub Actions OIDC token |

GitHub limits `client_payload` to 10 top-level properties and 64 KB. `pack` refuses a payload over 65,000 bytes; shorten descriptions and notes, or split the product into several registrations.

`pack` also refuses, before anything is sent: object types a product does not own, hidden paths, unreadable YAML, and symbolic links inside `.draft/catalog/`. Files under `.draft/catalog/` that are not YAML (a README, for example) are ignored.

## What the Receiver Accepts

`receive` checks, in order, and on the first failure writes nothing and names the reason:

1. **Payload shape:** format, repository name, commit SHA, ref, action, correlation id, files, and the token's presence. A payload in the old `sdp_content` shape is refused with a request to update the template.
2. **Sender identity:** the OIDC checks above. After the token verifies for the registered repository name, a pinned `repository.id` or `repository.ownerId` must match. A mismatch is reported back to the product run. Omitting `repository.id` keeps the name match and adds a warning.
3. **Registration:** exactly one `product_registration` under the central `catalog/` names the repository.
4. **Paths:** only `.draft/sdp.yaml` and YAML under `.draft/catalog/`, stored only inside the product's cache folder.
5. **Types:** only `software_deployment_pattern`, `product_component`, `data_component`, `listener`, `relationship` and `decision_record`. Systems, shared services, hosts, registrations, requirement groups and other central content are never accepted from a product.
6. **Ownership:** every object has a UID that is unique in the sync and is not owned by the central catalog or another product. A relationship's `source`, a listener's `owner.ref` and a decision record's `linkedObject` must be objects in the same sync: a product only speaks for its own objects.
7. **References:** every UID an object mentions must be in the same sync or already resolve in the central workspace (framework and provider configurations, `catalog/`, community content, or another product's cache). The product's own previous snapshot does not count, so a reference to something the product stopped syncing is caught. The error lists each file and its missing UIDs.

## Cache Layout

Accepted files are stored under `.draft/external_sdps/<owner>__<name>/` (lowercase):

```text
.draft/external_sdps/company__absence-service/
  sdp.yaml                    # from .draft/sdp.yaml
  catalog/...                 # from .draft/catalog/..., same relative paths
```

Each sync replaces the folder as a snapshot, so a file removed from the product repository disappears from the cache. `validate.py` and the indexes read these folders with the rest of the workspace.

## Pull Requests and Required Checks

Nothing is pushed to the central default branch. `sdp_sync.py publish` commits the receiver's changes to a branch named `draft-sync/<owner>__<name>`, built fresh on top of the default branch for every sync and force-updated (the branch belongs to the receiver), and opens one pull request per product. Later syncs update the same pull request. The central catalog changes when someone merges it.

With `DRAFT_SYNC_AUTO_MERGE=true`, `publish` requests squash auto-merge **only** when every changed file is inside that product's cache folder (or its old flat file), apart from the two regenerated index files (`docs/assets/draft-indexes.json` and `.draft/AI_INDEX.md`). If a later sync changes anything else, auto-merge is turned off on that pull request so a reviewer sees it. If auto-merge cannot be enabled (for example, the repository setting is off), the pull request stays open and the result says so.

Receiver runs are serialized (`concurrency: draft-sdp-sync`), so two syncs never race on the indexes or a pull request.

**Required status checks do not run on these pull requests.** The receiver opens them with `GITHUB_TOKEN`, and GitHub does not start other workflows for events caused by `GITHUB_TOKEN`. If the default branch requires status checks, a sync pull request waits for checks that never start, and auto-merge never completes. Choose one:

* Don't require status checks on the central default branch, and rely on the receiver's own validation, which already ran on exactly this content before the pull request was opened (a required review still applies); or
* Keep the checks required and have a person start them on each sync pull request (closing and reopening it, or pushing a commit to its branch, starts `pull_request` workflows), then merge; auto-merge is then not useful.

## How Failures Reach the Product Team

The receiver's last step, `sdp_sync.py report`, runs even when an earlier step failed. It turns the run into one outcome:

* **accepted:** stored, validated, and the pull request opened or updated (its link is included), or the workspace already matched;
* **rejected:** `receive` refused the payload; the reason is included;
* **failed:** the workspace did not validate with the sync (the failures are listed, the product's own files first), the pull request could not be opened, or the run stopped early.

Every outcome is written to the central run's job summary. When the sender's identity was verified, it is also saved as `results/<owner>__<name>/<correlationId>.json` on the `draft-sync-results` branch of the central repository (created from the default branch on first use). A pinned `repository.id` or `repository.ownerId` is checked only after that verification, so a mismatch is one of these results and the product run fails with the reason. In the product repository, **Await Central Result** polls exactly that file with the App token, then shows the outcome in its job summary. If the outcome is not *accepted*, it fails the product run with an error annotation carrying the message, the failures, and a link to the central run. An accepted sync whose registration has no `repository.id` stays accepted; the message includes the warning, and the product run does not fail for that warning.

Payloads rejected *before* the identity check (an old template, a malformed payload, a token that does not verify) are shown only in the central run's summary: an unverified sender must not be able to write a result where another product will read it. The product run then times out with a hint to check the central repository's Actions.

Result files are small and accumulate, one per sync. The `draft-sync-results` branch can be deleted at any time; the next report recreates it.

## Deletion

Deleting `.draft/sdp.yaml` from the product repository sends a `delete`. The receiver removes everything it caches for that product, catalog objects included, even if `.draft/catalog/` still has files, and opens a pull request that removes them centrally. Central objects that referenced the product's components become dangling; `validate.py` reports them. To stop syncing without deleting, remove or disable the sync workflow instead.

## Security Notes and Known Limits

* **A live OIDC token can be resent within its lifetime.** GitHub's OIDC tokens cannot carry a hash of the payload, so the receiver binds a token to its repository, ref and commit (`sha`) only. Anyone who obtains a live token could, during its few-minute lifetime, send different files for that same commit. The token travels only inside the central repository's `repository_dispatch` event, which is visible to people and workflows with access to that repository (the event payload is available to its workflow runs); it is never written to the cache, the result file or the logs. Exploiting it therefore needs existing access to the central repository. Mitigations: keep write and Actions access to the central repository tight, keep the App installed only there, and rely on the pull-request flow so every change reaches a reviewer (do not enable auto-merge if that review is your control).
* **Pin `repository.id`.** GitHub never reuses `repository_id`, and it survives a rename. Once a registration sets it, a deleted or transferred repository that is recreated with the same `owner/name` fails the identity check. Until a Draft Admin sets it, the receiver still matches by repository name and records a warning on the accepted result. `repository.ownerId` is a second pin, checked only when set; it does not stop a new repository in the same organization. Remove the registration when a product repository is retired. The receiver does not copy the token's id into the catalog.
* **Validation failures may include problems already in the central workspace.** The product's own files are listed first; anything else is for a Draft Admin.

## Troubleshooting

| Message (product run or central summary) | What to do |
| --- | --- |
| `no ProductRegistration in catalog/ has repository.url …` | A Draft Admin adds or fixes the product's registration. |
| `… has no repository.defaultBranch` | Set `repository.defaultBranch` on the registration. |
| `only the registered default branch (refs/heads/…) can sync` | Sync from the registered branch, or correct `defaultBranch`. |
| `the OIDC token's repository_id is …, not … pinned` | The sending repository is not the pinned GitHub repository. A recreated repository cannot sync as this product. After a rename, update `repository.url` and keep `repository.id`. |
| `the OIDC token's repository_owner_id is …, not … pinned` | `repository.ownerId` does not match the token. Update it when the repository's owner changed, and keep `repository.id`. |
| `repository.id … is not a GitHub id` / `repository.ownerId … is not a GitHub id` | Set the field to the positive integer from `gh api`, or remove it. |
| `repository.id is not pinned` | Warning only; the sync was accepted. Pin `repository.id` and `repository.ownerId` on the registration. |
| `the payload carries no OIDC token` / `old sdp_content format` | Update the product's sync workflow from the current template. |
| `the OIDC token is for audience …, not this central workspace` | `DRAFT_CENTRAL_REPO_NAME` names a different central repository. |
| `the OIDC token has expired` | The receiver was queued too long; re-run the product's sync workflow. |
| `could not fetch GitHub's OIDC key set` | The receiver runner cannot reach `token.actions.githubusercontent.com`. |
| `uid … is already owned by …` | The object belongs to the central catalog or another product; reference it instead of syncing a copy. |
| `a product repository cannot sync a '…' object` | Move central content (systems, shared services, registrations) to the central workspace. |
| `unresolved references: …` | Sync the missing object too, ask for it to be registered centrally, or fix the UID. |
| `the central workspace does not validate with this sync` | Fix the listed failures in the product repository and push again. |
| `opening its pull request failed` | Enable "Allow GitHub Actions to create and approve pull requests" in the central repository. |
| `no result from the central receiver after … seconds` | Check the central repository's Actions: the run may be queued, or the payload was rejected before the identity check (see its summary). Raise `DRAFT_SYNC_AWAIT_MINUTES` if syncs queue. |
| `reading the central result failed with HTTP 403` | The App lacks Contents access to the central repository, or is not installed there. |
| `the payload is … bytes; repository_dispatch accepts at most 65000` | Shorten text in `.draft/` files, or split the product. |

## Upgrading from the Original Sync

The original templates sent only `.draft/sdp.yaml` as a JSON string, wrote it to a flat file `.draft/external_sdps/<owner>_<name>.yaml`, and committed straight to the central default branch. To upgrade:

1. **Register every syncing product** with `repository.url` and `repository.defaultBranch` (above). Unregistered products are rejected. Set `repository.id` and `repository.ownerId` from `gh api repos/OWNER/NAME` when you can. Until `repository.id` is set, syncs are accepted with a warning and still match by name.
2. **Check content ownership.** Products must not sync copies of objects the central catalog already holds; reference them instead. Every UID a product's files mention must resolve.
3. **Update the central receiver first** from the current template, and enable the pull-request setting. From then on, products on the old template are rejected with a request to update.
4. **Update each product repository's workflow** from the current template. No new secrets are needed.
5. **Flat files migrate themselves.** On a product's first sync with the new receiver, its old `<owner>_<name>.yaml` is removed and its content is stored in `<owner>__<name>/sdp.yaml`; the change appears in that product's first sync pull request. A flat file whose product never syncs again stays until a Draft Admin removes it.

## Capability Profiles

* **Query profile**: Strictly read-only. Queries pre-compiled `catalog_indexes.json` to answer questions about architecture, ports, DB engines, and dependencies. Directs engineers to the Author profile for authoring.
* **Author profile**: Interactively scaffolds `.draft/sdp.yaml`, runs validation, and helps engineers edit product architecture directly inside their code repos.
