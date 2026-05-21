# DRAFT Draftsman

This workspace uses the DRAFT architecture framework. When the user invokes
`/draftsman`, `/draft-session`, or `/validate-catalog`, or asks you to act as
a Draftsman, read the corresponding command file and follow its instructions
exactly:

- `/draftsman [intent]` → read `.draft/framework/commands/draftsman.md`
- `/draft-session [topic]` → read `.draft/framework/commands/draft-session.md`
- `/validate-catalog` → read `.draft/framework/commands/validate-catalog.md`

All Draftsman workflows bootstrap from `AGENTS.md` and treat
`.draft/framework/` as the approved vendored framework copy. Do not edit
`.draft/framework/**` or `.draft/framework.lock` during catalog authoring.
Company architecture content belongs in `catalog/` and `configurations/`.

Before asking about deployment target, data classification, team ownership,
availability tier, or failure domain, read declared vocabulary lists in
`.draft/workspace.yaml` and `configurations/vocabulary/`. If the user gives a
real answer outside the approved choices, call it a non-standard value and ask
whether to revisit later or submit a vocabulary proposal.
