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


def steps(path: Path) -> list[dict]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


def step(path: Path, name: str) -> dict:
    (found,) = [s for s in steps(path) if s.get("name") == name]
    return found


class NoExpressionsInScriptsTests(unittest.TestCase):
    def test_no_run_step_contains_an_expression(self) -> None:
        for path in (SENDER, RECEIVER):
            for s in steps(path):
                if "run" in s:
                    with self.subTest(template=path.name, step=s.get("name")):
                        self.assertIsNone(EXPRESSION.search(s["run"]), "pass values through env: or files, not ${{ }} in run:")

    def test_no_template_reads_the_payload_through_an_expression(self) -> None:
        for path in (SENDER, RECEIVER):
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
        self.assertEqual(token["uses"], "actions/create-github-app-token@v1")
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
        self.assertEqual(names[-1], "Publish Sync Pull Request")
        self.assertLess(names.index("Regenerate Machine Indexes & AI Map"), names.index("Publish Sync Pull Request"))
        publish = step(RECEIVER, "Publish Sync Pull Request")
        self.assertEqual(publish["env"], {"GH_TOKEN": "${{ github.token }}", "BASE_BRANCH": "${{ github.event.repository.default_branch }}",
                                          "AUTO_MERGE": "${{ vars.DRAFT_SYNC_AUTO_MERGE }}"})
        self.assertIn("sdp_sync.py publish", publish["run"])
        self.assertIn('--result "$RUNNER_TEMP/sdp-sync-result.json"', publish["run"])

    def test_receiver_receives_from_the_event_file_then_validates(self) -> None:
        names = [s.get("name") for s in steps(RECEIVER)]
        receive = step(RECEIVER, "Store Decentralized SDP Payload")
        self.assertIn('sdp_sync.py receive', receive["run"])
        self.assertIn('--payload "$GITHUB_EVENT_PATH"', receive["run"])
        self.assertLess(names.index("Store Decentralized SDP Payload"), names.index("Validate Workspace Architecture"))


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
