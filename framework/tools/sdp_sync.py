#!/usr/bin/env python3
"""Decentralized SDP sync: pack a product repository's SDP and receive it into the central workspace (#195).

The product repository's workflow runs ``pack`` and sends the JSON it writes as a ``repository_dispatch``
``client_payload``. The central workspace's receiver workflow runs ``receive`` on the event file. Payload values
only ever travel through files; nothing here builds shell text.

The sender proves who it is with a GitHub Actions OIDC token whose audience names the central workspace
(``draft-sdp-sync:<central owner>/<central name>``). ``receive`` verifies the RS256 signature against GitHub's
published key set with the standard library, then checks the issuer, audience, expiry, that the token's repository
is the registered one and that its ref is the registered default branch.

Usage:
    python3 sdp_sync.py pack --repo-root . --repository OWNER/NAME --commit SHA --ref refs/heads/main \
        --central-repository CENTRAL_OWNER/CENTRAL_NAME --output payload.json
    python3 sdp_sync.py receive --workspace . --payload "$GITHUB_EVENT_PATH" --central-repository CENTRAL_OWNER/CENTRAL_NAME \
        --result sdp-sync-result.json
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
import sys
import time
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

    def as_json(self) -> dict[str, Any]:
        return {"status": self.status, "message": self.message, "repository": self.repository, "product": self.product,
                "registration": self.registration, "action": self.action, "correlationId": self.correlation_id,
                "commit": self.commit, "written": self.written, "removed": self.removed}


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


def check_identity(claims: Mapping[str, Any], payload: Mapping[str, Any], registration: Mapping[str, Any]) -> None:
    """The token must come from the registered repository's default branch, for this very commit and ref."""
    repository = str(payload["repository"]).lower()
    if str(claims.get("repository") or "").lower() != repository:
        raise SyncError(f"the OIDC token was issued to {claims.get('repository')!r}, not {payload['repository']}")
    repo = registration.get("repository") if isinstance(registration.get("repository"), dict) else {}
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
    try:
        audience = audience_for(central_repository)
        check_payload(payload)
        repository = payload["repository"]
        slug = product_slug(repository)
        claims = verify_oidc_token(payload["oidcToken"], audience, fetch_github_jwks if keys is None else keys, now)
        registration = find_registration(workspace, repository)
        check_identity(claims, payload, registration)
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
                      commit=str(payload.get("commit") or ""), registration=str(registration.get("uid") or ""))

    folder = workspace / CACHE_ROOT / slug
    result = Result("accepted", "", repository=repository, product=slug, action=payload["action"],
                    correlation_id=payload["correlationId"], commit=payload["commit"], registration=str(registration.get("uid") or ""))
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
    return result


def rel(workspace: Path, path: Path) -> str:
    return path.relative_to(workspace).as_posix()


def check_repository(value: Any) -> str:
    if not isinstance(value, str) or not _REPOSITORY.match(value) or value.endswith((".", "/")) or ".." in value:
        raise SyncError(f"{value!r} is not a GitHub repository name (owner/name)")
    return value


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
    args = parser.parse_args(argv)

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


if __name__ == "__main__":
    raise SystemExit(main())
