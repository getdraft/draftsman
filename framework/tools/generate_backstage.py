#!/usr/bin/env python3
"""Generate Backstage catalog-info.yaml files from a DRAFT workspace catalog.

Usage:
    python3 framework/tools/generate_backstage.py [--workspace PATH] [--output DIR]

The exporter reads the DRAFT catalog and emits Backstage entity files into the
output directory (default: backstage/ inside the workspace root). Each mappable
DRAFT object produces one catalog-info.yaml file named by the object UID.

Object mapping:
  domain           → System  (groups components by business domain)
  system           → System  (groups components by explicit boundary)
  runtime_service  → Component (spec.type: service)
  data_store_service → Component (spec.type: service)
  network_service → Component (spec.type: service)
  product_component  → Component (spec.type: service)
  technology_component → Resource

Lifecycle mapping:
  preferred      → production
  existing-only  → production
  candidate      → experimental
  deprecated     → deprecated
  retired        → deprecated
  (unknown)      → production
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = FRAMEWORK_ROOT.parent
WORKSPACE_ROOT = REPO_ROOT.parent if REPO_ROOT.name == ".draft" else REPO_ROOT
DEFAULT_WORKSPACE_ROOT = WORKSPACE_ROOT if REPO_ROOT.name == ".draft" else REPO_ROOT / "examples"
SKIP_DIRS = {"tools", "schemas", "docs", "adrs", ".github", ".git", ".draft"}

MAPPABLE_TYPES = {
    "domain",
    "system",
    "runtime_service",
    "data_store_service",
    "network_service",
    "product_component",
    "technology_component",
}

SERVICE_TYPES = {"runtime_service", "data_store_service", "network_service", "product_component"}
SYSTEM_TYPES = {"domain", "system"}
RESOURCE_TYPES = {"technology_component"}

LIFECYCLE_MAP = {
    "preferred": "production",
    "existing-only": "production",
    "candidate": "experimental",
    "deprecated": "deprecated",
    "retired": "deprecated",
}


def discover_yaml_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*.yaml")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return files


def workspace_yaml_roots(workspace_root: Path) -> list[Path]:
    roots = []
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


def load_catalog(workspace_root: Path) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    seen: set[Path] = set()
    for root in workspace_yaml_roots(workspace_root):
        for path in discover_yaml_files(root):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                with path.open("r", encoding="utf-8") as handle:
                    data = yaml.safe_load(handle) or {}
                if isinstance(data, dict) and data.get("uid") and data.get("type"):
                    catalog[str(data["uid"])] = data
            except Exception:
                pass
    return catalog


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.lower().strip()).strip("-") or "unknown"


def backstage_lifecycle(obj: dict[str, Any]) -> str:
    status = obj.get("lifecycleStatus", "")
    return LIFECYCLE_MAP.get(str(status), "production")


def backstage_owner(obj: dict[str, Any]) -> str:
    owner = obj.get("owner") or obj.get("definitionOwner") or {}
    if isinstance(owner, dict):
        team = owner.get("team") or owner.get("contact") or ""
        if team:
            return slugify(str(team))
    return "unknown"


def backstage_system(obj: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> str | None:
    for uid, candidate in catalog.items():
        if candidate.get("type") not in SYSTEM_TYPES:
            continue
        if candidate.get("type") == "system":
            containers = candidate.get("containers") or []
            if isinstance(containers, list):
                for c in containers:
                    if isinstance(c, dict) and c.get("ref") == obj.get("uid"):
                        return slugify(str(candidate.get("name") or uid))
        if candidate.get("type") == "domain":
            domain_uid = obj.get("domain")
            if domain_uid and domain_uid == uid:
                return slugify(str(candidate.get("name") or uid))
    return None


def entity_for_component(obj: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    name = slugify(str(obj.get("name") or obj.get("uid") or "unknown"))
    system = backstage_system(obj, catalog)
    tags = [str(t) for t in (obj.get("tags") or []) if t]
    annotations: dict[str, str] = {
        "draft/uid": str(obj.get("uid") or ""),
        "draft/type": str(obj.get("type") or ""),
    }
    if obj.get("lifecycleStatus"):
        annotations["draft/lifecycleStatus"] = str(obj["lifecycleStatus"])
    if obj.get("deliveryModel"):
        annotations["draft/deliveryModel"] = str(obj["deliveryModel"])
    spec: dict[str, Any] = {
        "type": "service",
        "lifecycle": backstage_lifecycle(obj),
        "owner": backstage_owner(obj),
    }
    if system:
        spec["system"] = system
    entity: dict[str, Any] = {
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "Component",
        "metadata": {
            "name": name,
            "title": str(obj.get("name") or name),
            "annotations": annotations,
        },
        "spec": spec,
    }
    if obj.get("description"):
        entity["metadata"]["description"] = str(obj["description"])
    if tags:
        entity["metadata"]["tags"] = tags
    return entity


def entity_for_system(obj: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    name = slugify(str(obj.get("name") or obj.get("uid") or "unknown"))
    annotations: dict[str, str] = {
        "draft/uid": str(obj.get("uid") or ""),
        "draft/type": str(obj.get("type") or ""),
    }
    entity: dict[str, Any] = {
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "System",
        "metadata": {
            "name": name,
            "title": str(obj.get("name") or name),
            "annotations": annotations,
        },
        "spec": {
            "owner": backstage_owner(obj),
        },
    }
    if obj.get("description"):
        entity["metadata"]["description"] = str(obj["description"])
    tags = [str(t) for t in (obj.get("tags") or []) if t]
    if tags:
        entity["metadata"]["tags"] = tags
    return entity


def entity_for_resource(obj: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    name = slugify(str(obj.get("name") or obj.get("uid") or "unknown"))
    annotations: dict[str, str] = {
        "draft/uid": str(obj.get("uid") or ""),
        "draft/type": "technology_component",
    }
    if obj.get("classification"):
        annotations["draft/classification"] = str(obj["classification"])
    if obj.get("productVersion"):
        annotations["draft/productVersion"] = str(obj["productVersion"])
    entity: dict[str, Any] = {
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "Resource",
        "metadata": {
            "name": name,
            "title": str(obj.get("name") or name),
            "annotations": annotations,
        },
        "spec": {
            "type": str(obj.get("classification") or "software"),
            "owner": backstage_owner(obj),
        },
    }
    if obj.get("description"):
        entity["metadata"]["description"] = str(obj["description"])
    return entity


def generate_entity(obj: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    obj_type = obj.get("type")
    if obj_type in SYSTEM_TYPES:
        return entity_for_system(obj, catalog)
    if obj_type in SERVICE_TYPES:
        return entity_for_component(obj, catalog)
    if obj_type in RESOURCE_TYPES:
        return entity_for_resource(obj, catalog)
    return None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export DRAFT catalog objects as Backstage catalog-info.yaml files."
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE_ROOT,
        help="Workspace root containing catalog/ and configurations/. Defaults to examples/.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory for generated Backstage files. Defaults to <workspace>/backstage/.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated YAML to stdout instead of writing files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    workspace_root = args.workspace.resolve()
    output_dir = args.output.resolve() if args.output else workspace_root / "backstage"

    catalog = load_catalog(workspace_root)
    if not catalog:
        print("No catalog objects found. Check the workspace path.", file=sys.stderr)
        return 1

    entities: list[tuple[str, dict[str, Any]]] = []
    skipped = 0
    for uid, obj in sorted(catalog.items()):
        if obj.get("type") not in MAPPABLE_TYPES:
            skipped += 1
            continue
        entity = generate_entity(obj, catalog)
        if entity:
            entities.append((uid, entity))

    if not entities:
        print(f"No mappable objects found in {workspace_root}. Mappable types: {sorted(MAPPABLE_TYPES)}")
        return 0

    if args.dry_run:
        for uid, entity in entities:
            print(f"# {uid} ({entity['kind']})")
            print(yaml.dump(entity, default_flow_style=False, allow_unicode=True))
            print("---")
        print(f"\n# Generated {len(entities)} entities, skipped {skipped} unmapped objects.")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for uid, entity in entities:
        out_path = output_dir / f"{uid}.yaml"
        with out_path.open("w", encoding="utf-8") as handle:
            handle.write(yaml.dump(entity, default_flow_style=False, allow_unicode=True))
        written += 1

    print(f"Generated {written} Backstage entity files in {output_dir}")
    print(f"Skipped {skipped} objects with unmapped types.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
