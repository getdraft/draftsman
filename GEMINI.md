# Gemini Instructions

Use [AGENTS.md](AGENTS.md) as the canonical AI bootstrap for this repository.
When the user asks for a draftsman, assume the Draftsman role described in
[framework/docs/draftsman.md](framework/docs/draftsman.md).
When the user asks to set up DRAFT, start onboarding, or make the DRAFT
workspace useful, enter setup mode from
[framework/docs/setup-mode.md](framework/docs/setup-mode.md).

For company workspaces, read declared vocabulary lists before setting governed
fields and treat answers outside approved choices as non-standard values that
can be revisited or proposed for review.

If company workspace work reveals a likely reusable DRAFT framework bug or
feature request, recommend a sanitized upstream issue in `getdraft/draftsman`;
ask before creating any public issue.
