"""#495: /draft update and the refresh workflow must vendor like vendor_framework().

Step 5 used to copy only the upstream framework/ directory and then copy
upstream templates/ onto .draft/templates. That dropped FRAMEWORK_VENDOR_FILES
and, when .draft/templates already existed, created .draft/templates/templates/.
The workflow kept a second directory list and skipped skills/. Both paths now
call vendor_framework().
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from draft_table.repo import (
    FRAMEWORK_VENDOR_DIRS,
    FRAMEWORK_VENDOR_FILES,
    vendor_framework,
)


ROOT = Path(__file__).resolve().parents[1]
STEPS = ROOT / "framework" / "skills" / "draftsman-update" / "references" / "steps.md"
WORKFLOWS = (
    ROOT / "framework" / "templates" / "github" / "draft-framework-update.yml",
    ROOT / "templates" / "workspace" / ".github" / "workflows" / "draft-framework-update.yml.tmpl",
)
SCAN_ROOTS = (
    ROOT / "framework" / "skills",
    ROOT / "framework" / "docs",
    ROOT / "framework" / "templates",
    ROOT / "templates",
    ROOT / "draft_table",
)
BAD_TEMPLATES_DESTINATION = ".draft/framework/../templates"
HEREDOC_RE = re.compile(r"python - <<'PY'\n(.*?)\n[ \t]*PY\n", re.S)


def snapshot(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def seed_workspace(workspace: Path) -> None:
    framework = workspace / ".draft" / "framework"
    framework.mkdir(parents=True)
    (framework / "AGENTS.md").write_text("STALE ROOT\n", encoding="utf-8")
    (framework / "STALE_VENDOR_MARKER.txt").write_text("remove me\n", encoding="utf-8")
    templates = workspace / ".draft" / "templates"
    templates.mkdir(parents=True)
    (templates / "keep.txt").write_text("company template\n", encoding="utf-8")
    (workspace / ".draft" / "framework.lock").write_text("LOCK SENTINEL\n", encoding="utf-8")


def embedded_script(path: Path) -> str:
    match = HEREDOC_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        raise AssertionError(f"{path} has no embedded Python refresh script")
    return textwrap.dedent(match.group(1))


def copy_framework_from(path: Path):
    script = embedded_script(path)
    module = ast.parse(script)
    function = next(
        (node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "copy_framework"),
        None,
    )
    if function is None:
        raise AssertionError(f"{path} does not define copy_framework")
    source = ast.get_source_segment(script, function)
    if not source:
        raise AssertionError(f"{path} copy_framework source could not be read")
    return script, source


class FrameworkVendorUpdateTests(unittest.TestCase):
    def test_update_docs_do_not_copy_templates_onto_the_workspace(self) -> None:
        for root in SCAN_ROOTS:
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in {".md", ".yml", ".yaml", ".tmpl", ".py"}:
                    continue
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(BAD_TEMPLATES_DESTINATION, text, str(path))

        step = STEPS.read_text(encoding="utf-8").split("## Step 5:", 1)[1].split("## Step 6:", 1)[0]
        self.assertIn("vendor_framework", step)
        self.assertNotIn("cp -r", step)
        self.assertNotIn("rm -rf .draft/framework", step)
        self.assertIn('vendor_framework(Path("."), Path("/tmp/draft-framework-update"), overwrite=True)', step)

    def test_documented_replace_matches_vendor_framework(self) -> None:
        reference = self.vendored_workspace(vendor_framework)
        documented = self.vendored_workspace(self.run_documented_step)
        for workflow in WORKFLOWS:
            produced = self.vendored_workspace(lambda workspace, path=workflow: self.run_workflow_copy(path, workspace))
            self.assert_same_tree(reference, produced, workflow.name)
        self.assert_same_tree(reference, documented, "steps.md")

    def test_workflows_delegate_to_vendor_framework(self) -> None:
        for path in WORKFLOWS:
            script, _source = copy_framework_from(path)
            self.assertIn("vendor_framework(workspace, source_repo, overwrite=True)", script)
            self.assertNotIn("shutil.copytree", script)
            self.assertNotIn("def vendored_text", script)

    def vendored_workspace(self, replace) -> dict[str, bytes]:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "company-draft"
            workspace.mkdir()
            seed_workspace(workspace)
            replace(workspace)
            self.assert_vendor_contract(workspace)
            return snapshot(workspace)

    def run_documented_step(self, workspace: Path) -> None:
        step = STEPS.read_text(encoding="utf-8").split("## Step 5:", 1)[1].split("## Step 6:", 1)[0]
        match = re.search(r"python3 - <<'PY'\n(.*)\nPY\n", step, re.S)
        self.assertIsNotNone(match, "step 5 is missing its vendor_framework command")
        code = match.group(1).replace('"/tmp/draft-framework-update"', repr(str(ROOT)))
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def run_workflow_copy(self, workflow: Path, workspace: Path) -> None:
        _script, source = copy_framework_from(workflow)
        namespace = {"workspace": workspace, "Path": Path}
        original_path = list(sys.path)
        try:
            exec(compile("from __future__ import annotations\n" + source, str(workflow), "exec"), namespace)
            namespace["copy_framework"](ROOT)
        finally:
            sys.path[:] = original_path

    def assert_vendor_contract(self, workspace: Path) -> None:
        vendor_root = workspace / ".draft" / "framework"
        self.assertFalse((vendor_root / "STALE_VENDOR_MARKER.txt").exists())
        for filename in FRAMEWORK_VENDOR_FILES:
            self.assertTrue((vendor_root / filename).is_file(), filename)
        for relative in FRAMEWORK_VENDOR_DIRS:
            self.assertTrue((vendor_root / relative).is_dir(), relative)
        agents = (vendor_root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("docs/draftsman.md", agents)
        self.assertIn(".draft/framework", agents)
        self.assertNotIn("STALE ROOT", agents)
        steps = vendor_root / "skills" / "draftsman-update" / "references" / "steps.md"
        self.assertIn("vendor_framework", steps.read_text(encoding="utf-8"))
        self.assertEqual((workspace / ".draft" / "templates" / "keep.txt").read_text(encoding="utf-8"), "company template\n")
        self.assertFalse((workspace / ".draft" / "templates" / "templates").exists())
        self.assertEqual((workspace / ".draft" / "framework.lock").read_text(encoding="utf-8"), "LOCK SENTINEL\n")
        self.assertFalse((vendor_root / "draft_table").exists())
        self.assertTrue((vendor_root / "templates" / "workspace").is_dir())

    def assert_same_tree(self, expected: dict[str, bytes], actual: dict[str, bytes], label: str) -> None:
        self.assertEqual(set(expected) - set(actual), set(), f"{label} is missing files")
        self.assertEqual(set(actual) - set(expected), set(), f"{label} has extra files")
        mismatched = [path for path in expected if expected[path] != actual[path]]
        self.assertEqual(mismatched, [], f"{label} content differs")


if __name__ == "__main__":
    unittest.main()
