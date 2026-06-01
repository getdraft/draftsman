---
description: Start or resume a guided DraftingSession for a system or product
argument-hint: "[system name or topic]"
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion]
---

# /draft session

Start or resume a DraftingSession. A DraftingSession captures in-progress
architecture work, interviews the user for missing facts, and produces valid
DRAFT catalog content.

## Step 1: Bootstrap

Read:

1. `AGENTS.md`
2. `.draft/framework/AI_INDEX.md`
3. `.draft/workspace.yaml`

## Step 2: Find or Create a Session

**If `$ARGUMENTS` is provided:** Use the argument as the system name or topic.
Search `catalog/sessions/` for an existing session file whose `uid` or `name`
matches that value (case-insensitive).

**If no arguments:** List any existing session files in `catalog/sessions/`
and ask:

> Which system or product area would you like to draft? I can resume an
> existing session or start a new one.

## Step 3: Load Session Context

If an existing session file is found:

- Read the session YAML.
- Summarize what is already known and what open questions remain.
- Ask: *"Would you like to continue this session or start fresh?"*

If no session exists:

- Confirm with the user what the session topic is.
- Read `.draft/framework/docs/drafting-sessions.md` for the session structure.
- Begin the interview, asking at most three questions at a time.

## Step 4: Run the Session

Follow the Draftsman role in `.draft/framework/docs/draftsman.md` throughout:

- Record open questions, assumptions, and next steps in the session file so the
  work is resumable; keep the live conversation focused on the current step
  rather than displaying a running backlog of remaining or revisit-later items.
- Produce or update catalog YAML from session discoveries.
- If the session exposes a framework-owned bug or reusable feature request,
  follow **Upstream Framework Feedback Routing** from the Draftsman role. With
  user approval, create the upstream public issue and record its URL in the
  session summary or unresolved follow-up.
- Validate with `python3 .draft/framework/tools/validate.py --workspace .`
  after each YAML update.
- Before ending, save the session file with all open questions and assumptions
  recorded so the session can be resumed later.
