#!/usr/bin/env python3
"""Decentralized SDP sync: pack a product repository's SDP and receive it into the central workspace (#195).

The product repository's workflow runs ``pack`` and sends the JSON it writes as a ``repository_dispatch``
``client_payload``. The central workspace's receiver workflow runs ``receive`` on the event file. Payload values
only ever travel through files; nothing here builds shell text.

The sender proves who it is with a GitHub Actions OIDC token whose audience names the central workspace
(``draft-sdp-sync:<central owner>/<central name>``). ``receive`` verifies the RS256 signature against GitHub's
published key set with the standard library, then checks the issuer, audience, expiry, that the token's repository
is the registered one and that its ref is the registered default branch. When the ProductRegistration pins
``repository.id`` or ``repository.ownerId``, the token's ``repository_id`` or ``repository_owner_id`` must be
that same number. A registration that omits ``repository.id`` still matches by name, and the result warns.

Usage:
    python3 sdp_sync.py pack --repo-root . --repository OWNER/NAME --commit SHA --ref refs/heads/main \
        --central-repository CENTRAL_OWNER/CENTRAL_NAME --output payload.json
    python3 sdp_sync.py receive --workspace . --payload "$GITHUB_EVENT_PATH" --central-repository CENTRAL_OWNER/CENTRAL_NAME \
        --result sdp-sync-result.json
    python3 sdp_sync.py publish --workspace . --result sdp-sync-result.json --base main [--auto-merge true]
    python3 sdp_sync.py merge --workspace . --repository OWNER/NAME --base main --sha SHA --head draft-sync/owner__name \
        [--auto-merge true]
    python3 sdp_sync.py report --payload "$GITHUB_EVENT_PATH" --result sdp-sync-result.json --validate-log validate.log \
        --job-status "$JOB_STATUS" --base main --summary "$GITHUB_STEP_SUMMARY"
    python3 sdp_sync.py await-result --central-repository CENTRAL_OWNER/CENTRAL_NAME --repository OWNER/NAME \
        --correlation-id ID --summary "$GITHUB_STEP_SUMMARY"

``publish`` never pushes to the default branch: it commits the receiver's changes to ``draft-sync/<product>`` and
opens or updates that branch's pull request. Every git and gh call is an argument list, never shell text.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from uid_utils import UID_PATTERN_TEXT

PAYLOAD_FORMAT = "draft-sdp-sync/1"
# GitHub repository_dispatch: client_payload has at most 10 top-level properties and must stay under 64 KB.
MAX_CLIENT_PAYLOAD_BYTES = 65_000
MAX_TOP_LEVEL_PROPERTIES = 10
SDP_PATH = ".draft/sdp.yaml"
CATALOG_DIR = ".draft/catalog"
CACHE_ROOT = Path(".draft") / "external_sdps"
ACTIONS = ("upsert", "delete")
_REPOSITORY = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")
_COMMIT = re.compile(r"^[0-9a-f]{7,64}$")
_CORRELATION = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_UID = re.compile(UID_PATTERN_TEXT)
_GITHUB_URL = re.compile(
    r"^(?:https?://(?:www\.)?github\.com/|ssh://git@github\.com/|git@github\.com:)([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", re.IGNORECASE
)
# Object types a product team owns and may sync. Everything else (systems, shared services, registrations,
# requirement groups, configurations) is central content and is never accepted from a product repository.
PRODUCT_OWNED_TYPES = ("software_deployment_pattern", "product_component", "data_component", "listener", "relationship", "decision_record")
# GitHub Actions OIDC. Tokens are short-lived; LEEWAY_SECONDS absorbs clock skew between GitHub and the runner.
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
OIDC_JWKS_URL = OIDC_ISSUER + "/.well-known/jwks"
AUDIENCE_PREFIX = "draft-sdp-sync:"
LEEWAY_SECONDS = 60
MIN_RSA_BITS = 2048
_JWT = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
# DER DigestInfo prefix for SHA-256 (RFC 8017 section 9.2, note 1).
_SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")
KeySource = Mapping[str, Any] | Callable[[], Mapping[str, Any]]


class SyncError(Exception):
    """A payload or input the sync refuses, with a message for the product team."""


# --------------------------------------------------------------------------- pack


def pack(repo_root: Path, repository: str, commit: str, ref: str, correlation_id: str | None = None,
         oidc_token: str | None = None) -> dict[str, Any]:
    """Build the client_payload for a product repository: .draft/sdp.yaml plus the YAML under .draft/catalog/.

    A missing .draft/sdp.yaml packs a delete, which removes everything the central workspace caches for the
    product; .draft/catalog/ is not sent without an SDP.
    """
    check_repository(repository)
    sdp = repo_root / SDP_PATH
    files: dict[str, str] = {}
    action = "delete"
    if sdp.is_file():
        files = product_files(repo_root)
        action = "upsert"
    payload = {
        "format": PAYLOAD_FORMAT,
        "repository": repository,
        "commit": commit,
        "ref": ref,
        "action": action,
        "correlationId": correlation_id or uuid.uuid4().hex,
        "files": files,
    }
    if oidc_token is not None:
        payload["oidcToken"] = oidc_token
    check_size(payload)
    return payload


def audience_for(central_repository: str) -> str:
    """The OIDC audience a sender requests and a receiver requires: it names one central workspace."""
    return AUDIENCE_PREFIX + check_repository(central_repository).lower()


def request_oidc_token(audience: str, env: Mapping[str, str] | None = None,
                       opener: Callable[..., Any] = urllib.request.urlopen) -> str:
    """Ask the GitHub Actions runner for an OIDC token (the job needs permissions: id-token: write)."""
    env = os.environ if env is None else env
    url, bearer = env.get("ACTIONS_ID_TOKEN_REQUEST_URL"), env.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not url or not bearer:
        raise SyncError("no GitHub Actions OIDC token is available; the sync job needs 'permissions: id-token: write'")
    separator = "&" if "?" in url else "?"
    request = urllib.request.Request(f"{url}{separator}audience={urllib.parse.quote(audience, safe='')}",
                                     headers={"Authorization": f"Bearer {bearer}", "Accept": "application/json"})
    try:
        with opener(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8")).get("value")
    except (OSError, ValueError, AttributeError) as exc:
        raise SyncError(f"could not get a GitHub Actions OIDC token: {exc.__class__.__name__}") from None
    if not isinstance(value, str) or not _JWT.match(value):
        raise SyncError("the GitHub Actions OIDC token request returned no token")
    return value


def product_files(repo_root: Path) -> dict[str, str]:
    """.draft/sdp.yaml and every YAML file under .draft/catalog/, checked the way the receiver will check them."""
    found = [repo_root / SDP_PATH]
    catalog = repo_root / CATALOG_DIR
    if catalog.is_symlink():
        raise SyncError(f"refusing {CATALOG_DIR}: synced files cannot be symbolic links")
    if catalog.is_dir():
        for path in sorted(catalog.rglob("*")):
            if path.is_symlink():  # a linked file or folder could pull in content from outside .draft/catalog/
                raise SyncError(f"refusing {path.relative_to(repo_root).as_posix()}: synced files cannot be symbolic links")
            if path.suffix in (".yaml", ".yml"):
                found.append(path)
    files: dict[str, str] = {}
    for path in found:
        source_path = path.relative_to(repo_root).as_posix()
        if any(part.is_symlink() for part in (path, *path.parents) if repo_root in part.parents):
            raise SyncError(f"refusing {source_path}: synced files cannot be symbolic links")
        if not path.is_file():
            continue
        cache_path(source_path)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise SyncError(f"cannot read {source_path}: {exc.__class__.__name__}") from None
        kind = parse_object(source_path, text).get("type")
        if kind not in PRODUCT_OWNED_TYPES:
            raise SyncError(f"{source_path}: a product repository cannot sync a {kind!r} object; allowed types are {', '.join(PRODUCT_OWNED_TYPES)}")
        files[source_path] = text
    return files


def check_size(payload: dict[str, Any]) -> None:
    if len(payload) > MAX_TOP_LEVEL_PROPERTIES:
        raise SyncError(f"the payload has {len(payload)} top-level properties; repository_dispatch allows {MAX_TOP_LEVEL_PROPERTIES}")
    size = len(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    if size > MAX_CLIENT_PAYLOAD_BYTES:
        raise SyncError(
            f"the payload is {size} bytes; repository_dispatch accepts at most {MAX_CLIENT_PAYLOAD_BYTES}. "
            "Shorten descriptions or notes in .draft/ files, or split the product into several registrations."
        )


# --------------------------------------------------------------------------- receive


@dataclass
class Result:
    status: str  # accepted | rejected
    message: str
    repository: str = ""
    product: str = ""
    action: str = ""
    correlation_id: str = ""
    commit: str = ""
    registration: str = ""
    written: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    identity_verified: bool = False
    warnings: list[str] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {"status": self.status, "message": self.message, "repository": self.repository, "product": self.product,
                "registration": self.registration, "action": self.action, "correlationId": self.correlation_id,
                "commit": self.commit, "written": self.written, "removed": self.removed,
                "identityVerified": self.identity_verified, "warnings": self.warnings}


def product_slug(repository: str) -> str:
    """Folder name for a product's cache: owner__name, lowercase (GitHub names are case-insensitive)."""
    owner, name = check_repository(repository).lower().split("/")
    return f"{owner}__{name}"


def legacy_flat_file(workspace: Path, repository: str) -> Path:
    """Where the original receiver wrote a product's SDP (owner_name.yaml)."""
    return workspace / CACHE_ROOT / f"{repository.replace('/', '_')}.yaml"


def load_payload(path: Path) -> dict[str, Any]:
    """Read a payload file, or a GitHub event file whose client_payload is the payload."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SyncError(f"cannot read the payload file: {exc}") from exc
    if isinstance(data, dict) and isinstance(data.get("client_payload"), dict):
        data = data["client_payload"]
    if not isinstance(data, dict):
        raise SyncError("the payload is not a JSON object")
    return data


def check_payload(payload: dict[str, Any]) -> None:
    if "sdp_content" in payload and "format" not in payload:
        raise SyncError("this payload uses the old sdp_content format; update the product repository's sync workflow to the current template")
    if payload.get("format") != PAYLOAD_FORMAT:
        raise SyncError(f"unsupported payload format {payload.get('format')!r}; expected {PAYLOAD_FORMAT!r}")
    check_size(payload)
    check_repository(payload.get("repository"))
    if not isinstance(payload.get("commit"), str) or not _COMMIT.match(payload["commit"]):
        raise SyncError("the payload's commit is not a git commit SHA")
    if not isinstance(payload.get("ref"), str) or not payload["ref"].startswith("refs/"):
        raise SyncError("the payload's ref is not a git ref (refs/...)")
    if payload.get("action") not in ACTIONS:
        raise SyncError(f"the payload's action must be one of {', '.join(ACTIONS)}")
    if not isinstance(payload.get("correlationId"), str) or not _CORRELATION.match(payload["correlationId"]):
        raise SyncError("the payload's correlationId is missing or has characters other than letters, digits, '.', '_' and '-'")
    files = payload.get("files")
    if not isinstance(files, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()):
        raise SyncError("the payload's files must map each path to its text")
    if payload["action"] == "upsert" and SDP_PATH not in files:
        raise SyncError(f"an upsert must include {SDP_PATH}")
    if payload["action"] == "delete" and files:
        raise SyncError("a delete carries no files")
    if "oidcToken" not in payload:
        raise SyncError("the payload carries no OIDC token; update the product repository's sync workflow to the current template "
                        "(its job needs 'permissions: id-token: write')")
    if not isinstance(payload["oidcToken"], str) or not _JWT.match(payload["oidcToken"]):
        raise SyncError("the payload's oidcToken is not a JWT")


def cache_path(source_path: str) -> PurePosixPath:
    """Map a product-repository path to its place in the product's cache folder, refusing anything else."""
    pure = PurePosixPath(source_path)
    if pure.is_absolute() or ".." in pure.parts or "\\" in source_path or any(part.startswith(".") and part != ".draft" for part in pure.parts):
        raise SyncError(f"refusing path {source_path!r}: only files under .draft/ are synced")
    if source_path == SDP_PATH:
        return PurePosixPath("sdp.yaml")
    if pure.parts[:2] == (".draft", "catalog") and len(pure.parts) > 2 and pure.suffix in (".yaml", ".yml"):
        return PurePosixPath("catalog", *pure.parts[2:])
    raise SyncError(f"refusing path {source_path!r}: only {SDP_PATH} and YAML files under .draft/catalog/ are synced")


def parse_object(path: str, text: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SyncError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict) or not data.get("type"):
        raise SyncError(f"{path} is not a DRAFT object (a YAML mapping with a type)")
    if path == SDP_PATH and data.get("type") != "software_deployment_pattern":
        raise SyncError(f"{SDP_PATH} must be a software_deployment_pattern, not {data.get('type')!r}")
    return data


# --------------------------------------------------------------------------- identity (OIDC)


def _b64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _b64url_int(text: Any) -> int:
    if not isinstance(text, str) or not text:
        raise SyncError("GitHub's OIDC key set has a malformed RSA key")
    try:
        return int.from_bytes(_b64url(text), "big")
    except ValueError:
        raise SyncError("GitHub's OIDC key set has a malformed RSA key") from None


def rs256_verify(n: int, e: int, signing_input: bytes, signature: bytes) -> bool:
    """RSASSA-PKCS1-v1_5 with SHA-256 (RFC 8017 section 8.2.2), standard library only."""
    k = (n.bit_length() + 7) // 8
    if n.bit_length() < MIN_RSA_BITS or len(signature) != k:
        return False
    s = int.from_bytes(signature, "big")
    if s >= n:
        return False
    encoded = pow(s, e, n).to_bytes(k, "big")
    digest = _SHA256_DIGEST_INFO + hashlib.sha256(signing_input).digest()
    expected = b"\x00\x01" + b"\xff" * (k - len(digest) - 3) + b"\x00" + digest
    return hmac.compare_digest(encoded, expected)


def fetch_github_jwks(opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, Any]:
    try:
        with opener(urllib.request.Request(OIDC_JWKS_URL, headers={"Accept": "application/json"}), timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise SyncError(f"could not fetch GitHub's OIDC key set: {exc.__class__.__name__}") from None


def _signing_key(keys: KeySource, kid: str) -> tuple[int, int]:
    jwks = keys() if callable(keys) else keys
    candidates = jwks.get("keys") if isinstance(jwks, Mapping) else None
    for key in candidates if isinstance(candidates, list) else []:
        if not isinstance(key, Mapping) or key.get("kid") != kid or key.get("kty") != "RSA":
            continue
        if key.get("use", "sig") != "sig" or key.get("alg", "RS256") != "RS256":
            continue
        return _b64url_int(key.get("n")), _b64url_int(key.get("e"))
    raise SyncError(f"the OIDC token's signing key {kid!r} is not in GitHub's key set")


def verify_oidc_token(token: str, audience: str, keys: KeySource, now: float | None = None) -> dict[str, Any]:
    """Verify a GitHub Actions OIDC token's signature, issuer, audience and lifetime; return its claims."""
    try:
        header_b64, claims_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url(header_b64))
        claims = json.loads(_b64url(claims_b64))
        signature = _b64url(signature_b64)
    except ValueError:
        raise SyncError("the payload's oidcToken is not a readable JWT") from None
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise SyncError("the payload's oidcToken is not a readable JWT")
    if header.get("alg") != "RS256":
        raise SyncError(f"the OIDC token is signed with {header.get('alg')!r}; only RS256 is accepted")
    if not isinstance(header.get("kid"), str):
        raise SyncError("the OIDC token names no signing key (kid)")
    n, e = _signing_key(keys, header["kid"])
    if not rs256_verify(n, e, f"{header_b64}.{claims_b64}".encode("ascii"), signature):
        raise SyncError("the OIDC token's signature does not verify against GitHub's key set")
    if claims.get("iss") != OIDC_ISSUER:
        raise SyncError(f"the OIDC token was issued by {claims.get('iss')!r}, not GitHub Actions ({OIDC_ISSUER})")
    aud = claims.get("aud")
    if audience not in (aud if isinstance(aud, list) else [aud]):
        raise SyncError(f"the OIDC token is for audience {aud!r}, not this central workspace ({audience!r})")
    now = time.time() if now is None else now
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)) or exp + LEEWAY_SECONDS < now:
        raise SyncError("the OIDC token has expired; re-run the product repository's sync workflow")
    for name in ("nbf", "iat"):
        if isinstance(claims.get(name), (int, float)) and claims[name] - LEEWAY_SECONDS > now:
            raise SyncError(f"the OIDC token's {name} is in the future")
    return claims


# Keep this in step with validate.py _parse_github_id (#455).
_MAX_GITHUB_ID = 2**63 - 1


def parse_github_id(value: Any) -> int | None:
    """A positive GitHub numeric id, from an int or a decimal digit string. None otherwise.

    Booleans are rejected (``bool`` is a subclass of ``int``). Leading zeros are rejected so the
    pinned form is the decimal GitHub publishes. The OIDC claims are strings; ``gh api`` prints integers.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 < value <= _MAX_GITHUB_ID else None
    if isinstance(value, str):
        text = value.strip()
        if not text.isascii() or not text.isdigit() or (len(text) > 1 and text[0] == "0"):
            return None
        try:
            number = int(text)
        except ValueError:
            return None
        if 0 < number <= _MAX_GITHUB_ID:
            return number
    return None


def _registration_repo(registration: Mapping[str, Any]) -> Mapping[str, Any]:
    repo = registration.get("repository")
    return repo if isinstance(repo, Mapping) else {}


def _pinned_github_id(registration: Mapping[str, Any], field: str, claim_name: str) -> int | None:
    """The pinned id, or None when the field is absent. A present but unusable value fails closed."""
    repo = _registration_repo(registration)
    if field not in repo or repo.get(field) is None:
        return None
    parsed = parse_github_id(repo.get(field))
    if parsed is None:
        raise SyncError(
            f"ProductRegistration {registration.get('uid')} repository.{field} {repo.get(field)!r} "
            f"is not a GitHub id; a Draft Admin must set it to the permanent numeric {claim_name} "
            "from `gh api repos/OWNER/NAME --jq .id` (repository.id) or `--jq .owner.id` (repository.ownerId)"
        )
    return parsed


def _require_pinned_claim(claims: Mapping[str, Any], registration: Mapping[str, Any], pinned: int, field: str, claim_name: str) -> None:
    raw = claims.get(claim_name)
    if parse_github_id(raw) != pinned:
        shown = "missing" if raw in (None, "") else repr(raw)
        raise SyncError(
            f"the OIDC token's {claim_name} is {shown}, not {pinned} pinned on "
            f"ProductRegistration {registration.get('uid')} (repository.{field}). "
            "A renamed repository still syncs when this id matches; a deleted and recreated repository does not."
        )


def check_repository_pin(claims: Mapping[str, Any], payload: Mapping[str, Any], registration: Mapping[str, Any]) -> list[str]:
    """Enforce repository.id and repository.ownerId when the registration pins them.

    ``repository.id`` is the check that stops a deleted and recreated repository: GitHub never
    reuses ``repository_id``. ``repository.ownerId`` is checked only when set, because a new
    repository in the same organization keeps the owner id. When ``repository.id`` is omitted the
    name match from ``check_identity`` stands, and the returned warning asks a Draft Admin to pin
    the ids. This function does not write the id back; the first sync of a recreated repository
    must not be able to pin itself.
    """
    pinned_id = _pinned_github_id(registration, "id", "repository_id")
    pinned_owner = _pinned_github_id(registration, "ownerId", "repository_owner_id")
    warnings: list[str] = []
    if pinned_id is None:
        repository = str(payload.get("repository") or "")
        warnings.append(
            f"repository.id is not pinned on ProductRegistration {registration.get('uid')}; "
            f"this sync matched {repository} by repository name only. "
            "A Draft Admin should set repository.id to GitHub's permanent repository id "
            f"(`gh api repos/{repository} --jq .id`) and repository.ownerId "
            f"(`gh api repos/{repository} --jq .owner.id`) so a deleted and recreated repository cannot sync as this product. "
            "The receiver does not record the id itself."
        )
    else:
        _require_pinned_claim(claims, registration, pinned_id, "id", "repository_id")
    if pinned_owner is not None:
        _require_pinned_claim(claims, registration, pinned_owner, "ownerId", "repository_owner_id")
    return warnings


def check_identity(claims: Mapping[str, Any], payload: Mapping[str, Any], registration: Mapping[str, Any]) -> None:
    """The token must come from the registered repository's default branch, for this very commit and ref."""
    repository = str(payload["repository"]).lower()
    if str(claims.get("repository") or "").lower() != repository:
        raise SyncError(f"the OIDC token was issued to {claims.get('repository')!r}, not {payload['repository']}")
    repo = _registration_repo(registration)
    branch = repo.get("defaultBranch")
    if not isinstance(branch, str) or not branch:
        raise SyncError(f"ProductRegistration {registration.get('uid')} has no repository.defaultBranch; a Draft Admin must set it")
    expected_ref = f"refs/heads/{branch}"
    if claims.get("ref") != expected_ref:
        raise SyncError(f"the OIDC token's ref is {claims.get('ref')!r}; only the registered default branch ({expected_ref}) can sync")
    if payload["ref"] != claims.get("ref"):
        raise SyncError(f"the payload's ref {payload['ref']!r} does not match the OIDC token's ref {claims.get('ref')!r}")
    if str(claims.get("sha") or "").lower() != str(payload["commit"]).lower():
        raise SyncError("the payload's commit does not match the OIDC token's sha")


# --------------------------------------------------------------------------- acceptance


def normalize_github_url(url: Any) -> str | None:
    """owner/name (lowercase) for a GitHub repository URL in any common form, else None."""
    match = _GITHUB_URL.match(str(url or "").strip())
    return f"{match.group(1)}/{match.group(2)}".lower() if match else None


def _read_file(path: Path) -> list[dict[str, Any]]:
    try:
        docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return []  # validate.py reports unreadable files; they cannot own or define a UID here
    found = []
    for data in docs:
        for doc in data if isinstance(data, list) else [data]:
            if isinstance(doc, dict):
                found.append(doc)
    return found


def _read_objects(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    if not root.exists():
        return []
    return [(path, doc) for path in sorted(root.rglob("*")) if path.suffix in (".yaml", ".yml") and path.is_file()
            for doc in _read_file(path)]


def find_registration(workspace: Path, repository: str) -> dict[str, Any]:
    """The one ProductRegistration in the central catalog whose repository.url is this repository."""
    wanted = repository.lower()
    matches = []
    for _, obj in _read_objects(workspace / "catalog"):
        if obj.get("type") != "product_registration":
            continue
        repo = obj.get("repository") if isinstance(obj.get("repository"), dict) else {}
        if str(repo.get("provider") or "github").lower() != "github":
            continue
        if normalize_github_url(repo.get("url")) == wanted:
            matches.append(obj)
    if not matches:
        raise SyncError(f"no ProductRegistration in catalog/ has repository.url https://github.com/{repository}; "
                        "a Draft Admin registers the product before it can sync")
    if len(matches) > 1:
        uids = ", ".join(sorted(str(m.get("uid")) for m in matches))
        raise SyncError(f"several ProductRegistrations name https://github.com/{repository} ({uids}); a Draft Admin must keep one")
    return matches[0]


def uid_owners(workspace: Path, own_slug: str, own_legacy: Path) -> dict[str, str]:
    """UID -> who owns it: 'the central catalog' or another product's cache folder. The product's own cache is skipped."""
    owners: dict[str, str] = {}
    for _, obj in _read_objects(workspace / "catalog"):
        if obj.get("uid"):
            owners.setdefault(str(obj["uid"]), "the central catalog")
    cache = workspace / CACHE_ROOT
    for path, obj in _read_objects(cache):
        relative = path.relative_to(cache)
        if relative.parts[0] == own_slug or path == own_legacy:
            continue
        if obj.get("uid"):
            owners.setdefault(str(obj["uid"]), f"another product ({relative.parts[0].removesuffix('.yaml')})")
    return owners


def check_ownership(workspace: Path, repository: str, objects: dict[str, dict[str, Any]]) -> None:
    """Only product-owned types, each with a UID nobody else owns, speaking only for the product's own objects."""
    owners = uid_owners(workspace, product_slug(repository), legacy_flat_file(workspace, repository))
    seen: dict[str, str] = {}
    for path, obj in objects.items():
        kind = obj.get("type")
        if kind not in PRODUCT_OWNED_TYPES:
            raise SyncError(f"{path}: a product repository cannot sync a {kind!r} object; allowed types are {', '.join(PRODUCT_OWNED_TYPES)}")
        uid = str(obj.get("uid") or "")
        if not uid:
            raise SyncError(f"{path}: every synced object needs a uid")
        if uid in seen:
            raise SyncError(f"{path}: uid {uid} is also used by {seen[uid]}")
        seen[uid] = path
        if uid in owners:
            raise SyncError(f"{path}: uid {uid} is already owned by {owners[uid]}; a product may only sync objects it owns")
    own = set(seen)
    for path, obj in objects.items():
        claims = {
            "relationship": ("source", obj.get("source")),
            "listener": ("owner.ref", (obj.get("owner") or {}).get("ref") if isinstance(obj.get("owner"), dict) else None),
            "decision_record": ("linkedObject", obj.get("linkedObject")),
        }.get(str(obj.get("type")))
        if claims and claims[1] and str(claims[1]) not in own:
            raise SyncError(f"{path}: {claims[0]} {claims[1]} is not an object this product syncs; "
                            "a product may only record relationships, listeners and decisions for its own objects")


def referenced_uids(data: Any, refs: set[str]) -> set[str]:
    """Every UID-shaped string in an object, the way validate.py collects references."""
    if isinstance(data, str):
        if _UID.match(data):
            refs.add(data)
    elif isinstance(data, dict):
        for value in data.values():
            referenced_uids(value, refs)
    elif isinstance(data, list):
        for item in data:
            referenced_uids(item, refs)
    return refs


def known_uids(workspace: Path, own_slug: str, own_legacy: Path) -> set[str]:
    """UIDs validate.py can resolve in this workspace (framework and provider configurations, catalog/, community,
    other products' caches), leaving out this product's own previous snapshot, which the sync replaces."""
    import validate  # the receiver's framework copy; imported here so the sender needs only this file and uid_utils

    cache = (workspace / CACHE_ROOT).resolve()
    own_folder, legacy = cache / own_slug, own_legacy.resolve()
    uids: set[str] = set()
    for root in validate.workspace_yaml_roots(workspace.resolve()):
        for path in validate.discover_yaml_files(root):
            resolved = path.resolve()
            if resolved == legacy or own_folder == resolved or own_folder in resolved.parents:
                continue
            uids.update(str(doc["uid"]) for doc in _read_file(path) if doc.get("uid"))
    return uids


def check_references(workspace: Path, repository: str, objects: dict[str, dict[str, Any]]) -> None:
    """Every UID a synced object references is defined by the sync itself or already resolves in the workspace."""
    own = {str(obj.get("uid")) for obj in objects.values() if obj.get("uid")}
    known: set[str] | None = None
    unresolved = []
    for path, obj in objects.items():
        refs = referenced_uids(obj, set()) - own
        if not refs:
            continue
        if known is None:
            known = known_uids(workspace, product_slug(repository), legacy_flat_file(workspace, repository))
        missing = sorted(refs - known)
        if missing:
            unresolved.append(f"{path} references {', '.join(missing)}")
    if unresolved:
        raise SyncError("unresolved references: " + "; ".join(unresolved) + ". Each UID must be an object in this sync "
                        "or already in the central workspace; sync or register the missing object first, or fix the UID")


# --------------------------------------------------------------------------- receive


def receive(workspace: Path, payload: dict[str, Any], *, central_repository: str, keys: KeySource | None = None,
            now: float | None = None) -> Result:
    """Accept a payload from a registered product and store it in its cache folder, replaced as a snapshot.

    ``central_repository`` is this workspace's owner/name (the OIDC audience); ``keys`` is GitHub's JWKS, or a
    function returning it, and defaults to fetching it from GitHub.
    """
    registration: dict[str, Any] = {}
    verified = False
    identity_warnings: list[str] = []
    try:
        audience = audience_for(central_repository)
        check_payload(payload)
        repository = payload["repository"]
        slug = product_slug(repository)
        claims = verify_oidc_token(payload["oidcToken"], audience, fetch_github_jwks if keys is None else keys, now)
        registration = find_registration(workspace, repository)
        check_identity(claims, payload, registration)
        # The token is signed for this repository name. A pin mismatch is a registration
        # constraint on that verified sender, so the product run is told the reason.
        verified = True
        identity_warnings = check_repository_pin(claims, payload, registration)
        targets: dict[PurePosixPath, str] = {}
        objects: dict[str, dict[str, Any]] = {}
        for source_path, text in sorted(payload["files"].items()):
            target = cache_path(source_path)
            if target in targets:
                raise SyncError(f"two files map to {target}")
            objects[source_path] = parse_object(source_path, text)
            targets[target] = text
        check_ownership(workspace, repository, objects)
        check_references(workspace, repository, objects)
    except SyncError as exc:
        return Result("rejected", str(exc), repository=str(payload.get("repository") or ""),
                      action=str(payload.get("action") or ""), correlation_id=str(payload.get("correlationId") or ""),
                      commit=str(payload.get("commit") or ""), registration=str(registration.get("uid") or ""),
                      identity_verified=verified)

    folder = workspace / CACHE_ROOT / slug
    result = Result("accepted", "", repository=repository, product=slug, action=payload["action"],
                    correlation_id=payload["correlationId"], commit=payload["commit"], registration=str(registration.get("uid") or ""),
                    identity_verified=True, warnings=identity_warnings)
    if folder.exists():
        result.removed = sorted(rel(workspace, p) for p in folder.rglob("*") if p.is_file())
        shutil.rmtree(folder)
    legacy = legacy_flat_file(workspace, repository)
    if legacy.is_file():
        legacy.unlink()
        result.removed.append(rel(workspace, legacy))
    for target, text in targets.items():
        destination = folder / Path(*target.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8", newline="")
        result.written.append(rel(workspace, destination))
    result.removed = sorted(set(result.removed) - set(result.written))
    if payload["action"] == "delete":
        result.message = f"removed the cached SDP for {repository}" if result.removed else f"nothing cached for {repository}"
    else:
        result.message = f"stored {len(result.written)} file(s) for {repository} at {result.commit[:12]}"
    if result.warnings:
        result.message += " Warning: " + " ".join(result.warnings)
    return result


def rel(workspace: Path, path: Path) -> str:
    return path.relative_to(workspace).as_posix()


def check_repository(value: Any) -> str:
    if not isinstance(value, str) or not _REPOSITORY.match(value) or value.endswith((".", "/")) or ".." in value:
        raise SyncError(f"{value!r} is not a GitHub repository name (owner/name)")
    return value


# --------------------------------------------------------------------------- publish (pull request)

SYNC_BRANCH_PREFIX = "draft-sync/"
# Files the receiver workflow regenerates after every sync: run from the workspace's .draft/framework copy,
# generate_indexes.py writes docs/assets/draft-indexes.json and generate_ai_index.py writes .draft/AI_INDEX.md.
# They follow from the cache change, so they do not stop auto-merge.
DERIVED_PATHS = ("docs/assets/draft-indexes.json", ".draft/AI_INDEX.md")
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38})__[a-z0-9._-]{1,100}$")
_BRANCH = re.compile(r"^[A-Za-z0-9._][A-Za-z0-9._/-]{0,199}$")
_PR_URL = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/(\d+)")
Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


def subprocess_runner(cwd: Path) -> Runner:
    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    return run


def _ok(run: Runner, args: list[str], what: str) -> str:
    proc = run(args)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise SyncError(f"{what} failed (exit {proc.returncode}){': ' + detail[-1] if detail else ''}")
    return proc.stdout or ""


def changed_paths(run: Runner) -> list[str]:
    """Paths git reports as changed or untracked, without Python bytecode the tools leave behind."""
    out = _ok(run, ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], "git status")
    entries, paths = out.split("\0"), []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        paths.append(path)
        if status[0] in "RC" and index < len(entries):  # a rename or copy is followed by its source path
            paths.append(entries[index])
            index += 1
    keep = [p for p in paths if "__pycache__" not in PurePosixPath(p).parts and not p.endswith(".pyc")]
    return sorted(set(keep))


def is_confined(paths: list[str], product: str, repository: str) -> bool:
    """True when the change is the product's cache folder (plus regenerated indexes) and nothing else."""
    folder = f"{CACHE_ROOT.as_posix()}/{product}/"
    legacy = f"{CACHE_ROOT.as_posix()}/{repository.replace('/', '_')}.yaml"
    in_cache = [p for p in paths if p.startswith(folder) or p == legacy]
    return bool(in_cache) and all(p in in_cache or p in DERIVED_PATHS for p in paths)


def _pr_body(result: Mapping[str, Any], paths: list[str], confined: bool) -> str:
    listed = "\n".join(f"- `{p}`" for p in paths[:200]) + ("\n- ..." if len(paths) > 200 else "")
    return (
        f"Decentralized SDP sync from `{result['repository']}` at `{result['commit']}`.\n\n"
        f"- Product registration: `{result.get('registration') or 'unknown'}`\n"
        f"- Action: `{result.get('action')}`\n"
        f"- Correlation id: `{result.get('correlationId')}`\n"
        f"- Confined to the product's cache folder: {'yes' if confined else 'no'}\n\n"
        f"Changed files:\n\n{listed}\n\n"
        "Opened by the DRAFT receiver workflow (`sdp_sync.py publish`). Later syncs from the same product update this "
        "pull request; merging it is what changes the central catalog.\n"
    )


def publish(result: Mapping[str, Any], base: str, run: Runner, auto_merge: bool = False) -> dict[str, Any]:
    """Commit the receiver's changes to draft-sync/<product> and open or update its pull request against base."""
    if result.get("status") != "accepted":
        raise SyncError("only an accepted sync can be published")
    product, repository, commit = str(result.get("product") or ""), check_repository(result.get("repository")), str(result.get("commit") or "")
    if not _SLUG.match(product) or product != product_slug(repository):
        raise SyncError(f"the result names an invalid product {product!r}")
    if not _COMMIT.match(commit):
        raise SyncError("the result's commit is not a git commit SHA")
    if not _BRANCH.match(base) or ".." in base or base.endswith(("/", ".lock")):
        raise SyncError(f"{base!r} is not a branch name")
    branch = SYNC_BRANCH_PREFIX + product
    outcome: dict[str, Any] = {"status": "unchanged", "branch": branch, "base": base, "changed": [], "confined": False,
                               "pullRequest": None, "autoMerge": "off"}
    paths = changed_paths(run)
    if not paths:
        return outcome
    confined = is_confined(paths, product, repository)
    outcome.update(changed=paths, confined=confined, status="published")
    title = f"DRAFT sync: {repository} at {commit[:12]}"
    _ok(run, ["git", "checkout", "-B", branch], "git checkout")
    _ok(run, ["git", "add", "-A", "--", *paths], "git add")
    _ok(run, ["git", "-c", f"user.name={BOT_NAME}", "-c", f"user.email={BOT_EMAIL}", "commit", "--no-verify", "-m", title,
              "-m", f"correlation id {result.get('correlationId')}"], "git commit")
    # The branch is the receiver's own: each sync is a fresh snapshot on top of the default branch.
    ours = _commit_sha(_ok(run, ["git", "rev-parse", "HEAD"], "git rev-parse"), "the commit that was just created")
    _push_sync_branch(run, branch)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(_pr_body(result, paths, confined))
        body_file = handle.name
    try:
        listed = json.loads(_ok(run, ["gh", "pr", "list", "--head", branch, "--base", base, "--state", "open",
                                      "--json", "number,url", "--limit", "1"], "gh pr list") or "[]")
        if listed:
            number, url = int(listed[0]["number"]), str(listed[0]["url"])
            _ok(run, ["gh", "pr", "edit", str(number), "--title", title, "--body-file", body_file], "gh pr edit")
            outcome["pullRequestAction"] = "updated"
        else:
            out = _ok(run, ["gh", "pr", "create", "--base", base, "--head", branch, "--title", title, "--body-file", body_file],
                      "gh pr create")
            match = _PR_URL.search(out)
            if not match:
                raise SyncError("gh pr create did not print a pull request URL")
            number, url = int(match.group(1)), match.group(0)
            outcome["pullRequestAction"] = "opened"
    finally:
        Path(body_file).unlink(missing_ok=True)
    # For a pull_request opened run, workflow_run.actor is whoever opened the pull request, not who pushed
    # the tip. Anything that replaced the branch between the push and gh pr create would be opened by this
    # App. Close that pull request, try to cancel validation of the other commit, put our commit back, and fail.
    _require_published_head(run, branch, number, ours)
    outcome["pullRequest"] = {"number": number, "url": url}
    outcome["head"] = ours
    if auto_merge and confined:
        # Arms GitHub auto-merge for a later approval. Auto-merge does not honor a ruleset bypass actor, so a
        # required review stays unsatisfied until a person approves. The receiver App calls `merge` instead.
        proc = run(["gh", "pr", "merge", str(number), "--auto", "--squash"])
        outcome["autoMerge"] = "enabled" if proc.returncode == 0 else "failed"
    elif outcome["pullRequestAction"] == "updated":
        # An earlier, confined sync may have turned auto-merge on; this change needs a reviewer.
        run(["gh", "pr", "merge", str(number), "--disable-auto"])
        outcome["autoMerge"] = "off" if not auto_merge else "off: the change reaches outside the product's cache folder"
    elif auto_merge:
        outcome["autoMerge"] = "off: the change reaches outside the product's cache folder"
    return outcome


_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def changes_from_name_status(text: str) -> list[tuple[str, str]]:
    """`(status, path)` pairs from `git diff --name-status`, both sides of a rename or copy."""
    changes: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status[:1] in "RC" and len(parts) >= 3:
            changes.append((status, parts[1]))
            changes.append((status, parts[2]))
        elif len(parts) >= 2:
            changes.append((status, parts[1]))
        else:
            changes.append(("?", line.strip()))  # unparsed output is not a cache path, so confinement fails closed
    return changes


def paths_from_name_status(text: str) -> list[str]:
    """Every path in `git diff --name-status`, including both sides of a rename or copy."""
    return sorted({path for _, path in changes_from_name_status(text)})


def _sync_branch(head: str) -> tuple[str, str] | None:
    """The product slug and repository for a draft-sync/<owner>__<name> branch, or None."""
    if not head.startswith(SYNC_BRANCH_PREFIX) or not _BRANCH.match(head):
        return None
    product = head[len(SYNC_BRANCH_PREFIX):]
    if not _SLUG.match(product):
        return None
    repository = product.replace("__", "/", 1)
    try:
        check_repository(repository)
    except SyncError:
        return None
    if product != product_slug(repository):
        return None
    return product, repository


_APP_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")
_HTTP_STATUS = re.compile(r"HTTP/\d+(?:\.\d+)?\s+(\d{3})\b")


def app_bot_login(slug: str) -> str:
    """The GitHub user login of an App, `<slug>[bot]`."""
    normalized = str(slug or "").strip().lower()
    if not _APP_SLUG.match(normalized):
        raise SyncError("the receiver App slug is not a GitHub App slug")
    return f"{normalized}[bot]"


def _require_receiver_pusher(pusher: str, slug: str) -> str:
    """The validating run's original pusher must be the receiver App. `triggering_actor` changes on re-run."""
    bot = app_bot_login(slug)
    if str(pusher or "").strip().lower() != bot.lower():
        raise SyncError(f"the validated commit was pushed by {pusher or 'unknown'}, not {bot}")
    return bot


def merge_confined(changes: list[tuple[str, str]], product: str, repository: str) -> bool:
    """`is_confined` for an unattended merge. The legacy flat file counts only when it is deleted.

    `owner_name.yaml` is the same path for `owner/name` and for some other `owner_name` repositories
    (`foo/bar_baz` and `foo_bar/baz`). Adding or editing that file must not count as this product's cache.
    """
    legacy = f"{CACHE_ROOT.as_posix()}/{repository.replace('/', '_')}.yaml"
    paths: list[str] = []
    for status, path in changes:
        if path == legacy:
            if not status.startswith("D"):
                return False
            continue
        paths.append(path)
    return is_confined(paths, product, repository)


def _commit_sha(text: str, what: str) -> str:
    token = text.strip().split()[0].lower() if text.strip() else ""
    if not _FULL_SHA.match(token):
        raise SyncError(f"{what} is not a full git commit SHA")
    return token


def _sha_or_blank(text: str) -> str:
    token = text.strip().split()[0].lower() if text.strip() else ""
    return token if _FULL_SHA.match(token) else ""


def _push_sync_branch(run: Runner, branch: str) -> None:
    _ok(run, ["git", "push", "--force", "origin", f"HEAD:refs/heads/{branch}"], "git push")


# The merge workflow listens for this workflow name. Cancel looks for the same name.
VALIDATE_WORKFLOW_NAME = "Validate Catalog"
_CANCEL_RUN_STATUSES = frozenset({"in_progress", "queued", "waiting", "requested", "pending"})


def _command_detail(proc: subprocess.CompletedProcess[str]) -> str:
    text = f"{proc.stderr or ''}\n{proc.stdout or ''}".strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else f"exit {proc.returncode}"


def _close_replaced_pull_request(run: Runner, number: int, ours: str, tip: str, pr_head: str) -> str:
    """Comment on and close the pull request that was opened on a commit this publish did not push."""
    comment = (
        "Closing this pull request. The sync branch moved while the receiver was publishing "
        f"(receiver commit `{ours}`, branch tip `{tip or 'unknown'}`, pull request head `{pr_head or 'unknown'}`). "
        "The receiver is putting its own commit back on the branch. A validation of the other commit must not be merged. "
        "Ruleset C on `draft-sync/**` is still required."
    )
    noted = run(["gh", "pr", "comment", str(number), "--body", comment])
    closed = run(["gh", "pr", "close", str(number)])
    problems = []
    if noted.returncode != 0:
        problems.append(f"the comment failed ({_command_detail(noted)})")
    if closed.returncode != 0:
        problems.append(f"the close failed ({_command_detail(closed)})")
    if problems:
        return f"pull request {number} stayed open: " + "; ".join(problems)
    return f"closed pull request {number}"


def _cancel_validate_runs(run: Runner, shas: list[str]) -> str:
    """Cancel in-progress Validate Catalog runs for these commits, when the token in use is allowed to.

    Publish's token has contents write and pull-requests write. It often cannot call the Actions API.
    A refusal is recorded and does not replace the publish failure. Ruleset C is still required.
    """
    notes: list[str] = []
    for sha in shas:
        proc = run(["gh", "run", "list", "--commit", sha, "--workflow", VALIDATE_WORKFLOW_NAME,
                    "--json", "databaseId,status,workflowName,headSha", "--limit", "20"])
        if proc.returncode != 0:
            notes.append(f"could not list {VALIDATE_WORKFLOW_NAME} runs for {sha} ({_command_detail(proc)})")
            continue
        try:
            listed = json.loads(proc.stdout or "[]")
        except ValueError:
            notes.append(f"could not read {VALIDATE_WORKFLOW_NAME} runs for {sha}")
            continue
        if not isinstance(listed, list):
            notes.append(f"could not read {VALIDATE_WORKFLOW_NAME} runs for {sha}")
            continue
        found = False
        for item in listed:
            if not isinstance(item, dict):
                continue
            workflow = str(item.get("workflowName") or VALIDATE_WORKFLOW_NAME)
            if workflow != VALIDATE_WORKFLOW_NAME:
                continue
            head = str(item.get("headSha") or "").lower()
            if head and head != sha:
                continue
            if str(item.get("status") or "") not in _CANCEL_RUN_STATUSES:
                continue
            run_id = item.get("databaseId")
            if isinstance(run_id, str) and run_id.isdigit():
                run_id = int(run_id)
            if not isinstance(run_id, int):
                continue
            found = True
            cancel = run(["gh", "run", "cancel", str(run_id)])
            if cancel.returncode != 0:
                notes.append(f"could not cancel {VALIDATE_WORKFLOW_NAME} run {run_id} for {sha} ({_command_detail(cancel)})")
            else:
                notes.append(f"cancelled {VALIDATE_WORKFLOW_NAME} run {run_id} for {sha}")
        if not found:
            notes.append(f"no in-progress {VALIDATE_WORKFLOW_NAME} run for {sha}")
    return "; ".join(notes)


def _require_published_head(run: Runner, branch: str, number: int, ours: str) -> None:
    """The remote tip and the pull request head must still be the commit this publish pushed.

    A mismatch closes the pull request and, when the token can, cancels Validate Catalog runs for the
    other commit, then force-pushes this publish's commit again. That stops the merge workflow from
    accepting a pull request the receiver App opened on someone else's commit. It does not stop the
    other push itself, and the token may not be allowed to cancel workflow runs. Ruleset C is still required.
    """
    tip = _sha_or_blank(_ok(run, ["git", "ls-remote", "origin", f"refs/heads/{branch}"], "git ls-remote"))
    pr_head = _sha_or_blank(_ok(run, ["gh", "pr", "view", str(number), "--json", "headRefOid", "--jq", ".headRefOid"],
                                "gh pr view"))
    if tip == ours and pr_head == ours:
        return
    foreign: list[str] = []
    for candidate in (tip, pr_head):
        if candidate and candidate != ours and candidate not in foreign:
            foreign.append(candidate)
    close_note = _close_replaced_pull_request(run, number, ours, tip, pr_head)
    cancel_note = _cancel_validate_runs(run, foreign)
    _push_sync_branch(run, branch)
    raise SyncError(
        f"the sync branch {branch} moved during publish (pushed {ours}, branch tip {tip or 'unknown'}, "
        f"pull request head {pr_head or 'unknown'}); {close_note}; restored {ours} and refused to publish"
        + (f"; {cancel_note}" if cancel_note else "")
    )


def _head_moved(status: int, detail: str) -> bool:
    """A moved head is a skip. Merge reports that as HTTP 409; update-branch reports expected_head_sha as HTTP 422."""
    text = detail.lower()
    if status == 409 and ("head branch was modified" in text or ("sha" in text and "head" in text and "must match" in text)):
        return True
    # update-branch: {"message":"expected_head_sha ..."} with HTTP 422. Other 422s still fail the job.
    return status == 422 and ("expected_head_sha" in text or "expected head sha" in text)


def _http_status(text: str) -> int | None:
    match = _HTTP_STATUS.search(text)
    return int(match.group(1)) if match else None


def _api(run: Runner, args: list[str]) -> tuple[int, str]:
    """Call `gh api -i`. Returns the HTTP status and the combined output. Status 0 means the call failed without one."""
    proc = run(["gh", "api", "-i", *args])
    blob = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    status = _http_status(blob)
    if proc.returncode != 0:
        return status or 0, blob.strip()
    return status or 200, proc.stdout or ""


def _json_body(stdout: str) -> Any:
    body = stdout
    if body.lstrip().startswith("HTTP/"):
        pieces = re.split(r"\r?\n\r?\n", body, maxsplit=1)
        body = pieces[1] if len(pieces) > 1 else ""
    return json.loads(body or "null")


# generate_ai_index.py writes next to its own framework checkout. Point that module at the worktree
# and run the copy of the tool from the default-branch checkout, which is the trusted one.
_RETARGET_AI_INDEX = """
import importlib.util
import sys
from pathlib import Path

script, root, output = sys.argv[1:]
spec = importlib.util.spec_from_file_location("draft_generate_ai_index_retarget", script)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load generate_ai_index")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.REPO_ROOT = Path(root)
module.FRAMEWORK_ROOT = Path(root) / "framework"
module.OUTPUT_PATH = Path(output)
module.main()
"""


def _trusted_generator_paths(workspace: Path) -> tuple[Path, Path] | None:
    """`generate_indexes.py` and `generate_ai_index.py` from this checkout, company layout first."""
    for tools in (workspace / ".draft" / "framework" / "tools", workspace / "framework" / "tools"):
        indexes, ai_index = tools / "generate_indexes.py", tools / "generate_ai_index.py"
        if indexes.is_file() and ai_index.is_file():
            return indexes, ai_index
    return None


def _ai_index_target(worktree: Path, tools: Path) -> tuple[Path, Path]:
    """The `REPO_ROOT` and output path that copy of `generate_ai_index.py` uses in a workspace."""
    if tools.parent.parent.name == ".draft":
        root = worktree / ".draft"
        return root, root / "AI_INDEX.md"
    return worktree, worktree / "AI_INDEX.md"


def _regenerate_shared_indexes(run: Runner, workspace: Path, worktree: Path) -> bool:
    """Rewrite the worktree's shared index files with the trusted generators. False when that cannot be done."""
    found = _trusted_generator_paths(workspace)
    if found is None:
        return False
    indexes, ai_index = found
    output = worktree / "docs" / "assets" / "draft-indexes.json"
    generated = run([sys.executable, str(indexes), "--workspace", str(worktree), "--output", str(output)])
    if generated.returncode != 0:
        return False
    root, ai_output = _ai_index_target(worktree, indexes.parent)
    retargeted = run([sys.executable, "-c", _RETARGET_AI_INDEX, str(ai_index), str(root), str(ai_output)])
    return retargeted.returncode == 0


def _updated_head_index_drift(run: Runner, workspace: Path, sha: str) -> str | None:
    """Why an updated head must not be merged, or None when this head may be merged.

    ``update-branch`` merges the default branch into the sync branch. The new head has two parents, and
    ``docs/assets/draft-indexes.json`` and ``.draft/AI_INDEX.md`` can be a blend of the two sides. A head
    with one parent is the receiver's own sync commit: the receiver already ran these generators, and this
    check does not run again. A blend is not merged and is not rewritten here, because a rewritten commit
    would not be the commit ``validate`` just passed. The next sync rebuilds the branch from the default branch.
    """
    proc = run(["git", "rev-parse", f"{sha}^@"])
    if proc.returncode != 0:
        return "could not read the parents of the validated head, so it was not merged"
    parents = [token.lower() for token in (proc.stdout or "").split() if _FULL_SHA.match(token.lower())]
    if len(parents) < 2:
        return None
    worktree = Path(tempfile.mkdtemp(prefix="sdp-index-"))
    try:
        added = run(["git", "worktree", "add", "--detach", str(worktree), sha])
        if added.returncode != 0:
            return "could not check out the updated head to regenerate the shared index files, so it was not merged"
        if not _regenerate_shared_indexes(run, workspace, worktree):
            return "the trusted index generators failed on the updated head, so it was not merged; the next sync rebuilds the branch"
        status = run(["git", "-C", str(worktree), "status", "--porcelain", "--", *DERIVED_PATHS])
        if status.returncode != 0:
            return "could not compare the shared index files on the updated head, so it was not merged"
        if (status.stdout or "").strip():
            listed = ", ".join(DERIVED_PATHS)
            return (f"the shared index files on the updated head are not what the trusted generators write ({listed}); "
                    "the next sync rebuilds the branch")
        return None
    finally:
        run(["git", "worktree", "remove", "--force", str(worktree)])
        shutil.rmtree(worktree, ignore_errors=True)


def merge_sync_pull_request(central: str, base: str, sha: str, head: str, run: Runner, auto_merge: bool = False,
                            pusher: str = "", app_slug: str = "", workspace: Path | None = None) -> dict[str, Any]:
    """Squash-merge the receiver App's confined sync pull request at this exact head SHA.

    The pusher is `workflow_run.actor` of the validating run (the account that triggered it initially).
    For a `synchronize` run that is the pusher; for an `opened` run it is whoever opened the pull request,
    which is why `publish` checks the branch tip after it opens the pull request.
    `triggering_actor` is whoever started the latest attempt and changes on re-run, so it is not used.
    GitHub auto-merge ignores a ruleset bypass actor, so this calls the merge API and passes ``sha``.
    A pull request opened by another account, including an older sync pull request from ``github-actions[bot]``,
    is skipped. Close it once so the next sync opens a new one as the receiver App.
    A pull request that is behind its base is updated instead of merged. The next green validation merges
    that head only when it is still one parent, or when its shared index files match a fresh run of the
    trusted generators. A blend is left for the next sync.
    """
    central = check_repository(central)
    if not auto_merge:
        return {"status": "skipped", "message": "DRAFT_SYNC_AUTO_MERGE is not true"}
    bot = _require_receiver_pusher(pusher, app_slug)
    sha = str(sha).lower()
    if not _FULL_SHA.match(sha):
        raise SyncError("the head SHA is not a full git commit SHA")
    found = _sync_branch(head)
    if found is None:
        return {"status": "skipped", "message": "the head is not a draft-sync product branch"}
    product, repository = found
    if not _BRANCH.match(base) or ".." in base or base.startswith("-") or base.endswith(("/", ".lock")):
        raise SyncError(f"{base!r} is not a branch name")
    _ok(run, ["git", "fetch", "--no-tags", "origin", f"+refs/heads/{base}:refs/remotes/origin/{base}",
              f"+refs/heads/{head}:refs/remotes/origin/{head}"], "git fetch")
    fetched = _ok(run, ["git", "rev-parse", f"refs/remotes/origin/{head}"], "git rev-parse").strip().lower()
    if fetched != sha:
        return {"status": "skipped", "message": "the branch head moved after this validation run"}
    diff = _ok(run, ["git", "diff", "--name-status", "--find-renames",
                     f"refs/remotes/origin/{base}...refs/remotes/origin/{head}"], "git diff")
    changes = changes_from_name_status(diff)
    if not merge_confined(changes, product, repository):
        return {"status": "left-open", "message": "the change reaches outside the product's cache folder",
                "changed": sorted({path for _, path in changes})}
    status, body = _api(run, [f"repos/{central}/commits/{sha}/pulls"])
    if status != 200:
        raise SyncError(f"listing pull requests for the commit failed (HTTP {status})")
    listed = _json_body(body)
    if not isinstance(listed, list):
        raise SyncError("the pull request list was not a JSON array")
    matches = []
    for pr in listed:
        if not isinstance(pr, dict):
            continue
        head_info, base_info = pr.get("head") or {}, pr.get("base") or {}
        head_repo = ((head_info.get("repo") or {}) if isinstance(head_info, dict) else {}).get("full_name") or ""
        if (str(pr.get("state")) == "open" and isinstance(head_info, dict) and isinstance(base_info, dict)
                and str(head_info.get("ref")) == head and str(head_info.get("sha") or "").lower() == sha
                and str(head_repo).lower() == central.lower() and str(base_info.get("ref")) == base):
            matches.append(pr)
    if not matches:
        return {"status": "skipped", "message": "no open same-repository pull request for this head SHA"}
    if len(matches) != 1:
        raise SyncError("more than one open pull request matches this head SHA")
    author = str((matches[0].get("user") or {}).get("login") or "")
    number = int(matches[0]["number"])
    url = str(matches[0].get("html_url") or f"https://github.com/{central}/pull/{number}")
    if author.lower() != bot.lower():
        # Pre-existing sync pull requests were opened by github-actions[bot]. Failing the job on every
        # green validate would block later syncs. Close that pull request once; the next publish opens a new one.
        return {"status": "skipped", "message": f"the pull request was opened by {author or 'unknown'}, not {bot}; "
                "close it once so the receiver App can open a new one",
                "pullRequest": {"number": number, "url": url}}
    compare_status, compare_body = _api(run, [f"repos/{central}/compare/{base}...{sha}"])
    if compare_status != 200:
        raise SyncError(f"comparing the pull request with {base} failed (HTTP {compare_status})")
    compare = _json_body(compare_body)
    behind = int(compare.get("behind_by") or 0) if isinstance(compare, dict) else 0
    if behind > 0:
        # An App update-branch push retriggers validate. The next workflow_run's actor is still this App.
        update_status, update_body = _api(run, ["--method", "PUT", f"repos/{central}/pulls/{number}/update-branch",
                                                "-f", f"expected_head_sha={sha}"])
        if update_status != 200 and _head_moved(update_status, update_body):
            return {"status": "skipped", "message": "the head SHA moved before the branch update"}
        if not 200 <= update_status < 300:
            last = update_body.splitlines()[-1] if update_body else ""
            raise SyncError(f"updating the pull request branch failed (HTTP {update_status})" + (f": {last}" if last else ""))
        return {"status": "updated", "message": f"updated {url} onto {base}; waiting for validate on the new head",
                "pullRequest": {"number": number, "url": url}, "sha": sha}
    drift = _updated_head_index_drift(run, Path(workspace) if workspace is not None else Path("."), sha)
    if drift:
        return {"status": "skipped", "message": drift, "pullRequest": {"number": number, "url": url}, "sha": sha}
    merge_status, merge_body = _api(run, ["--method", "PUT", f"repos/{central}/pulls/{number}/merge",
                                          "-f", "merge_method=squash", "-f", f"sha={sha}"])
    if _head_moved(merge_status, merge_body):
        return {"status": "skipped", "message": "the head SHA moved before merge"}
    if not 200 <= merge_status < 300:
        last = merge_body.splitlines()[-1] if merge_body else ""
        raise SyncError(f"merge failed (HTTP {merge_status})" + (f": {last}" if last else ""))
    return {"status": "merged", "message": f"merged {url} at {sha}", "pullRequest": {"number": number, "url": url}, "sha": sha}


# --------------------------------------------------------------------------- report back (#195 gap 7)

# The receiver records every outcome as results/<owner>__<name>/<correlationId>.json on this branch, with the
# GITHUB_TOKEN contents permission it already has. The sender reads it with the App token it already uses for
# the dispatch (contents access on the central repository), so reporting back needs no new permission.
RESULTS_BRANCH = "draft-sync-results"
MAX_REPORTED_LINES = 20
MAX_MESSAGE_CHARS = 6000


def result_path(repository: str, correlation_id: str) -> str:
    if not isinstance(correlation_id, str) or not _CORRELATION.match(correlation_id):
        raise SyncError("the correlation id is missing or has characters other than letters, digits, '.', '_' and '-'")
    return f"results/{product_slug(repository)}/{correlation_id}.json"


def validation_failures(log: str, workspace: Path | None = None, product: str = "") -> list[str]:
    """The 'Validation failures:' lines from validate.py output, this product's cache first, paths made relative."""
    lines: list[str] = []
    inside = False
    for line in log.splitlines():
        if line.strip() == "Validation failures:":
            inside = True
        elif inside and line.startswith("- "):
            lines.append(line[2:])
        elif inside and line.strip():
            break  # the next section ("Validation warnings:")
    if workspace is not None:
        prefix = str(workspace.resolve()) + "/"
        lines = [line.replace(prefix, "") for line in lines]
    mine = f"{CACHE_ROOT.as_posix()}/{product}/" if product else None
    return sorted(lines, key=lambda line: 0 if mine and mine in line else 1)


def final_outcome(result: Mapping[str, Any] | None, payload: Mapping[str, Any] | None, job_status: str,
                  validate_log: str = "", workspace: Path | None = None, run_url: str = "") -> dict[str, Any]:
    """One outcome for the whole receiver run: accepted, rejected, or failed (with the reason)."""
    source = result or payload or {}
    outcome: dict[str, Any] = {
        "format": "draft-sdp-sync-result/1",
        "repository": str(source.get("repository") or ""), "correlationId": str(source.get("correlationId") or ""),
        "commit": str(source.get("commit") or ""), "action": str(source.get("action") or ""),
        "product": str((result or {}).get("product") or ""), "registration": str((result or {}).get("registration") or ""),
        "receiverRun": run_url, "jobStatus": job_status, "pullRequest": None, "details": [],
        # Only a sync whose OIDC identity was verified is recorded where its product repository looks for it.
        "identityVerified": bool((result or {}).get("identityVerified")),
    }
    publish_outcome = (result or {}).get("publish") if isinstance((result or {}).get("publish"), dict) else None
    if result is None:
        outcome.update(status="failed", message=f"the central receiver stopped before it could check this sync (job {job_status or 'unknown'}); "
                                                "see the receiver run")
    elif result.get("status") != "accepted":
        outcome.update(status="rejected", message=str(result.get("message") or "rejected"))
    elif publish_outcome and publish_outcome.get("status") == "failed":
        outcome.update(status="failed", message="the sync was stored and validated, but opening its pull request failed: "
                                                f"{publish_outcome.get('message')}")
    elif publish_outcome:
        pr = publish_outcome.get("pullRequest") or None
        outcome.update(status="accepted", pullRequest=pr, autoMerge=publish_outcome.get("autoMerge"),
                       message=(f"{publish_outcome.get('pullRequestAction', 'updated')} pull request {pr['url']}" if pr
                                else "accepted; the central workspace already matches this sync"))
    else:
        failures = validation_failures(validate_log, workspace, outcome["product"])
        if failures:
            outcome.update(status="failed", details=failures[:MAX_REPORTED_LINES],
                           message=f"the central workspace does not validate with this sync ({len(failures)} failure(s)); "
                                   "fix them in the product repository and push again")
        else:
            outcome.update(status="failed", message=f"the sync was accepted but a later receiver step did not finish (job {job_status or 'unknown'}); "
                                                    "see the receiver run")
    outcome["message"] = _with_receive_warnings(outcome["message"], result)[:MAX_MESSAGE_CHARS]
    if isinstance(result, Mapping) and isinstance(result.get("warnings"), list):
        listed = [str(item) for item in result["warnings"] if item]
        if listed:
            outcome["warnings"] = listed
    return outcome


def _with_receive_warnings(message: str, result: Mapping[str, Any] | None) -> str:
    """Append receive's registration warnings so the product run sees an unpinned repository.id."""
    if not isinstance(result, Mapping) or not isinstance(result.get("warnings"), list):
        return message
    text = " ".join(str(item) for item in result["warnings"] if item)
    if not text:
        return message
    return f"{message} Warning: {text}"


def summary_markdown(outcome: Mapping[str, Any], heading: str = "DRAFT SDP sync") -> str:
    icon = {"accepted": "Accepted", "rejected": "Rejected", "failed": "Failed"}.get(str(outcome.get("status")), str(outcome.get("status")))
    lines = [f"## {heading}: {icon}", "", str(outcome.get("message") or ""), "",
             f"- Product repository: `{outcome.get('repository') or 'unknown'}`",
             f"- Commit: `{outcome.get('commit') or 'unknown'}`",
             f"- Correlation id: `{outcome.get('correlationId') or 'unknown'}`"]
    if outcome.get("pullRequest"):
        lines.append(f"- Pull request: {outcome['pullRequest']['url']}")
    if outcome.get("receiverRun"):
        lines.append(f"- Central receiver run: {outcome['receiverRun']}")
    if outcome.get("details"):
        lines += ["", "```", *[str(d) for d in outcome["details"]], "```"]
    return "\n".join(lines) + "\n"


def store_outcome(outcome: Mapping[str, Any], central_repository: str, base: str, run: Runner) -> str:
    """Write the outcome to RESULTS_BRANCH through the contents API (gh, argument lists only).

    Only outcomes whose sender identity was verified are written: an unauthenticated payload cannot plant a result
    where a product repository will read it.
    """
    if not outcome.get("identityVerified"):
        raise SyncError("the sender's identity was not verified, so the result is shown in this run's summary only")
    check_repository(central_repository)
    if not _BRANCH.match(base) or ".." in base:
        raise SyncError(f"{base!r} is not a branch name")
    path = result_path(str(outcome.get("repository")), str(outcome.get("correlationId")))
    api = f"repos/{central_repository}"
    if run(["gh", "api", f"{api}/git/ref/heads/{RESULTS_BRANCH}", "--jq", ".object.sha"]).returncode != 0:
        sha = _ok(run, ["gh", "api", f"{api}/git/ref/heads/{base}", "--jq", ".object.sha"], "reading the default branch").strip()
        created = run(["gh", "api", "--method", "POST", f"{api}/git/refs", "-f", f"ref=refs/heads/{RESULTS_BRANCH}", "-f", f"sha={sha}"])
        if created.returncode != 0 and run(["gh", "api", f"{api}/git/ref/heads/{RESULTS_BRANCH}"]).returncode != 0:
            raise SyncError(f"could not create the {RESULTS_BRANCH} branch")
    content = base64.b64encode((json.dumps(outcome, indent=2) + "\n").encode("utf-8")).decode("ascii")
    put = ["gh", "api", "--method", "PUT", f"{api}/contents/{path}", "-f", f"message=DRAFT sync result {outcome.get('correlationId')}",
           "-f", f"content={content}", "-f", f"branch={RESULTS_BRANCH}"]
    if run(put).returncode != 0:
        # The file exists (the report step was re-run): update it in place.
        sha = _ok(run, ["gh", "api", f"{api}/contents/{path}?ref={RESULTS_BRANCH}", "--jq", ".sha"], "reading the existing result").strip()
        _ok(run, [*put, "-f", f"sha={sha}"], "writing the sync result")
    return path


def annotation(text: str) -> str:
    """Escape text for a GitHub Actions workflow command, so a message cannot start a command of its own."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def github_contents_fetcher(central_repository: str, token: str, opener: Callable[..., Any] = urllib.request.urlopen,
                            api: str = "https://api.github.com") -> Callable[[str], bytes | None]:
    """GET a file from RESULTS_BRANCH; None while it does not exist yet."""
    check_repository(central_repository)

    def fetch(path: str) -> bytes | None:
        url = f"{api}/repos/{central_repository}/contents/{urllib.parse.quote(path)}?ref={RESULTS_BRANCH}"
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.raw+json",
                                                       "X-GitHub-Api-Version": "2022-11-28"})
        try:
            with opener(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise SyncError(f"reading the central result failed with HTTP {exc.code}; the App token needs contents access "
                            "to the central repository") from None
        except OSError as exc:
            raise SyncError(f"reading the central result failed: {exc.__class__.__name__}") from None
    return fetch


def await_result(repository: str, correlation_id: str, fetch: Callable[[str], bytes | None], timeout: float = 1200,
                 interval: float = 15, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """Poll for the receiver's outcome of this sync; transient read errors are retried until the timeout."""
    path = result_path(check_repository(repository), correlation_id)
    deadline = clock() + timeout
    last_error = ""
    while True:
        try:
            data = fetch(path)
        except SyncError as exc:
            data, last_error = None, str(exc)
            if "HTTP 401" in last_error or "HTTP 403" in last_error:
                raise
        if data is not None:
            try:
                outcome = json.loads(data.decode("utf-8"))
            except ValueError:
                outcome = None
            if (isinstance(outcome, dict) and outcome.get("correlationId") == correlation_id
                    and str(outcome.get("repository")).lower() == repository.lower()):
                return outcome
        if clock() >= deadline:
            raise SyncError(f"no result from the central receiver after {int(timeout)} seconds{' (' + last_error + ')' if last_error else ''}; "
                            "it may be queued behind other syncs or have failed to start; check the central repository's Actions")
        sleep(interval)


# --------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pack or receive a decentralized SDP sync payload (#195).")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pack", help="Build the client_payload in a product repository.")
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--repository", required=True, help="owner/name of the product repository")
    p.add_argument("--commit", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--correlation-id")
    p.add_argument("--central-repository", help="owner/name of the central workspace; attaches a GitHub Actions OIDC token for it")
    p.add_argument("--output", type=Path, required=True)
    r = sub.add_parser("receive", help="Store a payload in the central workspace.")
    r.add_argument("--workspace", type=Path, default=Path("."))
    r.add_argument("--payload", type=Path, required=True, help="payload JSON, or a GitHub event file with client_payload")
    r.add_argument("--central-repository", required=True, help="owner/name of this central workspace (the OIDC audience)")
    r.add_argument("--jwks", type=Path, help="read the OIDC key set from this file instead of fetching GitHub's (tests, offline checks)")
    r.add_argument("--result", type=Path, help="write the outcome as JSON here")
    u = sub.add_parser("publish", help="Open or update the product's sync pull request in the central workspace.")
    u.add_argument("--workspace", type=Path, default=Path("."))
    u.add_argument("--result", type=Path, required=True, help="the result file receive wrote; the publish outcome is added to it")
    u.add_argument("--base", required=True, help="the central workspace's default branch")
    u.add_argument("--auto-merge", type=str.lower, choices=("true", "false", ""), default="false",
                   help="arm auto-merge when the change stays inside the product's cache folder; a required review still blocks it")
    m = sub.add_parser("merge", help="Squash-merge a confined sync pull request at an exact head SHA (receiver App).")
    m.add_argument("--workspace", type=Path, default=Path("."))
    m.add_argument("--repository", required=True, help="owner/name of this central workspace")
    m.add_argument("--base", required=True, help="the central workspace's default branch")
    m.add_argument("--sha", required=True, help="the validated head SHA; the merge API rejects a newer head")
    m.add_argument("--head", required=True, help="the pull request head branch, draft-sync/<owner>__<name>")
    m.add_argument("--auto-merge", type=str.lower, choices=("true", "false", ""), default="false",
                   help="merge only when this is true (repository variable DRAFT_SYNC_AUTO_MERGE)")
    m.add_argument("--pusher", required=True, help="workflow_run.actor.login of the validating run (not triggering_actor)")
    m.add_argument("--app-slug", required=True, help="receiver App slug; the pusher and the pull request author must be <slug>[bot]")
    t = sub.add_parser("report", help="Record the receiver run's outcome (job summary and the results branch). Run with if: always().")
    t.add_argument("--workspace", type=Path, default=Path("."))
    t.add_argument("--payload", type=Path, help="the event file, to name the sync when receive never ran")
    t.add_argument("--result", type=Path, required=True)
    t.add_argument("--validate-log", type=Path)
    t.add_argument("--job-status", default="")
    t.add_argument("--base", required=True, help="the central workspace's default branch (the results branch starts there)")
    t.add_argument("--summary", type=Path, help="append Markdown here ($GITHUB_STEP_SUMMARY)")
    t.add_argument("--no-store", action="store_true", help="write the summary only (tests, dry runs)")
    w = sub.add_parser("await-result", help="In the product repository: wait for the central outcome and fail if it failed.")
    w.add_argument("--central-repository", required=True)
    w.add_argument("--repository", required=True)
    w.add_argument("--correlation-id", required=True)
    w.add_argument("--timeout-minutes", type=float, default=20)
    w.add_argument("--interval-seconds", type=float, default=15)
    w.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)

    if args.command == "merge":
        try:
            outcome = merge_sync_pull_request(args.repository, args.base, args.sha, args.head, subprocess_runner(args.workspace),
                                              auto_merge=args.auto_merge == "true", pusher=args.pusher, app_slug=args.app_slug,
                                              workspace=args.workspace)
        except SyncError as exc:
            print(f"sdp_sync merge: {exc}", file=sys.stderr)
            return 1
        print(f"sdp_sync merge: {outcome['status']}: {outcome.get('message', '')}")
        return 0

    if args.command == "report":
        return _report_cli(args)
    if args.command == "await-result":
        return _await_cli(args)

    if args.command == "publish":
        try:
            result = json.loads(args.result.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"sdp_sync publish: cannot read the result file: {exc.__class__.__name__}", file=sys.stderr)
            return 1
        try:
            outcome = publish(result, args.base, subprocess_runner(args.workspace), auto_merge=args.auto_merge == "true")
        except SyncError as exc:
            outcome = {"status": "failed", "message": str(exc)}
        result["publish"] = outcome
        args.result.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if outcome["status"] == "failed":
            print(f"sdp_sync publish: {outcome['message']}", file=sys.stderr)
            return 1
        pr = outcome.get("pullRequest")
        print(f"sdp_sync publish: {outcome['status']}" + (f": {outcome['pullRequestAction']} {pr['url']} (auto-merge {outcome['autoMerge']})" if pr else ""))
        return 0

    if args.command == "pack":
        try:
            check_repository(args.repository)
            token = request_oidc_token(audience_for(args.central_repository)) if args.central_repository else None
            payload = pack(args.repo_root, args.repository, args.commit, args.ref, args.correlation_id, oidc_token=token)
        except SyncError as exc:
            print(f"sdp_sync pack: {exc}", file=sys.stderr)
            return 1
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"packed {payload['action']} for {payload['repository']} ({len(payload['files'])} file(s)), correlation id {payload['correlationId']}")
        return 0

    try:
        payload = load_payload(args.payload)
        keys = None
        if args.jwks:
            try:
                keys = json.loads(args.jwks.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise SyncError(f"cannot read the key set file: {exc.__class__.__name__}") from None
    except SyncError as exc:
        result = Result("rejected", str(exc))
    else:
        result = receive(args.workspace, payload, central_repository=args.central_repository, keys=keys)
    if args.result:
        args.result.write_text(json.dumps(result.as_json(), indent=2) + "\n", encoding="utf-8")
    print(f"sdp_sync receive: {result.status}: {result.message}", file=sys.stdout if result.status == "accepted" else sys.stderr)
    return 0 if result.status == "accepted" else 1


def _read_json(path: Path | None) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path else None
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _append(path: Path | None, text: str) -> None:
    if path:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)


def _report_cli(args: argparse.Namespace) -> int:
    payload = None
    if args.payload:
        try:
            payload = load_payload(args.payload)
        except SyncError:
            payload = None
    log = ""
    if args.validate_log:
        try:
            log = args.validate_log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            log = ""
    env = os.environ
    central = env.get("GITHUB_REPOSITORY", "")
    run_url = f"{env.get('GITHUB_SERVER_URL', 'https://github.com')}/{central}/actions/runs/{env['GITHUB_RUN_ID']}" if env.get("GITHUB_RUN_ID") and central else ""
    outcome = final_outcome(_read_json(args.result), payload, args.job_status, log, args.workspace, run_url)
    _append(args.summary, summary_markdown(outcome))
    print(f"sdp_sync report: {outcome['status']}: {outcome['message']}")
    if args.no_store:
        return 0
    if not outcome["identityVerified"]:
        print("sdp_sync report: the sender's identity was not verified; the outcome is in this run's summary only")
        return 0
    try:
        path = store_outcome(outcome, central, args.base, subprocess_runner(args.workspace))
    except SyncError as exc:
        print(f"sdp_sync report: the product repository cannot be told: {exc}", file=sys.stderr)
        return 1
    print(f"sdp_sync report: recorded {path} on {RESULTS_BRANCH}")
    return 0


def _await_cli(args: argparse.Namespace) -> int:
    token = os.environ.get("GH_TOKEN", "")
    try:
        if not token:
            raise SyncError("GH_TOKEN is not set; pass the App token used for the dispatch")
        outcome = await_result(args.repository, args.correlation_id, github_contents_fetcher(args.central_repository, token),
                               timeout=args.timeout_minutes * 60, interval=args.interval_seconds)
    except SyncError as exc:
        print(f"::error title=DRAFT sync::{annotation(str(exc))}")
        _append(args.summary, f"## DRAFT SDP sync: no result\n\n{exc}\n")
        return 1
    _append(args.summary, summary_markdown(outcome, "DRAFT SDP sync (central result)"))
    if outcome.get("status") == "accepted":
        print(f"DRAFT sync accepted: {outcome.get('message')}")
        return 0
    details = "\n".join(str(d) for d in outcome.get("details") or [])
    text = str(outcome.get("message")) + (f"\n{details}" if details else "") + (f"\nCentral run: {outcome['receiverRun']}" if outcome.get("receiverRun") else "")
    print(f"::error title=DRAFT sync {annotation(str(outcome.get('status')))}::{annotation(text)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
