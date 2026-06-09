from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from draft_table.repo import (
    ensure_git_repo,
    ensure_workspace_layout,
    framework_status,
    is_workspace,
    refresh_vendored_framework,
    repo_name_from_url,
)


class RepoTests(unittest.TestCase):
    def test_repo_name_from_url_handles_common_github_urls(self) -> None:
        self.assertEqual(repo_name_from_url("https://github.com/acme/draft-content.git"), "draft-content")
        self.assertEqual(repo_name_from_url("git@github.com:acme/platform catalog.git"), "platform-catalog")

    def test_ensure_workspace_layout_bootstraps_expected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "company-draft"
            workspace.mkdir()
            created = ensure_workspace_layout(workspace)

            self.assertTrue((workspace / "catalog").exists())
            self.assertTrue((workspace / "catalog" / "technology-components").exists())
            self.assertTrue((workspace / "catalog" / "hosts").exists())
            self.assertTrue((workspace / "catalog" / "runtime-services").exists())
            self.assertTrue((workspace / "catalog" / "data-at-rest-services").exists())
            self.assertTrue((workspace / "catalog" / "network-services").exists())
            self.assertTrue((workspace / "catalog" / "software-deployment-patterns").exists())
            self.assertTrue((workspace / "configurations" / "object-patches").exists())
            self.assertTrue((workspace / "configurations" / "capabilities").exists())
            self.assertTrue((workspace / "configurations" / "requirement-groups").exists())
            self.assertTrue((workspace / ".github" / "workflows" / "draft-framework-update.yml").exists())
            self.assertTrue((workspace / ".github" / "copilot-instructions.md").exists())
            self.assertTrue((workspace / ".github" / "CONTRIBUTING.md").exists())
            self.assertTrue((workspace / "README.md").exists())
            self.assertTrue((workspace / "AGENTS.md").exists())
            self.assertTrue((workspace / "CLAUDE.md").exists())
            self.assertTrue((workspace / "GEMINI.md").exists())
            self.assertTrue((workspace / "llms.txt").exists())
            self.assertTrue((workspace / ".draft" / "providers").exists())
            self.assertTrue((workspace / ".draft" / "workspace.yaml").exists())
            self.assertTrue((workspace / ".draft" / "framework.lock").exists())
            self.assertTrue((workspace / ".draft" / "framework" / "tools" / "validate.py").exists())
            self.assertTrue((workspace / ".draft" / "framework" / "schemas").exists())
            agents = workspace / ".draft" / "framework" / "AGENTS.md"
            self.assertTrue(agents.exists())
            self.assertIn("docs/draftsman.md", agents.read_text(encoding="utf-8"))
            workspace_agents = workspace / "AGENTS.md"
            self.assertIn(".draft/framework/docs/draftsman.md", workspace_agents.read_text(encoding="utf-8"))
            self.assertIn("Do not edit `.draft/framework/**`", workspace_agents.read_text(encoding="utf-8"))
            self.assertIn(".github/CONTRIBUTING.md", workspace_agents.read_text(encoding="utf-8"))
            self.assertIn("source of truth", workspace_agents.read_text(encoding="utf-8"))
            contributing = workspace / ".github" / "CONTRIBUTING.md"
            contributing_text = contributing.read_text(encoding="utf-8")
            self.assertIn("Default: GitHub Flow (`github-flow`)", contributing_text)
            self.assertIn("single protected `main` branch", contributing_text)
            workspace_readme = workspace / "README.md"
            self.assertIn("Start With This Prompt", workspace_readme.read_text(encoding="utf-8"))
            self.assertIn("I want a Draftsman session", workspace_readme.read_text(encoding="utf-8"))
            self.assertTrue((workspace / ".draft" / "framework" / "draft-framework.yaml").exists())
            self.assertTrue((workspace / ".draft" / "framework" / "VERSIONING.md").exists())
            workspace_config = (workspace / ".draft" / "workspace.yaml").read_text(encoding="utf-8")
            self.assertIn("activeRequirementGroups", workspace_config)
            self.assertIn("displayName: Company DRAFT", workspace_config)
            self.assertIn("updateWorkflow: enabled", workspace_config)
            workspace_config_data = yaml.safe_load(workspace_config)
            self.assertEqual(workspace_config_data["contribution"]["branchingStrategy"], "github-flow")
            lock = yaml.safe_load((workspace / ".draft" / "framework.lock").read_text(encoding="utf-8"))
            manifest = yaml.safe_load(Path("draft-framework.yaml").read_text(encoding="utf-8"))
            self.assertEqual(lock["framework"]["version"], manifest["version"])
            self.assertTrue(created)
            self.assertTrue(is_workspace(workspace))

    def test_update_workflow_normalizes_bare_semver_target_ref(self) -> None:
        workflow = Path("framework/templates/github/draft-framework-update.yml").read_text(encoding="utf-8")

        self.assertIn("def canonical_target_ref(value: str) -> str:", workflow)
        self.assertIn('ref = value.strip().removeprefix("refs/tags/")', workflow)
        self.assertIn('v_tag = f"v{ref}"', workflow)
        self.assertIn('target_ref = canonical_target_ref(target_ref_input)', workflow)
        self.assertIn("Use a branch, commit, or tag such as vA.B.C.", workflow)

    def test_refresh_vendored_framework_updates_framework_copy_and_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "company-draft"
            workspace.mkdir()
            ensure_workspace_layout(workspace)
            (workspace / "README.md").unlink()

            refreshed = refresh_vendored_framework(workspace)
            status = framework_status(workspace)

            self.assertTrue((workspace / ".draft" / "framework" / "configurations").exists())
            self.assertTrue((workspace / ".draft" / "framework" / "templates").exists())
            self.assertTrue((workspace / "README.md").exists())
            self.assertTrue(any(path.name == "framework.lock" for path in refreshed))
            self.assertTrue(any(path.name == "README.md" for path in refreshed))
            self.assertTrue(status["vendored"])

    def test_workspace_templates_render_existing_workspace_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "frontline-drafting-table"
            workspace.mkdir()
            (workspace / ".draft").mkdir()
            (workspace / ".draft" / "workspace.yaml").write_text(
                yaml.safe_dump(
                    {
                        "schemaVersion": "1.0",
                        "workspace": {
                            "name": "frontline-drafting-table",
                            "displayName": "Frontline Education DRAFT Workspace",
                            "companyName": "Frontline Education",
                        },
                        "contribution": {"branchingStrategy": "trunk-based"},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            ensure_workspace_layout(workspace)

            readme = (workspace / "README.md").read_text(encoding="utf-8")
            agents = (workspace / "AGENTS.md").read_text(encoding="utf-8")
            contributing = (workspace / ".github" / "CONTRIBUTING.md").read_text(encoding="utf-8")
            llms = (workspace / "llms.txt").read_text(encoding="utf-8")
            self.assertIn("# Frontline Education DRAFT Workspace", readme)
            self.assertIn("I want a Draftsman session for Frontline Education DRAFT Workspace.", readme)
            self.assertIn("Read and follow the repository bootstrap instructions, starting with AGENTS.md.", readme)
            self.assertIn("Ask only the first question", readme)
            self.assertIn("catalog authoring requests for Frontline Education", agents)
            self.assertIn("trunk-based", contributing)
            self.assertIn("# Frontline Education DRAFT Workspace", llms)
            self.assertNotIn("{{workspace_label}}", readme)

    def test_ensure_git_repo_creates_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "new-draft-content"

            result = ensure_git_repo(workspace)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((workspace / ".git").exists())

    def test_ensure_git_repo_rejects_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "not-a-directory"
            target.write_text("content", encoding="utf-8")

            result = ensure_git_repo(target)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a directory", result.stderr)


if __name__ == "__main__":
    unittest.main()
