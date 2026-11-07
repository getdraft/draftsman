# Plan quality loop rounds

## Cycle 1 (reviewer: sonnet, jurors: 3x haiku)

| Finding | Severity | Juror A | Juror B | Juror C | Keeps | Result |
|---|---|---|---|---|---|---|
| F1 banned-term grep/lint false positives | blocker | keep | keep | keep | 3/3 | survives |
| F2 pytest gate vs CI unittest; CI step missing | bug | keep | keep | keep | 3/3 | survives |
| F3 framework.lock has no home in framework repo | bug | keep | keep | keep | 3/3 | survives |
| F4 MCP location, existing mcp_server.py, setup_ide overlap | bug | keep | keep | keep | 3/3 | survives |
| F5 skill set sources, names, review/update are new | bug | keep | keep | keep | 3/3 | survives |
| F6 generate_diagram.py only on #196 branch | bug | keep | keep | keep | 3/3 | survives |
| F7 E3 ordering; validate hook owned twice | bug | keep | keep | keep | 3/3 | survives |
| F8 CHANGELOG Unreleased entry needed in first PR | bug | keep | keep | keep | 3/3 | survives |
| F9 fixture checker format unspecified | nit | keep | drop | keep | 2/3 | dropped (nit needs 3/3) |

Orchestrator verification while revising found one more fact the plan must honor (not a juror finding):
`framework/integrations/` also holds `cursor/` and `windsurf/` templates that `setup_ide.py` reads, so only `slack/`, `discord/` and the README may be deleted. `framework/tools/validate.py` is a contract path in `check_release_notes.py`, so removing its agent hook is a contract change.

## Cycle 2 (reviewer: fresh sonnet, jurors: 3x haiku)

| Finding | Severity | Juror A | Juror B | Juror C | Keeps | Result |
|---|---|---|---|---|---|---|
| F1 skills not in draft_table FRAMEWORK_VENDOR_DIRS; non-goal wrong | blocker | keep | keep | keep | 3/3 | survives |
| F2 promote-release fires on every push to main; Unreleased consumed by E1 | blocker | keep | keep | keep | 3/3 | survives |
| F3 review.md/update.md exceed 200-line budget; step list undefined | bug | keep | keep | keep | 3/3 | survives |
| F4 generated header vs YAML frontmatter first; multi-file hash | bug | keep | keep | keep | 3/3 | survives |
| F5 freshness check compares nothing; symlinks cannot carry hash | bug | keep | keep | keep | 3/3 | survives |
| F6 git grep -E \b passes vacuously on macOS; KPF.md hit | bug | keep | keep | keep | 3/3 | survives |
| F7 E5 text list incomplete; soul.md links and content destination | bug | keep | keep | keep | 3/3 | survives |
| F8 agent/skills/draftsman and SOUL sections 1-2 have no destination | bug | keep | keep | keep | 3/3 | survives |
| F9 MCP tests retarget may expose differences | bug | keep | keep | keep | 3/3 | survives |
| F10 validate_skills.py must pass with one skill; E4 extends | bug | keep | drop | drop | 1/3 | dropped |
| F11 five rules not pinned by phrase | nit | keep | keep | keep | 3/3 | survives |
| F12 400-line limit source | nit | drop | keep | keep | 2/3 | dropped |

Orchestrator notes while revising: framework/personalities/ does not exist upstream (it is in FRAMEWORK_VENDOR_DIRS); soul.md has no cast-member fields although workspaces.md cites it for them.

## Cycle 3 (reviewer: fresh sonnet, jurors: 3x haiku)

| Finding | Severity | Juror A | Juror B | Juror C | Keeps | Result |
|---|---|---|---|---|---|---|
| F1 E6 adds a framework/docs file but only E5 requires AI_INDEX/indexes regeneration | blocker | keep | keep | keep | 3/3 | survives |
| F2 removal unittest and validate_skills.py match their own banned literals | blocker | keep | keep | keep | 3/3 | survives |
| F3 E3 move/rename of agent/skills dirs breaks validate_agent_package hook until E5 | bug | keep | keep | keep | 3/3 | survives |
| F4 draft-actions/validate.md has no matching skill | bug | keep | keep | keep | 3/3 | survives |
| F5 freshness check (a) compares a hash to itself | bug | keep | keep | keep | 3/3 | survives |
| F6 version bump is automatic (minor), not chosen by maintainers | bug | keep | keep | keep | 3/3 | survives |
| F7 integration branch conflicts on CHANGELOG Unreleased with #196 and main | nit | keep | keep | keep | 3/3 | survives |

Cycle cap reached (3). Plan not revised for cycle 3 findings. Stopped for user decision.

## Cycle 3 fixes applied (user chose: apply 7 fixes, re-run 1 cycle as exception to the cap)
F1: rule 'Generated indexes' for every story, E6 regeneration criterion. F2: allowlist for the lint files. F3: 'agent/ untouched until E5' rule, E3 copies. F4: validate stays a direct action. F5: freshness check (a) dropped, workspace check plus unit tests. F6: bump stated as automatic minor. F7: merge-main step and risk row.

## Cycle 4 (extra cycle, user-approved exception; reviewer: fresh sonnet, jurors: 3x haiku)

| Finding | Severity | Juror A | Juror B | Juror C | Keeps | Result |
|---|---|---|---|---|---|---|
| F1 E3 heading test reads action files that E4 turns into routers | blocker | keep | keep | keep | 3/3 | survives; fixed (fixtures) |
| F2 removal test would scan committed .sdlc/ artifacts | bug | keep | keep | keep | 3/3 | survives; fixed (.gitignore, git ls-files, rule) |
| F3 E1 says 'moves' where it means 'copies' | nit | keep | drop | keep | 2/3 | dropped |

No further cycle run. The F1 and F2 fixes were applied after the cycle and have not been re-reviewed.
