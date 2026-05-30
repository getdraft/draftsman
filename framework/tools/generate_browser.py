#!/usr/bin/env python3
# ARCHITECTURE CONTRACT
# This generator is data-driven. The following must remain true:
# 1. No catalog object UIDs are hardcoded in this file.
# 2. No product names (accelify, hrlinks, etc.) appear in rendering logic.
# 3. All relationships are derived from the cross-reference index built at load time.
# 4. All object types are rendered via type dispatch — unknown types get a generic fallback.
# 5. Adding a new catalog object type requires only: (a) a new YAML file, (b) optionally a new renderer.
#    No other changes to this file are required for the new type to appear in list view.
# Note: location icon inference uses generic string heuristics only; unknown patterns always fall back to a generic icon.
from __future__ import annotations

import argparse
import base64
import copy
from datetime import date
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = FRAMEWORK_ROOT.parent
WORKSPACE_ROOT = REPO_ROOT.parent if REPO_ROOT.name == ".draft" else REPO_ROOT
OUTPUT_PATH = WORKSPACE_ROOT / "docs" / "index.html"
SCHEMA_ROOT = FRAMEWORK_ROOT / "schemas"
BASE_CONFIGURATION_ROOT = FRAMEWORK_ROOT / "configurations"
USER_MANUAL_SOURCE_PATH = FRAMEWORK_ROOT / "docs" / "user-manual.md"
USER_MANUAL_OUTPUT_NAME = "user-manual.html"
COMPANY_VOCABULARY_SOURCE_PATH = FRAMEWORK_ROOT / "docs" / "company-vocabulary.md"
COMPANY_VOCABULARY_OUTPUT_NAME = "company-vocabulary.html"
DEFAULT_WORKSPACE_ROOT = WORKSPACE_ROOT if REPO_ROOT.name == ".draft" else REPO_ROOT / "examples"
LOGO_PATH = REPO_ROOT / "draft-logo.png"
LEGACY_LOGO_PATH = REPO_ROOT / "draftlogo.png"
CATALOG_FOLDERS = [
    "capabilities",
    "requirement-groups",
    "object-patches",
    "technology-components",
    "edge-gateway-services",
    "hosts",
    "runtime-services",
    "data-store-services",
    "network-services",
    "product-components",
    "data-components",
    "decision-records",
    "objects",
    "object-types",
    "automation-targets",
    "sessions",
    "software-deployment-patterns",
    "reference-architectures",
    "domains",
    "relationships",
    "systems",
]
LIFECYCLE_COLORS = {
    "preferred": "1f8a5b",
    "existing-only": "2a6fdb",
    "deprecated": "c47a14",
    "retired": "b93a3a",
    "candidate": "7c3a6b",
    "unknown": "7a6e60",
}
REF_CONTAINER_KEYS = {
    "ref",
    "runsOn",
    "substrate",
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
    "controls",
    "domain",
    "relatedCapability",
    "requirementGroup",
    "target",
    "source",
}
UID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{10}-[0-9A-HJKMNP-TV-Z]{4}$")


def is_saas_service_classification(obj: dict[str, Any]) -> bool:
    return obj.get("type") in {"runtime_service", "data_store_service", "edge_gateway_service"} and obj.get("deliveryModel") == "saas"


def is_paas_service_classification(obj: dict[str, Any]) -> bool:
    return obj.get("type") in {"runtime_service", "data_store_service", "edge_gateway_service"} and obj.get("deliveryModel") == "paas"


def is_database_service(obj: dict[str, Any]) -> bool:
    return obj.get("type") == "data_store_service"


def is_general_service(obj: dict[str, Any]) -> bool:
    return obj.get("type") == "runtime_service"


def load_workspace_catalog_folders(workspace_root: Path) -> list[str] | None:
    """Read optional paths.catalogFolders from workspace.yaml, or None to use framework defaults."""
    config_path = workspace_root / ".draft" / "workspace.yaml"
    if not config_path.exists():
        return None
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    paths = data.get("paths")
    if not isinstance(paths, dict):
        return None
    folders = paths.get("catalogFolders")
    if not isinstance(folders, list) or not folders:
        return None
    return [str(f) for f in folders if str(f).strip()]


def discover_yaml_files(root: Path, folder_names: list[str] | None = None) -> list[Path]:
    folders = folder_names if folder_names is not None else CATALOG_FOLDERS
    files: list[Path] = []
    for folder_name in folders:
        folder = root / folder_name
        if not folder.exists():
            continue
        files.extend(sorted(folder.rglob("*.yaml")))
    return files


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


def display_path(path: Path) -> str:
    for root in (REPO_ROOT, Path.cwd()):
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def load_workspace_requirements(workspace_root: Path) -> dict[str, Any]:
    config_path = workspace_root / ".draft" / "workspace.yaml"
    if not config_path.exists():
        return {"activeRequirementGroups": [], "requireActiveRequirementGroupDisposition": False}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {"activeRequirementGroups": [], "requireActiveRequirementGroupDisposition": False}
    if not isinstance(data, dict):
        return {"activeRequirementGroups": [], "requireActiveRequirementGroupDisposition": False}
    requirements = data.get("requirements") or {}
    if not isinstance(requirements, dict):
        return {"activeRequirementGroups": [], "requireActiveRequirementGroupDisposition": False}
    active = requirements.get("activeRequirementGroups") or []
    active_groups = [str(group_id) for group_id in active if str(group_id).strip()] if isinstance(active, list) else []
    return {
        "activeRequirementGroups": active_groups,
        "requireActiveRequirementGroupDisposition": requirements.get("requireActiveRequirementGroupDisposition") is True,
    }


def load_workspace_browser_config(workspace_root: Path) -> dict[str, Any]:
    """Read optional [browser] section from workspace.yaml and return config dict."""
    config_path = workspace_root / ".draft" / "workspace.yaml"
    defaults: dict[str, Any] = {"defaultMapView": "world"}
    if not config_path.exists():
        return defaults
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return defaults
    browser = data.get("browser") if isinstance(data, dict) else None
    if not isinstance(browser, dict):
        return defaults
    cfg = dict(defaults)
    if browser.get("defaultMapView") in ("world", "north-america", "europe", "asia"):
        cfg["defaultMapView"] = browser["defaultMapView"]
    return cfg


def load_workspace_business_taxonomy(workspace_root: Path) -> dict[str, Any]:
    config_path = workspace_root / ".draft" / "workspace.yaml"
    if not config_path.exists():
        return {"pillars": [], "requireSoftwareDeploymentPatternPillar": False}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {"pillars": [], "requireSoftwareDeploymentPatternPillar": False}
    if not isinstance(data, dict):
        return {"pillars": [], "requireSoftwareDeploymentPatternPillar": False}
    taxonomy = data.get("businessTaxonomy") or {}
    if not isinstance(taxonomy, dict):
        return {"pillars": [], "requireSoftwareDeploymentPatternPillar": False}
    pillars = taxonomy.get("pillars") or []
    if not isinstance(pillars, list):
        pillars = []
    return {
        "pillars": [pillar for pillar in pillars if isinstance(pillar, dict) and str(pillar.get("id") or "").strip()],
        "requireSoftwareDeploymentPatternPillar": taxonomy.get("requireSoftwareDeploymentPatternPillar") is True,
    }


def load_workspace_vocabulary(workspace_root: Path) -> dict[str, Any]:
    config_path = workspace_root / ".draft" / "workspace.yaml"
    if not config_path.exists():
        config_path = workspace_root / "workspace.yaml"
    if not config_path.exists():
        return {}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    vocabulary = data.get("vocabulary")
    if not isinstance(vocabulary, dict):
        return {}
    result: dict[str, Any] = {}
    for list_name, list_data in vocabulary.items():
        if not isinstance(list_data, dict):
            continue
        entry: dict[str, Any] = {}
        if "mode" in list_data:
            entry["mode"] = list_data["mode"]
        if "reviewBy" in list_data:
            entry["reviewBy"] = list_data["reviewBy"]
        source = list_data.get("source")
        if source:
            source_path = workspace_root / source
            try:
                source_data = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
                values = source_data.get("values", []) if isinstance(source_data, dict) else []
            except Exception:
                values = []
        else:
            values = list_data.get("values", [])
        entry["values"] = values if isinstance(values, list) else []
        result[list_name] = entry
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the static DRAFT browser for a workspace.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE_ROOT,
        help="Workspace root containing catalog/ and configurations/. Defaults to examples/.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="HTML output path. Defaults to docs/index.html.",
    )
    parser.add_argument(
        "--manual-output",
        type=Path,
        default=None,
        help="User manual HTML output path. Defaults to user-manual.html beside --output.",
    )
    parser.add_argument(
        "--skip-user-manual",
        action="store_true",
        help="Do not generate the user manual HTML from framework/docs/user-manual.md.",
    )
    parser.add_argument(
        "--refresh-shell",
        action="store_true",
        help=(
            "Overwrite the browser shell assets (draft-browser.css, draft-browser.js, "
            "index.html) from the framework source even if they already exist in the "
            "output directory. By default these files are only written on first install "
            "so that design-layer edits made directly to docs/assets/ are preserved "
            "across content regeneration runs."
        ),
    )
    return parser.parse_args(argv)


def load_objects(workspace_root: Path) -> dict[str, dict[str, Any]]:
    objects: dict[str, dict[str, Any]] = {}
    catalog_folders = load_workspace_catalog_folders(workspace_root)
    workspace_catalog = workspace_root / "catalog"
    for root in workspace_yaml_roots(workspace_root):
        folder_override = catalog_folders if (catalog_folders is not None and root == workspace_catalog) else None
        for path in discover_yaml_files(root, folder_override):
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            if isinstance(data, dict) and data.get("uid"):
                data["_source"] = display_path(path)
                objects[str(data["uid"])] = data
    return apply_object_patches(objects)


def deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = copy.deepcopy(base)
        for key, value in patch.items():
            if key in {"uid", "id", "type"}:
                continue
            merged[key] = deep_merge(merged.get(key), value)
        return merged
    return copy.deepcopy(patch)


def apply_object_patches(objects: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    patched = dict(objects)
    for obj in objects.values():
        if obj.get("type") != "object_patch":
            continue
        target_id = str(obj.get("target", ""))
        patch = obj.get("patch")
        if not target_id or target_id not in patched or not isinstance(patch, dict):
            continue
        patched[target_id] = deep_merge(patched[target_id], patch)
    return patched


def load_schemas(root: Path) -> list[dict[str, Any]]:
    schemas: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if isinstance(data, dict):
            data["_schema_path"] = display_path(path)
            schemas.append(data)
    return schemas


def is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def schema_specificity(schema: dict[str, Any]) -> int:
    return sum(1 for key in ("subtype", "category", "deliveryModel") if is_non_empty(schema.get(key)))


def select_schema(obj: dict[str, Any], schemas: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for schema in schemas:
        if schema.get("type") != obj.get("type"):
            continue
        if is_non_empty(schema.get("subtype")) and schema.get("subtype") != obj.get("subtype"):
            continue
        if is_non_empty(schema.get("category")) and schema.get("category") != obj.get("category"):
            continue
        if is_non_empty(schema.get("deliveryModel")) and schema.get("deliveryModel") != obj.get("deliveryModel"):
            continue
        candidates.append(schema)
    if not candidates:
        return None
    return sorted(candidates, key=schema_specificity, reverse=True)[0]


def repository_web_url(root: Path) -> str:
    try:
        remote = subprocess.check_output(
            ["git", "-C", str(root), "config", "--get", "remote.origin.url"],
            text=True,
        ).strip()
    except Exception:  # noqa: BLE001
        return ""
    if remote.startswith("git@github.com:"):
        remote = "https://github.com/" + remote[len("git@github.com:"):]
    if remote.endswith(".git"):
        remote = remote[:-4]
    return remote if remote.startswith("https://github.com/") else ""


def repository_name_from_url(url: str) -> str:
    if not url:
        return ""
    return url.rstrip("/").split("/")[-1] or ""


def workspace_repository_name(workspace_root: Path) -> str:
    config_path = workspace_root / ".draft" / "workspace.yaml"
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            config = {}
        repository = config.get("repository") if isinstance(config, dict) else {}
        if isinstance(repository, dict):
            owner = str(repository.get("owner") or "").strip()
            name = str(repository.get("name") or "").strip()
            if owner and name:
                return f"{owner}/{name}"
            if name:
                return name
    workspace_url = repository_web_url(workspace_root)
    if workspace_url:
        parts = workspace_url.rstrip("/").split("/")
        if len(parts) >= 2:
            return "/".join(parts[-2:])
    framework_url = repository_web_url(REPO_ROOT)
    return repository_name_from_url(framework_url) or workspace_root.name


def logo_data_uri() -> str:
    logo_path = LOGO_PATH if LOGO_PATH.exists() else LEGACY_LOGO_PATH
    if not logo_path.exists():
        return ""
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def is_probable_reference_key(path: str) -> bool:
    key = path.rsplit(".", 1)[-1]
    return key in REF_CONTAINER_KEYS or key.endswith("Refs")


def is_object_ref(value: Any, path: str, known_uids: set[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    if value in known_uids:
        return True
    return is_probable_reference_key(path) and bool(UID_PATTERN.match(value))


def extract_refs(node: Any, known_uids: set[str], path: str = "") -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else key
            if key in REF_CONTAINER_KEYS and is_object_ref(value, child_path, known_uids):
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


def build_reference_index(registry: dict[str, dict[str, Any]]) -> tuple[dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]], list[str]]:
    outbound: dict[str, list[dict[str, str]]] = {}
    referenced_by: dict[str, list[dict[str, str]]] = {}
    warnings: list[str] = []
    known_uids = set(registry)
    for object_uid, obj in registry.items():
        refs = extract_refs(obj, known_uids)
        outbound[object_uid] = [{"target": target, "path": ref_path} for target, ref_path in refs]
        for target, ref_path in refs:
            referenced_by.setdefault(target, []).append({"source": object_uid, "path": ref_path})
            if target not in registry:
                warnings.append(f"Warning: {object_uid} references missing object '{target}' via {ref_path}")
    return outbound, referenced_by, warnings


def shape_for(obj: dict[str, Any]) -> str:
    if obj["type"] == "reference_architecture":
        return "hexagon"
    if obj["type"] == "software_deployment_pattern":
        return "star"
    if obj["type"] == "drafting_session":
        return "round-rectangle"
    if obj["type"] == "capability":
        return "ellipse"
    if obj["type"] == "requirement_group":
        return "barrel"
    if obj["type"] == "decision_record":
        return "round-rectangle"
    if obj["type"] == "technology_component":
        return "ellipse"
    if obj["type"] == "edge_gateway_service":
        return "diamond"
    if obj["type"] in {"host", "runtime_service", "data_store_service"}:
        return "round-rectangle" if obj["type"] == "host" else "diamond"
    if obj["type"] in {"product_component", "data_component"}:
        return "round-rectangle"
    return "round-rectangle"


def to_json(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)


def humanize_slug(value: str) -> str:
    return value.replace("-", " ").title()


def filter_type_for(obj: dict[str, Any]) -> str:
    return str(obj.get("type", "unknown"))


def type_label_for(obj: dict[str, Any]) -> str:
    if obj["type"] == "technology_component":
        classification = humanize_slug(str(obj.get("classification", "unknown")))
        return f"TechnologyComponent / {classification}"
    if obj["type"] == "edge_gateway_service":
        delivery_model = str(obj.get("deliveryModel", "self-managed")).replace("-", " ").title()
        return f"EdgeGatewayService / {delivery_model}"
    if obj["type"] == "capability":
        return "Capability"
    if obj["type"] == "requirement_group":
        return "RequirementGroup"
    if obj["type"] == "decision_record":
        return f"DecisionRecord / {obj.get('category', 'risk')}"
    if obj["type"] == "reference_architecture":
        return "ReferenceArchitecture"
    if obj["type"] == "software_deployment_pattern":
        return "SoftwareDeploymentPattern"
    if obj["type"] == "drafting_session":
        return "DraftingSession"
    if obj["type"] == "host":
        return "Host"
    if obj["type"] == "runtime_service":
        delivery_model = str(obj.get("deliveryModel", "")).replace("-", " ").title()
        return f"RuntimeService / {delivery_model}" if delivery_model else "RuntimeService"
    if obj["type"] == "data_store_service":
        delivery_model = str(obj.get("deliveryModel", "")).replace("-", " ").title()
        return f"DataStoreService / {delivery_model}" if delivery_model else "DataStoreService"
    if obj["type"] == "product_component":
        classification = humanize_slug(str(obj.get("classification", "unknown")))
        return f"ProductComponent / {classification}"
    if obj["type"] == "data_component":
        engine = str(obj.get("targetEngine", "")).replace("-", " ").title()
        return f"DataComponent / {engine}" if engine else "DataComponent"
    if obj["type"] == "domain":
        return "Strategy Domain"
    if obj["type"] == "environment_tier":
        purpose = str(obj.get("purpose", "")).replace("-", " ").title()
        return f"Environment Tier / {purpose}" if purpose else "Environment Tier"
    return str(obj.get("type", "unknown")).replace("_", " ").title()


def internal_component_refs(obj: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[str] = set()

    for component in obj.get("internalComponents", []):
        ref = component.get("ref")
        if ref and ref not in seen:
            refs.append(
                {
                    "ref": ref,
                    "role": component.get("role", "component"),
                    "configuration": component.get("configuration", ""),
                    "notes": component.get("notes", ""),
                }
            )
            seen.add(ref)

    for field_name, role in (
        ("operatingSystemComponent", "os"),
        ("computePlatformComponent", "hardware"),
        ("host", "host"),
        ("primaryTechnologyComponent", "function"),
    ):
        ref = obj.get(field_name)
        if ref and ref not in seen:
            refs.append({"ref": ref, "role": role, "configuration": "", "notes": ""})
            seen.add(ref)

    return refs


def build_requirement_payload(registry: dict[str, dict[str, Any]], workspace_root: Path) -> dict[str, Any]:
    workspace_requirements = load_workspace_requirements(workspace_root)
    groups = sorted(
        [obj for obj in registry.values() if obj.get("type") == "requirement_group"],
        key=lambda item: item.get("name", ""),
    )
    active_ids = set(workspace_requirements["activeRequirementGroups"])
    return {
        "groups": [
            {
                "id": group["uid"],
                "uid": group["uid"],
                "name": group.get("name", group["uid"]),
                "activation": group.get("activation", ""),
                "catalogStatus": group.get("catalogStatus", ""),
                "provider": group.get("provider", {}),
                "authority": group.get("authority", {}),
                "active": group["uid"] in active_ids,
                "description": group.get("description", ""),
                "requirementCount": len(group.get("requirements", [])) if isinstance(group.get("requirements"), list) else 0,
            }
            for group in groups
        ],
        "activeRequirementGroups": workspace_requirements["activeRequirementGroups"],
        "requireActiveRequirementGroupDisposition": workspace_requirements["requireActiveRequirementGroupDisposition"],
    }


def build_sdp_connections(obj: dict[str, Any], all_objects: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Build inter-service connections from relationship objects where both endpoints are deployed in this SDP."""
    connections: list[dict[str, Any]] = []

    if not all_objects:
        return connections

    deployed_uids: set[str] = set()
    for group in obj.get("serviceGroups", []):
        if not isinstance(group, dict):
            continue
        for deployed in group.get("deployableObjects", []):
            if isinstance(deployed, dict) and deployed.get("ref"):
                deployed_uids.add(str(deployed["ref"]))

    for rel in all_objects:
        if rel.get("type") != "relationship":
            continue
        src = str(rel.get("source", "")).strip()
        tgt = str(rel.get("target", "")).strip()
        if not src or not tgt:
            continue
        if src in deployed_uids and tgt in deployed_uids:
            connections.append({
                "from": src,
                "to": tgt,
                "protocol": str(rel.get("technology", "")).strip(),
                "direction": str(rel.get("direction", "outbound")).strip(),
                "port": "",
                "label": str(rel.get("label", "")).strip(),
                "serviceGroup": "",
            })

    return connections


def build_browser_payload(registry: dict[str, dict[str, Any]], workspace_root: Path) -> dict[str, Any]:
    objects = list(registry.values())
    schemas = load_schemas(SCHEMA_ROOT)
    outbound_refs, referenced_by, warnings = build_reference_index(registry)
    risk_marked_rbb_ids = {
        deployed.get("ref")
        for obj in objects
        if obj.get("type") == "software_deployment_pattern"
        for group in obj.get("serviceGroups", [])
        if isinstance(group, dict)
        for deployed in group.get("deployableObjects", [])
        if isinstance(deployed, dict) and deployed.get("riskRef")
    }
    browser_objects: list[dict[str, Any]] = []

    def browser_lifecycle_status(obj: dict[str, Any]) -> str:
        if obj.get("type") == "technology_component":
            return ""
        return obj.get("lifecycleStatus", "unknown")

    def browser_lifecycle_color(status: str) -> str:
        if not status:
            return "#64748b"
        return f"#{LIFECYCLE_COLORS.get(status, LIFECYCLE_COLORS['unknown'])}"

    for obj in objects:
        object_id = obj["uid"]
        schema = select_schema(obj, schemas) or {}
        lifecycle_status = browser_lifecycle_status(obj)
        schema_meta = {
            "requiredFields": schema.get("requiredFields", []),
            "optionalFields": schema.get("optionalFields", []),
            "fieldTypes": schema.get("fieldTypes", {}),
            "enumFields": schema.get("enumFields", {}),
            "enumListFields": schema.get("enumListFields", {}),
            "collectionSchemas": schema.get("collectionSchemas", {}),
            "schemaPath": schema.get("_schema_path", ""),
        }
        browser_objects.append(
            {
                "id": object_id,
                "uid": object_id,
                "name": obj["name"],
                "aliases": obj.get("aliases", []),
                "type": obj["type"],
                "typeLabel": type_label_for(obj),
                "filterType": filter_type_for(obj),
                "category": obj.get("category", ""),
                "deliveryModel": obj.get("deliveryModel", ""),
                "domain": obj.get("domain", ""),
                "description": obj.get("description", ""),
                "version": obj.get("version", ""),
                "catalogStatus": obj.get("catalogStatus", ""),
                "lifecycleStatus": lifecycle_status,
                "status": obj.get("status", ""),
                "businessContext": obj.get("businessContext", {}),
                "product": obj.get("product", ""),
                "runsOn": obj.get("runsOn", ""),
                "subtype": obj.get("subtype", ""),
                "vendor": obj.get("vendor", ""),
                "productName": obj.get("productName", ""),
                "productVersion": obj.get("productVersion", ""),
                "classification": obj.get("classification", ""),
                "platformDependency": obj.get("platformDependency", ""),
                "capabilities": obj.get("capabilities", []),
                "configurations": obj.get("configurations", []),
                "networkPlacement": obj.get("networkPlacement", ""),
                "patchingOwner": obj.get("patchingOwner", ""),
                "complianceCerts": obj.get("complianceCerts", []),
                "requirementGroups": obj.get("requirementGroups", []),
                "requirementImplementations": obj.get("requirementImplementations", []),
                "dataLeavesInfrastructure": obj.get("dataLeavesInfrastructure", None),
                "dataResidencyCommitment": obj.get("dataResidencyCommitment", ""),
                "dpaNotes": obj.get("dpaNotes", ""),
                "vendorSLA": obj.get("vendorSLA", ""),
                "authenticationModel": obj.get("authenticationModel", ""),
                "incidentNotificationProcess": obj.get("incidentNotificationProcess", ""),
                "owner": obj.get("owner", {}),
                "definitionOwner": obj.get("definitionOwner", {}),
                "provider": obj.get("provider", {}),
                "authority": obj.get("authority", {}),
                "shape": shape_for(obj),
                "color": browser_lifecycle_color(lifecycle_status),
                "source": obj.get("_source", ""),
                "tags": obj.get("tags", []),
                "ardCategory": obj.get("category", "") if obj.get("type") == "decision_record" else "",
                "internalComponents": internal_component_refs(obj),
                "architectureNotes": obj.get("architectureNotes", {}),
                "requirements": obj.get("requirements", []),
                "implementations": obj.get("implementations", []),
                "appliesTo": obj.get("appliesTo", {}),
                "inherits": obj.get("inherits", ""),
                "scalingUnits": obj.get("scalingUnits", []),
                "networkZones": obj.get("networkZones", []),
                "sdpConnections": build_sdp_connections(obj, objects) if obj.get("type") == "software_deployment_pattern" else [],
                "serviceGroups": obj.get("serviceGroups", []),
                "tierVariants": obj.get("tierVariants", []),
                "tierId": obj.get("tierId", ""),
                "purpose": obj.get("purpose", ""),
                "availabilityExpectation": obj.get("availabilityExpectation", ""),
                "costPosture": obj.get("costPosture", ""),
                "complianceScope": obj.get("complianceScope", []),
                "parameterSurface": obj.get("parameterSurface", []),
                "followsReferenceArchitecture": obj.get("followsReferenceArchitecture", ""),
                "decisionRecords": obj.get("decisionRecords", []),
                "affectedComponent": obj.get("affectedComponent", ""),
                "impact": obj.get("impact", ""),
                "mitigationPath": obj.get("mitigationPath", ""),
                "decisionRationale": obj.get("decisionRationale", ""),
                "relatedDecisionRecords": obj.get("relatedDecisionRecords", []),
                "linkedObject": obj.get("linkedObject", ""),
                "primaryObjectType": obj.get("primaryObjectType", ""),
                "primaryObjectUid": obj.get("primaryObjectUid", ""),
                "generatedObjects": obj.get("generatedObjects", []),
                "unresolvedQuestions": obj.get("unresolvedQuestions", []),
                "assumptions": obj.get("assumptions", []),
                "nextSteps": obj.get("nextSteps", []),
                "defaultSelection": obj.get("defaultSelection", False),
                "requirementCount": len(obj.get("requirements", [])) if obj.get("type") == "requirement_group" and isinstance(obj.get("requirements"), list) else 0,
                "hasRiskRef": object_id in risk_marked_rbb_ids,
                "outboundRefs": outbound_refs.get(object_id, []),
                "referencedBy": referenced_by.get(object_id, []),
                "editorSchema": schema_meta,
                "detail": to_json(obj),
                "existsInCatalog": True,
            }
        )

    # Build per-object outbound/inbound relationship data from topology_edges
    outbound_rels_by_uid: dict[str, list[dict[str, Any]]] = {}
    inbound_rels_by_uid: dict[str, list[dict[str, Any]]] = {}
    for rel_obj in objects:
        if rel_obj.get("type") != "relationship":
            continue
        src = str(rel_obj.get("source", "")).strip()
        tgt = str(rel_obj.get("target", "")).strip()
        ext_tgt = str(rel_obj.get("externalTarget", "")).strip()
        if not src:
            continue
        rel_entry = {
            "uid": rel_obj.get("uid", ""),
            "name": rel_obj.get("name", ""),
            "label": rel_obj.get("label", ""),
            "technology": rel_obj.get("technology", ""),
            "direction": rel_obj.get("direction", ""),
            "targetUid": tgt,
            "targetName": registry.get(tgt, {}).get("name", "") if tgt else ext_tgt,
            "capabilities": rel_obj.get("capabilities", []),
        }
        outbound_rels_by_uid.setdefault(src, []).append(rel_entry)
        if tgt:
            inbound_entry = {**rel_entry, "sourceUid": src, "sourceName": registry.get(src, {}).get("name", "")}
            inbound_rels_by_uid.setdefault(tgt, []).append(inbound_entry)

    for browser_obj in browser_objects:
        uid = browser_obj["uid"]
        browser_obj["outboundRelationships"] = outbound_rels_by_uid.get(uid, [])
        browser_obj["inboundRelationships"] = inbound_rels_by_uid.get(uid, [])

    browser_lookup = {obj["uid"]: obj for obj in browser_objects}
    filter_values = sorted({obj["type"] for obj in objects})
    impact_lifecycle_types = {
        "reference_architecture",
        "software_deployment_pattern",
        "host",
        "runtime_service",
        "data_store_service",
        "edge_gateway_service",
        "product_component",
        "data_component",
    }
    lifecycle_values = sorted(
        {obj.get("lifecycleStatus", "unknown") for obj in objects if obj.get("type") in impact_lifecycle_types},
        key=lambda value: ["preferred", "existing-only", "candidate", "deprecated", "retired", "unknown"].index(value)
        if value in {"preferred", "existing-only", "candidate", "deprecated", "retired", "unknown"}
        else 999,
    )
    topology_edges = [
        {
            "id": obj["uid"],
            "source": obj.get("source", ""),
            "target": obj.get("target", ""),
            "label": obj.get("label", ""),
            "technology": obj.get("technology", ""),
            "direction": obj.get("direction", ""),
            "name": obj.get("name", ""),
        }
        for obj in objects
        if obj.get("type") == "relationship"
        and obj.get("source")
        and obj.get("target")
    ]

    return {
        "objects": browser_objects,
        "lookup": browser_lookup,
        "lifecycleColors": LIFECYCLE_COLORS,
        "filterValues": filter_values,
        "lifecycleValues": lifecycle_values,
        "referencedBy": referenced_by,
        "warnings": warnings,
        "requirements": build_requirement_payload(registry, workspace_root),
        "vocabulary": load_workspace_vocabulary(workspace_root),
        "businessTaxonomy": load_workspace_business_taxonomy(workspace_root),
        "browserConfig": load_workspace_browser_config(workspace_root),
        "repoUrl": repository_web_url(workspace_root) or repository_web_url(REPO_ROOT),
        "catalogName": workspace_repository_name(workspace_root),
        "logoDataUri": logo_data_uri(),
        "topologyEdges": topology_edges,
    }


BROWSER_DATA_OUTPUT_NAME = "browser-data.js"
BROWSER_ASSET_OUTPUT_DIR = "assets"
BROWSER_ASSET_ROOT = FRAMEWORK_ROOT / "browser"
BROWSER_INDEX_TEMPLATE_PATH = BROWSER_ASSET_ROOT / "index.template.html"
USER_MANUAL_TEMPLATE_PATH = BROWSER_ASSET_ROOT / "user-manual.html"
BROWSER_STATIC_ASSET_NAMES = ("draft-browser.css", "draft-browser-sdp.css", "draft-browser-targets.css", "draft-browser.js")
BROWSER_STATIC_FONT_DIR = "fonts"
WORKSPACE_THEME_OUTPUT_NAME = "workspace-theme.css"
DEFAULT_WORKSPACE_THEME_PATH = BROWSER_ASSET_ROOT / WORKSPACE_THEME_OUTPUT_NAME
WORKSPACE_THEME_CANDIDATES = (
    Path("configurations/browser/theme.css"),
    Path(".draft/browser/theme.css"),
)


def browser_asset_dir(output_path: Path) -> Path:
    return output_path.parent / BROWSER_ASSET_OUTPUT_DIR


def workspace_theme_source(workspace_root: Path) -> Path:
    for candidate in WORKSPACE_THEME_CANDIDATES:
        source = workspace_root / candidate
        if source.exists():
            return source
    return DEFAULT_WORKSPACE_THEME_PATH


def write_browser_data(payload: dict[str, Any], asset_dir: Path) -> Path:
    data_path = asset_dir / BROWSER_DATA_OUTPUT_NAME
    data = json.dumps(payload, default=str, indent=2)
    data_path.write_text(f"window.DRAFT_BROWSER_DATA = {data};\n", encoding="utf-8")
    return data_path


def shell_asset_has_drifted(source: Path, target: Path) -> bool:
    """Return True if the framework source file differs from the installed target."""
    if not target.exists():
        return False
    return source.read_bytes() != target.read_bytes()


def copy_browser_assets(workspace_root: Path, output_path: Path, *, refresh_shell: bool = False) -> list[Path]:
    """Copy browser shell assets to the output asset directory.

    By default (refresh_shell=False) each file is only written if it does not
    already exist in the target directory.  This preserves edits made directly
    to docs/assets/ by design tooling (e.g. claude.ai/design) without requiring
    those changes to be reflected back into framework/browser/ first.

    Pass refresh_shell=True (via --refresh-shell on the CLI) to force-overwrite
    all shell assets from the framework source — use this when pulling a
    framework design update.

    On a normal run, if any framework source file differs from the installed
    target a warning is printed so engineers know --refresh-shell is available.
    """
    asset_dir = browser_asset_dir(output_path)
    asset_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for asset_name in BROWSER_STATIC_ASSET_NAMES:
        source = BROWSER_ASSET_ROOT / asset_name
        target = asset_dir / asset_name
        if refresh_shell or not target.exists():
            shutil.copy2(source, target)
            copied.append(target)
        elif shell_asset_has_drifted(source, target):
            print(
                f"[browser] {asset_name} has been updated in the framework. "
                "Run with --refresh-shell to apply the update.",
                file=sys.stderr,
            )
    theme_source = workspace_theme_source(workspace_root)
    theme_target = asset_dir / WORKSPACE_THEME_OUTPUT_NAME
    if refresh_shell or not theme_target.exists():
        shutil.copy2(theme_source, theme_target)
        copied.append(theme_target)
    # Copy self-hosted fonts directory (file-by-file to avoid rmtree on mounted volumes)
    fonts_source = BROWSER_ASSET_ROOT / BROWSER_STATIC_FONT_DIR
    if fonts_source.is_dir():
        fonts_target = asset_dir / BROWSER_STATIC_FONT_DIR
        fonts_target.mkdir(parents=True, exist_ok=True)
        for font_file in fonts_source.iterdir():
            if not font_file.is_file():
                continue
            dest = fonts_target / font_file.name
            if refresh_shell or not dest.exists():
                shutil.copy2(font_file, dest)
                copied.append(dest)
    # Download world-atlas for the deployment targets map (bundled to avoid CDN dependency)
    world_atlas_target = asset_dir / "world-atlas" / "countries-110m.json"
    if refresh_shell or not world_atlas_target.exists():
        world_atlas_target.parent.mkdir(parents=True, exist_ok=True)
        world_atlas_url = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json"
        try:
            import urllib.request
            print(f"[browser] Downloading world-atlas from {world_atlas_url} …", file=sys.stderr)
            urllib.request.urlretrieve(world_atlas_url, world_atlas_target)
            copied.append(world_atlas_target)
        except Exception as exc:  # noqa: BLE001
            print(f"[browser] Warning: could not download world-atlas ({exc}). Map will fall back to CDN.", file=sys.stderr)
    return copied


def write_browser(payload: dict[str, Any], output_path: Path, workspace_root: Path, *, refresh_shell: bool = False) -> list[Path]:
    """Write the browser output directory.

    The data layer (browser-data.js) is always regenerated from the current
    catalog state.  The shell layer (draft-browser.css, draft-browser.js,
    index.html) is treated as install-once: files are only written when they do
    not already exist unless refresh_shell=True is passed.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    copied = copy_browser_assets(workspace_root, output_path, refresh_shell=refresh_shell)
    data_path = write_browser_data(payload, browser_asset_dir(output_path))
    if refresh_shell or not output_path.exists():
        template = BROWSER_INDEX_TEMPLATE_PATH.read_text(encoding="utf-8")
        output_path.write_text(template, encoding="utf-8")
        copied.append(output_path)
    return [data_path, *copied]


USER_MANUAL_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f7f4ef;
      --surface: #ffffff;
      --surface-soft: #f1ece4;
      --surface-strong: #e6ded2;
      --text: #2d2721;
      --subtle: #5f564b;
      --muted: #7a6e60;
      --border: rgba(122, 110, 96, 0.24);
      --accent: #7c3a6b;
      --accent-strong: #5d2950;
      --accent-soft: rgba(124, 58, 107, 0.10);
      --blue: #2a6fdb;
      --green: #1f8a5b;
      --code: #241f1a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 15px/1.65 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .layout {{
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      min-height: 100vh;
    }}
    .sidebar {{
      position: sticky;
      top: 0;
      height: 100vh;
      overflow-y: auto;
      padding: 22px 18px;
      border-right: 1px solid var(--border);
      background: var(--surface);
    }}
    .sidebar h1 {{
      margin: 0 0 4px;
      font-size: 17px;
      line-height: 1.25;
    }}
    .sidebar p {{
      margin: 0 0 20px;
      color: var(--muted);
      font-size: 12px;
    }}
    .toc {{
      display: grid;
      gap: 2px;
    }}
    .toc a {{
      display: block;
      border-radius: 7px;
      padding: 6px 8px;
      color: var(--subtle);
      font-size: 13px;
      text-decoration: none;
    }}
    .toc a:hover {{
      background: var(--surface-soft);
      color: var(--text);
    }}
    .toc .level-3 {{
      padding-left: 22px;
      font-size: 12px;
    }}
    .back-link {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 7px 10px;
      margin-bottom: 18px;
      color: var(--accent-strong);
      background: var(--accent-soft);
      font-size: 13px;
      font-weight: 600;
      text-decoration: none;
    }}
    main {{
      min-width: 0;
      padding: 42px 56px 72px;
    }}
    .content {{
      max-width: 980px;
      margin: 0 auto;
    }}
    h1, h2, h3, h4 {{
      color: var(--text);
      line-height: 1.25;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: clamp(32px, 5vw, 52px);
      letter-spacing: 0;
    }}
    h2 {{
      margin-top: 44px;
      padding-top: 18px;
      border-top: 1px solid var(--border);
      font-size: 28px;
      letter-spacing: 0;
    }}
    h3 {{
      margin-top: 28px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    h4 {{
      margin-top: 22px;
      font-size: 16px;
      letter-spacing: 0;
    }}
    p {{ margin: 12px 0; }}
    ul, ol {{ padding-left: 24px; }}
    li {{ margin: 6px 0; }}
    code {{
      border-radius: 5px;
      padding: 2px 5px;
      background: var(--surface-strong);
      color: var(--code);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.92em;
    }}
    pre {{
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      background: #241f1a;
      color: #f8f1e8;
    }}
    pre code {{
      padding: 0;
      background: transparent;
      color: inherit;
    }}
    table {{
      width: 100%;
      margin: 18px 0;
      border-collapse: collapse;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
      text-align: left;
    }}
    th {{
      background: var(--surface-soft);
      color: var(--accent-strong);
      font-size: 13px;
    }}
    .content img {{
      display: block;
      max-width: 100%;
      height: auto;
      margin: 20px auto;
      border: 1px solid var(--border);
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.06);
      background: var(--surface);
    }}
    tr:last-child td {{ border-bottom: 0; }}
    blockquote {{
      margin: 16px 0;
      padding: 12px 16px;
      border-left: 4px solid var(--green);
      background: rgba(31, 138, 91, 0.08);
      color: var(--subtle);
    }}
    .footer {{
      margin-top: 54px;
      color: var(--muted);
      font-size: 12px;
    }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidebar {{
        position: static;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--border);
      }}
      .toc {{ grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }}
      .toc .level-3 {{ padding-left: 8px; }}
      main {{ padding: 28px 20px 52px; }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <a class="back-link" href="index.html">Back to catalog</a>
      <h1>{title}</h1>
      <p>Generated {generated_date} from the framework-owned Markdown source.</p>
      <nav class="toc" aria-label="Table of contents">
        {toc}
      </nav>
    </aside>
    <main>
      <article class="content">
        {content}
        <div class="footer">Generated from Markdown by framework/tools/generate_browser.py.</div>
      </article>
    </main>
  </div>
</body>
</html>
"""


def slugify_heading(text: str, existing: dict[str, int]) -> str:
    plain = re.sub(r"`([^`]+)`", r"\1", text)
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
    base = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-") or "section"
    count = existing.get(base, 0)
    existing[base] = count + 1
    return base if count == 0 else f"{base}-{count + 1}"


def render_inline_markdown(text: str) -> str:
    rendered = html.escape(text, quote=False)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda match: (
            f'<img src="{html.escape(match.group(2), quote=True)}" '
            f'alt="{html.escape(match.group(1), quote=True)}">'
        ),
        rendered,
    )
    rendered = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: f'<a href="{html.escape(match.group(2), quote=True)}">{match.group(1)}</a>',
        rendered,
    )
    return rendered


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_delimiter(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def render_markdown_document(markdown_text: str) -> tuple[str, list[dict[str, str]]]:
    lines = markdown_text.splitlines()
    rendered: list[str] = []
    headings: list[dict[str, str]] = []
    heading_ids: dict[str, int] = {}
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            language = stripped.removeprefix("```").strip()
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            class_attr = f' class="language-{html.escape(language, quote=True)}"' if language else ""
            rendered.append(f"<pre><code{class_attr}>{html.escape(chr(10).join(code_lines))}</code></pre>")
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            heading_id = slugify_heading(text, heading_ids)
            if level in {2, 3}:
                headings.append({"level": str(level), "text": text, "id": heading_id})
            rendered.append(f'<h{level} id="{heading_id}">{render_inline_markdown(text)}</h{level}>')
            i += 1
            continue

        if stripped.startswith("> "):
            quote_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote_lines.append(lines[i].strip()[2:].strip())
                i += 1
            rendered.append(f"<blockquote>{render_inline_markdown(' '.join(quote_lines))}</blockquote>")
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and is_table_delimiter(lines[i + 1].strip()):
            headers = split_table_row(stripped)
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_table_row(lines[i].strip()))
                i += 1
            head_markup = "".join(f"<th>{render_inline_markdown(cell)}</th>" for cell in headers)
            body_markup = ""
            for row in rows:
                body_markup += "<tr>" + "".join(f"<td>{render_inline_markdown(cell)}</td>" for cell in row) + "</tr>"
            rendered.append(f"<table><thead><tr>{head_markup}</tr></thead><tbody>{body_markup}</tbody></table>")
            continue

        if re.match(r"^[-*]\s+", stripped):
            items: list[str] = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            rendered.append("<ul>" + "".join(f"<li>{render_inline_markdown(item)}</li>" for item in items) + "</ul>")
            continue

        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            rendered.append("<ol>" + "".join(f"<li>{render_inline_markdown(item)}</li>" for item in items) + "</ol>")
            continue

        paragraph_lines = [stripped]
        i += 1
        while i < len(lines):
            next_line = lines[i].strip()
            if (
                not next_line
                or next_line.startswith("```")
                or re.match(r"^(#{1,6})\s+", next_line)
                or next_line.startswith("> ")
                or re.match(r"^[-*]\s+", next_line)
                or re.match(r"^\d+\.\s+", next_line)
                or (next_line.startswith("|") and i + 1 < len(lines) and is_table_delimiter(lines[i + 1].strip()))
            ):
                break
            paragraph_lines.append(next_line)
            i += 1
        rendered.append(f"<p>{render_inline_markdown(' '.join(paragraph_lines))}</p>")

    return "\n".join(rendered), headings


def markdown_document_title(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line.strip())
        if match:
            return re.sub(r"`([^`]+)`", r"\1", match.group(1).strip())
    return fallback


def write_markdown_page(source_path: Path, output_path: Path, fallback_title: str) -> bool:
    if not source_path.exists():
        return False
    markdown_text = source_path.read_text(encoding="utf-8")
    title = markdown_document_title(markdown_text, fallback_title)
    content, headings = render_markdown_document(markdown_text)
    toc = "\n".join(
        f'<a class="level-{heading["level"]}" href="#{heading["id"]}">{render_inline_markdown(heading["text"])}</a>'
        for heading in headings
    )
    rendered = USER_MANUAL_HTML_TEMPLATE.format(
        title=html.escape(title, quote=False),
        generated_date=date.today().isoformat(),
        toc=toc,
        content=content,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    return True


def write_user_manual(source_path: Path, output_path: Path) -> bool:
    """Copy the pre-built user manual HTML template to the output path.

    Replaces the logo src placeholder with the actual base64 data URI so the
    page is fully self-contained and works regardless of the assets directory
    layout.

    Falls back to Markdown rendering if the HTML template is not present
    (preserves backward compatibility for workspaces that vendor an older
    framework without the template file).
    """
    if USER_MANUAL_TEMPLATE_PATH.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = USER_MANUAL_TEMPLATE_PATH.read_text(encoding="utf-8")
        logo_uri = logo_data_uri()
        if logo_uri:
            content = content.replace('src="assets/draft-logo.png"', f'src="{logo_uri}"')
        output_path.write_text(content, encoding="utf-8")
        return True
    return write_markdown_page(source_path, output_path, "DRAFT User Manual")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output_path = args.output.resolve()
    manual_output_path = (args.manual_output.resolve() if args.manual_output else output_path.parent / USER_MANUAL_OUTPUT_NAME)
    vocabulary_output_path = output_path.parent / COMPANY_VOCABULARY_OUTPUT_NAME
    registry = load_objects(args.workspace.resolve())
    payload = build_browser_payload(registry, args.workspace.resolve())
    write_browser(payload, output_path, args.workspace.resolve(), refresh_shell=args.refresh_shell)
    manual_generated = False
    vocabulary_generated = False
    if not args.skip_user_manual:
        manual_generated = write_user_manual(USER_MANUAL_SOURCE_PATH, manual_output_path)
        vocabulary_generated = write_markdown_page(
            COMPANY_VOCABULARY_SOURCE_PATH,
            vocabulary_output_path,
            "Company Vocabulary",
        )
    for warning in payload.get("warnings", []):
        print(warning, file=sys.stderr)
    print(f"Generated {display_path(output_path)} with {len(payload['objects'])} objects.")
    if manual_generated:
        template_used = USER_MANUAL_TEMPLATE_PATH if USER_MANUAL_TEMPLATE_PATH.exists() else USER_MANUAL_SOURCE_PATH
        verb = "Copied" if USER_MANUAL_TEMPLATE_PATH.exists() else "Generated"
        print(f"{verb} {display_path(manual_output_path)} from {display_path(template_used)}.")
    if vocabulary_generated:
        print(f"Generated {display_path(vocabulary_output_path)} from {display_path(COMPANY_VOCABULARY_SOURCE_PATH)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
