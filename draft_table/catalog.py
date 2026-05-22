from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .paths import REPO_ROOT, resolve_framework_root, workspace_framework_root


CATALOG_FOLDERS = (
    "technology-components",
    "edge-gateway-services",
    "hosts",
    "runtime-services",
    "data-at-rest-services",
    "product-services",
    "decision-records",
    "capabilities",
    "requirement-groups",
    "domains",
    "object-patches",
    "reference-architectures",
    "software-deployment-patterns",
    "sessions",
)

REFERENCE_KEYS = {
    "ref",
    "runsOn",
    "followsReferenceArchitecture",
    "host",
    "primaryTechnologyComponent",
    "operatingSystemComponent",
    "computePlatformComponent",
    "inherits",
    "platformDependency",
    "linkedObject",
    "primaryObjectUid",
    "riskRef",
    "domain",
    "relatedCapability",
    "requirementGroup",
    "target",
}

UID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{10}-[0-9A-HJKMNP-TV-Z]{4}$")


def load_effective_catalog(workspace: Path | None, framework_repo: Path = REPO_ROOT) -> dict[str, dict[str, Any]]:
    framework_root = selected_framework_root(workspace, framework_repo)
    objects: dict[str, dict[str, Any]] = {}
    roots = [framework_root / "configurations"]
    if workspace and workspace.exists():
        provider_root = workspace / ".draft" / "providers"
        if provider_root.exists():
            roots.extend(
                provider_config
                for provider_config in sorted(provider_root.glob("*/configurations"))
                if provider_config.exists()
            )
        workspace_config = workspace / "configurations"
        workspace_catalog = workspace / "catalog"
        if workspace_config.exists():
            roots.append(workspace_config)
        if workspace_catalog.exists():
            roots.append(workspace_catalog)
        elif workspace.name == "catalog":
            roots.append(workspace)
    else:
        examples_catalog = framework_root / "examples" / "catalog"
        if not examples_catalog.exists():
            examples_catalog = framework_root.parent / "examples" / "catalog"
        roots.append(examples_catalog)

    for root in roots:
        for path in discover_yaml_files(root):
            data = read_yaml(path)
            object_id = data.get("uid") or data.get("id")
            if object_id:
                data["_source"] = display_path(path, framework_root)
                objects[str(object_id)] = data
    return apply_object_patches(objects)


def selected_framework_root(workspace: Path | None, framework_repo: Path = REPO_ROOT) -> Path:
    if workspace:
        vendored = workspace_framework_root(workspace)
        if (vendored / "configurations").exists():
            return vendored.resolve()
    return resolve_framework_root(framework_repo)


def discover_yaml_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.exists():
        return files
    for folder in CATALOG_FOLDERS:
        folder_path = root / folder
        if folder_path.exists():
            files.extend(sorted(folder_path.rglob("*.yaml")))
    if root.name in {"catalog", "configurations"}:
        files.extend(path for path in sorted(root.glob("*.yaml")) if path.is_file())
    return sorted(set(files))


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def display_path(path: Path, framework_root: Path) -> str:
    for root in (framework_root, framework_root.parent, Path.cwd()):
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def apply_object_patches(objects: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    patched = dict(objects)
    for obj in objects.values():
        if obj.get("type") != "object_patch":
            continue
        target = str(obj.get("target") or "")
        patch = obj.get("patch")
        if target in patched and isinstance(patch, dict):
            patched[target] = deep_merge(patched[target], patch)
    return patched


def deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = dict(base)
        for key, value in patch.items():
            if key in {"uid", "id", "type"}:
                continue
            merged[key] = deep_merge(merged.get(key), value)
        return merged
    return patch


def build_reference_index(objects: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    referenced_by: dict[str, list[dict[str, str]]] = {}
    known_uids = set(objects)
    for object_id, obj in objects.items():
        for target, ref_path in extract_refs(obj, known_uids):
            referenced_by.setdefault(target, []).append({"source": object_id, "path": ref_path})
    return referenced_by


def is_probable_reference_key(path: str) -> bool:
    key = path.rsplit(".", 1)[-1]
    return key in REFERENCE_KEYS or key.endswith("Refs")


def is_object_ref(value: Any, path: str, known_uids: set[str] | None) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    if known_uids and value in known_uids:
        return True
    return is_probable_reference_key(path) and bool(UID_PATTERN.match(value))


def extract_refs(node: Any, known_uids: set[str] | None = None, path: str = "") -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else key
            if key in REFERENCE_KEYS and is_object_ref(value, child_path, known_uids):
                refs.append((value, child_path))
            elif key.endswith("Refs") and isinstance(value, list):
                for index, item in enumerate(value):
                    if is_object_ref(item, f"{child_path}[{index}]", known_uids):
                        refs.append((item, f"{child_path}[{index}]"))
            else:
                refs.extend(extract_refs(value, known_uids, child_path))
    elif isinstance(node, list):
        if path.endswith(".appliesTo"):
            return refs
        for index, item in enumerate(node):
            item_path = f"{path}[{index}]"
            if is_object_ref(item, item_path, known_uids):
                refs.append((item, f"{path}[{index}]"))
            else:
                refs.extend(extract_refs(item, known_uids, item_path))
    return refs


def search_objects(objects: dict[str, dict[str, Any]], query: str, limit: int = 8) -> list[dict[str, Any]]:
    tokens = tokenize(query)
    scored: list[tuple[int, dict[str, Any]]] = []
    for obj in objects.values():
        haystack = " ".join(
            str(value)
            for value in (
                obj.get("id", ""),
                obj.get("uid", ""),
                obj.get("name", ""),
                " ".join(str(alias) for alias in obj.get("aliases", []) if isinstance(obj.get("aliases"), list)),
                obj.get("type", ""),
                obj.get("description", ""),
                " ".join(str(tag) for tag in obj.get("tags", []) if isinstance(obj.get("tags"), list)),
            )
        ).lower()
        score = sum(1 for token in tokens if token in haystack)
        if score:
            scored.append((score, obj))
    return [obj for _score, obj in sorted(scored, key=lambda item: (-item[0], item[1].get("name", "")))[:limit]]


def tokenize(text: str) -> list[str]:
    return [token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if len(token) > 2]


def object_summary(obj: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(obj.get("uid") or obj.get("id") or ""),
        "uid": str(obj.get("uid") or obj.get("id") or ""),
        "name": str(obj.get("name") or obj.get("uid") or obj.get("id") or ""),
        "type": str(obj.get("type", "")),
        "status": str(obj.get("catalogStatus", "")),
        "source": str(obj.get("_source", "")),
        "description": str(obj.get("description", "")).strip(),
    }
