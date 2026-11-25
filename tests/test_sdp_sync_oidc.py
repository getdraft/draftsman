"""#195 S2.2: the receiver verifies the sender's GitHub Actions OIDC token before it stores anything."""
from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "framework" / "tools"))
sys.path.insert(0, str(ROOT))

import sdp_sync  # noqa: E402
from tests import sdp_sync_identity as identity  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "sdp_sync"
REPOSITORY = "example-org/absence-service"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
SDP = (FIXTURES / "product_repo" / ".draft" / "sdp.yaml").read_text(encoding="utf-8")
REGISTRATION = FIXTURES / "central_workspace" / "catalog" / "engineering" / "product-registrations" / "product-reg-absence-service.yaml"


def payload(**fields: object) -> dict:
    return {"format": sdp_sync.PAYLOAD_FORMAT, "repository": REPOSITORY, "commit": COMMIT, "ref": "refs/heads/main",
            "action": "upsert", "correlationId": "run-1", "files": {".draft/sdp.yaml": SDP}, **fields}


class Central:
    def __init__(self, test: unittest.TestCase) -> None:
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "central"
        shutil.copytree(FIXTURES / "central_workspace", self.root)
        self.test = test

    def receive(self, body: dict, **kw: object) -> sdp_sync.Result:
        kw.setdefault("central_repository", identity.CENTRAL)
        kw.setdefault("keys", identity.JWKS)
        return sdp_sync.receive(self.root, body, **kw)

    def rejects(self, body: dict, expected: str, **kw: object) -> None:
        result = self.receive(body, **kw)
        self.test.assertEqual(result.status, "rejected", result.message)
        self.test.assertIn(expected, result.message)
        self.test.assertFalse((self.root / ".draft" / "external_sdps").exists(), "nothing is written on rejection")

    def registration_path(self) -> Path:
        return self.root / REGISTRATION.relative_to(FIXTURES / "central_workspace")

    def set_default_branch(self, branch: str | None) -> None:
        path = self.registration_path()
        text = path.read_text(encoding="utf-8").replace("  defaultBranch: main\n", f"  defaultBranch: {branch}\n" if branch else "")
        path.write_text(text, encoding="utf-8")

    def pin_repository(self, repo_id: str | None = None, owner_id: str | None = None) -> None:
        """Insert repository.id / repository.ownerId as raw YAML tokens, such as 424242 or '\"424242\"'."""
        path = self.registration_path()
        text = path.read_text(encoding="utf-8")
        block = ""
        if repo_id is not None:
            block += f"  id: {repo_id}\n"
        if owner_id is not None:
            block += f"  ownerId: {owner_id}\n"
        needle = "  defaultBranch: main\n"
        if needle not in text:
            raise AssertionError("registration fixture has no defaultBranch line to anchor the pin")
        path.write_text(text.replace(needle, needle + block, 1), encoding="utf-8")

    def set_repository_url(self, url: str) -> None:
        path = self.registration_path()
        old = "  url: https://github.com/example-org/absence-service\n"
        text = path.read_text(encoding="utf-8")
        if old not in text:
            raise AssertionError(text)
        path.write_text(text.replace(old, f"  url: {url}\n", 1), encoding="utf-8")


def signed(**claims: object) -> dict:
    return identity.sign(payload(), **claims)


class SignatureTests(unittest.TestCase):
    def test_a_valid_token_from_the_registered_default_branch_is_accepted(self) -> None:
        result = Central(self).receive(signed())
        self.assertEqual(result.status, "accepted", result.message)

    def test_rs256_verify_matches_the_reference_signer(self) -> None:
        message = b"header.claims"
        signature = identity.rs256_sign(message)
        self.assertTrue(sdp_sync.rs256_verify(identity.N, identity.E, message, signature))
        self.assertFalse(sdp_sync.rs256_verify(identity.N, identity.E, b"header.claimz", signature))
        self.assertFalse(sdp_sync.rs256_verify(identity.N, identity.E, message, signature[:-1]))
        self.assertFalse(sdp_sync.rs256_verify(identity.N, identity.E, message, (identity.N).to_bytes(256, "big")))

    def test_tampered_claims_fail_the_signature(self) -> None:
        good = signed()
        head, _, sig = good["oidcToken"].split(".")
        forged = identity.b64url(json.dumps(identity.claims_for(REPOSITORY, COMMIT, sub="forged")).encode())
        Central(self).rejects({**good, "oidcToken": f"{head}.{forged}.{sig}"}, "signature does not verify")

    def test_a_token_signed_by_another_key_is_refused(self) -> None:
        # Same kid, different modulus in the key set: the signature cannot verify.
        other = {"keys": [{**identity.JWKS["keys"][0], "n": identity.int_b64url(identity.N - 2)}]}
        Central(self).rejects(signed(), "signature does not verify", keys=other)

    def test_an_unknown_kid_is_refused(self) -> None:
        body = payload(oidcToken=identity.token(identity.claims_for(REPOSITORY, COMMIT), {"alg": "RS256", "kid": "rotated-away"}))
        Central(self).rejects(body, "'rotated-away' is not in GitHub's key set")

    def test_only_rs256_is_accepted(self) -> None:
        claims = identity.claims_for(REPOSITORY, COMMIT)
        for alg in ("none", "HS256", "RS512"):
            with self.subTest(alg):
                Central(self).rejects(payload(oidcToken=identity.token(claims, {"alg": alg, "kid": identity.KID})), "only RS256 is accepted")

    def test_keys_too_short_or_for_another_use_are_ignored(self) -> None:
        key = identity.JWKS["keys"][0]
        Central(self).rejects(signed(), "not in GitHub's key set", keys={"keys": [{**key, "use": "enc"}]})
        Central(self).rejects(signed(), "not in GitHub's key set", keys={"keys": [{**key, "kty": "EC"}]})
        short = {"keys": [{**key, "n": identity.int_b64url(identity.N >> 1100)}]}
        Central(self).rejects(signed(), "signature does not verify", keys=short)

    def test_malformed_tokens_are_refused(self) -> None:
        for token, expected in (("not-a-jwt", "not a JWT"), ("a.b.c", "not a readable JWT"), (123, "not a JWT")):
            with self.subTest(token):
                Central(self).rejects(payload(oidcToken=token), expected)

    def test_a_payload_without_a_token_names_the_template_update(self) -> None:
        Central(self).rejects(payload(), "carries no OIDC token")
        Central(self).rejects(payload(action="delete", files={}), "carries no OIDC token")


class ClaimTests(unittest.TestCase):
    def test_issuer_must_be_github_actions(self) -> None:
        Central(self).rejects(signed(iss="https://token.example.com"), "not GitHub Actions")

    def test_audience_must_name_this_central_workspace(self) -> None:
        Central(self).rejects(signed(aud="draft-sdp-sync:example-org/other-table"), "not this central workspace")
        Central(self).rejects(signed(aud=None), "not this central workspace")
        self.assertEqual(Central(self).receive(signed(aud=["sts.amazonaws.com", identity.AUDIENCE])).status, "accepted")

    def test_the_audience_compares_case_insensitively(self) -> None:
        self.assertEqual(Central(self).receive(signed(), central_repository="Example-Org/Drafting-Table").status, "accepted")
        self.assertEqual(sdp_sync.audience_for("Example-Org/Drafting-Table"), "draft-sdp-sync:example-org/drafting-table")

    def test_expired_and_future_tokens_are_refused(self) -> None:
        now = int(time.time())
        Central(self).rejects(signed(exp=now - sdp_sync.LEEWAY_SECONDS - 5), "has expired")
        Central(self).rejects(signed(exp=None), "has expired")
        Central(self).rejects(signed(nbf=now + 600), "nbf is in the future")
        Central(self).rejects(signed(iat=now + 600), "iat is in the future")
        self.assertEqual(Central(self).receive(signed(exp=now - 10)).status, "accepted", "small clock skew is tolerated")

    def test_an_injected_clock_is_used(self) -> None:
        body = signed()
        Central(self).rejects(body, "has expired", now=time.time() + 3600)

    def test_the_token_repository_must_be_the_payload_repository(self) -> None:
        Central(self).rejects(signed(repository="example-org/absence-service-fork"), "was issued to 'example-org/absence-service-fork'")
        self.assertEqual(Central(self).receive(signed(repository="Example-Org/Absence-Service")).status, "accepted")

    def test_a_token_for_an_unregistered_repository_cannot_sync_as_it(self) -> None:
        # A real token from another repository, with the payload claiming to be that repository: no registration matches.
        body = identity.sign(payload(repository="example-org/sneaky"))
        Central(self).rejects(body, "no ProductRegistration")

    def test_only_the_registered_default_branch_can_sync(self) -> None:
        feature = identity.sign(payload(ref="refs/heads/feature/x"))
        Central(self).rejects(feature, "only the registered default branch (refs/heads/main) can sync")
        tag = identity.sign(payload(ref="refs/tags/v1"))
        Central(self).rejects(tag, "only the registered default branch")

    def test_the_registered_default_branch_is_the_one_that_counts(self) -> None:
        central = Central(self)
        central.set_default_branch("trunk")
        central.rejects(signed(), "only the registered default branch (refs/heads/trunk) can sync")
        self.assertEqual(central.receive(identity.sign(payload(ref="refs/heads/trunk"))).status, "accepted")

    def test_a_registration_without_a_default_branch_is_refused(self) -> None:
        central = Central(self)
        central.set_default_branch(None)
        central.rejects(signed(), "has no repository.defaultBranch")

    def test_payload_ref_and_commit_must_match_the_token(self) -> None:
        # A genuine default-branch token reused with a payload that claims another ref or commit.
        Central(self).rejects({**signed(), "ref": "refs/heads/release"}, "does not match the OIDC token's ref")
        Central(self).rejects({**signed(), "commit": "f" * 40}, "does not match the OIDC token's sha")
        Central(self).rejects(signed(sha=None), "does not match the OIDC token's sha")

    def test_deletes_need_the_same_identity(self) -> None:
        Central(self).rejects(identity.sign(payload(action="delete", files={}), repository="example-org/other"), "was issued to")
        self.assertEqual(Central(self).receive(identity.sign(payload(action="delete", files={}))).status, "accepted")


class KeySetTests(unittest.TestCase):
    def test_the_key_set_is_fetched_only_after_the_payload_checks_pass(self) -> None:
        calls = []

        def keys() -> dict:
            calls.append(1)
            return identity.JWKS

        Central(self).rejects(identity.sign(payload(format="nope")), "unsupported payload format", keys=keys)
        self.assertEqual(calls, [])
        self.assertEqual(Central(self).receive(signed(), keys=keys).status, "accepted")
        self.assertEqual(calls, [1])

    def test_the_default_fetches_githubs_published_key_set(self) -> None:
        requests = []

        def opener(request, timeout):
            requests.append((request.full_url, timeout))
            return io.BytesIO(json.dumps(identity.JWKS).encode())

        self.assertEqual(sdp_sync.fetch_github_jwks(opener), identity.JWKS)
        self.assertEqual(requests, [("https://token.actions.githubusercontent.com/.well-known/jwks", 30)])

        def broken(request, timeout):
            raise OSError("offline")

        with self.assertRaisesRegex(sdp_sync.SyncError, "could not fetch GitHub's OIDC key set"):
            sdp_sync.fetch_github_jwks(broken)

    def test_a_malformed_key_set_is_refused(self) -> None:
        for keys in ({}, {"keys": "x"}, {"keys": [{"kty": "RSA", "kid": identity.KID, "n": "", "e": "AQAB"}]},
                     {"keys": [{"kty": "RSA", "kid": identity.KID, "n": "!!", "e": "AQAB"}]}):
            with self.subTest(keys):
                result = Central(self).receive(signed(), keys=keys)
                self.assertEqual(result.status, "rejected")


class SenderTests(unittest.TestCase):
    ENV = {"ACTIONS_ID_TOKEN_REQUEST_URL": "https://runner.example/idtoken?api-version=2.0", "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "bearer-x"}

    def test_the_sender_requests_a_token_for_the_central_audience(self) -> None:
        requests = []
        jwt = identity.token(identity.claims_for(REPOSITORY, COMMIT))

        def opener(request, timeout):
            requests.append((request.full_url, request.headers.get("Authorization")))
            return io.BytesIO(json.dumps({"value": jwt}).encode())

        audience = sdp_sync.audience_for("example-org/drafting-table")
        self.assertEqual(sdp_sync.request_oidc_token(audience, self.ENV, opener), jwt)
        self.assertEqual(requests, [("https://runner.example/idtoken?api-version=2.0&audience=draft-sdp-sync%3Aexample-org%2Fdrafting-table",
                                     "Bearer bearer-x")])

    def test_a_job_without_id_token_permission_gets_a_clear_error(self) -> None:
        with self.assertRaisesRegex(sdp_sync.SyncError, "id-token: write"):
            sdp_sync.request_oidc_token(identity.AUDIENCE, {})

    def test_a_failed_or_empty_token_request_is_an_error(self) -> None:
        def empty(request, timeout):
            return io.BytesIO(b'{"value": null}')

        def failing(request, timeout):
            raise OSError("secret-bearer-x in a message")

        with self.assertRaisesRegex(sdp_sync.SyncError, "returned no token"):
            sdp_sync.request_oidc_token(identity.AUDIENCE, self.ENV, empty)
        with self.assertRaises(sdp_sync.SyncError) as caught:
            sdp_sync.request_oidc_token(identity.AUDIENCE, self.ENV, failing)
        self.assertNotIn("bearer-x", str(caught.exception))

    def test_pack_attaches_the_token_and_stays_within_dispatch_limits(self) -> None:
        jwt = identity.token(identity.claims_for(REPOSITORY, COMMIT))
        body = sdp_sync.pack(FIXTURES / "product_repo", REPOSITORY, COMMIT, "refs/heads/main", "run-1", oidc_token=jwt)
        self.assertEqual(body["oidcToken"], jwt)
        self.assertLessEqual(len(body), sdp_sync.MAX_TOP_LEVEL_PROPERTIES)

    def test_the_token_is_never_stored_or_reported(self) -> None:
        central = Central(self)
        body = signed()
        result = central.receive(body)
        self.assertEqual(result.status, "accepted", result.message)
        stored = "".join(p.read_text(encoding="utf-8") for p in (central.root / ".draft").rglob("*") if p.is_file())
        self.assertNotIn(body["oidcToken"], stored + json.dumps(result.as_json()))
        rejected = central.receive({**body, "commit": "f" * 40})
        self.assertNotIn(body["oidcToken"], json.dumps(rejected.as_json()))


REPO_ID = 424242
OWNER_ID = 1001


class RepositoryIdTests(unittest.TestCase):
    def test_parse_github_id_accepts_the_forms_github_and_yaml_produce(self) -> None:
        self.assertEqual(sdp_sync.parse_github_id(REPO_ID), REPO_ID)
        self.assertEqual(sdp_sync.parse_github_id(str(REPO_ID)), REPO_ID)
        self.assertEqual(sdp_sync.parse_github_id(f"  {REPO_ID}\n"), REPO_ID)
        for value in (None, "", "0", "042", "-1", 0, -1, True, False, 1.5, "abc", 2**63, [], {}):
            with self.subTest(value):
                self.assertIsNone(sdp_sync.parse_github_id(value))

    def test_a_pinned_id_matches_a_string_or_integer_claim(self) -> None:
        central = Central(self)
        central.pin_repository(str(REPO_ID), str(OWNER_ID))
        result = central.receive(signed(repository_id=str(REPO_ID), repository_owner_id=str(OWNER_ID)))
        self.assertEqual(result.status, "accepted", result.message)
        self.assertEqual(result.warnings, [])
        self.assertNotIn("not pinned", result.message)
        self.assertTrue(result.identity_verified)

        quoted = Central(self)
        quoted.pin_repository(f'"{REPO_ID}"', f'"{OWNER_ID}"')
        result = quoted.receive(signed(repository_id=REPO_ID, repository_owner_id=OWNER_ID))
        self.assertEqual(result.status, "accepted", result.message)
        self.assertEqual(result.warnings, [])

    def test_a_recreated_repository_with_the_same_name_is_refused(self) -> None:
        central = Central(self)
        central.pin_repository(str(REPO_ID), str(OWNER_ID))
        result = central.receive(signed(repository_id="999999", repository_owner_id=str(OWNER_ID)))
        self.assertEqual(result.status, "rejected", result.message)
        self.assertIn("repository_id is '999999', not 424242 pinned on ProductRegistration 01M7SYNC03-PR01", result.message)
        self.assertIn("deleted and recreated repository does not", result.message)
        self.assertTrue(result.identity_verified, "the token already matched the registered name, so the product run is told")
        self.assertFalse((central.root / ".draft" / "external_sdps").exists())

    def test_a_pinned_registration_rejects_a_token_with_no_repository_id(self) -> None:
        central = Central(self)
        central.pin_repository(str(REPO_ID))
        central.rejects(signed(), "repository_id is missing, not 424242 pinned")
        result = central.receive(signed())
        self.assertTrue(result.identity_verified)

    def test_a_rename_keeps_working_when_the_permanent_id_matches(self) -> None:
        central = Central(self)
        central.pin_repository(str(REPO_ID), str(OWNER_ID))
        central.set_repository_url("https://github.com/example-org/absence-renamed")
        body = identity.sign(payload(repository="example-org/absence-renamed"), repository_id=str(REPO_ID), repository_owner_id=str(OWNER_ID))
        result = central.receive(body)
        self.assertEqual(result.status, "accepted", result.message)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.product, "example-org__absence-renamed")

    def test_an_owner_id_mismatch_is_refused_when_the_repository_id_matches(self) -> None:
        central = Central(self)
        central.pin_repository(str(REPO_ID), str(OWNER_ID))
        central.rejects(signed(repository_id=str(REPO_ID), repository_owner_id="8888"), "repository_owner_id is '8888', not 1001 pinned")

    def test_owner_id_is_not_required_when_the_repository_id_is_pinned(self) -> None:
        central = Central(self)
        central.pin_repository(str(REPO_ID))
        result = central.receive(signed(repository_id=str(REPO_ID), repository_owner_id="8888"))
        self.assertEqual(result.status, "accepted", result.message)
        self.assertEqual(result.warnings, [])

    def test_an_unpinned_registration_accepts_any_repository_id_and_warns(self) -> None:
        result = Central(self).receive(signed(repository_id="999999", repository_owner_id="8888"))
        self.assertEqual(result.status, "accepted", result.message)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("repository.id is not pinned on ProductRegistration 01M7SYNC03-PR01", result.warnings[0])
        self.assertIn("matched example-org/absence-service by repository name only", result.warnings[0])
        self.assertIn("does not record the id itself", result.warnings[0])
        self.assertIn(result.warnings[0], result.message)
        self.assertEqual(result.as_json()["warnings"], result.warnings)
        outcome = sdp_sync.final_outcome({**result.as_json(), "publish": {"status": "published", "pullRequestAction": "opened",
                                            "pullRequest": {"number": 5, "url": "https://github.com/example-org/drafting-table/pull/5"}}},
                                          None, "success")
        self.assertEqual(outcome["status"], "accepted")
        self.assertTrue(outcome["message"].startswith("opened pull request https://github.com/example-org/drafting-table/pull/5"))
        self.assertIn("repository.id is not pinned", outcome["message"])
        self.assertEqual(outcome["warnings"], result.warnings)

    def test_a_missing_repository_id_still_warns_when_only_the_owner_id_is_pinned(self) -> None:
        central = Central(self)
        central.pin_repository(owner_id=str(OWNER_ID))
        refused = central.receive(signed(repository_owner_id="8888"))
        self.assertEqual(refused.status, "rejected", refused.message)
        self.assertIn("repository_owner_id is '8888', not 1001 pinned", refused.message)
        accepted = central.receive(signed(repository_id="999999", repository_owner_id=str(OWNER_ID)))
        self.assertEqual(accepted.status, "accepted", accepted.message)
        self.assertIn("repository.id is not pinned", accepted.message)

    def test_a_malformed_pin_fails_closed(self) -> None:
        central = Central(self)
        central.pin_repository("not-an-id", str(OWNER_ID))
        central.rejects(signed(repository_id=str(REPO_ID), repository_owner_id=str(OWNER_ID)), "repository.id 'not-an-id' is not a GitHub id")
        central = Central(self)
        central.pin_repository(str(REPO_ID), '"0"')
        central.rejects(signed(repository_id=str(REPO_ID), repository_owner_id=str(OWNER_ID)), "repository.ownerId '0' is not a GitHub id")

    def test_a_delete_needs_the_same_repository_id(self) -> None:
        central = Central(self)
        central.pin_repository(str(REPO_ID))
        central.rejects(identity.sign(payload(action="delete", files={}), repository_id="999999"), "repository_id is '999999'")
        result = central.receive(identity.sign(payload(action="delete", files={}), repository_id=str(REPO_ID)))
        self.assertEqual(result.status, "accepted", result.message)
        self.assertEqual(result.warnings, [])


if __name__ == "__main__":
    unittest.main()
