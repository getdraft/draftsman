"""Vendoring, projection and freshness of DRAFT skills (E4).

Projects the real framework skills into a temporary company workspace and
checks the generated markers against an independently computed sha256.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from draft_table.repo import ensure_workspace_layout, refresh_vendored_framework

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup_ide = load("setup_ide_dist", "framework/tools/setup_ide.py")
validate_skills = load("validate_skills_dist", "framework/tools/validate_skills.py")


def independent_sha(skill_dir: Path) -> str:
    """The documented hash: sorted relative paths and bytes of every file."""
    digest = hashlib.sha256()
    files = sorted(
        (p for p in skill_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts),
        key=lambda p: p.relative_to(skill_dir).as_posix(),
    )
    for path in files:
        digest.update(path.relative_to(skill_dir).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def frontmatter(text: str) -> dict:
    assert text.startswith("---\n"), "frontmatter must come first"
    return yaml.safe_load(text.split("---", 2)[1])


class Workspace:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "company-draft"
        self.path.mkdir()
        ensure_workspace_layout(self.path)
        refresh_vendored_framework(self.path)
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()

    def run_setup(self) -> None:
        with mock.patch("pathlib.Path.cwd", return_value=self.path), contextlib.redirect_stdout(io.StringIO()):
            setup_ide.setup_ide()

    def check(self) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = validate_skills.main(["--workspace", str(self.path)])
        return code, buf.getvalue()

    @property
    def source(self) -> Path:
        return self.path / ".draft" / "framework" / "skills"

    @property
    def projected(self) -> Path:
        return self.path / ".claude" / "skills"


class VendoringTests(unittest.TestCase):
    def test_refresh_vendors_skills(self):
        with Workspace() as ws:
            self.assertTrue((ws.source / "draftsman-core" / "SKILL.md").is_file())
            self.assertTrue((ws.source / "draftsman-core" / "references" / "character.md").is_file())
            self.assertTrue((ws.path / ".draft" / "framework" / "tools" / "skill_hash.py").is_file())

    def test_vendored_path_rewrite_covers_skills(self):
        from draft_table.repo import vendored_framework_text

        self.assertEqual(vendored_framework_text("see framework/skills/x and framework/skills"), "see skills/x and skills")


class ProjectionTests(unittest.TestCase):
    def test_projects_every_skill_as_marked_copies(self):
        with Workspace() as ws:
            ws.run_setup()
            names = sorted(p.name for p in ws.source.iterdir() if p.is_dir())
            self.assertIn("draftsman-core", names)
            for name in names:
                skill_md = ws.projected / name / "SKILL.md"
                self.assertTrue(skill_md.is_file(), name)
                self.assertFalse((ws.projected / name).is_symlink())
                self.assertFalse(skill_md.is_symlink())
                front = frontmatter(skill_md.read_text(encoding="utf-8"))
                self.assertIs(front["generated"], True)
                self.assertEqual(front["source_sha256"], independent_sha(ws.source / name))
                self.assertEqual(front["name"], name)
            self.assertTrue((ws.projected / "draftsman-core" / "references" / "character.md").is_file())

    def test_existing_outputs_unchanged(self):
        with Workspace() as ws:
            ws.run_setup()
            self.assertTrue((ws.path / ".claude" / "commands" / "draft.md").exists())

    def test_agents_index_created_and_existing_text_preserved(self):
        with Workspace() as ws:
            agents = ws.path / "AGENTS.md"
            agents.write_text("# Workspace bootstrap\n\nKeep this text.\n", encoding="utf-8")
            ws.run_setup()
            text = agents.read_text(encoding="utf-8")
            self.assertIn("Keep this text.", text)
            self.assertIn("<!-- DRAFT-SKILLS:BEGIN generated: true source_sha256: ", text)
            self.assertIn(".draft/framework/skills/draftsman-core/SKILL.md", text)
            ws.run_setup()
            self.assertEqual(agents.read_text(encoding="utf-8"), text, "second run must be idempotent")

    def test_new_agents_index_starts_with_marker_comment(self):
        with Workspace() as ws:
            agents = ws.path / "AGENTS.md"
            if agents.exists():
                agents.unlink()
            ws.run_setup()
            self.assertTrue(agents.read_text(encoding="utf-8").startswith("<!-- DRAFT-SKILLS:BEGIN generated: true"))

    def test_stale_generated_projection_is_removed_and_manual_one_kept(self):
        with Workspace() as ws:
            ws.run_setup()
            stale = ws.projected / "draftsman-gone"
            stale.mkdir()
            (stale / "SKILL.md").write_text("---\nname: draftsman-gone\ndescription: x\ngenerated: true\nsource_sha256: 0\n---\n", encoding="utf-8")
            manual = ws.projected / "my-own"
            manual.mkdir()
            (manual / "SKILL.md").write_text("---\nname: my-own\ndescription: mine\n---\n", encoding="utf-8")
            ws.run_setup()
            self.assertFalse(stale.exists())
            self.assertTrue(manual.exists())


class FreshnessTests(unittest.TestCase):
    def test_fresh_projection_passes(self):
        with Workspace() as ws:
            ws.run_setup()
            code, out = ws.check()
            self.assertEqual(code, 0, out)

    def test_editing_a_source_skill_fails_the_check(self):
        with Workspace() as ws:
            ws.run_setup()
            core = ws.source / "draftsman-core" / "SKILL.md"
            core.write_text(core.read_text(encoding="utf-8") + "\nAn edit.\n", encoding="utf-8")
            code, out = ws.check()
            self.assertEqual(code, 1)
            self.assertIn("draftsman-core", out)
            self.assertIn("stale", out)

    def test_editing_a_reference_file_also_fails(self):
        with Workspace() as ws:
            ws.run_setup()
            ref = ws.source / "draftsman-core" / "references" / "onboarding.md"
            ref.write_text(ref.read_text(encoding="utf-8") + "\nChanged.\n", encoding="utf-8")
            self.assertEqual(ws.check()[0], 1)

    def test_missing_projection_fails(self):
        with Workspace() as ws:
            ws.run_setup()
            import shutil

            shutil.rmtree(ws.projected / "draftsman-query")
            code, out = ws.check()
            self.assertEqual(code, 1)
            self.assertIn("draftsman-query: projection missing", out)

    def test_stale_agents_index_fails(self):
        with Workspace() as ws:
            ws.run_setup()
            skill = ws.source / "draftsman-query" / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\nx\n", encoding="utf-8")
            ws.run_setup()  # reprojects everything, index fresh again
            self.assertEqual(ws.check()[0], 0)
            agents = ws.path / "AGENTS.md"
            import re

            agents.write_text(
                re.sub(r"source_sha256: [0-9a-f]{64}", "source_sha256: " + "0" * 64, agents.read_text(encoding="utf-8"), count=1),
                encoding="utf-8",
            )
            code, out = ws.check()
            self.assertEqual(code, 1)
            self.assertIn("AGENTS.md: skill index is stale", out)

    def test_workspace_without_vendored_skills_fails_clearly(self):
        with tempfile.TemporaryDirectory() as d:
            code = validate_skills.main(["--workspace", d])
            self.assertEqual(code, 1)


class SafetyTests(unittest.TestCase):
    def test_editing_a_projected_file_fails_the_check(self):
        with Workspace() as ws:
            ws.run_setup()
            ref = ws.projected / "draftsman-core" / "references" / "role.md"
            ref.write_text("tampered", encoding="utf-8")
            code, out = ws.check()
            self.assertEqual(code, 1)
            self.assertIn("edited or is incomplete", out)

    def test_appending_to_a_projected_skill_md_fails_the_check(self):
        with Workspace() as ws:
            ws.run_setup()
            skill = ws.projected / "draftsman-core" / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\nextra\n", encoding="utf-8")
            self.assertEqual(ws.check()[0], 1)

    def test_an_extra_file_in_a_projection_fails_the_check(self):
        with Workspace() as ws:
            ws.run_setup()
            (ws.projected / "draftsman-core" / "stray.md").write_text("x", encoding="utf-8")
            self.assertEqual(ws.check()[0], 1)

    def test_a_user_skill_with_a_framework_name_is_not_overwritten(self):
        with Workspace() as ws:
            own = ws.projected / "draftsman-core"
            own.mkdir(parents=True)
            (own / "SKILL.md").write_text("---\nname: draftsman-core\ndescription: mine\n---\nMy own.\n", encoding="utf-8")
            (own / "notes.txt").write_text("keep", encoding="utf-8")
            ws.run_setup()
            self.assertIn("My own.", (own / "SKILL.md").read_text(encoding="utf-8"))
            self.assertTrue((own / "notes.txt").exists())
            self.assertEqual(ws.check()[0], 1, "the check must still flag the unprojected skill")

    def test_a_malformed_agents_block_is_left_untouched(self):
        with Workspace() as ws:
            agents = ws.path / "AGENTS.md"
            damaged = "# Mine\n\n<!-- DRAFT-SKILLS:BEGIN generated: true source_sha256: " + "a" * 64 + " -->\nUSER TEXT\n"
            agents.write_text(damaged, encoding="utf-8")
            ws.run_setup()
            ws.run_setup()
            self.assertEqual(agents.read_text(encoding="utf-8"), damaged)
            code, out = ws.check()
            self.assertEqual(code, 1)
            self.assertIn("malformed", out)

    def test_crlf_agents_file_keeps_its_line_endings(self):
        with Workspace() as ws:
            agents = ws.path / "AGENTS.md"
            agents.write_bytes(b"# Mine\r\n\r\nKeep.\r\n")
            ws.run_setup()
            data = agents.read_bytes()
            self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
            self.assertIn(b"Keep.", data)
            ws.run_setup()
            self.assertEqual(agents.read_bytes(), data)

    def test_routers_name_explicit_skill_paths_not_a_glob(self):
        for name in ("guide", "review", "update"):
            text = (ROOT / "framework" / "draft-actions" / f"{name}.md").read_text(encoding="utf-8").split("---", 2)[2]
            self.assertNotIn("Glob", text)
            self.assertIn(".draft/framework/skills/", text)
            self.assertIn("framework/skills/", text)
            self.assertIn("Do not use `.claude/skills/`", text)


if __name__ == "__main__":
    unittest.main()
