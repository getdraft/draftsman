"""Shared hash and marker helpers for projected DRAFT skills.

The hash covers every file in a skill directory: the sorted relative POSIX
paths and the bytes of each file, so ``references/`` and any scripts count.
Cache directories are ignored.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

IGNORED_PARTS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}

BLOCK_BEGIN = "<!-- DRAFT-SKILLS:BEGIN"
BLOCK_END = "<!-- DRAFT-SKILLS:END -->"
BLOCK_RE = re.compile(
    r"<!-- DRAFT-SKILLS:BEGIN generated: true source_sha256: ([0-9a-f]{64}) -->.*?<!-- DRAFT-SKILLS:END -->",
    re.DOTALL,
)


def skill_files(skill_dir: Path) -> list[Path]:
    files = []
    for path in skill_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir)
        if IGNORED_PARTS.intersection(rel.parts) or path.suffix in IGNORED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(skill_dir).as_posix())


def skill_source_sha256(skill_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in skill_files(skill_dir):
        digest.update(path.relative_to(skill_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def skills_set_sha256(skills_dir: Path) -> str:
    """Hash over every skill's name and hash, for the AGENTS.md index marker."""
    digest = hashlib.sha256()
    for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        digest.update(skill.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(skill_source_sha256(skill).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def add_generated_marker(skill_md: str, source_sha256: str) -> str:
    """Return SKILL.md text with ``generated`` and ``source_sha256`` added to the
    frontmatter, keeping the frontmatter first. Existing marker lines are replaced."""
    lines = skill_md.splitlines()
    if not lines or lines[0].rstrip() != "---":
        raise ValueError("SKILL.md has no frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if end is None:
        raise ValueError("SKILL.md frontmatter is not closed")
    front = [l for l in lines[1:end] if not l.startswith(("generated:", "source_sha256:"))]
    front += ["generated: true", f"source_sha256: {source_sha256}"]
    return "\n".join([lines[0], *front, *lines[end:]]) + "\n"
