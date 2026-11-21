"""#195 S2.5: every receiver outcome is recorded, and the product repository's run fails with the receiver's message."""
from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "framework" / "tools"))
sys.path.insert(0, str(ROOT))

import sdp_sync  # noqa: E402
from tests import sdp_sync_identity as identity  # noqa: E402

REPOSITORY = "example-org/absence-service"
PRODUCT = "example-org__absence-service"
CENTRAL = "example-org/drafting-table"
CID = "77-1"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
TEMPLATES = ROOT / "templates" / "github"
TOOL = ROOT / "framework" / "tools" / "sdp_sync.py"
ACCEPTED = {"status": "accepted", "message": "stored", "repository": REPOSITORY, "product": PRODUCT, "registration": "01M7SYNC03-PR01",
            "action": "upsert", "correlationId": CID, "commit": COMMIT, "written": [], "removed": [], "identityVerified": True}
PUBLISHED = {"status": "published", "pullRequestAction": "opened", "autoMerge": "off",
             "pullRequest": {"number": 5, "url": "https://github.com/example-org/drafting-table/pull/5"}}
VALIDATE_LOG = f"""FAIL /ws/.draft/external_sdps/{PRODUCT}/sdp.yaml
PASS catalog/x.yaml

Validation failures:
- /ws/catalog/other.yaml: a central problem
- /ws/.draft/external_sdps/{PRODUCT}/sdp.yaml: Add required field 'name'

Validation warnings:
- /ws/catalog/x.yaml: a warning that is not a failure
"""


def done(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode, stdout, "")


class OutcomeTests(unittest.TestCase):
    def test_an_accepted_and_published_sync_reports_its_pull_request(self) -> None:
        outcome = sdp_sync.final_outcome({**ACCEPTED, "publish": PUBLISHED}, None, "success")
        self.assertEqual(outcome["status"], "accepted")
        self.assertEqual(outcome["message"], "opened pull request https://github.com/example-org/drafting-table/pull/5")
        self.assertEqual(outcome["pullRequest"]["number"], 5)

    def test_an_unchanged_sync_is_accepted(self) -> None:
        outcome = sdp_sync.final_outcome({**ACCEPTED, "publish": {"status": "unchanged", "pullRequest": None}}, None, "success")
        self.assertEqual((outcome["status"], outcome["message"]), ("accepted", "accepted; the central workspace already matches this sync"))

    def test_a_rejection_carries_the_receivers_reason(self) -> None:
        result = {**ACCEPTED, "status": "rejected", "message": "unresolved references: .draft/sdp.yaml references 01M7SYNC0F-PC98"}
        outcome = sdp_sync.final_outcome(result, None, "failure")
        self.assertEqual((outcome["status"], outcome["message"]), ("rejected", result["message"]))

    def test_a_validation_failure_lists_the_failures_with_the_products_first(self) -> None:
        outcome = sdp_sync.final_outcome(ACCEPTED, None, "failure", VALIDATE_LOG, Path("/ws"))
        self.assertEqual(outcome["status"], "failed")
        self.assertIn("does not validate with this sync (2 failure(s))", outcome["message"])
        self.assertEqual(outcome["details"], [f".draft/external_sdps/{PRODUCT}/sdp.yaml: Add required field 'name'",
                                              "catalog/other.yaml: a central problem"])

    def test_a_failed_publish_is_a_failure(self) -> None:
        outcome = sdp_sync.final_outcome({**ACCEPTED, "publish": {"status": "failed", "message": "gh pr create failed (exit 1)"}}, None, "failure")
        self.assertEqual(outcome["status"], "failed")
        self.assertIn("opening its pull request failed: gh pr create failed", outcome["message"])

    def test_a_run_that_stopped_before_receive_is_a_failure_named_from_the_payload(self) -> None:
        outcome = sdp_sync.final_outcome(None, {"repository": REPOSITORY, "correlationId": CID, "commit": COMMIT}, "failure")
        self.assertEqual((outcome["status"], outcome["repository"], outcome["correlationId"]), ("failed", REPOSITORY, CID))
        self.assertFalse(outcome["identityVerified"])

    def test_an_accepted_run_with_a_later_unknown_failure_says_so(self) -> None:
        outcome = sdp_sync.final_outcome(ACCEPTED, None, "cancelled")
        self.assertEqual(outcome["status"], "failed")
        self.assertIn("job cancelled", outcome["message"])

    def test_the_summary_names_the_outcome_and_links(self) -> None:
        outcome = sdp_sync.final_outcome(ACCEPTED, None, "failure", VALIDATE_LOG, Path("/ws"), "https://github.com/x/y/actions/runs/9")
        text = sdp_sync.summary_markdown(outcome)
        self.assertTrue(text.startswith("## DRAFT SDP sync: Failed"))
        self.assertIn("Central receiver run: https://github.com/x/y/actions/runs/9", text)
        self.assertIn("Add required field 'name'", text)

    def test_receive_marks_whether_the_sender_was_verified(self) -> None:
        central = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(central, ignore_errors=True))
        __import__("shutil").copytree(ROOT / "tests" / "fixtures" / "sdp_sync" / "central_workspace", central, dirs_exist_ok=True)
        sdp = (ROOT / "tests" / "fixtures" / "sdp_sync" / "product_repo" / ".draft" / "sdp.yaml").read_text(encoding="utf-8")
        payload = {"format": sdp_sync.PAYLOAD_FORMAT, "repository": REPOSITORY, "commit": COMMIT, "ref": "refs/heads/main",
                   "action": "upsert", "correlationId": CID, "files": {".draft/sdp.yaml": sdp}}
        self.assertTrue(identity.receive(central, payload).as_json()["identityVerified"])
        late = identity.receive(central, {**payload, "files": {".draft/sdp.yaml": sdp + "  - ref: 01M7SYNC0F-PC98\n"}})
        self.assertEqual((late.status, late.identity_verified), ("rejected", True), "a rejection after the identity check is reported back")
        forged = identity.receive(central, payload, repository="example-org/other")
        self.assertEqual((forged.status, forged.identity_verified), ("rejected", False))


class StoreTests(unittest.TestCase):
    class Runner:
        def __init__(self, branch_exists: bool = True, file_exists: bool = False) -> None:
            self.calls, self.branch_exists, self.file_exists = [], branch_exists, file_exists

        def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
            self.calls.append(args)
            joined = " ".join(args)
            if "git/ref/heads/draft-sync-results" in joined:
                return done("abc\n", 0 if self.branch_exists else 1)
            if "git/ref/heads/main" in joined:
                return done("f00d\n")
            if "--method PUT" in joined and self.file_exists and "sha=" not in joined:
                return done("", 1)
            if "contents/" in joined and "--jq" in args:
                return done("oldsha\n")
            return done()

    def outcome(self, **kw: object) -> dict:
        return {**sdp_sync.final_outcome({**ACCEPTED, "publish": PUBLISHED}, None, "success"), **kw}

    def test_the_outcome_is_written_to_the_results_branch_by_correlation_id(self) -> None:
        run = self.Runner()
        path = sdp_sync.store_outcome(self.outcome(), CENTRAL, "main", run)
        self.assertEqual(path, f"results/{PRODUCT}/{CID}.json")
        (put,) = [c for c in run.calls if "PUT" in c]
        self.assertEqual(put[:5], ["gh", "api", "--method", "PUT", f"repos/{CENTRAL}/contents/results/{PRODUCT}/{CID}.json"])
        self.assertIn("branch=draft-sync-results", put)
        content = next(a for a in put if a.startswith("content="))[len("content="):]
        self.assertEqual(json.loads(base64.b64decode(content))["status"], "accepted")

    def test_the_results_branch_is_created_from_the_default_branch(self) -> None:
        run = self.Runner(branch_exists=False)
        sdp_sync.store_outcome(self.outcome(), CENTRAL, "main", run)
        (create,) = [c for c in run.calls if "POST" in c]
        self.assertEqual(create[-4:], ["-f", "ref=refs/heads/draft-sync-results", "-f", "sha=f00d"])

    def test_a_rerun_updates_the_existing_result(self) -> None:
        run = self.Runner(file_exists=True)
        sdp_sync.store_outcome(self.outcome(), CENTRAL, "main", run)
        puts = [c for c in run.calls if "PUT" in c]
        self.assertEqual(len(puts), 2)
        self.assertIn("sha=oldsha", puts[1])

    def test_an_unverified_sender_never_gets_a_result_file(self) -> None:
        run = self.Runner()
        with self.assertRaisesRegex(sdp_sync.SyncError, "identity was not verified"):
            sdp_sync.store_outcome(self.outcome(identityVerified=False), CENTRAL, "main", run)
        self.assertEqual(run.calls, [])

    def test_bad_correlation_ids_and_repositories_are_refused(self) -> None:
        for kw, expected in (({"correlationId": "../x"}, "correlation id"), ({"repository": "a/b; x"}, "not a GitHub repository name")):
            with self.subTest(kw):
                with self.assertRaisesRegex(sdp_sync.SyncError, expected):
                    sdp_sync.store_outcome(self.outcome(**kw), CENTRAL, "main", self.Runner())


class FakeContents:
    """A fake GitHub contents API: the result appears after a few polls."""

    def __init__(self, outcome: dict | None, appear_after: int = 2, error: Exception | None = None) -> None:
        self.outcome, self.appear_after, self.error, self.paths = outcome, appear_after, error, []

    def __call__(self, path: str) -> bytes | None:
        self.paths.append(path)
        if self.error:
            raise self.error
        if self.outcome is None or len(self.paths) <= self.appear_after:
            return None
        return json.dumps(self.outcome).encode()


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class AwaitTests(unittest.TestCase):
    def wait(self, fetch: FakeContents, timeout: float = 120) -> dict:
        clock = Clock()
        return sdp_sync.await_result(REPOSITORY, CID, fetch, timeout=timeout, interval=15, sleep=clock.sleep, clock=clock)

    def test_the_sender_polls_its_correlation_id_until_the_result_appears(self) -> None:
        outcome = sdp_sync.final_outcome({**ACCEPTED, "publish": PUBLISHED}, None, "success")
        fetch = FakeContents(outcome, appear_after=3)
        self.assertEqual(self.wait(fetch)["status"], "accepted")
        self.assertEqual(fetch.paths, [f"results/{PRODUCT}/{CID}.json"] * 4)

    def test_a_result_for_another_sync_is_ignored(self) -> None:
        stale = {**sdp_sync.final_outcome(ACCEPTED, None, "failure"), "correlationId": "76-1"}
        with self.assertRaisesRegex(sdp_sync.SyncError, "no result from the central receiver after 60 seconds"):
            self.wait(FakeContents(stale, appear_after=0), timeout=60)

    def test_a_timeout_explains_what_to_check(self) -> None:
        with self.assertRaisesRegex(sdp_sync.SyncError, "queued behind other syncs"):
            self.wait(FakeContents(None), timeout=30)

    def test_a_permission_error_stops_at_once(self) -> None:
        fetch = FakeContents(None, error=sdp_sync.SyncError("reading the central result failed with HTTP 403; ..."))
        with self.assertRaisesRegex(sdp_sync.SyncError, "HTTP 403"):
            self.wait(fetch)
        self.assertEqual(len(fetch.paths), 1)

    def test_the_fetcher_reads_the_results_branch_and_treats_404_as_not_yet(self) -> None:
        requests = []

        def opener(request, timeout):
            requests.append((request.full_url, request.headers.get("Authorization"), request.headers.get("Accept")))
            if len(requests) == 1:
                raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)
            return io.BytesIO(b'{"status": "accepted"}')

        fetch = sdp_sync.github_contents_fetcher(CENTRAL, "app-token", opener)
        self.assertIsNone(fetch(f"results/{PRODUCT}/{CID}.json"))
        self.assertEqual(fetch(f"results/{PRODUCT}/{CID}.json"), b'{"status": "accepted"}')
        self.assertEqual(requests[0], (f"https://api.github.com/repos/{CENTRAL}/contents/results/{PRODUCT}/{CID}.json?ref=draft-sync-results",
                                       "Bearer app-token", "application/vnd.github.raw+json"))

        def forbidden(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)

        with self.assertRaisesRegex(sdp_sync.SyncError, "HTTP 403; the App token needs contents access"):
            sdp_sync.github_contents_fetcher(CENTRAL, "t", forbidden)(f"results/{PRODUCT}/{CID}.json")

    def test_annotations_cannot_start_another_workflow_command(self) -> None:
        self.assertEqual(sdp_sync.annotation("bad\n::set-output name=x::y 100%"), "bad%0A::set-output name=x::y 100%25")


class CliTests(unittest.TestCase):
    def run_tool(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, check=False,
                              env={**os.environ, **(env or {})})

    def test_report_writes_a_job_summary_for_a_run_that_never_received(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        summary = tmp / "summary.md"
        event = tmp / "event.json"
        event.write_text(json.dumps({"client_payload": {"repository": REPOSITORY, "correlationId": CID}}), encoding="utf-8")
        out = self.run_tool("report", "--payload", str(event), "--result", str(tmp / "missing.json"), "--job-status", "failure",
                            "--base", "main", "--summary", str(summary),
                            env={"GITHUB_REPOSITORY": CENTRAL, "GITHUB_RUN_ID": "9", "GITHUB_SERVER_URL": "https://github.com"})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("identity was not verified", out.stdout)
        text = summary.read_text(encoding="utf-8")
        self.assertIn("## DRAFT SDP sync: Failed", text)
        self.assertIn(f"https://github.com/{CENTRAL}/actions/runs/9", text)

    def test_await_result_without_a_token_fails_with_an_annotation(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "GH_TOKEN"}
        out = subprocess.run([sys.executable, str(TOOL), "await-result", "--central-repository", CENTRAL, "--repository", REPOSITORY,
                              "--correlation-id", CID], capture_output=True, text=True, check=False, env=env)
        self.assertEqual(out.returncode, 1)
        self.assertIn("::error title=DRAFT sync::GH_TOKEN is not set", out.stdout)


class TemplateTests(unittest.TestCase):
    def steps(self, name: str) -> list[dict]:
        workflow = yaml.safe_load((TEMPLATES / name).read_text(encoding="utf-8"))
        return [s for job in workflow["jobs"].values() for s in job["steps"]]

    def test_the_receiver_always_reports_last(self) -> None:
        steps = self.steps("drafting-table-receiver.yml.tmpl")
        report = steps[-1]
        self.assertEqual((report["name"], report["if"]), ("Report Sync Result", "always()"))
        self.assertEqual(report["env"]["JOB_STATUS"], "${{ job.status }}")
        self.assertIn("sdp_sync.py report", report["run"])
        self.assertIn('--summary "$GITHUB_STEP_SUMMARY"', report["run"])
        (validate,) = [s for s in steps if s.get("name") == "Validate Workspace Architecture"]
        self.assertEqual(validate["shell"], "bash", "an explicit shell: bash adds pipefail (the default is bash -e), so tee keeps the failure")
        self.assertIn('tee "$RUNNER_TEMP/validate.log"', validate["run"])

    def test_the_sender_waits_for_its_correlation_id_with_the_dispatch_token(self) -> None:
        steps = self.steps("product-repo-sync.yml.tmpl")
        wait = steps[-1]
        self.assertEqual(wait["name"], "Await Central Result")
        self.assertEqual(wait["env"]["GH_TOKEN"], "${{ steps.generate_token.outputs.token }}")
        (pack,) = [s for s in steps if s.get("name") == "Pack SDP Payload"]
        self.assertEqual(wait["env"]["CORRELATION_ID"], pack["env"]["CORRELATION_ID"])
        self.assertEqual(wait["env"]["CENTRAL_REPOSITORY"], pack["env"]["CENTRAL_REPOSITORY"])
        self.assertIn("sdp_sync.py await-result", wait["run"])

    def test_no_new_permissions(self) -> None:
        sender = yaml.safe_load((TEMPLATES / "product-repo-sync.yml.tmpl").read_text(encoding="utf-8"))
        receiver = yaml.safe_load((TEMPLATES / "drafting-table-receiver.yml.tmpl").read_text(encoding="utf-8"))
        self.assertEqual(sender["jobs"]["transmit_sdp"]["permissions"], {"id-token": "write", "contents": "read"})
        self.assertEqual(receiver["permissions"], {"contents": "write", "pull-requests": "write"})


if __name__ == "__main__":
    unittest.main()
