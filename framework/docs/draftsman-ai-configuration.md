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

## AI-Agnostic Design

DRAFT is designed so that any capable AI assistant can act as the Draftsman.
The framework does not assume Claude, Gemini, Copilot, or any specific model.
A company can bring whichever AI tool their team already uses.

The canonical workflow instructions live in `framework/commands/` as plain
markdown. Any AI that can read files in the workspace can read and follow them.
What varies per IDE is how the AI *discovers* these commands — that is the only
tool-specific layer.

## Workflow Commands

The following commands are available in any IDE that has been wired up per
setup-mode step 7:

| Command | Purpose |
|---|---|
| `/draftsman [intent]` | Activate the Draftsman for authoring or workspace setup |
| `/draft-session [topic]` | Start or resume a guided Drafting Session |
| `/validate-catalog` | Run the validator and report issues with fix guidance |

Command files live in `.draft/framework/commands/`. They include Claude Code
frontmatter (`description`, `argument-hint`, `allowed-tools`) which other AI
tools skip — the instruction content that follows works for any AI without
modification.

## IDE Integration

Each IDE has its own registration mechanism. Per-IDE files live in
`framework/integrations/` (ready to copy into the workspace) and workspace
templates include command invocation guidance for each supported tool:

| IDE | Mechanism | Setup |
|---|---|---|
| Claude Code | `.claude/commands/` symlinks | setup-mode step 7a |
| Cursor | `.cursor/rules/draftsman.mdc` | setup-mode step 7b |
| Windsurf | `.windsurfrules` | setup-mode step 7c |
| GitHub Copilot | `.github/copilot-instructions.md` block | setup-mode step 7d |
| Gemini CLI | `GEMINI.md` (workspace bootstrap) | included automatically |
| OpenAI Codex / generic | `AGENTS.md` (workspace bootstrap) | included automatically |

See `framework/docs/setup-mode.md` step 7 for full instructions.

## Browser Boundary

The generated GitHub Pages browser is read-only. It helps humans and AI agents
inspect framework and example catalog content, but it does not execute
Draftsman actions or write files.
