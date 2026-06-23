#!/usr/bin/env python3
"""Generate C4 L2 Container diagrams from a DRAFT workspace catalog.

Usage:
    python3 framework/tools/generate_c4.py [--workspace PATH] [--output DIR] [--format {structurizr,mermaid,both}]

The exporter reads the DRAFT catalog and emits C4 L2 Container diagrams.
Without system objects, all deployable objects are placed in one implicit system.
With system objects, one diagram is generated per system boundary.
Relationship objects (type: relationship) are rendered as edges.

Output formats:
  structurizr  Structurizr DSL (.dsl) — use with structurizr.com or structurizr-cli
  mermaid      Mermaid C4 syntax (.md) — embed in GitHub markdown, Confluence, etc.
  both         Emit both formats (default)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any
import yaml

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = FRAMEWORK_ROOT.parent
WORKSPACE_ROOT = REPO_ROOT.parent if REPO_ROOT.name == ".draft" else REPO_ROOT
DEFAULT_WORKSPACE_ROOT = WORKSPACE_ROOT if REPO_ROOT.name == ".draft" else REPO_ROOT / "examples"
SKIP_DIRS = {"tools", "schemas", "docs", "adrs", ".github", ".git", ".draft"}

CONTAINER_TYPES = {
    "runtime_service",
    "data_store_service",
    "network_service",
    "product_component",
}

DATA_STORE_TYPES = {"data_store_service"}


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
                    docs = list(yaml.safe_load_all(handle))
                for doc in docs:
                    if isinstance(doc, dict) and doc.get("uid") and doc.get("type"):
                        catalog[str(doc["uid"])] = doc
            except Exception:
                pass
    
    from uid_utils import derive_inline_relationships
    derived = derive_inline_relationships(catalog)
    catalog.update(derived)
    return catalog


def c4_id(uid: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", uid)


def c4_label(obj: dict[str, Any]) -> str:
    return str(obj.get("name") or obj.get("uid") or "Unknown")


def c4_technology(obj: dict[str, Any]) -> str:
    tc = obj.get("primaryTechnologyComponent")
    if not tc:
        delivery = obj.get("deliveryModel", "")
        if delivery:
            return delivery
    return ""


def containers_for_system(
    system: dict[str, Any] | None,
    catalog: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if system is None:
        return [obj for obj in catalog.values() if obj.get("type") in CONTAINER_TYPES]
    container_refs = {
        str(c["ref"])
        for c in (system.get("containers") or [])
        if isinstance(c, dict) and c.get("ref")
    }
    return [catalog[ref] for ref in container_refs if ref in catalog]


def relationships_for_containers(
    container_uids: set[str],
    catalog: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        obj
        for obj in catalog.values()
        if obj.get("type") == "relationship"
        and obj.get("source") in container_uids
        and obj.get("target") in container_uids
    ]


def group_containers_by_sdp(
    containers: list[dict[str, Any]],
    catalog: dict[str, dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]] | None:
    """Return [(group_name, [container_objs])] derived from SDP service groups.

    Returns None when no grouping is found (caller falls back to flat rendering).
    Only returns a value when two or more distinct groups are found.
    """
    container_uids = {str(c.get("uid") or "") for c in containers}
    uid_to_group: dict[str, str] = {}
    group_order: list[str] = []

    for obj in catalog.values():
        if obj.get("type") != "software_deployment_pattern":
            continue
        for group in obj.get("serviceGroups", []):
            if not isinstance(group, dict):
                continue
            group_name = str(group.get("name", "")).strip()
            if not group_name:
                continue
            for deployed in group.get("deployableObjects", []):
                if not isinstance(deployed, dict):
                    continue
                ref = str(deployed.get("ref", "")).strip()
                if ref in container_uids and ref not in uid_to_group:
                    uid_to_group[ref] = group_name
                    if group_name not in group_order:
                        group_order.append(group_name)

    if not uid_to_group:
        return None

    groups: dict[str, list[dict[str, Any]]] = {name: [] for name in group_order}
    ungrouped: list[dict[str, Any]] = []
    for container in containers:
        uid = str(container.get("uid") or "")
        group_name = uid_to_group.get(uid)
        if group_name:
            groups[group_name].append(container)
        else:
            ungrouped.append(container)

    result = [(name, groups[name]) for name in group_order if groups[name]]
    if ungrouped:
        result.append(("Other", ungrouped))

    return result if len(result) > 1 else None


def _structurizr_container_line(obj: dict[str, Any], indent: str) -> str:
    uid_id = c4_id(str(obj.get("uid") or ""))
    label = c4_label(obj)
    tech = c4_technology(obj)
    desc = str(obj.get("description") or "").replace('"', "'").replace("\n", " ").strip()[:120]
    tech_str = f' "{tech}"' if tech else ""
    desc_str = f' "{desc}"' if desc else ""
    return f'{indent}{uid_id} = container "{label}"{tech_str}{desc_str}'


def generate_structurizr(
    system_name: str,
    system_description: str,
    containers: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    external_actors: list[dict[str, Any]],
    groups: list[tuple[str, list[dict[str, Any]]]] | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f'workspace "{system_name}" {{')
    lines.append("  model {")
    lines.append(f'    {c4_id("system")} = softwareSystem "{system_name}" {{')
    if system_description:
        lines.append(f'      description "{system_description}"')

    if groups:
        for group_name, group_containers in groups:
            lines.append(f'      group "{group_name}" {{')
            for obj in group_containers:
                lines.append(_structurizr_container_line(obj, "        "))
            lines.append("      }")
    else:
        for obj in containers:
            lines.append(_structurizr_container_line(obj, "      "))

    lines.append("    }")

    for actor in external_actors:
        actor_name = str(actor.get("name") or "External Actor")
        actor_id = c4_id(actor_name)
        actor_type = str(actor.get("type") or "person")
        actor_desc = str(actor.get("description") or "").replace('"', "'").strip()[:80]
        if actor_type == "person":
            desc_str = f' "{actor_desc}"' if actor_desc else ""
            lines.append(f'    {actor_id} = person "{actor_name}"{desc_str}')
        else:
            desc_str = f' "{actor_desc}"' if actor_desc else ""
            lines.append(f'    {actor_id} = softwareSystem "{actor_name}"{desc_str} {{')
            lines.append("      external true")
            lines.append("    }")

    for rel in relationships:
        src_id = c4_id(str(rel.get("source") or ""))
        tgt_id = c4_id(str(rel.get("target") or ""))
        label = str(rel.get("label") or "uses").replace('"', "'")
        tech = str(rel.get("technology") or "").replace('"', "'")
        tech_str = f' "{tech}"' if tech else ""
        lines.append(f'    {src_id} -> {tgt_id} "{label}"{tech_str}')

    lines.append("  }")
    lines.append("  views {")
    lines.append(f'    container {c4_id("system")} {{')
    lines.append("      include *")
    lines.append("      autolayout lr")
    lines.append("    }")
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines)


def _mermaid_container_line(obj: dict[str, Any], indent: str) -> str:
    uid_id = c4_id(str(obj.get("uid") or ""))
    label = c4_label(obj)
    tech = c4_technology(obj)
    desc = str(obj.get("description") or "").replace('"', "'").replace("\n", " ").strip()[:80]
    tech_str = f', "{tech}"' if tech else ', ""'
    desc_str = f', "{desc}"' if desc else ', ""'
    if obj.get("type") in DATA_STORE_TYPES:
        return f'{indent}ContainerDb({uid_id}, "{label}"{tech_str}{desc_str})'
    return f'{indent}Container({uid_id}, "{label}"{tech_str}{desc_str})'


def generate_mermaid(
    system_name: str,
    containers: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    external_actors: list[dict[str, Any]],
    groups: list[tuple[str, list[dict[str, Any]]]] | None = None,
) -> str:
    lines: list[str] = ["```mermaid", "C4Container"]
    lines.append(f'    title "{system_name}"')
    lines.append("")

    for actor in external_actors:
        actor_name = str(actor.get("name") or "External Actor")
        actor_id = c4_id(actor_name)
        actor_desc = str(actor.get("description") or "").replace('"', "'").strip()[:80]
        actor_type = str(actor.get("type") or "person")
        desc_str = f', "{actor_desc}"' if actor_desc else ', ""'
        if actor_type == "person":
            lines.append(f'    Person_Ext({actor_id}, "{actor_name}"{desc_str})')
        else:
            lines.append(f'    System_Ext({actor_id}, "{actor_name}"{desc_str})')

    if external_actors:
        lines.append("")

    if groups:
        for i, (group_name, group_containers) in enumerate(groups):
            boundary_id = f"b{i}"
            lines.append(f'    Boundary({boundary_id}, "{group_name}") {{')
            for obj in group_containers:
                lines.append(_mermaid_container_line(obj, "        "))
            lines.append("    }")
            lines.append("")
    else:
        for obj in containers:
            lines.append(_mermaid_container_line(obj, "    "))
        lines.append("")

    if relationships:
        for rel in relationships:
            src_id = c4_id(str(rel.get("source") or ""))
            tgt_id = c4_id(str(rel.get("target") or ""))
            label = str(rel.get("label") or "uses").replace('"', "'")
            tech = str(rel.get("technology") or "").replace('"', "'")
            tech_str = f', "{tech}"' if tech else ""
            lines.append(f'    Rel({src_id}, {tgt_id}, "{label}"{tech_str})')

    lines.append("```")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export DRAFT catalog as C4 L2 Container diagrams."
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
        help="Output directory for generated diagram files. Defaults to <workspace>/c4/.",
    )
    parser.add_argument(
        "--format",
        choices=["structurizr", "mermaid", "both"],
        default="both",
        help="Output format: structurizr DSL, Mermaid C4, or both (default: both).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated diagrams to stdout instead of writing files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    workspace_root = args.workspace.resolve()
    output_dir = args.output.resolve() if args.output else workspace_root / "c4"

    catalog = load_catalog(workspace_root)
    if not catalog:
        print("No catalog objects found. Check the workspace path.", file=sys.stderr)
        return 1

    systems = [obj for obj in catalog.values() if obj.get("type") == "system"]
    all_containers = [obj for obj in catalog.values() if obj.get("type") in CONTAINER_TYPES]
    all_relationships = [obj for obj in catalog.values() if obj.get("type") == "relationship"]

    if not all_containers:
        print("No deployable container objects found in catalog.", file=sys.stderr)
        return 1

    if not all_relationships:
        print(
            "Warning: no relationship objects found. Diagrams will show containers without edges. "
            "Add relationship YAML files to catalog/relationships/ to show inter-service communication.",
            file=sys.stderr,
        )

    diagrams: list[tuple[str, str, str]] = []

    if systems:
        for system in systems:
            containers = containers_for_system(system, catalog)
            if not containers:
                continue
            container_uids = {str(c.get("uid") or "") for c in containers}
            rels = relationships_for_containers(container_uids, catalog)
            actors = [
                a for a in (system.get("externalActors") or [])
                if isinstance(a, dict)
            ]
            system_name = str(system.get("name") or "System")
            system_desc = str(system.get("description") or "")
            slug = re.sub(r"[^a-z0-9-]+", "-", system_name.lower()).strip("-")
            groups = group_containers_by_sdp(containers, catalog)

            if args.format in ("structurizr", "both"):
                dsl = generate_structurizr(system_name, system_desc, containers, rels, actors, groups)
                diagrams.append((f"{slug}.dsl", dsl, "Structurizr DSL"))

            if args.format in ("mermaid", "both"):
                md = generate_mermaid(system_name, containers, rels, actors, groups)
                diagrams.append((f"{slug}.md", md, "Mermaid C4"))
    else:
        system_name = "System"
        container_uids = {str(c.get("uid") or "") for c in all_containers}
        rels = relationships_for_containers(container_uids, catalog)
        groups = group_containers_by_sdp(all_containers, catalog)

        if args.format in ("structurizr", "both"):
            dsl = generate_structurizr(system_name, "", all_containers, rels, [], groups)
            diagrams.append(("system.dsl", dsl, "Structurizr DSL"))

        if args.format in ("mermaid", "both"):
            md = generate_mermaid(system_name, all_containers, rels, [], groups)
            diagrams.append(("system.md", md, "Mermaid C4"))

    if args.dry_run:
        for filename, content, fmt in diagrams:
            print(f"# {filename} ({fmt})")
            print(content)
            print()
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content, fmt in diagrams:
        out_path = output_dir / filename
        out_path.write_text(content, encoding="utf-8")
        print(f"  Wrote {out_path} ({fmt})")

    print(f"\nGenerated {len(diagrams)} diagram file(s) in {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
