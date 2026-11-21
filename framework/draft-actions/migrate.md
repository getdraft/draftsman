---
description: Propose listener-based replacements for deprecated relationship fields and review them with the user
argument-hint: "[object <uid> | sdp <uid> | folder <path>] (empty scans the whole catalog)"
allowed-tools: [Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion]
---

# /draft migrate

Help the user move relationships off the deprecated fields (`flow: inbound`,
`flow: bidirectional`, free-text `externalTarget`) onto listeners. This is a
direct action: the migration helper only proposes, and nothing in `catalog/`
changes until the user approves a patch.

## Step 1: Scope

Read `$ARGUMENTS`:

- empty: the whole workspace
- `object <uid>`: relationships whose source or target is that object
- `sdp <uid>`: relationships touching the objects a SoftwareDeploymentPattern places
- `folder <path>`: relationships stored under that folder

## Step 2: Run the helper

Write the outputs outside `catalog/` (the helper refuses otherwise):

```bash
python3 .draft/framework/tools/migrate_relationships.py --workspace . \
  [--object <uid> | --sdp <uid> | --folder <path>] \
  --report .draft/migration-report.md --patch .draft/migration.patch
```

Upstream, the helper is `framework/tools/migrate_relationships.py`. If it fails
because of a framework bug, follow **Upstream Framework Feedback Routing** in
the Draftsman role.

## Step 3: Present the proposals for review

Read the report and present it grouped as the helper groups it:

- **Needs your input:** ask each question one at a time (the listener a
  swapped call lands on, a protocol and port, which of several systems is
  meant). When an item lists a **near match**, ask whether the call is on that
  existing listener. Never link a near match silently: link it only when the
  user says it is the same listener; otherwise author a new listener.
- **Conversions:** show each one (bidirectional to outbound, swapped source and
  target, externalTarget to a System and Listener) with its file.
- **Removals:** an inbound call from an unknown outside party is removed;
  offer to record its protection on the component's listener
  (`authenticationModel`, `description`).
- **New stubs:** System and Listener stubs to be created, with their UIDs.
- **Protection descriptions:** relationships that describe protection rather
  than a call; offer to move the wording onto the listener.

Ask which proposals to accept. Do not apply anything the user has not approved.

## Step 4: Apply what the user approves

On a branch, apply the approved changes: `git apply .draft/migration.patch` when
everything is accepted, or the accepted edits by hand. Answer the input items
the user resolved by editing the relationships following Listener Lookup Before
Create in `.draft/framework/docs/draftsman.md`. Then follow
`draft-actions/validate.md` and report the result. Edited relationships are
checked as errors again, so fix what validation reports before proposing a PR.
Delete `.draft/migration-report.md` and `.draft/migration.patch` when done.
