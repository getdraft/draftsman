# DRAFT Draftsman

This workspace uses the DRAFT architecture framework. When the user types
`/draft <verb>`, or asks you to act as a Draftsman, read
`.draft/framework/commands/draft.md`, resolve the verb to its action file under
`.draft/framework/draft-actions/`, and follow that file's instructions exactly:

- `/draft` (or `/draft help`) → list the available verbs
- `/draft guide [intent]` → read `.draft/framework/draft-actions/guide.md`
- `/draft review [PR|security|path]` → read `.draft/framework/draft-actions/review.md`
- Other verbs (`update`) resolve the same way.

All Draftsman workflows bootstrap from `AGENTS.md` and treat
`.draft/framework/` as the approved vendored framework copy. Do not edit
`.draft/framework/**` or `.draft/framework.lock` during catalog authoring.
Company architecture content belongs in `catalog/` and `configurations/`.

Before asking about deployment target, data classification, team ownership,
availability tier, or failure domain, read declared vocabulary lists in
`.draft/workspace.yaml` and `configurations/vocabulary/`. If the user gives a
real answer outside the approved choices, call it a non-standard value and ask
whether to revisit later or submit a vocabulary proposal.
