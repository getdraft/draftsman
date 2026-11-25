"""#195 S1.2: the sync workflow templates call sdp_sync.py and never put a payload value in script text."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates" / "github"
SENDER = TEMPLATES / "product-repo-sync.yml.tmpl"
RECEIVER = TEMPLATES / "drafting-table-receiver.yml.tmpl"
FIXTURES = ROOT / "tests" / "fixtures" / "sdp_sync"
EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.S)
sys.path.insert(0, str(ROOT))
from tests import sdp_sync_identity as identity  # noqa: E402


def names_index(path: Path, name: str) -> int:
    return [s.get("name") for s in steps(path)].index(name)


def steps(path: Path) -> list[dict]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


def step(path: Path, name: str) -> dict:
    (found,) = [s for s in steps(path) if s.get("name") == name]
    return found


class NoExpressionsInScriptsTests(unittest.TestCase):
    def test_no_run_step_contains_an_expression(self) -> None:
        for path in (SENDER, RECEIVER, MERGE):
            for s in steps(path):
                if "run" in s:
                    with self.subTest(template=path.name, step=s.get("name")):
                        self.assertIsNone(EXPRESSION.search(s["run"]), "pass values through env: or files, not ${{ }} in run:")

    def test_no_template_reads_the_payload_through_an_expression(self) -> None:
        for path in (SENDER, RECEIVER, MERGE):
            with self.subTest(path.name):
                self.assertNotIn("client_payload", "".join(EXPRESSION.findall(path.read_text(encoding="utf-8"))))

    def test_the_old_inline_payload_handling_is_gone(self) -> None:
        sender, receiver = SENDER.read_text(encoding="utf-8"), RECEIVER.read_text(encoding="utf-8")
        self.assertNotIn("jq -s -R", sender)
        self.assertNotIn("toJson(", receiver)
        self.assertNotIn("echo '", receiver)


class WiringTests(unittest.TestCase):
    def test_sender_packs_with_the_framework_tool_and_dispatches_the_file(self) -> None:
        tool = step(SENDER, "Checkout the DRAFT sync tool")
        self.assertEqual((tool["uses"], tool["with"]["repository"], tool["with"]["path"]),
                         ("actions/checkout@v4", "getdraft/draftsman", ".draft-sync-tool"))
        pack = step(SENDER, "Pack SDP Payload")
        self.assertIn(".draft-sync-tool/framework/tools/sdp_sync.py pack", pack["run"])
        self.assertEqual(set(pack["env"]), {"REPOSITORY", "COMMIT", "REF", "CORRELATION_ID", "CENTRAL_REPOSITORY"})
        self.assertIn('--central-repository "$CENTRAL_REPOSITORY"', pack["run"])
        dispatch = step(SENDER, "Dispatch SDP Payload to Central Workspace")
        self.assertIn('--slurpfile payload "$RUNNER_TEMP/sdp-payload.json"', dispatch["run"])
        self.assertIn("GH_TOKEN", dispatch["env"])
        self.assertIn("--fail-with-body", dispatch["run"])

    def test_the_app_token_step_is_unchanged(self) -> None:
        token = step(SENDER, "Generate Ephemeral App Token for Central Workspace")
        self.assertEqual(token["uses"], APP_TOKEN_ACTION)
        self.assertEqual(token["with"]["repositories"], "${{ secrets.DRAFT_CENTRAL_REPO_NAME }}")

    def test_sender_runs_when_the_sdp_or_the_product_catalog_changes(self) -> None:
        sender = yaml.safe_load(SENDER.read_text(encoding="utf-8"))
        trigger = sender.get("on", sender.get(True))  # YAML 1.1 reads a bare `on:` key as True
        self.assertEqual(trigger["push"]["paths"], [".draft/sdp.yaml", ".draft/catalog/**"])

    def test_sender_requests_an_oidc_token_for_the_receivers_audience(self) -> None:
        sender = yaml.safe_load(SENDER.read_text(encoding="utf-8"))
        self.assertEqual(sender["jobs"]["transmit_sdp"]["permissions"]["id-token"], "write")
        sent = step(SENDER, "Pack SDP Payload")["env"]["CENTRAL_REPOSITORY"]
        received = step(RECEIVER, "Store Decentralized SDP Payload")
        self.assertEqual(sent, "${{ github.repository_owner }}/${{ secrets.DRAFT_CENTRAL_REPO_NAME }}")
        self.assertEqual(received["env"]["CENTRAL_REPOSITORY"], "${{ github.repository }}")
        self.assertIn('--central-repository "$CENTRAL_REPOSITORY"', received["run"])
        self.assertNotIn("--jwks", received["run"], "the receiver must use GitHub's published keys")
        receiver = yaml.safe_load(RECEIVER.read_text(encoding="utf-8"))
        self.assertNotIn("id-token", json.dumps(receiver.get("permissions", {})), "the receiver needs no OIDC permission")

    def test_receiver_publishes_a_pull_request_instead_of_pushing(self) -> None:
        text = RECEIVER.read_text(encoding="utf-8")
        receiver = yaml.safe_load(text)
        self.assertNotIn("git-auto-commit", text)
        self.assertNotIn("git push", text)
        self.assertEqual(receiver["permissions"], {"contents": "write", "pull-requests": "write"})
        self.assertEqual(receiver["concurrency"], {"group": "draft-sdp-sync", "cancel-in-progress": False})
        names = [s.get("name") for s in steps(RECEIVER)]
        self.assertEqual(names[-2:], ["Publish Sync Pull Request", "Report Sync Result"])
        self.assertLess(names.index("Regenerate Machine Indexes & AI Map"), names.index("Publish Sync Pull Request"))
        publish = step(RECEIVER, "Publish Sync Pull Request")
        token = "${{ steps.receiver_token.outcome == 'success' && steps.receiver_token.outputs.token || github.token }}"
        self.assertEqual(publish["env"], {"GH_TOKEN": token, "BASE_BRANCH": "${{ github.event.repository.default_branch }}",
                                          "AUTO_MERGE": "${{ steps.receiver_token.outcome == 'success' && 'false' || vars.DRAFT_SYNC_AUTO_MERGE }}"})
        self.assertIn("sdp_sync.py publish", publish["run"])
        self.assertIn('--result "$RUNNER_TEMP/sdp-sync-result.json"', publish["run"])

    def test_receiver_receives_from_the_event_file_then_validates(self) -> None:
        names = [s.get("name") for s in steps(RECEIVER)]
        receive = step(RECEIVER, "Store Decentralized SDP Payload")
        self.assertIn('sdp_sync.py receive', receive["run"])
        self.assertIn('--payload "$GITHUB_EVENT_PATH"', receive["run"])
        self.assertLess(names.index("Store Decentralized SDP Payload"), names.index("Validate Workspace Architecture"))


# A successful mint uses the App token. A skipped or failed mint keeps github.token, and checkout still runs.
RECEIVER_TOKEN = "${{ steps.receiver_token.outcome == 'success' && steps.receiver_token.outputs.token || github.token }}"
MERGE = TEMPLATES / "drafting-table-sync-merge.yml.tmpl"
# v1.12.0 of actions/create-github-app-token. The moving @v1 tag is not used: the step receives the App private key.
APP_TOKEN_ACTION = "actions/create-github-app-token@d72941d797fd3113feb6b93fd0dec494b13a2547"
APP_TOKEN_VERSION = "v1.12.0"


class ReceiverAppTokenTests(unittest.TestCase):
    """Opt-in receiver App: mint before checkout, and use that token for the force-push and for gh."""

    def test_the_token_step_is_conditional_and_runs_before_checkout(self) -> None:
        names = [s.get("name") for s in steps(RECEIVER)]
        self.assertLess(names.index("Detect Receiver App Credentials"), names.index("Mint Receiver App Token"))
        self.assertLess(names.index("Mint Receiver App Token"), names.index("Checkout Workspace"))
        detect = step(RECEIVER, "Detect Receiver App Credentials")
        self.assertEqual(detect["id"], "receiver_app")
        self.assertEqual(detect["env"], {
            "RECEIVER_APP_ID": "${{ secrets.DRAFT_RECEIVER_APP_ID }}",
            "RECEIVER_APP_PRIVATE_KEY": "${{ secrets.DRAFT_RECEIVER_APP_PRIVATE_KEY }}",
        })
        self.assertNotIn("${{", detect["run"])
        token = step(RECEIVER, "Mint Receiver App Token")
        self.assertEqual(token["id"], "receiver_token")
        self.assertEqual(token["if"], "steps.receiver_app.outputs.present == 'true'")
        self.assertEqual(token["uses"], APP_TOKEN_ACTION)
        self.assertEqual(token["with"], {
            "app-id": "${{ secrets.DRAFT_RECEIVER_APP_ID }}",
            "private-key": "${{ secrets.DRAFT_RECEIVER_APP_PRIVATE_KEY }}",
            "repositories": "${{ github.event.repository.name }}",
            "permission-contents": "write",
            "permission-pull-requests": "write",
        })

    def test_python_setup_and_pyyaml_still_run_after_a_failed_token_mint(self) -> None:
        setup = step(RECEIVER, "Set up Python")
        install = step(RECEIVER, "Install Dependencies")
        self.assertEqual(setup["if"], "always()")
        self.assertEqual(install["if"], "always()")
        self.assertIn("pyyaml", install["run"].lower())
        names = [s.get("name") for s in steps(RECEIVER)]
        self.assertLess(names.index("Checkout Workspace"), names.index("Set up Python"))
        self.assertLess(names.index("Install Dependencies"), names.index("Report Sync Result"))
        self.assertEqual(step(RECEIVER, "Report Sync Result")["if"], "always()")

    def test_the_app_token_action_is_pinned_in_the_receiver_and_the_dispatch_templates(self) -> None:
        for path, step_name in (
            (RECEIVER, "Mint Receiver App Token"),
            (MERGE, "Mint Receiver App Token"),
            (SENDER, "Generate Ephemeral App Token for Central Workspace"),
        ):
            with self.subTest(template=path.name):
                self.assertEqual(step(path, step_name)["uses"], APP_TOKEN_ACTION)
                self.assertNotIn("actions/create-github-app-token@v1\n", path.read_text(encoding="utf-8"))
                lines = path.read_text(encoding="utf-8").splitlines()
                uses_at = [index for index, line in enumerate(lines) if line.strip() == f"uses: {APP_TOKEN_ACTION}"]
                self.assertEqual(len(uses_at), 1)
                self.assertIn(APP_TOKEN_VERSION, lines[uses_at[0] - 1])

    def test_checkout_publish_and_report_share_the_app_token_with_a_github_token_fallback(self) -> None:
        checkout = step(RECEIVER, "Checkout Workspace")
        self.assertEqual(checkout["if"], "always()")
        self.assertEqual(checkout["with"]["token"], RECEIVER_TOKEN)
        self.assertIs(checkout["with"]["persist-credentials"], True)
        self.assertLess(names_index(RECEIVER, "Mint Receiver App Token"), names_index(RECEIVER, "Checkout Workspace"))
        self.assertEqual(step(RECEIVER, "Publish Sync Pull Request")["env"]["GH_TOKEN"], RECEIVER_TOKEN)
        self.assertEqual(step(RECEIVER, "Report Sync Result")["env"]["GH_TOKEN"], RECEIVER_TOKEN)
        self.assertIn("github.token", RECEIVER_TOKEN)
        receiver = yaml.safe_load(RECEIVER.read_text(encoding="utf-8"))
        self.assertEqual(receiver["permissions"], {"contents": "write", "pull-requests": "write"})

    def test_product_repos_keep_the_dispatch_app(self) -> None:
        sender = SENDER.read_text(encoding="utf-8")
        self.assertNotIn("DRAFT_RECEIVER_APP_ID", sender)
        self.assertNotIn("DRAFT_RECEIVER_APP_PRIVATE_KEY", sender)
        token = step(SENDER, "Generate Ephemeral App Token for Central Workspace")
        self.assertEqual(token["with"]["app-id"], "${{ secrets.DRAFT_APP_ID }}")
        self.assertEqual(token["with"]["private-key"], "${{ secrets.DRAFT_APP_PRIVATE_KEY }}")

    def test_detect_script_reports_both_modes_and_does_not_print_the_key(self) -> None:
        script = step(RECEIVER, "Detect Receiver App Credentials")["run"]
        key = "receiver-key-should-not-appear"
        cases = (
            ({}, "present=false\n", 0),
            ({"RECEIVER_APP_ID": "12345", "RECEIVER_APP_PRIVATE_KEY": key}, "present=true\n", 0),
            ({"RECEIVER_APP_ID": "12345"}, None, 1),
            ({"RECEIVER_APP_PRIVATE_KEY": key}, None, 1),
        )
        for env, output, code in cases:
            with self.subTest(env=sorted(env)):
                out_file = self._output_file()
                proc = bash(script, Path("."), {"GITHUB_OUTPUT": str(out_file), **env})
                self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
                self.assertNotIn(key, proc.stdout)
                self.assertNotIn(key, proc.stderr)
                if output is None:
                    self.assertIn("Set both DRAFT_RECEIVER_APP_ID and DRAFT_RECEIVER_APP_PRIVATE_KEY", proc.stdout)
                    self.assertEqual(out_file.read_text(encoding="utf-8"), "")
                else:
                    self.assertEqual(out_file.read_text(encoding="utf-8"), output)

    def _output_file(self) -> Path:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        tmp.close()
        return Path(tmp.name)


class SyncMergeWorkflowTests(unittest.TestCase):
    """After validate succeeds, the receiver App merges the confined pull request at that exact SHA."""

    def test_it_follows_a_successful_validation_of_a_same_repository_sync_branch(self) -> None:
        workflow = yaml.safe_load(MERGE.read_text(encoding="utf-8"))
        trigger = workflow.get("on", workflow.get(True))
        self.assertEqual(trigger["workflow_run"]["workflows"], ["Validate Catalog"])
        self.assertEqual(trigger["workflow_run"]["types"], ["completed"])
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        job = workflow["jobs"]["merge_sync"]
        self.assertIn("github.event.workflow_run.conclusion == 'success'", job["if"])
        self.assertIn("github.event.workflow_run.event == 'pull_request'", job["if"])
        self.assertIn("startsWith(github.event.workflow_run.head_branch, 'draft-sync/')", job["if"])
        self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository", job["if"])
        self.assertEqual(workflow["concurrency"], {"group": "draft-sdp-merge", "cancel-in-progress": False})
        text = MERGE.read_text(encoding="utf-8")
        self.assertNotIn("workflow_run.triggering_actor", text)
        self.assertNotIn("github.triggering_actor", text)
        self.assertIn("github.event.workflow_run.actor.login", text)

    def test_it_mints_the_receiver_app_token_and_merges_that_sha(self) -> None:
        self.assertLess(names_index(MERGE, "Mint Receiver App Token"), names_index(MERGE, "Require Receiver App Push"))
        self.assertLess(names_index(MERGE, "Require Receiver App Push"), names_index(MERGE, "Checkout Workspace"))
        self.assertLess(names_index(MERGE, "Checkout Workspace"), names_index(MERGE, "Merge Confined Sync Pull Request"))
        self.assertEqual(step(MERGE, "Detect Receiver App Credentials")["run"], step(RECEIVER, "Detect Receiver App Credentials")["run"])
        token = step(MERGE, "Mint Receiver App Token")
        self.assertEqual(token["if"], "steps.receiver_app.outputs.present == 'true'")
        self.assertEqual(token["uses"], APP_TOKEN_ACTION)
        self.assertEqual(token["with"]["permission-contents"], "write")
        self.assertEqual(token["with"]["permission-pull-requests"], "write")
        self.assertEqual(token["with"]["repositories"], "${{ github.event.repository.name }}")
        guard = step(MERGE, "Require Receiver App Push")
        self.assertEqual(guard["env"]["PUSHER"], "${{ github.event.workflow_run.actor.login }}")
        self.assertEqual(guard["env"]["APP_SLUG"], "${{ steps.receiver_token.outputs.app-slug }}")
        self.assertIn('expected="${APP_SLUG}[bot]"', guard["run"])
        self.assertIn('[ "$PUSHER" != "$expected" ]', guard["run"])
        checkout = step(MERGE, "Checkout Workspace")
        self.assertNotIn("ref", checkout.get("with", {}))
        self.assertNotIn("head_sha", json.dumps(checkout))
        self.assertNotIn("head_branch", json.dumps(checkout))
        merge = step(MERGE, "Merge Confined Sync Pull Request")
        self.assertEqual(merge["if"], "success() && steps.receiver_token.outcome == 'success'")
        self.assertEqual(merge["env"]["GH_TOKEN"], "${{ steps.receiver_token.outputs.token }}")
        self.assertEqual(merge["env"]["HEAD_SHA"], "${{ github.event.workflow_run.head_sha }}")
        self.assertEqual(merge["env"]["HEAD_BRANCH"], "${{ github.event.workflow_run.head_branch }}")
        self.assertEqual(merge["env"]["PUSHER"], "${{ github.event.workflow_run.actor.login }}")
        self.assertEqual(merge["env"]["APP_SLUG"], "${{ steps.receiver_token.outputs.app-slug }}")
        self.assertEqual(merge["env"]["AUTO_MERGE"], "${{ vars.DRAFT_SYNC_AUTO_MERGE }}")
        self.assertIn("sdp_sync.py merge", merge["run"])
        self.assertIn('--sha "$HEAD_SHA"', merge["run"])
        self.assertIn('--pusher "$PUSHER"', merge["run"])
        self.assertIn('--app-slug "$APP_SLUG"', merge["run"])
        self.assertIn('--auto-merge "${AUTO_MERGE:-false}"', merge["run"])
        self.assertNotIn("gh pr merge", MERGE.read_text(encoding="utf-8"))
        self.assertIn("def _require_receiver_pusher", (ROOT / "framework" / "tools" / "sdp_sync.py").read_text(encoding="utf-8"))
        self.assertIn("workflow_run.actor", (ROOT / "framework" / "tools" / "sdp_sync.py").read_text(encoding="utf-8"))


def bash(script: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-e", "-c", script], cwd=cwd, env={**os.environ, **env}, capture_output=True, text=True, check=False)


class ScriptSimulationTests(unittest.TestCase):
    """Run the templates' own run: scripts with hostile values to show they stay data."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.product = self.tmp / "product"
        self.central = self.tmp / "central"
        shutil.copytree(FIXTURES / "product_repo", self.product)
        shutil.copytree(FIXTURES / "central_workspace", self.central)
        (self.product / ".draft-sync-tool").symlink_to(ROOT)
        (self.central / ".draft" / "framework").parent.mkdir(exist_ok=True)
        (self.central / ".draft" / "framework").symlink_to(ROOT / "framework")
        self.canary = self.tmp / "pwned"
        self.env = {"RUNNER_TEMP": str(self.tmp), "PATH": f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}"}

    def pack_script(self) -> str:
        # Drop the pip line: the test interpreter already has PyYAML.
        return "\n".join(line for line in step(SENDER, "Pack SDP Payload")["run"].splitlines() if "pip install" not in line)

    def test_sender_pack_script_treats_hostile_values_as_data(self) -> None:
        hostile = f'example-org/x"; touch {self.canary}; echo "'
        out = bash(self.pack_script(), self.product, {**self.env, "REPOSITORY": hostile, "COMMIT": "0" * 40,
                                                       "REF": "refs/heads/main", "CORRELATION_ID": "1-1"})
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("not a GitHub repository name", out.stderr)
        self.assertFalse(self.canary.exists())

    def fake_token_endpoint(self, claims: dict) -> str:
        """A stand-in for the runner's ACTIONS_ID_TOKEN_REQUEST_URL that signs a token for the requested audience."""
        seen = self.token_requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                query = parse_qs(urlparse(self.path).query)
                seen.append((query, self.headers.get("Authorization")))
                body = json.dumps({"value": identity.token({**claims, "aud": query["audience"][0]})}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}/token?api-version=2.0"

    @unittest.skipUnless(shutil.which("jq"), "jq is not installed (GitHub-hosted runners have it)")
    def test_sender_and_receiver_scripts_round_trip_a_hostile_sdp(self) -> None:
        sdp = self.product / ".draft" / "sdp.yaml"
        sdp.write_text(sdp.read_text(encoding="utf-8") + f"notes:\n  shell: \"$(touch {self.canary}) `touch {self.canary}` ' \\\" ;\"\n", encoding="utf-8")
        url = self.fake_token_endpoint(identity.claims_for("example-org/absence-service", "a" * 40))
        packed = bash(self.pack_script(), self.product, {**self.env, "REPOSITORY": "example-org/absence-service", "COMMIT": "a" * 40,
                                                          "REF": "refs/heads/main", "CORRELATION_ID": "7-1",
                                                          "CENTRAL_REPOSITORY": "Example-Org/drafting-table",
                                                          "ACTIONS_ID_TOKEN_REQUEST_URL": url, "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "runner-bearer"})
        self.assertEqual(packed.returncode, 0, packed.stderr)
        # Build the dispatch body exactly as the sender's jq does, and hand it to the receiver as the event file.
        jq = step(SENDER, "Dispatch SDP Payload to Central Workspace")["run"].split("|", 1)[0]
        body = bash(jq, self.product, self.env)
        self.assertEqual(body.returncode, 0, body.stderr)
        event = json.loads(body.stdout)
        self.assertEqual(event["event_type"], "sdp_updated")
        event_file = self.tmp / "event.json"
        event_file.write_text(json.dumps({"action": "sdp_updated", "client_payload": event["client_payload"]}), encoding="utf-8")
        self.assertEqual(self.token_requests, [({"api-version": ["2.0"], "audience": [identity.AUDIENCE]}, "Bearer runner-bearer")])
        # The receiver normally fetches GitHub's key set; here it reads the test key set from a file.
        jwks = identity.write_jwks(self.tmp / "jwks.json")
        receive_script = step(RECEIVER, "Store Decentralized SDP Payload")["run"].rstrip("\n") + f' \\\n  --jwks "{jwks}"\n'
        received = bash(receive_script, self.central, {**self.env, "GITHUB_EVENT_PATH": str(event_file), "CENTRAL_REPOSITORY": identity.CENTRAL})
        self.assertEqual(received.returncode, 0, received.stderr)
        stored = self.central / ".draft" / "external_sdps" / "example-org__absence-service" / "sdp.yaml"
        self.assertEqual(stored.read_text(encoding="utf-8"), sdp.read_text(encoding="utf-8"))
        self.assertFalse(self.canary.exists())
        self.assertEqual(json.loads((self.tmp / "sdp-sync-result.json").read_text())["status"], "accepted")



if __name__ == "__main__":
    unittest.main()
