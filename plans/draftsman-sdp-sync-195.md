# Draftsman #195: a tested, hardened decentralized SDP sync pipeline

<!-- sdlc-plan-id: draftsman-sdp-sync-195 -->

## Plan: Draftsman #195: a tested, hardened decentralized SDP sync pipeline

**Goal:** A product team in Dale's Draftsman updates .draft/sdp.yaml in its own repository and sees it reach the central catalog as a reviewed pull request, or sees exactly why it did not, in its own workflow run. Every step runs through one tested tool, the receiver accepts content only from the repository its ProductRegistration names, and nothing from the payload is ever run as shell text.

**Target repo(s):** `getdraft/draftsman`

**Approval:** Dale's standing instruction "I want the backlog cleared", and his 2026-11-20 7:51 PM Phoenix go-ahead: "Write Plan B and build it directly, no approval stop needed." This plan follows the same direct path as the #341 and #368 plans, and Dale approved this approach for #195 (E1 testable sync core, E2 receiver hardening, E3 docs and a return-path design document only). Built outside the agentic SDLC because BeerCanLabs GitHub Actions billing blocks the fleet; draftsman CI is unaffected.

### In scope
- The #195 acceptance criteria: fixture product and central repositories, a real payload round trip, sender identity, unknown references named, a pull request instead of a push, failures reported to the product repository, deletion, no payload values in shell text.
- Known gaps 1-6 and 8 from #195, and a design for gap 7.

### Out of scope
- Building the return path (central changes becoming pull requests in product repositories): E3 designs it only.
- Non-GitHub providers, and sync modes other than `repository_dispatch`.
- Editing the 'frontline-drafting-table' comment line, or anything Frontline-specific.

### Acceptance criteria
- framework/tools/sdp_sync.py has pack and receive commands and a versioned JSON payload (format, product repository, commit, action, correlation id, files). receive writes each file as the YAML text that was sent, never a JSON-quoted string, and refuses payloads over the repository_dispatch size limit with a clear message.
- tests/fixtures holds a fixture product repository (.draft/sdp.yaml, .draft/catalog/) and a fixture central workspace with its ProductRegistration; a test packs the product repository, receives the payload into a copy of the central workspace, and validate.py accepts the result.
- The sender and receiver workflow templates call sdp_sync.py instead of inline jq/echo; no run: step contains a ${{ github.event.client_payload... }} or other payload expression, and a template test enforces it. The 'frontline-drafting-table' comment line in product-repo-sync.yml.tmpl is left unchanged.
- The receiver accepts a payload only when its repository matches exactly one ProductRegistration repository.url (normalized), only for files under that product's own cache folder and of product-owned types, and never with a UID that another product or the central catalog already owns; every rejection names the reason.
- The sender proves its identity with a GitHub Actions OIDC token (audience configurable); the receiver verifies its RS256 signature against GitHub's published keys with the standard library only, and checks issuer, audience, expiry, the repository claim against the registration and the ref against the registered default branch.
- Product components, data components, listeners, relationships and decision records under the product's .draft/catalog/ are synced with the SDP; a reference the central catalog cannot resolve fails with a message that names the reference. Removing .draft/sdp.yaml sends a delete, and the receiver removes that product's cached files.
- A valid payload becomes a pull request against the central repository from a per-product branch (draft-sync/<product>), updated on later syncs; nothing is pushed to the default branch. Auto-merge is optional and only when the change touches that product's cache folder alone.
- Every outcome is written as a result file and job summary on the receiver; the sender waits for the matching receiver run by correlation id and fails its own run, in the product repository, with the receiver's message when validation or acceptance fails.
- decentralized-sdp-setup.md describes the tested pipeline: App and token permissions, OIDC audience, payload format, cache layout, the pull-request flow, how failures reach the product team, deletion, troubleshooting, and the upgrade from the old flat external_sdps files.
- A design document (framework/docs/proposals/sdp-return-path.md) describes how a central change (a review finding, a shared-service update) reaches a product repository, and answers who owns that step. Design only: no workflow or tool is built for it.

### Story breakdown
1. **S1.1 Sync tool, payload format and fixtures.** Files: `framework/tools/sdp_sync.py`, `tests/fixtures/sdp_sync/`, `tests/test_sdp_sync.py`, `CHANGELOG.md`.
2. **S1.2 Workflow templates call the tool, no payload in shell text.** Files: `templates/github/product-repo-sync.yml.tmpl`, `templates/github/drafting-table-receiver.yml.tmpl`, `tests/test_sdp_sync_templates.py`, `CHANGELOG.md`.
3. **S2.1 Registration match, path and type allowlist, UID ownership.** Files: `framework/tools/sdp_sync.py`, `tests/test_sdp_sync.py`, `CHANGELOG.md`.
4. **S2.2 OIDC sender identity.** Files: `framework/tools/sdp_sync.py`, `templates/github/*.tmpl`, `tests/test_sdp_sync_oidc.py`, `CHANGELOG.md`.
5. **S2.3 Product components, unresolved references and deletion.** Files: `framework/tools/sdp_sync.py`, `templates/github/product-repo-sync.yml.tmpl`, `tests/test_sdp_sync.py`, `CHANGELOG.md`.
6. **S2.4 Pull request instead of a push to main.** Files: `framework/tools/sdp_sync.py`, `templates/github/drafting-table-receiver.yml.tmpl`, `tests/test_sdp_sync_publish.py`, `CHANGELOG.md`.
7. **S2.5 Failures reported back to the product repository.** Files: `framework/tools/sdp_sync.py`, `templates/github/*.tmpl`, `tests/test_sdp_sync_report.py`, `CHANGELOG.md`.
8. **S3.1 Setup docs and return-path design.** Files: `framework/docs/decentralized-sdp-setup.md`, `framework/docs/proposals/sdp-return-path.md`, `CHANGELOG.md`.

Stories run in order; each is one squash-merged PR that closes its story issue.

### Decisions made while planning
- **One tool, thin workflows.** All sender and receiver logic is in `framework/tools/sdp_sync.py`; the templates only check out, set environment variables and call it. That makes every acceptance criterion testable without running Actions.
- **The sender runs the framework's own tool.** Product repositories do not vendor the framework, so the sender checks out the public `getdraft/draftsman` at the central workspace's framework version to run `sdp_sync.py pack`.
- **Identity is a registration match plus OIDC.** The repository name in the payload is only a claim; a GitHub Actions OIDC token signed by GitHub proves it. Verification uses the standard library (RS256 with GitHub's published keys), so no new dependency.
- **Per-product cache folder.** Synced content lives in `.draft/external_sdps/<product>/` (sdp.yaml plus catalog objects). Only product-owned types are accepted (SDP, product and data components, listeners, relationships, decision records); a UID already owned elsewhere is rejected.
- **Pull request, not push.** Each product gets a `draft-sync/<product>` branch and one pull request that later syncs update. Auto-merge is opt-in and only when the change stays inside that product's cache folder.
- **Failures come back through the sender.** The central side has no product credentials, so the sender waits for its receiver run (matched by correlation id) and fails its own run with the receiver's message.
- **Return path is design only** (E3), with an ownership recommendation; no workflow is built for it.
- **The 'frontline-drafting-table' comment line stays untouched.**
