#!/usr/bin/env python3
"""Migrate deprecated externalInteractions to relationship objects.

For each catalog object that has a top-level externalInteractions list, this
script generates a stub relationship YAML file for every entry that has a `ref`
pointing to an existing catalog object. Entries without a ref receive an
`externalTarget` relationship. The original externalInteractions field is left
in place (not removed) so you can review the generated files before cleaning up
by hand or with your editor.

Usage:
    python3 framework/tools/migrate_interactions.py --workspace <path>
    python3 framework/tools/migrate_interactions.py --workspace <path> --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from uid_utils import generate_uid

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = FRAMEWORK_ROOT.parent
DEFAULT_WORKSPACE_ROOT = REPO_ROOT / "examples"
SKIP_DIRS = {"tools", "schemas", "docs", "adrs", ".github", ".git"}

TYPES_WITH_INTERACTIONS = {
    "runtime_service",
    "data_store_service",
    "edge_gateway_service",
    "host",
}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate externalInteractions to relationship objects.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE_ROOT, help="Workspace root directory")
    parser.add_argument("--dry-run", action="store_true", help="Print generated files without writing them")
    return parser.parse_args(argv)


def discover_yaml_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.yaml"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def slug(name: str) -> str:
    return name.lower().replace(" ", "-").replace("/", "-").replace("_", "-")


def infer_label(interaction: dict[str, Any]) -> str:
    capabilities = interaction.get("capabilities", [])
    if isinstance(capabilities, list) and capabilities:
        cap = str(capabilities[0]).lower()
        if "auth" in cap or "identity" in cap:
            return "authenticates via"
        if "log" in cap:
            return "sends logs to"
        if "monitor" in cap or "metric" in cap:
            return "sends metrics to"
        if "secret" in cap:
            return "reads secrets from"
        if "backup" in cap or "storage" in cap:
            return "writes to"
    notes = str(interaction.get("notes", "")).lower()
    if "call" in notes or "request" in notes:
        return "calls"
    if "read" in notes:
        return "reads from"
    if "write" in notes:
        return "writes to"
    if "send" in notes or "publish" in notes or "emit" in notes:
        return "sends events to"
    return "calls"


def build_relationship_yaml(
    source_uid: str,
    source_name: str,
    interaction: dict[str, Any],
    target_obj: dict[str, Any] | None,
    external_name: str | None,
) -> tuple[str, dict[str, Any]]:
    label = infer_label(interaction)
    target_name = (target_obj.get("name") if target_obj else None) or external_name or "Unknown"

    source_slug = slug(source_name)
    target_slug = slug(target_name)
    verb_slug = slug(label.replace(" ", "-"))
    filename = f"relationship-{source_slug}-{verb_slug}-{target_slug}.yaml"

    obj: dict[str, Any] = {
        "schemaVersion": "1.0",
        "type": "relationship",
        "uid": generate_uid(),
        "name": f"{source_name} → {target_name}",
        "catalogStatus": "stub",
        "source": source_uid,
        "label": label,
    }
    if target_obj:
        obj["target"] = target_obj["uid"]
    elif external_name:
        obj["externalTarget"] = external_name

    notes = interaction.get("notes")
    if notes:
        obj["notes"] = str(notes)

    return filename, obj


def yaml_dump(obj: dict[str, Any]) -> str:
    return yaml.dump(obj, default_flow_style=False, sort_keys=False, allow_unicode=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    workspace_root = args.workspace.resolve()

    files = discover_yaml_files(workspace_root)
    objects: dict[str, dict[str, Any]] = {}

    for path in files:
        try:
            obj = load_yaml(path)
            if isinstance(obj, dict) and obj.get("uid"):
                objects[obj["uid"]] = obj
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIP {path}: {exc}", file=sys.stderr)

    relationships_dir = workspace_root / "catalog" / "relationships"
    generated = 0

    for uid, obj in objects.items():
        if obj.get("type") not in TYPES_WITH_INTERACTIONS:
            continue
        interactions = obj.get("externalInteractions", [])
        if not isinstance(interactions, list) or not interactions:
            continue

        source_name = obj.get("name") or uid
        print(f"  {source_name} ({uid}) — {len(interactions)} externalInteraction(s)")

        for interaction in interactions:
            if not isinstance(interaction, dict):
                continue
            ref = interaction.get("ref")
            target_obj = objects.get(str(ref)) if ref else None
            external_name = interaction.get("name") if not ref else None

            if ref and not target_obj:
                print(f"    WARNING: ref '{ref}' not found in catalog — skipping")
                continue

            filename, rel_obj = build_relationship_yaml(uid, source_name, interaction, target_obj, external_name)
            output_path = relationships_dir / filename

            if output_path.exists():
                print(f"    SKIP {filename} (already exists)")
                continue

            if args.dry_run:
                print(f"    DRY RUN: would write {output_path.relative_to(workspace_root)}")
                print("    ---")
                for line in yaml_dump(rel_obj).splitlines():
                    print(f"    {line}")
            else:
                relationships_dir.mkdir(parents=True, exist_ok=True)
                output_path.write_text(yaml_dump(rel_obj), encoding="utf-8")
                print(f"    WROTE {output_path.relative_to(workspace_root)}")
            generated += 1

    action = "would generate" if args.dry_run else "generated"
    print(f"\nDone — {action} {generated} relationship file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
