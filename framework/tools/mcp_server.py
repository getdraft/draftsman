#!/usr/bin/env python3
"""
Draftsman Stdio MCP Server: Model Context Protocol Server for DRAFT Architecture Catalog Queries.

Exposes standard JSON-RPC 2.0 stdio tools (`query_architecture`, `get_c4_diagram`, `check_compliance`, `validate_yaml_object`)
to any agent or developer IDE that can launch an MCP server.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

TOOLS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_ROOT.parent.parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from indexes import build_catalog_indexes, sorted_objects


def token_allowed_for(url: str) -> bool:
    """Send a read token only over https to GitHub's own hosts, judged by parsed hostname."""
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return False
    return any(host == base or host.endswith("." + base) for base in ("github.com", "githubusercontent.com"))


class _KeepTokenOnGitHubOnly(urllib.request.HTTPRedirectHandler):
    """Drop the Authorization header when a redirect leads anywhere the token may not go."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None and not token_allowed_for(newurl):
            for name in list(new_req.headers):
                if name.lower() == "authorization":
                    del new_req.headers[name]
            for name in list(new_req.unredirected_hdrs):
                if name.lower() == "authorization":
                    del new_req.unredirected_hdrs[name]
        return new_req


def load_catalog_index() -> dict[str, Any]:
    url = os.getenv("DRAFT_CATALOG_INDEX_URL")
    path_str = os.getenv("DRAFT_CATALOG_INDEX_PATH")
    read_token = os.getenv("GITHUB_READ_TOKEN") or os.getenv("GITHUB_TOKEN")

    if url:
        try:
            req = urllib.request.Request(url)
            if read_token and token_allowed_for(url):
                req.add_header("Authorization", f"Bearer {read_token}")
            with urllib.request.build_opener(_KeepTokenOnGitHubOnly).open(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    if isinstance(data, dict):
                        return data
        except Exception as exc:
            sys.stderr.write(f"Warning: Failed to fetch index from DRAFT_CATALOG_INDEX_URL ({url}): {exc}\n")

    if path_str:
        file_path = Path(path_str)
        if file_path.exists():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception as exc:
                sys.stderr.write(f"Warning: Failed to read index from DRAFT_CATALOG_INDEX_PATH ({file_path}): {exc}\n")

    for fallback in [
        REPO_ROOT / "catalog_indexes.json",
        REPO_ROOT / "docs" / "catalog_indexes.json",
        Path("catalog_indexes.json"),
        Path("docs/catalog_indexes.json"),
    ]:
        if fallback.exists():
            try:
                data = json.loads(fallback.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

    sys.stderr.write(
        "Warning: no catalog index found. Set DRAFT_CATALOG_INDEX_PATH or DRAFT_CATALOG_INDEX_URL; "
        "answering from an empty index.\n"
    )
    return {"objects": []}


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


def _q(value: Any) -> str:
    """Make a value safe inside a double-quoted Mermaid label."""
    return str(value).replace('"', "'")


def _edge_label(label: Any, tech: str) -> str:
    return (_q(label) + tech).replace("|", "/").replace('"', "'")


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
    matches = [obj for obj in candidates if wanted in str(obj.get("name", "")).lower()]
    # A fragment that matches several objects names none of them: say unknown rather than guess.
    return matches[0] if len(matches) == 1 else None


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
                "error": "No single object with that name or uid is in the catalog index (it is absent or the name is ambiguous).",
            })

        target_uid = str(target.get("uid", ""))
        target_name = str(target.get("name") or product_name)
        all_objs = _objects(index_data)
        objs_by_uid = {str(o.get("uid")): o for o in all_objs if o.get("uid")}

        rel_objs = [o for o in all_objs if o.get("type") == "relationship"]
        outbound = []
        inbound = []

        for r in rel_objs:
            src = str(r.get("source", ""))
            tgt = str(r.get("target", ""))
            lbl = r.get("label") or "connects to"
            tech = r.get("technology")
            edge_info = {"rel": r, "label": lbl, "technology": tech}

            if src == target_uid:
                other_uid = tgt
                other_obj = objs_by_uid.get(other_uid)
                edge_info["other"] = other_obj or {"uid": tgt, "name": tgt, "type": "unknown"}
                outbound.append(edge_info)
            elif tgt == target_uid:
                other_uid = src
                other_obj = objs_by_uid.get(other_uid)
                edge_info["other"] = other_obj or {"uid": src, "name": src, "type": "unknown"}
                inbound.append(edge_info)

        total_edges = len(outbound) + len(inbound)
        if total_edges == 0:
            return _text({
                "product": target_name,
                "uid": target_uid,
                "status": "no_relationships_recorded",
                "message": f"No relationships are recorded in the catalog for {target_name} ({target_uid}).",
            })

        max_display_edges = 12
        displayed_out = outbound[:max_display_edges]
        displayed_in = inbound[:max_display_edges]
        omitted = total_edges - (len(displayed_out) + len(displayed_in))

        # 1. Build ASCII Text Representation (readable where Mermaid is shown as plain text)
        lines = [f"{target_name} ({target.get('type', 'object')})", "│"]
        if displayed_out:
            lines.append(f"├─ outbound ─────────────────────────────── {len(outbound)} edges")
            for edge in displayed_out:
                other_name = edge["other"].get("name", edge["other"].get("uid"))
                lbl = edge["label"]
                tech_str = f" via {edge['technology']}" if edge["technology"] else ""
                lines.append(f"│   ▪ {other_name:<30} {lbl}{tech_str}")
            lines.append("│")
        if displayed_in:
            lines.append(f"└─ inbound ──────────────────────────────── {len(inbound)} edges")
            for edge in displayed_in:
                other_name = edge["other"].get("name", edge["other"].get("uid"))
                lbl = edge["label"]
                tech_str = f" via {edge['technology']}" if edge["technology"] else ""
                lines.append(f"    ▪ {other_name:<30} {lbl}{tech_str}")

        if omitted > 0:
            lines.append(f"\n_Omitted {omitted} additional edges due to diagram degree cap (12 max shown)._")

        text_repr = "\n".join(lines)

        # 2. Build Mermaid Diagram Block
        mermaid_lines = ["graph LR", f'  node_target["{_q(target_name)}"]']
        node_idx = 0
        for edge in displayed_out:
            node_idx += 1
            other_name = edge["other"].get("name", edge["other"].get("uid"))
            lbl = edge["label"]
            tech_str = f" ({edge['technology']})" if edge["technology"] else ""
            nid = f"n_out_{node_idx}"
            mermaid_lines.append(f'  {nid}["{_q(other_name)}"]')
            mermaid_lines.append(f'  node_target -->|{_edge_label(lbl, tech_str)}| {nid}')

        for edge in displayed_in:
            node_idx += 1
            other_name = edge["other"].get("name", edge["other"].get("uid"))
            lbl = edge["label"]
            tech_str = f" ({edge['technology']})" if edge["technology"] else ""
            nid = f"n_in_{node_idx}"
            mermaid_lines.append(f'  {nid}["{_q(other_name)}"]')
            mermaid_lines.append(f'  {nid} -->|{_edge_label(lbl, tech_str)}| node_target')

        mermaid_lines.append("  style node_target stroke-width:3px")
        mermaid_code = "\n".join(mermaid_lines)

        combined_text = f"```\n{text_repr}\n```\n\n```mermaid\n{mermaid_code}\n```"

        return {
            "content": [
                {
                    "type": "text",
                    "text": combined_text,
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
                "reason": "No single object with that name or uid is in the catalog index (it is absent or the name is ambiguous).",
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
    sys.stderr.write("Draftsman MCP Server starting on stdio...\n")
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
