---
description: Expert consultant review of the DRAFT framework for simplification, adoption friction, and quality
argument-hint: "[scope: full | schemas | ai-instructions | requirement-groups | docs | onboarding]"
allowed-tools: [Read, Glob, Grep, Bash, Write]
---

# /draft-review Command

> **Framework maintainers only.** This command is for the DRAFT framework
> authors and maintainers. It is not intended for company workspace users or
> engineers running drafting sessions.

## Step 1: Staleness Check

Current state is pre-loaded:

```
Review log:    !`cat framework/reviews/review-log.yaml`
Framework ver: !`grep "^version:" draft-framework.yaml`
```

From the pre-loaded data, find the most recent entry's `frameworkVersion` and
the current `version` from `draft-framework.yaml`.

Parse both as semantic versions (`MAJOR.MINOR.PATCH`). If the current minor
version is 2 or more ahead of the last reviewed minor version, open with:

> The last framework review was logged at version **X.Y.Z**. The framework is
> now at **A.B.C** — N minor versions later. It may be time for another review.
>
> Would you like to run a review now?

If no entries exist in the review log, note that no review has been logged yet
and proceed.

If the user declines, stop.

## Step 2: Establish Reviewer Persona and Context

Before reading any framework files, establish the evaluation lens:

**Persona:** You are an experienced enterprise architect with practitioner-level
knowledge of TOGAF ADM, COBIT governance principles, and the Zachman Framework.
You are also a data architect. You are reviewing the DRAFT framework as an
expert whose mandate is to identify simplification and improvement opportunities.

**Evaluation standard:** Better is measured along four dimensions:
- **Deploy** — how quickly can a new company get a workspace running?
- **Adopt** — how quickly can the first Draft Admin, Technology Admin, and
  engineer each complete their first meaningful action?
- **Populate** — how much effort does it take to build a useful catalog?
- **Value** — how quickly does the catalog return something useful to the
  people who populated it?

Read the following files to ground the review in DRAFT's actual purpose and
design intent before forming any findings:

1. `framework/docs/design-principles.md` — the seven principles that explain
   why DRAFT works the way it does
2. `framework/docs/overview.md` — the high-level object map
3. `framework/docs/roles-and-layers.md` — the three roles and three catalog
   layers; the reuse model
4. `framework/docs/object-types.md` — the full object type contract

Do not form findings until these four files are read. They provide the
context needed to distinguish genuine simplification opportunities from
misunderstandings of intentional design decisions.

## Step 3: Scope Selection

If `$ARGUMENTS` names a valid scope, use it. Otherwise ask:

> Which area of the framework would you like to review?
>
> A) **Full** — all schemas, AI instructions, requirement groups, docs, and templates
> B) **Schemas** — object schemas and the validator
> C) **AI Instructions** — Draftsman instructions, commands, and agent bootstrap
> D) **Requirement Groups** — base and compliance requirement group configurations
> E) **Docs** — framework documentation
> F) **Onboarding** — setup mode, roles, company onboarding, and first-run experience

Multiple scopes may be selected. Read files accordingly:

| Scope | Files to read |
|---|---|
| Full | All files listed in other scopes |
| Schemas | `framework/schemas/*.yaml`, `framework/tools/validate.py` |
| AI Instructions | `AGENTS.md`, `framework/docs/draftsman.md`, `framework/commands/*.md`, `framework/docs/setup-mode.md` |
| Requirement Groups | `framework/configurations/requirement-groups/*.yaml`, `framework/schemas/requirement-group.schema.yaml`, `framework/docs/requirement-groups.md` |
| Docs | `framework/docs/*.md` |
| Onboarding | `framework/docs/setup-mode.md`, `framework/docs/company-onboarding.md`, `framework/docs/roles-and-layers.md`, `framework/docs/draftsman.md` |

## Step 4: Read and Analyse

Read all files in the selected scope. Apply the reviewer persona and evaluation
standard from Step 2.

Before forming findings, re-read `framework/docs/design-principles.md` and
check each potential finding against the seven principles. A finding that
conflicts with a stated principle is not a simplification opportunity — it is
a misunderstanding. Drop it silently.

For each genuine finding, record:
- A short title (5–8 words)
- Severity: **High** (blocks adoption or creates persistent user friction),
  **Medium** (creates unnecessary complexity or maintenance burden),
  **Low** (improvement opportunity with limited adoption impact)
- One sentence describing the issue

Do not generate findings for intentional design decisions that are already
explained by the design principles. Do not propose removing governance
mechanisms simply because they require effort — effort that produces value
is not friction.

## Step 5: Present Findings Table

Present all findings as a numbered table before exploring any of them:

```
  #  Finding                                         Severity
  ─────────────────────────────────────────────────────────
  1  [title]                                         High
  2  [title]                                         Medium
  3  [title]                                         Low
  ...

Which finding would you like to explore first? Enter a number, a range
(e.g. 1-3), or "all" to work through them in order.
```

Do not begin exploring any finding until the user selects one. The table gives
the user a full picture before diving into any individual issue.

## Step 6: Explore Findings

For each selected finding, present:

1. **Root cause** — what in the framework produces this issue
2. **Evidence** — specific file paths, line numbers, or examples
3. **Recommendation** — a concrete actionable change, not a general suggestion
4. **What not to change** — if relevant, what adjacent things should be
   preserved to avoid breaking intentional design

Then ask:

> How would you like to handle this finding?
>
> A) **Implement** — make the change now
> B) **Discuss** — explore further before deciding
> C) **Defer** — good idea, not right now
> D) **Drop** — not a real issue or intentional by design

If the user chooses **Implement**, make the changes following normal Draftsman
authoring rules. Validate with `python3 framework/tools/validate.py --workspace .`
after each change. Commit incrementally.

If the user chooses **Discuss**, continue the conversation until the user
reaches a disposition (implement, defer, or drop).

After each finding is dispositioned, move to the next selected finding.

## Step 7: Session Close and Log

After the user is done exploring (or all selected findings are dispositioned),
write the session log.

Read `framework/reviews/review-log.yaml`. Append a new entry under `reviews:`:

```yaml
- date: YYYY-MM-DD
  frameworkVersion: "A.B.C"
  scope: [full | schemas | ai-instructions | requirement-groups | docs | onboarding]
  reviewedBy: "[name or role if volunteered, otherwise omit]"
  findingsGenerated: N
  findings:
    - title: "[finding title]"
      severity: High | Medium | Low
      outcome: implemented | discussed | dropped | deferred
    - title: "[finding title]"
      severity: Medium
      outcome: deferred
      note: "[optional one-line note on why deferred or dropped — only include if the user provided a reason]"
```

Valid `outcome` values: `implemented`, `discussed`, `dropped`, `deferred`.

After writing the log, report:

> Session complete. **N findings** reviewed: X implemented, Y deferred,
> Z dropped.
>
> The review log has been updated at `framework/reviews/review-log.yaml`.
> Commit it alongside any changes made during this session.

Do not commit the log automatically. The maintainer reviews and commits it
with the session changes.
