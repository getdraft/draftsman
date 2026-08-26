#!/usr/bin/env python3
"""
Draftsman Stdio MCP Server: Model Context Protocol Server for DRAFT Architecture Catalog Queries.

Self-contained inside agent/mcp/server.py.
Exposes standard JSON-RPC 2.0 stdio tools (`query_architecture`, `get_c4_diagram`, `check_compliance`, `validate_yaml_object`)
to LLM agents deployed in enterprise agent factories or developer IDEs.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from indexes import load_catalog_index


TOOLS_MANIFEST = [
    {
        "name": "query_architecture",
        "description": "Search the architecture catalog for products, ports, database engines, dependencies, hosts, or business pillars.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword, product name, port number, database engine, or pillar identifier."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_c4_diagram",
        "description": "Generate a Mermaid C4 topology diagram definition for a specified product or deployment pattern.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "Name or UID of the product or software_deployment_pattern."}
            },
            "required": ["product_name"],
        },
    },
    {
        "name": "check_compliance",
        "description": "Audit an object or product against active framework RequirementGroups and capabilities.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "Name or UID of the product object to audit."}
            },
            "required": ["product_name"],
        },
    },
    {
        "name": "validate_yaml_object",
        "description": "Validate a DRAFT YAML artifact snippet against schema rules.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "yaml_content": {"type": "string", "description": "DRAFT YAML content string to validate."}
            },
            "required": ["yaml_content"],
        },
    },
]



def _text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


def _objects(index_data: dict[str, Any]) -> list[dict[str, Any]]:
    objects = index_data.get("objects", [])
    if isinstance(objects, dict):
        objects = list(objects.values())
    return [o for o in objects if isinstance(o, dict)]


def _find_object(index_data: dict[str, Any], needle: str) -> dict[str, Any] | None:
    """Resolve a name or uid to a catalog object, or None. Exact match before substring."""
    wanted = needle.strip().lower()
    if not wanted:
        return None
    candidates = _objects(index_data)
    for obj in candidates:
        if wanted in (str(obj.get("name", "")).lower(), str(obj.get("uid", "")).lower()):
            return obj
    for obj in candidates:
        if wanted in str(obj.get("name", "")).lower():
            return obj
    return None


def handle_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    index_data = load_catalog_index()

    if name == "query_architecture":
        query = str(arguments.get("query", "")).lower()
        results = []
        objects = index_data.get("objects", [])
        if isinstance(objects, dict):
            objects = list(objects.values())

        for obj in objects:
            if not isinstance(obj, dict):
                continue
            obj_name = str(obj.get("name", "")).lower()
            uid = str(obj.get("uid", "")).lower()
            obj_type = str(obj.get("type", "")).lower()
            if query in obj_name or query in uid or query in obj_type:
                results.append({
                    "uid": obj.get("uid"),
                    "name": obj.get("name"),
                    "type": obj.get("type"),
                    "catalogStatus": obj.get("catalogStatus"),
                })
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"match_count": len(results), "results": results[:20]}, indent=2),
                }
            ]
        }

    if name == "get_c4_diagram":
        product_name = str(arguments.get("product_name", ""))
        target = _find_object(index_data, product_name)
        if target is None:
            return _text({
                "product": product_name,
                "error": "No object with that name or uid is in the catalog index.",
            })
        diagram = f"graph TD\n  subgraph {target.get('name') or product_name}\n    API[Product API]\n    DB[(Database)]\n    API --> DB\n  end"
        return {
            "content": [
                {
                    "type": "text",
                    # Still a placeholder shape rather than the object's real relationships, and
                    # labelled as one so it is not mistaken for the catalog's own topology.
                    "text": f"```mermaid\n{diagram}\n```\n\n_Placeholder topology: generated from the object's identity, not its recorded relationships._",
                }
            ]
        }

    if name == "check_compliance":
        product_name = str(arguments.get("product_name", ""))
        target = _find_object(index_data, product_name)
        if target is None:
            return _text({
                "product": product_name,
                "complianceStatus": "unknown",
                "reason": "No object with that name or uid is in the catalog index.",
            })

        rows = (index_data.get("requirementImplementations") or {}).get("rows") or []
        mine = [r for r in rows if str(r.get("object")) == str(target.get("uid"))]
        if not mine:
            # Distinct from "compliant". Nothing was assessed, and saying otherwise is the kind of
            # answer that gets believed precisely because someone asked the question.
            return _text({
                "product": target.get("name") or product_name,
                "uid": target.get("uid"),
                "complianceStatus": "unknown",
                "reason": "The object is in the catalog but has no requirement implementations recorded.",
            })

        satisfied = sorted({str(r.get("requirementId")) for r in mine if r.get("status") == "satisfied"})
        unsatisfied = sorted({
            str(r.get("requirementId")) for r in mine if r.get("status") not in (None, "", "satisfied")
        })
        return _text({
            "product": target.get("name") or product_name,
            "uid": target.get("uid"),
            "complianceStatus": "compliant" if not unsatisfied else "non_compliant",
            "satisfiedRequirements": satisfied,
            "unsatisfiedRequirements": unsatisfied,
            "assessedCount": len(mine),
        })

    if name == "validate_yaml_object":
        yaml_str = str(arguments.get("yaml_content", ""))
        has_schema = "schemaVersion:" in yaml_str
        has_uid = "uid:" in yaml_str
        has_type = "type:" in yaml_str
        valid = has_schema and has_uid and has_type
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"valid": valid, "errors": [] if valid else ["Missing required metadata fields (schemaVersion, uid, type)"]}, indent=2),
                }
            ]
        }

    raise ValueError(f"Unknown tool name: {name}")


def main() -> None:
    sys.stderr.write("Draftsman Stdio MCP Server starting on stdio...\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "draftsman-mcp-server",
                        "version": "1.0.3"
                    }
                }
            }
        elif method == "notifications/initialized":
            continue
        elif method == "ping":
            response = {"jsonrpc": "2.0", "id": req_id, "result": {}}
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": TOOLS_MANIFEST
                }
            }
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                res = handle_tool_call(name, arguments)
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": res
                }
            except Exception as exc:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32603,
                        "message": str(exc)
                    }
                }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
