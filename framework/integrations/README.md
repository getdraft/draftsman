# DRAFT Integrations: Cursor & Windsurf

These files give IDE assistants the DRAFT rules. `framework/tools/setup_ide.py` reads them and writes the project-level files for each tool.

## Included files

* `cursor/draftsman.mdc`: Cursor rule, written to `.cursor/rules/draftsman.mdc`.
* `windsurf/draftsman.md`: Windsurf rule, written to `.windsurfrules`.

## Setup

From the root of a DRAFT workspace, run:

```bash
python3 .draft/framework/tools/setup_ide.py
```

The script also sets up the Claude Code `/draft` command, GitHub Copilot instructions, the projected skills in `.claude/skills/`, and the skill index in `AGENTS.md`.
