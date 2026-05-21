# Draftsman AI Guidance

DRAFT does not include a built-in AI runtime. The Draftsman is an external AI
agent role that uses the selected framework copy as source material, edits YAML
when asked, and validates the result with the framework tools.

## Operating Model

An AI assistant acting as the Draftsman should:

- read [AGENTS.md](../../AGENTS.md) first
- use [AI_INDEX.md](../../AI_INDEX.md) for discovery
- read the relevant schema in `framework/schemas/`
- read the applicable Requirement Group in `framework/configurations/requirement-groups/`
- read declared company vocabulary lists in `.draft/workspace.yaml` and any
  configured `configurations/vocabulary/*.yaml` sources
- use templates from `templates/` for new objects
- write changes to framework or workspace YAML only when the user asks for
  changes
- run `python3 framework/tools/validate.py` before considering edits complete

If the assistant is connected only to the upstream framework repository and the
user asks for company architecture content changes, it should ask for the
company-specific DRAFT repo path before editing. The upstream repo is the
framework implementation source; it is not the place to record a company's
architecture catalog.

## Workspace Context

For private company workspaces, the effective model is:

1. vendored framework base configuration in `.draft/framework/configurations/`
2. workspace configuration overlays in `configurations/`
3. workspace catalog content in `catalog/`

The AI should inspect all three layers before creating new objects. In a
company repo, prefer `.draft/framework/docs/`, `.draft/framework/schemas/`, and
`.draft/framework/configurations/` over the public upstream checkout because
those files represent the framework version the company has approved. Reuse a
matching existing object when one is already present, and create a Drafting
Session when important architecture facts are missing.

Company architecture updates should go under `catalog/` or company-owned
`configurations/`. Do not edit `.draft/framework/**` or `.draft/framework.lock`
during normal Draftsman work; those files change only through an explicit
framework refresh/update workflow.

## Vocabulary And Pull Requests

When a declared vocabulary list covers a question, the Draftsman should offer
approved values as choices. If the user gives a real answer that is not in the
approved list, call it a non-standard value and ask whether to revisit later or
submit a vocabulary proposal.

A vocabulary proposal is a tracked YAML artifact under
`configurations/vocabulary-proposals/`. It gives any AI assistant or GitHub
Actions workflow enough information to add the proposed value to the official
company list in a separate review pull request.

DRAFT does not assume every AI runtime can create pull requests. If the AI
environment has Git and repository access through the user's credentials, it
should create a branch, commit, push, and open the pull request. If it lacks
that ability, it should still write the local YAML changes and give the user
the exact commands or review steps needed to submit them.

## Secrets

Do not store AI provider credentials, API keys, Git credentials, or unrelated
secrets in tracked framework or workspace files. DRAFT content is architecture
metadata and should remain reviewable as source.

## Slash Commands

DRAFT ships IDE-ready slash commands in `framework/commands/`. When a workspace
has linked these into its IDE command folder, the following commands are
available without relying on role-activation phrases:

| Command | Purpose |
|---|---|
| `/draftsman [intent]` | Activate the Draftsman for authoring or workspace setup |
| `/draft-session [topic]` | Start or resume a guided Drafting Session |
| `/validate-catalog` | Run the validator and report issues with fix guidance |

Commands are symlinked during setup from `.draft/framework/commands/` into
`.claude/commands/` (or the equivalent for other IDEs). The links are shallow —
they follow the vendored framework copy, so updating the framework automatically
updates command behavior without re-linking.

See `framework/docs/setup-mode.md` step 7 for linking instructions.

## Browser Boundary

The generated GitHub Pages browser is read-only. It helps humans and AI agents
inspect framework and example catalog content, but it does not execute
Draftsman actions or write files.
