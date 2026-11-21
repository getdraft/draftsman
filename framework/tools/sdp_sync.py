#!/usr/bin/env python3
"""Decentralized SDP sync: pack a product repository's SDP and receive it into the central workspace (#195).

The product repository's workflow runs ``pack`` and sends the JSON it writes as a ``repository_dispatch``
``client_payload``. The central workspace's receiver workflow runs ``receive`` on the event file. Payload values
only ever travel through files; nothing here builds shell text.

Usage:
    python3 sdp_sync.py pack --repo-root . --repository OWNER/NAME --commit SHA --ref refs/heads/main --output payload.json
    python3 sdp_sync.py receive --workspace . --payload "$GITHUB_EVENT_PATH" --result sdp-sync-result.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

PAYLOAD_FORMAT = "draft-sdp-sync/1"
# GitHub repository_dispatch: client_payload has at most 10 top-level properties and must stay under 64 KB.
MAX_CLIENT_PAYLOAD_BYTES = 65_000
MAX_TOP_LEVEL_PROPERTIES = 10
SDP_PATH = ".draft/sdp.yaml"
CACHE_ROOT = Path(".draft") / "external_sdps"
ACTIONS = ("upsert", "delete")
_REPOSITORY = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")
_COMMIT = re.compile(r"^[0-9a-f]{7,64}$")
_CORRELATION = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class SyncError(Exception):
    """A payload or input the sync refuses, with a message for the product team."""


# --------------------------------------------------------------------------- pack


def pack(repo_root: Path, repository: str, commit: str, ref: str, correlation_id: str | None = None) -> dict[str, Any]:
    """Build the client_payload for a product repository. A missing .draft/sdp.yaml packs a delete."""
    check_repository(repository)
    sdp = repo_root / SDP_PATH
    files: dict[str, str] = {}
    action = "delete"
    if sdp.is_file():
        text = sdp.read_text(encoding="utf-8")
        parse_object(SDP_PATH, text)
        files[SDP_PATH] = text
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
    check_size(payload)
    return payload


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
    written: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {"status": self.status, "message": self.message, "repository": self.repository, "product": self.product,
                "action": self.action, "correlationId": self.correlation_id, "commit": self.commit,
                "written": self.written, "removed": self.removed}


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


def receive(workspace: Path, payload: dict[str, Any]) -> Result:
    """Store a payload in the product's cache folder. The folder is replaced as a whole: a sync is a snapshot."""
    try:
        check_payload(payload)
        repository = payload["repository"]
        slug = product_slug(repository)
        targets: dict[PurePosixPath, str] = {}
        for source_path, text in sorted(payload["files"].items()):
            target = cache_path(source_path)
            if target in targets:
                raise SyncError(f"two files map to {target}")
            parse_object(source_path, text)
            targets[target] = text
    except SyncError as exc:
        return Result("rejected", str(exc), repository=str(payload.get("repository") or ""),
                      action=str(payload.get("action") or ""), correlation_id=str(payload.get("correlationId") or ""),
                      commit=str(payload.get("commit") or ""))

    folder = workspace / CACHE_ROOT / slug
    result = Result("accepted", "", repository=repository, product=slug, action=payload["action"],
                    correlation_id=payload["correlationId"], commit=payload["commit"])
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
    p.add_argument("--output", type=Path, required=True)
    r = sub.add_parser("receive", help="Store a payload in the central workspace.")
    r.add_argument("--workspace", type=Path, default=Path("."))
    r.add_argument("--payload", type=Path, required=True, help="payload JSON, or a GitHub event file with client_payload")
    r.add_argument("--result", type=Path, help="write the outcome as JSON here")
    args = parser.parse_args(argv)

    if args.command == "pack":
        try:
            payload = pack(args.repo_root, args.repository, args.commit, args.ref, args.correlation_id)
        except SyncError as exc:
            print(f"sdp_sync pack: {exc}", file=sys.stderr)
            return 1
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"packed {payload['action']} for {payload['repository']} ({len(payload['files'])} file(s)), correlation id {payload['correlationId']}")
        return 0

    try:
        payload = load_payload(args.payload)
    except SyncError as exc:
        result = Result("rejected", str(exc))
    else:
        result = receive(args.workspace, payload)
    if args.result:
        args.result.write_text(json.dumps(result.as_json(), indent=2) + "\n", encoding="utf-8")
    print(f"sdp_sync receive: {result.status}: {result.message}", file=sys.stdout if result.status == "accepted" else sys.stderr)
    return 0 if result.status == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
