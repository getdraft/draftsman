---
name: draftsman-author
description: Use when someone wants to create or change DRAFT catalog or SDP files, onboard a product, or have a code repository scanned into catalog entries. Needs the Author profile from draftsman-core.
---

# Draftsman Author

Load `draftsman-core` first. This skill needs the **Author profile**: read the repository, edit files, run local validation. If you only have the Query profile, say so and stop; do not write YAML into the answer.

## Workflow

1. **Bootstrap.** Read `AGENTS.md`, `.draft/framework/AI_INDEX.md` and `.draft/workspace.yaml`. If the workspace is empty or unconfigured, follow `.draft/framework/docs/setup-mode.md`.
2. **Find the work.** Search `catalog/governance/sessions/` for an existing DraftingSession that matches the topic. Resume it, start one for a concrete system or product, or work directly for a one-off change.
3. **Search before you create.** Look through the effective catalog inventory so you do not duplicate an object.
4. **Interview.** Ask only for missing architecture facts, at most three questions at a time: runtime, ingress boundary, datastores and queues, infrastructure-as-code format.
5. **Write.** Read the matching schema under `.draft/framework/schemas/` (it lists the required fields) and the RequirementGroup, then write valid YAML under `catalog/` or `configurations/`. Offer approved vocabulary values and flag non-standard ones.
6. **Validate.** Run `python3 .draft/framework/tools/validate.py --workspace .` after each YAML change and fix every error.
7. **Label what you guessed.** Apply rule R6: any value you did not read from the user, the code or an existing record is marked inferred and confirmed with the user.
8. **Hand off.** Summarise what changed, what is inferred and what is unknown. If the harness allows git, you may offer to commit on a `draft/<feature>` branch and open a pull request. If it does not, give the user the file list.

## Scanning a code repository

Read only what the harness already lets you read; never ask the user for credentials or tokens. Map what you find to DRAFT objects and mark every mapping inferred until the user confirms it. The mapping table and the full conversational flow are in `references/guide.md`.

## References

- `references/guide.md`: the conversational flow, session handling and the repository-scan mapping.
