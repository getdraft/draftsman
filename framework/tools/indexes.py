#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


UNASSIGNED_DOMAIN_ID = "domain.unassigned"


def object_id(obj: dict[str, Any]) -> str:
    return str(obj.get("uid") or obj.get("id") or "").strip()


def object_name(obj: dict[str, Any], fallback: str = "") -> str:
    value = str(obj.get("name") or fallback).strip()
    return value or fallback


def sorted_objects(registry: dict[str, dict[str, Any]], object_type: str) -> list[dict[str, Any]]:
    return sorted(
        (obj for obj in registry.values() if obj.get("type") == object_type and object_id(obj)),
        key=lambda obj: (object_name(obj, object_id(obj)).lower(), object_id(obj)),
    )


def implementation_sort_key(implementation: dict[str, Any], registry: dict[str, dict[str, Any]]) -> tuple[str, str, str, str]:
    ref = str(implementation.get("ref") or "").strip()
    target = registry.get(ref, {})
    return (
        str(target.get("vendor") or "").lower(),
        object_name(target, ref).lower(),
        str(implementation.get("lifecycleStatus") or "").lower(),
        ref,
    )


def build_domain_capability_index(registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build canonical domain -> capability -> implementation mappings.

    The source of record is capability.domain plus capability.implementations. This
    intentionally does not read domain.capabilities so the index stays aligned
    with the owner-authored capability object.
    """
    domain_entries: dict[str, dict[str, Any]] = {}

    for domain in sorted_objects(registry, "domain"):
        domain_uid = object_id(domain)
        domain_entries[domain_uid] = {
            "id": domain_uid,
            "uid": domain_uid,
            "name": object_name(domain, domain_uid),
            "description": domain.get("description", ""),
            "capabilities": [],
        }

    capabilities_by_domain: dict[str, list[dict[str, Any]]] = {}
    for capability in sorted_objects(registry, "capability"):
        capability_uid = object_id(capability)
        domain_uid = str(capability.get("domain") or UNASSIGNED_DOMAIN_ID).strip() or UNASSIGNED_DOMAIN_ID
        if domain_uid not in domain_entries:
            domain = registry.get(domain_uid, {})
            domain_entries[domain_uid] = {
                "id": domain_uid,
                "uid": domain_uid,
                "name": object_name(domain, domain_uid if domain_uid != UNASSIGNED_DOMAIN_ID else "Unassigned Domain"),
                "description": domain.get("description", ""),
                "capabilities": [],
            }
        raw_implementations = capability.get("implementations")
        implementations = raw_implementations if isinstance(raw_implementations, list) else []
        implementation_entries = [
            {
                "ref": str(implementation.get("ref") or "").strip(),
                "lifecycleStatus": implementation.get("lifecycleStatus", ""),
                "configuration": implementation.get("configuration", ""),
                "notes": implementation.get("notes", ""),
            }
            for implementation in sorted(
                (item for item in implementations if isinstance(item, dict)),
                key=lambda item: implementation_sort_key(item, registry),
            )
        ]
        capabilities_by_domain.setdefault(domain_uid, []).append(
            {
                "id": capability_uid,
                "uid": capability_uid,
                "name": object_name(capability, capability_uid),
                "description": capability.get("description", ""),
                "owner": capability.get("owner", {}),
                "implementationCount": len([item for item in implementation_entries if item.get("ref")]),
                "implementations": implementation_entries,
            }
        )

    for domain_uid, capabilities in capabilities_by_domain.items():
        domain_entries[domain_uid]["capabilities"] = sorted(
            capabilities,
            key=lambda capability: (str(capability.get("name") or "").lower(), str(capability.get("id") or "")),
        )

    domains = sorted(
        domain_entries.values(),
        key=lambda domain: (str(domain.get("name") or "").lower(), str(domain.get("id") or "")),
    )
    return {
        "version": 1,
        "source": "capability.domain",
        "domains": domains,
    }


def build_requirement_implementation_index(registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build canonical requirement implementation evidence rows."""
    rows: list[dict[str, Any]] = []
    for obj in sorted(registry.values(), key=lambda item: (object_name(item, object_id(item)).lower(), object_id(item))):
        implementations = obj.get("requirementImplementations")
        if not isinstance(implementations, list):
            continue
        for implementation in implementations:
            if not isinstance(implementation, dict):
                continue
            requirement_group = str(implementation.get("requirementGroup") or "").strip()
            requirement_id = str(implementation.get("requirementId") or "").strip()
            implementation_entry = dict(implementation)
            rows.append(
                {
                    "object": object_id(obj),
                    "requirementGroup": requirement_group,
                    "requirementId": requirement_id,
                    "status": implementation.get("status", ""),
                    "evidence": implementation.get("evidence", ""),
                    "notes": implementation.get("notes", ""),
                    "implementation": implementation_entry,
                }
            )
    rows.sort(key=lambda row: (row["requirementGroup"], row["requirementId"], row["object"]))
    return {
        "version": 1,
        "source": "object.requirementImplementations",
        "rows": rows,
    }


def build_catalog_indexes(registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    try:
        from catalog_indexes import build_domain_capability_index as build_raw_index
    except ImportError:
        from framework.tools.catalog_indexes import build_domain_capability_index as build_raw_index

    raw_idx = build_raw_index(registry)
    return {
        "domainCapability": build_domain_capability_index(registry),
        "requirementImplementations": build_requirement_implementation_index(registry),
        "domainCapabilities": raw_idx["domainCapabilities"],
        "capabilityDomain": raw_idx["capabilityDomain"],
        "unassignedCapabilities": raw_idx["unassignedCapabilities"],
    }
