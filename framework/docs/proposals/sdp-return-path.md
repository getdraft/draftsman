# Proposal: The SDP Return Path (Central to Product)

**Status**: Design only. Nothing in this document is built; no workflow, tool or schema change ships with it.
**Context**: #195 (decentralized SDP sync). The forward path, from a product repository to the central workspace, is described in [decentralized-sdp-setup.md](../decentralized-sdp-setup.md).
**Authors**: Draft prepared for Dale Sackrider

---

## 1. Problem

The sync pipeline moves a product's SDP and catalog objects one way: from the product repository into the central workspace's cache (`.draft/external_sdps/<owner>__<name>/`). The product repository is the source of truth, and every sync replaces the cached snapshot.

Some changes start centrally and need to reach a product:

1. **A review finding.** A Draft Admin or architecture reviewer reads a product's SDP in the central catalog and asks for a change ("this data component needs an encryption decision record", "this listener should use the shared ingress").
2. **A shared-service update.** A platform team changes, deprecates or retires something products depend on (a runtime, a data store service, a reference architecture), and every product that references it needs to act.
3. **A central correction.** A UID is renamed or merged, a vocabulary value is retired, or a validation rule tightens, and product content must follow.

Today there is no path back. Editing the cached copy centrally does nothing useful: the next sync overwrites it. The only channel is out-of-band (a chat message or a ticket), so central changes are easy to lose and impossible to track.

## 2. Constraints

* **The product repository stays the source of truth.** The central workspace never edits product content in place.
* **No central credentials for product repositories.** `drafting-table` holds no token that can read or write product code today. The return path must not change that.
* **No new standing permissions** beyond what the forward path already uses: the GitHub App's Contents access on the central repository, the OIDC token, and each repository's own `GITHUB_TOKEN`.
* **Every request is traceable**: who raised it, against which object, and whether it was resolved.
* **Same tooling style as the forward path**: logic in a tested tool, templates that only call it, no payload values in shell text.

## 3. Options

### Option A: The central workspace writes to product repositories

The central workspace (or an App installed on product repositories) opens issues or pull requests directly in each product repository.

* Fast and familiar for product teams.
* **Rejected**: it needs credentials with write access to every product repository, reversing the forward path's central guarantee (`drafting-table` holds no product credentials) and widening the blast radius of a compromised central workflow.

### Option B: Notify only

The central workspace posts findings somewhere neutral (a ticketing system, a mailing list) and product teams act manually.

* No new permissions.
* Not traceable to catalog objects, easy to ignore, and nothing in DRAFT knows whether a finding was resolved.

### Option C (recommended): Central publishes, product pulls

1. **Findings are central catalog content.** A reviewer records a request as a central object that points at a product object by UID: a `decision_record` with a new status such as `requested` (or a small new `change_request` type, see open questions), stored under `catalog/engineering/requests/<owner>__<name>/`. Shared-service updates are recorded the same way, generated per affected product from the indexes' reverse-reference data ("which SDPs reference this runtime"). They are merged into the central default branch through a normal pull request, so they are reviewed and versioned.
2. **The product repository pulls.** A workflow in the product repository (on a schedule, on `workflow_dispatch`, and right after each sync) uses the **same GitHub App token it already has** (Contents on the central repository) to read the open requests for its own product, and its **own `GITHUB_TOKEN`** to open or update one issue (or a draft pull request with a suggested edit, when the change is mechanical) in its own repository.
3. **Resolution flows forward.** When the product team changes `.draft/` and pushes, the normal sync carries the change to the central workspace. The receiver marks a request resolved when the synced content satisfies it (for example, the requested decision record now exists, or the deprecated reference is gone), or the product team answers it with a decision record that declines it with a reason.

Why this option:

* No new credentials: the central side never touches product repositories; each product reads only what is addressed to it, with access it already has.
* Requests live next to the catalog objects they are about, so the central catalog can show "open requests" per product and per shared service.
* The product team decides when and how to change its own source of truth, and the change arrives through the already tested forward path.

## 4. Who Owns the Return Path

| Step | Owner |
| --- | --- |
| Raising a review finding | The reviewer (Draft Admin or architecture reviewer) who found it |
| Raising a shared-service update | The platform team that owns the shared service; a Draft Admin approves the generated per-product requests |
| Reviewing and merging requests into the central catalog | Draft Admins (normal pull request review on `drafting-table`) |
| Bringing open requests into the product repository | The product team, through the return-path workflow in its own repository (it runs with the product's own credentials, so the product team owns it) |
| Changing product content | The product team, in its own repository; the central workspace never edits it |
| Closing a request | Automatic when a sync satisfies it; otherwise the product team, with a decision record that explains the outcome; a Draft Admin can withdraw it |
| The tool and templates | DRAFT framework maintainers, as for the forward path |

In short: **the central side owns asking, the product team owns changing, and nobody central writes to a product repository.**

## 5. Sketch of the Pieces (Not Built)

* **Schema**: either a `requested` status and `requestedBy` / `requestedChange` fields on `decision_record`, or a `change_request` type with `target` (a product object UID), `reason`, `requestedBy`, `status` (`open`, `resolved`, `declined`, `withdrawn`) and an optional suggested patch. Allowed only in the central catalog; the receiver already refuses product-synced objects of central types.
* **Tool**: `sdp_sync.py requests --repository OWNER/NAME` lists open requests for a product from the central repository's contents (read with the App token); `sdp_sync.py open-issue` turns them into one issue body in the product repository. Both tested with fake API clients, like `await-result`.
* **Template**: a third template, `product-repo-requests.yml.tmpl`, reusing the sender's App token step and `permissions: issues: write` on the product repository's own `GITHUB_TOKEN`.
* **Receiver**: after a verified sync, mark requests resolved when their condition holds, in the same sync pull request.
* **Discovery for shared-service updates**: a small generator that, given a shared-service UID and a reason, writes one request per product cache that references it, for a Draft Admin to review as a single pull request.

## 6. Open Questions

1. Extend `decision_record` or add `change_request`? A new type keeps decision records meaning "a decision was made"; extending avoids a schema addition.
2. How is "satisfied" checked: a fixed set of machine-checkable conditions (object exists, reference removed, field set), with everything else closed by the product team?
3. Issue only, or also a suggested pull request for mechanical changes (UID renames, retired vocabulary)? A suggested pull request is helpful but means the tool edits product YAML.
4. Should a request with a deadline (a shared service being retired) fail the product's sync after the deadline, or only warn?
5. Where do product teams without GitHub Issues receive requests?

## 7. Non-Goals

* Building any of the above in #195.
* Central edits to product content, or any central credential for product repositories.
* Replacing the forward sync or its pull-request review.
