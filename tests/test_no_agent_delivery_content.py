"""The agent-delivery model is gone: no tracked file may name its parts.

Scans tracked files only, with Python `re` so the result does not depend on the
platform's grep. Files that must name the banned terms to enforce or test the
ban are on the allowlist, together with a few unrelated mentions (Slack as a
downstream ticket integration, a Slack channel as a contact example).
"""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERN = re.compile(
    r"\b(slack|discord|hermes|gatekeeper|archie|fargate)\b|switch-game"
    r"|validate_agent_package|agent-spec\.yaml|\bsoul\.md\b|\bagent/(SOUL|skills|mcp|bindings|docs)\b",
    re.IGNORECASE,
)

ALLOW_FILES = {
    "CHANGELOG.md",
    "framework/docs/ticketing.md",
    "framework/docs/operations-guide.md",
    "tests/test_no_agent_delivery_content.py",
    "tests/test_doc_links.py",
    "framework/tools/validate_skills.py",
    "tests/test_validate_skills.py",
    "tests/test_draftsman_core.py",
    "tests/test_skill_set.py",
}
ALLOW_PREFIXES = ("framework/docs/proposals/", "tests/fixtures/skills/")

REMOVED_PATHS = (
    "agent",
    "framework/integrations/slack",
    "framework/integrations/discord",
    "framework/tools/validate_agent_package.py",
    "framework/docs/soul.md",
)


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


class NoAgentDeliveryContentTests(unittest.TestCase):
    def test_removed_paths_are_gone(self):
        for rel in REMOVED_PATHS:
            self.assertFalse((ROOT / rel).exists(), f"{rel} should have been removed")

    def test_no_banned_terms_outside_allowlist(self):
        hits = []
        for rel in tracked_files():
            if rel in ALLOW_FILES or rel.startswith(ALLOW_PREFIXES):
                continue
            path = ROOT / rel
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if PATTERN.search(line):
                    hits.append(f"{rel}:{number}: {line.strip()[:100]}")
        self.assertEqual(hits, [], "banned terms found:\n" + "\n".join(hits))

    def test_pattern_matches_what_it_should(self):
        for text in (
            "Slack bot", "discord", "Hermes agent", "AWS Fargate", "gatekeeper", "Archie", "switch-game-architect",
            "see framework/docs/soul.md", "validate_agent_package.py", "agent/SOUL.md", "agent-spec.yaml",
        ):
            self.assertTrue(PATTERN.search(text), text)
        for text in ("switch statement", "hierarchy", "archive"):
            self.assertIsNone(PATTERN.search(text), text)


if __name__ == "__main__":
    unittest.main()
