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


OUR = "c" * 40


class FakeRunner:
    """Records every command; answers git status and gh from a script, everything else succeeds."""

    def __init__(self, status: str, open_prs: list | None = None, fail: dict | None = None,
                 remote_tip: str | None = None, pr_head: str | None = None) -> None:
        self.status, self.open_prs, self.fail, self.calls, self.bodies = status, open_prs or [], fail or {}, [], []
        self.remote_tip, self.pr_head = remote_tip, pr_head

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(list(args))
        key = " ".join(args[:3])
        if key in self.fail:
            return done(returncode=1, stderr=self.fail[key])
        if "--body-file" in args:
            self.bodies.append(Path(args[args.index("--body-file") + 1]).read_text(encoding="utf-8"))
        if args[:2] == ["git", "status"]:
            return done(self.status)
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return done(OUR + "\n")
        if args[:2] == ["git", "ls-remote"]:
            return done(f"{OUR if self.remote_tip is None else self.remote_tip}\t{args[-1]}\n")
        if args[:3] == ["gh", "pr", "view"]:
            return done((OUR if self.pr_head is None else self.pr_head) + "\n")
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
        self.assertEqual(run.commands("git rev-parse"), [["git", "rev-parse", "HEAD"]])
        self.assertTrue(run.commands("git ls-remote"))
        self.assertEqual(run.commands("gh pr view")[0][:4], ["gh", "pr", "view", "42"])
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

    def test_a_tip_replaced_before_the_pull_request_is_opened_is_restored_and_rejected(self) -> None:
        attacker = "d" * 40
        for kwargs in ({"remote_tip": attacker}, {"pr_head": attacker}, {"remote_tip": attacker, "pr_head": attacker}):
            with self.subTest(kwargs):
                run = FakeRunner(CACHE_ONLY, **kwargs)
                with self.assertRaises(sdp_sync.SyncError) as caught:
                    sdp_sync.publish(RESULT, "main", run)
                self.assertIn("moved during publish", str(caught.exception))
                self.assertIn(OUR, str(caught.exception))
                self.assertIn(attacker, str(caught.exception))
                pushes = run.commands("git push")
                self.assertEqual(len(pushes), 2, "the receiver's commit is force-pushed again after the mismatch")
                self.assertTrue(all(push[-1] == f"HEAD:refs/heads/{BRANCH}" for push in pushes))

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
            '  "pr view") git rev-parse HEAD ;;\n'
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
        self.assertEqual([c.split()[:3] for c in gh_calls], [["pr", "list", "--head"], ["pr", "create", "--base"], ["pr", "view", "5"], ["pr", "merge", "5"]])
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


SHA = "a" * 40
HEAD = "draft-sync/" + PRODUCT
CENTRAL = "example-org/drafting-table"


APP = "draft-receiver"
BOT = "draft-receiver[bot]"


def pull(number: int, sha: str = SHA, head: str = HEAD, repo: str = CENTRAL, base: str = "main", state: str = "open",
         author: str = BOT) -> dict:
    return {"number": number, "state": state, "html_url": f"https://github.com/{CENTRAL}/pull/{number}",
            "user": {"login": author}, "head": {"ref": head, "sha": sha, "repo": {"full_name": repo}}, "base": {"ref": base}}


class ScriptedRunner:
    def __init__(self, replies: list[tuple[str, str, int, str]]) -> None:
        self.replies, self.calls = replies, []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(list(args))
        text = " ".join(args)
        matches = [item for item in self.replies if text.startswith(item[0])]
        if not matches:
            return done()
        _, stdout, code, stderr = max(matches, key=lambda item: len(item[0]))
        return done(stdout, code, stderr)


def confined_replies(pulls: list | None = None, diff: str = f"M\t.draft/external_sdps/{PRODUCT}/sdp.yaml\n",
                     sha: str = SHA, merge_code: int = 0, merge_stderr: str = "",
                     behind: int = 0, update_code: int = 0, update_stderr: str = "") -> list[tuple[str, str, int, str]]:
    return [
        ("git fetch", "", 0, ""),
        ("git rev-parse", sha + "\n", 0, ""),
        ("git diff", diff, 0, ""),
        (f"gh api -i repos/{CENTRAL}/commits/", json.dumps(pulls if pulls is not None else [pull(9)]), 0, ""),
        (f"gh api -i repos/{CENTRAL}/compare/", json.dumps({"behind_by": behind, "status": "behind" if behind else "ahead"}), 0, ""),
        (f"gh api -i --method PUT repos/{CENTRAL}/pulls/9/update-branch", "", update_code, update_stderr),
        (f"gh api -i --method PUT repos/{CENTRAL}/pulls/9/merge", "{\"merged\":true}\n", merge_code, merge_stderr),
    ]


def merge(run: ScriptedRunner, **kwargs: object) -> dict:
    values = {"auto_merge": True, "pusher": BOT, "app_slug": APP}
    values.update(kwargs)
    return sdp_sync.merge_sync_pull_request(CENTRAL, "main", SHA, HEAD, run, **values)  # type: ignore[arg-type]


class MergeTests(unittest.TestCase):
    def test_a_confined_same_repository_pull_request_is_squash_merged_at_that_sha(self) -> None:
        run = ScriptedRunner(confined_replies())
        outcome = merge(run)
        self.assertEqual(outcome["status"], "merged")
        self.assertEqual(outcome["pullRequest"]["number"], 9)
        self.assertIn(["gh", "api", "-i", "--method", "PUT", f"repos/{CENTRAL}/pulls/9/merge", "-f", "merge_method=squash", "-f", f"sha={SHA}"], run.calls)
        fetch = run.calls[0]
        self.assertEqual(fetch[:4], ["git", "fetch", "--no-tags", "origin"])
        self.assertIn(f"+refs/heads/{HEAD}:refs/remotes/origin/{HEAD}", fetch)

    def test_auto_merge_off_does_not_touch_git_or_the_api(self) -> None:
        run = ScriptedRunner([])
        outcome = merge(run, auto_merge=False)
        self.assertEqual(outcome["status"], "skipped")
        self.assertEqual(run.calls, [])

    def test_a_change_outside_the_cache_is_left_open(self) -> None:
        diff = f"M\t.draft/external_sdps/{PRODUCT}/sdp.yaml\nM\tcatalog/x.yaml\n"
        run = ScriptedRunner(confined_replies(diff=diff))
        outcome = merge(run)
        self.assertEqual(outcome["status"], "left-open")
        self.assertFalse([c for c in run.calls if "merge" in c and "--method" in c])

    def test_a_rename_out_of_the_cache_is_left_open(self) -> None:
        diff = f"R100\t.draft/external_sdps/{PRODUCT}/sdp.yaml\tcatalog/stolen.yaml\n"
        self.assertEqual(sdp_sync.paths_from_name_status(diff),
                         [f".draft/external_sdps/{PRODUCT}/sdp.yaml", "catalog/stolen.yaml"])
        run = ScriptedRunner(confined_replies(diff=diff))
        self.assertEqual(merge(run)["status"], "left-open")

    def test_a_fork_and_a_moved_head_are_not_merged(self) -> None:
        fork = ScriptedRunner(confined_replies(pulls=[pull(9, repo="attacker/drafting-table")]))
        self.assertEqual(merge(fork)["status"], "skipped")
        moved = ScriptedRunner(confined_replies(sha="b" * 40))
        self.assertEqual(merge(moved)["status"], "skipped")
        self.assertFalse([c for c in moved.calls if c[0] == "gh"])

    def test_only_a_409_head_move_is_skipped(self) -> None:
        raced = ScriptedRunner(confined_replies(merge_code=1, merge_stderr="HTTP/2.0 409 Conflict\nHead branch was modified. Review and try the merge again."))
        self.assertEqual(merge(raced)["status"], "skipped")
        sha_mismatch = ScriptedRunner(confined_replies(merge_code=1, merge_stderr="HTTP/2.0 409 Conflict\nSHA of the pull request's head must match"))
        self.assertEqual(merge(sha_mismatch)["status"], "skipped")
        ruleset = ScriptedRunner(confined_replies(merge_code=1, merge_stderr="HTTP/2.0 409 Conflict\nCommit message must match a given regex pattern."))
        with self.assertRaisesRegex(sdp_sync.SyncError, "must match"):
            merge(ruleset)
        blocked = ScriptedRunner(confined_replies(merge_code=1, merge_stderr="HTTP/2.0 405 Method Not Allowed\nAt least 1 approving review is required"))
        with self.assertRaisesRegex(sdp_sync.SyncError, "approving review"):
            merge(blocked)
        self.assertFalse(sdp_sync._head_moved(405, "SHA of the pull request's head must match"))
        self.assertTrue(sdp_sync._head_moved(409, "Head branch was modified"))
        self.assertFalse(sdp_sync._head_moved(422, "Validation Failed"))

    def test_update_branch_422_for_a_moved_head_is_skipped(self) -> None:
        self.assertTrue(sdp_sync._head_moved(422, "expected_head_sha did not match the current head"))
        moved = ScriptedRunner(confined_replies(
            behind=2, update_code=1,
            update_stderr="HTTP/2.0 422 Unprocessable Entity\nexpected_head_sha did not match the current head"))
        self.assertEqual(merge(moved)["status"], "skipped")
        other = ScriptedRunner(confined_replies(behind=2, update_code=1, update_stderr="HTTP/2.0 422 Unprocessable Entity\nValidation Failed"))
        with self.assertRaisesRegex(sdp_sync.SyncError, "Validation Failed"):
            merge(other)

    def test_a_bad_sha_or_two_pull_requests_are_refused(self) -> None:
        with self.assertRaisesRegex(sdp_sync.SyncError, "not a full git commit SHA"):
            sdp_sync.merge_sync_pull_request(CENTRAL, "main", "abc", HEAD, ScriptedRunner([]), auto_merge=True, pusher=BOT, app_slug=APP)
        both = ScriptedRunner(confined_replies(pulls=[pull(9), pull(10)]))
        with self.assertRaisesRegex(sdp_sync.SyncError, "more than one"):
            merge(both)

    def test_the_pusher_and_the_pull_request_author_must_be_the_receiver_app(self) -> None:
        quiet = ScriptedRunner([])
        with self.assertRaisesRegex(sdp_sync.SyncError, "not draft-receiver\\[bot\\]"):
            merge(quiet, pusher="dispatch-app[bot]")
        self.assertEqual(quiet.calls, [])
        stranger = ScriptedRunner(confined_replies(pulls=[pull(9, author="octocat")]))
        with self.assertRaisesRegex(sdp_sync.SyncError, "opened by octocat"):
            merge(stranger)
        self.assertFalse([c for c in stranger.calls if "--method" in c])

    def test_a_pull_request_behind_its_base_is_updated_instead_of_merged(self) -> None:
        run = ScriptedRunner(confined_replies(behind=3))
        outcome = merge(run)
        self.assertEqual(outcome["status"], "updated")
        self.assertIn(["gh", "api", "-i", "--method", "PUT", f"repos/{CENTRAL}/pulls/9/update-branch", "-f", f"expected_head_sha={SHA}"], run.calls)
        self.assertFalse([c for c in run.calls if c[-4:] == ["-f", "merge_method=squash", "-f", f"sha={SHA}"]])

    def test_the_legacy_flat_file_may_only_be_deleted_on_the_merge_path(self) -> None:
        legacy = f".draft/external_sdps/{REPOSITORY.replace('/', '_')}.yaml"
        cache = f".draft/external_sdps/{PRODUCT}/sdp.yaml"
        self.assertEqual(f".draft/external_sdps/{'foo/bar_baz'.replace('/', '_')}.yaml",
                         f".draft/external_sdps/{'foo_bar/baz'.replace('/', '_')}.yaml")
        self.assertTrue(sdp_sync.is_confined([legacy], PRODUCT, REPOSITORY), "publish still treats the legacy file as confined")
        self.assertTrue(sdp_sync.merge_confined([("M", cache), ("D", legacy)], PRODUCT, REPOSITORY))
        self.assertFalse(sdp_sync.merge_confined([("M", cache), ("A", legacy)], PRODUCT, REPOSITORY))
        self.assertFalse(sdp_sync.merge_confined([("M", cache), ("M", legacy)], PRODUCT, REPOSITORY))
        deleted = ScriptedRunner(confined_replies(diff=f"M\t{cache}\nD\t{legacy}\n"))
        self.assertEqual(merge(deleted)["status"], "merged")
        added = ScriptedRunner(confined_replies(diff=f"M\t{cache}\nA\t{legacy}\n"))
        self.assertEqual(merge(added)["status"], "left-open")


if __name__ == "__main__":
    unittest.main()
