"""Step-list guard for draftsman-review and draftsman-update (E3).

The fixtures in tests/fixtures/skills/step_lists/ record every ## and ###
heading of the source action file at the time the skill was written. This
test reads only those fixtures and the skill folder, never the live action
files, so the action files can later become routers without breaking it.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "framework" / "skills"
FIXTURES = ROOT / "tests" / "fixtures" / "skills" / "step_lists"

HEADING_RE = re.compile(r"^#{2,3} ")


def skill_headings(skill: str) -> set[str]:
    headings: set[str] = set()
    base = SKILLS / skill
    for path in [base / "SKILL.md", *sorted((base / "references").glob("*.md"))]:
        in_fence = False
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
            if not in_fence and HEADING_RE.match(line):
                headings.add(line.rstrip())
    return headings


class StepListTests(unittest.TestCase):
    def check(self, fixture: str, skill: str) -> None:
        recorded = [l for l in (FIXTURES / fixture).read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertGreater(len(recorded), 5, f"{fixture} records too few headings")
        for heading in recorded:
            self.assertRegex(heading, HEADING_RE)
        present = skill_headings(skill)
        missing = [h for h in recorded if h not in present]
        self.assertEqual(missing, [], f"{skill} lacks recorded headings: {missing}")

    def test_review_keeps_every_step_heading(self):
        self.check("review.txt", "draftsman-review")

    def test_update_keeps_every_step_heading(self):
        self.check("update.txt", "draftsman-update")

    def test_skill_md_maps_every_step_in_one_line(self):
        for skill in ("draftsman-review", "draftsman-update"):
            text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("references/steps.md", text)
            self.assertLessEqual(len(text.splitlines()), 200)


if __name__ == "__main__":
    unittest.main()
