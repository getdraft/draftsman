#!/usr/bin/env python3
"""Render a DRAFT Software Deployment Pattern as a visual diagram page.

Usage:
    python3 framework/tools/generate_diagram.py --list [--workspace PATH]
    python3 framework/tools/generate_diagram.py --sdp NAME_OR_UID [--workspace PATH]
        [--output FILE] [--placed-only] [--svg-dir DIR] [--write-layout] [--editable] [--layout-from FILE]
    python3 framework/tools/generate_diagram.py --all --output-dir DIR [--svg-dir DIR]
        [--workspace PATH] [--placed-only]

The generator reads the DRAFT catalog and writes one self-contained HTML page
(inline SVG, no external requests, light and dark themes). It is deterministic:
the same catalog always produces the same page.

What is drawn comes only from the catalog:

* In the deployment view, a deployment target holds the service groups recorded
  for it, each group is a container captioned with its substrate, and network
  zone lanes hold the placed objects.
* In the logical view, one box per object in the pattern's scope, in bands by tier.
* One arrow per ``relationship`` object or recorded ``runtimeSpec.dependencies``
  entry whose source and target are both drawn. A component with no recorded
  relationship gets no arrow. Nothing is inferred.

By default the scope is the objects placed in the pattern plus each object a placed
object has a relationship to (its dependencies, D42) whose type is a component, data, data store,
runtime, network, AI gateway or host object. Objects that only call into the pattern are not drawn. ``--placed-only`` restricts the drawing to placed objects.
Derived ``runs on`` relationships never extend the scope.

The page holds the logical application diagram and the deployment pattern diagram
(two inline SVG figures that pin together), then the recorded relationships,
conflicts, characteristics, open questions and an inventory of every in-scope
object. The framework version appears only in the footer.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import itertools
import math
import re
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from generate_c4 import DEFAULT_WORKSPACE_ROOT, load_catalog  # noqa: E402

E = html.escape

CHIP_W = 190
CHIP_H = 46


# --------------------------------------------------------------------------- model
def sdps(catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    found = [o for o in catalog.values() if o.get("type") == "software_deployment_pattern"]
    return sorted(found, key=lambda o: (str(o.get("name", "")).lower(), str(o.get("uid", ""))))


def pick_sdp(catalog: dict[str, dict[str, Any]], selector: str | None) -> dict[str, Any]:
    patterns = sdps(catalog)
    if not patterns:
        raise SystemExit("No software_deployment_pattern objects found in this workspace.")
    if selector is None:
        if len(patterns) == 1:
            return patterns[0]
        names = ", ".join(f"{p.get('name')} ({p.get('uid')})" for p in patterns)
        raise SystemExit(f"Several deployment patterns found; pass --sdp. Available: {names}")
    wanted = selector.strip().lower()
    by_uid = [p for p in patterns if str(p.get("uid", "")).lower() == wanted]
    if len(by_uid) == 1:
        return by_uid[0]
    matches = [
        p
        for p in patterns
        if wanted in {str(p.get("uid", "")).lower(), str(p.get("name", "")).lower(), *(str(a).lower() for a in (p.get("aliases") or []))}
    ]
    if len(matches) > 1:
        names = ", ".join(f"{p.get('name')} ({p.get('uid')})" for p in matches)
        raise SystemExit(f"'{selector}' matches several deployment patterns; pass a uid. Matches: {names}")
    if matches:
        return matches[0]
    raise SystemExit(f"No deployment pattern matches '{selector}'. Use --list to see the choices.")


def lifecycle(obj: dict[str, Any]) -> str:
    return str(obj.get("lifecycleStatus") or "")


def clean(text: Any) -> str:
    return " ".join(str(text or "").split())


@dataclass
class DiagramNode:
    """One node of a view: a placed object, an outside-lane object or an external target."""

    uid: str
    name: str
    node_type: str
    placed: bool = False
    external: bool = False
    outside: bool = False  # drawn in the outside lane (D5)
    band: str = ""  # D4 band; empty for externals, which have no catalog type
    derived: bool = False  # placed entry without diagramTier (D4)
    caption: str = ""  # D5 caption for outside-lane nodes
    life: str = ""  # lifecycleStatus of the object; empty for external nodes (D12)
    tech: str = ""  # technology line of the box (D11)


@dataclass
class DiagramEdge:
    """One drawn relationship. ``derived`` marks a runtimeSpec.dependencies edge (D31)."""

    source: str
    target: str
    label: str = ""
    derived: bool = False
    uid: str = ""
    origin: str = "relationship object"  # D31: "inline dependency" for runtimeSpec.dependencies
    direction: str = ""
    flow: str = ""
    technology: str = ""


@dataclass
class DiagramStore:
    """The container of the data components of one group that run on one data store service (D45).

    uid is "" for the 'data store not recorded' container (runsOn absent or not a data store service).
    """

    uid: str
    name: str  # the store's recorded name, or "data store not recorded"
    members: list[str] = field(default_factory=list)  # data components drawn as boxes inside it, in listing order
    life: str = ""  # lifecycleStatus of the store, for the retired and deprecated classes (D12)


@dataclass
class DiagramLane:
    """One network-zone lane inside a service group container (D9). zone is "" for 'zone not recorded'."""

    zone: str
    name: str
    tier: str  # informational only; never affects band placement (D4, D9)
    members: list[str] = field(default_factory=list)
    stores: list[DiagramStore] = field(default_factory=list)  # D45: data store containers in this lane


@dataclass
class DiagramContainer:
    """The drawn container of one service group (D6, D7). uid is "" when no catalog object resolves."""

    uid: str
    caption: str = ""
    group: str = ""
    target: str = ""
    derived: bool = False
    members: list[str] = field(default_factory=list)  # placed objects drawn as boxes; never the container itself
    lanes: list[DiagramLane] = field(default_factory=list)
    name: str = ""  # the substrate object's recorded name, for edge tooltips; "" when no object resolves
    drawn: bool = False  # D6: False for a group with nothing to draw, which the caption names instead
    life: str = ""  # lifecycleStatus of the container's object, for the retired and deprecated classes (D12)


@dataclass
class Conflict:
    """A placed component whose runsOn differs from its group's recorded substrate (D8). Nothing is resolved."""

    group: str
    component: str
    runs_on: str
    substrate: str


@dataclass
class DiagramModel:
    sdp_uid: str
    nodes: list[DiagramNode] = field(default_factory=list)
    edges: list[DiagramEdge] = field(default_factory=list)
    containers: list[DiagramContainer] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    deployment_nodes: list[DiagramNode] = field(default_factory=list)  # D29: nodes minus drawn containers
    logical_positions: dict[str, int] = field(default_factory=dict)  # D38/D39: diagram_layout positions, logical view
    deployment_positions: dict[str, int] = field(default_factory=dict)  # D38/D39: diagram_layout positions, deployment view


# D2: object types that may appear one hop away from a placed object.
ONE_HOP_TYPES = frozenset(
    {"product_component", "data_component", "data_store_service", "runtime_service", "network_service", "ai_gateway", "host"}
)

# D13: flow values from the relationship schema; any other recorded value is treated as absent, with a warning.
FLOWS = ("outbound", "inbound", "bidirectional")

# D43: placed objects of these types are drawn in the deployment view only; D44: what they source is kept
# only when its target is placed in the same pattern.
INFRA_TYPES = frozenset({"network_service", "runtime_service", "host", "ai_gateway", "data_store_service"})

# D7: types whose runsOn may name the substrate of their service group.
COMPONENT_TYPES = frozenset({"product_component", "data_component"})

# D4: band derived from type when the placing entry records no diagramTier.
TYPE_BANDS = {
    "product_component": "application",
    "data_component": "data",
    "data_store_service": "data",
    "runtime_service": "application",
    "network_service": "presentation",
    "ai_gateway": "application",
    "host": "utility",
}


def type_band(obj_type: Any) -> str:
    # D4 (type-derived band): types outside the map fall back to application. Behaviour kept; not listed in D4.
    return TYPE_BANDS.get(str(obj_type or ""), "application")


def _endpoint(rel: dict[str, Any], key: str) -> str:
    value = rel.get(key)
    return value.strip() if isinstance(value, str) else ""


def is_dependency(rel: dict[str, Any]) -> bool:
    """Built from runtimeSpec.dependencies (D31): a recorded dependency, drawn as an edge."""
    return bool(rel.get("_derived")) and "[inline dependency]" in str(rel.get("_source", ""))


def is_runs_on(rel: dict[str, Any]) -> bool:
    """Built from runsOn or host (D31): a placement fact that is never an edge or a row."""
    return bool(rel.get("_derived")) and not is_dependency(rel)


def external_uid(text: str) -> str:
    """Stable id of an externalTarget string (D3): 'ext:' plus 12 hex characters of its sha256."""
    return "ext:" + hashlib.sha256(clean(text).encode("utf-8")).hexdigest()[:12]


def _other_pattern_names(catalog: dict[str, dict[str, Any]], sdp: dict[str, Any]) -> dict[str, list[str]]:
    """uid -> names of the other patterns that place it, in pattern order (D5 captions)."""
    found: dict[str, list[tuple[int, str]]] = {}  # uid -> (pattern position, display name)
    for position, other in enumerate(sdps(catalog)):
        if other is sdp:
            continue
        groups = other.get("serviceGroups")
        if not isinstance(groups, list):
            continue
        label = str(other.get("name") or other.get("uid") or "")
        for group in groups:
            if not isinstance(group, dict):
                continue
            for entry in group.get("deployableObjects") or []:
                if isinstance(entry, dict) and entry.get("ref"):
                    places = found.setdefault(str(entry["ref"]), [])
                    if all(seen != position for seen, _name in places):
                        places.append((position, label))
    return {uid: [name for _position, name in places] for uid, places in found.items()}


def technology_line(catalog: dict[str, dict[str, Any]], obj: dict[str, Any]) -> str:
    """D11: the technology line of a node box. The inventory column of the page uses the same rule.

    A reference that does not resolve is shown as its raw uid. Empty means nothing is recorded.
    """

    def named(value: Any) -> str:
        uid = clean(value)
        if not uid:
            return ""
        target = catalog.get(uid)
        if isinstance(target, dict):
            return clean(target.get("name")) or uid
        return uid

    kind = str(obj.get("type", ""))
    if kind == "product_component":
        return clean(obj.get("language"))
    if kind == "data_component":
        return clean(obj.get("targetEngine"))
    if kind in ("data_store_service", "runtime_service", "network_service", "ai_gateway"):
        return clean(obj.get("productName")) or named(obj.get("primaryTechnologyComponent"))
    if kind == "host":
        return named(obj.get("computePlatformComponent")) or named(obj.get("operatingSystemComponent"))
    return ""


class Model:
    """Everything the page shows, resolved from the catalog.

    Scope (D2, narrowed by D41 and D42): every placed object plus each unplaced object that a placed
    object is the source of a relationship to, when its type is in ONE_HOP_TYPES. Unplaced consumers
    (objects that only source relationships into placed ones) are not nodes, and only relationships
    whose source is placed are edges or rows. Derived ``runs on`` relationships never extend scope
    and never become edges or relationship rows (D31).
    """

    def __init__(self, catalog: dict[str, dict[str, Any]], sdp: dict[str, Any], placed_only: bool):
        self.catalog = catalog
        self.sdp = sdp
        self.placed_only = placed_only
        self.warnings: list[str] = []  # in discovery order; de-duplicated and sorted by the page (S4)
        self.placement: dict[str, dict[str, str]] = {}  # first placement of each uid, in document order
        self.groups: list[dict[str, Any]] = []
        self.containers: list[DiagramContainer] = []
        self.conflicts: list[Conflict] = []
        self.container_uids: set[str] = set()  # membership tests only
        self.drawn_container_uids: set[str] = set()  # containers of groups that have drawable objects
        self.store_container_uids: set[str] = set()  # D45: data store services drawn as containers, never as boxes
        self._read_groups()
        self._other_patterns = _other_pattern_names(catalog, sdp)
        self._build_nodes_and_edges()
        self._build_containers()
        self.layout_uid = ""  # uid of the honoured diagram_layout; "" when none
        self.layout_positions: dict[str, dict[str, int]] = {"logical": {}, "deployment": {}}
        self._read_layout()
        self.warnings = sorted(set(self.warnings))  # D18: each distinct string once, in code-point order

    @property
    def warning_count_line(self) -> str:
        return f"{len(self.warnings)} warnings"

    def name(self, uid: str) -> str:
        return str(self.catalog.get(uid, {}).get("name") or uid)

    def sub(self, uid: str) -> str:
        obj = self.catalog[uid]
        if lifecycle(obj) in {"retired", "deprecated"}:
            return lifecycle(obj)
        return str(obj.get("classification") or str(obj.get("type", "")).replace("_", " "))

    def nodes_for_view(self, view: str) -> list[DiagramNode]:
        if view == "logical":
            # D43: placed infrastructure belongs to the deployment view; unplaced dependencies stay in the lane.
            # An outside node reached only by infrastructure-sourced edges would sit in the lane with no edge.
            fed = {e.target for e in self.edges if not self._is_infra_source(e.source)}
            return [
                node
                for node in self._nodes
                if not (node.placed and node.node_type in INFRA_TYPES) and (not node.outside or node.uid in fed)
            ]
        if view == "deployment":
            # D29: a service group's drawn container is never also a box in the deployment view. A substrate
            # whose group is not drawn has no container figure, so it stays a box (see _build_containers).
            # D45: likewise a data store service that is drawn as a data component container.
            hidden = self.drawn_container_uids | self.store_container_uids
            return [node for node in self._nodes if node.uid not in hidden]
        raise ValueError(f"unknown view: {view!r}")

    def _read_layout(self) -> None:
        """D38: the diagram_layout for this pattern (lowest uid wins), read as view -> ref -> position (D39)."""
        sdp_uid = str(self.sdp.get("uid", ""))
        found = sorted(
            str(uid) for uid, obj in self.catalog.items() if obj.get("type") == "diagram_layout" and obj.get("pattern") == sdp_uid
        )
        if not found:
            return
        self.layout_uid = found[0]
        if len(found) > 1:
            self.warnings.append(f"multiple diagram layouts for {sdp_uid}; using {found[0]}")
        layout = self.catalog[found[0]]
        drawn = {
            "logical": {n.uid for n in self.nodes_for_view("logical")},
            "deployment": {n.uid for n in self.nodes_for_view("deployment")} | self.drawn_container_uids | self.store_container_uids,
        }
        for view in ("logical", "deployment"):
            entries = layout.get(view)
            for entry in entries if isinstance(entries, list) else []:
                if not isinstance(entry, dict) or not entry.get("ref"):
                    continue
                ref = str(entry["ref"])
                position = entry.get("position")
                if isinstance(position, bool) or not isinstance(position, int) or position < 1:
                    continue
                if ref not in drawn[view]:
                    self.warnings.append(f"layout position for undrawn object {ref}")
                    continue
                known = self.layout_positions[view].get(ref)
                self.layout_positions[view][ref] = position if known is None else min(known, position)

    def _read_groups(self) -> None:
        raw_groups = self.sdp.get("serviceGroups")
        if raw_groups is None:
            raw_groups = []
        if not isinstance(raw_groups, list):
            raise ValueError("serviceGroups must be a list")  # D32
        occurrences: dict[str, list[str]] = {}  # uid -> group names of every valid listing, in document order
        for number, group in enumerate(raw_groups, start=1):
            if not isinstance(group, dict):
                self.warnings.append(f"serviceGroups entry {number} is not a mapping; skipped")
                continue
            group_name = str(group.get("name", ""))
            target = str(group.get("deploymentTarget", ""))
            uids: list[str] = []
            group_listed: list[str] = []  # every resolvable ref in this group, repeats included (D7 "also listed")
            zone_of: dict[str, str] = {}  # first-listed uid of this group -> its networkZone ("" when absent)
            for entry in group.get("deployableObjects") or []:
                if not isinstance(entry, dict) or not entry.get("ref"):
                    self.warnings.append(f"service group '{group.get('name')}' has an entry without a ref; skipped")
                    continue
                ref = str(entry["ref"])
                if ref not in self.catalog:
                    self.warnings.append(f"service group '{group.get('name')}' references unknown uid '{ref}'")
                    continue
                occurrences.setdefault(ref, []).append(group_name)
                group_listed.append(ref)
                if ref in self.placement:
                    continue
                uids.append(ref)
                zone = clean(entry.get("networkZone"))
                zone_of[ref] = zone
                self.placement[ref] = {
                    "group": group_name,
                    "target": target,
                    "tier": clean(entry.get("diagramTier")),
                    "zone": zone,
                }
            self.groups.append(
                {
                    "name": group_name,
                    "target": target,
                    "uids": uids,
                    "substrate": clean(group.get("substrate")),
                    "listed": group_listed,
                    "zone_of": zone_of,
                }
            )
        for uid, listed in occurrences.items():  # D26
            if len(listed) > 1:
                later: list[str] = []
                for group_name in listed[1:]:
                    if group_name not in later:
                        later.append(group_name)
                self.warnings.append(
                    f"duplicate placement: {self.name(uid)} ({uid}) first placed in {listed[0]}; "
                    f"also listed in {', '.join(later)}"
                )
        for uid, place in self.placement.items():  # D4: placed entries only
            if not place["tier"]:
                self.warnings.append(f"derived tier: {self.name(uid)} ({uid}) -> {type_band(self.catalog[uid].get('type'))}")

    def _build_nodes_and_edges(self) -> None:
        catalog = self.catalog
        placed = set(self.placement)  # membership tests only; output order comes from lists
        recorded = sorted(
            (o for o in catalog.values() if o.get("type") == "relationship" and not is_runs_on(o)),
            key=lambda o: str(o.get("uid", "")),
        )
        infra = {uid for uid in placed if catalog[uid].get("type") in INFRA_TYPES}  # D44: sources that carry no borrowed flows
        outside: set[str] = set()
        externals: dict[str, str] = {}  # external id -> trimmed, whitespace-collapsed text (D3)
        if not self.placed_only:
            for rel in recorded:
                source, target = _endpoint(rel, "source"), _endpoint(rel, "target")
                # D42: only the objects a placed object depends on enter scope; consumers do not.
                # D44: a placed infrastructure object's relationship to a target another pattern places belongs to that page.
                if source in infra and target in self._other_patterns:
                    continue
                if source in placed and target and target not in placed and catalog.get(target, {}).get("type") in ONE_HOP_TYPES:
                    outside.add(target)
                text = clean(rel.get("externalTarget"))
                if source in placed and not target and text:
                    externals.setdefault(external_uid(text), text)

        nodes: list[DiagramNode] = []
        for uid, place in self.placement.items():
            obj = catalog[uid]
            tier = place["tier"]
            nodes.append(
                DiagramNode(
                    uid=uid,
                    name=self.name(uid),
                    node_type=str(obj.get("type", "")),
                    placed=True,
                    band=tier or type_band(obj.get("type")),
                    derived=not tier,
                    life=lifecycle(obj),
                    tech=technology_line(catalog, obj),
                )
            )
        outer: list[DiagramNode] = []
        for uid in outside:
            obj = catalog[uid]
            outer.append(
                DiagramNode(
                    uid=uid,
                    name=self.name(uid),
                    node_type=str(obj.get("type", "")),
                    outside=True,
                    band=type_band(obj.get("type")),
                    caption=self._caption(uid),
                    life=lifecycle(obj),
                    tech=technology_line(catalog, obj),
                )
            )
        for ext_id, text in externals.items():
            outer.append(
                DiagramNode(uid=ext_id, name=text, node_type="external", external=True, outside=True, caption="external")
            )
        outer.sort(key=lambda n: n.uid)
        self._nodes = nodes + outer
        self._by_uid = {node.uid: node for node in self._nodes}
        self.scope = {node.uid for node in self._nodes if not node.external}
        self.unplaced_drawn = sorted(
            (node.uid for node in outer if not node.external), key=lambda u: self.name(u).lower()
        )

        self.edges: list[DiagramEdge] = []
        self.relationships: list[dict[str, Any]] = []  # catalog-to-catalog relationship objects that are drawn
        self.relationship_rows: list[dict[str, str]] = []
        drawn: set[int] = set()  # ids of drawn relationship dicts; membership only
        for rel in recorded:
            flow = str(rel.get("flow") or "")
            if flow and flow not in FLOWS:  # D13: an unknown flow is absent flow, with a warning
                self.warnings.append(f"unknown flow '{flow}' on {rel.get('uid', '')}")
                flow = ""
            source, target = _endpoint(rel, "source"), _endpoint(rel, "target")
            if target:
                end = target
            else:
                text = clean(rel.get("externalTarget"))
                if not text:
                    continue
                end = external_uid(text)
            if source not in self._by_uid or end not in self._by_uid:
                continue
            if source not in placed:  # D41/D42: edges of unplaced sources (consumers, outside-to-outside) are not drawn
                continue
            if source in infra and end not in placed and end in self._other_patterns:  # D44: no borrowed flows, so not drawn and not tabled
                continue
            dependency = is_dependency(rel)
            edge = DiagramEdge(
                source=source,
                target=end,
                label=clean(rel.get("label")),
                derived=dependency,
                uid=str(rel.get("uid", "")),
                origin="inline dependency" if dependency else "relationship object",
                direction=str(rel.get("direction") or ""),
                flow=flow,
                technology=clean(rel.get("technology")),
            )
            self.edges.append(edge)
            drawn.add(id(rel))
            if target:
                self.relationships.append(rel)
            self.relationship_rows.append(
                {
                    "uid": edge.uid,
                    "from": self._by_uid[source].name,
                    "label": edge.label,
                    "to": self._by_uid[end].name,
                    "description": clean(rel.get("description") or rel.get("notes")),
                    "source": edge.origin,
                }
            )
        self.relationship_rows.sort(key=lambda r: (r["from"].lower(), r["label"], r["to"].lower(), r["uid"]))
        # Recorded relationships that touch the placed set but are not drawn (D2 placed-only, D31).
        self.undrawn_relationship_count = sum(
            1
            for rel in recorded
            if (_endpoint(rel, "source") in placed or _endpoint(rel, "target") in placed) and id(rel) not in drawn
        )

    def _derive_substrate(self, uids: list[str]) -> str:
        """D7: the runsOn target that every placed component recording runsOn agrees on, else ''.

        Only runsOn of product and data components is read; host fields are never used.
        """
        targets = {
            clean(self.catalog[uid].get("runsOn"))
            for uid in uids
            if self.catalog[uid].get("type") in COMPONENT_TYPES and not self._on_store(uid)
        }
        targets.discard("")
        return targets.pop() if len(targets) == 1 else ""

    def _is_infra_source(self, uid: str) -> bool:
        return uid in self.placement and self.catalog[uid].get("type") in INFRA_TYPES

    def _on_store(self, uid: str) -> bool:
        """D45/D8: a data component whose runsOn is a data store service, absent or unresolved sits in a store container.

        It is never compared with the group substrate and does not take part in substrate derivation.
        """
        obj = self.catalog[uid]
        if obj.get("type") != "data_component":
            return False
        runs_on = clean(obj.get("runsOn"))
        # absent or unresolved runsOn is D45's 'data store not recorded' case, not a D7 substrate target
        return runs_on not in self.catalog or self.catalog[runs_on].get("type") == "data_store_service"

    def _build_containers(self) -> None:
        """Service group containers with caption variants (D7), conflicts (D8) and zone lanes (D9)."""
        catalog = self.catalog
        zones = self.sdp.get("networkZones")
        declared: dict[str, dict[str, Any]] = {}  # zone id -> entry, in networkZones document order
        for zone in zones if isinstance(zones, list) else []:
            zone_id = clean(zone.get("id")) if isinstance(zone, dict) else ""
            if zone_id:
                declared.setdefault(zone_id, zone)
        # D6, D7, D29: a group is drawn when it lists at least one object that is not the container of another
        # drawn group; its own substrate listed among its objects counts, since that object is drawn as this
        # group's container. Which groups are drawn and which objects are containers depend on each other, so
        # iterate to a fixed point; the drawn set only shrinks, so this ends.
        planned = [group["substrate"] or self._derive_substrate(group["uids"]) for group in self.groups]
        planned = [uid if uid in catalog else "" for uid in planned]
        drawable = [bool(group["uids"]) for group in self.groups]

        def store_hosts(flags: list) -> set:
            """D45: data store services drawn as data component containers by the groups flagged as drawn."""
            return {
                store
                for index, (group, ok) in enumerate(zip(self.groups, flags))
                if ok
                for store in (self._store_of(uid, planned[index]) for uid in group["uids"])
                if store
            }

        while True:
            containers = {uid for uid, ok in zip(planned, drawable) if ok and uid} | store_hosts(drawable)
            again = [
                ok and any(uid == planned[index] or uid not in containers for uid in group["uids"])
                for index, (group, ok) in enumerate(zip(self.groups, drawable))
            ]
            if again == drawable:
                break
            drawable = again
        # Groups that name each other's substrate can all drop out above while the objects they list are nobody's
        # container. Every placed object needs a home, so such a group is drawn after all (its substrate then
        # becomes a container, and the object it lists stays a box or becomes the other group's container).
        while True:
            containers = {uid for uid, ok in zip(planned, drawable) if ok and uid} | store_hosts(drawable)
            homeless = [
                index for index, (group, ok) in enumerate(zip(self.groups, drawable))
                if not ok and any(uid not in containers for uid in group["uids"])
            ]
            if not homeless:
                break
            for index in homeless:
                drawable[index] = True
        self.container_uids = {uid for uid, ok in zip(planned, drawable) if ok and uid}
        self.drawn_container_uids = set(self.container_uids)
        self.store_container_uids = store_hosts(drawable)  # D45: a store hosting a drawn data component is a container
        for group_index, group in enumerate(self.groups):
            group_name = group["name"]
            recorded = group["substrate"]
            sub_uid = recorded or self._derive_substrate(group["uids"])
            derived = bool(sub_uid) and not recorded
            container_uid = ""
            if not sub_uid:
                caption = "substrate not recorded"
            elif sub_uid not in catalog:
                caption = f"substrate not found: {sub_uid}"
                self.warnings.append(f"unknown substrate uid '{sub_uid}' in {group_name}")
            else:
                container_uid = sub_uid
                obj = catalog[sub_uid]
                name = self.name(sub_uid)
                sub_type = str(obj.get("type", ""))
                caption = name
                if sub_type not in ("runtime_service", "host"):
                    caption = f"{name} ({sub_type})"
                    self.warnings.append(
                        f"substrate {name} ({sub_uid}) has type {sub_type}; expected runtime_service or host"
                    )
                if derived:
                    caption += " derived"
                host = clean(obj.get("host"))
                if host:  # one level only: the host's own host is not followed
                    caption += f" on {self.name(host)}"
                if sub_uid in group["listed"]:
                    self.warnings.append(f"substrate also listed as deployable object: {name} ({sub_uid}) in {group_name}")
            if recorded:  # D8: only a recorded substrate can conflict; nothing is resolved
                for uid in group["uids"]:
                    obj = catalog[uid]
                    runs_on = clean(obj.get("runsOn")) if obj.get("type") in COMPONENT_TYPES and not self._on_store(uid) else ""
                    if runs_on and runs_on != recorded:
                        self.conflicts.append(Conflict(group=group_name, component=uid, runs_on=runs_on, substrate=recorded))
                        self.warnings.append(
                            f"conflict: {self.name(uid)} runsOn {self.name(runs_on)}; group substrate is {self.name(recorded)}"
                        )
            hidden = self.container_uids | self.store_container_uids
            members = [uid for uid in group["uids"] if uid not in hidden] if drawable[group_index] else []
            plain: list[str] = []
            stores: dict[str, DiagramStore] = {}  # D45: store uid ("" when not recorded) -> container, in listing order
            for uid in members:
                store = self._store_of(uid, sub_uid)
                if store is None:
                    plain.append(uid)
                    continue
                if store not in stores:
                    store_name = self.name(store) if store else "data store not recorded"
                    store_type = str(catalog[store].get("type", "")) if store else ""
                    if store and store_type != "data_store_service":  # D45, as D7 for a substrate: name the type and warn
                        store_name = f"{store_name} ({store_type})"
                        self.warnings.append(
                            f"data store {self.name(store)} ({store}) has type {store_type}; expected data_store_service"
                        )
                    stores[store] = DiagramStore(uid=store, name=store_name, life=lifecycle(catalog[store]) if store else "")
                stores[store].members.append(uid)
                if not store:
                    self.warnings.append(f"data store not recorded: {self.name(uid)} ({uid}) has no runsOn data store service")
            if container_uid and not drawable[group_index] and container_uid not in self.container_uids:
                # D29: nothing is drawn for this group. A substrate that is a node stays a box; any other
                # substrate has no node, so say plainly that it is not drawn.
                if any(n.uid == container_uid for n in self._nodes):
                    self.warnings.append(
                        f"substrate of a group with no drawable objects kept as a box: {self.name(container_uid)} ({container_uid}) in {group_name}"
                    )
                else:
                    self.warnings.append(
                        f"substrate of a group with no drawable objects is not drawn: {self.name(container_uid)} ({container_uid}) in {group_name}"
                    )
            zone_of = group["zone_of"]
            buckets: dict[str, list[str]] = {}
            unrecorded: list[str] = []
            undeclared: list[str] = []
            store_buckets: dict[str, list[DiagramStore]] = {}
            store_unrecorded: list[DiagramStore] = []
            for uid in plain:
                zone = zone_of.get(uid, "")
                if zone in declared:
                    buckets.setdefault(zone, []).append(uid)
                else:
                    unrecorded.append(uid)
                    if zone and zone not in undeclared:
                        undeclared.append(zone)
            # D45: the container takes the zone lane of its first data component; 'not recorded' is always last (D40)
            for store in sorted(stores.values(), key=lambda st: not st.uid):
                zone = zone_of.get(store.members[0], "")
                for uid in store.members:  # a data component is never silently moved out of its zone (D9)
                    other = zone_of.get(uid, "")
                    if other and other not in declared and other not in undeclared:
                        undeclared.append(other)
                    if uid == store.members[0]:
                        continue
                    if (other if other in declared else "") != (zone if zone in declared else ""):
                        lane_name = clean(declared[zone].get("name")) or zone if zone in declared else "zone not recorded"
                        self.warnings.append(f"data component {self.name(uid)} zone {other or 'not recorded'} drawn in lane {lane_name}")
                if zone in declared:
                    store_buckets.setdefault(zone, []).append(store)
                else:
                    store_unrecorded.append(store)
            for zone in undeclared:
                self.warnings.append(f"undeclared network zone: {zone} in {group_name}")
            lanes = [
                DiagramLane(
                    zone=zone,
                    name=clean(declared[zone].get("name")) or zone,
                    tier=clean(declared[zone].get("tier")),
                    members=buckets.get(zone, []),
                    stores=store_buckets.get(zone, []),
                )
                for zone in declared
                if zone in buckets or zone in store_buckets
            ]
            if unrecorded or store_unrecorded:  # D9: absent or undeclared zones share a last lane
                lanes.append(DiagramLane(zone="", name="zone not recorded", tier="", members=unrecorded, stores=store_unrecorded))
            self.containers.append(
                DiagramContainer(
                    uid=container_uid,
                    caption=caption,
                    group=group_name,
                    target=group["target"],
                    derived=derived,
                    members=members,
                    lanes=lanes,
                    name=self.name(container_uid) if container_uid else "",
                    drawn=drawable[group_index],
                    life=lifecycle(catalog[container_uid]) if container_uid else "",
                )
            )

    def _store_of(self, uid: str, substrate: str) -> str | None:
        """D45: the object a placed data component runs on; "" when runsOn is absent or unresolved; None for other objects.

        A data component whose runsOn is its own group's substrate stays a plain box (D7, D29), so None too.
        """
        obj = self.catalog[uid]
        if obj.get("type") != "data_component":
            return None
        runs_on = clean(obj.get("runsOn"))
        if runs_on and runs_on == substrate:
            return None
        return runs_on if runs_on in self.catalog else ""

    def _caption(self, uid: str) -> str:
        names = self._other_patterns.get(uid, [])
        if not names:
            return "not placed in any pattern"
        if len(names) == 1:
            return names[0]
        return f"placed in {len(names)} other patterns"



# --------------------------------------------------------------------------- layout
def wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    lines.append(current)
    return lines


def border_point(
    c: tuple[float, float], toward: tuple[float, float], w: float = CHIP_W, h: float = CHIP_H
) -> tuple[float, float]:
    """Point where the line from centre c toward another point leaves a w by h rectangle centred on c."""
    dx, dy = toward[0] - c[0], toward[1] - c[1]
    if dx == 0 and dy == 0:
        return c
    t = min((w / 2) / abs(dx) if dx else math.inf, (h / 2) / abs(dy) if dy else math.inf)
    return c[0] + dx * t, c[1] + dy * t


# --------------------------------------------------------------------------- html parts
# A vendored copy keeps draft-framework.yaml beside its tools/ inside the framework directory; the source repo keeps it at the root.
FRAMEWORK_MANIFESTS = (TOOLS_ROOT.parent / "draft-framework.yaml", TOOLS_ROOT.parents[1] / "draft-framework.yaml")
FIGURE_IDS = ("fig-logical", "fig-deployment")  # D19: the pin script finds both figures by these ids


def framework_version() -> str:
    """The framework version recorded in draft-framework.yaml. It is stamped only in the HTML footer (D15)."""
    manifest = None
    for path in FRAMEWORK_MANIFESTS:
        if path.is_file():
            try:
                manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                return "version not recorded"
            break
    version = manifest.get("version") if isinstance(manifest, dict) else None
    return clean(version) or "version not recorded"


def _text_of(value: Any) -> str:
    """Plain text for a nested recorded value such as tierVariants or scalingUnits (D10)."""
    if isinstance(value, dict):
        return "; ".join(f"{clean(k)}: {_text_of(v)}" for k, v in value.items() if v not in (None, "", [], {}))
    if isinstance(value, list):
        return "; ".join(text for text in (_text_of(v) for v in value) if text)
    if isinstance(value, bool):
        return "true" if value else "false"
    return clean(value)


def header_html(model: Model) -> str:
    """D19 header: pattern name, lifecycle, owner team, and the reference architecture when it resolves."""
    sdp = model.sdp
    name = clean(sdp.get("name")) or "Deployment pattern"
    owner = sdp.get("owner")
    team = clean(owner.get("team")) if isinstance(owner, dict) else ""
    lifecycle_text = clean(sdp.get("lifecycleStatus")) or "not recorded"
    ref_uid = clean(sdp.get("followsReferenceArchitecture"))
    ref = model.catalog.get(ref_uid) if ref_uid else None
    ref_name = clean(ref.get("name")) if isinstance(ref, dict) else ""
    meta = [
        f"<span>Lifecycle: <b>{E(lifecycle_text)}</b></span>",
        f"<span>Owner team: <b>{E(team or 'not recorded')}</b></span>",
    ]
    if ref_name:
        meta.append(f"<span>Reference architecture: <b>{E(ref_name)}</b></span>")
    return (
        f"<header><h1>{E(name)} Architecture</h1>"
        f'<div class="meta">{"".join(meta)}</div>'
        '<p class="lede">Generated from the DRAFT catalog. Each box, arrow and row comes from a catalog object. '
        "An object with no recorded relationship has no arrow, and nothing is inferred.</p></header>"
    )


def counts_html(model: Model, dm: DiagramModel) -> str:
    placed = len(model.placement)
    unplaced = len([u for u in model.scope if u in model.catalog and u not in model.placement])
    retired = sum(1 for u in model.scope if u in model.catalog and lifecycle(model.catalog[u]) == "retired")
    seen = {n.uid for n in dm.nodes + dm.deployment_nodes if not n.external}  # drawn in either view (D43)
    seen |= {c.uid for c in dm.containers if c.drawn and c.uid}
    seen |= {st.uid for c in dm.containers for lane in c.lanes for st in lane.stores if st.uid}
    drawn = len(seen & model.scope)
    spans = [
        f"<span><b>{drawn}</b> objects drawn</span>",
        f"<span><b>{placed}</b> placed in a service group</span>",
        f"<span><b>{unplaced}</b> in scope but not placed</span>",
        f"<span><b>{retired}</b> retired</span>",
        f"<span><b>{len(model.relationship_rows)}</b> recorded relationships</span>",
    ]
    if model.placed_only:  # D2: the undrawn count is always reported under --placed-only
        spans.append(
            f"<span>{model.undrawn_relationship_count} recorded relationships lead outside the placed set and are not drawn</span>"
        )
    return '<div class="counts">' + "".join(spans) + "</div>"


def inventory_rows(model: Model) -> str:
    def key(uid: str) -> tuple[int, str, int, str, str]:
        placed = model.placement.get(uid)
        return (0 if placed else 1, placed["group"] if placed else "", 1 if lifecycle(model.catalog[uid]) == "retired" else 0, model.name(uid).lower(), uid)

    rows = []
    for uid in sorted((u for u in model.scope if u in model.catalog), key=key):
        obj = model.catalog[uid]
        placed = model.placement.get(uid)
        where = (
            f"{placed['group']} ({placed['target'] or 'deployment target not recorded'})"
            if placed
            else "Not placed in a service group"
        )
        runs_on = obj.get("runsOn")
        host = model.name(str(runs_on)) if runs_on and str(runs_on) in model.catalog else str(runs_on or "")
        tech = technology_line(model.catalog, obj)  # D11: the same rule as the box technology line
        life = lifecycle(obj)
        pill = {"retired": "ret", "deprecated": "dep"}.get(life, "")
        rows.append(
            f'<tr data-life="{E(life)}" data-placed="{int(bool(placed))}"><td class="nm">{E(model.name(uid))}</td>'
            f'<td>{E(str(obj.get("classification") or str(obj.get("type", "")).replace("_", " ")))}</td>'
            f'<td><span class="pill {pill}">{E(life)}</span></td><td>{E(where)}</td><td>{E(host)}</td><td>{E(tech)}</td>'
            f'<td class="ds">{E(clean(obj.get("description")))}</td><td class="src">{E(uid)}</td></tr>'
        )
    return "".join(rows)


def relationship_rows(model: Model) -> str:
    out = []
    for row in model.relationship_rows:
        out.append(
            f'<tr><td>{E(row["from"])}</td><td class="lbl">{E(row["label"] or "no label recorded")}</td>'
            f'<td>{E(row["to"])}</td><td>{E(row["source"])}</td><td class="ds">{E(row["description"])}</td></tr>'
        )
    return "".join(out)


def conflicts_html(model: Model) -> str:
    rows = []
    for conflict in model.conflicts:
        rows.append(
            f"<tr><td>{E(clean(conflict.group))}</td><td>{E(model.name(conflict.component))}</td>"
            f"<td>{E(model.name(conflict.runs_on))}</td><td>{E(model.name(conflict.substrate))}</td></tr>"
        )
    return "".join(rows)


def facts_html(model: Model) -> str:
    items: list[tuple[str, str]] = []
    omitted = "Recorded in the pattern file; not shown on this page."
    for field in ("architectureNotes", "notes"):
        block = model.sdp.get(field)
        if isinstance(block, dict):
            for key, value in block.items():
                if isinstance(value, dict):
                    text = value.get("description") or value.get("scope") or ""
                    items.append((key, clean(text) or omitted))
                elif isinstance(value, bool):
                    items.append((key, "true" if value else "false"))
                elif isinstance(value, (str, int, float)):
                    if clean(value):
                        items.append((key, clean(value)))
                elif isinstance(value, list):
                    if value and all(isinstance(v, (str, int, float)) and not isinstance(v, bool) for v in value):
                        items.append((key, "; ".join(clean(v) for v in value if clean(v))))
                    elif value:
                        items.append((key, omitted))
    for key in ("scalingUnits", "tierVariants"):  # D10: shown as text only, no figure depends on them
        text = _text_of(model.sdp.get(key))
        if text:
            items.append((key, text))
    seen: set[str] = set()
    cards = []
    for key, value in items:
        if key in seen:
            continue
        seen.add(key)
        label = "".join(f" {c.lower()}" if c.isupper() else c for c in str(key)).strip().capitalize()
        cards.append(f'<div class="fact"><dt>{E(label)}</dt><dd>{E(value)}</dd></div>')
    return "".join(cards)


def empty_groups_html(model: Model) -> str:
    empty = [g for g in model.groups if not g["uids"]]
    if not empty:
        return ""
    names = "; ".join(
        f"{clean(g.get('name')) or 'unnamed group'} ({clean(g.get('target')) or 'deployment target not recorded'})" for g in empty
    )
    return f'<p class="cap">Service groups recorded with no objects to draw: {E(names)}.</p>'


def questions_html(model: Model) -> str:
    items = []
    for uid in sorted(model.catalog):  # D15: catalog insertion order must not reach the page
        obj = model.catalog[uid]
        if obj.get("type") != "drafting_session" and "unresolvedQuestions" not in obj:
            continue
        if obj.get("primaryObjectUid") != model.sdp.get("uid"):
            continue
        for q in obj.get("unresolvedQuestions") or []:
            if not isinstance(q, dict) or not q.get("question"):
                continue
            status = clean(q.get("status") or "open")
            answer = clean(q.get("currentBestGuess") or q.get("resolution") or q.get("answer"))
            pill = "" if status == "answered" else "open"
            items.append(
                f'<li><span class="pill {pill}">{E(status)}</span> <b>{E(clean(q.get("id")))}</b> {E(clean(q["question"]))}'
                + (f'<div class="ans">{E(answer)}</div>' if answer else "")
                + "</li>"
            )
    return "".join(items)


def figure_html(svg: str, fig_id: str) -> str:
    """The figure SVG with its element id added to the inline copy only; the standalone SVG files are unchanged."""
    return '<div class="scroll">' + svg.replace("<svg ", '<svg id="' + fig_id + '" ', 1) + "</div>"


CSS = """
:root{--bg:#f5f7fa;--fg:#1a2230;--muted:#586374;--surface:#fff;--line:#aab4c2;--zone:#eaeff5;--zone-line:#9aa6b6;--accent:#0b62c4;--amber:#a85a00;--warn:#9a3412;--hi-edge:#7c3a6b;--hi-out:#7c3a6b;--hi-in:#b45309;--hi-node:#006064;--hi-node-bg:#e0f2f1}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0e131a;--fg:#e4e9f0;--muted:#97a2b3;--surface:#18202b;--line:#4a586b;--zone:#121923;--zone-line:#3c485a;--accent:#5fadff;--amber:#f2a64e;--warn:#fb923c;--hi-edge:#c58fd3;--hi-out:#c58fd3;--hi-in:#f0a24a;--hi-node:#3fc1b4;--hi-node-bg:#103a38;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0e131a;--fg:#e4e9f0;--muted:#97a2b3;--surface:#18202b;--line:#4a586b;--zone:#121923;--zone-line:#3c485a;--accent:#5fadff;--amber:#f2a64e;--warn:#fb923c;--hi-edge:#c58fd3;--hi-out:#c58fd3;--hi-in:#f0a24a;--hi-node:#3fc1b4;--hi-node-bg:#103a38;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:28px max(16px,env(safe-area-inset-right,0px)) 56px max(16px,env(safe-area-inset-left,0px))}
.wrap{max-width:1280px;margin:0 auto;display:flex;flex-direction:column;gap:30px}
header{display:flex;flex-direction:column;gap:6px}
h1{font-size:26px;line-height:1.2;margin:0;font-weight:600}h2{font-size:17px;margin:0 0 4px;font-weight:600}
.lede,.sec>p,.cap{color:var(--muted);max-width:76ch;font-size:14px;margin:6px 0 12px}
.meta{display:flex;flex-wrap:wrap;gap:4px 22px;font-size:13.5px;color:var(--muted)}.meta b{color:var(--fg);font-weight:600}
.counts{display:flex;flex-wrap:wrap;gap:6px 22px;font-size:13.5px}.counts b{font-variant-numeric:tabular-nums}
.scroll,.tw{overflow-x:auto;border:1px solid var(--zone-line);border-radius:6px;background:var(--surface)}
svg{display:block;width:100%;min-width:760px;height:auto;color:var(--fg)}svg text{fill:currentColor;font-family:inherit}
svg.quiet .edge:not(.on){display:none}svg .edge.on .fl{display:inline}svg .edge.on .ln{stroke:var(--hi-edge);stroke-width:3}svg .edge.on text{fill:var(--hi-edge)}svg .mk{fill:context-stroke}svg .edge.on.out .ln{stroke:var(--hi-out)}svg .edge.on.out text{fill:var(--hi-out)}svg .edge.on.in .ln{stroke:var(--hi-in)}svg .edge.on.in text{fill:var(--hi-in)}.tog{display:inline-flex;align-items:center;gap:6px;font-size:13.5px;color:var(--muted);margin:0 0 10px}.tog input{margin:0}.key{display:inline-flex;gap:14px;font-size:13px;color:var(--muted);margin-left:14px}.key i{display:inline-block;width:18px;height:0;border-top:3px solid;vertical-align:middle;margin-right:5px}.key .o i{border-color:var(--hi-out)}.key .i i{border-color:var(--hi-in)}
svg .node.on .box{stroke:var(--hi-node);stroke-width:2.6;fill:var(--hi-node-bg)}svg .group.on>.grp{stroke:var(--hi-node);stroke-width:2.6}
svg [data-id]:focus{outline:none}svg [data-id]:focus>rect,svg .node.on:focus>.box,svg .group.on:focus>.grp{stroke:var(--accent);stroke-width:2.6}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--zone-line)}
th{background:var(--zone);font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);white-space:nowrap}tr:last-child td{border-bottom:0}
td.nm{font-weight:600;white-space:nowrap}td.lbl{color:var(--accent);white-space:nowrap}td.ds{min-width:320px;color:var(--muted)}td.src{font:11px ui-monospace,Menlo,monospace;color:var(--muted);white-space:nowrap}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;border:1px solid var(--zone-line);font-size:11.5px;white-space:nowrap}
.pill.ret{color:var(--muted);border-style:dashed}.pill.dep{color:var(--amber);border-color:var(--amber)}.pill.open{color:var(--warn);border-color:var(--warn)}
.tools{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:10px}.tools input,.tools select{font:inherit;font-size:13.5px;padding:7px 10px;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--fg);min-width:0}.tools input{flex:1 1 240px;max-width:360px}
dl.facts{margin:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:10px}
.fact{border:1px solid var(--zone-line);border-radius:6px;padding:10px 12px;background:var(--surface);min-width:0}.fact dt{font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);font-weight:600;margin-bottom:3px}.fact dd{margin:0;font-size:13.5px;overflow-wrap:anywhere}
ul.q{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px;max-width:90ch}ul.q li{border:1px solid var(--zone-line);border-radius:6px;padding:10px 12px;background:var(--surface);font-size:13.5px}.ans{color:var(--muted);margin-top:6px;font-size:13px}
.foot{color:var(--muted);font-size:12.5px;border-top:1px solid var(--zone-line);padding-top:12px}
"""

JS = """
(function(){
 var figs=['fig-logical','fig-deployment'].map(function(id){return document.getElementById(id)}).filter(Boolean);
 var pinned=null,hover=null;
 function uidOf(t){var el=t&&t.closest?t.closest('[data-id]'):null;return el?el.getAttribute('data-id'):null}
 var order=figs.map(function(svg){return [].slice.call(svg.querySelectorAll('[data-from]'))});
 function paint(){
  var id=pinned||hover;
  figs.forEach(function(svg,k){
   order[k].forEach(function(el){el.parentNode.appendChild(el)});
   var els=[].slice.call(svg.querySelectorAll('[data-id],[data-from]')),near={};
   if(id){near[id]=1;els.forEach(function(el){var a=el.getAttribute('data-from');if(a!==null&&(a===id||el.getAttribute('data-to')===id)){near[a]=1;near[el.getAttribute('data-to')]=1}})}
   svg.classList.toggle('focus',!!id);
   els.forEach(function(el){var a=el.getAttribute('data-from'),to=el.getAttribute('data-to');
    var on=!!id&&(a!==null?(a===id||to===id):!!near[el.getAttribute('data-id')]);
    el.classList.toggle('on',on);
    if(a!==null){el.classList.toggle('out',on&&a===id);el.classList.toggle('in',on&&a!==id&&to===id)}});
   els.forEach(function(el){if(el.hasAttribute('data-from')&&el.classList.contains('on'))el.parentNode.appendChild(el)});
  });
 }
 figs.forEach(function(svg){
  svg.classList.add('quiet');
  var tog=document.querySelector('input[data-all="'+svg.id+'"]');
  if(tog){tog.checked=false;tog.addEventListener('change',function(){svg.classList.toggle('quiet',!tog.checked)})}
  [].slice.call(svg.querySelectorAll('[data-id]')).forEach(function(el){el.setAttribute('tabindex','0')});
  svg.addEventListener('mouseover',function(e){var id=uidOf(e.target);if(id!==hover){hover=id;paint()}});
  svg.addEventListener('mouseleave',function(){hover=null;paint()});
  svg.addEventListener('focusin',function(e){hover=uidOf(e.target);paint()});
  svg.addEventListener('focusout',function(){hover=null;paint()});
  svg.addEventListener('click',function(e){var id=uidOf(e.target);pinned=id&&pinned!==id?id:null;paint()});
  svg.addEventListener('keydown',function(e){var id=uidOf(e.target);if(id&&(e.key==='Enter'||e.key===' ')){e.preventDefault();pinned=pinned===id?null:id;paint()}});
 });
 var q=document.getElementById('q'),lf=document.getElementById('lf'),pf=document.getElementById('pf'),cnt=document.getElementById('cnt');
 if(!q)return;
 var rows=[].slice.call(document.querySelectorAll('#inv tbody tr'));
 function run(){var t=q.value.toLowerCase(),l=lf.value,p=pf.value,n=0;rows.forEach(function(r){var ok=(!t||r.textContent.toLowerCase().indexOf(t)>-1)&&(!l||r.dataset.life===l)&&(!p||r.dataset.placed===p);r.hidden=!ok;if(ok)n++});cnt.textContent=n+' of '+rows.length+' shown'}
 q.addEventListener('input',run);lf.addEventListener('change',run);pf.addEventListener('change',run);run();
})();
"""


# --------------------------------------------------------------------------- editable local render (D48)
# The pure part of the edit script. ``draftOrdinals`` is the JavaScript twin of ``layout_ordinals`` and ``draftLayoutYaml``
# of ``export_layout_document`` (tests run both on one fixture). It touches no DOM, so node can load it alone.
EDIT_JS_PURE = """
function draftOrdinals(lists){
 var out=[];
 lists.forEach(function(list){list.forEach(function(ref,i){out.push({ref:ref,position:i+1})})});
 return out;
}
function draftLayoutYaml(meta,logical,deployment){
 function entries(lists){var rows=draftOrdinals(lists);if(!rows.length)return ' []';
  return '\\n'+rows.map(function(r){return '  - ref: '+JSON.stringify(r.ref)+'\\n    position: '+r.position}).join('\\n')}
 return ['schemaVersion: "1.0"','uid: '+(meta.uid?JSON.stringify(meta.uid):'NEW'),'type: diagram_layout','name: '+JSON.stringify(meta.name),
  'pattern: '+JSON.stringify(meta.pattern),'catalogStatus: complete','logical:'+entries(logical),'deployment:'+entries(deployment)].join('\\n')+'\\n';
}
"""

EDIT_JS_DOM = """
(function(){
 var panel=document.getElementById('edit-panel');if(!panel)return;
 var meta={uid:panel.getAttribute('data-uid'),pattern:panel.getAttribute('data-pattern'),name:panel.getAttribute('data-name')};
 var state={},slots={},base={},drag=null,justDragged=false;
 function ctrOf(el){return el.getAttribute('data-ctr')}
 ['fig-logical','fig-deployment'].forEach(function(fid){
  var svg=document.getElementById(fid);if(!svg)return;
  [].slice.call(svg.querySelectorAll('[data-ctr]')).forEach(function(el){
   var id=ctrOf(el);(state[id]=state[id]||[]).push(el);
  });
 });
 Object.keys(state).forEach(function(id){
  state[id].sort(function(a,b){return +a.getAttribute('data-ord')-+b.getAttribute('data-ord')});
  state[id].forEach(function(el){var b=el.getBBox();base[key(el)]={x:b.x,y:b.y}});
  slots[id]=state[id].map(function(el){return base[key(el)]});
 });
 function key(el){return el.getAttribute('data-id')+'|'+ctrOf(el)+'|'+el.getAttribute('data-ord')}
 function movable(id){return state[id].filter(function(el){return !el.hasAttribute('data-fixed')})}
 function place(id){
  var mv=movable(id);
  var origin=mv.map(function(el){return +el.getAttribute('data-ord')}).sort(function(a,b){return a-b});
  mv.forEach(function(el,i){var own=base[key(el)],slot=slots[id][origin[i]-1];
   var dx=slot.x-own.x,dy=slot.y-own.y;
   if(dx||dy)el.setAttribute('transform','translate('+dx+' '+dy+')');else el.removeAttribute('transform')});
 }
 function sortDom(id){
  var list=state[id],parts=list.slice().sort(function(a,b){return a.compareDocumentPosition(b)&4?-1:1});
  var marks=parts.map(function(el){var m=document.createComment('');el.parentNode.insertBefore(m,el);return m});
  list.forEach(function(el,i){marks[i].parentNode.insertBefore(el,marks[i])});
  marks.forEach(function(m){m.parentNode.removeChild(m)});
 }
 function moveTo(el,index){
  var id=ctrOf(el),mv=movable(id),from=mv.indexOf(el);
  if(from<0)return false;
  index=Math.max(0,Math.min(mv.length-1,index));
  if(index===from)return false;
  mv.splice(from,1);mv.splice(index,0,el);
  var fixed=state[id].filter(function(x){return x.hasAttribute('data-fixed')});
  state[id]=mv.concat(fixed);
  place(id);sortDom(id);say(label(el)+' moved to position '+(index+1)+' of '+state[id].length+'.');
  return true;
 }
 function label(el){var t=el.querySelector?el.querySelector('title'):null;return t&&t.textContent?t.textContent:el.getAttribute('data-id')}
 function say(msg){var n=document.getElementById('edit-note');if(n)n.textContent=msg}
 function scaleOf(svg){var m=svg.getScreenCTM();return m?m.a:1}
 function onDown(e){
  if(drag)return;
  var el=e.target.closest?e.target.closest('[data-ctr]'):null;
  if(!el||el.hasAttribute('data-fixed')||(e.button!==undefined&&e.button!==0))return;
  var svg=el.ownerSVGElement,id=ctrOf(el),mv=movable(id);
  var tr=(el.getAttribute('transform')||'').match(/translate\\(([-+\\d.eE]+) ([-+\\d.eE]+)\\)/);
  var s=slots[id],xs=s.map(function(r){return r.x}),ys=s.map(function(r){return r.y});
  drag={pid:e.pointerId,el:el,svg:svg,id:id,sx:e.clientX,sy:e.clientY,ox:tr?+tr[1]:0,oy:tr?+tr[2]:0,k:scaleOf(svg),moved:false,
   box:{x0:Math.min.apply(null,xs),x1:Math.max.apply(null,xs),y0:Math.min.apply(null,ys),y1:Math.max.apply(null,ys)},own:base[key(el)]};
  svg.classList.add('dragging');
  try{el.setPointerCapture(e.pointerId)}catch(x){}
 }
 function onMove(e){
  if(!drag||e.pointerId!==drag.pid)return;
  var dx=(e.clientX-drag.sx)/drag.k,dy=(e.clientY-drag.sy)/drag.k;
  if(!drag.moved&&Math.abs(dx)+Math.abs(dy)<4)return;
  drag.moved=true;
  var nx=drag.own.x+drag.ox+dx,ny=drag.own.y+drag.oy+dy;
  nx=Math.max(drag.box.x0,Math.min(drag.box.x1,nx));ny=Math.max(drag.box.y0,Math.min(drag.box.y1,ny));
  drag.el.setAttribute('transform','translate('+(nx-drag.own.x)+' '+(ny-drag.own.y)+')');
  drag.cx=nx;drag.cy=ny;
 }
 function onUp(e){
  if(!drag||(e&&e.pointerId!==undefined&&e.pointerId!==drag.pid))return;
  var d=drag;drag=null;d.svg.classList.remove('dragging');
  if(!d.moved)return;
  justDragged=true;setTimeout(function(){justDragged=false},0);
  var mv=movable(d.id),origin=mv.map(function(el){return +el.getAttribute('data-ord')}).sort(function(a,b){return a-b});
  var best=0,bd=1e18;
  origin.forEach(function(o,i){var r=slots[d.id][o-1],dist=Math.pow(r.x-d.cx,2)+Math.pow(r.y-d.cy,2);if(dist<bd){bd=dist;best=i}});
  var from=mv.indexOf(d.el);
  if(best===from){place(d.id)}else{moveTo(d.el,best)}
 }
 function onKey(e){
  var el=e.target.closest?e.target.closest('[data-ctr]'):null;
  if(!el||!e.altKey)return;
  var back=e.key==='ArrowLeft'||e.key==='ArrowUp',fwd=e.key==='ArrowRight'||e.key==='ArrowDown';
  if(!back&&!fwd)return;
  e.preventDefault();
  if(el.hasAttribute('data-fixed')){say(label(el)+' is fixed and cannot be moved.');return}
  var mv=movable(ctrOf(el));
  if(!moveTo(el,mv.indexOf(el)+(fwd?1:-1)))say(label(el)+' is already at the '+(fwd?'end':'start')+' of its container and cannot move further.');
  el.focus();
 }
 ['fig-logical','fig-deployment'].forEach(function(fid){
  var svg=document.getElementById(fid);if(!svg)return;
  svg.classList.add('editing');
  svg.addEventListener('pointerdown',onDown);svg.addEventListener('pointermove',onMove);
  svg.addEventListener('pointerup',onUp);svg.addEventListener('pointercancel',onUp);svg.addEventListener('lostpointercapture',onUp);
  svg.addEventListener('keydown',onKey);
  svg.addEventListener('click',function(e){if(justDragged){e.stopPropagation();e.preventDefault()}},true);
 });
 function names(prefix){return Object.keys(state).filter(function(id){return id.charAt(0)===prefix}).sort(function(a,b){return +a.slice(1)-+b.slice(1)})}
 function lists(prefix){return names(prefix).map(function(id){return state[id].map(function(el){return el.getAttribute('data-id')})})}
 var out=document.getElementById('layout-out'),note=document.getElementById('edit-note');
 document.getElementById('export-layout').addEventListener('click',function(){
  var text=draftLayoutYaml(meta,lists('l'),lists('d'));
  out.value=text;out.focus();out.select();
  var done=function(msg){note.textContent=msg};
  try{
   if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(text).then(function(){done('Layout copied to the clipboard and shown below.')},function(){done('Layout shown below; copy it from the box.')})}
   else{done('Layout shown below; copy it from the box.')}
  }catch(x){done('Layout shown below; copy it from the box.')}
 });
})();
"""

EDIT_CSS = """
.edit{border:1px solid var(--zone-line);border-radius:6px;background:var(--surface);padding:12px 14px}
.edit button{font:inherit;font-size:13.5px;padding:6px 12px;border:1px solid var(--line);border-radius:6px;background:var(--zone);color:var(--fg);cursor:pointer}
.edit textarea{display:block;width:100%;min-height:12em;margin-top:10px;font:12px ui-monospace,Menlo,monospace;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:8px}
svg.dragging{user-select:none;-webkit-user-select:none}
svg.editing [data-ctr]:not([data-fixed]){cursor:grab;touch-action:none}
"""


def layout_ordinals(containers: list[list[str]]) -> list[dict[str, Any]]:
    """D48: one ``{ref, position}`` entry per drawn node, positions 1-based in drawn order within each container.

    The Export layout control computes the same thing in JavaScript (``draftOrdinals``); tests run both on one fixture."""
    return [{"ref": uid, "position": number} for uids in containers for number, uid in enumerate(uids, start=1)]


def export_layout_document(uid: str, pattern_uid: str, pattern_name: str, logical: list[list[str]], deployment: list[list[str]]) -> dict[str, Any]:
    """D48: the complete diagram_layout object the Export layout control serialises. ``uid`` is ``NEW`` when no layout was loaded."""
    return {
        "schemaVersion": "1.0",
        "uid": uid or "NEW",
        "type": "diagram_layout",
        "name": f"{pattern_name} diagram layout",
        "pattern": pattern_uid,
        "catalogStatus": "complete",
        "logical": layout_ordinals(logical),
        "deployment": layout_ordinals(deployment),
    }


def annotate_containers(svg: str, containers: list[list[str]], prefix: str, fixed: set[str] | None = None) -> str:
    """D48: add ``data-ctr`` (container id, prefix plus index in drawn order) and ``data-ord`` (1-based place in it) to each drawn node.

    The k-th ``data-id`` occurrence of a uid in the figure pairs with the k-th place that uid has in ``containers``, which
    follow the same document order. ``fixed`` uids (data store containers) are marked ``data-fixed`` and are not draggable."""
    places: dict[str, list[tuple[str, int]]] = {}
    for index, uids in enumerate(containers):
        for number, uid in enumerate(uids, start=1):
            places.setdefault(xml_text(uid), []).append((f"{prefix}{index}", number))
    taken: dict[str, int] = {}

    def attach(match: re.Match) -> str:
        uid = match.group(1)
        k = taken.get(uid, 0)
        found = places.get(uid, [])
        if k >= len(found):
            return match.group(0)
        taken[uid] = k + 1
        ctr, number = found[k]
        extra = ' data-fixed="1"' if fixed and uid in fixed else ""
        return f'{match.group(0)} data-ctr="{ctr}" data-ord="{number}"{extra}'

    return re.sub(r'data-id="([^"]*)"', attach, svg)


def _deployment_store_uids(dm: DiagramModel) -> set[str]:
    """Escaped uids of the data store containers of the deployment figure; they keep their place in the layout but are not draggable."""
    return {xml_text(st.uid) for _t, groups in _deployment_outline(dm) for g in groups for lane in g.lanes for st in lane.stores if st.uid}


def edit_panel_html(model: Model) -> str:
    sdp_uid = str(model.sdp.get("uid", ""))
    name = clean(model.sdp.get("name")) or sdp_uid
    return (
        f'<section class="sec edit" id="edit-panel" data-uid="{E(model.layout_uid)}" data-pattern="{E(sdp_uid)}" data-name="{E(name)} diagram layout">'
        "<h2>Edit box order</h2>"
        "<p>Drag a box, or focus it and press Alt with an arrow key, to move it within its own band, zone lane or data store container. "
        "Connections are not redrawn while you edit. Export layout writes the order shown as a diagram_layout document; "
        "nothing is stored, and reloading returns to the catalog order. Save the text to a file and run "
        "<code>generate_diagram.py --sdp NAME --write-layout --layout-from FILE</code>.</p>"
        '<button type="button" id="export-layout">Export layout</button> <span class="cap">Keyboard: focus a box and press Alt with an arrow key to move it one place.</span> <span id="edit-note" role="status"></span>'
        '<textarea id="layout-out" aria-label="Exported diagram layout" spellcheck="false"></textarea></section>'
    )


def render_page(model: Model, dm: DiagramModel, back_link: str | None = None, editable: bool = False) -> str:
    """The D19 page: header, counts, the two figures, relationships, conflicts, characteristics, questions, inventory, footer.

    ``back_link`` (D46) is a relative href that adds a ``Back to catalog`` link to the footer; it is set only by the browser generator.
    ``editable`` (D48) adds the edit script, the Export layout panel and container attributes on the boxes; only ``--editable`` sets it."""
    sdp = model.sdp
    marks: dict[str, list[list[str]]] = {}
    if editable:
        marks = drawn_order(model)
    title = clean(sdp.get("name")) or "Deployment pattern"
    logical_empty = not dm.nodes
    logical_body = (
        (
            "<p>This pattern places no component or data component, so there is nothing to draw here; its infrastructure is in the deployment diagram.</p>"
            if model.placement
            else "<p>No object is placed in a service group, so there is nothing to draw.</p>"
        )
        if logical_empty
        else figure_html(annotate_containers(render_logical_svg(dm), marks["logical"], "l") if editable else render_logical_svg(dm), FIGURE_IDS[0])
    )
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
        f"<title>{E(title)} Architecture</title><style>{CSS}{EDIT_CSS if editable else ''}</style></head><body><div class=\"wrap\">",
        header_html(model),
        counts_html(model, dm),
        edit_panel_html(model) if editable else "",
        f'<section class="sec" id="logical"><h2>{E(LOGICAL_TITLE)}</h2>'
        '<label class="tog"><input type="checkbox" data-all="fig-logical"> Show all connections</label><span class="key"><span class="o"><i></i>calls it makes</span><span class="i"><i></i>calls it receives</span></span>'
        "<p>Components and data components in bands by diagram tier; placed infrastructure (network, runtime, host, AI gateway and data store services) is drawn in the deployment diagram only. Dependencies that this pattern does not place sit in the right-hand lane, captioned with the pattern that places them. "
        "Connections are hidden until you hover over, focus or click a box; then only that box's own connections appear, purple for calls it makes and orange for calls it receives. "
        "Click to pin. A dashed box has a derived tier.</p>"
        + logical_body
        + "</section>",
        f'<section class="sec" id="deployment"><h2>{E(DEPLOYMENT_TITLE)}</h2>'
        '<label class="tog"><input type="checkbox" data-all="fig-deployment"> Show all connections</label><span class="key"><span class="o"><i></i>calls it makes</span><span class="i"><i></i>calls it receives</span></span>'
        "<p>Deployment targets hold service groups, each drawn as a container around its boxes, including the infrastructure the logical diagram leaves out. Data components sit inside a container named for the data store service they run on. Connections are hidden until you hover over, focus or click a box, and pinning an object in one figure highlights it in the other.</p>"
        + figure_html(
            annotate_containers(render_deployment_svg(dm), marks["deployment"], "d", _deployment_store_uids(dm)) if editable else render_deployment_svg(dm),
            FIGURE_IDS[1],
        )
        + empty_groups_html(model)
        + "</section>",
    ]
    if model.relationship_rows:
        parts.append(
            '<section class="sec"><h2>Recorded relationships</h2><div class="tw"><table><thead><tr>'
            "<th>From</th><th>Relationship</th><th>To</th><th>Source</th><th>Description</th></tr></thead><tbody>"
            f"{relationship_rows(model)}</tbody></table></div></section>"
        )
    else:
        parts.append('<section class="sec"><h2>Recorded relationships</h2><p>No relationship objects connect these objects.</p></section>')
    if model.conflicts:
        parts.append(
            '<section class="sec"><h2>Recorded conflicts</h2><p>A placed component records a runsOn that differs from its service group substrate. '
            "Nothing is resolved here; both records are shown as recorded.</p><div class=\"tw\"><table><thead><tr>"
            "<th>Service group</th><th>Component</th><th>Component runs on</th><th>Group substrate</th></tr></thead>"
            f"<tbody>{conflicts_html(model)}</tbody></table></div></section>"
        )
    facts = facts_html(model)
    parts.append(
        '<section class="sec"><h2>Recorded characteristics</h2><p>Quoted from the deployment pattern.</p>'
        + (f'<dl class="facts">{facts}</dl>' if facts else "<p>No characteristics are recorded for this pattern.</p>")
        + "</section>"
    )
    questions = questions_html(model)
    parts.append(
        '<section class="sec"><h2>Open questions on record</h2>'
        + (f'<ul class="q">{questions}</ul>' if questions else "<p>No open questions are recorded for this pattern.</p>")
        + "</section>"
    )
    parts.append(
        '<section class="sec"><h2>Object inventory</h2><p>Every in-scope object with its catalog fields as recorded. '
        "Placed objects are listed first.</p>"
        '<div class="tools"><input id="q" type="search" placeholder="Filter by name, host, language or description" aria-label="Filter objects">'
        '<select id="lf" aria-label="Lifecycle filter"><option value="">All lifecycles</option><option value="preferred">preferred</option>'
        '<option value="candidate">candidate</option><option value="existing-only">existing-only</option>'
        '<option value="retired">retired</option><option value="deprecated">deprecated</option></select>'
        '<select id="pf" aria-label="Placement filter"><option value="">Placed and not placed</option><option value="1">Placed</option><option value="0">Not placed</option></select>'
        '<span id="cnt" style="align-self:center;color:var(--muted);font-size:13px"></span></div>'
        '<div class="tw"><table id="inv"><thead><tr><th>Object</th><th>Class</th><th>Lifecycle</th><th>Service group (target)</th>'
        "<th>Runs on</th><th>Language / runtime</th><th>Description</th><th>UID</th></tr></thead>"
        f"<tbody>{inventory_rows(model)}</tbody></table></div></section>"
    )
    parts.append(
        f'<footer class="foot">DRAFT framework version {E(framework_version())}. '
        "Generated from the catalog; the same catalog always produces the same page."
        + (f' <a href="{E(back_link)}">Back to catalog</a>' if back_link else "")
        + "</footer>"
    )
    scripts = f"<script>{JS}</script>" + (f"<script>{EDIT_JS_PURE}{EDIT_JS_DOM}</script>" if editable else "")
    parts.append(f"</div>{scripts}</body></html>")
    return "".join(parts)


# --------------------------------------------------------------------------- stubs
def diagram_of(model: Model) -> DiagramModel:
    """The two-view model of one resolved pattern: logical nodes, deployment nodes, edges, containers, warnings."""
    return DiagramModel(
        sdp_uid=str(model.sdp.get("uid", "")),
        nodes=model.nodes_for_view("logical"),
        deployment_nodes=model.nodes_for_view("deployment"),
        edges=list(model.edges),
        containers=list(model.containers),
        warnings=list(model.warnings),
        logical_positions=dict(model.layout_positions["logical"]),
        deployment_positions=dict(model.layout_positions["deployment"]),
    )


def build_diagram_model(catalog: dict[str, dict[str, Any]], sdp: dict[str, Any], placed_only: bool) -> DiagramModel:
    """The two-view model for one pattern, built from a catalog dict."""
    return diagram_of(Model(catalog, sdp, placed_only))


# --------------------------------------------------------------------------- logical view
GRID = 10  # every node x and y is a multiple of this (D14)
LOGICAL_COLUMNS = 4  # a band wraps to a new row after this many boxes (D4)
LOGICAL_SWEEPS = 4  # barycentre sweeps downward, then the same number upward (D14)
LOGICAL_BOX_W = 200
LOGICAL_BOX_H = 60
LOGICAL_COL_GAP = 30
LOGICAL_ROW_GAP = 30
LOGICAL_BAND_GAP = 40
LOGICAL_BAND_PAD = 10
LOGICAL_LABEL_W = 110
LOGICAL_LANE_GAP = 90
LOGICAL_LANE_HEAD = 40
LOGICAL_MARGIN = 20
LOGICAL_TITLE = "Logical application diagram"
BAND_ORDER = ("presentation", "application", "data", "utility")  # D4, top to bottom
GENERATOR_NAME = "generate_diagram"

_XML_INVALID = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def xml_text(value: Any) -> str:
    """Escape a catalog string for SVG text or an attribute value (markup and quotes)."""
    return html.escape(_XML_INVALID.sub("", str(value)), quote=True)


def _band_rank(node: DiagramNode) -> int:
    """Index in BAND_ORDER; externals have no band and sort after every band (D5)."""
    if node.external:
        return len(BAND_ORDER)
    return BAND_ORDER.index(node.band) if node.band in BAND_ORDER else BAND_ORDER.index("application")


def barycentre_order(layers: list[list[str]], pairs: list[tuple[str, str]], columns: int = LOGICAL_COLUMNS) -> list[list[str]]:
    """D14: order each layer by the mean column of its neighbours in other layers.

    Layers start sorted by uid; LOGICAL_SWEEPS downward then LOGICAL_SWEEPS upward sweeps reorder one
    layer at a time. A node with no neighbour on the swept side keeps its current column. Ties break
    by uid, plain code-point comparison. Nothing depends on dict or set iteration order.
    """
    order = [sorted(layer) for layer in layers]
    layer_of = {uid: i for i, layer in enumerate(order) for uid in layer}
    neighbours: dict[str, list[str]] = {uid: [] for uid in layer_of}
    for a, b in pairs:
        if a in layer_of and b in layer_of and a != b and layer_of[a] != layer_of[b]:
            neighbours[a].append(b)
            neighbours[b].append(a)
    column = {uid: i % columns for layer in order for i, uid in enumerate(layer)}

    def reorder(index: int, side: range) -> None:
        def key(uid: str) -> tuple[Fraction, str]:
            cols = [column[v] for v in neighbours[uid] if layer_of[v] in side]
            return (Fraction(sum(cols), len(cols)) if cols else Fraction(column[uid]), uid)

        order[index] = sorted(order[index], key=key)
        for i, uid in enumerate(order[index]):
            column[uid] = i % columns

    count = len(order)
    for _ in range(LOGICAL_SWEEPS):
        for index in range(1, count):
            reorder(index, range(0, index))
    for _ in range(LOGICAL_SWEEPS):
        for index in range(count - 2, -1, -1):
            reorder(index, range(index + 1, count))
    return order


def apply_positions(order: list[str], positions: dict[str, int]) -> list[str]:
    """D39: positioned uids first, by (position, uid); the rest follow in their given order."""
    placed = sorted((u for u in order if u in positions), key=lambda u: (positions[u], u))
    return placed + [u for u in order if u not in positions]


def _fit_lines(text: str, width: int, limit: int) -> list[str]:
    lines = wrap(clean(text), width)
    if len(lines) > limit:
        lines = lines[:limit]
        lines[-1] += "..."
    return [line if len(line) <= width + 3 else line[: width - 1] + "..." for line in lines]


TRACK_PITCH = 5  # D35: distance between two tracks of a row gap, gutter, band or channel, in both views
ATTACH_DX = 20  # D36: a box's edges leave its bottom at centre + ATTACH_DX and enter its top at centre - ATTACH_DX
LOGICAL_TRACK_PAD = 10  # D35: free space between a gap's or gutter's outer tracks and its boxes
LOGICAL_LANE_SPACE = 50  # minimum free space between the main area and the outside lane (the lane gutter)
GUTTER_EXACT = 7  # a gutter with at most this many tracks gets the crossing-minimal track order
LOGICAL_LANE_SHIFT = 2  # outside-lane tracks sit this far off the main TRACK_PITCH lattice, so the two never share a y


def _ceil_grid(value: int) -> int:
    return -(-value // GRID) * GRID


def _track_space(tracks: int, minimum: int) -> int:
    """D35: a gap or gutter is its default size until its tracks need more: tracks * pitch + 2 * pad, on the grid."""
    return max(minimum, _ceil_grid(tracks * TRACK_PITCH + 2 * LOGICAL_TRACK_PAD)) if tracks else minimum


def _track_at(start: int, size: int, tracks: int, track: int) -> int:
    """Coordinate of one track in a space: the tracks are centred, on a TRACK_PITCH lattice from start."""
    return start + (size - TRACK_PITCH * (tracks - 1)) // (2 * TRACK_PITCH) * TRACK_PITCH + TRACK_PITCH * track


@dataclass
class _Run:
    """One horizontal or vertical run of a bundle of edges (D35, D36) and the uids its edges touch."""

    key: tuple
    lo: int
    hi: int
    uids: set
    first: int  # smallest edge index in the bundle; the left-edge tie-break
    track: int = 0
    gap: Any = None  # the row gap of a horizontal run in the logical view
    x: int = 0  # attachment x of a row-gap run's box
    parts: list = field(default_factory=list)  # (lo, hi, endpoint uids) of each edge's own stretch of the run


def _left_edge(runs: list) -> int:
    """D35: left-edge track assignment. Runs sorted by start coordinate, then edge order, each take the lowest
    track that holds no co-visible run (one sharing an endpoint uid) overlapping its span. Returns the track count."""
    tracks: list[list[_Run]] = []
    for run in sorted(runs, key=lambda r: (r.lo, r.first, r.key)):
        k = 0
        while k < len(tracks) and any(run.uids & o.uids and run.lo <= o.hi and o.lo <= run.hi for o in tracks[k]):
            k += 1
        if k == len(tracks):
            tracks.append([])
        tracks[k].append(run)
        run.track = k
    return len(tracks)


@dataclass
class LogicalLayout:
    pos: dict[str, tuple[int, int]] = field(default_factory=dict)  # uid -> top-left, multiples of GRID
    bands: list[tuple[str, int, int, int]] = field(default_factory=list)  # band, y, height, width
    lane: tuple[int, int, int, int] | None = None  # x, y, width, height of the outside lane
    order: list[list[str]] = field(default_factory=list)  # uid order of each drawn band
    band_names: list[str] = field(default_factory=list)  # band of each entry in order
    lane_order: list[str] = field(default_factory=list)
    gutters: list[int] = field(default_factory=list)  # x of the centre of each vertical channel between box columns
    lane_gutter: int | None = None  # x of the centre of the vertical channel left of the outside lane
    width: int = 0
    height: int = 0
    rows: list[list[str]] = field(default_factory=list)  # main rows top to bottom, across bands
    row_of: dict[str, tuple[str, int]] = field(default_factory=dict)  # uid -> ("m", row) or ("l", lane row)
    gaps: dict[tuple[str, int], tuple[int, int]] = field(default_factory=dict)  # gap (stack, k) above row k -> top, size
    gap_tracks: dict[tuple[str, int], int] = field(default_factory=dict)
    spaces: list[tuple[int, int]] = field(default_factory=list)  # left, width of each gutter; the lane gutter is last
    space_tracks: list[int] = field(default_factory=list)
    plan: dict[int, tuple] = field(default_factory=dict)  # edge index -> ("direct",), ("gutter", j) or ("lane",)
    halves: dict[int, tuple] = field(default_factory=dict)  # edge index -> keys of its out-run and in-run (None if direct)
    runs: dict[tuple, _Run] = field(default_factory=dict)  # bundle runs by key; see _plan_logical_tracks
    gap_bands: dict[tuple[str, int], tuple[int, int, int]] = field(default_factory=dict)  # D37: px of lb-s band, lb-t band, loop rise
    label_rows: dict[int, int] = field(default_factory=dict)  # edge index -> index among its same-ordered-pair siblings
    gap_tech: set = field(default_factory=set)  # D37: gaps where a labelled edge records a technology (two-line label rows)


def _place_logical(layout: LogicalLayout, outer: bool) -> None:
    """Positions from the order and the track counts (D35): every gap and gutter is as large as its tracks need."""
    gap_size = layout.gap_tracks.get

    def room(gap: tuple, minimum: int) -> int:
        """A gap's size: its tracks' space plus the label bands and the loop rise it reserves (D37)."""
        return _ceil_grid(_track_space(gap_size(gap, 0), minimum) + sum(layout.gap_bands.get(gap, (0, 0, 0))))  # D14

    n_cols = len(layout.space_tracks) - 2
    # spaces[0 .. n_cols] are the gutters left of each column and right of the last; the lane gutter comes last.
    layout.spaces = []
    columns: list[int] = []
    x = LOGICAL_MARGIN + LOGICAL_LABEL_W - 10
    for j in range(n_cols + 1):
        width = _track_space(layout.space_tracks[j], LOGICAL_COL_GAP)
        layout.spaces.append((x, width))
        x += width
        if j < n_cols:
            columns.append(x)
            x += LOGICAL_BOX_W
    band_right = x
    layout.spaces.append((x, _track_space(layout.space_tracks[-1], LOGICAL_LANE_SPACE)))
    layout.gutters = [left + width // 2 for left, width in layout.spaces[:-1]]
    layout.lane_gutter = layout.spaces[-1][0] + layout.spaces[-1][1] // 2
    layout.pos = {}
    layout.bands = []
    layout.gaps = {}
    count = len(layout.rows)
    y = LOGICAL_MARGIN
    r = 0
    for b, (band, layer) in enumerate(zip(layout.band_names, layout.order)):
        band_rows = -(-len(layer) // LOGICAL_COLUMNS)
        top = y
        pad = room(("m", 0), LOGICAL_BAND_PAD) if b == 0 else LOGICAL_BAND_PAD
        if b == 0:
            layout.gaps[("m", 0)] = (top, pad)
        y += pad
        for k in range(band_rows):
            for col, uid in enumerate(layout.rows[r]):
                layout.pos[uid] = (columns[col], y)
            y += LOGICAL_BOX_H
            r += 1
            if k < band_rows - 1:
                size = room(("m", r), LOGICAL_ROW_GAP)
                layout.gaps[("m", r)] = (y, size)
                y += size
        last = b == len(layout.order) - 1
        pad = room(("m", count), LOGICAL_BAND_PAD) if last else LOGICAL_BAND_PAD
        if last:
            layout.gaps[("m", count)] = (y, pad)
        y += pad
        layout.bands.append((band, top, y - top, band_right - LOGICAL_MARGIN))
        if not last:
            size = room(("m", r), LOGICAL_BAND_GAP)
            layout.gaps[("m", r)] = (y, size)  # an inter-band gap keeps its tracks between the two band rectangles
            y += size
    bottom = y if layout.bands else LOGICAL_MARGIN
    right = band_right
    layout.lane = None
    if outer:
        lane_x = layout.spaces[-1][0] + layout.spaces[-1][1] + LOGICAL_BAND_PAD
        top = LOGICAL_MARGIN
        y = top + LOGICAL_LANE_HEAD - LOGICAL_BAND_PAD  # the lane caption sits above the first gap
        for i, uid in enumerate(layout.lane_order):
            size = room(("l", i), LOGICAL_BAND_PAD if i == 0 else LOGICAL_ROW_GAP)
            layout.gaps[("l", i)] = (y, size)
            y += size
            layout.pos[uid] = (lane_x, y)
            y += LOGICAL_BOX_H
        size = room(("l", len(layout.lane_order)), LOGICAL_BAND_PAD)
        layout.gaps[("l", len(layout.lane_order))] = (y, size)
        y += size
        layout.lane = (lane_x - LOGICAL_BAND_PAD, top, LOGICAL_BOX_W + 2 * LOGICAL_BAND_PAD, y - top)
        right = lane_x + LOGICAL_BOX_W + LOGICAL_BAND_PAD
        bottom = max(bottom, y)
    layout.width = right + LOGICAL_MARGIN
    layout.height = bottom + LOGICAL_MARGIN


def layout_logical(model: DiagramModel) -> LogicalLayout:
    """Band rows top to bottom (D4), barycentre order (D14), outside lane at the right edge (D5).

    Gap and gutter sizes come from the edge tracks they carry (D35), so placing and routing run in two passes
    (see _plan_logical_tracks): the order and the lane order come from a layout with no tracks, row-gap tracks are
    assigned on that layout's x order, the rows are placed, gutter tracks are assigned on the placed y, and the
    columns are placed. Neither pass changes the order of anything, so the result is a pure function of the model.
    """
    main = [n for n in model.nodes if not n.outside]
    outer = [n for n in model.nodes if n.outside]
    known = {n.uid for n in model.nodes}
    pairs = [(e.source, e.target) for e in model.edges if e.source in known and e.target in known and e.source != e.target]
    layers: list[list[str]] = []
    names: list[str] = []
    for band in BAND_ORDER:
        uids = [n.uid for n in main if (n.band if n.band in BAND_ORDER else "application") == band]
        if uids:
            layers.append(uids)
            names.append(band)
    layout = LogicalLayout()
    layout.order = [apply_positions(layer, model.logical_positions) for layer in barycentre_order(layers, pairs)]
    layout.band_names = names
    for layer in layout.order:
        for start in range(0, len(layer), LOGICAL_COLUMNS):
            for uid in layer[start : start + LOGICAL_COLUMNS]:
                layout.row_of[uid] = ("m", len(layout.rows))
            layout.rows.append(layer[start : start + LOGICAL_COLUMNS])
    used = min(LOGICAL_COLUMNS, max((len(layer) for layer in layout.order), default=1))
    layout.space_tracks = [0] * (used + 2)  # used + 1 gutters, then the lane gutter
    _place_logical(layout, False)
    if outer:
        centre_y = {uid: pos[1] + LOGICAL_BOX_H // 2 for uid, pos in layout.pos.items()}
        near: dict[str, list[int]] = {n.uid: [] for n in outer}
        for a, b in pairs:
            for lane_uid, other in ((a, b), (b, a)):
                if lane_uid in near and other in centre_y:
                    near[lane_uid].append(centre_y[other])

        def lane_key(node: DiagramNode) -> tuple[int, Fraction, str]:
            ys = near[node.uid]
            return (_band_rank(node), Fraction(sum(ys), len(ys)) if ys else Fraction(0), node.uid)

        layout.lane_order = apply_positions([n.uid for n in sorted(outer, key=lane_key)], model.logical_positions)  # D39
        for i, uid in enumerate(layout.lane_order):
            layout.row_of[uid] = ("l", i)
    _place_logical(layout, bool(outer))
    _plan_logical_tracks(model, layout, bool(outer))
    return layout


def _logical_drawn(model: DiagramModel, layout: LogicalLayout) -> list[tuple[int, DiagramEdge]]:
    return [(i, e) for i, e in enumerate(model.edges) if e.source != e.target and e.source in layout.pos and e.target in layout.pos]


def _plan_logical_tracks(model: DiagramModel, layout: LogicalLayout, outer: bool) -> None:
    """D35 and D36 for the logical view; fills layout.plan, layout.runs and the track counts, then places again.

    Every edge leaves its source's bottom at one attachment point shared by all of the source's edges, runs down
    to its out-run in the gap below the source, and enters its target's top from the target's in-run in the gap
    above it. A target in the next row of the same stack is reached straight from the out-run ("direct"); any
    other target through a gutter between columns, or through the lane gutter when either end is in the outside
    lane. The out-run of a box is one run for all its edges and so is its in-run; a gutter carries one run per
    source. Row-gap runs are assigned on the x order of the layout without tracks (a run that ends in a gutter is
    taken to cover the whole gutter, so the order, and therefore every overlap, is the same once gutters grow);
    gutter runs are assigned on the y of the placed rows, which the gutter widths do not move.
    """
    pos = layout.pos
    used = len(layout.space_tracks) - 2
    lane_space = layout.spaces[used + 1]
    drawn = _logical_drawn(model, layout)

    def out_x(uid: str) -> int:
        return pos[uid][0] + LOGICAL_BOX_W // 2 + ATTACH_DX

    def in_x(uid: str) -> int:
        return pos[uid][0] + LOGICAL_BOX_W // 2 - ATTACH_DX

    def toward(x: int, space: tuple[int, int]) -> tuple[int, int]:
        left, width = space
        return (min(x, left), max(x, left + width))  # the whole gutter: its tracks are not placed yet

    runs: dict[tuple, _Run] = {}

    def add(key: tuple, lo: int, hi: int, i: int, e: DiagramEdge) -> None:
        run = runs.get(key)
        if run is None:
            run = runs[key] = _Run(key, lo, hi, {e.source, e.target}, i)
        else:
            run.lo, run.hi = min(run.lo, lo), max(run.hi, hi)
            run.uids |= {e.source, e.target}
        run.parts.append((lo, hi, {e.source, e.target}))

    layout.plan = {}
    targets: dict[int, tuple] = {}  # edge index -> (out x, far x of the out-run, in x, far x of the in-run or None)
    for i, e in drawn:
        (ss, sr), (ts, tr) = layout.row_of[e.source], layout.row_of[e.target]
        ax, bx = out_x(e.source), in_x(e.target)
        if ss == ts and tr == sr + 1:
            layout.plan[i] = ("direct",)
            targets[i] = (ax, bx, bx, None)
            continue
        if ss == "m" and ts == "m":
            j = min(range(used + 1), key=lambda g: (abs(ax - layout.gutters[g]) + abs(bx - layout.gutters[g]), g))
            layout.plan[i] = ("gutter", j)
            space = layout.spaces[j]
        else:
            layout.plan[i] = ("lane",)
            space = lane_space
        centre = space[0] + space[1] // 2
        targets[i] = (ax, centre, bx, centre)

    def collect(split: set) -> dict:
        """Row-gap runs. A box's edges share its stub (D36); in a gap listed in ``split`` its edges leaving to the
        left and to the right part at the stub and are two runs, elsewhere they are one run."""
        runs.clear()
        layout.halves = {}
        for i, e in drawn:
            ax, far_a, bx, far_b = targets[i]
            gap_a = _gap_of(layout, ("out", e.source))
            out_key = ("out", e.source, (1 if far_a > ax else -1) if gap_a in split else 0)
            if far_b is None:
                layout.halves[i] = (out_key, None)
                add(out_key, min(ax, far_a), max(ax, far_a), i, e)
                continue
            space = layout.spaces[layout.plan[i][1]] if layout.plan[i][0] == "gutter" else lane_space
            gap_b = _gap_of(layout, ("in", e.target))
            in_key = ("in", e.target, (1 if far_b > bx else -1) if gap_b in split else 0)
            layout.halves[i] = (out_key, in_key)
            add(out_key, *toward(ax, space), i, e)
            add(in_key, *toward(bx, space), i, e)
        by_gap: dict[tuple[str, int], list[_Run]] = {}
        for key in sorted(runs):
            runs[key].gap = _gap_of(layout, key)
            by_gap.setdefault(runs[key].gap, []).append(runs[key])
        # The verticals inside each gap: a box's out-stub (from the row above down to its out-run), its in-stub
        # (from its in-run down to the row below) and the drop of a direct edge (from the source's out-run down to
        # the target).
        stubs: dict[tuple[str, int], list[tuple[int, str, tuple, set]]] = {}
        for key, run in sorted(runs.items()):
            run.x = out_x(key[1]) if key[0] == "out" else in_x(key[1])
            stubs.setdefault(run.gap, []).append((run.x, key[0], key, run.uids))
        for i, e in drawn:
            if layout.plan[i][0] == "direct":
                out_key = layout.halves[i][0]
                stubs[runs[out_key].gap].append((in_x(e.target), "direct", out_key, {e.source, e.target}))
        return {gap: _order_gap(items, stubs[gap]) for gap, items in sorted(by_gap.items())}

    # A gap whose runs cannot be ordered without crossing a co-visible stub (a cycle of rules in _order_gap) is
    # split into left and right runs, which removes the cycles a wall (an edge passing both the stub and the drop of
    # a co-visible direct edge) makes; the other gaps keep one run per box, which keeps their crossings fewer. A
    # cycle can remain in a split gap under a pinned box order (D39); _order_gap then breaks it as it documents.
    split: set = set()
    while True:
        result = collect(split)
        broken = {gap for gap, (_count, cycle) in result.items() if cycle} - split
        if not broken:
            break
        split |= broken
    layout.gap_tracks = {gap: count for gap, (count, _cycle) in result.items()}
    _plan_label_bands(model, layout, drawn)
    _place_logical(layout, outer)
    # Gutter runs: one per source and gutter, from the source's out-run to each target's in-run, on the placed y.
    vertical: dict[tuple, _Run] = {}
    for i, e in drawn:
        step = layout.plan[i]
        if step[0] == "direct":
            continue
        j = step[1] if step[0] == "gutter" else used + 1
        ya, yb = _run_y(layout, runs[layout.halves[i][0]]), _run_y(layout, runs[layout.halves[i][1]])
        key = ("v", j, e.source)
        run = vertical.get(key)
        if run is None:
            vertical[key] = _Run(key, min(ya, yb), max(ya, yb), {e.source, e.target}, i)
        else:
            run.lo, run.hi = min(run.lo, ya, yb), max(run.hi, ya, yb)
            run.uids |= {e.source, e.target}
    joins: dict[tuple, list[tuple[int, int]]] = {}  # vertical run key -> (y, side) of each row-gap run joining it
    for i, e in drawn:
        step = layout.plan[i]
        if step[0] != "direct":
            j = step[1] if step[0] == "gutter" else used + 1
            centre = layout.spaces[j][0] + layout.spaces[j][1] // 2
            for x, key in ((out_x(e.source), layout.halves[i][0]), (in_x(e.target), layout.halves[i][1])):
                joins.setdefault(("v", j, e.source), []).append((_run_y(layout, runs[key]), 1 if x > centre else -1))
    layout.space_tracks = [_order_gutter([run for key, run in sorted(vertical.items()) if key[1] == j], joins) for j in range(used + 2)]
    _place_logical(layout, outer)
    runs.update(vertical)
    layout.runs = runs


def _plan_label_bands(model: DiagramModel, layout: LogicalLayout, drawn: list) -> None:
    """D37: each row gap reserves a label band of LABEL_BAND px times the largest same-ordered-pair multiplicity at
    its top (labels of edges leaving the row above) and at its bottom (labels of edges entering the row below), and
    the rise of the self-loops of the row below under the bottom band; tracks run between the bands."""
    layout.label_rows, mult = _label_pairs(drawn)
    rows_s: dict[tuple, int] = {}
    rows_t: dict[tuple, int] = {}
    layout.gap_tech = set()
    for i, e in drawn:
        if i in layout.label_rows:
            n = mult[(e.source, e.target)]
            gs, gt = _gap_of(layout, ("out", e.source)), _gap_of(layout, ("in", e.target))
            if clean(e.technology):
                layout.gap_tech.update((gs, gt))
            rows_s[gs] = max(rows_s.get(gs, 0), n)
            rows_t[gt] = max(rows_t.get(gt, 0), n)
    loops: dict[str, list] = {}
    for e in model.edges:
        if e.source == e.target and e.source in layout.pos:
            loops.setdefault(e.source, []).append(bool(clean(e.technology)))
    rise: dict[tuple, int] = {}
    for uid, techs in loops.items():
        gap = _gap_of(layout, ("in", uid))
        rise[gap] = max(rise.get(gap, 0), _loop_rise(techs))  # two-line loop labels are taller
    layout.gap_bands = {
        gap: (_pitch(gap in layout.gap_tech) * rows_s.get(gap, 0), _pitch(gap in layout.gap_tech) * rows_t.get(gap, 0), rise.get(gap, 0))
        for gap in sorted(set(rows_s) | set(rows_t) | set(rise))
    }


def _order_gap(items: list, stubs: list) -> tuple[int, bool]:
    """Tracks of one row gap, top to bottom (D35, D36); returns the track count and whether a cycle was broken.

    A run must not cross a vertical of a co-visible edge inside the gap: when the stretch of one of its edges that
    shares an endpoint with the vertical's edges passes over a box's out-stub
    it lies below that box's out-run, over an in-stub above that box's in-run, and over the drop of a direct edge
    above the out-run the drop leaves from. Out-runs otherwise lie above in-runs, so neither crosses the other
    side's stubs. Runs are placed in an order that honours these rules (ties by kind, start, attachment x and uid;
    nothing depends on relationship document order), each on the lowest track below every run it must lie under
    that holds no co-visible run overlapping it. When no run is free of the rules (a cycle), the first remaining run
    in the tie order is placed anyway and the cycle is reported. A wall across the gap (an edge passing over both
    the stub and the drop of a co-visible direct edge) makes such cycles, and splitting the gap's runs into left and
    right halves removes those; a residual cycle can remain under a pinned box order (D39), where at most one
    co-visible stub crossing can result. D35 and D36 hold either way.
    """
    by_key = {run.key: run for run in items}
    above: dict[tuple, set] = {run.key: set() for run in items}  # run key -> keys of runs that must lie above it
    required: set = set()
    for run in items:
        for x, kind, owner, uids in stubs:
            if owner == run.key or owner not in by_key or not any(lo < x < hi and ends & uids for lo, hi, ends in run.parts):
                continue
            pair = (owner, run.key) if kind == "out" else (run.key, owner)
            above[pair[1]].add(pair[0])
            required.add(pair)
    for out in items:
        for inner in items:
            if out.key[0] == "out" and inner.key[0] == "in" and (inner.key, out.key) not in required:
                above[inner.key].add(out.key)
    rank = {run.key: (run.key[0] != "out", run.lo, run.x, run.key) for run in items}
    placed: list = []
    cycle = False
    left = sorted(by_key, key=lambda k: rank[k])
    while left:
        ready = [k for k in left if not (above[k] & set(left))]
        cycle = cycle or not ready
        key = min(ready or left, key=lambda k: rank[k])
        left.remove(key)
        run = by_key[key]
        track = 1 + max([by_key[k].track for k in above[key] if k not in left], default=-1)
        while any(o.track == track and o.uids & run.uids and run.lo <= o.hi and o.lo <= run.hi for o in placed):
            track += 1
        run.track = track
        placed.append(run)
    return 1 + max([run.track for run in items], default=-1), cycle


def _order_gutter(items: list, joins: dict) -> int:
    """Assign a gutter's tracks (D35), then choose where each track sits across the gutter.

    The track positions are free, so they are ordered to cut crossings: a row-gap run that joins a gutter run from
    the left crosses every track left of its own whose runs span its y, and one from the right every track right
    of it. Up to GUTTER_EXACT tracks the order with the fewest such crossings is found by trying every order (the
    first in lexicographic order wins a tie); above that tracks keep their left-edge order.
    """
    count = _left_edge(items)
    if 1 < count <= GUTTER_EXACT:
        spans: list[list[tuple[int, int]]] = [[] for _ in range(count)]
        ends: list[list[tuple[int, int]]] = [[] for _ in range(count)]
        for run in items:
            spans[run.track].append((run.lo, run.hi))
            ends[run.track].extend(joins[run.key])

        def inside(y: int, k: int) -> int:
            return sum(1 for lo, hi in spans[k] if lo < y < hi)

        # left[a][b]: crossings between tracks a and b when a sits left of b.
        left = [[0] * count for _ in range(count)]
        for a in range(count):
            for b in range(count):
                if a != b:
                    left[a][b] = sum(inside(y, a) for y, side in ends[b] if side < 0) + sum(inside(y, b) for y, side in ends[a] if side > 0)
        best = min(
            itertools.permutations(range(count)),
            key=lambda order: sum(left[order[i]][order[k]] for i in range(count) for k in range(i + 1, count)),
        )
        place = {k: n for n, k in enumerate(best)}
        for run in items:
            run.track = place[run.track]
    return count


def _gap_of(layout: LogicalLayout, key: tuple) -> tuple[str, int]:
    """The row gap of an out-run (below its box) or an in-run (above its box)."""
    stack, row = layout.row_of[key[1]]
    return (stack, row + 1) if key[0] == "out" else (stack, row)


def _run_y(layout: LogicalLayout, run: _Run) -> int:
    top, size = layout.gaps[run.gap]
    above, below, rise = layout.gap_bands.get(run.gap, (0, 0, 0))  # D37: tracks run between the label bands
    return _track_at(top + above, size - above - below - rise, layout.gap_tracks[run.gap], run.track) + (LOGICAL_LANE_SHIFT if run.gap[0] == "l" else 0)


def _run_x(layout: LogicalLayout, run: _Run) -> int:
    left, width = layout.spaces[run.key[1]]
    return _track_at(left, width, layout.space_tracks[run.key[1]], run.track)


def _route_edges(model: DiagramModel, layout: LogicalLayout) -> dict[int, list[tuple[int, int]]]:
    """Orthogonal route per edge (index in model.edges) from the tracks layout_logical assigned (D35, D36).

    An edge leaves its source through the bottom side and enters its target through the top side; every edge of a
    source shares its attachment point and out-run, every edge of a target its in-run and attachment point. Runs
    travel only in row gaps and gutters, so a route never crosses a box that is not one of its endpoints.
    """
    pos = layout.pos
    routes: dict[int, list[tuple[int, int]]] = {}
    for i, e in _logical_drawn(model, layout):
        a, b = pos[e.source], pos[e.target]
        ax, bx = a[0] + LOGICAL_BOX_W // 2 + ATTACH_DX, b[0] + LOGICAL_BOX_W // 2 - ATTACH_DX
        ya = _run_y(layout, layout.runs[layout.halves[i][0]])
        step = layout.plan[i]
        if step[0] == "direct":
            raw = [(ax, a[1] + LOGICAL_BOX_H), (ax, ya), (bx, ya), (bx, b[1])]
        else:
            j = step[1] if step[0] == "gutter" else len(layout.spaces) - 1
            gx = _run_x(layout, layout.runs[("v", j, e.source)])
            yb = _run_y(layout, layout.runs[layout.halves[i][1]])
            raw = [(ax, a[1] + LOGICAL_BOX_H), (ax, ya), (gx, ya), (gx, yb), (bx, yb), (bx, b[1])]
        pts: list[tuple[int, int]] = []
        for point in raw:
            if not pts or pts[-1] != point:
                pts.append(point)
        routes[i] = pts
    return routes


def _loop_path(x: float, y: float, grow: float) -> str:
    """Self-relationship loop off the top-right corner of the box at x, y."""
    p1 = (x + LOGICAL_BOX_W * 0.62, y)
    p2 = (x + LOGICAL_BOX_W, y + LOGICAL_BOX_H * 0.3)
    return (
        f"M{p1[0]:.1f} {p1[1]:.1f} C{p1[0]:.1f} {y - 24 - grow:.1f} "
        f"{x + LOGICAL_BOX_W + 30 + grow:.1f} {p2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    )


def _loop_apex(grow: float) -> float:
    """Height above the box top of the highest point of the loop with ``grow``, by sampling its Bezier."""
    c1, c2 = 24 + grow, -LOGICAL_BOX_H * 0.3  # control heights above the box top: first control, then the shared one and end
    best = 0.0
    for i in range(1, 100):
        t = i / 100
        best = max(best, 3 * (1 - t) ** 2 * t * c1 + 3 * (1 - t) * t * t * c2 + t ** 3 * c2)
    return best


def _loop_stack(techs: list) -> list:
    """D37: where the labels of the loops of one box sit, in drawing order: (bottom offset above the box top, height)
    each. A label is one line (14 px) or, when the loop records a technology, two (28 px); it stacks on the label of
    the loop before it, and keeps 4 px clear of the apex of the next loop's curve, so the order of the loops does not
    matter. The first label's bottom is 26 px above the box."""
    out: list = []
    bottom = 26
    for k, tech in enumerate(techs):
        if out:
            bottom = out[-1][0] + out[-1][1]
        if k + 1 < len(techs):
            bottom = max(bottom, _loop_apex(LOOP_STEP * (k + 1)) + 4)
        out.append((int(-(-bottom // 1)), LABEL_ROW if tech else LABEL_H))
    return out


def _loop_rise(techs: list) -> int:
    """Rise reserved above a box for its loops' labels: the top of the highest label, at least LOOP_RISE."""
    stack = _loop_stack(techs)
    return int(max([LOOP_RISE] + [-(-(b + h) // 1) for b, h in stack]))


# --------------------------------------------------------------------------- vocabulary (D11, D12, D13)
# Type chip label and CSS class key for each node type (D11). Unknown types get the chip "other" with the raw type name.
CHIP_LABELS = {
    "product_component": "component",
    "data_component": "data",
    "data_store_service": "data store",
    "runtime_service": "runtime",
    "network_service": "network",
    "ai_gateway": "ai gateway",
    "host": "host",
    "external": "external",
}
CHIP_KEYS = ("component", "data", "data-store", "runtime", "network", "ai-gateway", "host", "external", "other")

# D12: every colour is a custom property with a light and a dark value. The dark values apply under
# prefers-color-scheme unless the page forces light, and under an explicit data-theme="dark".
THEME_TOKENS = {
    "surface": ("#ffffff", "#18202b"),
    "ink": ("#1a2230", "#e4e9f0"),
    "muted": ("#586374", "#97a2b3"),
    "line": ("#7a8696", "#8c99ab"),
    "box": ("#ffffff", "#18202b"),
    "box-line": ("#555555", "#8c99ab"),
    "band": ("#f3f5f8", "#121923"),
    "band-line": ("#c3cad4", "#3c485a"),
    "lane": ("#fbf6ec", "#221d12"),
    "lane-line": ("#d8c9a8", "#6b5d3f"),
    "target": ("#eef1f6", "#121923"),
    "target-line": ("#9aa6b6", "#3c485a"),
    "group": ("#f8f9fb", "#141b25"),
    "group-line": ("#7a8696", "#4a586b"),
    "zone-line": ("#c3cad4", "#3c485a"),
    "amber": ("#a85a00", "#f2a64e"),
    "chip-component": ("#dbeafe", "#1e3a5f"),
    "chip-data": ("#dcfce7", "#14532d"),
    "chip-data-store": ("#ccfbf1", "#134e4a"),
    "chip-runtime": ("#ede9fe", "#4c1d95"),
    "chip-network": ("#fef3c7", "#713f12"),
    "chip-ai-gateway": ("#fce7f3", "#831843"),
    "chip-host": ("#e5e7eb", "#374151"),
    "chip-external": ("#f1f5f9", "#0f172a"),
    "chip-other": ("#f5f5f4", "#292524"),
    "chip-ink": ("#1a2230", "#e4e9f0"),
}


def _theme_css() -> str:
    light = "".join(f"--{name}:{pair[0]};" for name, pair in THEME_TOKENS.items())
    dark = "".join(f"--{name}:{pair[1]};" for name, pair in THEME_TOKENS.items())
    return (
        f":root{{{light}}}"
        "@media (prefers-color-scheme:dark){:root:not([data-theme=\"light\"]){" + dark + "}}"
        ":root[data-theme=\"dark\"]{" + dark + "}"
    )


_FIGURE_CSS = (
    ".band{fill:var(--band);stroke:var(--band-line)}"
    ".lane{fill:var(--lane);stroke:var(--lane-line);stroke-dasharray:6 4}"
    ".bl,.ll{font:600 11px sans-serif;fill:var(--muted)}"
    ".tgt{fill:var(--target);stroke:var(--target-line);stroke-width:1.4}"
    ".grp{fill:var(--group);stroke:var(--group-line)}"
    ".store>.grp{fill:var(--band);stroke:var(--band-line)}"
    ".zl{fill:var(--surface);stroke:var(--zone-line);stroke-dasharray:3 3}"
    ".tl{font:700 12px sans-serif;fill:var(--ink)}"
    ".gl,.zc{font:600 11px sans-serif;fill:var(--muted)}"
    ".gc{font:600 12px sans-serif;fill:var(--ink)}"
    ".box{fill:var(--box);stroke:var(--box-line);stroke-width:1.4}"
    ".ttl{font:600 12px sans-serif;fill:var(--ink)}"
    ".cap{font:10px sans-serif;fill:var(--muted)}"
    ".dashed .box,.group.dashed .grp{stroke-dasharray:5 3}"
    ".ret .box{stroke-dasharray:5 3;opacity:.6}.dep .box{stroke:var(--amber)}"
    ".ret .grp{stroke-dasharray:5 3;opacity:.6}.dep .grp{stroke:var(--amber)}"
    + "".join(f".chip-{key}{{fill:var(--chip-{key})}}" for key in CHIP_KEYS)
    + ".chip-t{font:600 9px sans-serif;fill:var(--chip-ink)}"
    ".tech-line{font:9px sans-serif;fill:var(--muted)}"
    ".ln{fill:none;stroke:var(--line);stroke-width:1.4}"
    ".ln.dashed{stroke-dasharray:6 4}"
    ".ln.dotted{stroke-dasharray:1 3;stroke-linecap:round;stroke-width:1.8}"
    ".fl{display:none;fill:none;stroke:var(--surface);stroke-width:1.6;stroke-linecap:round;stroke-dasharray:2 8;animation:flow .9s linear infinite}"
    ".fl.rev{animation-direction:reverse}"
    "@keyframes flow{to{stroke-dashoffset:-10}}"
    "@media (prefers-reduced-motion:reduce){.fl{animation:none}}"
    ".mk{fill:var(--line)}"
    ".lb{font:600 10.5px sans-serif;fill:var(--muted);paint-order:stroke;stroke:var(--surface);stroke-width:3px;stroke-linejoin:round}"
    ".lb .tech{font-weight:400}"
    ".lb{display:none}"
    ".edge.on.out .lb-t,.edge.on.in .lb-s{display:inline}"
    ".callout{display:none;font:600 11px sans-serif;fill:var(--ink);paint-order:stroke;stroke:var(--surface);stroke-width:4px;stroke-linejoin:round;pointer-events:none}"
    ".callout .tech{font-weight:400}"
    ".edge:hover .callout{display:inline}"
)


def _with_fallbacks(css: str) -> str:
    """Each var(--token) gets its light value as fallback, so viewers without custom properties still draw colour."""
    return re.sub(r"var\(--([a-z0-9-]+)\)", lambda m: f"var(--{m.group(1)},{THEME_TOKENS[m.group(1)][0]})", css)


SVG_STYLE = _theme_css() + _with_fallbacks(_FIGURE_CSS)


def chip_label(node_type: str) -> str:
    return CHIP_LABELS.get(node_type, node_type.replace("_", " ") or "other")


def chip_key(node_type: str) -> str:
    return CHIP_LABELS[node_type].replace(" ", "-") if node_type in CHIP_LABELS else "other"


def _clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(1, width - 3)] + "..."


def _marker_defs(prefix: str) -> str:
    """Arrowheads for one figure (D13). ``-end`` points along the path; ``-start`` points back toward its start."""

    def marker(suffix: str, orient: str) -> str:
        return (
            f'<marker id="{prefix}-{suffix}" viewBox="0 0 8 7" refX="8" refY="3.5" markerWidth="8" markerHeight="7" '
            f'markerUnits="userSpaceOnUse" orient="{orient}"><polygon class="mk" points="0,0 8,3.5 0,7"/></marker>'
        )

    return "<defs>" + marker("end", "auto") + marker("start", "auto-start-reverse") + "</defs>"


def _edge_marks(edge: DiagramEdge, prefix: str) -> tuple[str, str]:
    """Path class and arrowhead attributes (D13).

    Asynchronous draws dashed and event dotted; synchronous or absent is solid. The arrowhead is at the target for
    outbound or absent flow, at the source for inbound, and at both ends for bidirectional.
    """
    cls = "ln"
    if edge.direction == "asynchronous":
        cls += " dashed"
    elif edge.direction == "event":
        cls += " dotted"
    marks = ""
    if edge.flow in ("", "outbound", "bidirectional"):
        marks += f' marker-end="url(#{prefix}-end)"'
    if edge.flow in ("inbound", "bidirectional"):
        marks += f' marker-start="url(#{prefix}-start)"'
    return cls, marks


def _flow_overlay(path: str, flow: str) -> str:
    """D34: animated dots that travel along a highlighted line toward its arrowhead (CSS only; static markup).

    Outbound or absent flow runs source to target; inbound runs the other way; bidirectional draws both.
    """
    if flow == "inbound":
        return f'<path class="fl rev" d="{path}"/>'
    if flow == "bidirectional":
        return f'<path class="fl" d="{path}"/><path class="fl rev" d="{path}"/>'
    return f'<path class="fl" d="{path}"/>'


LABEL_BAND = 18  # D37: one label row: 14 px of text plus 4 px of pad
LABEL_PAD = 2
LABEL_H = 14
LABEL_ROW = 28  # D37 two-line amendment: a label row is two 14 px lines in a gap where a labelled edge records a technology
LABEL_DX = 5  # a label starts this far right of its own box's left edge (a container end: the container's)
LABEL_CHAR_W = 6.2  # D13 metrics: about 6.2 px a character, 14 px tall
CALLOUT_CHAR_W = 6.8


def _overlap(a: tuple, b: tuple) -> float:
    """Overlapping area of two (x, y, w, h) rectangles."""
    return max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])) * max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))


def _row_h(tech: bool) -> int:
    """Height of a label row in a gap: two lines when any labelled edge there records a technology, else one."""
    return LABEL_ROW if tech else LABEL_H


def _pitch(tech: bool) -> int:
    """Distance between the rows of a label band: the row height plus the 4 px pad of LABEL_BAND."""
    return _row_h(tech) + LABEL_BAND - LABEL_H


def _has_label(edge: DiagramEdge) -> bool:
    return bool(clean(edge.label) or clean(edge.technology))


def _max_chars(width: float) -> int:
    """Characters that fit a label under a box of ``width`` px: the text is clipped to the box width minus 10 px."""
    return max(4, int((width - 10 - 4) / LABEL_CHAR_W))


def _label_parts(edge: DiagramEdge, limit: Any = None) -> tuple:
    """The label and the technology part (with its separator) as drawn; clipped with an ellipsis to ``limit``
    characters when one is given."""
    label, tech = clean(edge.label), clean(edge.technology)
    tech_part = ((" / " if label else "") + tech) if tech else ""
    if limit is not None and len(label) + len(tech_part) > limit:
        whole = (label + tech_part)[: limit - 3] + "..."
        return whole[: len(label)], whole[len(label) :]
    return label, tech_part


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _label_lines(edge: DiagramEdge, limit: int) -> list:
    """D37: the lines of a label as drawn, each clipped independently with an ellipsis to ``limit`` characters:
    the label phrase, then the recorded technology (each omitted when empty). Returns (text, is technology) pairs."""
    label, tech = clean(edge.label), clean(edge.technology)
    return ([(_clip(label, limit), False)] if label else []) + ([(_clip(tech, limit), True)] if tech else [])


def _label_len(edge: DiagramEdge, limit: int) -> int:
    """Characters of the longest line of an edge label as drawn."""
    return max(len(text) for text, _t in _label_lines(edge, limit))


def _label_box_at(x: float, top: float, edge: DiagramEdge, limit: Any, anchor: str = "start", height: Any = None) -> tuple:
    """(x, y, w, h) of a label whose text starts (or, anchored at the end, ends) at x and whose box starts at top;
    ``height`` is the row height in effect (one line, or two when the edge records a technology)."""
    w = _label_len(edge, limit) * LABEL_CHAR_W + 4
    return (x - 2 if anchor == "start" else x - w + 2, top, w, _row_h(bool(clean(edge.technology))) if height is None else height)


def _stub_side(left: float, width: float, stub: float) -> tuple:
    """D37: within its box a label sits on the side of its own stub with more room: left-aligned at the box's left
    edge plus LABEL_DX when the stub is right of the box centre, otherwise right-aligned at the right edge minus
    LABEL_DX; clipped to that side's width minus 6 px of clearance from the stub. Returns (x, anchor, max chars)."""
    if stub > left + width / 2:
        x = left + LABEL_DX
        return (x, "start", max(4, int((stub - 6 - x - 4) / LABEL_CHAR_W)))
    x = left + width - LABEL_DX
    return (x, "end", max(4, int((x - (stub + 6) - 4) / LABEL_CHAR_W)))


def _label_pairs(drawn: list) -> tuple:
    """D37: for each labelled, non-loop edge its index among the edges of the same ordered pair (edge order), and
    the count per ordered pair. ``drawn`` is a list of (edge number, edge)."""
    index: dict[int, int] = {}
    mult: dict[tuple, int] = {}
    for number, edge in drawn:
        if edge.source == edge.target or not _has_label(edge):
            continue
        key = (edge.source, edge.target)
        index[number] = mult.get(key, 0)
        mult[key] = index[number] + 1
    return index, mult


def _longest_segments(pts: list) -> list:
    """Segments of a route, longest first (first wins a tie)."""
    segs = [(abs(bx - ax) + abs(by - ay), i, (ax, ay), (bx, by)) for i, ((ax, ay), (bx, by)) in enumerate(zip(pts, pts[1:]))]
    return [(a, b) for _n, _i, a, b in sorted(segs, key=lambda t: (-t[0], t[1]))]


def _callout_at(pts: list, edge: DiagramEdge, obstacles: list) -> tuple:
    """D37: where the hover callout goes: the midpoint of the longest segment, moved along the segments (50%, 25%,
    75%, longest first) to the first spot clear of every obstacle (boxes and captions); least overlap otherwise."""
    width = (len(clean(edge.label)) + (len(clean(edge.technology)) + 3 if clean(edge.technology) else 0)) * CALLOUT_CHAR_W + 6
    best: tuple = ()
    for (ax, ay), (bx, by) in _longest_segments(pts):
        for fraction in (0.5, 0.25, 0.75):
            cx, cy = ax + (bx - ax) * fraction, ay + (by - ay) * fraction
            box = (cx - width / 2, cy - 16, width, 18)
            area = sum(_overlap(box, o) for o in obstacles)
            if area == 0:
                return (cx, cy - 6)
            if not best or area < best[0]:
                best = (area, (cx, cy - 6))
    return best[1]


def _loop_callout(at: tuple, edge: DiagramEdge, obstacles: list) -> tuple:
    """The callout of a self-loop: one row above the loop's label, moved up while it overlaps an obstacle (node
    boxes, captions and every label visible while the box is selected). ``at`` is (x, baseline, limit)."""
    width = (len(clean(edge.label)) + (len(clean(edge.technology)) + 3 if clean(edge.technology) else 0)) * CALLOUT_CHAR_W + 6
    cx = at[0] - 2 + (_label_len(edge, at[2]) * LABEL_CHAR_W + 4) / 2  # centred over its label
    base = at[1] - LABEL_BAND
    for _ in range(12):
        if not any(_overlap((cx - width / 2, base - 10, width, 18), o) for o in obstacles):
            break
        base -= LABEL_BAND
    return (cx, base)


def _place_loop_label(base: tuple, edge: DiagramEdge, avoid: list) -> tuple:
    """A self-loop's label (left-aligned above the loop) steps up one row at a time until it is clear of ``avoid``
    (node boxes, captions and the labels of the edges that share its box); least overlap if nothing is clear.
    ``base`` is (x, baseline, limit)."""
    best: tuple = ()
    for step in range(8):
        y = base[1] - LABEL_BAND * step
        area = sum(_overlap(_loop_box((base[0], y, base[2]), edge), o) for o in avoid)
        if area == 0:
            return (base[0], y, base[2])
        if not best or area < best[0]:
            best = (area, (base[0], y, base[2]))
    return best[1]


def _loop_box(at: tuple, edge: DiagramEdge) -> tuple:
    return (at[0] - 2, at[1] - 10, _label_len(edge, at[2]) * LABEL_CHAR_W + 4, _row_h(bool(clean(edge.technology))))


def _edge_label(edge: DiagramEdge, ends: tuple, loop: Any, callout: tuple) -> str:
    """Two labels per edge (D37): ``lb lb-s`` beside the source end and ``lb lb-t`` beside the target end, each
    (x, baseline, limit), left-aligned; a self-loop has one ``lb lb-t`` label (``loop``). The label text is clipped
    to its box and followed by the recorded technology in a lighter weight (D13); the callout repeats the full
    text. Empty when neither label nor technology is recorded."""
    if not _has_label(edge):
        return ""
    full_label, full_tech = _label_parts(edge)

    def body(l: str, t: str) -> str:
        return (xml_text(l) if l else "") + (f'<tspan class="tech">{xml_text(t)}</tspan>' if t else "")

    out = ""
    placed = [("lb-t", loop + ("start",))] if loop is not None else [("lb-s", ends[0]), ("lb-t", ends[1])]
    for cls, (x, y, limit, anchor) in placed:
        lines = "".join(
            f'<tspan class="tech" x="{x:.1f}" dy="{LABEL_H * k}">{xml_text(t)}</tspan>' if tech else f'<tspan x="{x:.1f}" dy="{LABEL_H * k}">{xml_text(t)}</tspan>'
            for k, (t, tech) in enumerate(_label_lines(edge, limit))
        )
        out += f'<text class="lb {cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}">{lines}</text>'
    out += f'<text class="callout" x="{callout[0]:.1f}" y="{callout[1]:.1f}" text-anchor="middle">{body(full_label, full_tech)}</text>'
    return out


def _edge_label_svgs(edges: list, routes: dict, tops: dict, loops: dict, obstacles: list) -> dict:
    """D37: the label and callout markup of every drawn edge, by edge number.

    ``edges`` is a list of (number, edge); ``routes`` the polyline of each non-loop edge; ``tops`` the row tops
    (((source box left, width, stub x), row top), ((target box left, width, stub x), row top)) of each labelled non-loop edge,
    computed by the view from its label bands; ``loops`` (box left, width, default baseline) of each self-loop's
    label. A label starts 5 px right of its box's left edge and is clipped to the box width minus 10 px. A
    self-loop label steps up until it is clear of ``obstacles`` and of the labels of edges that share its box.
    """
    boxes: dict[int, list] = {}
    texts: dict[int, tuple] = {}
    for number, edge in edges:
        if number in tops:
            ends = []
            heights = []
            for (left, width, stub), top, *row in tops[number]:  # an optional third item: the row height in effect
                x, anchor, limit = _stub_side(left, width, stub)
                ends.append((x, top, limit, anchor))
                heights.append(row[0] if row else None)
            boxes[number] = [_label_box_at(x, top, edge, limit, anchor, h) for (x, top, limit, anchor), h in zip(ends, heights)]
            texts[number] = tuple((x, top + 10, limit, anchor) for x, top, limit, anchor in ends)
    out: dict[int, str] = {}
    loop_at: dict[int, tuple] = {}
    placed_loops: list = []
    for number, edge in edges:
        if edge.source == edge.target and _has_label(edge):
            left, width, base = loops[number]
            avoid = list(obstacles) + [b for n, e in edges if n in boxes and edge.source in (e.source, e.target) for b in boxes[n]]
            avoid += [b for uid, b in placed_loops if uid == edge.source]
            x = left + width / 2 - ATTACH_DX + 6  # right of the box's own in-stub, so no stub crosses the text
            at = _place_loop_label((x, base, max(4, int((left + width - LABEL_DX - x - 4) / LABEL_CHAR_W))), edge, avoid)
            loop_at[number] = at
            placed_loops.append((edge.source, _loop_box(at, edge)))
    for number, edge in edges:
        if not _has_label(edge):
            out[number] = ""
        elif edge.source == edge.target:
            visible = list(obstacles) + [b for n, e in edges if n in boxes and edge.source in (e.source, e.target) for b in boxes[n]]
            visible += [b for uid, b in placed_loops if uid == edge.source]
            out[number] = _edge_label(edge, (), loop_at[number], _loop_callout(loop_at[number], edge, visible))
        else:
            shown = list(obstacles)  # also the labels visible while either end of the hovered line is selected
            for n2, e2 in edges:
                if n2 in boxes:
                    for end in (edge.source, edge.target):
                        if e2.source == end:
                            shown.append(boxes[n2][1])
                        if e2.target == end:
                            shown.append(boxes[n2][0])
            shown += [b for uid, b in placed_loops if uid in (edge.source, edge.target)]
            out[number] = _edge_label(edge, texts[number], None, _callout_at(routes[number], edge, shown))
    return out


def _node_svg(node: DiagramNode, x: int, y: int) -> str:
    """One node box, shared by the logical and deployment figures (D11, D12).

    The top row holds the type chip and the technology line beside it. The name takes at most two lines. An
    outside-lane box puts its caption on the bottom row. Retired and deprecated boxes carry those classes.
    """
    cls = "node" + (" dashed" if node.derived else "") + (" outside" if node.outside else "") + (" external" if node.external else "")
    if node.life == "retired":
        cls += " ret"
    elif node.life == "deprecated":
        cls += " dep"
    lines = _fit_lines(node.name, 26, 2)
    mid = x + LOGICAL_BOX_W // 2
    first = y + (31 if len(lines) == 2 else 37)
    label = chip_label(node.node_type)
    chip_w = int(len(label) * 5.4) + 12
    chip_x = x + 8
    top = (
        f'<rect class="chip chip-{chip_key(node.node_type)}" x="{chip_x}" y="{y + 5}" width="{chip_w}" height="13" rx="3"/>'
        f'<text class="chip-t" x="{chip_x + 6}" y="{y + 15}">{xml_text(label)}</text>'
    )
    tech = clean(node.tech)
    room = int((LOGICAL_BOX_W - 16 - chip_w - 6) / 5.4)
    if tech and room > 3:
        top += f'<text class="tech-line" x="{chip_x + chip_w + 6}" y="{y + 15}">{xml_text(_clip(tech, room))}</text>'
    text = "".join(
        f'<text class="ttl" x="{mid}" y="{first + 13 * i}" text-anchor="middle">{xml_text(line)}</text>'
        for i, line in enumerate(lines)
    )
    if node.outside and node.caption:
        cap = _fit_lines(node.caption, 34, 1)[0]
        text += f'<text class="cap" x="{mid}" y="{y + 56}" text-anchor="middle">{xml_text(cap)}</text>'
    return (
        f'<g class="{cls}" data-id="{xml_text(node.uid)}"><title>{xml_text(node.name)}</title>'
        f'<rect class="box" x="{x}" y="{y}" width="{LOGICAL_BOX_W}" height="{LOGICAL_BOX_H}" rx="6"/>{top}{text}</g>'
    )


def render_logical_svg(model: DiagramModel) -> str:
    """The logical application figure as a standalone SVG (D11 to D13).

    Deterministic (D15): no version, timestamp or path; ``<desc>`` holds the generator name and SDP uid only.
    """
    layout = layout_logical(model)
    by_uid = {n.uid: n for n in model.nodes}
    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {layout.width} {layout.height}" '
        f'width="{layout.width}" height="{layout.height}" role="img" aria-label="{LOGICAL_TITLE}">',
        f"<title>{LOGICAL_TITLE}</title>",
        f"<desc>{xml_text(GENERATOR_NAME)} {xml_text(model.sdp_uid)}</desc>",
        _marker_defs("lg"),
        f"<style>{SVG_STYLE}</style>",
    ]
    for band, y, height, width in layout.bands:
        out.append(f'<rect class="band" x="{LOGICAL_MARGIN}" y="{y}" width="{width}" height="{height}" rx="6"/>')
        out.append(f'<text class="bl" x="{LOGICAL_MARGIN + 10}" y="{y + 20}">{xml_text(band)}</text>')
    if layout.lane:
        lx, ly, lw, lh = layout.lane
        out.append(f'<rect class="lane" x="{lx}" y="{ly}" width="{lw}" height="{lh}" rx="6"/>')
        out.append(f'<text class="ll" x="{lx + 10}" y="{ly + 24}">External interactions</text>')
    routes = _route_edges(model, layout)
    # D13: edge labels keep clear of node boxes, band labels and the outside lane caption.
    obstacles = [(x0, y0, LOGICAL_BOX_W, LOGICAL_BOX_H) for x0, y0 in layout.pos.values()]
    obstacles += [(LOGICAL_MARGIN + 10, y + 11, len(band) * 7 + 4, 12) for band, y, _h, _w in layout.bands]
    if layout.lane:
        obstacles.append((layout.lane[0] + 10, layout.lane[1] + 15, len("External interactions") * 7 + 4, 12))
    loops: dict[str, int] = {}
    shown = [(n, e) for n, e in enumerate(model.edges) if e.source in layout.pos and e.target in layout.pos]
    tops: dict[int, tuple] = {}
    loop_base: dict[int, tuple] = {}
    loop_techs: dict[str, list] = {}  # per box, whether each loop records a technology (two-line label)
    for _n, edge in shown:
        if edge.source == edge.target:
            loop_techs.setdefault(edge.source, []).append(bool(clean(edge.technology)))
    for number, edge in shown:
        if edge.source == edge.target:
            x, y = layout.pos[edge.source]
            lb_bottom, lb_height = _loop_stack(loop_techs[edge.source])[loops.get(edge.source, 0)]
            loops[edge.source] = loops.get(edge.source, 0) + 1
            loop_base[number] = (x, LOGICAL_BOX_W, y - lb_bottom - lb_height + 10)
        elif number in layout.label_rows:
            k = layout.label_rows[number]
            gs, gt = _gap_of(layout, ("out", edge.source)), _gap_of(layout, ("in", edge.target))
            ps, pt = _pitch(gs in layout.gap_tech), _pitch(gt in layout.gap_tech)
            top_s = layout.gaps[gs][0] + LABEL_PAD + ps * k
            gtop, gsize = layout.gaps[gt]
            own_rise = _loop_rise(loop_techs[edge.target]) if loop_techs.get(edge.target) else 0
            bottom_t = gtop + gsize - own_rise  # a target's own loops rise under its label
            tops[number] = (
                ((layout.pos[edge.source][0], LOGICAL_BOX_W, routes[number][0][0]), top_s, _row_h(gs in layout.gap_tech)),
                ((layout.pos[edge.target][0], LOGICAL_BOX_W, routes[number][-1][0]), bottom_t - pt * (k + 1) + LABEL_PAD, _row_h(gt in layout.gap_tech)),
            )
    labels = _edge_label_svgs(shown, routes, tops, loop_base, obstacles)
    loops = {}
    for number, edge in shown:
        s, t = edge.source, edge.target
        tip = xml_text(f"{by_uid[s].name} {edge.label or '(no label recorded)'} {by_uid[t].name}")
        head = f'<g class="edge" data-from="{xml_text(s)}" data-to="{xml_text(t)}"><title>{tip}</title>'
        cls, marks = _edge_marks(edge, "lg")
        if s == t:  # a self-relationship: a small loop off the top-right corner
            x, y = layout.pos[s]
            grow = 14 * loops.get(s, 0)
            loops[s] = loops.get(s, 0) + 1
            path = _loop_path(x, y, grow)
        else:
            path = "M" + " L".join(f"{px} {py}" for px, py in routes[number])
        out.append(f'{head}<path class="{cls}" d="{path}"{marks}/>{_flow_overlay(path, edge.flow)}{labels[number]}</g>')
    for uid in [u for names in layout.order for u in names] + layout.lane_order:
        x, y = layout.pos[uid]
        out.append(_node_svg(by_uid[uid], x, y))
    out.append("</svg>")
    return "\n".join(out) + "\n"


DEPLOY_COLUMNS = 3  # boxes per row inside a zone lane
DEPLOY_PAD = 10
DEPLOY_COL_GAP = 60  # minimum gap between box columns; widened when self-loops would reach the next column
DEPLOY_LEVEL = TRACK_PITCH  # D35: distance between two tracks of a free band
DEPLOY_TRACK_PAD = 6  # from a band's edges to its outer tracks
DEPLOY_MIN_BAND = 24  # a free band that carries no edge run is still this tall
DEPLOY_CHANNEL_PAD = 20  # from the stack's right border to the first vertical channel
DEPLOY_CHANNEL_STEP = TRACK_PITCH  # D35: between vertical channel tracks
DEPLOY_LANE_GAP = 40  # from the last channel to the outside lane
DEPLOY_MAX_PASSES = 400  # safety net for the layout and routing fixed-point loop; bands only grow, so the loop
# ends by itself in a few passes
DEPLOY_BORDER_CLEAR = 4  # vertical edge runs keep at least this far from every container border
LOOP_REACH = 36  # a self-loop reaches this far right of its box; each further loop on the same box adds LOOP_STEP
LOOP_RISE = 40  # and this far above it (room for the loop's label)
LOOP_STEP = 14
DEPLOY_LANE_HEAD = 30
DEPLOY_TARGET_HEAD = 30
DEPLOY_TARGET_GAP = 30
DEPLOY_CHAR_W = 7  # estimated text width in px, used to wrap container text to its container
DEPLOY_LINE_H = 14
DEPLOYMENT_TITLE = "Deployment pattern diagram"


def _deployment_outline(model: DiagramModel) -> list[tuple[str, list[DiagramContainer]]]:
    """D6: deployment targets in SDP document order (first group that names them), each with its drawn groups."""
    order: list[str] = []
    for container in model.containers:
        if container.target not in order:
            order.append(container.target)
    outline = [(target, [c for c in model.containers if c.drawn and c.target == target]) for target in order]
    return [(target, groups) for target, groups in outline if groups]


def _wrap_to(text: str, width_px: int) -> list[str]:
    """Wrap catalog text to a pixel width without dropping anything; over-long words are split."""
    chars = max(8, (width_px - 20) // DEPLOY_CHAR_W - 2)  # two characters of margin: bold upper case runs wider than the estimate
    lines: list[str] = []
    for line in wrap(clean(text), chars):
        while len(line) > chars:
            lines.append(line[:chars])
            line = line[chars:]
        lines.append(line)
    return lines


def _ordered_stores(stores: list[DiagramStore], positions: dict[str, int]) -> list[DiagramStore]:
    """D39: positioned data store containers first, by (position, uid); the rest follow in listing order.

    The 'data store not recorded' container cannot be positioned and always comes last, so a layout written from
    the drawn order renders the same order again (D40).
    """
    placed = sorted((st for st in stores if st.uid in positions), key=lambda st: (positions[st.uid], st.uid))
    rest = [st for st in stores if st.uid not in positions]
    return placed + [st for st in rest if st.uid] + [st for st in rest if not st.uid]  # 'not recorded' has no uid: last


def _fmt(value: Any) -> str:
    value = float(value)
    return str(int(value)) if value == int(value) else f"{value:.1f}"


@dataclass
class _Band:
    """A horizontal strip of free space between two rows of boxes, or two containers, that carries edge runs.

    Out-runs of the element above the band (its edges leave through its bottom side, D36) take tracks from the top
    of the band downward; in-runs of the element below take tracks from the bottom upward, above the ``rise``
    reserved for that row's self-loops. ``rightward`` says which way runs leave the band: right toward the channels,
    or left from the outside lane toward them. ``tracks`` is what the layout made room for; the router sets ``need``.
    """

    lo: int
    hi: int
    rise: int
    rightward: bool
    tracks: int = 0
    need: int = 0
    bs: int = 0  # D37: px reserved at the top for lb-s labels of the elements above
    bt: int = 0  # and above the rise, at the bottom, for lb-t labels of the elements below
    tech: bool = False  # D37: a labelled edge here records a technology, so its label rows are two lines


def _band_height(tracks: int, rise: int, bs: int = 0, bt: int = 0) -> int:
    """D35: a band is as tall as its tracks need (pitch apart, pad from each edge), and never below DEPLOY_MIN_BAND;
    D37 adds the label bands at its top and bottom."""
    return max(DEPLOY_MIN_BAND, DEPLOY_LEVEL * tracks + 2 * DEPLOY_TRACK_PAD) + rise + bs + bt


def _band_label_rows(drawn: list, pools: dict, bands: list) -> list:
    """D37: per band, the label rows it reserves at its top (edges leaving the element above) and bottom (edges
    entering the element below): the largest same-ordered-pair multiplicity there, zero where no label ends."""
    index = {id(band): k for k, band in enumerate(bands)}
    _rows, mult = _label_pairs(drawn)
    rows = [[0, 0] for _ in bands]
    techs = [False] * len(bands)  # D37: a band holding a labelled edge with a technology has two-line rows
    tech_pairs = {(e.source, e.target) for _n, e in drawn if e.source != e.target and _has_label(e) and clean(e.technology)}
    for (source, target), n in sorted(mult.items()):
        for uid, slot, pool in ((source, 0, "bottom"), (target, 1, "top")):
            band = pools.get(uid, {}).get(pool)
            if band is not None:
                k = index[id(band)]
                rows[k][slot] = max(rows[k][slot], n)
                techs[k] = techs[k] or (source, target) in tech_pairs
    return [(a, b, t, t) for (a, b), t in zip(rows, techs)]


def _route_deployment_edges(
    drawn: list,
    rects: dict,
    pools: dict,
    bands: list,
    stack_right: int,
    chan_pad: int,
) -> tuple[dict, int]:
    """Comb routing (D15, D35, D36, deterministic): every edge runs out of the stack to a vertical channel on its right.

    An edge leaves its source, box or container, through the bottom side and enters its target through the top
    side. All edges of a source share one attachment point, one out-run along a track of the band below the source
    and one channel; all edges of a target share one in-run along a track of the band above it and one attachment
    point. Channels lie right of every container and left of the outside lane, so no run crosses a box.

    Channel runs are assigned by the left-edge rule over the y span of the bands they join. Band tracks are taken
    in order from the run nearest the channels outward, each run the lowest track that holds no co-visible run and
    keeps it clear of the stub of every co-visible run already placed (so a run never crosses such a stub). Runs
    in the outside lane's bands also keep a track apart from co-visible stack runs that overlap them in x. Runs of
    edges that share no endpoint may share a track (D35).

    Returns the polyline per edge index and the number of channel tracks; each band's ``need`` holds its tracks.
    """

    def attach(uid: str, out: bool) -> int:
        x, _y, w, _h = rects[uid]
        return x + w // 2 + (ATTACH_DX if out else -ATTACH_DX)

    chan_runs: dict[str, _Run] = {}
    for i, e in drawn:
        lo = min(pools[e.source]["bottom"].lo, pools[e.target]["top"].lo)
        hi = max(pools[e.source]["bottom"].hi, pools[e.target]["top"].hi)
        run = chan_runs.get(e.source)
        if run is None:
            chan_runs[e.source] = _Run(("c", e.source), lo, hi, {e.source, e.target}, i)
        else:
            run.lo, run.hi = min(run.lo, lo), max(run.hi, hi)
            run.uids |= {e.source, e.target}
    count = _left_edge([chan_runs[uid] for uid in sorted(chan_runs)])
    chan_x = {uid: stack_right + chan_pad + DEPLOY_CHANNEL_STEP * run.track for uid, run in chan_runs.items()}
    # Band runs, keyed (band index, out-run?, uid, attachment x); lo and hi are the run's x span.
    runs: dict[tuple, _Run] = {}
    index = {id(band): k for k, band in enumerate(bands)}  # identity lookup only; nothing iterates this dict
    for i, e in drawn:
        for uid, out, band in ((e.source, True, pools[e.source]["bottom"]), (e.target, False, pools[e.target]["top"])):
            x, cx = attach(uid, out), chan_x[e.source]
            lo, hi = (x, cx) if band.rightward else (cx, x)
            key = (index[id(band)], out, uid, x)
            run = runs.get(key)
            if run is None:
                runs[key] = _Run(key, lo, hi, {e.source, e.target}, i)
            else:
                run.lo, run.hi = min(run.lo, lo), max(run.hi, hi)
                run.uids |= {e.source, e.target}
    level: dict[tuple[bool, str], int] = {}
    placed: list[tuple[int, _Run]] = []  # (y, run) of every stack run, for the outside lane's bands
    by_band: dict[int, list[_Run]] = {}
    for run in sorted(runs.values(), key=lambda r: r.key):
        by_band.setdefault(run.key[0], []).append(run)
    order = sorted(by_band, key=lambda k: (not bands[k].rightward, k))  # stack bands first, then the outside lane's
    for k in order:
        band = bands[k]
        used = {True: 0, False: 0}
        for from_top in (True, False):
            pool = sorted(
                (r for r in by_band[k] if r.key[1] == from_top), key=lambda r: ((-r.key[3] if band.rightward else r.key[3]), r.first)
            )
            done: list[_Run] = []
            for run in pool:
                track = 1 + max([o.track for o in done if o.uids & run.uids], default=-1)
                while True:
                    y = band.lo + band.bs + DEPLOY_TRACK_PAD + DEPLOY_LEVEL * track if from_top else band.hi - band.rise - band.bt - DEPLOY_TRACK_PAD - DEPLOY_LEVEL * track
                    if band.rightward or not any(
                        abs(y - oy) < DEPLOY_LEVEL and o.uids & run.uids and run.lo <= o.hi and o.lo <= run.hi for oy, o in placed
                    ):
                        break
                    track += 1
                run.track = track
                done.append(run)
                level[(from_top, run.key[2])] = y
                if band.rightward:
                    placed.append((y, run))
                used[from_top] = max(used[from_top], track + 1)
        band.need = used[True] + used[False]
    routes: dict[int, list[tuple[int, int]]] = {}
    for i, e in drawn:
        sx, sy, _sw, sh = rects[e.source]
        tx, ty, _tw, _th = rects[e.target]
        ox, ix, cx = attach(e.source, True), attach(e.target, False), chan_x[e.source]
        ys, yt = level[(True, e.source)], level[(False, e.target)]
        raw = [(ox, sy + sh), (ox, ys), (cx, ys), (cx, yt), (ix, yt), (ix, ty)]
        pts: list[tuple[int, int]] = []
        for point in raw:
            if not pts or pts[-1] != point:
                pts.append(point)
        routes[i] = pts
    return routes, count


def render_deployment_svg(model: DiagramModel, order_out: dict[str, list[str]] | None = None) -> str:
    """The deployment pattern figure: target -> group container -> zone lanes -> boxes (D6).

    Edges are plain solid orthogonal routes (S7 styles them) from the boxes and containers to vertical
    channels right of the stack; see _route_deployment_edges. Container text is wrapped to its container
    and the container grows to hold it. Free bands between rows, between groups and around the outside
    lane's boxes are as tall as the tracks their runs need (D35). Deterministic (D15).
    """
    by_uid = {n.uid: n for n in model.deployment_nodes}
    outline = _deployment_outline(model)
    containers = {g.uid for _t, groups in outline for g in groups if g.uid}
    containers |= {st.uid for _t, groups in outline for g in groups for lane in g.lanes for st in lane.stores if st.uid}  # D45
    drawable = set(by_uid) | containers
    drawn = [(i, e) for i, e in enumerate(model.edges) if e.source != e.target and e.source in drawable and e.target in drawable]
    loops: dict[str, int] = {}
    loop_techs: dict[str, list] = {}  # per box or container, whether each loop records a technology (two-line label)
    for e in model.edges:
        if e.source == e.target and (e.source in by_uid or e.source in containers):
            loops[e.source] = loops.get(e.source, 0) + 1
            loop_techs.setdefault(e.source, []).append(bool(clean(e.technology)))
    most_loops = max([n for uid, n in loops.items() if uid in by_uid], default=0)  # box loops size lanes and columns
    container_loops = max([n for uid, n in loops.items() if uid in containers], default=0)
    # A container's loop (D13) sits at its top-right corner and reaches past the target border; the channels start
    # beyond its reach.
    chan_pad = max(DEPLOY_CHANNEL_PAD, LOOP_REACH + LOOP_STEP * (container_loops - 1) + DEPLOY_LEVEL) if container_loops else DEPLOY_CHANNEL_PAD

    def rise(uids: list) -> int:
        return max([_loop_rise(loop_techs[u]) for u in uids if loops.get(u)], default=0)

    loop_room = (LOOP_REACH + LOOP_STEP * (most_loops - 1) + 4 - DEPLOY_PAD) if most_loops else 0
    col_gap = max(DEPLOY_COL_GAP, LOOP_REACH + LOOP_STEP * (most_loops - 1) + 10) if most_loops else DEPLOY_COL_GAP
    col_gap = -(-col_gap // GRID) * GRID  # D14: box x on the grid
    step_x = LOGICAL_BOX_W + col_gap
    lane_sizes = [len(lane.members) for _t, groups in outline for g in groups for lane in g.lanes]
    used = min(DEPLOY_COLUMNS, max(lane_sizes, default=1))
    inner_w = used * LOGICAL_BOX_W + (used - 1) * col_gap

    def store_width(store: DiagramStore) -> int:  # D45: a data store container holds its data components in rows
        cols = min(DEPLOY_COLUMNS, len(store.members))
        return cols * LOGICAL_BOX_W + (cols - 1) * col_gap + 2 * DEPLOY_PAD

    inner_w = max([inner_w] + [store_width(st) for _t, groups in outline for g in groups for lane in g.lanes for st in lane.stores])
    lane_w = inner_w + 2 * DEPLOY_PAD + loop_room
    group_w = lane_w + 2 * DEPLOY_PAD

    captions: list = []  # (x, y, w, h) of every container caption of the last build_stack call, for D37 obstacles

    def build_stack(levels: list, lab: list) -> tuple:
        """Lay out the stack and the outside lane's rows.

        levels[k] is the number of tracks the k-th band created needed in the last routing pass (D35; see
        _route_deployment_edges); a band no pass has routed yet has none. Bands are created in the same order on
        every call.
        """
        target_w = group_w + 2 * DEPLOY_PAD
        captions.clear()
        bands: list[_Band] = []
        rects: dict[str, tuple[int, int, int, int]] = {}  # uid -> x, y, w, h of a box or the first container with that uid
        pools: dict[str, dict[str, _Band]] = {}
        names: dict[str, str] = {n.uid: n.name for n in model.deployment_nodes}
        pos: dict[str, tuple[int, int]] = {}
        body: list[str] = []

        def band_at(lo: int, rise_px: int, rightward: bool = True) -> _Band:
            tracks = levels[len(bands)] if len(bands) < len(levels) else 0
            rows_s, rows_t, tech_s, tech_t = lab[len(bands)] if len(bands) < len(lab) else (0, 0, False, False)
            bs, bt = _pitch(tech_s) * rows_s, _pitch(tech_t) * rows_t
            hi = -(-(lo + _band_height(tracks, rise_px, bs, bt)) // GRID) * GRID  # D14: the row below starts on the grid
            band = _Band(lo=lo, hi=hi, rise=rise_px, rightward=rightward, tracks=tracks, bs=bs, bt=bt, tech=tech_s or tech_t)
            bands.append(band)
            return band

        def rows_of(members: list) -> list[list[str]]:
            return [members[r : r + DEPLOY_COLUMNS] for r in range(0, len(members), DEPLOY_COLUMNS)]

        y = LOGICAL_MARGIN
        for target, groups in outline:
            tx = LOGICAL_MARGIN
            label = clean(target) or "deployment target not recorded"
            t_lines = _wrap_to(label, target_w)
            ty = y
            cursor = y + DEPLOY_TARGET_HEAD + DEPLOY_LINE_H * (len(t_lines) - 1)
            # Geometry first (band heights depend only on edge counts), then the SVG text in nesting order.
            group_boxes: list[str] = []
            for g_index, g in enumerate(groups):
                prev_uid = groups[g_index - 1].uid if g_index else ""
                band = band_at(cursor, rise([g.uid]) if g.uid not in rects else 0)
                if prev_uid and prev_uid in pools and "bottom" not in pools[prev_uid]:
                    pools[prev_uid]["bottom"] = band
                gy = band.hi
                n_lines = _wrap_to(g.group, group_w)
                c_lines = _wrap_to(g.caption, group_w)
                g_head = 18 + DEPLOY_LINE_H * (len(n_lines) - 1) + 20 + DEPLOY_LINE_H * (len(c_lines) - 1) + 12
                gx = tx + DEPLOY_PAD
                first_time = bool(g.uid) and g.uid not in rects
                if first_time:
                    pools[g.uid] = {"top": band}
                    names[g.uid] = g.name or g.caption
                lane_svgs: list[str] = []
                ly = gy + g_head
                for lane in g.lanes:
                    lx = gx + DEPLOY_PAD
                    z_lines = _wrap_to(f"{lane.name} ({lane.tier})" if lane.tier else lane.name, lane_w)
                    caption_end = DEPLOY_LANE_HEAD + DEPLOY_LINE_H * (len(z_lines) - 1)
                    rows = rows_of(apply_positions(lane.members, model.deployment_positions))  # D39
                    cursor2 = ly + caption_end
                    node_svgs: list[str] = []
                    prev_row: list[str] = []

                    def lay_rows(rows_in: list, cx: int, cursor_in: int, prev_in: list) -> tuple:
                        """Rows of boxes at x cx from cursor_in; returns the new cursor and the last row's uids."""
                        for row in rows_in:
                            above = band_at(cursor_in, rise(row))
                            for uid in prev_in:
                                if uid in pools and "bottom" not in pools[uid]:
                                    pools[uid]["bottom"] = above
                            row_top = above.hi
                            for col, uid in enumerate(row):
                                bx = cx + col * step_x
                                if uid in by_uid and uid not in pos:
                                    pos[uid] = (bx, row_top)
                                    rects[uid] = (bx, row_top, LOGICAL_BOX_W, LOGICAL_BOX_H)
                                    pools[uid] = {"top": above}
                                    node_svgs.append(_node_svg(by_uid[uid], bx, row_top))
                            cursor_in = row_top + LOGICAL_BOX_H
                            prev_in = row
                        return cursor_in, prev_in

                    cursor2, prev_row = lay_rows(rows, lx + DEPLOY_PAD, cursor2, prev_row)
                    for store in _ordered_stores(lane.stores, model.deployment_positions):  # D45
                        above = band_at(cursor2, rise([store.uid]))
                        for uid in prev_row:
                            if uid in pools and "bottom" not in pools[uid]:
                                pools[uid]["bottom"] = above
                        sx, sy, sw = lx + DEPLOY_PAD, above.hi, store_width(store)
                        s_lines = _wrap_to(store.name, sw)
                        s_head = 18 + DEPLOY_LINE_H * (len(s_lines) - 1) + 6 + 13 + 8
                        inner: list[str] = []
                        saved = node_svgs
                        node_svgs = inner
                        s_rows = rows_of(apply_positions(store.members, model.deployment_positions))  # D39
                        s_cursor, s_prev = lay_rows(s_rows, sx + DEPLOY_PAD, sy + s_head, [])
                        node_svgs = saved
                        s_below = band_at(s_cursor, 0)
                        for uid in s_prev:
                            if uid in pools and "bottom" not in pools[uid]:
                                pools[uid]["bottom"] = s_below
                        sh = s_below.hi - sy
                        first_store = bool(store.uid) and store.uid not in rects
                        if first_store:
                            rects[store.uid] = (sx, sy, sw, sh)
                            pools[store.uid] = {"top": above}
                            names[store.uid] = store.name
                        chip_w = int(len(chip_label("data_store_service")) * 5.4) + 12
                        captions.extend((sx + 10, sy + 18 + DEPLOY_LINE_H * k - 11, len(line) * DEPLOY_CHAR_W + 4, 12) for k, line in enumerate(s_lines))
                        if store.uid:
                            captions.append((sx + 10, sy + 18 + DEPLOY_LINE_H * (len(s_lines) - 1) + 6, chip_w, 13))
                        s_text = "".join(
                            f'<text class="gl" x="{sx + 10}" y="{sy + 18 + DEPLOY_LINE_H * k}">{xml_text(line)}</text>' for k, line in enumerate(s_lines)
                        )
                        if store.uid:
                            chip_y = sy + 18 + DEPLOY_LINE_H * (len(s_lines) - 1) + 6
                            s_text += (
                                f'<rect class="chip chip-{chip_key("data_store_service")}" x="{sx + 10}" y="{chip_y}" width="{chip_w}" height="13" rx="3"/>'
                                f'<text class="chip-t" x="{sx + 16}" y="{chip_y + 10}">{xml_text(chip_label("data_store_service"))}</text>'
                            )
                        s_cls = "group store" + (" dashed" if not store.uid else "")
                        s_cls += " ret" if store.life == "retired" else " dep" if store.life == "deprecated" else ""
                        s_ident = f' data-id="{xml_text(store.uid)}"' if store.uid else ""
                        node_svgs.append(
                            f'<g class="{s_cls}"{s_ident} data-group="{xml_text(store.name)}"><title>{xml_text(store.name)}</title>'
                            f'<rect class="grp" x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="6"/>{s_text}'
                            + "".join("\n" + node for node in inner)
                            + "\n</g>"
                        )
                        cursor2 = sy + sh
                        prev_row = [store.uid]
                    below = band_at(cursor2, 0)
                    for uid in prev_row:
                        if uid in pools and "bottom" not in pools[uid]:
                            pools[uid]["bottom"] = below
                    lane_h = below.hi - ly
                    for k, line in enumerate(z_lines):
                        captions.append((lx + 10, ly + 19 + DEPLOY_LINE_H * k - 11, len(line) * DEPLOY_CHAR_W + 4, 12))
                    ztext = "".join(
                        f'<text class="zc" x="{lx + 10}" y="{ly + 19 + DEPLOY_LINE_H * k}">{xml_text(line)}</text>' for k, line in enumerate(z_lines)
                    )
                    lane_svgs.append(
                        f'<g class="zlane" data-zone="{xml_text(lane.zone)}">'
                        f'<rect class="zl" x="{lx}" y="{ly}" width="{lane_w}" height="{lane_h}" rx="5"/>{ztext}'
                        + "".join("\n" + node for node in node_svgs)
                        + "\n</g>"
                    )
                    ly += lane_h + DEPLOY_PAD
                group_h = (ly if g.lanes else ly + DEPLOY_PAD) - gy
                if first_time:
                    rects[g.uid] = (gx, gy, group_w, group_h)
                cap_y = gy + 18 + DEPLOY_LINE_H * (len(n_lines) - 1) + 20
                captions.extend((gx + 10, gy + 18 + DEPLOY_LINE_H * k - 11, len(line) * DEPLOY_CHAR_W + 4, 12) for k, line in enumerate(n_lines))
                captions.extend((gx + 10, cap_y + DEPLOY_LINE_H * k - 11, len(line) * DEPLOY_CHAR_W + 4, 12) for k, line in enumerate(c_lines))
                texts = "".join(
                    f'<text class="gl" x="{gx + 10}" y="{gy + 18 + DEPLOY_LINE_H * k}">{xml_text(line)}</text>' for k, line in enumerate(n_lines)
                ) + "".join(
                    f'<text class="gc" x="{gx + 10}" y="{cap_y + DEPLOY_LINE_H * k}">{xml_text(line)}</text>' for k, line in enumerate(c_lines)
                )
                ident = f' data-id="{xml_text(g.uid)}"' if g.uid else ""
                cls = "group" + (" dashed" if g.derived else "")
                cls += " ret" if g.life == "retired" else " dep" if g.life == "deprecated" else ""
                group_boxes.append(
                    f'<g class="{cls}"{ident} data-group="{xml_text(g.group)}"><title>{xml_text(g.group)}</title>'
                    f'<rect class="grp" x="{gx}" y="{gy}" width="{group_w}" height="{group_h}" rx="6"/>{texts}'
                    + "".join("\n" + lane for lane in lane_svgs)
                    + "\n</g>"
                )
                cursor = gy + group_h
            last_uid = groups[-1].uid
            tail_band = band_at(cursor, 0)
            if last_uid and last_uid in pools and "bottom" not in pools[last_uid]:
                pools[last_uid]["bottom"] = tail_band
            target_h = tail_band.hi - ty
            captions.extend((tx + 10, ty + 20 + DEPLOY_LINE_H * k - 11, len(line) * DEPLOY_CHAR_W + 4, 12) for k, line in enumerate(t_lines))
            text = "".join(
                f'<text class="tl" x="{tx + 10}" y="{ty + 20 + DEPLOY_LINE_H * k}">{xml_text(line)}</text>' for k, line in enumerate(t_lines)
            )
            body.append(
                f'<g class="target" data-target="{xml_text(clean(target))}">'
                f'<rect class="tgt" x="{tx}" y="{ty}" width="{target_w}" height="{target_h}" rx="8"/>{text}'
                + "".join("\n" + group for group in group_boxes)
                + "\n</g>"
            )
            y = ty + target_h + DEPLOY_TARGET_GAP
        stack_bottom = y - DEPLOY_TARGET_GAP if outline else LOGICAL_MARGIN
        stack_right = LOGICAL_MARGIN + target_w if outline else LOGICAL_MARGIN
        # The outside lane (D5): boxes in a single column at the right, ordered as in the logical view; their y
        # positions do not depend on the lane's x, which waits for the channel count.
        outer = [n for n in model.deployment_nodes if n.outside]
        lane_rows: list[tuple[DiagramNode, int]] = []
        lane_top = LOGICAL_MARGIN
        lane_h = 0
        if outer:
            centre_y = {uid: r[1] + r[3] / 2 for uid, r in rects.items()}
            near: dict[str, list[float]] = {n.uid: [] for n in outer}
            for _i, e in drawn:
                for lane_uid, other in ((e.source, e.target), (e.target, e.source)):
                    if lane_uid in near and other in centre_y:
                        near[lane_uid].append(centre_y[other])

            def lane_key(node: DiagramNode) -> tuple[int, Fraction, str]:
                ys = near[node.uid]
                return (_band_rank(node), Fraction(sum(ys)) / len(ys) if ys else Fraction(0), node.uid)

            by_node = {n.uid: n for n in outer}
            ordered = [by_node[u] for u in apply_positions([n.uid for n in sorted(outer, key=lane_key)], model.deployment_positions)]  # D39
            cursor = lane_top + DEPLOY_LANE_HEAD
            prev: list[str] = []
            for node in ordered:
                above = band_at(cursor, rise([node.uid]), rightward=False)
                for uid in prev:
                    pools[uid]["bottom"] = above
                lane_rows.append((node, above.hi))
                pools[node.uid] = {"top": above}
                cursor = above.hi + LOGICAL_BOX_H
                prev = [node.uid]
            below = band_at(cursor, 0, rightward=False)
            pools[prev[0]]["bottom"] = below
            lane_h = below.hi - lane_top
        return bands, rects, pools, names, pos, body, stack_bottom, stack_right, lane_rows, lane_top, lane_h, outer

    # Layout and routing depend on each other: the outside lane's x follows the channel count, and a band is as
    # tall as the tracks its runs need (D35), which moves everything below it and so the channel spans. Iterate to
    # a fixed point; band tracks only grow, so it ends. The loop is a pure function of the catalog, so the result is
    # deterministic. Each pass is cheap, so the cap is only a safety net.
    levels: list[int] = []
    lab: list[tuple] = []  # D37: label rows (top, bottom) each band reserves
    n_channels = 0
    for _attempt in range(DEPLOY_MAX_PASSES):
        laid = build_stack(levels, lab)
        bands, rects, pools, names, pos, body, stack_bottom, stack_right, lane_rows, lane_top, lane_h, outer = laid
        last_channel = stack_right + chan_pad + DEPLOY_CHANNEL_STEP * (n_channels - 1) if n_channels else stack_right
        lane_x = -(-(last_channel + DEPLOY_LANE_GAP) // GRID) * GRID  # D14
        for node, by in lane_rows:
            rects[node.uid] = (lane_x, by, LOGICAL_BOX_W, LOGICAL_BOX_H)
            pos[node.uid] = (lane_x, by)
        routes, used = _route_deployment_edges(drawn, rects, pools, bands, stack_right, chan_pad)
        grown = [max(band.tracks, band.need) for band in bands]
        lab_now = _band_label_rows(drawn, pools, bands)
        if used == n_channels and grown == [band.tracks for band in bands] and lab_now == lab:
            break
        n_channels, levels, lab = used, grown, lab_now
    else:  # the cap is a safety net; the figure is still drawn, from the last pass
        last_channel = stack_right + chan_pad + DEPLOY_CHANNEL_STEP * (max(used, 1) - 1)
        lane_x = max(lane_x, -(-(last_channel + DEPLOY_LANE_GAP) // GRID) * GRID)
    if order_out is not None:
        order_out["outside"] = [node.uid for node, _by in lane_rows]  # drawn order of the outside lane (D40)
    lane_box = ""
    loop_reach = LOOP_REACH + LOOP_STEP * (container_loops - 1) + DEPLOY_LEVEL if container_loops else 0
    right = max(stack_right + loop_reach, (last_channel + DEPLOY_CHANNEL_PAD) if n_channels else 0)  # container loops pass the target border
    bottom = stack_bottom
    if outer:
        lane_box = (
            f'<rect class="lane" x="{lane_x - LOGICAL_BAND_PAD}" y="{lane_top}" width="{LOGICAL_BOX_W + 2 * LOGICAL_BAND_PAD + loop_room}" '
            f'height="{lane_h}" rx="6"/><text class="ll" x="{lane_x}" y="{lane_top + 24}">External interactions</text>'
            + "".join(_node_svg(node, *pos[node.uid]) for node, _by in lane_rows)
        )
        right = lane_x + LOGICAL_BOX_W + LOGICAL_BAND_PAD + loop_room
        bottom = max(bottom, lane_top + lane_h)
    edges: list[str] = []
    deploy_obstacles = [rects[u] for u in by_uid if u in rects] + captions  # D37: boxes and every caption, then the lane caption
    if outer:
        deploy_obstacles.append((lane_x, lane_top + 15, len("External interactions") * 7 + 4, 12))
    shown = [(n, e) for n, e in enumerate(model.edges) if e.source in rects and e.target in rects]
    label_rows, _mult = _label_pairs([(n, e) for n, e in shown if e.source != e.target])
    tops: dict[int, tuple] = {}
    loop_base: dict[int, tuple] = {}
    loop_count: dict[str, int] = {}
    for number, edge in shown:
        if edge.source == edge.target:
            lb_bottom, lb_height = _loop_stack(loop_techs[edge.source])[loop_count.get(edge.source, 0)]
            loop_count[edge.source] = loop_count.get(edge.source, 0) + 1
            rx, ry, rw, _rh = rects[edge.source]
            loop_base[number] = (rx + rw - LOGICAL_BOX_W, LOGICAL_BOX_W, ry - lb_bottom - lb_height + 10)
        elif number in label_rows:
            k = label_rows[number]
            band_s, band_t = pools[edge.source]["bottom"], pools[edge.target]["top"]
            ps, pt = _pitch(band_s.tech), _pitch(band_t.tech)
            top_s = band_s.lo + LABEL_PAD + ps * k
            bottom_t = band_t.hi - rise([edge.target])  # a target's own loops rise under its label
            tops[number] = (
                ((rects[edge.source][0], rects[edge.source][2], routes[number][0][0]), top_s, _row_h(band_s.tech)),
                ((rects[edge.target][0], rects[edge.target][2], routes[number][-1][0]), bottom_t - pt * (k + 1) + LABEL_PAD, _row_h(band_t.tech)),
            )
    labels = _edge_label_svgs(shown, routes, tops, loop_base, deploy_obstacles)
    loop_count = {}
    for number, edge in shown:
        s, t = edge.source, edge.target
        tip = xml_text(f"{names.get(s, s)} {edge.label or '(no label recorded)'} {names.get(t, t)}")
        head = f'<g class="edge" data-from="{xml_text(s)}" data-to="{xml_text(t)}"><title>{tip}</title>'
        cls, marks = _edge_marks(edge, "dp")
        if s == t:  # D13: the existing loop, off the top-right corner of the box or of the container
            grow = LOOP_STEP * loop_count.get(s, 0)
            loop_count[s] = loop_count.get(s, 0) + 1
            rx, ry, rw, _rh = rects[s]
            path = _loop_path(rx + rw - LOGICAL_BOX_W, ry, grow)
        else:
            path = "M" + " L".join(f"{_fmt(px)} {_fmt(py)}" for px, py in routes[number])
        edges.append(f'{head}<path class="{cls}" d="{path}"{marks}/>{_flow_overlay(path, edge.flow)}{labels[number]}</g>')
    width = right + LOGICAL_MARGIN
    note = ""
    empty = [c for c in model.containers if not c.drawn]
    if empty:
        listing = ", ".join(f"{clean(c.group) or 'unnamed group'} ({clean(c.target) or 'deployment target not recorded'})" for c in empty)
        lines = wrap(f"Service groups recorded with no objects to draw: {listing}.", max(40, (width - 2 * LOGICAL_MARGIN) // 6))
        width = max(width, 2 * LOGICAL_MARGIN + 6 * max(len(line) for line in lines))  # D6: the caption is content too
        note = "".join(
            f'<text class="cap" x="{LOGICAL_MARGIN}" y="{bottom + 30 + 14 * i}">{xml_text(line)}</text>' for i, line in enumerate(lines)
        )
        bottom += 20 + 14 * len(lines)
    height = bottom + LOGICAL_MARGIN
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{DEPLOYMENT_TITLE}">',
        f"<title>{DEPLOYMENT_TITLE}</title>",
        f"<desc>{xml_text(GENERATOR_NAME)} {xml_text(model.sdp_uid)}</desc>",
        _marker_defs("dp"),
        f"<style>{SVG_STYLE}</style>",
    ]
    out.extend(body)
    out.append(lane_box)
    out.extend(edges)
    out.append(note)
    out.append("</svg>")
    return "\n".join(p for p in out if p) + "\n"


# --------------------------------------------------------------------------- cli
def build_from_catalog(catalog: dict[str, dict[str, Any]], selector: str | None, placed_only: bool = False) -> tuple[str, Model]:
    """Public seam (D16c): render one pattern's page from an already loaded catalog dict."""
    sdp = pick_sdp(catalog, selector)
    model = Model(catalog, sdp, placed_only)
    return render_page(model, diagram_of(model)), model


def build(workspace: Path, selector: str | None, placed_only: bool = False, editable: bool = False) -> tuple[str, Model]:
    """The page and model for one pattern. ``editable`` (D48) is set only by the ``--editable`` command line option."""
    catalog = load_catalog(workspace)
    if not editable:
        return build_from_catalog(catalog, selector, placed_only)
    model = Model(catalog, pick_sdp(catalog, selector), placed_only)
    return render_page(model, diagram_of(model), editable=True), model


def slug(text: str) -> str:
    """File-name stem: lower-case ASCII letters and digits, other characters become dashes (no path separators)."""
    return "".join(c.lower() if (c.isascii() and c.isalnum()) else "-" for c in text).strip("-") or "diagram"


def pattern_stems(patterns: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """D33: one file stem per pattern, in the order given, and the collision notes to print.

    A slug shared by two or more patterns is replaced, for all of them, by ``<slug>-<uid lower-cased>``.
    """
    bases = [slug(str(p.get("name", ""))) for p in patterns]
    counts: dict[str, int] = {}
    for base in bases:
        counts[base] = counts.get(base, 0) + 1
    stems = []
    for pattern, base in zip(patterns, bases):
        stems.append(f"{base}-{slug(str(pattern.get('uid', '')))}" if counts[base] > 1 else base)
    notes = [
        f"slug collision: {base} used by {counts[base]} patterns; uid suffix added"
        for base in sorted(counts)
        if counts[base] > 1
    ]
    return stems, notes


# --------------------------------------------------------------------------- layout writer (D40)
def drawn_order(model: Model) -> dict[str, list[list[str]]]:
    """Per view, the uids of each container (band, lane, outside lane) in drawn order."""
    dm = diagram_of(model)
    logical = layout_logical(dm)
    out: dict[str, list[list[str]]] = {"logical": [list(layer) for layer in logical.order], "deployment": []}
    if logical.lane_order:
        out["logical"].append(list(logical.lane_order))
    for _target, groups in _deployment_outline(dm):
        for group in groups:
            for lane in group.lanes:
                stores = [st for st in _ordered_stores(lane.stores, dm.deployment_positions) if st.uid]
                out["deployment"].append(apply_positions(lane.members, dm.deployment_positions) + [st.uid for st in stores])
                for store in _ordered_stores(lane.stores, dm.deployment_positions):  # D45
                    out["deployment"].append(apply_positions(store.members, dm.deployment_positions))
    order_out: dict[str, list[str]] = {}
    render_deployment_svg(dm, order_out)
    if order_out.get("outside"):
        out["deployment"].append(order_out["outside"])
    return out


def _layout_entries(containers: list[list[str]], kept: dict[str, int]) -> list[dict[str, Any]]:
    """One entry per drawn node. Kept positions stay; a new node follows the highest position of its container."""
    entries: list[dict[str, Any]] = []
    for uids in containers:
        top = max([kept[u] for u in uids if u in kept], default=0)
        for number, uid in enumerate(uids, start=1):
            if kept:
                if uid in kept:
                    position = kept[uid]
                else:
                    top += 1
                    position = top
            else:
                position = number
            entries.append({"ref": uid, "position": position})
    return entries


def _yaml_docs(path: Path) -> list[Any]:
    with path.open("r", encoding="utf-8") as handle:
        return [d for d in yaml.safe_load_all(handle) if d is not None]


def read_layout_source(path: Path, model: Model) -> dict[str, list[dict[str, Any]]]:
    """D48: the logical and deployment entries of an exported diagram_layout document, checked against what the pattern draws.

    Raises ValueError, naming the ref, for an entry the pattern does not draw in that view."""
    try:
        docs = _yaml_docs(path)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot read {path}: {exc}")
    if len(docs) != 1 or not isinstance(docs[0], dict):
        raise ValueError(f"{path} must hold one diagram_layout document")
    doc = docs[0]
    sdp_uid = str(model.sdp.get("uid", ""))
    if doc.get("type") != "diagram_layout":
        raise ValueError(f"{path} is not a diagram_layout document")
    if doc.get("pattern") != sdp_uid:
        raise ValueError(f"{path} orders pattern {doc.get('pattern')}, not {sdp_uid}")
    order = drawn_order(model)
    result: dict[str, list[dict[str, Any]]] = {}
    for view in ("logical", "deployment"):
        drawn = {uid for uids in order[view] for uid in uids}
        entries = doc.get(view) or []
        if not isinstance(entries, list):
            raise ValueError(f"{view} must be a list of ref and position entries")
        checked = []
        for entry in entries:
            if not isinstance(entry, dict) or "ref" not in entry or "position" not in entry:
                raise ValueError(f"every {view} entry needs ref and position")
            ref, position = str(entry["ref"]), entry["position"]
            if not isinstance(position, int) or isinstance(position, bool) or position < 1:
                raise ValueError(f"position of {ref} in {view} must be a positive integer")
            if ref not in drawn:
                raise ValueError(f"{view} ref {ref} is not drawn by pattern {sdp_uid}")
            checked.append({"ref": ref, "position": position})
        result[view] = checked
    return result


def write_layout(workspace: Path, model: Model, source: dict[str, list[dict[str, Any]]] | None = None) -> Path:
    """D40: write or update the pattern's diagram_layout file; no other file is touched. Returns its path.

    With ``source`` (D48, entries from ``read_layout_source``) the entries come from an exported document instead of the
    computed order; an existing layout keeps its uid and a new one gets a fresh uid, never the literal ``NEW``."""
    from generate_c4 import discover_yaml_files, workspace_yaml_roots
    from uid_utils import generate_uid

    sdp_uid = str(model.sdp.get("uid", ""))
    sdp_file: Path | None = None
    files: dict[str, Path] = {}  # uid -> file, first seen
    for root in workspace_yaml_roots(workspace):
        for path in discover_yaml_files(root):
            try:
                docs = _yaml_docs(path)
            except Exception:
                continue
            for doc in docs:
                if isinstance(doc, dict) and doc.get("uid"):
                    files.setdefault(str(doc["uid"]), path)
                    if str(doc["uid"]) == sdp_uid and sdp_file is None:
                        sdp_file = path
    if sdp_file is None:
        raise ValueError(f"cannot find the file that defines {sdp_uid}")
    existing_uid = model.layout_uid
    if existing_uid:
        target = files[existing_uid]
        docs = _yaml_docs(target)
        if len(docs) != 1 or not isinstance(docs[0], dict):
            raise ValueError(f"{target} holds more than one document; move the layout to its own file")
        doc = dict(docs[0])
    else:
        target = sdp_file.parent / f"diagram-layout-{slug(str(model.sdp.get('name', 'diagram')))}.yaml"
        if target.exists():
            raise ValueError(f"{target} already exists and is not the layout of {sdp_uid}")
        pattern_name = clean(model.sdp.get("name")) or sdp_uid
        doc = {
            "schemaVersion": "1.0",
            "uid": generate_uid(list(model.catalog)),
            "type": "diagram_layout",
            "name": f"{pattern_name} diagram layout",
            "pattern": sdp_uid,
            "catalogStatus": "complete",
        }
    if source is not None:
        doc["logical"] = source["logical"]
        doc["deployment"] = source["deployment"]
    else:
        order = drawn_order(model)
        doc["logical"] = _layout_entries(order["logical"], dict(model.layout_positions["logical"]))
        doc["deployment"] = _layout_entries(order["deployment"], dict(model.layout_positions["deployment"]))
    text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, default_flow_style=False)
    if not target.exists() or target.read_text(encoding="utf-8") != text:
        target.write_text(text, encoding="utf-8")
    return target


def _print_warnings(model: Model) -> None:
    # D18: the count line, then each distinct warning once, in sorted order (the model sorts and de-duplicates them)
    print(f"{len(model.warnings)} warnings", file=sys.stderr)
    for warning in model.warnings:
        print(warning, file=sys.stderr)


def _svg_pair(dm: DiagramModel, stem: str) -> list[tuple[str, str]]:
    """The two standalone figures of one pattern, as (file name, text)."""
    return [(f"{stem}-logical.svg", render_logical_svg(dm)), (f"{stem}-deployment.svg", render_deployment_svg(dm))]


def _check_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """D20 argument matrix; each violation is a usage error (exit 2)."""
    if args.list:
        for flag, given in (
            ("--sdp", args.sdp is not None),
            ("--all", args.all),
            ("--output", args.output is not None),
            ("--output-dir", args.output_dir is not None),
            ("--svg-dir", args.svg_dir is not None),
        ):
            if given:
                parser.error(f"--list cannot be combined with {flag}")
    if args.layout_from is not None and not args.write_layout:
        parser.error("--layout-from requires --write-layout")
    if args.editable:
        if args.all:
            parser.error("--editable renders one page, so it cannot be combined with --all")
        if args.list:
            parser.error("--editable cannot be combined with --list")
    if args.write_layout:
        if args.sdp is None:
            parser.error("--write-layout requires --sdp")
        if args.placed_only:
            parser.error("--write-layout cannot be combined with --placed-only (the layout would drop nodes the full drawing shows)")
    if args.all:
        if args.output_dir is None:
            parser.error("--all requires --output-dir DIR")
        if args.sdp is not None:
            parser.error("--all renders every pattern, so --sdp cannot be combined with it")
        if args.output is not None:
            parser.error("--all writes one file per pattern under --output-dir, so --output cannot be combined with it")
    elif args.output_dir is not None:
        parser.error("--output-dir is only used with --all")


def _render_single(args: argparse.Namespace) -> int:
    try:
        page, model = build(args.workspace, args.sdp, args.placed_only, args.editable)
        source = read_layout_source(args.layout_from, model) if args.layout_from is not None else None
    except ValueError as exc:  # D32: a malformed pattern is reported, not traced
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_warnings(model)
    stem = slug(str(model.sdp.get("name", "diagram")))
    output = args.output or Path(f"{stem}-architecture.html")
    svgs = _svg_pair(diagram_of(model), stem) if args.svg_dir is not None else []
    replaced = output.exists()
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(page, encoding="utf-8")
        if args.svg_dir is not None:
            args.svg_dir.mkdir(parents=True, exist_ok=True)
            for name, text in svgs:
                (args.svg_dir / name).write_text(text, encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write {exc.filename or output}: {exc.strerror or exc}", file=sys.stderr)
        return 1
    note = "; replaced the existing file" if replaced else ""
    print(f"Wrote {output} ({len(model.relationships)} relationships, {len(model.scope)} objects in scope){note}")
    for name, _ in svgs:
        print(f"Wrote {args.svg_dir / name}")
    if args.write_layout:
        try:
            layout_path = write_layout(args.workspace, model, source)
        except (OSError, ValueError) as exc:
            print(f"error: cannot write layout: {exc}", file=sys.stderr)
            return 1
        print(f"Wrote {layout_path}")
    return 0


def _render_all(args: argparse.Namespace) -> int:
    catalog = load_catalog(args.workspace)
    patterns = sdps(catalog)
    if not patterns:
        print(f"error: no software_deployment_pattern objects found under {args.workspace}", file=sys.stderr)
        return 1
    stems, notes = pattern_stems(patterns)
    for note in notes:
        print(note, file=sys.stderr)
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if args.svg_dir is not None:
            args.svg_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot create output directory: {exc.strerror or exc}", file=sys.stderr)
        return 1
    failures = 0
    used: set[str] = set()
    for pattern, stem in zip(patterns, stems):
        uid = str(pattern.get("uid", ""))
        name = clean(pattern.get("name")) or uid
        try:
            if stem in used:  # only possible when two uids differ by case alone
                raise ValueError(f"output name {stem} is already used by another pattern")
            model = Model(catalog, pattern, args.placed_only)
            dm = diagram_of(model)
            page = render_page(model, dm)
            svgs = _svg_pair(dm, stem) if args.svg_dir is not None else []
            html_path = args.output_dir / f"{stem}.html"
            html_path.write_text(page, encoding="utf-8")
            for svg_name, text in svgs:
                (args.svg_dir / svg_name).write_text(text, encoding="utf-8")
        except Exception as exc:  # one failing pattern must not stop the others (D20)
            print(f"error: {name} ({uid}): {exc}", file=sys.stderr)
            failures += 1
            continue
        used.add(stem)
        print(f"{uid}\t{name}\t{len(model.warnings)} warnings\t{html_path}")
        _print_warnings(model)
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a DRAFT deployment pattern as a visual diagram page.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE_ROOT, help="Workspace root containing catalog/.")
    parser.add_argument("--sdp", help="Deployment pattern name, alias or uid. Optional when only one exists.")
    parser.add_argument("--output", type=Path, help="Output HTML file. Default: <slug>-architecture.html in the current directory.")
    parser.add_argument("--placed-only", action="store_true", help="Limit scope to objects placed in a service group.")
    parser.add_argument("--list", action="store_true", help="List deployment patterns and exit.")
    parser.add_argument("--svg-dir", type=Path, help="Also write <slug>-logical.svg and <slug>-deployment.svg into this directory.")
    parser.add_argument("--all", action="store_true", help="Render every deployment pattern; requires --output-dir.")
    parser.add_argument("--output-dir", type=Path, help="With --all: directory that receives one <slug>.html per pattern.")
    parser.add_argument("--write-layout", action="store_true", help="With --sdp: write or update the pattern's diagram_layout file beside the pattern file from the drawn order. An update rewrites the file and drops hand-written comments.")
    parser.add_argument("--editable", action="store_true", help="With --sdp: add an edit mode to the page (drag or Alt+arrow boxes within their band or lane, then Export layout). Nothing is stored.")
    parser.add_argument("--layout-from", type=Path, help="With --write-layout: write the layout from an exported diagram_layout document instead of the drawn order.")
    args = parser.parse_args(argv)
    _check_arguments(parser, args)
    if not (args.workspace / "catalog").is_dir():
        print(f"error: no catalog/ directory under workspace {args.workspace}", file=sys.stderr)
        return 2
    if args.list:
        for pattern in sdps(load_catalog(args.workspace)):
            print(f"{pattern.get('uid')}\t{pattern.get('name')}")
        return 0
    if args.all:
        return _render_all(args)
    return _render_single(args)


if __name__ == "__main__":
    raise SystemExit(main())
