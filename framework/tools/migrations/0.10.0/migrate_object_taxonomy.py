#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import yaml


TYPE_MAP = {
    "host_standard": "host",
    "database_standard": "data_at_rest_service",
    "service_standard": "runtime_service",
    "paas_service_standard": "runtime_service",
    "saas_service_standard": "runtime_service",
    "appliance_component": "network_service",
}

PRIMARY_TYPE_MAP = {
    "host_standard": "host",
    "database_standard": "data_at_rest_service",
    "service_standard": "runtime_service",
    "paas_service_standard": "runtime_service",
    "saas_service_standard": "runtime_service",
    "appliance_component": "network_service",
}

EXPAND_APPLIES_TO = {
    "host_standard": ["host"],
    "database_standard": ["data_at_rest_service"],
    "service_standard": ["runtime_service", "network_service"],
    "paas_service_standard": ["runtime_service", "data_at_rest_service", "network_service"],
    "saas_service_standard": ["runtime_service", "data_at_rest_service", "network_service"],
    "appliance_component": ["runtime_service", "data_at_rest_service", "network_service"],
}

TEXT_REPLACEMENTS = {
    "Host Standard": "Host",
    "Host Standards": "Hosts",
    "host_standard": "host",
    "host-standards": "hosts",
    "hostStandard": "host",
    "Service Standard": "Runtime Service",
    "Service Standards": "Runtime Services",
    "service_standard": "runtime_service",
    "service-standards": "runtime-services",
    "Database Standard": "Data-at-Rest Service",
    "Database Standards": "Data-at-Rest Services",
    "database_standard": "data_at_rest_service",
    "database-standards": "data-at-rest-services",
    "PaaS Service Standard": "PaaS Delivery",
    "PaaS Service Standards": "PaaS Delivery",
    "paas_service_standard": "runtime_service",
    "paas-services": "runtime-services",
    "SaaS Service Standard": "SaaS Delivery",
    "SaaS Service Standards": "SaaS Delivery",
    "saas_service_standard": "runtime_service",
    "saas-services": "runtime-services",
    "Appliance Component": "NetworkService",
    "Appliance Components": "Network Services",
    "appliance_component": "network_service",
    "appliance-components": "network-services",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate DRAFT pre-1.0 object taxonomy to 0.10.0.")
    parser.add_argument("root", type=Path, help="Framework or workspace repository root.")
    parser.add_argument("--dry-run", action="store_true", help="Report planned changes without writing files.")
    return parser.parse_args()


def read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(path: Path, data: Any, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=False, width=1000),
        encoding="utf-8",
    )


def yaml_files(root: Path) -> list[Path]:
    skip_parts = {".git", "node_modules", "__pycache__"}
    files: list[Path] = []
    for path in sorted(root.rglob("*.yaml")):
        parts = path.relative_to(root).parts
        if any(part in skip_parts for part in parts):
            continue
        if len(parts) >= 2 and parts[0] == ".draft" and parts[1] == "framework":
            continue
        files.append(path)
    return files


def is_mapping(value: Any) -> bool:
    return isinstance(value, dict)


def classify_service_family(path: Path, obj: dict[str, Any]) -> str:
    old_type = str(obj.get("type") or "")
    text = " ".join(
        str(value or "")
        for value in (
            path.as_posix(),
            obj.get("name"),
            obj.get("description"),
            obj.get("productName"),
            obj.get("vendor"),
        )
    ).lower()
    tags = [str(tag).lower() for tag in obj.get("tags", []) or []]

    if old_type == "database_standard":
        if "cache" in text or "redis" in text or "memcached" in text:
            return "runtime_service"
        return "data_at_rest_service"

    if old_type == "paas_service_standard":
        data_terms = [
            "s3",
            "fsx",
            "dynamodb",
            "aurora",
            "postgres",
            "neptune",
            "opensearch",
            "mongodb",
            "snowflake",
            "object storage",
            "file storage",
            "database",
            "data",
        ]
        edge_terms = ["alb", "nlb", "cloudfront", "load balancer", "api gateway", "waf", "firewall", "ingress"]
        if any(term in text for term in data_terms):
            return "data_at_rest_service"
        if any(term in text for term in edge_terms):
            return "network_service"
        return "runtime_service"

    if old_type == "saas_service_standard":
        if any(term in text for term in ["snowflake", "database", "data warehouse", "object storage", "file"]):
            return "data_at_rest_service"
        if any(term in text for term in ["waf", "firewall", "cdn", "gateway", "proxy"]):
            return "network_service"
        return "runtime_service"

    if old_type == "appliance_component":
        if any(term in text for term in ["database", "storage", "file", "object"]):
            return "data_at_rest_service"
        if any(term in text for term in ["runtime", "lambda", "application"]):
            return "runtime_service"
        return "network_service"

    edge_terms = [
        "gateway",
        "waf",
        "firewall",
        "load balancer",
        "reverse proxy",
        "api proxy",
        "ingress",
        "edge",
        "kong",
        "nginx gateway",
        "f5",
        "imperva",
    ]
    if any(term in text for term in edge_terms) or any(tag in {"gateway", "waf", "firewall", "edge"} for tag in tags):
        return "network_service"
    return "runtime_service"


def delivery_model_for(old_type: str) -> str:
    if old_type == "paas_service_standard":
        return "paas"
    if old_type == "saas_service_standard":
        return "saas"
    if old_type == "appliance_component":
        return "appliance"
    return "self-managed"


def migrate_object_type(path: Path, obj: dict[str, Any]) -> bool:
    old_type = str(obj.get("type") or "")
    if old_type == "host_standard":
        obj["type"] = "host"
        return True
    if old_type in {"service_standard", "database_standard", "paas_service_standard", "saas_service_standard", "appliance_component"}:
        obj["type"] = classify_service_family(path, obj)
        obj.setdefault("deliveryModel", delivery_model_for(old_type))
        if old_type == "appliance_component":
            if "classification" in obj:
                obj.setdefault("technologyClassification", obj.pop("classification"))
        return True
    return False


def migrate_requirement_group(obj: dict[str, Any]) -> bool:
    changed = False
    name = str(obj.get("name") or "")
    if name == "Host Requirement Group":
        obj["appliesTo"] = ["host"]
        changed = True
    elif name == "General Service Requirement Group":
        obj["name"] = "Service Behavior Requirement Group"
        obj["description"] = "Structured checklist of required questions and answers used to define complete and correct Runtime and Network Services."
        obj["appliesTo"] = ["runtime_service", "network_service"]
        obj.pop("appliesToQualifiers", None)
        changed = True
    elif name == "DBMS Service Requirement Group":
        obj["name"] = "Data-at-Rest Service Requirement Group"
        obj["description"] = "Additional data-at-rest checklist items extending the service behavior Requirement Group for durable data, recovery, and access control."
        obj["appliesTo"] = ["data_at_rest_service"]
        obj.pop("appliesToQualifiers", None)
        changed = True
    elif name == "Appliance Component Requirement Group":
        obj["name"] = "Appliance Delivery Requirement Group"
        obj["description"] = "Structured requirements used when a Runtime, Data-at-Rest, or NetworkService uses appliance delivery and the underlying host is blackbox to the adopter."
        obj["appliesTo"] = ["runtime_service", "data_at_rest_service", "network_service"]
        obj["appliesToQualifiers"] = {"deliveryModel": "appliance"}
        changed = True
    elif name == "PaaS Service Requirement Group":
        obj["name"] = "PaaS Delivery Requirement Group"
        obj["description"] = "Structured requirements used when a Runtime, Data-at-Rest, or NetworkService is vendor-managed inside the organization's cloud boundary."
        obj["appliesTo"] = ["runtime_service", "data_at_rest_service", "network_service"]
        obj["appliesToQualifiers"] = {"deliveryModel": "paas"}
        changed = True
    elif name == "SaaS Service Requirement Group":
        obj["name"] = "SaaS Delivery Requirement Group"
        obj["description"] = "Structured requirements used when a Runtime, Data-at-Rest, or NetworkService is consumed as a vendor-managed external service."
        obj["appliesTo"] = ["runtime_service", "data_at_rest_service", "network_service"]
        obj["appliesToQualifiers"] = {"deliveryModel": "saas"}
        changed = True
    return changed


def replace_string(value: str, context_key: str | None = None) -> Any:
    if context_key in {"type", "primaryObjectType"}:
        return PRIMARY_TYPE_MAP.get(value, TYPE_MAP.get(value, value))
    if context_key in {"appliesTo"}:
        return EXPAND_APPLIES_TO.get(value, TYPE_MAP.get(value, value))
    return TYPE_MAP.get(value, value)


def recursively_migrate(value: Any, context_key: str | None = None) -> tuple[Any, bool]:
    changed = False
    if isinstance(value, str):
        replacement = replace_string(value, context_key)
        if replacement != value:
            return replacement, True
        return value, False
    if isinstance(value, list):
        new_values: list[Any] = []
        for item in value:
            migrated, item_changed = recursively_migrate(item, context_key)
            changed = changed or item_changed
            if isinstance(migrated, list):
                for nested in migrated:
                    if nested not in new_values:
                        new_values.append(nested)
            else:
                new_values.append(migrated)
        return new_values, changed
    if isinstance(value, dict):
        new_mapping: dict[Any, Any] = {}
        for key, item in value.items():
            new_key = "host" if key == "hostStandard" else key
            migrated, item_changed = recursively_migrate(item, str(new_key))
            changed = changed or item_changed or new_key != key
            new_mapping[new_key] = migrated
        return new_mapping, changed
    return value, False


def migrate_service_group_appliances(obj: dict[str, Any]) -> bool:
    changed = False
    for group in obj.get("serviceGroups", []) or []:
        if not isinstance(group, dict):
            continue
        standards = group.pop("standards", None)
        if standards is not None:
            group["deployableObjects"] = standards if isinstance(standards, list) else []
            changed = True

        appliances = group.pop("applianceComponents", None)
        if appliances:
            deployable_objects = group.setdefault("deployableObjects", [])
            if isinstance(deployable_objects, list):
                for appliance in appliances:
                    if isinstance(appliance, dict) and appliance.get("ref"):
                        entry = {"ref": appliance["ref"], "diagramTier": "utility"}
                        if appliance.get("notes"):
                            entry["notes"] = appliance["notes"]
                        deployable_objects.append(entry)
                        changed = True
    return changed


def target_path_for(path: Path, root: Path, obj: dict[str, Any]) -> Path:
    rel = path.relative_to(root)
    parts = list(rel.parts)
    folder_by_type = {
        "host": "hosts",
        "runtime_service": "runtime-services",
        "network_service": "network-services",
        "data_at_rest_service": "data-at-rest-services",
    }
    old_catalog_folders = {
        "host-standards",
        "service-standards",
        "database-standards",
        "paas-services",
        "saas-services",
        "appliance-components",
    }
    for index, part in enumerate(parts[:-1]):
        if part in old_catalog_folders:
            replacement = folder_by_type.get(str(obj.get("type") or ""))
            if replacement:
                parts[index] = replacement
                break
    filename = parts[-1]
    filename = filename.replace("host-standard", "host")
    filename = filename.replace("service-standard", "runtime-service")
    filename = filename.replace("database-standard", "data-at-rest-service")
    filename = filename.replace("paas-service", str(obj.get("type") or "runtime-service").replace("_", "-"))
    filename = filename.replace("saas-service", str(obj.get("type") or "runtime-service").replace("_", "-"))
    filename = filename.replace("appliance", str(obj.get("type") or "network-service").replace("_", "-"))
    parts[-1] = filename
    return root.joinpath(*parts)


def migrate_yaml_file(path: Path, root: Path, dry_run: bool) -> tuple[Path, bool]:
    try:
        data = read_yaml(path)
    except Exception:
        return path, False
    if not isinstance(data, dict):
        return path, False

    changed = migrate_object_type(path, data)
    migrated, recursive_changed = recursively_migrate(data)
    data = migrated
    changed = changed or recursive_changed
    changed = migrate_requirement_group(data) or changed
    changed = migrate_service_group_appliances(data) or changed

    target = target_path_for(path, root, data)
    if target != path:
        changed = True
    if changed:
        write_yaml(target, data, dry_run)
        if target != path and not dry_run:
            path.unlink()
    return target, changed


def migrate_text_file(path: Path, dry_run: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    migrated = text
    for before, after in TEXT_REPLACEMENTS.items():
        migrated = migrated.replace(before, after)
    if migrated == text:
        return False
    if not dry_run:
        path.write_text(migrated, encoding="utf-8")
    return True


def remove_empty_catalog_dirs(root: Path, dry_run: bool) -> None:
    for folder in [
        "catalog/appliance-components",
        "catalog/host-standards",
        "catalog/service-standards",
        "catalog/database-standards",
        "catalog/paas-services",
        "catalog/saas-services",
        "examples/catalog/appliance-components",
        "examples/catalog/host-standards",
        "examples/catalog/service-standards",
        "examples/catalog/database-standards",
        "examples/catalog/paas-services",
        "examples/catalog/saas-services",
    ]:
        path = root / folder
        if path.exists() and path.is_dir() and not any(path.iterdir()) and not dry_run:
            path.rmdir()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    changed_paths: list[Path] = []

    for path in yaml_files(root):
        target, changed = migrate_yaml_file(path, root, args.dry_run)
        if changed:
            changed_paths.append(target)

    text_candidates = [
        *root.glob("templates/*.tmpl"),
        *root.glob("framework/docs/*.md"),
        root / "AGENTS.md",
        root / "README.md",
        root / "draft_table" / "catalog.py",
        root / "draft_table" / "repo.py",
        root / "draft_table" / "web.py",
        root / "draft_table" / "draftsman.py",
    ]
    for path in text_candidates:
        if path.exists() and path.is_file() and migrate_text_file(path, args.dry_run):
            changed_paths.append(path)

    if not args.dry_run:
        remove_empty_catalog_dirs(root, args.dry_run)

    print(f"Migrated {len(changed_paths)} files.")
    for path in changed_paths[:50]:
        print(path.relative_to(root).as_posix())
    if len(changed_paths) > 50:
        print(f"... {len(changed_paths) - 50} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
