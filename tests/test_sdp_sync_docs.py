"""#195 S3.1: the setup guide describes the pipeline the templates and tool actually implement."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "framework" / "tools"))

import sdp_sync  # noqa: E402

GUIDE = (ROOT / "framework" / "docs" / "decentralized-sdp-setup.md").read_text(encoding="utf-8")
RETURN_PATH = (ROOT / "framework" / "docs" / "proposals" / "sdp-return-path.md").read_text(encoding="utf-8")
TEMPLATES = ROOT / "templates" / "github"


def template_names(pattern: str) -> set[str]:
    text = "".join(p.read_text(encoding="utf-8") for p in TEMPLATES.glob("*.tmpl"))
    return set(re.findall(pattern, text))


class SetupGuideTests(unittest.TestCase):
    def test_every_secret_and_variable_the_templates_read_is_documented(self) -> None:
        names = template_names(r"(?:secrets|vars)\.([A-Z_]+)")
        self.assertEqual(names, {"DRAFT_APP_ID", "DRAFT_APP_PRIVATE_KEY", "DRAFT_CENTRAL_REPO_NAME", "DRAFT_FRAMEWORK_REF",
                                 "DRAFT_RECEIVER_APP_ID", "DRAFT_RECEIVER_APP_PRIVATE_KEY",
                                 "DRAFT_SYNC_AUTO_MERGE", "DRAFT_SYNC_AWAIT_MINUTES"})
        for name in names:
            self.assertIn(f"`{name}`", GUIDE)

    def test_every_workflow_and_step_name_matches_the_templates(self) -> None:
        for path in TEMPLATES.glob("*.tmpl"):
            workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIn(f"**{workflow['name']}**", GUIDE)
        for step in ("Await Central Result",):
            self.assertIn(step, GUIDE)

    def test_the_pipeline_constants_are_the_tools(self) -> None:
        for text in (sdp_sync.PAYLOAD_FORMAT, sdp_sync.AUDIENCE_PREFIX, sdp_sync.RESULTS_BRANCH, sdp_sync.SYNC_BRANCH_PREFIX,
                     sdp_sync.OIDC_JWKS_URL, *sdp_sync.PRODUCT_OWNED_TYPES, *sdp_sync.DERIVED_PATHS, "65,000", "draft-sdp-sync"):
            self.assertIn(text, GUIDE)

    def test_the_required_known_limits_are_documented(self) -> None:
        self.assertIn("A live OIDC token can be resent within its lifetime", GUIDE)
        self.assertIn("Approve workflows to run", GUIDE)
        self.assertIn("Allow GitHub Actions to create and approve pull requests", GUIDE)
        self.assertIn("Allow auto-merge", GUIDE)
        self.assertIn("For pull requests only", GUIDE)
        self.assertIn("repository.id", GUIDE)
        self.assertIn("repository_id", GUIDE)
        self.assertIn("A renamed repository still syncs", GUIDE)
        self.assertNotIn("tracked as a follow-up (getdraft/draftsman#455)", GUIDE)

    def test_fully_automatic_merge_uses_a_second_app_and_two_rulesets(self) -> None:
        self.assertIn("## Fully Automatic Merge", GUIDE)
        self.assertIn("`DRAFT_RECEIVER_APP_ID`", GUIDE)
        self.assertIn("`DRAFT_RECEIVER_APP_PRIVATE_KEY`", GUIDE)
        self.assertIn("**Ruleset A**", GUIDE)
        self.assertIn("**Ruleset B**", GUIDE)
        self.assertIn("**Ruleset C**", GUIDE)
        self.assertIn("must be **Always**", GUIDE)
        self.assertIn("For an `opened` run, `workflow_run.actor` is the account that opened the pull request", GUIDE)
        self.assertIn("draft-sdp-merge", GUIDE)
        self.assertIn("workflow_run.actor", GUIDE)
        self.assertIn("triggering_actor", GUIDE)
        self.assertIn("up to date", GUIDE)
        self.assertIn("contents write and pull-requests write", GUIDE)
        self.assertIn("skips every rule", GUIDE)
        self.assertIn("Pull requests: Read and write", GUIDE)
        self.assertIn("For pull requests only", GUIDE)
        self.assertIn("**DRAFT Sync Pull Request Merge**", GUIDE)
        self.assertIn("the main gate", GUIDE)
        self.assertIn("repository.id", GUIDE)
        checks = GUIDE.split("## Pull Requests and Required Checks", 1)[1].split("## Fully Automatic Merge", 1)[0]
        self.assertIn("Approve workflows to run", checks)
        self.assertIn("(#fully-automatic-merge)", checks)
        self.assertIn("synchronize", checks)
        self.assertNotIn("does not start other workflows", checks)
        dispatch = GUIDE.split("### 2. Dispatch GitHub App", 1)[1].split("### 3.", 1)[0]
        self.assertIn("*Contents: Read and write*. Nothing else.", dispatch)
        self.assertNotIn("Pull requests", dispatch)
        self.assertIn("organization secrets", dispatch)

    def test_the_upgrade_from_flat_files_is_described(self) -> None:
        self.assertIn("## Upgrading from the Original Sync", GUIDE)
        self.assertIn("<owner>_<name>.yaml", GUIDE)

    def test_example_uids_are_valid(self) -> None:
        for uid in re.findall(r"^\s*(?:uid|- ref): (\S+)$", GUIDE, re.M):
            self.assertRegex(uid, sdp_sync.UID_PATTERN_TEXT)


class ReturnPathTests(unittest.TestCase):
    def test_it_is_design_only_and_answers_who_owns_it(self) -> None:
        self.assertIn("**Status**: Design only", RETURN_PATH)
        self.assertIn("## 4. Who Owns the Return Path", RETURN_PATH)
        self.assertIn("nobody central writes to a product repository", RETURN_PATH)
        self.assertFalse((TEMPLATES / "product-repo-requests.yml.tmpl").exists(), "the return path is not built in #195")


if __name__ == "__main__":
    unittest.main()
