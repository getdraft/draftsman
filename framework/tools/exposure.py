"""Shared exposure resolution (E4) for the diagram renderer and the browser.

A service group of a software deployment pattern is exposed when traffic from outside its
zone reaches it through an edge device chain. The precedence lives here once:

1. ``exposedThrough: none`` switches exposure off.
2. ``exposedThrough`` as a uid or a list of uids is the chain, in the given order.
3. Otherwise the filled edge slots of the reference architecture the pattern follows apply,
   in ``EDGE_SLOTS`` order, except to a data tier (a group whose deployable objects are all
   data components), which only ``exposedThrough`` exposes.

The resolver is lenient: values that are not network services are left out and repeats are
dropped, so a pattern that fails validation still renders. ``validate.py`` reports those
values (``validate_exposed_through`` and ``validate_fills``).
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

# Drawn and resolved in this order: protection, then availability, then routing.
EDGE_SLOTS: tuple[str, ...] = ("firewall", "web-application-firewall", "load-balancer", "api-gateway", "ingress")


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def _is_network_service(uid: str, catalog: Mapping[str, Mapping[str, Any]]) -> bool:
    return (catalog.get(uid) or {}).get("type") == "network_service"


def slot_chain(reference_architecture: Mapping[str, Any] | None, catalog: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """The filled edge slots of a reference architecture, as a device chain.

    Every entry whose slot is an edge slot and whose ``fills`` names a network_service, in
    ``EDGE_SLOTS`` order (document order within a slot), each uid once. The reference
    architecture service group an entry sits in does not matter.
    """
    ra_groups = reference_architecture.get("serviceGroups") if isinstance(reference_architecture, Mapping) else None
    filled: list[tuple[int, str]] = []
    for ra_group in ra_groups if isinstance(ra_groups, list) else []:
        entries = ra_group.get("deployableObjects") if isinstance(ra_group, Mapping) else None
        for entry in entries or []:
            if not isinstance(entry, Mapping) or _clean(entry.get("slot")) not in EDGE_SLOTS:
                continue
            uid = _clean(entry.get("fills"))
            if _is_network_service(uid, catalog) and uid not in [u for _k, u in filled]:
                filled.append((EDGE_SLOTS.index(_clean(entry.get("slot"))), uid))
    return [uid for _k, uid in sorted(filled, key=lambda item: item[0])]


def pattern_slot_chain(sdp: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """``slot_chain`` of the reference architecture the pattern follows; [] when it follows none."""
    return slot_chain(catalog.get(_clean(sdp.get("followsReferenceArchitecture"))), catalog)


def group_chain(
    exposed_through: Any,
    listed: Iterable[str],
    catalog: Mapping[str, Mapping[str, Any]],
    default_chain: list[str],
) -> list[str]:
    """A service group's edge device chain; [] when it is not exposed.

    ``exposed_through`` is the group's raw ``exposedThrough`` value, ``listed`` the catalog uids
    its deployable objects reference, and ``default_chain`` the pattern's ``pattern_slot_chain``.
    """
    if exposed_through == "none":
        return []
    if isinstance(exposed_through, str) and _clean(exposed_through):
        values: list[Any] | None = [exposed_through]
    elif isinstance(exposed_through, list) and exposed_through:
        values = exposed_through
    else:
        values = None
    if values is not None:
        chain: list[str] = []
        for value in values:
            uid = _clean(value) if isinstance(value, str) else ""
            if _is_network_service(uid, catalog) and uid not in chain:
                chain.append(uid)
        return chain
    listed = list(listed)
    if listed and all((catalog.get(uid) or {}).get("type") == "data_component" for uid in listed):
        return []
    return list(default_chain)


def resolve_pattern_exposure(sdp: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]]) -> list[list[str]]:
    """The chain of every entry of ``sdp.serviceGroups``, by index ([] for a non-mapping entry)."""
    default_chain = pattern_slot_chain(sdp, catalog)
    chains: list[list[str]] = []
    groups = sdp.get("serviceGroups")
    for group in groups if isinstance(groups, list) else []:
        if not isinstance(group, Mapping):
            chains.append([])
            continue
        listed = [
            str(entry["ref"])
            for entry in group.get("deployableObjects") or []
            if isinstance(entry, Mapping) and entry.get("ref") and str(entry["ref"]) in catalog
        ]
        chains.append(group_chain(group.get("exposedThrough"), listed, catalog, default_chain))
    return chains
