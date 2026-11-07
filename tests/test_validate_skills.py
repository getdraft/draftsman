"""Tests for framework/tools/validate_skills.py (E2-S1).

Each failure mode is exercised with a small bad skill in a temporary
directory. The validator is only read, never executed, by these tests.
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


def skill_text(name: str, lines: int | None = None, body: str = "") -> str:
    """Valid SKILL.md, optionally padded so the file has exactly `lines` lines."""
    text = VALID_FRONTMATTER.format(name=name) + "# Title\n\nBody text.\n" + body
    if lines is not None:
        current = len(text.splitlines())
        text += "filler\n" * (lines - current)
    return text


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_skill(root: Path, name: str, text: str) -> Path:
    skill = root / name
    write(skill / "SKILL.md", text)
    return skill


class ValidateSkillsTests(unittest.TestCase):
    def run_main(self, skills_dir: Path) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = validate_skills.main(["--skills-dir", str(skills_dir)])
        return code, out.getvalue() + err.getvalue()

    def failures_for(self, root: Path) -> list[str]:
        results = validate_skills.validate_skills(root)
        return [f for fs in results.values() for f in fs]

    def assert_fails(self, root: Path, needle: str) -> None:
        failures = self.failures_for(root)
        self.assertTrue(
            any(needle in f for f in failures),
            f"no failure mentions {needle!r}: {failures}",
        )
        code, output = self.run_main(root)
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL", output)
        self.assertNotIn("Traceback", output)

    # --- acceptance: the real pack and the passing case -------------------

    def test_repo_skills_pass_with_exit_zero(self) -> None:
        code, output = self.run_main(SKILLS)
        self.assertEqual(code, 0, output)

    def test_valid_temp_skills_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            make_skill(root, "other-skill", skill_text("other-skill"))
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    # --- skills directory presence (requirement 6) ------------------------

    def test_missing_skills_dir_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = self.run_main(Path(tmp) / "absent")
            self.assertEqual(code, 2)

    def test_empty_skills_dir_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, output = self.run_main(Path(tmp))
            self.assertEqual(code, 1)
            self.assertIn("no skill directories found", output)

    def test_only_hidden_dirs_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".hidden").mkdir()
            write(root / ".hidden" / "SKILL.md", skill_text("hidden"))
            code, output = self.run_main(root)
            self.assertEqual(code, 1)
            self.assertIn("no skill directories found", output)

    def test_files_only_in_skills_dir_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "README.md", "# not a skill\n")
            code, output = self.run_main(root)
            self.assertEqual(code, 1)
            self.assertIn("no skill directories found", output)

    # --- frontmatter (acceptance: missing or invalid frontmatter) ---------

    def test_missing_skill_md_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "empty-skill").mkdir()
            self.assert_fails(root, "SKILL.md missing")

    def test_missing_frontmatter_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(root, "no-frontmatter", "# Title\n\nNo frontmatter here.\n")
            self.assert_fails(root, "frontmatter missing")

    def test_unclosed_frontmatter_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(root, "unclosed", "---\nname: unclosed\ndescription: x\n# Title\n")
            self.assert_fails(root, "frontmatter not closed")

    def test_invalid_yaml_frontmatter_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(root, "bad-yaml", "---\nname: [unclosed\n---\n# Title\n")
            self.assert_fails(root, "invalid YAML")

    def test_frontmatter_not_a_mapping_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(root, "list-yaml", "---\n- just\n- a list\n---\n# Title\n")
            self.assert_fails(root, "must be a YAML mapping")

    def test_missing_description_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(root, "no-description", "---\nname: no-description\n---\n# Title\n")
            self.assert_fails(root, "'description' must be a non-empty string")

    def test_empty_name_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(root, "empty-name", "---\nname: ''\ndescription: x\n---\n# Title\n")
            self.assert_fails(root, "'name' must be a non-empty string")

    def test_closing_fence_with_trailing_whitespace_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = "---\nname: trailing\ndescription: x\n---  \t\n# Title\n"
            make_skill(root, "trailing", text)
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    def test_bom_before_frontmatter_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bom").mkdir()
            (root / "bom" / "SKILL.md").write_bytes(
                b"\xef\xbb\xbf" + skill_text("bom").encode("utf-8")
            )
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    # --- line budgets (acceptance) ----------------------------------------

    def test_core_skill_at_150_lines_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("draftsman-core", 150)
            self.assertEqual(len(text.splitlines()), 150)
            make_skill(root, "draftsman-core", text)
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    def test_core_skill_at_151_lines_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("draftsman-core", 151)
            self.assertEqual(len(text.splitlines()), 151)
            make_skill(root, "draftsman-core", text)
            self.assert_fails(root, "over the 150-line budget")

    def test_other_skill_at_200_lines_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("other-skill", 200)
            self.assertEqual(len(text.splitlines()), 200)
            make_skill(root, "other-skill", text)
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    def test_other_skill_at_201_lines_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("other-skill", 201)
            self.assertEqual(len(text.splitlines()), 201)
            make_skill(root, "other-skill", text)
            self.assert_fails(root, "over the 200-line budget")

    def test_long_references_file_is_not_budgeted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            write(skill / "references" / "long.md", "line\n" * 500)
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    # --- links (acceptance and requirements 3, 4, 5) ----------------------

    def test_broken_relative_link_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("draftsman-core") + "\nSee [the guide](references/missing.md).\n"
            make_skill(root, "draftsman-core", text)
            self.assert_fails(root, "broken relative link")

    def test_broken_link_inside_references_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            write(skill / "references" / "page.md", "[back](../gone.md)\n")
            self.assert_fails(root, "broken relative link")

    def test_valid_relative_and_external_links_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(
                root,
                "draftsman-core",
                skill_text("draftsman-core")
                + "\n[ok](references/page.md) [anchor](#top) [web](https://example.com/x)"
                + " [mail](mailto:a@example.com) [frag](references/page.md#sec)\n",
            )
            write(skill / "references" / "page.md", "# Page\n")
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    def test_url_encoded_relative_link_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(
                root,
                "draftsman-core",
                skill_text("draftsman-core") + "\nSee [x](references/my%20file.md).\n",
            )
            write(skill / "references" / "my file.md", "# Page\n")
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    def test_link_with_title_and_angle_brackets_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(
                root,
                "draftsman-core",
                skill_text("draftsman-core")
                + '\n[a](<references/with space.md> "Title") [b][ref]\n\n[ref]: references/page.md\n',
            )
            write(skill / "references" / "with space.md", "# A\n")
            write(skill / "references" / "page.md", "# B\n")
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    def test_link_escaping_skill_directory_fails_even_if_target_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            skills = repo / "skills"
            write(repo / "docs" / "x.md", "# Shared doc\n")
            make_skill(
                skills,
                "draftsman-core",
                skill_text("draftsman-core") + "\nSee [docs](../../docs/x.md).\n",
            )
            self.assert_fails(skills, "link escapes skill directory")

    def test_percent_encoded_dot_dot_escape_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            skills = repo / "skills"
            write(repo / "docs" / "x.md", "# Shared doc\n")
            make_skill(
                skills,
                "draftsman-core",
                skill_text("draftsman-core") + "\nSee [docs](%2e%2e/%2e%2e/docs/x.md).\n",
            )
            self.assert_fails(skills, "link escapes skill directory")

    def test_encoded_slash_dot_dot_escape_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            skills = repo / "skills"
            write(repo / "docs" / "x.md", "# Shared doc\n")
            make_skill(
                skills,
                "draftsman-core",
                skill_text("draftsman-core") + "\nSee [docs](..%2f..%2fdocs%2fx.md).\n",
            )
            self.assert_fails(skills, "link escapes skill directory")

    def test_absolute_path_link_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            skills = repo / "skills"
            write(repo / "docs" / "x.md", "# Shared doc\n")
            make_skill(
                skills,
                "draftsman-core",
                skill_text("draftsman-core") + f"\nSee [docs]({(repo / 'docs' / 'x.md').as_posix()}).\n",
            )
            self.assert_fails(skills, "link escapes skill directory")

    def test_symlink_pointing_outside_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            skills = repo / "skills"
            write(repo / "docs" / "x.md", "# Shared doc\n")
            skill = make_skill(
                skills,
                "draftsman-core",
                skill_text("draftsman-core") + "\nSee [docs](references/linked.md).\n",
            )
            (skill / "references").mkdir()
            try:
                os.symlink(repo / "docs" / "x.md", skill / "references" / "linked.md")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks not available on this platform")
            self.assert_fails(skills, "link escapes skill directory")

    def test_nul_byte_in_link_reports_fail_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(
                root,
                "draftsman-core",
                skill_text("draftsman-core") + "\nSee [x](references/a%00b.md).\n",
            )
            code, output = self.run_main(root)
            self.assertEqual(code, 1)
            self.assertIn("FAIL draftsman-core", output)
            self.assertIn("NUL byte", output)
            self.assertNotIn("Traceback", output)

    def test_link_to_directory_named_md_reports_fail_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            (skill / "references" / "folder.md").mkdir(parents=True)
            code, output = self.run_main(root)
            self.assertEqual(code, 1)
            self.assertIn("unreadable file references/folder.md", output)
            self.assertNotIn("Traceback", output)

    def test_invalid_utf8_skill_md_reports_fail_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad-bytes").mkdir()
            (root / "bad-bytes" / "SKILL.md").write_bytes(b"---\nname: x\n\xff\xfe\n---\n")
            code, output = self.run_main(root)
            self.assertEqual(code, 1)
            self.assertIn("FAIL bad-bytes", output)
            self.assertIn("unreadable", output)
            self.assertNotIn("Traceback", output)

    def test_invalid_utf8_reference_file_reports_fail_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            (skill / "references").mkdir()
            (skill / "references" / "bad.md").write_bytes(b"\xff\xfe broken\n")
            code, output = self.run_main(root)
            self.assertEqual(code, 1)
            self.assertIn("unreadable file references/bad.md", output)
            self.assertNotIn("Traceback", output)

    # --- fenced code and inline code (requirement 1 and the inline rules) -

    def test_links_and_script_paths_inside_fences_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = (
                skill_text("draftsman-core")
                + "\n```markdown\n[example](nope/also-missing.md)\nRun scripts/ghost.py\n```\n"
                + "\n~~~\n[tilde](nope/tilde.md)\n`scripts/ghost2.py`\n~~~\n"
            )
            make_skill(root, "draftsman-core", text)
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    def test_longer_fence_is_not_closed_by_shorter_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = (
                skill_text("draftsman-core")
                + "\n````\n```\n[hidden](nope.md)\n```\n````\n"
                + "\nAfter the fence [after](nope2.md).\n"
            )
            make_skill(root, "draftsman-core", text)
            self.assert_fails(root, "nope2.md")

    def test_unclosed_fence_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("draftsman-core") + "\n```\n[hidden](nope.md)\n"
            make_skill(root, "draftsman-core", text)
            self.assert_fails(root, "unclosed code fence")

    def test_links_inside_inline_code_are_ignored_for_any_run_length(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = (
                skill_text("draftsman-core")
                + "\nInline `[x](nope/a.md)` and ``[y](nope/b.md)`` and "
                + "`` a ` [z](nope/c.md) ``, all examples.\n"
            )
            make_skill(root, "draftsman-core", text)
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    def test_link_after_code_fence_is_still_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = (
                skill_text("draftsman-core")
                + "\n```\n[example](nope.md)\n```\n"
                + "\nReal [broken](nope/real.md) link.\n"
            )
            make_skill(root, "draftsman-core", text)
            self.assert_fails(root, "broken relative link")

    # --- script paths (requirement 2) -------------------------------------

    def test_missing_script_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("draftsman-core") + "\nRun scripts/check.py first.\n"
            make_skill(root, "draftsman-core", text)
            self.assert_fails(root, "missing script path")

    def test_present_script_path_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("draftsman-core") + "\nRun scripts/check.py first.\n"
            skill = make_skill(root, "draftsman-core", text)
            write(skill / "scripts" / "check.py", "print('never executed')\n")
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    def test_missing_backticked_script_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("draftsman-core") + "\nRun `scripts/absent.py` first.\n"
            make_skill(root, "draftsman-core", text)
            self.assert_fails(root, "missing script path")

    def test_present_backticked_script_path_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("draftsman-core") + "\nRun `scripts/check.py` first.\n"
            skill = make_skill(root, "draftsman-core", text)
            write(skill / "scripts" / "check.py", "x = 1\n")
            code, output = self.run_main(root)
            self.assertEqual(code, 0, output)

    def test_script_in_double_backtick_span_is_still_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("draftsman-core") + "\nRun ``scripts/absent.py`` first.\n"
            make_skill(root, "draftsman-core", text)
            self.assert_fails(root, "missing script path")

    def test_script_path_escaping_skill_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside.py"
            write(outside, "x = 1\n")
            text = skill_text("draftsman-core") + "\nRun `scripts/../../outside.py`.\n"
            make_skill(root / "skills", "draftsman-core", text)
            self.assert_fails(root / "skills", "escapes skill directory")

    def test_validator_does_not_execute_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = Path(tmp) / "ran.marker"
            skill = make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            write(
                skill / "scripts" / "boom.py",
                f"open({str(marker)!r}, 'w').write('ran')\n",
            )
            self.run_main(root)
            self.assertFalse(marker.exists())

    # --- failure reporting --------------------------------------------------

    def test_failure_lines_name_skill_and_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            make_skill(root, "broken", "# no frontmatter\n")
            code, output = self.run_main(root)
            self.assertEqual(code, 1)
            self.assertIn("OK   draftsman-core", output)
            self.assertIn("FAIL broken", output)
            self.assertIn("1 of 2 skill(s) failed", output)

    # --- review round 1: resolved roots (F1) ------------------------------

    def test_relative_skills_dir_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root / "skills", "draftsman-core", skill_text("draftsman-core", body="See [r](references/page.md) and `scripts/check.py`.\n"))
            write(skill / "references" / "page.md", "# Page\n")
            write(skill / "scripts" / "check.py", "x = 1\n")
            previous = os.getcwd()
            os.chdir(root)
            try:
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = validate_skills.main(["--skills-dir", "skills"])
            finally:
                os.chdir(previous)
            self.assertEqual(code, 0, out.getvalue() + err.getvalue())
            self.assertIn("OK   draftsman-core", out.getvalue())
            self.assertNotIn("internal error", out.getvalue())

    def test_symlinked_skills_dir_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real-skills"
            skill = make_skill(real, "draftsman-core", skill_text("draftsman-core", body="See [r](references/page.md).\n"))
            write(skill / "references" / "page.md", "# Page\n")
            link = root / "linked-skills"
            try:
                os.symlink(real, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks not available on this platform")
            code, output = self.run_main(link)
            self.assertEqual(code, 0, output)
            self.assertIn("OK   draftsman-core", output)
            self.assertNotIn("internal error", output)

    def test_symlinked_skill_directory_passes_and_keeps_its_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            elsewhere = root / "elsewhere" / "pack-copy"
            write(elsewhere / "SKILL.md", skill_text("draftsman-core", 150))
            skills = root / "skills"
            skills.mkdir()
            try:
                os.symlink(elsewhere, skills / "draftsman-core", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks not available on this platform")
            code, output = self.run_main(skills)
            self.assertEqual(code, 0, output)
            self.assertIn("OK   draftsman-core", output)

    # --- review round 1: a script path inside a link is reported once (F2) --

    def test_script_inside_link_target_is_reported_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_skill(root, "draftsman-core", skill_text("draftsman-core", body="[x](scripts/foo.py)\n"))
            failures = self.failures_for(root)
            matching = [f for f in failures if "foo.py" in f]
            self.assertEqual(len(matching), 1, failures)
            self.assertIn("broken relative link", matching[0])
            code, _ = self.run_main(root)
            self.assertEqual(code, 1)

    def test_link_from_references_resolves_once_against_its_own_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "draftsman-core", skill_text("draftsman-core"))
            write(skill / "references" / "page.md", "[x](scripts/foo.py)\n")
            write(skill / "scripts" / "foo.py", "x = 1\n")
            failures = self.failures_for(root)
            matching = [f for f in failures if "foo.py" in f]
            self.assertEqual(len(matching), 1, failures)
            self.assertIn("broken relative link in references/page.md", matching[0])

    def test_bare_script_path_on_a_link_line_is_still_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = skill_text("draftsman-core", body="See [docs](references/page.md) then run scripts/absent.py.\n")
            skill = make_skill(root, "draftsman-core", text)
            write(skill / "references" / "page.md", "# Page\n")
            self.assert_fails(root, "missing script path")


if __name__ == "__main__":
    unittest.main()
