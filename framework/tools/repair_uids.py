#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import sys
import re
from pathlib import Path
from typing import Any

import yaml

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from uid_utils import UID_PATTERN_TEXT, generate_uid


FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = FRAMEWORK_ROOT.parent
BASE_CONFIGURATION_ROOT = FRAMEWORK_ROOT / "configurations"
DEFAULT_WORKSPACE_ROOT = REPO_ROOT / "examples"
SKIP_DIRS = {"tools", "schemas", "docs", "adrs", ".github", ".git"}
UID_PATTERN = re.compile(UID_PATTERN_TEXT)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair generated DRAFT object UIDs and rewrite UID references.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE_ROOT,
        help="Workspace root containing catalog/ and configurations/. Defaults to examples/.",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="Repair only the specified object file, while still rewriting references across the workspace.",
    )
    parser.add_argument("--uid", help="Use this exact generated UID for a single --file repair.")
    parser.add_argument("--dry-run", action="store_true", help="Report planned UID repairs without writing files.")
    return parser.parse_args(argv)


def workspace_yaml_roots(workspace_root: Path) -> list[Path]:
    roots = [BASE_CONFIGURATION_ROOT]
    provider_root = workspace_root / ".draft" / "providers"
    if provider_root.exists():
        roots.extend(
            provider_config
            for provider_config in sorted(provider_root.glob("*/configurations"))
            if provider_config.exists()
        )
    workspace_config = workspace_root / "configurations"
    workspace_catalog = workspace_root / "catalog"
    if workspace_config.exists():
        roots.append(workspace_config)
    if workspace_catalog.exists():
        roots.append(workspace_catalog)
    elif workspace_root.exists() and workspace_root.name == "catalog":
        roots.append(workspace_root)
    return roots


def discover_yaml_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*.yaml")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return files


def discover_workspace_yaml_files(workspace_root: Path) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for root in workspace_yaml_roots(workspace_root):
        for path in discover_yaml_files(root):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)
    workspace_config = workspace_root / ".draft" / "workspace.yaml"
    if workspace_config.exists():
        files.append(workspace_config)
    return sorted(files)


def resolve_requested_files(workspace_root: Path, requested: list[str]) -> set[Path]:
    resolved: set[Path] = set()
    for item in requested:
        candidate = Path(item)
        candidates = [candidate]
        if not candidate.is_absolute():
            candidates = [Path.cwd() / candidate, workspace_root / candidate, REPO_ROOT / candidate]
        for path in candidates:
            if path.exists():
                resolved.add(path.resolve())
                break
        else:
            raise FileNotFoundError(f"Could not resolve --file {item}")
    return resolved


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def dump_yaml(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True, width=1000)


def is_first_class_object(data: Any) -> bool:
    return isinstance(data, dict) and isinstance(data.get("type"), str) and bool(data.get("type").strip())


def ordered_with_uid(data: dict[str, Any], uid: str) -> dict[str, Any]:
    migrated: dict[str, Any] = {}
    if "schemaVersion" in data:
        migrated["schemaVersion"] = data["schemaVersion"]
    migrated["uid"] = uid
    for key, value in data.items():
        if key in {"schemaVersion", "uid", "id"}:
            continue
        migrated[key] = value
    return migrated


def legacy_ids_for_path(path: Path, data: dict[str, Any]) -> list[str]:
    object_type = data.get("type")
    stem = path.stem
    if object_type == "capability" and stem.startswith("capability-"):
        return ["capability." + stem.removeprefix("capability-")]
    if object_type == "requirement_group" and stem.startswith("requirement-group-"):
        return ["requirement-group." + stem.removeprefix("requirement-group-")]
    if object_type == "domain":
        return ["domain." + stem]
    if object_type == "object_patch" and stem.startswith("patch-"):
        return ["patch." + stem.removeprefix("patch-")]
    if object_type == "technology_component" and stem.startswith("technology-"):
        parts = stem.removeprefix("technology-").split("-", 1)
        if len(parts) == 2:
            return [f"technology.{parts[0]}.{parts[1]}"]
    if object_type == "edge_gateway_service" and stem.startswith("edge-gateway-service-"):
        return ["edge-gateway-service." + stem.removeprefix("edge-gateway-service-")]
    if object_type == "host" and stem.startswith("host-"):
        return ["host." + stem.removeprefix("host-")]
    if object_type == "runtime_service" and stem.startswith("runtime-service-"):
        return ["runtime-service." + stem.removeprefix("runtime-service-")]
    if object_type == "data_at_rest_service" and stem.startswith("data-at-rest-service-"):
        return ["data-at-rest-service." + stem.removeprefix("data-at-rest-service-")]
    if object_type == "product_service" and stem.startswith("product-service-"):
        return ["product-service." + stem.removeprefix("product-service-")]
    if object_type == "reference_architecture" and stem.startswith("reference-architecture-"):
        return ["reference-architecture." + stem.removeprefix("reference-architecture-")]
    if object_type == "software_deployment_pattern" and stem.startswith("software-deployment-"):
        return ["software-deployment." + stem.removeprefix("software-deployment-")]
    if object_type == "decision_record" and stem.startswith("decision-"):
        return ["decision." + stem.removeprefix("decision-")]
    if object_type == "drafting_session" and stem.startswith("session-"):
        return ["session." + stem.removeprefix("session-")]
    return []


def migrate_legacy_uid_fields(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    migrated = copy.deepcopy(data)
    if "primaryObjectId" in migrated and "primaryObjectUid" not in migrated:
        migrated["primaryObjectUid"] = migrated.pop("primaryObjectId")
    elif "primaryObjectId" in migrated:
        migrated.pop("primaryObjectId")
    generated_objects = migrated.get("generatedObjects")
    if isinstance(generated_objects, list):
        for entry in generated_objects:
            if not isinstance(entry, dict):
                continue
            if "proposedId" in entry and "proposedUid" not in entry:
                entry["proposedUid"] = entry.pop("proposedId")
            elif "proposedId" in entry:
                entry.pop("proposedId")
    return migrated


def replace_refs(node: Any, replacements: dict[str, str]) -> Any:
    if isinstance(node, str):
        return replacements.get(node, node)
    if isinstance(node, list):
        changed = False
        items = []
        for item in node:
            replaced = replace_refs(item, replacements)
            changed = changed or replaced is not item
            items.append(replaced)
        return items if changed else node
    if isinstance(node, dict):
        changed = False
        items: dict[Any, Any] = {}
        for key, value in node.items():
            replaced_key = replacements.get(key, key) if isinstance(key, str) else key
            replaced = replace_refs(value, replacements)
            changed = changed or replaced is not value or replaced_key != key
            items[replaced_key] = replaced
        return items if changed else node
    return node


def display_path(path: Path) -> str:
    for root in (Path.cwd(), REPO_ROOT):
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    workspace_root = args.workspace.resolve()
    forced_uid = str(args.uid or "").strip()
    if forced_uid:
        if len(args.file) != 1:
            raise ValueError("--uid can only be used with exactly one --file")
        if not UID_PATTERN.match(forced_uid):
            raise ValueError(f"--uid must match {UID_PATTERN_TEXT}")
    requested_files = resolve_requested_files(workspace_root, args.file)
    files = discover_workspace_yaml_files(workspace_root)
    loaded: dict[Path, Any] = {path: load_yaml(path) for path in files}

    object_paths = [path for path, data in loaded.items() if is_first_class_object(data)]
    selected = requested_files or {path.resolve() for path in object_paths}
    used_uids = {
        str(data.get("uid"))
        for data in loaded.values()
        if is_first_class_object(data) and isinstance(data.get("uid"), str) and UID_PATTERN.match(str(data.get("uid")))
    }
    seen: set[str] = set()
    replacements: dict[str, str] = {}
    updated: dict[Path, Any] = copy.deepcopy(loaded)
    changes: list[str] = []

    for path in object_paths:
        data = updated[path]
        uid = str(data.get("uid") or "").strip()
        if UID_PATTERN.match(uid):
            for legacy_id in legacy_ids_for_path(path, data):
                replacements.setdefault(legacy_id, uid)

    for path in object_paths:
        data = updated[path]
        data = migrate_legacy_uid_fields(data)
        updated[path] = data
        if path.resolve() not in selected and "id" not in data:
            uid = str(data.get("uid") or "")
            if uid in seen:
                selected.add(path.resolve())
            elif uid:
                seen.add(uid)
            continue

        old_id = data.get("id")
        old_uid = data.get("uid")
        uid = str(old_uid or "").strip()
        needs_new = not uid or not UID_PATTERN.match(uid) or uid in seen or path.resolve() in selected and "id" in data
        if needs_new:
            uid = forced_uid if forced_uid and path.resolve() in selected else generate_uid(used_uids)
            if uid in used_uids and uid != old_uid:
                raise ValueError(f"--uid {uid} is already used by another object")
            used_uids.add(uid)
        seen.add(uid)
        if isinstance(old_id, str) and old_id:
            replacements[old_id] = uid
        if isinstance(old_uid, str) and old_uid and old_uid != uid:
            replacements[old_uid] = uid
        migrated = ordered_with_uid(data, uid)
        if migrated != data:
            updated[path] = migrated
            changes.append(f"{display_path(path)} -> {uid}")

    if replacements:
        for path, data in list(updated.items()):
            replaced = replace_refs(data, replacements)
            if replaced != data:
                updated[path] = replaced
                if f"{display_path(path)} ->" not in "\n".join(changes):
                    changes.append(f"{display_path(path)} references updated")

    if not changes:
        print("No UID repairs needed.")
        return 0

    print("UID repair plan:")
    for change in changes:
        print(f"- {change}")

    if args.dry_run:
        return 0

    for path, data in updated.items():
        if data != loaded[path]:
            dump_yaml(path, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
