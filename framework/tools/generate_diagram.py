#!/usr/bin/env python3
"""Render a DRAFT Software Deployment Pattern as a visual diagram page.

Usage:
    python3 framework/tools/generate_diagram.py --list [--workspace PATH]
    python3 framework/tools/generate_diagram.py --sdp NAME_OR_UID [--workspace PATH]
        [--output FILE] [--placed-only] [--svg-dir DIR] [--write-layout]
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
LABEL_LIMIT = 8  # show edge labels permanently only up to this many edges; larger graphs label on hover


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
class DiagramLane:
    """One network-zone lane inside a service group container (D9). zone is "" for 'zone not recorded'."""

    zone: str
    name: str
    tier: str  # informational only; never affects band placement (D4, D9)
    members: list[str] = field(default_factory=list)


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

    Scope is one hop (D2): every placed object plus each direct relationship endpoint
    of a placed object whose type is in ONE_HOP_TYPES. Derived ``runs on`` relationships
    never extend scope and never become edges or relationship rows (D31).
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
            return list(self._nodes)
        if view == "deployment":
            # D29: a service group's drawn container is never also a box in the deployment view. A substrate
            # whose group is not drawn has no container figure, so it stays a box (see _build_containers).
            return [node for node in self._nodes if node.uid not in self.drawn_container_uids]
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
            "deployment": {n.uid for n in self.nodes_for_view("deployment")} | self.drawn_container_uids,
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
        outside: set[str] = set()
        externals: dict[str, str] = {}  # external id -> trimmed, whitespace-collapsed text (D3)
        if not self.placed_only:
            for rel in recorded:
                source, target = _endpoint(rel, "source"), _endpoint(rel, "target")
                # D42: only the objects a placed object depends on enter scope; consumers do not.
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
        targets = {clean(self.catalog[uid].get("runsOn")) for uid in uids if self.catalog[uid].get("type") in COMPONENT_TYPES}
        targets.discard("")
        return targets.pop() if len(targets) == 1 else ""

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
        while True:
            containers = {uid for uid, ok in zip(planned, drawable) if ok and uid}
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
            containers = {uid for uid, ok in zip(planned, drawable) if ok and uid}
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
                    runs_on = clean(obj.get("runsOn")) if obj.get("type") in COMPONENT_TYPES else ""
                    if runs_on and runs_on != recorded:
                        self.conflicts.append(Conflict(group=group_name, component=uid, runs_on=runs_on, substrate=recorded))
                        self.warnings.append(
                            f"conflict: {self.name(uid)} runsOn {self.name(runs_on)}; group substrate is {self.name(recorded)}"
                        )
            members = [uid for uid in group["uids"] if uid not in self.container_uids] if drawable[group_index] else []
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
            for uid in members:
                zone = zone_of.get(uid, "")
                if zone in declared:
                    buckets.setdefault(zone, []).append(uid)
                else:
                    unrecorded.append(uid)
                    if zone and zone not in undeclared:
                        undeclared.append(zone)
            for zone in undeclared:
                self.warnings.append(f"undeclared network zone: {zone} in {group_name}")
            lanes = [
                DiagramLane(
                    zone=zone,
                    name=clean(declared[zone].get("name")) or zone,
                    tier=clean(declared[zone].get("tier")),
                    members=buckets[zone],
                )
                for zone in declared
                if zone in buckets
            ]
            if unrecorded:  # D9: absent or undeclared zones share a last lane
                lanes.append(DiagramLane(zone="", name="zone not recorded", tier="", members=unrecorded))
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
    drawn = len([n for n in dm.nodes if not n.external])
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


def render_page(model: Model, dm: DiagramModel) -> str:
    """The D19 page: header, counts, the two figures, relationships, conflicts, characteristics, questions, inventory, footer."""
    sdp = model.sdp
    title = clean(sdp.get("name")) or "Deployment pattern"
    logical_empty = not dm.nodes
    logical_body = (
        "<p>No object is placed in a service group and no recorded relationship connects an object, so there is nothing to draw.</p>"
        if logical_empty
        else figure_html(render_logical_svg(dm), FIGURE_IDS[0])
    )
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
        f"<title>{E(title)} Architecture</title><style>{CSS}</style></head><body><div class=\"wrap\">",
        header_html(model),
        counts_html(model, dm),
        f'<section class="sec" id="logical"><h2>{E(LOGICAL_TITLE)}</h2>'
        '<label class="tog"><input type="checkbox" data-all="fig-logical"> Show all connections</label><span class="key"><span class="o"><i></i>calls it makes</span><span class="i"><i></i>calls it receives</span></span>'
        "<p>Components in bands by diagram tier. Objects that this pattern does not place sit in the right-hand lane, captioned with the pattern that places them. "
        "Connections are hidden until you hover over, focus or click a box; then only that box's own connections appear, purple for calls it makes and orange for calls it receives. "
        "Click to pin. A dashed box has a derived tier.</p>"
        + logical_body
        + "</section>",
        f'<section class="sec" id="deployment"><h2>{E(DEPLOYMENT_TITLE)}</h2>'
        '<label class="tog"><input type="checkbox" data-all="fig-deployment"> Show all connections</label><span class="key"><span class="o"><i></i>calls it makes</span><span class="i"><i></i>calls it receives</span></span>'
        "<p>Deployment targets hold service groups, each drawn as a container around its boxes. Connections are hidden until you hover over, focus or click a box, and pinning an object in one figure highlights it in the other.</p>"
        + figure_html(render_deployment_svg(dm), FIGURE_IDS[1])
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
        "Generated from the catalog; the same catalog always produces the same page.</footer>"
    )
    parts.append(f"</div><script>{JS}</script></body></html>")
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


@dataclass
class LogicalLayout:
    pos: dict[str, tuple[int, int]] = field(default_factory=dict)  # uid -> top-left, multiples of GRID
    bands: list[tuple[str, int, int, int]] = field(default_factory=list)  # band, y, height, width
    lane: tuple[int, int, int, int] | None = None  # x, y, width, height of the outside lane
    order: list[list[str]] = field(default_factory=list)  # uid order of each drawn band
    band_names: list[str] = field(default_factory=list)  # band of each entry in order
    lane_order: list[str] = field(default_factory=list)
    gutters: list[int] = field(default_factory=list)  # x of each vertical channel between box columns
    lane_gutter: int | None = None  # x of the vertical channel left of the outside lane
    width: int = 0
    height: int = 0


def layout_logical(model: DiagramModel) -> LogicalLayout:
    """Band rows top to bottom (D4), barycentre order (D14), outside lane at the right edge (D5)."""
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
    step_x = LOGICAL_BOX_W + LOGICAL_COL_GAP
    step_y = LOGICAL_BOX_H + LOGICAL_ROW_GAP
    used = min(LOGICAL_COLUMNS, max((len(layer) for layer in layout.order), default=1))
    main_w = used * LOGICAL_BOX_W + (used - 1) * LOGICAL_COL_GAP
    x0 = LOGICAL_MARGIN + LOGICAL_LABEL_W
    layout.gutters = [x0 - 15 + k * step_x for k in range(used + 1)]
    y = LOGICAL_MARGIN
    for band, layer in zip(names, layout.order):
        rows = -(-len(layer) // LOGICAL_COLUMNS)
        height = rows * LOGICAL_BOX_H + (rows - 1) * LOGICAL_ROW_GAP + 2 * LOGICAL_BAND_PAD
        layout.bands.append((band, y, height, LOGICAL_LABEL_W + main_w + LOGICAL_BAND_PAD))
        for i, uid in enumerate(layer):
            row, col = divmod(i, LOGICAL_COLUMNS)
            layout.pos[uid] = (x0 + col * step_x, y + LOGICAL_BAND_PAD + row * step_y)
        y += height + LOGICAL_BAND_GAP
    main_bottom = y - LOGICAL_BAND_GAP if layout.bands else LOGICAL_MARGIN
    right = x0 + main_w + LOGICAL_BAND_PAD if layout.bands else LOGICAL_MARGIN + LOGICAL_LABEL_W
    bottom = main_bottom
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

        layout.lane_order = apply_positions([n.uid for n in sorted(outer, key=lane_key)], model.logical_positions)
        lane_x = x0 + main_w + LOGICAL_LANE_GAP
        layout.lane_gutter = lane_x - 20
        top = LOGICAL_MARGIN
        for i, uid in enumerate(layout.lane_order):
            layout.pos[uid] = (lane_x, top + LOGICAL_LANE_HEAD + i * step_y)
        lane_h = LOGICAL_LANE_HEAD + len(outer) * LOGICAL_BOX_H + (len(outer) - 1) * LOGICAL_ROW_GAP + LOGICAL_BAND_PAD
        layout.lane = (lane_x - LOGICAL_BAND_PAD, top, LOGICAL_BOX_W + 2 * LOGICAL_BAND_PAD, lane_h)
        right = lane_x + LOGICAL_BOX_W + LOGICAL_BAND_PAD
        bottom = max(bottom, top + lane_h)
    layout.width = right + LOGICAL_MARGIN
    layout.height = bottom + LOGICAL_MARGIN
    return layout


def _fit_lines(text: str, width: int, limit: int) -> list[str]:
    lines = wrap(clean(text), width)
    if len(lines) > limit:
        lines = lines[:limit]
        lines[-1] += "..."
    return [line if len(line) <= width + 3 else line[: width - 1] + "..." for line in lines]


def _route_edges(model: DiagramModel, layout: LogicalLayout) -> dict[int, list[tuple[int, int]]]:
    """Orthogonal route per edge (index in model.edges), travelling only in the channels between boxes.

    An edge leaves its source through the top or bottom side, runs along the gap between box rows to a
    vertical channel between columns, follows it, and enters its target the same way, so it never
    crosses a box that is not one of its endpoints. Attachment points, gap lanes and channel lanes are
    spread by edge order so edges do not overlap. Everything is integer arithmetic keyed on uid and
    edge order.
    """
    pos = layout.pos
    lane_uids = set(layout.lane_order)
    drawn = [
        (i, e) for i, e in enumerate(model.edges) if e.source != e.target and e.source in pos and e.target in pos
    ]
    sides: dict[int, tuple[str, str]] = {}
    slots: dict[tuple[str, str], list[tuple[int, str, int]]] = {}
    for i, e in drawn:
        a, b = pos[e.source], pos[e.target]
        sa = "bottom" if b[1] > a[1] else "top"
        sb = "top" if b[1] > a[1] else ("bottom" if b[1] < a[1] else "top")
        sides[i] = (sa, sb)
        slots.setdefault((e.source, sa), []).append((pos[e.target][0], e.target, i))
        slots.setdefault((e.target, sb), []).append((pos[e.source][0], e.source, i))
    half = LOGICAL_BOX_W // 2
    offset: dict[tuple[int, str], int] = {}  # (edge index, uid) -> x offset from the box centre
    for (uid, _side), items in slots.items():
        items.sort()
        for rank, (_x, _other, i) in enumerate(items):
            shift = (160 * (rank + 1)) // (len(items) + 1) // GRID * GRID - 80
            offset[(i, uid)] = shift
    routes: dict[int, list[tuple[int, int]]] = {}
    for i, e in drawn:
        a, b = pos[e.source], pos[e.target]
        sa, sb = sides[i]
        ax, bx = a[0] + half + offset[(i, e.source)], b[0] + half + offset[(i, e.target)]
        track = i % 2
        ga = a[1] + LOGICAL_BOX_H + 5 + 5 * track if sa == "bottom" else a[1] - 5 - 5 * track
        gb = b[1] + LOGICAL_BOX_H + 5 + 5 * track if sb == "bottom" else b[1] - 5 - 5 * track
        if e.source in lane_uids or e.target in lane_uids:
            options = ([layout.gutters[-1]] if layout.gutters else []) + [layout.lane_gutter]
            if e.source in lane_uids and e.target in lane_uids:
                options = [layout.lane_gutter]
        else:
            options = layout.gutters
        gx = min(options, key=lambda g: (abs(ax - g) + abs(bx - g), g)) + (i % 3 - 1) * 10
        raw = [
            (ax, a[1] + LOGICAL_BOX_H if sa == "bottom" else a[1]),
            (ax, ga),
            (gx, ga),
            (gx, gb),
            (bx, gb),
            (bx, b[1] + LOGICAL_BOX_H if sb == "bottom" else b[1]),
        ]
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
    ".lb.hov{display:none}"
    ".edge:hover .lb.hov,.edge.on .lb.hov{display:inline}"
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


def _polyline_mid(pts: list) -> tuple:
    """The point halfway along an orthogonal polyline, by length; edge labels sit there."""
    total = sum(abs(bx - ax) + abs(by - ay) for (ax, ay), (bx, by) in zip(pts, pts[1:]))
    if total == 0:
        return pts[0]
    half = total / 2
    walked = 0.0
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        seg = abs(bx - ax) + abs(by - ay)
        if seg and walked + seg >= half:
            t = (half - walked) / seg
            return (ax + (bx - ax) * t, ay + (by - ay) * t)
        walked += seg
    return pts[-1]


def _label_mid(pts: list, text_len: int, obstacles: list) -> tuple:
    """D13: the label anchor on a route, chosen so the label keeps clear of every obstacle.

    Obstacles are (x, y, w, h) rectangles: node boxes, band labels and the outside lane caption. Candidates are
    points at 50%, 25% and 75% along each segment, longest segment first, each tried on the line and 18 px
    either side of it. The first candidate that overlaps nothing wins. If none is clear, the candidate with the
    least overlap wins. A label is about 6.2 px per character and 14 px tall, drawn 4 px above its anchor.
    """
    width = text_len * 6.2 + 4
    order = sorted(range(len(pts) - 1), key=lambda i: (-(abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1])), i))
    best: tuple = ()
    for i in order:
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        for fraction in (0.5, 0.25, 0.75):
            cx = ax + (bx - ax) * fraction
            for shift in (0, 18, -18):
                cy = ay + (by - ay) * fraction + shift
                x0, y0 = cx - width / 2, cy - 13
                area = 0.0
                for ox, oy, ow, oh in obstacles:
                    area += max(0.0, min(x0 + width, ox + ow) - max(x0, ox)) * max(0.0, min(y0 + 14, oy + oh) - max(y0, oy))
                if area == 0:
                    return (cx, cy)
                if not best or area < best[0]:
                    best = (area, (cx, cy))
    return best[1] if best else _polyline_mid(pts)


def _label_len(edge: DiagramEdge) -> int:
    """Characters drawn for an edge label: the label, a separator and the technology."""
    return len(clean(edge.label)) + (len(clean(edge.technology)) + 3 if clean(edge.technology) else 0)


def _edge_label(edge: DiagramEdge, mid: tuple, cls: str) -> str:
    """Label, then the recorded technology in a lighter weight (D13). Empty when neither is recorded."""
    label, tech = clean(edge.label), clean(edge.technology)
    if not label and not tech:
        return ""
    body = xml_text(label) if label else ""
    if tech:
        body += '<tspan class="tech">' + (" / " if label else "") + xml_text(tech) + "</tspan>"
    return f'<text class="{cls}" x="{mid[0]:.1f}" y="{mid[1] - 4:.1f}" text-anchor="middle">{body}</text>'


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
    shown = [e for e in model.edges if e.source in layout.pos and e.target in layout.pos]
    label_cls = "lb hov" if len(shown) > LABEL_LIMIT else "lb"  # D13: more than 8 edges, labels on hover or pin
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
    for number, edge in enumerate(model.edges):
        s, t = edge.source, edge.target
        if s not in layout.pos or t not in layout.pos:
            continue
        tip = xml_text(f"{by_uid[s].name} {edge.label or '(no label recorded)'} {by_uid[t].name}")
        head = f'<g class="edge" data-from="{xml_text(s)}" data-to="{xml_text(t)}"><title>{tip}</title>'
        cls, marks = _edge_marks(edge, "lg")
        if s == t:  # a self-relationship: a small loop off the top-right corner
            x, y = layout.pos[s]
            grow = 14 * loops.get(s, 0)
            loops[s] = loops.get(s, 0) + 1
            path = _loop_path(x, y, grow)
            mid = (x + LOGICAL_BOX_W * 0.8, y - 26 - grow)
        else:
            pts = routes[number]
            path = "M" + " L".join(f"{px} {py}" for px, py in pts)
            mid = _label_mid(pts, _label_len(edge), obstacles)
        out.append(f'{head}<path class="{cls}" d="{path}"{marks}/>{_flow_overlay(path, edge.flow)}{_edge_label(edge, mid, label_cls)}</g>')
    for uid in [u for names in layout.order for u in names] + layout.lane_order:
        x, y = layout.pos[uid]
        out.append(_node_svg(by_uid[uid], x, y))
    out.append("</svg>")
    return "\n".join(out) + "\n"


DEPLOY_COLUMNS = 3  # boxes per row inside a zone lane
DEPLOY_PAD = 10
DEPLOY_COL_GAP = 60  # minimum gap between box columns; widened when self-loops would reach the next column
DEPLOY_LEVEL = 6  # distance between horizontal edge runs in a free band, and from the band's edges
DEPLOY_MIN_BAND = 24  # a free band that carries no edge run is still this tall
DEPLOY_BAND_SPARE = 2  # spare levels per band, for runs that must skip a level another run holds
DEPLOY_CHANNEL_PAD = 20  # from the stack's right border to the first vertical channel
DEPLOY_CHANNEL_STEP = 8  # between vertical channels
DEPLOY_LANE_GAP = 40  # from the last channel to the outside lane
DEPLOY_MAX_PASSES = 400  # safety net for the layout and routing fixed-point loop; every pass grows something, so
# the loop ends by itself (3 passes for the fixtures, about 25 for a pattern of 200 edges)
DEPLOY_SPREAD = 8  # between container ends that would otherwise share one border point
DEPLOY_MIN_STUB = 4  # a box side takes more stubs than fit this far apart only when the other side is full too
DEPLOY_BORDER_CLEAR = 4  # vertical edge runs keep at least this far from every container border
DEPLOY_SIDE_STEP = 5  # a container end on a left border steps this far out, between the group and target borders
LOOP_REACH = 36  # a self-loop reaches this far right of its box; each further loop on the same box adds LOOP_STEP
LOOP_RISE = 30  # and this far above it
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


def _fmt(value: Any) -> str:
    value = float(value)
    return str(int(value)) if value == int(value) else f"{value:.1f}"


@dataclass
class _Band:
    """A horizontal strip of free space between two rows of boxes, or two containers, that carries edge runs.

    ``upper`` ends belong to the element above the band (they leave through its bottom side) and take levels
    from the top of the band downward; ``lower`` ends belong to the element below and take levels from the
    bottom upward, above the ``rise`` reserved for that row's self-loops. ``rightward`` says which way runs
    leave the band: right toward the channels, or left from the outside lane toward them.
    """

    lo: int
    hi: int
    rise: int
    rightward: bool
    upper: list = field(default_factory=list)  # (sort x, edge index, uid)
    lower: list = field(default_factory=list)
    extra: int = 0  # levels added by the layout after a routing pass ran out of room here
    overflow: int = 0  # ends that found no free level in the last routing pass


def _band_height(cap: int, rise: int, extra: int = 0) -> int:
    return max(DEPLOY_MIN_BAND, DEPLOY_LEVEL * (cap + 2 + DEPLOY_BAND_SPARE + extra)) + rise


@dataclass
class _End:
    """One end of a routed edge: where it meets its box or container and which band carries its run."""

    uid: str
    side: str  # top, bottom, left or right
    x: Any  # stub x for a box end, border x for a container end
    y: Any  # border y the edge meets
    band: Any = None  # _Band, or None for a right-border container end, which runs straight to its channel
    level: Any = None  # y of the horizontal run, once allocated
    step_x: Any = None  # left-border container ends only: x of the short vertical outside the border


def _route_deployment_edges(
    drawn: list,
    rects: dict,
    pools: dict,
    containers: set,
    bands: list,
    loops: dict,
    stack_right: int,
    chan_pad: int,
) -> tuple[dict, int, dict]:
    """Comb routing (D15, deterministic): every edge runs out of the stack to a vertical channel on its right.

    A box end leaves through its top or bottom side (whichever faces the other endpoint) at its own x, runs
    along a level of the free band beside it to a channel, and the channel carries it to the other end's
    level. Channels lie right of every container and left of the outside lane, so no run crosses a box, and
    an edge shares a channel only with edges whose vertical spans are apart. A container end starts at the
    border_point toward the other endpoint (D29): top and bottom border ends use the band beside the
    container, a right border end runs straight to its channel, a left border end steps out between the
    group and target borders first. Within a band, ends are levelled so that a run never crosses another
    end's stub. Everything is keyed on edge document order and geometry; nothing else.

    Returns the polyline per edge index, the number of channels used, and the number of left-border ends per
    container (the layout widens the target's left padding to hold their verticals). A band that ran out of
    levels has ``overflow`` set; the layout grows it and routes again.
    """
    centre = {uid: (x + w / 2, y + h / 2) for uid, (x, y, w, h) in rects.items()}
    ends: dict[tuple[int, str], _End] = {}
    # Container ends: border_point toward the other endpoint, then spread coincident points along the border.
    attach: dict[tuple[int, str], tuple[float, float]] = {}
    for i, e in drawn:
        for uid, other in ((e.source, e.target), (e.target, e.source)):
            if uid in containers:
                x, y, w, h = rects[uid]
                toward = centre[other]
                if toward == centre[uid]:  # a box centred on its own container: the ray has no direction, so use "up"
                    toward = (toward[0], toward[1] - 1)
                attach[(i, uid)] = border_point(centre[uid], toward, w, h)
    # Ends on one border of one container are pushed DEPLOY_SPREAD apart along that border (edge order breaks
    # ties); a lone end keeps its exact border_point, and a cluster slides back as a whole when it meets a corner.
    # A border that cannot hold its ends that far apart hands the surplus to another border of the container.
    partner = {}
    for i, e in drawn:
        partner[(i, e.source)] = e.target
        partner[(i, e.target)] = e.source
    on_border: dict[tuple[str, str], list[tuple[float, int]]] = {}
    for (i, uid), (px, py) in sorted(attach.items()):
        x, y, w, h = rects[uid]
        if abs(py - y) < 1e-6 or abs(py - (y + h)) < 1e-6:
            on_border.setdefault((uid, "top" if abs(py - y) < 1e-6 else "bottom"), []).append((px, i))
        else:
            on_border.setdefault((uid, "left" if abs(px - x) < 1e-6 else "right"), []).append((py, i))

    def extent(uid: str, border: str) -> tuple[float, float]:
        x, y, w, h = rects[uid]
        low, high = (x + 4, x + w - 4) if border in ("top", "bottom") else (y + 4, y + h - 4)
        if loops.get(uid):  # D13: the container's own loop sits at its top-right corner; ends keep clear of it
            if border == "top":
                high = x + w - LOGICAL_BOX_W + int(LOGICAL_BOX_W * 0.62) - DEPLOY_SPREAD
            elif border == "right":
                low = y + int(LOGICAL_BOX_H * 0.3) + DEPLOY_SPREAD
        return low, high

    def capacity(uid: str, border: str) -> int:
        low, high = extent(uid, border)
        return max(1, int((high - low) // DEPLOY_SPREAD) + 1)

    for _pass in range(4):  # a receiving border may fill up too; the surplus moves on in a fixed order
        moved = False
        for (uid, border) in sorted(on_border):
            items = on_border[(uid, border)]
            room = capacity(uid, border)
            if len(items) <= room:
                continue
            items.sort()
            surplus = items[room:]
            del items[room:]
            x, y, w, h = rects[uid]
            for value, i in surplus:
                ocx, ocy = centre[partner[(i, uid)]]
                prefer = ("bottom", "top") if ocy > y + h / 2 else ("top", "bottom")
                for target in prefer + ("right", "left"):
                    if target != border and len(on_border.get((uid, target), [])) < capacity(uid, target):
                        low, high = extent(uid, target)
                        along = min(max(ocx if target in ("top", "bottom") else ocy, low), high)
                        on_border.setdefault((uid, target), []).append((along, i))
                        attach[(i, uid)] = {
                            "top": (along, y), "bottom": (along, y + h), "left": (x, along), "right": (x + w, along)
                        }[target]
                        moved = True
                        break
                else:
                    items.append((value, i))  # every border is full: this end stays where it was
        if not moved:
            break
    for (uid, border), items in sorted(on_border.items()):
        low, high = extent(uid, border)
        if len(items) < 2 and low <= items[0][0] <= high:
            continue  # a lone end keeps its exact border_point
        items.sort()
        placed = [max(low, items[0][0])]
        for value, _i in items[1:]:
            placed.append(max(value, placed[-1] + DEPLOY_SPREAD))
        slide = max(0, placed[-1] - high)  # a cluster past the far corner slides back as a whole ...
        placed = [v - slide for v in placed]
        for k in range(len(placed)):  # ... and ends that would pass the near corner are spread again from it
            placed[k] = max(placed[k], low if k == 0 else placed[k - 1] + DEPLOY_SPREAD)
        for (_value, i), v in zip(items, placed):
            px, py = attach[(i, uid)]
            attach[(i, uid)] = (v, py) if border in ("top", "bottom") else (px, v)
    # Box ends: the side facing the other endpoint; stub x by the other endpoint's x so stubs never cross.
    slots: dict[tuple[str, str], list[tuple[float, str, int]]] = {}
    left_ends: dict[str, list[tuple[int, float, int]]] = {}  # container uid -> (band order, border y, edge index)
    for i, e in drawn:
        for uid, other in ((e.source, e.target), (e.target, e.source)):
            if uid in containers:
                x, y, w, h = rects[uid]
                px, py = attach[(i, uid)]
                if abs(py - y) < 1e-6:
                    ends[(i, uid)] = _End(uid, "top", px, py, pools[uid]["top"])
                elif abs(py - (y + h)) < 1e-6:
                    ends[(i, uid)] = _End(uid, "bottom", px, py, pools[uid]["bottom"])
                elif abs(px - (x + w)) < 1e-6:
                    ends[(i, uid)] = _End(uid, "right", px, py, None)
                else:
                    side = "top" if centre[other][1] < centre[uid][1] else "bottom"
                    ends[(i, uid)] = _End(uid, side, px, py, pools[uid][side], step_x=x - DEPLOY_SIDE_STEP)
                    left_ends.setdefault(uid, []).append((0 if side == "top" else 1, py if side == "top" else -py, i))
            else:
                side = "top" if centre[other][1] <= centre[uid][1] else "bottom"
                slots.setdefault((uid, side), []).append((centre[other][0], other, i))
                ends[(i, uid)] = _End(uid, side, 0, 0, pools[uid][side])
    # Left-border ends of one container each take their own vertical: the end nearest its band is innermost,
    # so a run out to a farther vertical never crosses an inner end's vertical.
    for uid, items in left_ends.items():
        items.sort()
        for rank, (_order, _py, i) in enumerate(items):
            ends[(i, uid)].step_x = rects[uid][0] - DEPLOY_SIDE_STEP - DEPLOY_LEVEL * rank
    left_counts = {uid: len(items) for uid, items in left_ends.items()}
    def stub_span(uid: str, side: str) -> tuple[int, int]:
        x, _y, w, _h = rects[uid]
        if side == "top" and loops.get(uid):  # stay left of the self-loop, which starts at 62% of the width
            return x + 8, int(w * 0.6) - 16
        return x + w // 10, w - 2 * (w // 10)

    # A side holds at most span / DEPLOY_MIN_STUB ends before stubs merge visually; the ends beyond that (the
    # last in x order) leave through the box's other side instead and reach their channel through that band.
    for uid in sorted({uid for uid, _side in slots}):
        for side, other_side in (("top", "bottom"), ("bottom", "top")):
            items = slots.get((uid, side), [])
            room = stub_span(uid, side)[1] // DEPLOY_MIN_STUB - 1
            spare = stub_span(uid, other_side)[1] // DEPLOY_MIN_STUB - 1 - len(slots.get((uid, other_side), []))
            if len(items) > room and spare > 0:
                items.sort()
                moved = items[room:][:spare]
                del items[room : room + len(moved)]
                slots.setdefault((uid, other_side), []).extend(moved)
                for _ox, _other, i in moved:
                    ends[(i, uid)].side = other_side
                    ends[(i, uid)].band = pools[uid][other_side]
    for (uid, side), items in sorted(slots.items()):
        items.sort()
        x, y, w, h = rects[uid]
        left, span = stub_span(uid, side)
        for rank, (_ox, _other, i) in enumerate(items):
            end = ends[(i, uid)]
            end.x = left + Fraction(span * (rank + 1), len(items) + 1)
            end.y = y if side == "top" else y + h
    # Channels: first fit by document order over a span that covers both ends' bands, so the exact vertical
    # runs chosen later are always apart on a shared channel.
    channels: list[list[tuple[float, float]]] = []
    chan_of: dict[int, int] = {}
    for i, e in drawn:
        lo, hi = math.inf, -math.inf
        for uid in (e.source, e.target):
            if uid in containers:
                lo, hi = min(lo, pools[uid]["top"].lo), max(hi, pools[uid]["bottom"].hi)
            else:
                band = ends[(i, uid)].band
                lo, hi = min(lo, band.lo), max(hi, band.hi)
        for k, spans in enumerate(channels):
            if all(hi + DEPLOY_LEVEL <= a or b + DEPLOY_LEVEL <= lo for a, b in spans):
                spans.append((lo, hi))
                chan_of[i] = k
                break
        else:
            channels.append([(lo, hi)])
            chan_of[i] = len(channels) - 1
    chan_x = {i: stack_right + chan_pad + DEPLOY_CHANNEL_STEP * k for i, k in chan_of.items()}
    # Levels. Right-border runs are fixed by geometry and go first; band levels then avoid them, and the
    # outside lane's bands avoid the stack's, so two runs within DEPLOY_LEVEL in y are always apart in x.
    taken: list[tuple[float, float, float]] = []  # (y, x0, x1) of every horizontal run so far

    def clear(y: float, x0: float, x1: float) -> bool:
        """No run closer than DEPLOY_LEVEL in y overlaps x0..x1 within DEPLOY_LEVEL."""
        return all(abs(y - ty) >= DEPLOY_LEVEL or x1 + DEPLOY_LEVEL <= a or b + DEPLOY_LEVEL <= x0 for ty, a, b in taken)

    for (i, uid), end in sorted(ends.items()):
        if end.side == "right":
            end.level = end.y
            taken.append((end.y, end.x, chan_x[i]))
        else:
            if end.step_x is not None:  # the short step out of a left border is a horizontal run too
                taken.append((end.y, end.step_x, end.x))
            pool = end.band.lower if end.side == "top" else end.band.upper
            pool.append((end.x if end.step_x is None else end.step_x, i, uid))
    for band in bands:
        deepest = band.lo  # the upper pool's lowest level; the lower pool stays below it so stubs never interleave
        for pool, from_top in ((band.upper, True), (band.lower, False)):
            pool.sort(key=lambda item: ((-item[0] if band.rightward else item[0]), item[1]))
            k = 0
            for sort_x, i, uid in pool:
                end = ends[(i, uid)]
                run_x = end.x if end.step_x is None else end.step_x
                x0, x1 = (run_x, chan_x[i]) if band.rightward else (chan_x[i], run_x)
                first = band.lo + DEPLOY_LEVEL if from_top else band.hi - band.rise - DEPLOY_LEVEL
                last = band.hi - band.rise - DEPLOY_LEVEL if from_top else deepest + DEPLOY_LEVEL
                level = first
                while True:
                    level = first + (DEPLOY_LEVEL * k if from_top else -DEPLOY_LEVEL * k)
                    k += 1
                    beyond = level > last if from_top else level < last
                    if beyond:  # out of room: take the last level and tell the layout to grow this band
                        level = last
                        band.overflow += 1
                        break
                    if clear(level, x0, x1):
                        break
                end.level = level
                taken.append((level, x0, x1))
                if from_top:
                    deepest = max(deepest, level)
    routes: dict[int, list[tuple[float, float]]] = {}
    for i, e in drawn:
        cx = chan_x[i]

        def leg(end: _End) -> list[tuple[float, float]]:
            if end.side == "right":
                return [(end.x, end.y), (cx, end.y)]
            if end.step_x is not None:
                return [(end.x, end.y), (end.step_x, end.y), (end.step_x, end.level), (cx, end.level)]
            return [(end.x, end.y), (end.x, end.level), (cx, end.level)]

        raw = leg(ends[(i, e.source)]) + list(reversed(leg(ends[(i, e.target)])))
        pts: list[tuple[float, float]] = []
        for point in raw:
            if not pts or pts[-1] != point:
                pts.append(point)
        routes[i] = pts
    return routes, len(channels), left_counts


def render_deployment_svg(model: DiagramModel, order_out: dict[str, list[str]] | None = None) -> str:
    """The deployment pattern figure: target -> group container -> zone lanes -> boxes (D6).

    Edges are plain solid orthogonal routes (S7 styles them) from the boxes and containers to vertical
    channels right of the stack; see _route_deployment_edges. Container text is wrapped to its container
    and the container grows to hold it. Free bands between rows, between groups and around the outside
    lane's boxes are sized for the edge ends they may carry. Deterministic (D15).
    """
    by_uid = {n.uid: n for n in model.deployment_nodes}
    outline = _deployment_outline(model)
    containers = {g.uid for _t, groups in outline for g in groups if g.uid}
    drawable = set(by_uid) | containers
    drawn = [(i, e) for i, e in enumerate(model.edges) if e.source != e.target and e.source in drawable and e.target in drawable]
    incident: dict[str, int] = {}
    loops: dict[str, int] = {}
    for _i, e in drawn:
        incident[e.source] = incident.get(e.source, 0) + 1
        incident[e.target] = incident.get(e.target, 0) + 1
    for e in model.edges:
        if e.source == e.target and (e.source in by_uid or e.source in containers):
            loops[e.source] = loops.get(e.source, 0) + 1
    most_loops = max([n for uid, n in loops.items() if uid in by_uid], default=0)  # box loops size lanes and columns
    container_loops = max([n for uid, n in loops.items() if uid in containers], default=0)
    # A container's loop (D13) sits at its top-right corner and reaches past the target border; the channels start
    # beyond its reach.
    chan_pad = max(DEPLOY_CHANNEL_PAD, LOOP_REACH + LOOP_STEP * (container_loops - 1) + DEPLOY_LEVEL) if container_loops else DEPLOY_CHANNEL_PAD

    def inc(uids: list) -> int:
        return sum(incident.get(u, 0) for u in uids)

    def rise(uids: list) -> int:
        return max([LOOP_RISE + LOOP_STEP * (loops[u] - 1) for u in uids if loops.get(u)], default=0)

    loop_room = (LOOP_REACH + LOOP_STEP * (most_loops - 1) + 4 - DEPLOY_PAD) if most_loops else 0
    col_gap = max(DEPLOY_COL_GAP, LOOP_REACH + LOOP_STEP * (most_loops - 1) + 10) if most_loops else DEPLOY_COL_GAP
    col_gap = -(-col_gap // GRID) * GRID  # D14: box x on the grid
    step_x = LOGICAL_BOX_W + col_gap
    lane_sizes = [len(lane.members) for _t, groups in outline for g in groups for lane in g.lanes]
    used = min(DEPLOY_COLUMNS, max(lane_sizes, default=1))
    inner_w = used * LOGICAL_BOX_W + (used - 1) * col_gap
    lane_w = inner_w + 2 * DEPLOY_PAD + loop_room
    group_w = lane_w + 2 * DEPLOY_PAD

    def build_stack(left_room: int, extras: list) -> tuple:
        """Lay out the stack and the outside lane's rows.

        left_room widens the targets' left padding (on the D14 grid) so every left-border container end has its
        own vertical; extras[k] adds levels to the k-th band created, after a routing pass ran out of room there
        (see _route_deployment_edges). Bands are created in the same order on every call.
        """
        target_w = group_w + 2 * DEPLOY_PAD + left_room
        bands: list[_Band] = []
        rects: dict[str, tuple[int, int, int, int]] = {}  # uid -> x, y, w, h of a box or the first container with that uid
        pools: dict[str, dict[str, _Band]] = {}
        names: dict[str, str] = {n.uid: n.name for n in model.deployment_nodes}
        pos: dict[str, tuple[int, int]] = {}
        body: list[str] = []

        def band_at(lo: int, cap: int, rise_px: int, rightward: bool = True) -> _Band:
            extra = extras[len(bands)] if len(bands) < len(extras) else 0
            hi = -(-(lo + _band_height(cap, rise_px, extra)) // GRID) * GRID  # D14: the row below starts on the grid
            band = _Band(lo=lo, hi=hi, rise=rise_px, rightward=rightward, extra=extra)
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
                band = band_at(cursor, inc([prev_uid, g.uid]), rise([g.uid]) if g.uid not in rects else 0)
                if prev_uid and prev_uid in pools and "bottom" not in pools[prev_uid]:
                    pools[prev_uid]["bottom"] = band
                gy = band.hi
                n_lines = _wrap_to(g.group, group_w)
                c_lines = _wrap_to(g.caption, group_w)
                g_head = 18 + DEPLOY_LINE_H * (len(n_lines) - 1) + 20 + DEPLOY_LINE_H * (len(c_lines) - 1) + 12
                gx = tx + DEPLOY_PAD + left_room
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
                    for row in rows:
                        above = band_at(cursor2, inc(prev_row + row), rise(row))
                        for uid in prev_row:
                            if uid in pools and "bottom" not in pools[uid]:
                                pools[uid]["bottom"] = above
                        row_top = above.hi
                        for col, uid in enumerate(row):
                            bx = lx + DEPLOY_PAD + col * step_x
                            if uid in by_uid and uid not in pos:
                                pos[uid] = (bx, row_top)
                                rects[uid] = (bx, row_top, LOGICAL_BOX_W, LOGICAL_BOX_H)
                                pools[uid] = {"top": above}
                                node_svgs.append(_node_svg(by_uid[uid], bx, row_top))
                        cursor2 = row_top + LOGICAL_BOX_H
                        prev_row = row
                    below = band_at(cursor2, inc(prev_row), 0)
                    for uid in prev_row:
                        if uid in pools and "bottom" not in pools[uid]:
                            pools[uid]["bottom"] = below
                    lane_h = below.hi - ly
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
            tail_band = band_at(cursor, inc([last_uid]), 0)
            if last_uid and last_uid in pools and "bottom" not in pools[last_uid]:
                pools[last_uid]["bottom"] = tail_band
            target_h = tail_band.hi - ty
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
                above = band_at(cursor, inc(prev + [node.uid]), rise([node.uid]), rightward=False)
                for uid in prev:
                    pools[uid]["bottom"] = above
                lane_rows.append((node, above.hi))
                pools[node.uid] = {"top": above}
                cursor = above.hi + LOGICAL_BOX_H
                prev = [node.uid]
            below = band_at(cursor, inc(prev), 0, rightward=False)
            pools[prev[0]]["bottom"] = below
            lane_h = below.hi - lane_top
        return bands, rects, pools, names, pos, body, stack_bottom, stack_right, lane_rows, lane_top, lane_h, outer

    # Layout and routing depend on each other in three small ways: the outside lane's x follows the channel
    # count, several left-border ends on one container need a wider left padding, and a band may run out of
    # levels when it has to dodge runs from the other column. Iterate to a fixed point (every step only grows
    # something, so it ends); the loop is a pure function of the catalog, so the result is deterministic. Each
    # pass is cheap, so the cap is only a safety net.
    left_room, extras, n_channels = 0, [], len(drawn)
    for _attempt in range(DEPLOY_MAX_PASSES):
        laid = build_stack(left_room, extras)
        bands, rects, pools, names, pos, body, stack_bottom, stack_right, lane_rows, lane_top, lane_h, outer = laid
        last_channel = stack_right + chan_pad + DEPLOY_CHANNEL_STEP * (n_channels - 1) if n_channels else stack_right
        lane_x = -(-(last_channel + DEPLOY_LANE_GAP) // GRID) * GRID  # D14
        for node, by in lane_rows:
            rects[node.uid] = (lane_x, by, LOGICAL_BOX_W, LOGICAL_BOX_H)
            pos[node.uid] = (lane_x, by)
        routes, used, left_counts = _route_deployment_edges(drawn, rects, pools, containers, bands, loops, stack_right, chan_pad)
        need = max(left_counts.values(), default=0)
        room = -(-(DEPLOY_LEVEL * (need - 1)) // GRID) * GRID if need > 1 else 0
        grown = [band.extra + band.overflow for band in bands]
        if used == n_channels and room == left_room and not any(band.overflow for band in bands):
            break
        n_channels, left_room, extras = used, room, grown
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
    loop_count: dict[str, int] = {}
    deploy_obstacles = [rects[u] for u in by_uid if u in rects]  # D13: boxes, then the outside lane caption
    if outer:
        deploy_obstacles.append((lane_x, lane_top + 15, len("External interactions") * 7 + 4, 12))
    shown = [e for e in model.edges if e.source in rects and e.target in rects]
    label_cls = "lb hov" if len(shown) > LABEL_LIMIT else "lb"  # D13: more than 8 edges, labels on hover or pin
    for number, edge in enumerate(model.edges):
        s, t = edge.source, edge.target
        if s not in rects or t not in rects:
            continue
        tip = xml_text(f"{names.get(s, s)} {edge.label or '(no label recorded)'} {names.get(t, t)}")
        head = f'<g class="edge" data-from="{xml_text(s)}" data-to="{xml_text(t)}"><title>{tip}</title>'
        cls, marks = _edge_marks(edge, "dp")
        if s == t:  # D13: the existing loop, off the top-right corner of the box or of the container
            grow = LOOP_STEP * loop_count.get(s, 0)
            loop_count[s] = loop_count.get(s, 0) + 1
            rx, ry, rw, _rh = rects[s]
            x0 = rx + rw - LOGICAL_BOX_W
            path = _loop_path(x0, ry, grow)
            mid = (x0 + LOGICAL_BOX_W * 0.8, ry - 26 - grow)
        else:
            pts = routes[number]
            path = "M" + " L".join(f"{_fmt(px)} {_fmt(py)}" for px, py in pts)
            mid = _label_mid(pts, _label_len(edge), deploy_obstacles)
        edges.append(f'{head}<path class="{cls}" d="{path}"{marks}/>{_flow_overlay(path, edge.flow)}{_edge_label(edge, mid, label_cls)}</g>')
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


def build(workspace: Path, selector: str | None, placed_only: bool = False) -> tuple[str, Model]:
    return build_from_catalog(load_catalog(workspace), selector, placed_only)


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
                out["deployment"].append(apply_positions(lane.members, dm.deployment_positions))
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


def write_layout(workspace: Path, model: Model) -> Path:
    """D40: write or update the pattern's diagram_layout file; no other file is touched. Returns its path."""
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
        page, model = build(args.workspace, args.sdp, args.placed_only)
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
            layout_path = write_layout(args.workspace, model)
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
