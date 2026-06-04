from __future__ import annotations

from typing import Any


def build_domain_capability_index(registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Derive domain/capability relationships from capability.domain.

    The authored source of record is the capability object. Domain objects do not
    need to repeat capability membership; this function creates the optimized
    read model used by the browser, AI indexes, and future validators.
    """
    domains = {
        uid: obj
        for uid, obj in registry.items()
        if obj.get("type") == "domain"
    }
    capabilities = {
        uid: obj
        for uid, obj in registry.items()
        if obj.get("type") == "capability"
    }

    domain_capabilities: dict[str, list[str]] = {uid: [] for uid in sorted(domains)}
    capability_domain: dict[str, str] = {}
    unassigned: list[str] = []

    for capability_uid, capability in capabilities.items():
        domain_uid = str(capability.get("domain") or "").strip()
        if domain_uid:
            capability_domain[capability_uid] = domain_uid
            domain_capabilities.setdefault(domain_uid, []).append(capability_uid)
        else:
            unassigned.append(capability_uid)

    def capability_sort_key(uid: str) -> tuple[str, str]:
        capability = capabilities.get(uid, {})
        return (str(capability.get("name") or "").lower(), uid)

    for domain_uid, capability_uids in domain_capabilities.items():
        capability_uids.sort(key=capability_sort_key)
    unassigned.sort(key=capability_sort_key)

    return {
        "domainCapabilities": domain_capabilities,
        "capabilityDomain": dict(sorted(capability_domain.items())),
        "unassignedCapabilities": unassigned,
    }
