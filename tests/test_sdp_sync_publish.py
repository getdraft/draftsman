"""#195 S2.4: the receiver opens or updates a pull request from draft-sync/<product> instead of pushing to main."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "framework" / "tools"))
sys.path.insert(0, str(ROOT))

import sdp_sync  # noqa: E402

REPOSITORY = "example-org/absence-service"
PRODUCT = "example-org__absence-service"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
BRANCH = "draft-sync/" + PRODUCT
RECEIVER = ROOT / "templates" / "github" / "drafting-table-receiver.yml.tmpl"
RESULT = {"status": "accepted", "message": "stored", "repository": REPOSITORY, "product": PRODUCT, "registration": "01M7SYNC03-PR01",
          "action": "upsert", "correlationId": "77-1", "commit": COMMIT, "written": [], "removed": []}


def done(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class FakeRunner:
    """Records every command; answers git status and gh from a script, everything else succeeds."""

    def __init__(self, status: str, open_prs: list | None = None, fail: dict | None = None) -> None:
        self.status, self.open_prs, self.fail, self.calls, self.bodies = status, open_prs or [], fail or {}, [], []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(list(args))
        key = " ".join(args[:3])
        if key in self.fail:
            return done(returncode=1, stderr=self.fail[key])
        if "--body-file" in args:
            self.bodies.append(Path(args[args.index("--body-file") + 1]).read_text(encoding="utf-8"))
        if args[:2] == ["git", "status"]:
            return done(self.status)
        if args[:3] == ["gh", "pr", "list"]:
            return done(json.dumps(self.open_prs))
        if args[:3] == ["gh", "pr", "create"]:
            return done("https://github.com/example-org/drafting-table/pull/42\n")
        return done()

    def commands(self, prefix: str) -> list[list[str]]:
        return [c for c in self.calls if " ".join(c).startswith(prefix)]


def status(*entries: str) -> str:
    return "".join(e + "\0" for e in entries)


CACHE_ONLY = status(f"?? .draft/external_sdps/{PRODUCT}/sdp.yaml", f" M .draft/external_sdps/{PRODUCT}/catalog/w.yaml",
                    " M docs/assets/draft-indexes.json", " M .draft/AI_INDEX.md", "?? .draft/framework/tools/__pycache__/x.cpython-311.pyc")


class PublishTests(unittest.TestCase):
    def test_a_first_sync_commits_to_the_product_branch_and_opens_a_pull_request(self) -> None:
        run = FakeRunner(CACHE_ONLY)
        outcome = sdp_sync.publish(RESULT, "main", run)
        self.assertEqual((outcome["status"], outcome["branch"], outcome["pullRequestAction"]), ("published", BRANCH, "opened"))
        self.assertEqual(outcome["pullRequest"], {"number": 42, "url": "https://github.com/example-org/drafting-table/pull/42"})
        self.assertEqual(run.commands("git checkout"), [["git", "checkout", "-B", BRANCH]])
        (add,) = run.commands("git add")
        self.assertEqual(add[:4], ["git", "add", "-A", "--"])
        self.assertNotIn(".draft/framework/tools/__pycache__/x.cpython-311.pyc", add, "bytecode is never committed")
        self.assertEqual(run.commands("git push"), [["git", "push", "--force", "origin", f"HEAD:refs/heads/{BRANCH}"]])
        (create,) = run.commands("gh pr create")
        self.assertEqual(create[3:7], ["--base", "main", "--head", BRANCH])
        self.assertIn(f"DRAFT sync: {REPOSITORY} at {COMMIT[:12]}", create)
        self.assertIn("77-1", run.bodies[0])
        self.assertIn(f"`.draft/external_sdps/{PRODUCT}/sdp.yaml`", run.bodies[0])

    def test_nothing_is_ever_pushed_to_the_default_branch(self) -> None:
        run = FakeRunner(CACHE_ONLY)
        sdp_sync.publish(RESULT, "main", run, auto_merge=True)
        for push in run.commands("git push"):
            self.assertEqual(push[-1], f"HEAD:refs/heads/{BRANCH}")
        self.assertFalse([c for c in run.calls if "main" in c and c[:2] == ["git", "push"]])

    def test_a_later_sync_updates_the_open_pull_request(self) -> None:
        run = FakeRunner(CACHE_ONLY, open_prs=[{"number": 7, "url": "https://github.com/example-org/drafting-table/pull/7"}])
        outcome = sdp_sync.publish(RESULT, "main", run)
        self.assertEqual((outcome["pullRequestAction"], outcome["pullRequest"]["number"]), ("updated", 7))
        self.assertEqual(run.commands("gh pr create"), [])
        (edit,) = run.commands("gh pr edit")
        self.assertEqual(edit[:4], ["gh", "pr", "edit", "7"])
        (listing,) = run.commands("gh pr list")
        self.assertEqual(listing[3:9], ["--head", BRANCH, "--base", "main", "--state", "open"])

    def test_no_changes_publishes_nothing(self) -> None:
        run = FakeRunner(status("?? .draft/framework/tools/__pycache__/sdp_sync.cpython-311.pyc"))
        outcome = sdp_sync.publish(RESULT, "main", run)
        self.assertEqual(outcome["status"], "unchanged")
        self.assertEqual([c[:2] for c in run.calls], [["git", "status"]])


class AutoMergeTests(unittest.TestCase):
    def test_auto_merge_is_requested_only_when_asked_and_confined(self) -> None:
        run = FakeRunner(CACHE_ONLY)
        outcome = sdp_sync.publish(RESULT, "main", run, auto_merge=True)
        self.assertEqual((outcome["confined"], outcome["autoMerge"]), (True, "enabled"))
        self.assertEqual(run.commands("gh pr merge"), [["gh", "pr", "merge", "42", "--auto", "--squash"]])

    def test_auto_merge_is_off_by_default(self) -> None:
        run = FakeRunner(CACHE_ONLY)
        self.assertEqual(sdp_sync.publish(RESULT, "main", run)["autoMerge"], "off")
        self.assertEqual(run.commands("gh pr merge"), [])

    def test_a_change_outside_the_product_cache_is_never_auto_merged(self) -> None:
        for extra in (" M catalog/engineering/systems/x.yaml", "?? .draft/external_sdps/example-org__payroll-service/sdp.yaml",
                      " M .draft/workspace.yaml", " M .github/workflows/x.yml"):
            with self.subTest(extra):
                run = FakeRunner(CACHE_ONLY + status(extra))
                outcome = sdp_sync.publish(RESULT, "main", run, auto_merge=True)
                self.assertFalse(outcome["confined"])
                self.assertIn("outside the product's cache folder", outcome["autoMerge"])
                self.assertEqual(run.commands("gh pr merge"), [])
                self.assertIn("Confined to the product's cache folder: no", run.bodies[0])

    def test_an_update_that_leaves_the_cache_turns_earlier_auto_merge_off(self) -> None:
        run = FakeRunner(CACHE_ONLY + status(" M catalog/x.yaml"), open_prs=[{"number": 7, "url": "https://github.com/o/r/pull/7"}])
        sdp_sync.publish(RESULT, "main", run, auto_merge=True)
        self.assertEqual(run.commands("gh pr merge"), [["gh", "pr", "merge", "7", "--disable-auto"]])

    def test_only_regenerated_indexes_do_not_count_as_confined(self) -> None:
        self.assertFalse(sdp_sync.is_confined(["docs/assets/draft-indexes.json"], PRODUCT, REPOSITORY))
        self.assertTrue(sdp_sync.is_confined([".draft/external_sdps/example-org_absence-service.yaml"], PRODUCT, REPOSITORY))
        self.assertFalse(sdp_sync.is_confined([f".draft/external_sdps/{PRODUCT}-evil/x.yaml"], PRODUCT, REPOSITORY))

    def test_a_failed_auto_merge_request_leaves_the_pull_request_open(self) -> None:
        run = FakeRunner(CACHE_ONLY, fail={"gh pr merge": "auto-merge is not allowed for this repository"})
        outcome = sdp_sync.publish(RESULT, "main", run, auto_merge=True)
        self.assertEqual((outcome["status"], outcome["autoMerge"]), ("published", "failed"))


class SafetyTests(unittest.TestCase):
    def test_only_accepted_valid_results_are_published(self) -> None:
        cases = [({**RESULT, "status": "rejected"}, "only an accepted sync"),
                 ({**RESULT, "product": "../../etc"}, "invalid product"),
                 ({**RESULT, "product": "example-org__payroll-service"}, "invalid product"),
                 ({**RESULT, "repository": "a/b; rm -rf /"}, "not a GitHub repository name"),
                 ({**RESULT, "commit": "$(id)"}, "not a git commit SHA")]
        for result, expected in cases:
            with self.subTest(expected):
                run = FakeRunner(CACHE_ONLY)
                with self.assertRaisesRegex(sdp_sync.SyncError, expected):
                    sdp_sync.publish(result, "main", run)
                self.assertEqual(run.calls, [])

    def test_the_base_branch_cannot_be_an_option_or_a_bad_ref(self) -> None:
        for base in ("--force", "-x", "a..b", "main/", "x.lock", "", "a b"):
            with self.subTest(base):
                with self.assertRaisesRegex(sdp_sync.SyncError, "not a branch name"):
                    sdp_sync.publish(RESULT, base, FakeRunner(CACHE_ONLY))

    def test_a_failing_git_or_gh_step_stops_with_its_reason(self) -> None:
        for key, expected in (("git push --force", "git push failed"), ("gh pr create", "gh pr create failed")):
            with self.subTest(key):
                run = FakeRunner(CACHE_ONLY, fail={key: "remote: denied"})
                with self.assertRaisesRegex(sdp_sync.SyncError, f"{expected} \\(exit 1\\): remote: denied"):
                    sdp_sync.publish(RESULT, "main", run)

    def test_renames_report_both_paths(self) -> None:
        run = FakeRunner(status(f"R  .draft/external_sdps/{PRODUCT}/new.yaml", f".draft/external_sdps/{PRODUCT}/old.yaml"))
        self.assertEqual(sdp_sync.changed_paths(run), [f".draft/external_sdps/{PRODUCT}/new.yaml", f".draft/external_sdps/{PRODUCT}/old.yaml"])

    def test_derived_paths_match_where_the_generators_write_in_a_workspace(self) -> None:
        # Run from <workspace>/.draft/framework/tools: generate_browser's WORKSPACE_ROOT is <workspace> (indexes go to
        # <workspace>/docs/assets/) and generate_ai_index writes to FRAMEWORK_ROOT.parent, i.e. <workspace>/.draft/.
        browser = (ROOT / "framework" / "tools" / "generate_browser.py").read_text(encoding="utf-8")
        ai_index = (ROOT / "framework" / "tools" / "generate_ai_index.py").read_text(encoding="utf-8")
        indexes = (ROOT / "framework" / "tools" / "generate_indexes.py").read_text(encoding="utf-8")
        self.assertIn('WORKSPACE_ROOT = REPO_ROOT.parent if REPO_ROOT.name == ".draft" else REPO_ROOT', browser)
        self.assertIn('OUTPUT_PATH = WORKSPACE_ROOT / "docs" / "index.html"', browser)
        self.assertIn('return OUTPUT_PATH.parent / "assets" / INDEX_OUTPUT_NAME', indexes)
        self.assertIn('OUTPUT_PATH = REPO_ROOT / "AI_INDEX.md"', ai_index)
        self.assertEqual(sdp_sync.DERIVED_PATHS, ("docs/assets/draft-indexes.json", ".draft/AI_INDEX.md"))


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class RealGitTests(unittest.TestCase):
    """The template's publish script against a real git repository and a fake gh on PATH."""

    def git(self, *args: str, cwd: Path) -> str:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.origin, self.ws = self.tmp / "origin.git", self.tmp / "central"
        self.git("init", "--bare", "-q", "-b", "main", str(self.origin), cwd=self.tmp)
        self.ws.mkdir()
        self.git("init", "-q", "-b", "main", cwd=self.ws)
        for key, value in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
            self.git("config", key, value, cwd=self.ws)
        (self.ws / "catalog").mkdir()
        (self.ws / "catalog" / "keep.yaml").write_text("type: x\n", encoding="utf-8")
        (self.ws / ".draft").mkdir()
        (self.ws / ".draft" / "framework").symlink_to(ROOT / "framework")
        (self.ws / ".gitignore").write_text(".draft/framework\n", encoding="utf-8")
        self.git("add", "-A", cwd=self.ws)
        self.git("commit", "-q", "-m", "init", cwd=self.ws)
        self.git("remote", "add", "origin", str(self.origin), cwd=self.ws)
        self.git("push", "-q", "origin", "main", cwd=self.ws)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        self.gh_log = self.tmp / "gh.log"
        (bin_dir / "gh").write_text(
            "#!/usr/bin/env bash\n"
            f'printf "%s\\n" "$*" >> "{self.gh_log}"\n'
            'case "$1 $2" in\n'
            '  "pr list") echo "[]" ;;\n'
            '  "pr create") echo "https://github.com/example-org/drafting-table/pull/5" ;;\n'
            "esac\n", encoding="utf-8")
        (bin_dir / "gh").chmod(0o755)
        self.env = {**os.environ, "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ.get('PATH', '')}",
                    "RUNNER_TEMP": str(self.tmp), "BASE_BRANCH": "main", "AUTO_MERGE": "TRUE", "GH_TOKEN": "x"}
        (self.tmp / "sdp-sync-result.json").write_text(json.dumps(RESULT), encoding="utf-8")

    def publish_script(self) -> str:
        workflow = yaml.safe_load(RECEIVER.read_text(encoding="utf-8"))
        (step,) = [s for s in workflow["jobs"]["sync_sdp"]["steps"] if s.get("name") == "Publish Sync Pull Request"]
        return step["run"]

    def test_the_template_script_pushes_the_product_branch_and_leaves_main_alone(self) -> None:
        cache = self.ws / ".draft" / "external_sdps" / PRODUCT
        cache.mkdir(parents=True)
        (cache / "sdp.yaml").write_text("type: software_deployment_pattern\n", encoding="utf-8")
        proc = subprocess.run(["bash", "-e", "-c", self.publish_script()], cwd=self.ws, env=self.env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("opened https://github.com/example-org/drafting-table/pull/5 (auto-merge enabled)", proc.stdout)
        heads = self.git("for-each-ref", "--format=%(refname)", "refs/heads", cwd=self.origin).split()
        self.assertEqual(sorted(heads), ["refs/heads/draft-sync/" + PRODUCT, "refs/heads/main"])
        self.assertEqual(self.git("log", "--format=%s", "main", cwd=self.origin).split("\n")[0], "init")
        files = self.git("show", "--name-only", "--format=", f"refs/heads/{BRANCH}", cwd=self.origin).split()
        self.assertEqual(files, [f".draft/external_sdps/{PRODUCT}/sdp.yaml"])
        self.assertIn(f"DRAFT sync: {REPOSITORY} at {COMMIT[:12]}", self.git("log", "-1", "--format=%s", f"refs/heads/{BRANCH}", cwd=self.origin))
        gh_calls = self.gh_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual([c.split()[:3] for c in gh_calls], [["pr", "list", "--head"], ["pr", "create", "--base"], ["pr", "merge", "5"]])
        result = json.loads((self.tmp / "sdp-sync-result.json").read_text())
        self.assertEqual((result["status"], result["publish"]["status"], result["publish"]["pullRequest"]["number"]), ("accepted", "published", 5))

    def test_a_resync_force_updates_the_branch_with_a_fresh_snapshot(self) -> None:
        cache = self.ws / ".draft" / "external_sdps" / PRODUCT
        cache.mkdir(parents=True)
        (cache / "sdp.yaml").write_text("type: software_deployment_pattern\nname: one\n", encoding="utf-8")
        script = self.publish_script()
        self.assertEqual(subprocess.run(["bash", "-e", "-c", script], cwd=self.ws, env=self.env, capture_output=True).returncode, 0)
        self.git("checkout", "-q", "main", cwd=self.ws)  # the next workflow run starts from a fresh default-branch checkout
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "sdp.yaml").write_text("type: software_deployment_pattern\nname: two\n", encoding="utf-8")
        self.assertEqual(subprocess.run(["bash", "-e", "-c", script], cwd=self.ws, env=self.env, capture_output=True).returncode, 0)
        log = self.git("log", "--format=%s", f"refs/heads/{BRANCH}", cwd=self.origin).strip().splitlines()
        self.assertEqual(len(log), 2, "one sync commit on top of main, not a growing history")
        self.assertIn("name: two", self.git("show", f"refs/heads/{BRANCH}:.draft/external_sdps/{PRODUCT}/sdp.yaml", cwd=self.origin))

    def test_a_rejected_result_fails_the_step_without_touching_git(self) -> None:
        (self.tmp / "sdp-sync-result.json").write_text(json.dumps({**RESULT, "status": "rejected"}), encoding="utf-8")
        proc = subprocess.run(["bash", "-e", "-c", self.publish_script()], cwd=self.ws, env=self.env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("only an accepted sync can be published", proc.stderr)
        self.assertEqual(self.git("branch", "--show-current", cwd=self.ws).strip(), "main")
        self.assertFalse(self.gh_log.exists())


if __name__ == "__main__":
    unittest.main()
