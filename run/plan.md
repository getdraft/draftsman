# Plan: Draftsman Skill Pack (replace the deployed agent)

Source design: `framework/docs/proposals/rfc-draftsman-skill-pack.md` (branch `docs/rfc-draftsman-skill-pack`, uncommitted). This plan is the executable form of that RFC. Where they differ, this plan wins, and E1 commits the RFC with the corrections listed at the end.

Repo: `getDraft/draftsman`. Final target: `main`. Working base for every story PR: the integration branch `feat/draftsman-skill-pack`, created from `main` (see "Release model").

## Outcome

Any company can give its own agent the Draftsman capability by vendoring files, with no DRAFT-operated agent, container, secret, or chat integration. When this plan is done:

1. `framework/skills/` holds `draftsman-core` (always loaded) and six workflow skills, and is delivered to company workspaces as `.draft/framework/skills/` by the framework refresh.
2. Evidence Discipline (Recorded / Inferred / Unknown) lives in `draftsman-core` as the single source, in a form that also fits an agent reading catalog files directly, not only a pre-built index.
3. `framework/tools/setup_ide.py` projects the skills into `.claude/skills/` and a generic `AGENTS.md` skill index, alongside its existing Cursor, Windsurf, Copilot and Claude command output.
4. `python3 framework/tools/validate_skills.py` passes, runs in CI, and enforces frontmatter, size budgets, link integrity, the portability lint, projection freshness, and the Evidence Discipline fixtures.
5. `agent/`, the Slack and Discord integrations, the gatekeeper workflow, and every reference to the removed delivery model, Archie, Switch agents and `switch-game-architect` are gone, apart from CHANGELOG history and an explicit allowlist.

## Non-goals

- A new skill format. Use the existing `SKILL.md` convention.
- Any change to the DRAFT object model, schemas, or catalog validation logic.
- Keeping, relocating, or exampling any deployment, IaC, chat-channel, or company-specific agent content. Delete it.
- Editing `draft-framework.yaml` or bumping the version. The promote-release workflow does that.
- Changing the framework-lock logic or `.draft/framework.lock` handling in `draft_table/repo.py`. (E4 does edit `draft_table/repo.py`, but only to add `skills` to the vendored directories and path rewrites.)
- Changing the existing Cursor, Windsurf, or Copilot projections that `setup_ide.py` already writes.
- Resolving the distributed-architecture work (#195).

## Release model (decides what "deploy" means here)

`.github/workflows/promote-release.yml` runs on every push to `main`. If `CHANGELOG.md` has `## Unreleased`, it bumps `draft-framework.yaml`, renames the header to a numbered version, and commits to `main`. Merging story PRs straight to `main` would therefore cut a release per story and ship the removals piecemeal.

So:

- Create the integration branch `feat/draftsman-skill-pack` from `main` before E1 starts. Every story PR targets it. Merging a story PR does not trigger promote-release, because that workflow fires only on pushes to `main`. CI (`validate-catalog.yml`, which runs on every pull request) still runs on each story PR.
- E1 creates the `## Unreleased` section on the integration branch. Every later story appends to it.
- **The single release point** is one PR from `feat/draftsman-skill-pack` into `main`, opened at the end of E6. That PR is **not merged by the loop**. The user merges it, which triggers promote-release once with one complete release.
- The SDLC run's base branch is `feat/draftsman-skill-pack`, not `main`. The run's "merge, then stop" stop point merges clean story PRs into the integration branch only.

## Assumed decisions (confirm at plan approval)

| Decision | Assumed |
| :--- | :--- |
| Skills location | `framework/skills/`, with `draft_table/repo.py` changed in E4 so refresh vendors it |
| Canonical identity text | The Evidence Discipline section of `agent/SOUL.md`; the rest merged per the disposition table in E1 and E3 |
| Skill set | See the E3 table. Names are fixed. |
| Launch adapters | Claude Code (`.claude/skills/`) and a generic `AGENTS.md` skill index. Others are out of scope. |
| Behavior fixtures | `tests/fixtures/evidence_discipline/`, one JSON file per fixture (format under E2) |
| Deprecation window | None. No known consumers of `agent/` or the Slack and Discord integrations. |
| MCP | `framework/tools/mcp_server.py` already exists as a near-duplicate of `agent/mcp/server.py`. Keep it, delete `agent/mcp/`. |
| Diagram skill timing | Waits for PR #196 to merge to `main`, then the integration branch is updated from `main` before the diagram story starts. |
| Evidence Discipline for Author profile | Reworded for agents that read files directly (new text, not a move) |

## Prerequisites (hard gates)

- Plan approved, and `feat/draftsman-skill-pack` created from `main` and pushed.
- PR #196 is merged to `main` and merged into the integration branch before the E3 diagram story starts. No other story depends on it.
- The unmerged `beta` rename of "Pattern 2" does not block this work. Skills must not name "Pattern 2".

## Epics (titles only, in order)

1. **E1: Core skill, Evidence Discipline, RFC commit, and the Unreleased release-notes entry**
2. **E2: Skill validator, portability lint, and Evidence Discipline fixtures**
3. **E3: Workflow skills extracted and made harness-neutral**
4. **E4: Distribution: vendoring, projections, `/draft` routers, MCP adapter, freshness check**
5. **E5: Removal of agent-delivery content**
6. **E6: Bring-your-own-agent guide, release-notes completion, and the release PR**

Order: E1, E2, E3, E4, E5, E6. E2 needs only `draftsman-core`. E3 is gated by the E2 lint. E4 needs E3. E5 needs E4 (nothing may still point at `agent/`). `validate_skills.py` is added alongside the existing `validate_agent_package` hook in E2 and extended in E4 with the freshness check. The hook is removed only in E5.

## Rules for every story

- **Generated indexes.** Any story that adds, removes, or edits a file under `framework/docs/*.md` (or anything else that feeds the indexes) runs `python framework/tools/generate_indexes.py` and `python framework/tools/generate_ai_index.py` and commits the results. `git diff --exit-code docs/assets/draft-indexes.json AI_INDEX.md` must be clean after that. CI enforces this on every PR.
- **`agent/` is untouched until E5.** `framework/tools/validate.py` runs `validate_agent_package` on every CI run, and that check requires every skill in `agent/agent-spec.yaml` to exist under `agent/skills/`. So E1 to E4 copy content out of `agent/` and never move, rename, or delete anything under it. `python framework/tools/validate.py` must pass on every story PR.
- **Run artifacts are never committed.** `.sdlc/` is added to `.gitignore` in E1, and no story PR may stage anything under `.sdlc/`. The removal test (E5) scans only `git ls-files`, so ignored or untracked run files are not scanned.
- **CHANGELOG.** Every story appends its bullets to the single `## Unreleased` section on the integration branch.

## Acceptance criteria

Each is checkable by a command or file check. The test gate is `python -m unittest discover -s tests` (what CI runs). New tests are `unittest` tests that need nothing beyond `pyyaml`.

**E1**
- `framework/skills/draftsman-core/SKILL.md` exists, is under 150 lines, and has valid frontmatter (`name`, and a `description` stating when to use it).
- It contains the Recorded / Inferred / Unknown table and these five rules, each under a stable label (`R1` to `R5`) with the key phrase in brackets, and a unit test asserts each key phrase is present: R1 [relationship the index does not characterise], R2 [parse prose into structure], R3 [the catalog does not record], R4 [A count is a claim], R5 [Refusing is a valid answer].
- It defines exactly two capability profiles, Query and Author, and names no channel, runtime, credential, or company agent.
- It adds an Author-profile rule `R6`: a field the agent guessed while authoring is labeled as inferred, and an unwritten relationship is not asserted.
- Long material is in `framework/skills/draftsman-core/references/`. The character, voice, session-feel, cognitive-design and never-does content of `framework/docs/soul.md` moves to `references/character.md`. The onboarding playbook from `agent/SOUL.md` ("How do I get my product into DRAFT?") moves to `references/onboarding.md` with all Slack, Discord and Web UI wording removed.
- `framework/docs/proposals/rfc-draftsman-skill-pack.md` is committed with the corrections listed under "RFC corrections".
- `.gitignore` contains `.sdlc/`.
- `CHANGELOG.md` gets a `## Unreleased` section with the five required subsections (Compatibility Impact, Added, Changed, Fixed, Migration Notes) on the integration branch, and `python framework/tools/check_release_notes.py` passes.

**E2**
- `framework/tools/validate_skills.py` runs with `python3` and `pyyaml` only and exits non-zero on: missing or invalid frontmatter, a `SKILL.md` over its line budget (150 for `draftsman-core`, 200 for every other skill's `SKILL.md`; `references/` files are not budgeted), a broken relative link or missing script path, or a banned term.
- It exits zero on a skills directory containing only `draftsman-core`.
- The portability lint scans only `framework/skills/`. It matches these case-insensitive patterns with word boundaries: `\bslack\b`, `\bdiscord\b`, `\bhermes\b`, `\bfargate\b`, `\barchie\b`, `\bcentral chat\b`, the literal `switch-game-architect`, and the literal `ANTHROPIC_API_KEY`. It does not match the bare word "switch" or "hierarchy".
- A `unittest` module exercises each failure mode with a small bad skill in a temp dir, plus the passing case.
- Evidence Discipline fixtures live in `tests/fixtures/evidence_discipline/` as JSON: `{id, rule, question, index_excerpt, forbidden_phrases, required_phrases}`. There is one fixture per rule R1 to R6. A deterministic test asserts that, for each fixture, `draftsman-core` contains the rule's key phrase, and that `forbidden_phrases` and `required_phrases` are non-empty. The fixtures are not run against a live model, and the PR says so.
- `.github/workflows/validate-catalog.yml` has a step `python framework/tools/validate_skills.py`, and the Unreleased entry records the workflow change.

**E3**
- Exactly these skill directories exist under `framework/skills/` in addition to `draftsman-core`. The table is the complete disposition of the eight existing `agent/skills` and of `SOUL.md` and `soul.md`.

| Source | Destination | Kind |
| :--- | :--- | :--- |
| `agent/skills/draftsman` (unified role skill, dual-mode text) | `draftsman-core` (profiles replace dual modes; E1 already covers this). Any content not covered by E1 goes to `draftsman-core/references/` | merge |
| `agent/SOUL.md` sections 1 and 2 (role, onboarding) | `draftsman-core` and `references/onboarding.md` (E1) | merge |
| `agent/skills/draftsman-author`, `draftsman-autodiscover`, `framework/draft-actions/guide.md` | `draftsman-author` | merge into a new skill; originals deleted in E5 |
| `agent/skills/draftsman-query`, `draftsman-standards` | `draftsman-query` | merge into a new skill; originals deleted in E5 |
| `framework/draft-actions/review.md` | `draftsman-review` | new skill from an action file |
| `agent/skills/draftsman-diagram` (including the #196 rendered-page section) | `draftsman-diagram` | copy; original deleted in E5 |
| `agent/skills/draftsman-engineering-maturity` | `draftsman-maturity` | copy under the new name, strip company names; original deleted in E5 |
| `framework/draft-actions/update.md` | `draftsman-update` | new skill from an action file |
| `agent/skills/switch-game-architect` | none | deleted in E5 |
| `framework/docs/soul.md` | `draftsman-core/references/character.md` (E1) | merge, then deleted in E5 |

- Each skill states which profile it needs and passes `validate_skills.py`. `agent/skills/` is byte-for-byte unchanged by E3 (checked with `git diff --exit-code <integration-base> -- agent/` in the story's PR), and `python framework/tools/validate.py` passes.
- `draftsman-review` and `draftsman-update` keep `SKILL.md` within the 200-line budget by holding a one-line summary per step in `SKILL.md` and the verbatim step bodies in `references/steps.md`. In E3, the story records "the step list" as fixture files `tests/fixtures/skills/step_lists/review.txt` and `update.txt`, each holding every `##` and `###` heading of the source action file as it exists at that time. A unit test asserts each recorded heading appears as a heading in the matching skill folder (`SKILL.md` or `references/`). The test reads only the fixtures and the skill, never the live action files, so E4 can turn the action files into routers without breaking it.
- `switch-game-architect` is not present in `framework/skills/`.
- `draftsman-diagram` documents `generate_diagram.py`, and `framework/tools/generate_diagram.py` exists on the integration branch before this story starts.
- Every script path a skill references exists under `framework/tools/`.

**E4**
- `draft_table/repo.py` adds `skills` to `FRAMEWORK_VENDOR_DIRS` and adds `framework/skills/` and `framework/skills` entries to the path-rewrite map in `vendored_framework_text`, matching the existing `integrations` entries. An existing-style test in `tests/` asserts a fresh refresh in a temp dir yields `.draft/framework/skills/draftsman-core/SKILL.md`. The Unreleased entry records the `draft_table/` governed-path change.
- `framework/tools/setup_ide.py` additionally writes `.claude/skills/<name>/` for each skill (as copies, never symlinks) and a generic `AGENTS.md` skill index. It leaves the existing Cursor, Windsurf, Copilot, and Claude command output unchanged, and its existing tests pass.
- Generated-file marker: each projected `.claude/skills/<name>/SKILL.md` keeps its YAML frontmatter first and adds the frontmatter fields `generated: true` and `source_sha256: <hash>`. The generic `AGENTS.md` index carries the same marker as a leading HTML comment, since it has no frontmatter requirement. `<hash>` is the sha256 over the sorted relative paths and bytes of every file in the source skill directory (so `references/` and any scripts are included).
- Freshness, with no lock file: `validate_skills.py --workspace <path>` compares each `<path>/.claude/skills/*/SKILL.md` `source_sha256` to the hash of the matching `<path>/.draft/framework/skills/*` directory and fails on any mismatch or missing projection. A unit test projects the skills into a temp workspace with `setup_ide.py` and asserts the check passes, then edits a source skill and asserts the check fails. A second unit test asserts the markers (`generated: true` and a hash matching an independently computed sha256) are present in each projection. `draft update` is documented to rerun `setup_ide.py`. The framework repo itself commits no projections.
- `framework/commands/draft.md` and `framework/draft-actions/guide.md`, `review.md`, and `update.md` route to `draftsman-author`, `draftsman-review`, and `draftsman-update` respectively. `framework/draft-actions/validate.md` stays a direct action (it runs `validate.py` and has no skill), and `draft.md` says so. `/draft guide`, `review`, `update`, and `validate` all still resolve.
- The optional MCP adapter is `framework/tools/mcp_server.py` (existing). `tests/test_agent_mcp_tools.py` is retargeted to it and renamed `tests/test_mcp_server.py`. Its tests must pass against `mcp_server.py`. If a test fails because of a real behavior difference, either the test expectation is corrected (when the difference is intended) or `mcp_server.py` is fixed; both are in scope and the PR lists each change. The test docstring no longer references `validate_agent_package.py`. `KPF-DFT-004` in `KPF.md` is repointed and renamed in the same PR.

**E5**
- Deleted: `agent/` (all of it), `framework/integrations/slack/`, `framework/integrations/discord/`, `framework/integrations/README.md` (or rewritten to describe only `cursor/` and `windsurf/`), `framework/tools/validate_agent_package.py`, `framework/docs/soul.md`.
- Kept: `framework/integrations/cursor/` and `framework/integrations/windsurf/`, which `setup_ide.py` reads.
- `framework/tools/validate.py` has no reference to `validate_agent_package` or `agent/agent-spec.yaml`. Because `validate.py` is a contract path in `check_release_notes.py`, the release will be bumped to a minor version automatically. The Compatibility Impact section states the contract-path change and the removals.
- Text removed or rewritten: the Slack, Discord and Web UI mode text in `framework/docs/draftsman.md` and `framework/docs/decentralized-sdp-setup.md`; the whole `agent/` section of `README.md` (the bullets around lines 114 to 118, including the SOUL.md, bindings and `DEPLOYMENT.md` lines) and the factory-agent sentence near line 26; `KPF-DFT-004` in `KPF.md` is already handled in E4 and must leave no Hermes mention.
- Dangling links fixed: `framework/docs/draftsman.md` (around line 21) and `framework/docs/workspaces.md` (around line 325) no longer link to `soul.md`. They link to the skill's `references/character.md`. The `workspaces.md` sentence about "cast member fields" is checked against `soul.md`: that file has no cast fields, so the sentence is removed or repointed to `framework/personalities/README.md` only if that file exists. A unit test asserts no markdown link under `framework/`, `README.md` or `docs/` points to a deleted path (`soul.md`, anything under `agent/`).
- After running `python framework/tools/generate_indexes.py` and `generate_ai_index.py`, `git diff --exit-code docs/assets/draft-indexes.json AI_INDEX.md` is clean.
- Removal check, platform independent: a `unittest` (`tests/test_no_agent_delivery_content.py`) scans every tracked file with Python `re` for `\b(slack|discord|hermes|gatekeeper|archie|fargate)\b|switch-game` (case-insensitive) and fails on any match outside this allowlist: `CHANGELOG.md`, `framework/docs/proposals/`, `framework/docs/ticketing.md` (Slack as a downstream ticket integration), `framework/docs/operations-guide.md` (a Slack channel as a contact example), and the files that must name the banned terms to enforce or test the ban: `tests/test_no_agent_delivery_content.py`, `framework/tools/validate_skills.py`, `tests/test_validate_skills.py`, `tests/test_draftsman_core.py` (asserts the core skill's rule phrases and the lint terms), `tests/test_skill_set.py` (names `switch-game-architect` to assert it is absent), and `tests/fixtures/skills/` (the bad-skill fixtures). The equivalent manual command is `git grep -n -P -i "\b(slack|discord|hermes|gatekeeper|archie|fargate)\b|switch-game" -- . ':!CHANGELOG.md' ':!framework/docs/proposals' ':!framework/docs/ticketing.md' ':!framework/docs/operations-guide.md' ':!tests/test_no_agent_delivery_content.py' ':!framework/tools/validate_skills.py' ':!tests/test_validate_skills.py' ':!tests/test_draftsman_core.py' ':!tests/test_skill_set.py' ':!tests/fixtures/skills'`, which must be run with `-P`, because `\b` is not reliable under `-E` on macOS.
- `python -m unittest discover -s tests`, `python framework/tools/validate.py`, and `python framework/tools/validate_skills.py` all pass.

**E6**
- `framework/docs/bring-your-own-agent.md` exists, `AI_INDEX.md` and `docs/assets/draft-indexes.json` are regenerated and clean, and it states the four-point contract: load the skills, provide the profile's capabilities, publish the index from CI if needed, keep credentials in the harness.
- The CHANGELOG Unreleased entry is complete: all five subsections filled in, removals listed, and the migration note tells any unknown consumer to load `framework/skills/` instead.
- `draft-framework.yaml` is unchanged. `check_release_notes.py` passes.
- `main` is merged into `feat/draftsman-skill-pack` and any `## Unreleased` conflict is resolved to a single section. All CI checks pass on the integration branch.
- A single PR from `feat/draftsman-skill-pack` into `main` is opened and left for the user to merge. The loop does not merge it.

## RFC corrections (done in E1)

The RFC has these errors, fixed when it is committed:
1. It says `framework/integrations/` is deleted whole. Only `slack/`, `discord/` and the README go; `cursor/` and `windsurf/` stay.
2. It says the MCP adapter moves to `framework/tools/mcp/`. `framework/tools/mcp_server.py` already exists, so `agent/mcp/` is deleted and the existing file is kept.
3. It omits the `validate.py` hook removal, the `draft_table/repo.py` vendoring change, and the release model above.
4. It says skills "arrive with the rest of the framework" with no code change; they need the vendoring change in E4.

## Deploy points

One, and it is outside the loop: the merge of `feat/draftsman-skill-pack` into `main`, done by the user, which triggers promote-release once. No story deploys anything.

## Risks

| Risk | Mitigation |
| :--- | :--- |
| Evidence Discipline is dropped or weakened in the merge | Per-rule key-phrase tests and fixtures gating CI before `agent/SOUL.md` is deleted in E5 |
| Skills drift back to naming a harness | Portability lint in CI, landing in E2 before any workflow skill is added |
| Premature release per merged story | Integration branch; one release PR to `main`, merged by the user |
| Integration branch drifts from `main`; `CHANGELOG.md` `## Unreleased` conflicts (PR #196 and E1 both add one, and promote-release renames it on `main`) | Merge `main` into the integration branch when #196 lands and again before the E6 release PR. On conflict, keep a single `## Unreleased` section containing both sets of bullets. |
| Banned-term checks give false positives or pass vacuously | Word-boundary patterns scoped to `framework/skills/`; removal check is a Python `unittest` with an explicit allowlist, not a platform-dependent grep |
| Deleting `agent/` or `soul.md` leaves dangling links | Link-integrity unit test in E5, generated-index diff, full unittest run |
| Deleting `framework/integrations/` whole breaks `setup_ide.py` | E5 deletes only `slack/`, `discord/` and the README |
| Skills do not reach workspaces | E4 adds `skills` to vendored dirs with a refresh test |
| Projection staleness undetected | Hash markers in frontmatter, checked in the framework repo and in workspaces |
| Editing `validate.py` is a contract-path change, and `draft_table/` is governed | The version bump is automatic, not chosen: `check_release_notes.py --detect-bump` (called by promote-release) returns **minor** when `framework/tools/validate.py` changes and never returns major, even though this release deletes `agent/` and the integrations. The Compatibility Impact section says so. A major bump would need a manual edit to the manifest or workflow and is a maintainer decision outside this plan. |
| Author-profile Evidence Discipline wording is new and untested on a live model | Fixtures check structure and rule presence only; the PR states that |
| Non-Claude harness adapters are untested | Only Claude Code and the generic index ship; others are out of scope |

## Decisions made at approval

1. A CHANGELOG notice is enough for removing `agent/` and the Slack and Discord integrations. No separate heads-up.
2. The Author-profile rule R6 ships in the E1 PR and is reviewed there. No separate maintainer review beforehand. The E1 PR description must flag R6 as new text (not a move) and as untested on a live model.

## Open questions

None.
