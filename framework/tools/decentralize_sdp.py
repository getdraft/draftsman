#!/usr/bin/env python3
"""
Migration Utility: Convert Central Catalog SDPs to Product Registrations & Decentralized SDPs

Usage:
    python3 framework/tools/decentralize_sdp.py --sdp <path-to-sdp.yaml> --output-dir <export-dir>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from uid_utils import generate_uid


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a central SoftwareDeploymentPattern into a ProductRegistration and a decentralized .draft/sdp.yaml manifest."
    )
    parser.add_argument(
        "--sdp",
        type=Path,
        required=True,
        help="Path to central SoftwareDeploymentPattern YAML file.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("."),
        help="Workspace root directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./exported_sdps"),
        help="Output directory for generated decentralized .draft/sdp.yaml.",
    )
    parser.add_argument(
        "--repo-url",
        type=str,
        default="",
        help="Product repository URL.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    sdp_path = args.sdp.resolve()
    if not sdp_path.exists():
        print(f"Error: SDP file '{sdp_path}' does not exist.", file=sys.stderr)
        return 1

    try:
        sdp_data = yaml.safe_load(sdp_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"Error parsing '{sdp_path}': {exc}", file=sys.stderr)
        return 1

    if not isinstance(sdp_data, dict) or sdp_data.get("type") != "software_deployment_pattern":
        print(f"Error: '{sdp_path}' is not a valid software_deployment_pattern.", file=sys.stderr)
        return 1

    product_name = sdp_data.get("name", sdp_path.stem)
    slug = sdp_path.stem.replace("software-deployment-", "").replace("sdp-", "")
    repo_url = args.repo_url or f"https://github.com/company/{slug}-service"
    owner = sdp_data.get("owner") or {"team": f"{slug}-team", "contact": f"{slug}-team@example.com"}
    business_context = sdp_data.get("businessContext") or {}

    reg_uid = generate_uid()
    registration = {
        "schemaVersion": "1.0",
        "uid": reg_uid,
        "type": "product_registration",
        "name": product_name,
        "catalogStatus": "complete",
        "owner": owner,
        "businessContext": business_context,
        "repository": {
            "provider": "github",
            "url": repo_url,
            "defaultBranch": "main",
        },
        "sdpManifest": {
            "mode": "git",
            "path": ".draft/sdp.yaml",
        },
    }

    workspace_root = args.workspace.resolve()
    reg_dir = workspace_root / "catalog" / "engineering" / "product-registrations"
    reg_dir.mkdir(parents=True, exist_ok=True)
    reg_file = reg_dir / f"product-reg-{slug}.yaml"

    with reg_file.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(registration, handle, sort_keys=False)

    print(f"Created ProductRegistration: {reg_file}")

    export_dir = args.output_dir.resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    export_sdp_file = export_dir / "sdp.yaml"

    with export_sdp_file.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(sdp_data, handle, sort_keys=False)

    print(f"Created Decentralized Manifest: {export_sdp_file}")
    print("\nNext Steps:")
    print(f"1. Commit {reg_file} to your central drafting-table repo.")
    print(f"2. Copy {export_sdp_file} to .draft/sdp.yaml in the {repo_url} repository.")
    print("3. Run 'python3 framework/tools/validate.py' to verify catalog status.")
    print("4. Set repository.id and repository.ownerId from `gh api repos/OWNER/NAME --jq .id` and `--jq .owner.id`.")
    print("   Until repository.id is set, syncs match by repository name and warn.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
