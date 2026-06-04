#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path
from typing import Any
import yaml

# Representer to output clean multi-line block scalars for description and rationale
def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)

REPO_ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON_URL = "https://raw.githubusercontent.com/ibuildingsnl/owasp-asvs/master/src/asvs.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "providers" / "owasp-asvs" / "configurations" / "requirement-groups"

# crockford base32 stable UIDs
LEVEL_UIDS = {
    1: "01KQQ4Q027-ASV1",
    2: "01KQQ4Q027-ASV2",
    3: "01KQQ4Q027-ASV3",
}

# Map ASVS chapters to standard DRAFT capabilities
CHAPTER_CAPABILITY_MAP = {
    "1": "01KT0XNZEY-35Y2",   # Architecture -> Configuration Management
    "2": "01KQQ4Q026-MHJM",   # Authentication -> Authentication
    "3": "01KQQ4Q026-MHJM",   # Session Management -> Authentication
    "4": "01KQQ4Q026-4JR6",   # Access Control -> Access Control Model
    "5": "01KT0V5MCV-Z079",   # Input Validation -> WAF
    "6": "01KT0V5MCV-Z079",   # Output Encoding -> WAF
    "7": "01KQQ4Q026-H3B5",   # Cryptography at Rest -> Encryption At Rest
    "8": "01KQQ4Q026-D04B",   # Logging -> Log Management
    "9": "01KQQ4Q026-H3B5",   # Data Protection -> Encryption At Rest
    "10": "01KSWVZSZ5-1RTH",  # Comm Security -> Network Segmentation
    "11": "01KT0XNZEY-35Y2",  # HTTP Config -> Configuration Management
    "12": "01KT0XNZEY-35Y2",  # Security Config -> Configuration Management
    "13": "01KQQ4Q026-JW52",  # Malicious controls -> Security Monitoring
    "14": "01KQQ4Q026-JW52",  # Internal security -> Security Monitoring
    "15": "01KQQ4Q026-RTWC",  # Business logic -> Quality Gates
    "16": "01KT0V5MCV-924J",  # Files -> File Storage
    "17": "01KQQ4Q026-1HZP",  # Mobile -> Compute Platform
    "18": "01KT0V5MCV-3A6F",  # Web services -> API Gateway
    "19": "01KT0XNZEY-35Y2",  # Configuration -> Configuration Management
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and import OWASP ASVS into DRAFT RequirementGroups.")
    parser.add_argument(
        "--source",
        default=DEFAULT_JSON_URL,
        help="Local file path or URL to the ASVS requirements JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "Directory for generated RequirementGroup YAML files. Defaults to the reusable "
            "OWASP ASVS provider pack under providers/owasp-asvs/configurations/requirement-groups."
        ),
    )
    return parser.parse_args()

def load_json(source: str) -> dict[str, Any]:
    if source.startswith("http://") or source.startswith("https://"):
        print(f"Downloading ASVS JSON from {source}...")
        with urllib.request.urlopen(source) as response:
            content = response.read().decode("utf-8")
    else:
        print(f"Reading ASVS JSON from local file: {source}...")
        content = Path(source).read_text(encoding="utf-8")
    
    # Remove trailing commas that break python's strict json parser
    cleaned = re.sub(r',\s*([\]}])', r'\1', content)
    return json.loads(cleaned)

def build_requirement(req: dict[str, Any]) -> dict[str, Any] | None:
    if "chapterNr" not in req or "nr" not in req or "title" not in req:
        return None
    chapter = str(req["chapterNr"])
    nr = str(req["nr"])
    desc = req["title"].get("en", "").strip()
    if not desc:
        return None
    cap = CHAPTER_CAPABILITY_MAP.get(chapter, "01KT0XNZEY-35Y2")  # default to Configuration Management if missing
    
    return {
        "id": f"V{chapter}.{nr}",
        "externalControlId": f"V{chapter}.{nr}",
        "name": f"ASVS V{chapter}.{nr}",
        "description": desc,
        "requirementMode": "mandatory",
        "naAllowed": True,
        "relatedCapability": cap,
        "canBeSatisfiedBy": [
            {
                "mechanism": "relationship",
                "criteria": {
                    "capability": cap
                }
            },
            {
                "mechanism": "decisionRecord",
                "key": f"asvs.v{chapter}.{nr}"
            }
        ],
        "minimumSatisfactions": 1,
        "validAnswerTypes": [
            "relationship",
            "decisionRecord"
        ]
    }

def main() -> None:
    args = parse_args()
    try:
        data = load_json(args.source)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    raw_reqs = data.get("requirements", [])
    print(f"Parsed {len(raw_reqs)} requirements from ASVS JSON.")

    # Group requirements by level
    level_reqs: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: []}
    for r in raw_reqs:
        req_levels = r.get("levels", [])
        draft_req = build_requirement(r)
        if not draft_req:
            continue
        
        # In ASVS:
        # - L1 requirements have 1, 2, 3 in levels
        # - L2 requirements have 2, 3 (but not 1) in levels
        # - L3 requirements have only 3 in levels
        # We group them strictly by their MINIMUM level of appearance, 
        # because the higher groups will inherit the lower ones.
        if 1 in req_levels:
            level_reqs[1].append(draft_req)
        elif 2 in req_levels:
            level_reqs[2].append(draft_req)
        elif 3 in req_levels:
            level_reqs[3].append(draft_req)

    print(f"Grouped requirements: Level 1: {len(level_reqs[1])}, Level 2: {len(level_reqs[2])}, Level 3: {len(level_reqs[3])}")

    # Ensure output dir exists
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    provider = {
        "id": "provider.owasp-asvs",
        "type": "third-party",
        "name": "OWASP ASVS Provider Pack"
    }

    # Generate Level 1 Group
    l1_path = output_dir / "requirement-group-owasp-asvs-l1.yaml"
    l1_group = {
        "schemaVersion": "1.0",
        "uid": LEVEL_UIDS[1],
        "type": "requirement_group",
        "name": "OWASP ASVS Level 1",
        "description": "Baseline verification controls that apply to all web applications, services, and APIs.",
        "version": "4.0.3",
        "catalogStatus": "complete",
        "activation": "workspace",
        "appliesTo": [
            "runtime_service",
            "product_component",
            "software_deployment_pattern"
        ],
        "provider": provider,
        "authority": {
            "name": "OWASP Foundation",
            "shortName": "ASVS L1",
            "source": "OWASP Application Security Verification Standard v4.0.3"
        },
        "requirements": level_reqs[1]
    }
    l1_path.write_text(yaml.safe_dump(l1_group, sort_keys=False, width=120), encoding="utf-8")
    print(f"Wrote Level 1 RequirementGroup to {l1_path}")

    # Generate Level 2 Group
    l2_path = output_dir / "requirement-group-owasp-asvs-l2.yaml"
    l2_group = {
        "schemaVersion": "1.0",
        "uid": LEVEL_UIDS[2],
        "type": "requirement_group",
        "name": "OWASP ASVS Level 2",
        "description": "Standard verification controls for sensitive business applications, inheriting Level 1.",
        "version": "4.0.3",
        "catalogStatus": "complete",
        "activation": "workspace",
        "inherits": [LEVEL_UIDS[1]],
        "appliesTo": [
            "runtime_service",
            "product_component",
            "software_deployment_pattern"
        ],
        "provider": provider,
        "authority": {
            "name": "OWASP Foundation",
            "shortName": "ASVS L2",
            "source": "OWASP Application Security Verification Standard v4.0.3"
        },
        "requirements": level_reqs[2]
    }
    l2_path.write_text(yaml.safe_dump(l2_group, sort_keys=False, width=120), encoding="utf-8")
    print(f"Wrote Level 2 RequirementGroup to {l2_path}")

    # Generate Level 3 Group
    l3_path = output_dir / "requirement-group-owasp-asvs-l3.yaml"
    l3_group = {
        "schemaVersion": "1.0",
        "uid": LEVEL_UIDS[3],
        "type": "requirement_group",
        "name": "OWASP ASVS Level 3",
        "description": "Advanced verification controls for critical infrastructure and high-value transactions, inheriting Level 2.",
        "version": "4.0.3",
        "catalogStatus": "complete",
        "activation": "workspace",
        "inherits": [LEVEL_UIDS[2]],
        "appliesTo": [
            "runtime_service",
            "product_component",
            "software_deployment_pattern"
        ],
        "provider": provider,
        "authority": {
            "name": "OWASP Foundation",
            "shortName": "ASVS L3",
            "source": "OWASP Application Security Verification Standard v4.0.3"
        },
        "requirements": level_reqs[3]
    }
    l3_path.write_text(yaml.safe_dump(l3_group, sort_keys=False, width=120), encoding="utf-8")
    print(f"Wrote Level 3 RequirementGroup to {l3_path}")

if __name__ == "__main__":
    main()
