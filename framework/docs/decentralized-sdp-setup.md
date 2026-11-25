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
5. The receiver runs `validate.py`, regenerates the indexes, and `sdp_sync.py publish` opens or updates the product's pull request. By default that uses `GITHUB_TOKEN`. When the central repository has set the receiver App secrets, the checkout, the force-push, and `GH_TOKEN` use that App instead, and **DRAFT Sync Pull Request Merge** squash-merges a confined pull request after the central validation workflow succeeds ([Fully automatic merge](#fully-automatic-merge)).
6. `sdp_sync.py report` records the outcome. Back in the product repository, `sdp_sync.py await-result` waits for that outcome and fails the product's run with the receiver's message if the sync was rejected or did not validate.

No step puts a payload value into shell text: values reach scripts only through environment variables and files, and template tests enforce it.

## One-Time Setup

### 1. Central workspace (`drafting-table`)

1. Copy `templates/github/drafting-table-receiver.yml.tmpl` to `.github/workflows/draft-sdp-receiver.yml`. For an unattended merge, also copy `templates/github/drafting-table-sync-merge.yml.tmpl` to `.github/workflows/draft-sdp-sync-merge.yml` on the default branch. The workspace must have the framework vendored at `.draft/framework/` (both workflows run the tools from there).
2. In **Settings → Actions → General**, enable **Allow GitHub Actions to create and approve pull requests**. Without it, a publish that uses `GITHUB_TOKEN` fails and the product run reports the failure. The receiver App path uses the App's own pull-request permission; leave the setting on so the `GITHUB_TOKEN` path still works.
3. Optional: set the repository variable `DRAFT_SYNC_AUTO_MERGE` to `true`. With only `GITHUB_TOKEN`, also enable **Allow auto-merge** (Settings → General). That path arms auto-merge and still waits for a human approval when a review is required. To merge with no human review once `validate` is green, follow [Fully automatic merge](#fully-automatic-merge). See [Pull requests and required checks](#pull-requests-and-required-checks).

### 2. Dispatch GitHub App

Create (or reuse) one GitHub App for product repositories to send syncs. This is the dispatch App. Fully automatic merge uses a different App, and this one must not be a ruleset bypass actor.

* **Repository permissions:** *Contents: Read and write*. Nothing else. Contents write is what `repository_dispatch` requires; the same access lets the product run read its result from the central repository.
* **Install it on the central repository only.** It needs no access to any product repository.
* In each product repository (or once at the organization level), store the App's ID as the secret `DRAFT_APP_ID`, its private key as `DRAFT_APP_PRIVATE_KEY`, and the central repository's name (without the owner) as `DRAFT_CENTRAL_REPO_NAME`. The central repository must have the same owner as the product repository.

Those secrets are often organization secrets, visible to many repositories. That is appropriate for dispatch. Do not let this App bypass review on the central repository: a product repository that can read the secrets could then merge into the drafting table without a reviewer. See [Fully automatic merge](#fully-automatic-merge).

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
| Dispatch App installation token | Product run. Secrets `DRAFT_APP_ID` and `DRAFT_APP_PRIVATE_KEY`, often organization secrets | Contents: read and write, central repository only, about 60 minutes. No other permission | Sending the `repository_dispatch` event; reading the result file |
| GitHub Actions OIDC token | Product run (`id-token: write`) | None: it is a signed statement of who is sending | Proving the sync comes from the registered repository's default branch |
| `GITHUB_TOKEN` | Central receiver run, when `DRAFT_RECEIVER_APP_ID` and `DRAFT_RECEIVER_APP_PRIVATE_KEY` are not both set | `contents: write`, `pull-requests: write` | Pushing the `draft-sync/<product>` branch, opening its pull request, writing the result file. Its `pull_request` `opened`, `synchronize`, and `reopened` runs are created and held for **Approve workflows to run**; they do not go green unattended |
| Receiver App installation token | Central receiver run, and **DRAFT Sync Pull Request Merge**. Repository secrets `DRAFT_RECEIVER_APP_ID` and `DRAFT_RECEIVER_APP_PRIVATE_KEY` on the central repository, not on product repositories | Contents: Read and write, Pull requests: Read and write, this repository only, about 60 minutes | The same publish and report calls, including the force-push, and the merge API after `validate` succeeds. Its `pull_request` runs start without the approval prompt |

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

With `DRAFT_SYNC_AUTO_MERGE=true` and no receiver App token, `publish` requests squash auto-merge **only** when every changed file is inside that product's cache folder (or its old flat file), apart from the two regenerated index files (`docs/assets/draft-indexes.json` and `.draft/AI_INDEX.md`). That request does not finish while a required approving review is still open. GitHub auto-merge does not honor a ruleset bypass actor, so arming it does not replace an approval. If a later sync changes anything else, auto-merge is turned off on that pull request so a reviewer sees it. If auto-merge cannot be enabled (for example, the repository setting is off), the pull request stays open and the result says so. The receiver App path does not arm auto-merge; [**DRAFT Sync Pull Request Merge**](#fully-automatic-merge) merges the pull request itself.

Receiver runs are serialized (`concurrency: draft-sdp-sync`), so two syncs never race on the indexes or a pull request. The merge workflow is outside that group, so one product's validation does not block the next sync.

**Required status checks wait for approval on these pull requests** when the receiver pushes and opens them with `GITHUB_TOKEN`. GitHub does create the `pull_request` `opened`, `synchronize`, and `reopened` workflow runs, and it holds them under **Approve workflows to run**. They do not go green unattended. That includes the synchronize run from a later force-push: `sdp_sync.py publish` force-pushes with the credentials `actions/checkout` saved, not with `GH_TOKEN`. An App token's events run without that approval prompt. To merge without a person, use a [receiver App](#fully-automatic-merge). With only `GITHUB_TOKEN`, choose one:

* Don't require status checks on the central default branch, and rely on the receiver's own validation, which already ran on exactly this content before the pull request was opened (a required review still applies); or
* Keep the checks required and have a person approve the workflow runs on each sync pull request, then approve and merge; auto-merge then completes only after that approval, and it is not a substitute for the approval.

## Fully Automatic Merge

Some organizations want a sync pull request to merge once the receiver has accepted it and the drafting table's required status check is green, with no human approval. That is opt-in. It needs a second GitHub App, three repository rulesets, `DRAFT_SYNC_AUTO_MERGE=true`, and **DRAFT Sync Pull Request Merge**. Leave the receiver App secrets unset and the receiver keeps today's `GITHUB_TOKEN` behavior, including arming auto-merge when that variable is true. Auto-merge still waits for a human when a review is required.

Product repositories change nothing. They keep the dispatch App (`DRAFT_APP_ID`, `DRAFT_APP_PRIVATE_KEY`, Contents: Read and write on the central repository only).

### Why a second App

The dispatch App's credentials live in product repositories, often as organization secrets that many repositories can read. A ruleset bypass actor skips every rule in that ruleset. If the dispatch App were allowed to bypass review, any repository that can read those secrets could mint a token and merge an unreviewed pull request into the drafting table. The receiver App is a different App. Its secrets stay on the central repository.

Anyone with the receiver App secrets can open and merge pull requests as that App. The merge workflow additionally requires the validating run's original pusher to be the receiver App, and the pull request to have been opened by that App. The bypass is on the App, not on a path. A person who uses the token outside the workflow can still merge any other pull request that passes the required status checks. Store `DRAFT_RECEIVER_APP_ID` and `DRAFT_RECEIVER_APP_PRIVATE_KEY` as repository secrets of the central repository, not as organization secrets product repositories can read, and limit who can administer that repository.

### Receiver App

Create a GitHub App used only by the central receiver:

* **Repository permissions:** *Contents: Read and write* and *Pull requests: Read and write*. Contents is what the force-push, the branch update, and the result-file write need. Pull requests is what opening, editing, and merging the sync pull request need. The merge API rejects an App token that has only contents read, so the merge workflow's token asks for contents write and pull-requests write.
* **Install it on the central repository only.**
* Store the App ID as the repository secret `DRAFT_RECEIVER_APP_ID` and the private key (the whole PEM) as `DRAFT_RECEIVER_APP_PRIVATE_KEY`. Set both, or neither. If only one is set, the receiver run fails instead of falling back in silence.

Copy the current `templates/github/drafting-table-receiver.yml.tmpl` over `.github/workflows/draft-sdp-receiver.yml`, and `templates/github/drafting-table-sync-merge.yml.tmpl` over `.github/workflows/draft-sdp-sync-merge.yml`. When both secrets are set, before it stores the payload, the receiver:

1. Mints an installation token with `actions/create-github-app-token`, scoped to this repository, with contents write and pull-requests write. The token step runs before checkout.
2. Passes that token to `actions/checkout` as `token:` and leaves credential persistence on. `sdp_sync.py publish` force-pushes with the credentials checkout saved, not with `GH_TOKEN`. A `GITHUB_TOKEN` push's `pull_request` `synchronize` run is held for **Approve workflows to run** and does not go green unattended. The App token runs it without that prompt. If minting fails, checkout still runs with `GITHUB_TOKEN`, so the report step can write the job summary.
3. Passes the same token as `GH_TOKEN` to `sdp_sync.py publish` and `sdp_sync.py report`. `gh` uses it to open or update the pull request and to write the result file on `draft-sync-results`. It does not arm auto-merge. **DRAFT Sync Pull Request Merge** does the merge after validation.

When the secrets are absent, checkout's `token:` and both `GH_TOKEN` values are `github.token`, which is today's behavior, and `publish` may still arm auto-merge.

### Three rulesets

A bypass actor skips every rule in its ruleset, including a required status check. The check and the review bypass have to be different rulesets, or the App would skip CI as well as review. Rulesets A and B target the default branch. Ruleset C targets the sync branches. All three are enforced, not evaluate-only.

* **Ruleset A** requires the `validate` status check (the check name the drafting table's validation workflow reports on `pull_request`; the workflow's `name:` is what **DRAFT Sync Pull Request Merge** listens for, and on this framework repository that name is `Validate Catalog`). Also require branches to be up to date before merging, on the strict setting. Bypass list: empty. Do not add the receiver App. If you do, the App skips the check.
* **Ruleset B** requires a pull request before merging, with at least one approval. Bypass list: the receiver App only, with bypass mode **For pull requests only**. Do not choose **Always**. Always lets the App push straight to the default branch and skip every rule in the ruleset, not only the review on a pull request. **For pull requests only** lets the App merge a pull request without an approval and still subjects a direct push to the ruleset. Everyone else still needs an approval. `github-actions[bot]` is not a reliable bypass actor; use the App.
* **Ruleset C** targets `refs/heads/draft-sync/**`, not the default branch. Restrict creation, update, and deletion of those branches to the receiver App (the bypass actor is the receiver App only). Bypass mode on this ruleset must be **Always**. Force-push and `update-branch` are branch updates, not pull-request merges, so **For pull requests only** returns 403 and the receiver cannot update its own branch. That is the opposite of ruleset B, whose bypass must stay **For pull requests only** and must not be **Always**. The dispatch App has Contents write on this repository, and its secrets often live in product repositories, so without this ruleset any of those repositories could push `draft-sync/<product>` itself. An App push is not held for **Approve workflows to run**, so `validate` would go green and a merge that trusted only the branch name would land the push without `receive` ever checking the OIDC token or `repository.id`.

Set the repository variable `DRAFT_SYNC_AUTO_MERGE` to `true`. **Allow auto-merge** is only for the `GITHUB_TOKEN` path that arms `gh pr merge --auto`. The receiver App calls `PUT /repos/{owner}/{repo}/pulls/{n}/merge` with `merge_method=squash` and `sha` set to the validated head. That call needs Contents write on the App token, and it honors the bypass. Auto-merge does not, so the pull request would stay `REVIEW_REQUIRED`.

**DRAFT Sync Pull Request Merge** runs when the validation workflow completes with success (`workflow_run`). It uses concurrency group `draft-sdp-merge` (`cancel-in-progress: false`), separate from `draft-sdp-sync`, so one product's validation does not block the next sync and two merges do not race on the regenerated indexes. It checks out the default branch only, never the pull request head. It mints the receiver App token (contents write and pull-requests write) and reads `app-slug`. The validating run's `workflow_run.actor` must be `<app-slug>[bot]`. For a `synchronize` run, that account pushed the commit. For an `opened` run, `workflow_run.actor` is the account that opened the pull request, not the account that pushed the tip. `publish` therefore records the commit it force-pushed and, after it creates or edits the pull request, reads the branch tip and the pull request head. If either is a different commit, it force-pushes its own commit again and fails, so a Contents-write token cannot replace the tip in that window and have the receiver App open the pull request on the replacement. `triggering_actor` is whoever started the latest attempt and changes on a re-run, so it is not used. `sdp_sync.py merge` checks the actor again, and it also requires the pull request's author to be that bot. It then fetches `draft-sync/<product>`, refuses a fork, refuses a head SHA that is not the SHA that just validated, and refuses a diff that is not confined to that product's cache folder plus the regenerated `docs/assets/draft-indexes.json` and `.draft/AI_INDEX.md`. The old flat file `.draft/external_sdps/<owner>_<name>.yaml` counts only when the diff deletes it: the same path is shared by different `owner/name` pairs, so an add or edit must not merge. If the pull request is behind the default branch, merge calls `PUT /repos/{owner}/{repo}/pulls/{n}/update-branch` with `expected_head_sha` set to the validated SHA and does not merge. That update is an App push, so `validate` runs again and `workflow_run.actor` is still the App; the next success merges the new head. Otherwise it merges that exact SHA. A 409 that says the head moved, or an `update-branch` HTTP 422 that names `expected_head_sha`, is left for the newer run. Any other API error fails the job. A change outside the cache folder stays open for a human. If the `workflows:` list does not match the validation workflow's `name:`, the merge never starts; change that one line.

### Registration is the main gate on receive

`repository.id` is the main gate on the receive path: which repository may send a payload that the receiver stores. It does not stop a push straight to `draft-sync/*`. The merge path is protected by the pusher binding and by ruleset C. Pin `repository.id` on every ProductRegistration before enabling unattended merge, and set `repository.ownerId` when you want the owner pin as well. GitHub never reuses `repository.id`, and it survives a rename. A registration that omits it still matches by repository name: a deleted repository recreated with the same `owner/name` would pass the identity check, and the accepted result only warns. Look the ids up with `gh api repos/OWNER/NAME --jq .id` and `--jq .owner.id`. Do not copy them from a sync warning.

## How Failures Reach the Product Team

The receiver's last step, `sdp_sync.py report`, runs even when an earlier step failed. It turns the run into one outcome:

* **accepted:** stored, validated, and the pull request opened or updated (its link is included), or the workspace already matched;
* **rejected:** `receive` refused the payload; the reason is included;
* **failed:** the workspace did not validate with the sync (the failures are listed, the product's own files first), the pull request could not be opened, or the run stopped early.

Every outcome is written to the central run's job summary. When the sender's identity was verified, it is also saved as `results/<owner>__<name>/<correlationId>.json` on the `draft-sync-results` branch of the central repository (created from the default branch on first use). A pinned `repository.id` or `repository.ownerId` is checked only after that verification, so a mismatch is one of these results and the product run fails with the reason. In the product repository, **Await Central Result** polls exactly that file with the dispatch App token, then shows the outcome in its job summary. If the outcome is not *accepted*, it fails the product run with an error annotation carrying the message, the failures, and a link to the central run. An accepted sync whose registration has no `repository.id` stays accepted; the message includes the warning, and the product run does not fail for that warning.

Payloads rejected *before* the identity check (an old template, a malformed payload, a token that does not verify) are shown only in the central run's summary: an unverified sender must not be able to write a result where another product will read it. The product run then times out with a hint to check the central repository's Actions.

Result files are small and accumulate, one per sync. The `draft-sync-results` branch can be deleted at any time; the next report recreates it.

## Deletion

Deleting `.draft/sdp.yaml` from the product repository sends a `delete`. The receiver removes everything it caches for that product, catalog objects included, even if `.draft/catalog/` still has files, and opens a pull request that removes them centrally. Central objects that referenced the product's components become dangling; `validate.py` reports them. To stop syncing without deleting, remove or disable the sync workflow instead.

## Security Notes and Known Limits

* **A live OIDC token can be resent within its lifetime.** GitHub's OIDC tokens cannot carry a hash of the payload, so the receiver binds a token to its repository, ref and commit (`sha`) only. Anyone who obtains a live token could, during its few-minute lifetime, send different files for that same commit. The token travels only inside the central repository's `repository_dispatch` event, which is visible to people and workflows with access to that repository (the event payload is available to its workflow runs); it is never written to the cache, the result file or the logs. Exploiting it therefore needs existing access to the central repository. Mitigations: keep write and Actions access to the central repository tight, install the dispatch App only there, and rely on the pull-request flow so every change reaches a reviewer (do not enable auto-merge if that review is your control). [Fully automatic merge](#fully-automatic-merge) drops that review for a confined cache update. Anyone with the receiver App secrets can open and merge those pull requests.
* **Pin `repository.id`.** GitHub never reuses `repository_id`, and it survives a rename. Once a registration sets it, a deleted or transferred repository that is recreated with the same `owner/name` fails the identity check. Until a Draft Admin sets it, the receiver still matches by repository name and records a warning on the accepted result. `repository.ownerId` is a second pin, checked only when set; it does not stop a new repository in the same organization. Remove the registration when a product repository is retired. The receiver does not copy the token's id into the catalog. Pin `repository.id` before enabling unattended merge: it is the main gate on the receive path. The merge path also requires the validating run's `workflow_run.actor` to be the receiver App and ruleset C on `draft-sync/**`.
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
| `reading the central result failed with HTTP 403` | The dispatch App lacks Contents access to the central repository, or is not installed there. |
| `Set both DRAFT_RECEIVER_APP_ID and DRAFT_RECEIVER_APP_PRIVATE_KEY, or neither` | The central repository has only one of the receiver App secrets. Set both, or remove the one that is set. The App also needs Contents: Read and write and Pull requests: Read and write, installed only on the central repository. |
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
