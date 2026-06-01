#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Maps old flat folder names under catalog/ to their new nested role paths under catalog/
FOLDER_MAPPING = {
    # Engineering
    "product-components": "engineering/product-components",
    "data-components": "engineering/data-components",
    "software-deployment-patterns": "engineering/software-deployment-patterns",
    # Shared Services
    "hosts": "shared-services/hosts",
    "runtime-services": "shared-services/runtime-services",
    "data-store-services": "shared-services/data-store-services",
    "network-services": "shared-services/network-services",
    "technology-components": "shared-services/technology-components",
    # Governance
    "decision-records": "governance/decision-records",
    "sessions": "governance/sessions",
    "relationships": "governance/relationships",
    "systems": "governance/systems",
    "reference-architectures": "governance/reference-architectures",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate a company DRAFT workspace from a flat catalog folder structure to a role-based nested catalog structure."
    )
    parser.add_argument(
        "root",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Path to the repository workspace root (defaults to current directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned moves without performing any file changes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    catalog_root = root / "catalog"

    if not catalog_root.exists() or not catalog_root.is_dir():
        print(f"Error: Could not find a 'catalog' directory at: {catalog_root}")
        print("Please point this script to the root of a valid DRAFT workspace.")
        return 1

    print(f"Scanning DRAFT workspace catalog at: {catalog_root}")
    if args.dry_run:
        print("=== DRY RUN MODE: No changes will be written ===\n")

    moves_planned = 0
    moves_performed = 0

    for old_folder, nested_path in FOLDER_MAPPING.items():
        src = catalog_root / old_folder
        dest = catalog_root / nested_path

        if src.exists() and src.is_dir():
            moves_planned += 1
            src_rel = src.relative_to(root)
            dest_rel = dest.relative_to(root)

            if args.dry_run:
                print(f"[Plan] Move: {src_rel} -> {dest_rel}")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    print(f"Merging: {src_rel} -> {dest_rel}")
                    # Move individual files/dirs inside to prevent nested folders (e.g. dest/old_folder)
                    for item in list(src.iterdir()):
                        target_item = dest / item.name
                        if target_item.exists():
                            print(f"  Warning: Skipping {item.name} because it already exists in destination.")
                        else:
                            shutil.move(str(item), str(target_item))
                    # Remove the empty source directory
                    try:
                        if not any(src.iterdir()):
                            src.rmdir()
                            print(f"  Removed empty directory: {src_rel}")
                    except Exception as e:
                        print(f"  Warning: Could not remove directory {src_rel}: {e}")
                else:
                    print(f"Moving: {src_rel} -> {dest_rel}")
                    shutil.move(str(src), str(dest))
                moves_performed += 1

    print("\n=== Migration Summary ===")
    if args.dry_run:
        print(f"Planned {moves_planned} directory moves.")
    else:
        print(f"Successfully migrated {moves_performed} of {moves_planned} directories.")
        if moves_performed > 0:
            print("\nMigration complete! Running 'python3 framework/tools/validate.py' is recommended to verify the workspace.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
