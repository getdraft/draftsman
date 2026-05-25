from __future__ import annotations

import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from draft_table.config import save_config
from draft_table.draftsman import (
    DraftsmanEngine,
    build_draftsman_prompt,
    draftsman_workspace_context,
    invoke_provider,
    parse_provider_response,
    provider_timeout_seconds,
    public_proposal,
    safe_workspace_path,
)
from draft_table.paths import REPO_ROOT
from draft_table.repo import ensure_workspace_layout
from draft_table.sessions import DraftsmanSessionStore


class DraftsmanTests(unittest.TestCase):
    def test_answers_framework_question_without_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.yaml"
            save_config({"framework_repo_path": str(REPO_ROOT)}, config_path)
            engine = DraftsmanEngine(config_path, DraftsmanSessionStore(Path(directory) / "sessions"))

            response = engine.chat("What is a Technology Component?")

        self.assertFalse(response.provider_used)
        self.assertIn("Technology Component", response.answer)
        self.assertFalse(response.proposals)

    def test_answers_catalog_usage_question_without_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.yaml"
            save_config({"framework_repo_path": str(REPO_ROOT)}, config_path)
            engine = DraftsmanEngine(config_path, DraftsmanSessionStore(Path(directory) / "sessions"))

            response = engine.chat("Where is the Falcon agent used?")

        self.assertFalse(response.provider_used)
        self.assertIn("CrowdStrike Falcon Agent", response.answer)
        self.assertNotIn("```", response.answer)

    def test_setup_mode_without_workspace_guides_first_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.yaml"
            save_config({"framework_repo_path": str(REPO_ROOT)}, config_path)
            engine = DraftsmanEngine(config_path, DraftsmanSessionStore(Path(directory) / "sessions"))

            response = engine.chat("start setup mode")

        self.assertFalse(response.provider_used)
        self.assertIn("Setup mode", response.answer)
        self.assertIn("Current step", response.answer)
        self.assertIn("Left after that", response.answer)
        self.assertEqual(len(response.questions), 1)
        self.assertIn("company DRAFT workspace", response.questions[0])

    def test_public_proposal_hides_backend_content(self) -> None:
        public = public_proposal(
            {
                "id": "p1",
                "action": "create",
                "artifactType": "Host",
                "name": "Managed Host",
                "summary": "Creates a reusable host.",
                "path": "catalog/hosts/host-managed.yaml",
                "content": "schemaVersion: '1.0'",
            }
        )

        self.assertNotIn("content", public)
        self.assertEqual(public["path"], "catalog/hosts/host-managed.yaml")
        self.assertEqual(public["name"], "Managed Host")

    def test_parse_provider_response_extracts_json(self) -> None:
        raw = "Here is the result:\n" + json.dumps({"answer": "Done", "questions": [], "proposals": []})

        parsed = parse_provider_response(raw)

        self.assertEqual(parsed["answer"], "Done")

    def test_provider_timeout_returns_visible_answer(self) -> None:
        with mock.patch(
            "draft_table.draftsman.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["gemini"], timeout=10),
        ):
            answer = invoke_provider(
                {"type": "gemini-cli", "executable": "/usr/bin/gemini", "timeout_seconds": 10},
                "Draft something",
            )

        self.assertIn("Gemini CLI provider did not return within 10 seconds", answer)
        self.assertIn("I did not create or apply any artifacts", answer)
        self.assertNotIn("Draft something", answer)

    def test_provider_timeout_is_clamped(self) -> None:
        self.assertEqual(provider_timeout_seconds({"timeout_seconds": 1}), 5)
        self.assertEqual(provider_timeout_seconds({"timeout_seconds": 99999}), 1800)
        self.assertEqual(provider_timeout_seconds({"timeout_seconds": "invalid"}), 180)

    def test_prompt_guides_host_patch_management_as_mechanism_not_team_owner(self) -> None:
        prompt = build_draftsman_prompt(REPO_ROOT, None, "Build a Windows Server Host.", {"uploads": []})

        self.assertIn("For Host Requirement Group patch management", prompt)
        self.assertIn("patch platform, installed component", prompt)
        self.assertIn("do not ask which", prompt)
        self.assertIn("team owns patching", prompt)

    def test_prompt_includes_setup_mode_and_guided_cadence(self) -> None:
        prompt = build_draftsman_prompt(REPO_ROOT, None, "Help us get started.", {"uploads": []})

        self.assertIn("start setup mode", prompt)
        self.assertIn("current step", prompt)
        self.assertIn("what remains", prompt)
        self.assertIn("Ask no more than three questions", prompt)

    def test_prompt_explains_appliance_delivery_service_like_capability_answers(self) -> None:
        prompt = build_draftsman_prompt(REPO_ROOT, None, "Build an appliance-delivered Edge/Gateway Service.", {"uploads": []})

        self.assertIn("deliveryModel appliance", prompt)
        self.assertIn("vendor-product", prompt)
        self.assertIn("no Host wrapper", prompt)

    def test_prompt_requires_company_workspace_before_content_updates(self) -> None:
        prompt = build_draftsman_prompt(REPO_ROOT, REPO_ROOT, "Create a Frontline host.", {"uploads": []})

        self.assertIn("upstream draft-framework", prompt)
        self.assertIn("company-specific DRAFT repo path", prompt)
        self.assertIn("do not propose catalog/configuration content changes", prompt)

    def test_workspace_context_identifies_missing_company_workspace(self) -> None:
        context = draftsman_workspace_context(REPO_ROOT, None)

        self.assertIn("No company DRAFT workspace is selected", context)
        self.assertIn("company-specific DRAFT repo path", context)

    def test_safe_workspace_path_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                safe_workspace_path(Path(directory), "../outside.yaml")

    def test_safe_workspace_path_rejects_vendored_framework_edits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "must not edit"):
                safe_workspace_path(Path(directory), ".draft/framework/schemas/host.schema.yaml")
            with self.assertRaisesRegex(ValueError, "must not edit"):
                safe_workspace_path(Path(directory), ".draft/framework.lock")

    def test_provider_response_creates_public_artifact_proposal_without_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "provider.py"
            script.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "print(json.dumps({'answer':'I proposed one artifact.', 'questions': [], "
                "'proposals':[{'id':'p1','action':'create','artifactType':'Host','name':'Managed Host',"
                "'summary':'A reusable host pattern.','path':'catalog/hosts/host-managed.yaml',"
                "'content':'schemaVersion: 1.0'}]}))\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            config_path = Path(directory) / "config.yaml"
            save_config(
                {
                    "framework_repo_path": str(REPO_ROOT),
                    "provider": {"type": "custom-command", "executable": str(script)},
                },
                config_path,
            )
            engine = DraftsmanEngine(config_path, DraftsmanSessionStore(Path(directory) / "sessions"))

            response = engine.chat("Draft a managed host.")

        public = response.public_dict()
        self.assertTrue(response.provider_used)
        self.assertEqual(public["proposals"][0]["name"], "Managed Host")
        self.assertNotIn("content", public["proposals"][0])


    def test_apply_proposals_writes_draft_files_and_reports_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            ensure_workspace_layout(workspace)
            config_path = Path(directory) / "config.yaml"
            save_config(
                {
                    "framework_repo_path": str(REPO_ROOT),
                    "content_repo_path": str(workspace),
                },
                config_path,
            )
            engine = DraftsmanEngine(config_path, DraftsmanSessionStore(Path(directory) / "sessions"))
            session = engine.session_store.load(None)
            session["proposals"] = [
                {
                    "id": "stub-tech",
                    "action": "create",
                    "artifactType": "Technology Component",
                    "name": "Stub Technology",
                    "summary": "Incomplete stub — uid will be repaired before approval.",
                    "path": "catalog/technology-components/technology-stub.yaml",
                    "content": textwrap.dedent(
                        """
                        schemaVersion: "1.0"
                        type: technology_component
                        name: Stub Technology
                        vendor: Test Vendor
                        productName: Stub Tech
                        productVersion: "1"
                        classification: software
                        catalogStatus: stub
                        """
                    ).strip()
                    + "\n",
                    "applied": False,
                }
            ]
            engine.session_store.save(session)

            result = engine.apply_proposals(session["id"])

            target = workspace / "catalog" / "technology-components" / "technology-stub.yaml"
            self.assertTrue(target.exists())
            self.assertFalse(result.get("preWriteFailure"))
            self.assertEqual(len(result["applied"]), 1)


if __name__ == "__main__":
    unittest.main()
