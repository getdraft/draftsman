#!/usr/bin/env python3
"""
Skill Validator: checks SKILL.md frontmatter, line budgets, relative links and script paths.

Reads files only. It never executes skill scripts.

Usage:
    python3 framework/tools/validate_skills.py [--skills-dir DIR]

Exit codes:
    0  every skill passed
    1  at least one skill failed a check
    2  the skills directory does not exist
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


TOOLS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_ROOT.parent.parent
DEFAULT_SKILLS_DIR = REPO_ROOT / "framework" / "skills"

CORE_SKILL = "draftsman-core"
CORE_LINE_BUDGET = 150
OTHER_LINE_BUDGET = 200

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SCRIPT_PATH_RE = re.compile(r"(?<![\w./-])(scripts/[\w./-]*[\w-])")
URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
INLINE_CODE_RE = re.compile(r"`[^`]*`")


def line_budget(skill_name: str) -> int:
    return CORE_LINE_BUDGET if skill_name == CORE_SKILL else OTHER_LINE_BUDGET


def check_frontmatter(text: str) -> list[str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ["frontmatter missing: SKILL.md must start with a '---' line"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return ["frontmatter not closed: no second '---' line"]
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        return [f"frontmatter invalid YAML: {exc}"]
    if not isinstance(data, dict):
        return ["frontmatter invalid: must be a YAML mapping"]
    failures = []
    for key in ("name", "description"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"frontmatter invalid: '{key}' must be a non-empty string")
    return failures


def check_line_budget(skill_name: str, text: str) -> list[str]:
    budget = line_budget(skill_name)
    count = len(text.splitlines())
    if count > budget:
        return [f"SKILL.md is {count} lines, over the {budget}-line budget"]
    return []


def strip_fences(text: str) -> str:
    """Blank out fenced code blocks so examples inside them are not checked."""
    kept: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in text.splitlines():
        stripped = line.lstrip()
        if not in_fence and (stripped.startswith("```") or stripped.startswith("~~~")):
            in_fence = True
            fence_marker = stripped[:3]
            kept.append("")
            continue
        if in_fence:
            if stripped.startswith(fence_marker):
                in_fence = False
            kept.append("")
            continue
        kept.append(line)
    return "\n".join(kept)


def strip_code(text: str) -> str:
    """Blank out fenced code blocks and inline code spans, for the link check."""
    return "\n".join(INLINE_CODE_RE.sub("", line) for line in strip_fences(text).splitlines())


def markdown_files(skill_dir: Path) -> list[Path]:
    return sorted(skill_dir.rglob("*.md"))


def check_links(skill_dir: Path, md_file: Path, text: str) -> list[str]:
    failures = []
    rel = md_file.relative_to(skill_dir).as_posix()
    skill_root = skill_dir.resolve()
    for match in LINK_RE.finditer(strip_code(text)):
        target = match.group(1).strip("<>")
        if not target or target.startswith("#") or URI_SCHEME_RE.match(target):
            continue
        path_part = target.split("#", 1)[0].split("?", 1)[0]
        if not path_part:
            continue
        resolved = (md_file.parent / path_part).resolve()
        try:
            resolved.relative_to(skill_root)
        except ValueError:
            failures.append(f"link escapes skill directory in {rel}: '{target}'")
            continue
        if not resolved.exists():
            failures.append(f"broken relative link in {rel}: '{target}'")
    return failures


def check_script_paths(skill_dir: Path, md_file: Path, text: str) -> list[str]:
    failures = []
    rel = md_file.relative_to(skill_dir).as_posix()
    for match in SCRIPT_PATH_RE.finditer(strip_fences(text)):
        script = match.group(1)
        if not (skill_dir / script).exists():
            failures.append(f"missing script path in {rel}: '{script}'")
    return failures


def validate_skill(skill_dir: Path) -> list[str]:
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return ["SKILL.md missing"]
    text = skill_file.read_text(encoding="utf-8")
    failures = check_frontmatter(text)
    failures.extend(check_line_budget(skill_dir.name, text))
    for md_file in markdown_files(skill_dir):
        md_text = md_file.read_text(encoding="utf-8")
        failures.extend(check_links(skill_dir, md_file, md_text))
        failures.extend(check_script_paths(skill_dir, md_file, md_text))
    return failures


def validate_skills(skills_dir: Path) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        if skill_dir.name.startswith("."):
            continue
        results[skill_dir.name] = validate_skill(skill_dir)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate DRAFT skill packs.")
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=DEFAULT_SKILLS_DIR,
        help="directory containing one subdirectory per skill",
    )
    args = parser.parse_args(argv)

    skills_dir = args.skills_dir
    if not skills_dir.is_dir():
        print(f"skills directory not found: {skills_dir}", file=sys.stderr)
        return 2

    results = validate_skills(skills_dir)
    failed = 0
    for name, failures in results.items():
        if failures:
            failed += 1
            print(f"FAIL {name}")
            for failure in failures:
                print(f"  - {failure}")
        else:
            print(f"OK   {name}")
    if failed:
        print(f"{failed} of {len(results)} skill(s) failed")
        return 1
    print(f"{len(results)} skill(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
