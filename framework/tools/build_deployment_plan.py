#!/usr/bin/env python3
"""DRAFT Deployment Plan Generator.

Resolves a Software Deployment Pattern (SDP) and its referenced shared services
down to executable IaC modules (`deployablePackage`) and highlights any
reference-only or stubbed services.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml


def find_sdp_files(workspace_root: Path) -> list[Path]:
    """Finds all sdp.yaml or sdp-*.yaml files in workspace."""
    sdps = []
    for root, _, files in os.walk(workspace_root):
        for file in files:
            if file == "sdp.yaml" or (file.startswith("sdp-") and file.endswith(".yaml")):
                sdps.append(Path(root) / file)
    return sdps


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_deployment_plan(sdp_path: Path, workspace_root: Path) -> dict[str, Any]:
    sdp_data = load_yaml(sdp_path)
    if sdp_data.get("type") != "software_deployment_pattern":
        raise ValueError(f"{sdp_path} is not a valid software_deployment_pattern")

    plan: dict[str, Any] = {
        "sdpName": sdp_data.get("name"),
        "version": sdp_data.get("version"),
        "catalogStatus": sdp_data.get("catalogStatus", "complete"),
        "deployableModules": [],
        "referenceServices": [],
        "stubbedServices": [],
    }

    # Index all catalog objects in workspace for reference resolution
    catalog_index: dict[str, dict[str, Any]] = {}
    for root, _, files in os.walk(workspace_root):
        for file in files:
            if file.endswith(".yaml") or file.endswith(".yml"):
                fpath = Path(root) / file
                try:
                    obj = load_yaml(fpath)
                    if isinstance(obj, dict) and "uid" in obj:
                        catalog_index[obj["uid"]] = obj
                except Exception:
                    pass

    # Process deployable objects
    deployable_objs = sdp_data.get("deployableObjects", [])
    for entry in deployable_objs:
        if isinstance(entry, dict):
            for key, val in entry.items():
                obj = catalog_index.get(str(val)) or {"uid": str(val), "name": str(val), "type": key}
                prov_model = obj.get("provisioningModel", "reference-only")
                cat_status = obj.get("catalogStatus", "complete")

                if prov_model == "deployable" and "deployablePackage" in obj:
                    plan["deployableModules"].append({
                        "id": obj.get("uid"),
                        "name": obj.get("name"),
                        "type": obj.get("type"),
                        "package": obj.get("deployablePackage"),
                    })
                elif cat_status == "documentation" or prov_model == "reference-only":
                    plan["stubbedServices"].append({
                        "id": obj.get("uid"),
                        "name": obj.get("name"),
                        "type": obj.get("type"),
                        "provisioningModel": prov_model,
                        "catalogStatus": cat_status,
                        "note": "Reference or documentation stub -- no executable IaC module provided.",
                    })

    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate executable deployment plan from DRAFT SDP")
    parser.add_argument("--sdp", help="Path to sdp.yaml manifest")
    parser.add_argument("--workspace", default=".", help="Path to workspace root")
    parser.add_argument("--json", action="store_true", help="Output raw JSON plan")
    args = parser.parse_args()

    workspace_root = Path(args.workspace).resolve()

    if args.sdp:
        sdp_path = Path(args.sdp).resolve()
    else:
        sdps = find_sdp_files(workspace_root)
        if not sdps:
            print(f"Error: No SDP manifests found under {workspace_root}", file=sys.stderr)
            sys.exit(1)
        sdp_path = sdps[0]

    plan = build_deployment_plan(sdp_path, workspace_root)

    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(f"=== DRAFT Executable Deployment Plan: {plan['sdpName']} ===")
        print(f"Catalog Status: {plan['catalogStatus']}\n")

        print("--- Executable IaC Modules ---")
        if plan["deployableModules"]:
            for mod in plan["deployableModules"]:
                pkg = mod["package"]
                print(f"  • [{mod['type']}] {mod['name']}")
                print(f"    Source: {pkg.get('source')} ({pkg.get('registry', 'github')})")
                print(f"    Version: {pkg.get('version', 'latest')}")
                if "modulePath" in pkg:
                    print(f"    Module Path: {pkg['modulePath']}")
        else:
            print("  (None)")

        print("\n--- Reference & Stubbed Services ---")
        if plan["stubbedServices"]:
            for stub in plan["stubbedServices"]:
                print(f"  • [{stub['type']}] {stub['name']} (model: {stub['provisioningModel']}, status: {stub['catalogStatus']})")
                print(f"    Note: {stub['note']}")
        else:
            print("  (None)")


if __name__ == "__main__":
    main()
