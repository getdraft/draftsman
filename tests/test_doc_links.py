"""No markdown link (inline, angle-bracket or reference-style) may point at a deleted path.

Deleted paths: soul.md and anything under agent/. Scans README.md and the other root docs,
framework/ and docs/. This is not a general dangling-link check."""

import re
import subprocess
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
INLINE_RE = re.compile(r"\]\(\s*<?([^)\s>]+)")
REFDEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)", re.MULTILINE)
SCOPES = ("framework/", "docs/")
ROOT_DOCS = {"README.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "MATURITY.md", "KPF.md", "HISTORY.md", "RELEASE.md"}
SKIP_PREFIXES = ("framework/docs/proposals/",)


def tracked_markdown() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "*.md"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def is_deleted_target(resolved: Path) -> bool:
    try:
        rel = resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return False
    return rel == "agent" or rel.startswith("agent/") or rel.endswith("/soul.md") or rel == "soul.md"


class DocLinkTests(unittest.TestCase):
    def test_no_link_points_to_a_deleted_path(self):
        bad = []
        for rel in tracked_markdown():
            if rel not in ROOT_DOCS and not rel.startswith(SCOPES):
                continue
            if rel.startswith(SKIP_PREFIXES):
                continue
            base = (ROOT / rel).parent
            text = (ROOT / rel).read_text(encoding="utf-8")
            for target in INLINE_RE.findall(text) + REFDEF_RE.findall(text):
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                path = unquote(target.split("#", 1)[0])
                if not path:
                    continue
                resolved = (base / path).resolve()
                if is_deleted_target(resolved):
                    bad.append(f"{rel}: {target}")
        self.assertEqual(bad, [])

    def test_link_forms_are_all_recognised(self):
        sample = "[a](soul.md) [b](<soul.md>) [c][r] [d](soul.md \"t\")\n\n[r]: ../../agent/SOUL.md\n"
        found = INLINE_RE.findall(sample) + REFDEF_RE.findall(sample)
        self.assertEqual(sorted(found), ["../../agent/SOUL.md", "soul.md", "soul.md", "soul.md"])

    def test_the_checker_flags_a_link_to_soul_md(self):
        self.assertTrue(is_deleted_target(ROOT / "framework" / "docs" / "soul.md"))
        self.assertTrue(is_deleted_target(ROOT / "agent" / "SOUL.md"))
        self.assertFalse(is_deleted_target(ROOT / "framework" / "skills" / "draftsman-core" / "SKILL.md"))


if __name__ == "__main__":
    unittest.main()
