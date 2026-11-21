"""Fake GitHub Actions OIDC tokens for the #195 sync tests, signed with a fixed TEST-ONLY key.

Importable from tests as ``from tests import sdp_sync_identity as identity``. The key in
``fixtures/sdp_sync/oidc_test_key.json`` is trusted only by the key set built here.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "framework" / "tools"))

import sdp_sync  # noqa: E402

_KEY = json.loads((ROOT / "tests" / "fixtures" / "sdp_sync" / "oidc_test_key.json").read_text(encoding="utf-8"))
N, E, D = int(_KEY["n"], 16), int(_KEY["e"], 16), int(_KEY["d"], 16)
KID = _KEY["kid"]
CENTRAL = "example-org/drafting-table"
AUDIENCE = sdp_sync.audience_for(CENTRAL)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def int_b64url(value: int) -> str:
    return b64url(value.to_bytes((value.bit_length() + 7) // 8, "big"))


JWKS = {"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": KID, "n": int_b64url(N), "e": int_b64url(E)}]}


def rs256_sign(signing_input: bytes, d: int = D, n: int = N) -> bytes:
    k = (n.bit_length() + 7) // 8
    digest = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(signing_input).digest()
    encoded = b"\x00\x01" + b"\xff" * (k - len(digest) - 3) + b"\x00" + digest
    return pow(int.from_bytes(encoded, "big"), d, n).to_bytes(k, "big")


def token(claims: dict[str, Any], header: dict[str, Any] | None = None) -> str:
    head = b64url(json.dumps(header or {"alg": "RS256", "typ": "JWT", "kid": KID}).encode())
    body = b64url(json.dumps(claims).encode())
    return f"{head}.{body}.{b64url(rs256_sign(f'{head}.{body}'.encode()))}"


def claims_for(repository: str, commit: str, ref: str = "refs/heads/main", /, **overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims = {"iss": sdp_sync.OIDC_ISSUER, "aud": AUDIENCE, "repository": repository, "repository_owner": repository.split("/")[0],
              "ref": ref, "sha": commit, "event_name": "push", "iat": now, "nbf": now, "exp": now + 300,
              "sub": f"repo:{repository}:ref:{ref}"}
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def sign(payload: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """The payload with an OIDC token for its own repository, commit and ref (claims overridable)."""
    if not isinstance(payload.get("repository"), str):
        return dict(payload)
    claims = claims_for(payload["repository"], str(payload.get("commit")), str(payload.get("ref")), **overrides)
    return {**payload, "oidcToken": token(claims)}


def receive(workspace: Path, payload: dict[str, Any], **overrides: Any) -> sdp_sync.Result:
    return sdp_sync.receive(workspace, sign(payload, **overrides), central_repository=CENTRAL, keys=JWKS)


def write_jwks(path: Path) -> Path:
    path.write_text(json.dumps(JWKS), encoding="utf-8")
    return path
