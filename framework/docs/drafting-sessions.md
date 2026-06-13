---
type: documentation
title: "DraftingSessions"
description: "A DraftingSession is a machine-readable record of partial architecture work."
tags:
  - draft
  - documentation
  - drafting_sessions
timestamp: 2026-06-12T21:06:02-07:00
---
# DraftingSessions

## What A DraftingSession Is

A DraftingSession is a machine-readable record of partial architecture work.

Use it when the Draftsman or a human architect has enough information to start
building DRAFT content, but not enough to finish every downstream object in one
pass.

The point of the session object is to preserve:

- what the session was trying to build
- what source material informed the work
- what YAML objects were created or proposed
- what assumptions were made so progress could continue
- what questions remain open
- what next steps should be revisited later

This is the framework object that makes prompts like “let’s address open DRAFT
questions for TX-ERP” possible without relying on chat history.

## When To Use One

Create a DraftingSession when:

- source material is incomplete or ambiguous
- a diagram or intake only partially answers the needed questions
- the Draftsman must make best-effort guesses to keep going
- downstream stubs or provisional objects are created
- unresolved questions need to be revisited later in a structured way

Do not use a DraftingSession as a replacement for a SoftwareDeploymentPattern, ReferenceArchitecture, or deployable object. It is a working object
that wraps incomplete authoring state.

## YAML Shape

The authoritative schema is
[drafting-session.schema.yaml](../schemas/drafting-session.schema.yaml).

At minimum, a DraftingSession includes:

- `uid`
- `type: drafting_session`
- `name`
- `sessionStatus`
- `primaryObjectType`
- `sourceArtifacts`
- `generatedObjects`
- `unresolvedQuestions`

Common optional fields include:

- `primaryObjectUid`
- `assumptions`
- `nextSteps`
- `architectureNotes`

## How To Use It

The normal pattern is:

1. Start the session from a partial source such as a Confluence page, Visio,
   spreadsheet, or interview.
2. Create or update the target DRAFT objects with best-effort answers.
3. Record the generated or stubbed objects in `generatedObjects`.
4. Record open questions with their current best guess and impact in
   `unresolvedQuestions`.
5. Record follow-up work in `nextSteps`.

That keeps the draft moving without pretending uncertainty does not exist.

## Relationship To SoftwareDeploymentPatterns

DraftingSessions are especially useful for SoftwareDeploymentPatterns because SoftwareDeploymentPattern authoring often
starts before all downstream runtime details are known.

In that case:

- the SoftwareDeploymentPattern can still be created and validated
- provisional assumptions can be made explicit
- unresolved runtime questions can be tracked outside the SoftwareDeploymentPattern itself

This prevents the SoftwareDeploymentPattern from turning into a dumping ground for half-finished
notes while still preserving the work that remains.
