"""Tests for the portability lint in framework/tools/validate_skills.py (E2-S2).

Each banned term is exercised with a small bad skill in a temporary directory.
The validator is only read, never executed, by these tests.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "framework" / "skills"

_spec = importlib.util.spec_from_file_location(
    "validate_skills", ROOT / "framework" / "tools" / "validate_skills.py"
)
validate_skills = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_skills)

VALID_FRONTMATTER = (
    "---\n"
    "name: {name}\n"
    "description: Use when testing the validator.\n"
    "---\n"
)


def skill_text(name: str, body: str = "") -> str:
    return VALID_FRONTMATTER.format(name=name) + "# Title\n\nBody text.\n" + body


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_skill(root: Path, name: str, text: str) -> Path:
    skill = root / name
    write(skill / "SKILL.md", text)
    return skill


class PortabilityLintTests(unittest.TestCase):
    """E2-S2: banned harness, channel and company terms under framework/skills/."""

    def run_main(self, skills_dir: Path) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = validate_skills.main(["--skills-dir", str(skills_dir)])
        return code, out.getvalue() + err.getvalue()

    def lint_failures(self, root: Path) -> list[str]:
        return validate_skills.check_banned_terms(root)

    def assert_banned(self, root: Path, label: str) -> None:
        failures = self.lint_failures(root)
        self.assertTrue(
            any(f"banned term '{label}'" in f for f in failures),
            f"no banned-term failure for {label!r}: {failures}",
        )
        code, output = self.run_main(root)
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL", output)
        self.assertNotIn("Traceback", output)

    # --- acceptance 1: each banned term in turn exits non-zero ------------

    def test_each_banned_term_in_turn_fails(self) -> None:
        samples = {
            "slack": "Post to Slack when done.",
            "discord": "Ping the Discord channel.",
            "hermes": "The hermes runtime loads this.",
            "fargate": "Deploy on Fargate.",
            "archie": "Ask Archie for the answer.",
            "central chat": "Use Central Chat to ask.",
            "switch-game-architect": "Run as switch-game-architect.",
            "ANTHROPIC_API_KEY": "Set ANTHROPIC_API_KEY first.",
            "Pattern 2": "This follows Pattern 2 of the plan.",
        }
        for label, sentence in samples.items():
            with self.subTest(term=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                make_skill(root, "draftsman-core", skill_text("draftsman-core", body=sentence + "\n"))
                self.assert_banned(root, label)

    def test_banned_terms_match_case_insensitively(self) -> None:
        samples = {
            "slack": "SLACK",
            "discord": "dIsCoRd",
            "central chat": "central   CHAT",
            "ANTHROPIC_API_KEY": "anthropic_api_key",
            "Pattern 2": "pattern 2",
        }
        for label, variant in samples.items():
            with self.subTest(term=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                make_skill(root, "draftsman-core", skill_text("draftsman-core", body=f"{variant}\n"))
                self.assert_banned(root, label)

    def test_banned_term_in_reference_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            write(skill / "references" / "onboarding.md", "Ask in Slack.\n")
            self.assert_banned(root, "slack")

    def test_banned_term_in_fenced_code_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = "```\nFargate task\n```\n"
            make_skill(root, "draftsman-core", skill_text("draftsman-core", body=body))
            self.assert_banned(root, "fargate")

    def test_banned_term_in_file_name_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            write(skill / "references" / "hermes-notes.md", "# Notes\n")
            self.assert_banned(root, "hermes")

    def test_banned_term_in_non_markdown_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            write(skill / "scripts" / "helper.py", "# posts to Discord\n")
            self.assert_banned(root, "discord")

    # --- acceptance 2: bare words that are not banned pass ----------------

    def test_switch_and_hierarchy_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = "A switch statement sits in the hierarchy.\n"
            make_skill(root, "draftsman-core", skill_text("draftsman-core", body=body))
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)
            self.assertEqual(self.lint_failures(root), [])

    def test_words_that_only_contain_a_banned_term_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = (
                "Slacker, archies, hermesbot, fargates, discordant, Pattern 22,\n"
                "central chatter, and Pattern-2 are fine.\n"
            )
            make_skill(root, "draftsman-core", skill_text("draftsman-core", body=body))
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    # --- scope and reporting ----------------------------------------------

    def test_term_outside_skills_dir_is_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(repo / "docs" / "ticketing.md", "Slack is a ticket integration.\n")
            skills = repo / "skills"
            make_skill(skills, "draftsman-core", skill_text("draftsman-core"))
            code, output = self.run_main(skills)
            self.assertEqual(code, 0, output)

    def test_same_term_twice_on_one_line_is_reported_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(root, "draftsman-core", skill_text("draftsman-core", body="Slack and slack.\n"))
            failures = self.lint_failures(root)
            self.assertEqual(len(failures), 1, failures)

    def test_banned_term_reported_with_file_and_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(root, "draftsman-core", skill_text("draftsman-core", body="Text.\nUse Slack here.\n"))
            code, output = self.run_main(root)
            self.assertEqual(code, 1)
            self.assertIn("FAIL draftsman-core", output)
            self.assertIn("banned term 'slack' in SKILL.md line 9", output)
            self.assertNotIn("Traceback", output)

    def test_symlinked_file_pointing_outside_is_scanned_without_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(repo / "outside.txt", "Slack\n")
            skill = make_skill(repo / "skills", "draftsman-core", skill_text("draftsman-core"))
            try:
                os.symlink(repo / "outside.txt", skill / "linked.txt")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks not available on this platform")
            code, output = self.run_main(repo / "skills")
            self.assertEqual(code, 1, output)
            self.assertIn("banned term 'slack' in linked.txt line 1", output)
            self.assertNotIn("Traceback", output)

    def test_symlink_loop_inside_skill_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            try:
                os.symlink(skill, skill / "loop", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks not available on this platform")
            code, output = self.run_main(root)
            self.assertNotIn("Traceback", output)
            self.assertNotIn("internal error", output)
            self.assertEqual(code, 0, output)

    def test_repo_skill_pack_has_no_banned_terms(self) -> None:
        self.assertEqual(self.lint_failures(SKILLS / "draftsman-core"), [])


if __name__ == "__main__":
    unittest.main()
