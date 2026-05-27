# Drafting Sessions

## What A Drafting Session Is

A Drafting Session is a machine-readable record of partial architecture work.

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

Create a Drafting Session when:

- source material is incomplete or ambiguous
- a diagram or intake only partially answers the needed questions
- the Draftsman must make best-effort guesses to keep going
- downstream stubs or provisional objects are created
- unresolved questions need to be revisited later in a structured way

Do not use a Drafting Session as a replacement for a Software Deployment
Pattern, Reference Architecture, or deployable object. It is a working object
that wraps incomplete authoring state.

## YAML Shape

The authoritative schema is
[drafting-session.schema.yaml](../schemas/drafting-session.schema.yaml).

At minimum, a Drafting Session includes:

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
2. Create or update the target architecture objects with best-effort answers.
3. Record the generated or stubbed objects in `generatedObjects`.
4. Record open questions with their current best guess and impact in
   `unresolvedQuestions`.
5. Record follow-up work in `nextSteps`.

That keeps the draft moving without pretending uncertainty does not exist.

## Relationship To Software Deployment Patterns

Drafting Sessions are especially useful for Software Deployment Patterns because Software Deployment Pattern authoring often
starts before all downstream runtime details are known.

In that case:

- the Software Deployment Pattern can still be created and validated
- provisional assumptions can be made explicit
- unresolved runtime questions can be tracked outside the Software Deployment Pattern itself

This prevents the Software Deployment Pattern from turning into a dumping ground for half-finished
notes while still preserving the work that remains.
