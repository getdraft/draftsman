---
type: documentation
title: "Bring Your Own Agent"
description: "How a company gives its own AI agent the Draftsman capability by loading the DRAFT skills, with no DRAFT-operated agent"
tags:
  - draft
  - documentation
  - skills
  - agents
timestamp: 2026-11-07T00:00:00-07:00
---
# Bring Your Own Agent

DRAFT does not operate an agent for you. It ships the Draftsman as portable skills, and your own agent, in your own harness and under your own credentials, uses them. This page is the whole contract.

## What you get

`framework/skills/` (vendored into a company workspace as `.draft/framework/skills/`) holds:

| Skill | Use it when | Profile |
| :--- | :--- | :--- |
| `draftsman-core` | Always. Holds Evidence Discipline (Recorded, Inferred, Unknown; rules R1 to R6) and the two capability profiles. | both |
| `draftsman-query` | Answering questions about the catalog, standards and requirements | Query or Author |
| `draftsman-author` | Creating or changing catalog and SDP files, onboarding a product | Author |
| `draftsman-review` | Reviewing a pull request or auditing catalog quality and compliance | Author |
| `draftsman-update` | Upgrading the vendored framework (Draft Admins) | Author |
| `draftsman-maturity` | Engineering maturity checks for a repository | Author |

Each skill is a `SKILL.md` with YAML frontmatter plus optional `references/` files. Nothing in them names a chat product, a runtime or a company.

## The four-point contract

1. **Load the skills.** Give your agent `draftsman-core` first, then the workflow skill that matches the request. For Claude Code, run `python3 .draft/framework/tools/setup_ide.py`: it copies the skills into `.claude/skills/` and adds a skill index to `AGENTS.md`. Any other harness can read `.draft/framework/skills/<name>/SKILL.md` directly, or use the `AGENTS.md` index.
2. **Provide the profile's capabilities.**
   - **Query profile:** read access to the catalog files or to the published index (`AI_INDEX.md`, `docs/assets/draft-indexes.json`). No write access.
   - **Author profile:** read the repository, edit files, run local commands (`python3 .draft/framework/tools/validate.py --workspace .`). Pull request work additionally needs your git host tooling.
3. **Publish the index from CI if you need it.** An agent that cannot read the repository can answer from the generated indexes. Run `python3 framework/tools/generate_indexes.py` and `generate_ai_index.py` in your CI and publish the results where the agent can read them. This is optional.
4. **Keep credentials in the harness.** The skills never ask for a token, a key or a password. Your harness holds whatever access the agent has, and decides what it may do.

## Keeping the skills current

`/draft update` refreshes the vendored framework. After it, run `python3 .draft/framework/tools/setup_ide.py` again, then check freshness with `python3 .draft/framework/tools/validate_skills.py --workspace .`. A projection that no longer matches its source fails that check.

## Optional MCP adapter

If your harness prefers tools to files, `framework/tools/mcp_server.py` is an optional MCP server over the catalog index. It answers only from the index: an unknown product, or an ambiguous name, is reported as unknown, never as compliant. Tools: `query_architecture`, `get_c4_diagram`, `check_compliance`, `validate_yaml_object`.

Launch it over stdio from your harness's MCP configuration:

```json
{
  "mcpServers": {
    "draftsman-query-server": {
      "command": "python3",
      "args": [".draft/framework/tools/mcp_server.py"],
      "env": { "DRAFT_CATALOG_INDEX_PATH": "docs/assets/draft-indexes.json" }
    }
  }
}
```

The server needs an index file; it does not build one. It looks in this order: `DRAFT_CATALOG_INDEX_URL` (fetched over HTTP), `DRAFT_CATALOG_INDEX_PATH` (a local JSON index such as `docs/assets/draft-indexes.json`, which `framework/tools/generate_indexes.py` writes), then a file named `catalog_indexes.json` next to the framework or in the working directory (also under `docs/`). With none of these it answers from an empty index and says so on stderr. For a private URL, set `GITHUB_READ_TOKEN` (or `GITHUB_TOKEN`) in the harness environment; the adapter sends it only over https to `github.com` and `githubusercontent.com` hosts. That token is the harness's credential, not a DRAFT one.

## What the skills do not do

They do not run a server, hold secrets, post to chat channels, or open pull requests on their own. Anything beyond reading and editing the repository is what your harness grants.
