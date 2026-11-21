---
name: draftsman-author
description: Use when someone wants to create or change DRAFT catalog or SDP files, onboard a product, or have a code repository scanned into catalog entries. Needs the Author profile from draftsman-core.
---

# Draftsman Author

Load `draftsman-core` first. This skill needs the **Author profile**: read the repository, edit files, run local validation. If you only have the Query profile, say so and stop; do not write YAML into the answer.

## Workflow

1. **Bootstrap.** Read `AGENTS.md`, `.draft/framework/AI_INDEX.md` and `.draft/workspace.yaml`. If the workspace is empty or unconfigured, follow `.draft/framework/docs/setup-mode.md`.
2. **Find the work.** Search `catalog/governance/sessions/` for an existing DraftingSession that matches the topic. Resume it, start one for a concrete system or product, or work directly for a one-off change.
3. **Search before you create.** Look through the effective catalog inventory so you do not duplicate an object. For listeners, run the lookup below.
4. **Interview.** Ask only for missing architecture facts, at most three questions at a time: runtime, ingress boundary, datastores and queues, infrastructure-as-code format.
5. **Write.** Read the matching schema under `.draft/framework/schemas/` and the RequirementGroup, then write valid YAML under `catalog/` or `configurations/`. Offer approved vocabulary values and flag non-standard ones.
6. **Validate.** Run `python3 .draft/framework/tools/validate.py --workspace .` after each YAML change and fix every error.
7. **Label what you guessed.** Apply rule R6: any value you did not read from the user, the code or an existing record is marked inferred and confirmed with the user.
8. **Hand off.** Summarise what changed, what is inferred and what is unknown. If the harness allows git, you may offer to commit on a `draft/<feature>` branch and open a pull request. If it does not, give the user the file list.

## What a pattern places

A software deployment pattern places only product components and data components. A group's runtime or host goes in `substrate`; a data component names its data store in `runsOn`; edge services (load balancer, firewall, ingress) come from the reference architecture the pattern follows. External services are relationship targets, drawn as External interactions. A service definition (an object under the shared-services catalog folder, or `serviceRole: definition`) is never placed and never a relationship endpoint: record the relationship on the component or instance. Rules `sdp-placement-types` and `relationship-definition-endpoint` check this.

## Calls land on listeners

Every relationship sets `targetListener` to the UID of the listener it calls, including calls to data components and external targets (ratcheted rule `relationship-target-listener`). A listener is its own `listener` object, owned by a product component, data component or external system (`owner.kind`, `owner.ref`), and it holds `protocol`, `port`, `endpoint` and `authenticationModel`; the caller never does. Before you write a relationship, follow Listener Lookup Before Create in `.draft/framework/docs/draftsman.md`:

1. **Resolve the owner** by UID, then exact name or alias. Several matches: list them and ask. Never pick one.
2. **Normalize the key:** owner + protocol + port + endpoint path (default ports filled in, host dropped, path parameters templated).
3. **Exact match:** link its UID without asking.
4. **No match:** create a listener with `catalogStatus: stub` and `authenticationModel: TBD` from what the caller knows, and link it. Several matches: list them and ask.
5. **Real listener authored later:** upgrade the stub in place; keep its UID.

A stub owned by an external system needs a company-internal caller. A pattern cannot be completed while it calls an internally owned stub (`sdp-internal-stub-listener`). `authenticationModel: none` needs a committed DecisionRecord keyed `interface_unprotected`. When you can run Python, use `draft_table.catalog` (`link_or_stub_listener`, `record_authored_listener`) instead of matching by hand. A port or endpoint you did not read is not recorded: leave the listener a stub and list the gap (rule R6).

The caller is always the relationship's `source`. Omit `flow` (`outbound` is the default). Never write `flow: inbound`, `flow: bidirectional` or free-text `externalTarget` in a new or edited relationship: they are deprecated (still accepted on existing content). Make the caller the source instead of `inbound`, use `direction: synchronous` for request/response instead of `bidirectional`, and target the external party's `system` object instead of `externalTarget` (Deprecated Relationship Fields in `.draft/framework/docs/draftsman.md`).

## Scanning a code repository

Read only what the harness already lets you read; never ask the user for credentials or tokens. Map what you find to DRAFT objects and mark every mapping inferred until the user confirms it. The mapping table and the full conversational flow are in `references/guide.md`.

## References

- `references/guide.md`: the conversational flow, session handling and the repository-scan mapping.
