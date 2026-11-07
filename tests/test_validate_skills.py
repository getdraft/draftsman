from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from framework.tools import validate_skills


REPO_SKILLS = validate_skills.DEFAULT_SKILLS_DIR

VALID_FRONTMATTER = (
    "---\n"
    "name: {name}\n"
    "description: Use when testing the validator.\n"
    "---\n"
)


def write_skill(root: Path, name: str, text: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
    return skill_dir


def valid_skill_text(name: str, lines: int | None = None) -> str:
    """Valid SKILL.md; when `lines` is given, pad with filler so the file has exactly that many lines."""
    text = VALID_FRONTMATTER.format(name=name) + "# Title\n\nBody text.\n"
    if lines is not None:
        current = len(text.splitlines())
        text += "filler\n" * (lines - current)
    return text


class ValidateSkillsTests(unittest.TestCase):
    def run_validator(self, skills_dir: Path) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return validate_skills.main(["--skills-dir", str(skills_dir)])

    def assert_fails(self, root: Path, needle: str) -> None:
        results = validate_skills.validate_skills(root)
        failures = [f for fs in results.values() for f in fs]
        self.assertTrue(failures, "expected at least one failure")
        self.assertTrue(
            any(needle in f for f in failures), f"no failure mentions {needle!r}: {failures}"
        )
        self.assertNotEqual(self.run_validator(root), 0)

    def test_repo_skills_pass(self) -> None:
        self.assertEqual(self.run_validator(REPO_SKILLS), 0)

    def test_valid_temp_skill_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(root, "draftsman-core", valid_skill_text("draftsman-core"))
            write_skill(root, "other-skill", valid_skill_text("other-skill"))
            self.assertEqual(self.run_validator(root), 0)

    def test_missing_skills_dir_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_validator(Path(tmp) / "absent"), 2)

    def test_missing_skill_md_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "empty-skill").mkdir()
            self.assert_fails(root, "SKILL.md missing")

    def test_missing_frontmatter_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(root, "no-frontmatter", "# Title\n\nNo frontmatter here.\n")
            self.assert_fails(root, "frontmatter missing")

    def test_unclosed_frontmatter_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(root, "unclosed", "---\nname: unclosed\ndescription: x\n# Title\n")
            self.assert_fails(root, "frontmatter not closed")

    def test_invalid_yaml_frontmatter_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(root, "bad-yaml", "---\nname: [unclosed\n---\n# Title\n")
            self.assert_fails(root, "invalid YAML")

    def test_missing_description_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(root, "no-description", "---\nname: no-description\n---\n# Title\n")
            self.assert_fails(root, "'description' must be a non-empty string")

    def test_empty_name_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(root, "empty-name", "---\nname: ''\ndescription: x\n---\n# Title\n")
            self.assert_fails(root, "'name' must be a non-empty string")

    def test_core_skill_at_150_lines_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_skill_text("draftsman-core", 150)
            self.assertEqual(len(text.splitlines()), 150)
            write_skill(root, "draftsman-core", text)
            self.assertEqual(self.run_validator(root), 0)

    def test_core_skill_at_151_lines_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_skill_text("draftsman-core", 151)
            self.assertEqual(len(text.splitlines()), 151)
            write_skill(root, "draftsman-core", text)
            self.assert_fails(root, "over the 150-line budget")

    def test_other_skill_at_200_lines_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_skill_text("other-skill", 200)
            self.assertEqual(len(text.splitlines()), 200)
            write_skill(root, "other-skill", text)
            self.assertEqual(self.run_validator(root), 0)

    def test_other_skill_at_201_lines_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_skill_text("other-skill", 201)
            self.assertEqual(len(text.splitlines()), 201)
            write_skill(root, "other-skill", text)
            self.assert_fails(root, "over the 200-line budget")

    def test_long_references_file_is_not_budgeted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = write_skill(root, "draftsman-core", valid_skill_text("draftsman-core"))
            refs = skill / "references"
            refs.mkdir()
            (refs / "long.md").write_text("line\n" * 500, encoding="utf-8")
            self.assertEqual(self.run_validator(root), 0)

    def test_broken_relative_link_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_skill_text("draftsman-core") + "\nSee [the guide](references/missing.md).\n"
            write_skill(root, "draftsman-core", text)
            self.assert_fails(root, "broken relative link")

    def test_broken_link_inside_references_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = write_skill(root, "draftsman-core", valid_skill_text("draftsman-core"))
            refs = skill / "references"
            refs.mkdir()
            (refs / "page.md").write_text("[back](../gone.md)\n", encoding="utf-8")
            self.assert_fails(root, "broken relative link")

    def test_valid_relative_link_and_external_links_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = write_skill(
                root,
                "draftsman-core",
                valid_skill_text("draftsman-core")
                + "\n[ok](references/page.md) [anchor](#top) [web](https://example.com/x)\n",
            )
            refs = skill / "references"
            refs.mkdir()
            (refs / "page.md").write_text("# Page\n", encoding="utf-8")
            self.assertEqual(self.run_validator(root), 0)

    def test_missing_script_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_skill_text("draftsman-core") + "\nRun scripts/check.py first.\n"
            write_skill(root, "draftsman-core", text)
            self.assert_fails(root, "missing script path")

    def test_present_script_path_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_skill_text("draftsman-core") + "\nRun scripts/check.py first.\n"
            skill = write_skill(root, "draftsman-core", text)
            scripts = skill / "scripts"
            scripts.mkdir()
            (scripts / "check.py").write_text("print('never executed')\n", encoding="utf-8")
            self.assertEqual(self.run_validator(root), 0)

    def test_links_and_script_paths_inside_code_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = (
                valid_skill_text("draftsman-core")
                + "\nInline code `[x](nope/missing.md)` is an example.\n"
                + "\n```markdown\n[example](nope/also-missing.md)\nRun scripts/ghost.py\n```\n"
                + "\n~~~\n[tilde](nope/tilde.md)\n~~~\n"
            )
            write_skill(root, "draftsman-core", text)
            self.assertEqual(self.run_validator(root), 0)

    def test_missing_backticked_script_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_skill_text("draftsman-core") + "\nRun `scripts/absent.py` first.\n"
            write_skill(root, "draftsman-core", text)
            self.assert_fails(root, "missing script path")

    def test_present_backticked_script_path_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = valid_skill_text("draftsman-core") + "\nRun `scripts/check.py` first.\n"
            skill = write_skill(root, "draftsman-core", text)
            (skill / "scripts").mkdir()
            (skill / "scripts" / "check.py").write_text("x = 1\n", encoding="utf-8")
            self.assertEqual(self.run_validator(root), 0)

    def test_link_outside_code_still_checked_after_code_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = (
                valid_skill_text("draftsman-core")
                + "\n```\n[example](nope.md)\n```\n"
                + "\nReal [broken](nope/real.md) link.\n"
            )
            write_skill(root, "draftsman-core", text)
            self.assert_fails(root, "broken relative link")

    def test_link_escaping_skill_directory_fails_even_if_target_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            skills = repo / "skills"
            (repo / "docs").mkdir()
            (repo / "docs" / "x.md").write_text("# Shared doc\n", encoding="utf-8")
            write_skill(
                skills,
                "draftsman-core",
                valid_skill_text("draftsman-core") + "\nSee [docs](../../docs/x.md).\n",
            )
            self.assert_fails(skills, "link escapes skill directory")

    def test_validator_does_not_execute_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = Path(tmp) / "ran.marker"
            skill = write_skill(root, "draftsman-core", valid_skill_text("draftsman-core"))
            scripts = skill / "scripts"
            scripts.mkdir()
            (scripts / "boom.py").write_text(
                f"open({str(marker)!r}, 'w').write('ran')\n", encoding="utf-8"
            )
            self.run_validator(root)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
