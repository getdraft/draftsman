---
description: Validate the DRAFT catalog and report issues with fix guidance
argument-hint: ""
allowed-tools: [Bash, Read, Glob]
---

# /draft validate

Run the DRAFT catalog validator and present each issue with enough context to
act on it immediately.

## Step 1: Run the Validator

```bash
python3 .draft/framework/tools/validate.py --workspace .
```

Capture both stdout and stderr. If the command is not found, check that the
framework is vendored at `.draft/framework/` and that Python 3 is available.

## Step 2: Parse and Categorize Issues

Group each reported issue by severity:

- **Error** — schema violations, invalid YAML, missing required fields. Must be
  fixed before the catalog is considered valid.
- **Warning** — missing recommended fields, unresolved references, non-standard
  vocabulary values. Should be addressed but do not block authoring.
- **Info** — advisory notices and style guidance.

## Step 3: Present Results

If there are no issues:

> Catalog is valid — no errors or warnings found.

If there are issues, group them by file and include the affected field, the
violation, and a one-line fix hint:

```
catalog/product-components/my-service.yaml
  ERROR   runsOn — required field missing
          → add a runsOn reference to a declared Host or RuntimeService
  WARNING owner.team — "platform-eng" is not in the approved teams vocabulary
          → approved values: platform, core-hr, ...
```

## Step 4: Offer to Fix

After presenting all issues, ask:

> Would you like me to fix any of these?

If yes, address each issue following the Draftsman role in
`.draft/framework/docs/draftsman.md`. Re-run the validator after fixes to
confirm the catalog is clean.
