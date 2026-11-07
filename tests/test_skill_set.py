"""Completeness guard for framework/skills/ (E3).

Names `switch-game-architect` only to assert that it is absent.
"""

import re
import unittest
from pathlib import Path

import yaml

SKILLS = Path(__file__).resolve().parents[1] / "framework" / "skills"
ROOT = SKILLS.parents[1]

EXPECTED = {
    "draftsman-core": None,
    "draftsman-author": "Author",
    "draftsman-query": "Query",
    "draftsman-review": "Author",
    "draftsman-update": "Author",
    "draftsman-maturity": "Author",
}


class SkillSetTests(unittest.TestCase):
    def test_exact_skill_directories(self):
        found = {p.name for p in SKILLS.iterdir() if p.is_dir()}
        self.assertEqual(found, set(EXPECTED))

    def test_switch_game_architect_absent(self):
        self.assertFalse((SKILLS / "switch-game-architect").exists())

    def test_frontmatter_name_matches_directory(self):
        for name in EXPECTED:
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            front = yaml.safe_load(text.split("---", 2)[1])
            self.assertEqual(front["name"], name)
            self.assertIn("Use when", front["description"])

    def test_each_workflow_skill_states_its_profile(self):
        for name, profile in EXPECTED.items():
            if profile is None:
                continue
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(f"{profile} profile", text, name)

    def test_profile_matches_declared_need(self):
        for name, profile in EXPECTED.items():
            if profile is None:
                continue
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            other = "Query" if profile == "Author" else "Author"
            self.assertNotIn(f"needs the **{other} profile**", text, name)

    def test_script_paths_exist(self):
        pattern = re.compile(r"framework/tools/[\w./-]*\.py")
        for path in SKILLS.rglob("*.md"):
            for match in pattern.findall(path.read_text(encoding="utf-8")):
                self.assertTrue((ROOT / match).exists(), f"{path}: {match}")


if __name__ == "__main__":
    unittest.main()
