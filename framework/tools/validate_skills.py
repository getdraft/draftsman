#!/usr/bin/env python3
"""
Skill validator: checks SKILL.md frontmatter, line budgets, relative links and script paths.

Reads files only. It never executes skill scripts.

Usage:
    python3 framework/tools/validate_skills.py [--skills-dir DIR]

Exit codes:
    0  every skill passed
    1  at least one check failed (including unreadable files, unresolvable
       paths, and a skills directory with no skill subdirectories)
    2  the skills directory does not exist or is not a directory

Portability lint:
    Every file under a skill directory (including fenced code, file names and
    directory names) is scanned for banned harness, channel and company terms.
    Matching is case-insensitive. Word-boundary patterns stop bare words such
    as "switch" or "hierarchy" from matching. Only the skills directory is
    scanned; nothing outside it is read by this check.

Markdown handling:
    Each file is scanned line by line first. Fenced code blocks (``` or ~~~,
    closed by a fence of the same character and at least the same length) are
    excluded from every check. An opening fence with no closing fence is a
    failure, because the rest of the file would otherwise go unchecked.

    Inline code spans (a backtick run closed by a run of the same length) are
    blanked only when extracting link targets. Script paths (`scripts/...`) are
    checked outside fences, including inside inline code.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import NamedTuple
from pathlib import Path
from urllib.parse import unquote

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_hash  # noqa: E402


TOOLS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_ROOT.parent.parent
DEFAULT_SKILLS_DIR = REPO_ROOT / "framework" / "skills"

CORE_SKILL = "draftsman-core"
CORE_LINE_BUDGET = 150
OTHER_LINE_BUDGET = 200

OPEN_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
REFERENCE_DEF_RE = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
TAIL_RE = re.compile(r"""^\s*(?:"[^"]*"|'[^']*'|\([^)]*\))?\s*\)""")
ESCAPE_RE = re.compile(r"\\([!-/:-@\[-`{-~])")
URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]+:")
# An optional leading "./" is part of the reference, so "./scripts/x" is checked.
# "../scripts/x" and "foo/scripts/x" are still not matched: the lookbehind
# rejects a "." or "/" directly before the "scripts/" segment.
SCRIPT_PATH_RE = re.compile(r"(?<![\w./-])((?:\./)?scripts/[\w./-]*[\w-])")


# Portability lint: terms that must not appear in any file under framework/skills/.
# Matching is case-insensitive. Patterns with \b are word-bounded; the literal
# identifiers are matched as written, so they also match inside longer names.
BANNED_TERM_PATTERNS: tuple[tuple[str, str], ...] = (
    ("slack", r"\bslack\b"),
    ("discord", r"\bdiscord\b"),
    ("hermes", r"\bhermes\b"),
    ("fargate", r"\bfargate\b"),
    ("archie", r"\barchie\b"),
    ("central chat", r"\bcentral\s+chat\b"),
    ("switch-game-architect", r"switch-game-architect"),
    ("ANTHROPIC_API_KEY", r"ANTHROPIC_API_KEY"),
    ("Pattern 2", r"\bPattern\s+2\b"),
)
BANNED_TERM_RES = tuple(
    (label, re.compile(pattern, re.IGNORECASE)) for label, pattern in BANNED_TERM_PATTERNS
)


class SourceLine(NamedTuple):
    number: int
    text: str
    in_fence: bool


def line_budget(skill_name: str) -> int:
    return CORE_LINE_BUDGET if skill_name == CORE_SKILL else OTHER_LINE_BUDGET


def scan_lines(text: str) -> tuple[list[SourceLine], list[str]]:
    """Split text into lines and mark fenced code (including the fence lines).

    Returns the lines and a list of structural problems (an unclosed fence).
    """
    lines: list[SourceLine] = []
    fence_char = ""
    fence_len = 0
    fence_start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        if not fence_char:
            match = OPEN_FENCE_RE.match(raw)
            if match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
                fence_char = match.group(1)[0]
                fence_len = len(match.group(1))
                fence_start = number
                lines.append(SourceLine(number, raw, True))
            else:
                lines.append(SourceLine(number, raw, False))
            continue
        stripped = raw.strip()
        if stripped and set(stripped) == {fence_char} and len(stripped) >= fence_len:
            fence_char = ""
        lines.append(SourceLine(number, raw, True))
    problems = []
    if fence_char:
        problems.append(f"unclosed code fence opened at line {fence_start}; the rest of the file is unchecked")
    return lines, problems


def strip_code_spans(line: str) -> str:
    """Blank inline code spans of any backtick run length, keeping offsets.

    Only used for link extraction. A backslash-escaped backtick is literal.
    """
    out: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        char = line[i]
        if char == "\\" and i + 1 < n:
            out.append(line[i : i + 2])
            i += 2
            continue
        if char != "`":
            out.append(char)
            i += 1
            continue
        j = i
        while j < n and line[j] == "`":
            j += 1
        run = j - i
        close = -1
        k = j
        while k < n:
            if line[k] != "`":
                k += 1
                continue
            m = k
            while m < n and line[m] == "`":
                m += 1
            if m - k == run:
                close = m
                break
            k = m
        if close == -1:
            out.append(line[i:j])
            i = j
        else:
            out.append(" " * (close - i))
            i = close
    return "".join(out)


def parse_destination(text: str, start: int) -> tuple[str, int] | None:
    """Parse a link destination beginning at text[start] (just after '(').

    Returns (raw destination, index after the closing parenthesis) or None when
    the text is not a complete inline link.
    """
    i = start
    while i < len(text) and text[i] in " \t":
        i += 1
    if i < len(text) and text[i] == "<":
        end = text.find(">", i + 1)
        if end == -1:
            return None
        dest = text[i + 1 : end]
        i = end + 1
    else:
        begin = i
        depth = 0
        while i < len(text):
            char = text[i]
            if char == "\\" and i + 1 < len(text):
                i += 2
                continue
            if char in " \t":
                break
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            i += 1
        dest = text[begin:i]
    tail = TAIL_RE.match(text[i:])
    if not tail:
        return None
    return dest, i + tail.end()


def link_spans(line: str) -> list[tuple[str, int, int]]:
    """Return (raw destination, start, end) for each link on one line.

    start and end are offsets into `line` that cover the destination text
    (for inline links, through the closing parenthesis). Code spans are not links.
    """
    spans: list[tuple[str, int, int]] = []
    visible = strip_code_spans(line)
    pos = visible.find("](")
    while pos != -1:
        parsed = parse_destination(visible, pos + 2)
        if parsed:
            dest, end = parsed
            spans.append((dest, pos + 2, end))
        pos = visible.find("](", pos + 2)
    definition = REFERENCE_DEF_RE.match(line)
    if definition:
        spans.append((definition.group(1).strip("<>"), definition.start(1), definition.end(1)))
    return spans


def link_targets(line: str) -> list[str]:
    """Return raw inline and reference link destinations on one line (code spans removed)."""
    return [dest for dest, _, _ in link_spans(line) if dest]


def mask_link_destinations(line: str) -> str:
    """Blank link destinations so script paths inside them are not scanned twice.

    The link check owns those; link text and prose stay visible to the script scan.
    """
    chars = list(line)
    for _, start, end in link_spans(line):
        for k in range(start, min(end, len(chars))):
            chars[k] = " "
    return "".join(chars)


def normalise_target(raw: str) -> str:
    """Undo markdown backslash escapes, then URL-decode (unquote first, per the spec)."""
    return unquote(ESCAPE_RE.sub(r"\1", raw))


def check_path(skill_root: Path, base_dir: Path, decoded: str) -> str | None:
    """Return a failure reason for a path inside a skill, or None when it resolves inside it."""
    if "\x00" in decoded:
        return "invalid path (NUL byte)"
    if decoded.startswith(("/", "\\")) or Path(decoded).is_absolute():
        return "link escapes skill directory"
    try:
        candidate = base_dir / decoded
        resolved = candidate.resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        return f"cannot resolve path ({type(exc).__name__})"
    try:
        resolved.relative_to(skill_root)
    except ValueError:
        return "link escapes skill directory"
    try:
        exists = candidate.exists()
    except (OSError, ValueError) as exc:
        return f"cannot stat path ({type(exc).__name__})"
    return None if exists else "broken relative link"


def check_frontmatter(text: str) -> list[str]:
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return ["frontmatter missing: SKILL.md must start with a '---' line"]
    end = next((idx for idx in range(1, len(lines)) if lines[idx].rstrip() == "---"), None)
    if end is None:
        return ["frontmatter not closed: no second '---' line"]
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except (yaml.YAMLError, ValueError, RecursionError) as exc:
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


def check_markdown(skill_root: Path, md_file: Path, text: str) -> list[str]:
    """Check relative links and script paths in one markdown file, outside fenced code."""
    failures: list[str] = []
    rel = md_file.relative_to(skill_root).as_posix()
    lines, problems = scan_lines(text)
    failures.extend(f"{problem} in {rel}" for problem in problems)
    for line in lines:
        if line.in_fence:
            continue
        for raw_target in link_targets(line.text):
            if not raw_target or raw_target.startswith("#"):
                continue
            if URI_SCHEME_RE.match(raw_target):
                continue
            try:
                decoded = normalise_target(raw_target)
            except (ValueError, UnicodeError):
                failures.append(f"invalid link in {rel} line {line.number}: '{raw_target}'")
                continue
            path_part = re.split(r"[#?]", decoded, maxsplit=1)[0]
            if not path_part:
                continue
            reason = check_path(skill_root, md_file.parent, path_part)
            if reason:
                failures.append(f"{reason} in {rel} line {line.number}: '{raw_target}'")
        for match in SCRIPT_PATH_RE.finditer(mask_link_destinations(line.text)):
            script = match.group(1)
            reason = check_path(skill_root, skill_root, script)
            if reason == "broken relative link":
                failures.append(f"missing script path in {rel} line {line.number}: '{script}'")
            elif reason:
                failures.append(f"{reason} in {rel} line {line.number}: '{script}'")
    # The same target repeated on one line gives identical messages; report each once.
    return list(dict.fromkeys(failures))


def skill_files(skill_root: Path) -> list[tuple[str, Path]]:
    """Every regular file under one skill, as (skill-relative path, file path).

    Symlinked directories are followed. Each directory is walked once, by its
    resolved path, so a symlink loop ends and a directory reached twice is
    listed under the first relative path the walk reaches. A file reached by
    two routes (for example a symlinked file plus its real directory) is listed
    once, under its smallest relative path. Unreadable entries are skipped.
    """
    by_resolved: dict[Path, str] = {}
    seen_dirs: set[Path] = set()
    stack: list[Path] = [skill_root]
    while stack:
        directory = stack.pop()
        try:
            key = directory.resolve()
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except (OSError, RuntimeError, ValueError):
            continue
        for entry in entries:
            path = Path(entry.path)
            try:
                if entry.is_dir():
                    stack.append(path)
                elif entry.is_file():
                    resolved = path.resolve()
                    rel = path.relative_to(skill_root).as_posix()
                    by_resolved[resolved] = min(by_resolved.get(resolved, rel), rel)
            except (OSError, RuntimeError, ValueError):
                continue
    pairs = [(rel, resolved) for resolved, rel in by_resolved.items()]
    return sorted(pairs, key=lambda pair: pair[0])


def scan_banned_terms(files: list[tuple[str, Path]]) -> list[str]:
    """Portability lint over (relative path, file) pairs. Never raises.

    Each file is scanned as one text, so a term split across a line break is
    still matched. A match is reported at the line where it starts, once per
    (file, line, term). Paths are checked too, so a file or folder named after
    a banned term also fails.
    """
    failures: list[str] = []
    for rel, file_path in files:
        for label, rx in BANNED_TERM_RES:
            if rx.search(rel):
                failures.append(f"banned term '{label}' in path {rel}")
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            failures.append(f"unreadable file {rel}: {type(exc).__name__}: {exc}")
            continue
        for label, rx in BANNED_TERM_RES:
            for match in rx.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                failures.append(f"banned term '{label}' in {rel} line {line}")
    return list(dict.fromkeys(failures))


def check_banned_terms(skill_root: Path) -> list[str]:
    """Portability lint over every file under one skill directory. Never raises."""
    return scan_banned_terms(skill_files(skill_root))


def top_level_files(skills_dir: Path) -> list[tuple[str, Path]]:
    """Files directly under the skills directory, plus the contents of hidden
    directories (which are not skills). Files inside a skill directory are left
    to that skill's check, so each file is scanned exactly once. Never raises.
    """
    try:
        skill_roots = [p.resolve() for p in skill_directories(skills_dir)]
        entries = sorted(os.scandir(skills_dir), key=lambda entry: entry.name)
    except (OSError, RuntimeError, ValueError):
        return []
    pairs: list[tuple[str, Path]] = []
    for entry in entries:
        path = Path(entry.path)
        try:
            if entry.is_file():
                resolved = path.resolve()
                if any(resolved.is_relative_to(root) for root in skill_roots):
                    continue
                pairs.append((entry.name, path))
            elif entry.is_dir() and entry.name.startswith("."):
                pairs.extend((f"{entry.name}/{rel}", file_path) for rel, file_path in skill_files(path))
        except (OSError, RuntimeError, ValueError):
            continue
    return pairs


def check_top_level_banned_terms(skills_dir: Path) -> list[str]:
    """Portability lint for everything in framework/skills/ outside a skill directory."""
    return scan_banned_terms(top_level_files(skills_dir))


def markdown_files(skill_dir: Path) -> list[Path]:
    return sorted(skill_dir.rglob("*.md"))


def validate_skill(skill_dir: Path) -> list[str]:
    """Return every failure for one skill directory. Never raises.

    The directory is resolved once, and every file is taken from that resolved
    root, so relative --skills-dir values and symlinked paths compare correctly.
    The budget uses the directory name as given (a symlink may point elsewhere).
    """
    try:
        name = skill_dir.name
        root = skill_dir.resolve()
        skill_file = root / "SKILL.md"
        if not skill_file.is_file():
            return ["SKILL.md missing"]
        failures: list[str] = []
        try:
            text = skill_file.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            return [f"SKILL.md unreadable: {type(exc).__name__}: {exc}"]
        failures.extend(check_frontmatter(text))
        failures.extend(check_line_budget(name, text))
        for md_file in markdown_files(root):
            rel = md_file.relative_to(root).as_posix()
            try:
                md_text = md_file.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError) as exc:
                failures.append(f"unreadable file {rel}: {type(exc).__name__}: {exc}")
                continue
            failures.extend(check_markdown(root, md_file, md_text))
        failures.extend(check_banned_terms(root))
        return failures
    except Exception as exc:  # last-resort guard: report, never traceback
        return [f"internal error while checking skill: {type(exc).__name__}: {exc}"]


def skill_directories(skills_dir: Path) -> list[Path]:
    return sorted(p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def validate_skills(skills_dir: Path) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for skill_dir in skill_directories(skills_dir):
        results[skill_dir.name] = validate_skill(skill_dir)
    return results


def projected_frontmatter(path: Path) -> dict | None:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        return None
    if not lines or lines[0].rstrip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if end is None:
        return None
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except (yaml.YAMLError, ValueError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


def check_workspace(workspace: Path) -> list[str]:
    """Compare projections in <workspace>/.claude/skills and the AGENTS.md index
    with the vendored skills in <workspace>/.draft/framework/skills.

    There is no lock file: freshness is the source_sha256 marker that setup_ide.py
    wrote into each projection.
    """
    source_root = workspace / ".draft" / "framework" / "skills"
    if not source_root.is_dir():
        return [f"no vendored skills at {source_root} (refresh the framework first)"]
    failures: list[str] = []
    sources = sorted(p for p in source_root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    if not sources:
        return [f"no skills found in {source_root}"]
    for source in sources:
        projection = workspace / ".claude" / "skills" / source.name / "SKILL.md"
        if not projection.is_file():
            failures.append(f"{source.name}: projection missing; run setup_ide.py")
            continue
        front = projected_frontmatter(projection) or {}
        if front.get("generated") is not True:
            failures.append(f"{source.name}: projection lacks 'generated: true'; run setup_ide.py")
            continue
        if front.get("source_sha256") != skill_hash.skill_source_sha256(source):
            failures.append(f"{source.name}: projection is stale (source_sha256 differs); run setup_ide.py")
    agents = workspace / "AGENTS.md"
    if agents.is_file():
        match = skill_hash.BLOCK_RE.search(agents.read_text(encoding="utf-8"))
        if not match:
            failures.append("AGENTS.md: skill index missing; run setup_ide.py")
        elif match.group(1) != skill_hash.skills_set_sha256(source_root):
            failures.append("AGENTS.md: skill index is stale; run setup_ide.py")
    else:
        failures.append("AGENTS.md: missing; run setup_ide.py")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate DRAFT skill packs.")
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=DEFAULT_SKILLS_DIR,
        help="directory containing one subdirectory per skill",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="check that projections under <path>/.claude/skills match <path>/.draft/framework/skills",
    )
    args = parser.parse_args(argv)

    if args.workspace is not None:
        failures = check_workspace(args.workspace)
        for failure in failures:
            print(f"FAIL {failure}")
        if failures:
            return 1
        print("projections are fresh")
        return 0

    skills_dir = args.skills_dir
    if not skills_dir.is_dir():
        print(f"skills directory not found: {skills_dir}", file=sys.stderr)
        return 2
    try:
        names = skill_directories(skills_dir)
    except OSError as exc:
        print(f"FAIL cannot list skills directory {skills_dir}: {type(exc).__name__}: {exc}")
        return 1
    if not names:
        print(f"FAIL no skill directories found in {skills_dir} (expected one subdirectory per skill)")
        return 1

    failed = 0
    for skill_dir in names:
        failures = validate_skill(skill_dir)
        if failures:
            failed += 1
            print(f"FAIL {skill_dir.name}")
            for failure in failures:
                print(f"  - {failure}")
        else:
            print(f"OK   {skill_dir.name}")
    top_failures = check_top_level_banned_terms(skills_dir)
    if top_failures:
        print("FAIL skills directory (top-level files)")
        for failure in top_failures:
            print(f"  - {failure}")
    if failed:
        print(f"{failed} of {len(names)} skill(s) failed")
    if failed or top_failures:
        return 1
    print(f"{len(names)} skill(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
