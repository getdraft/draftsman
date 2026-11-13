#!/usr/bin/env python3
"""Render a DRAFT Software Deployment Pattern as a visual diagram page.

Usage:
    python3 framework/tools/generate_diagram.py --list [--workspace PATH]
    python3 framework/tools/generate_diagram.py --sdp NAME_OR_UID [--workspace PATH]
        [--output FILE] [--placed-only]

The generator reads the DRAFT catalog and writes one self-contained HTML page
(inline SVG, no external requests, light and dark themes). It is deterministic:
the same catalog always produces the same page.

What is drawn comes only from the catalog:

* One zone per service group of the Software Deployment Pattern, labelled with
  the group's recorded ``deploymentTarget``; zones that share a target are
  stacked in the same column.
* One box per deployable object placed in a service group.
* One arrow per ``relationship`` object whose source and target are both drawn.
  A component with no recorded relationship gets no arrow. Nothing is inferred.
* Components that are not placed in any service group but have a recorded
  relationship are drawn in a separate "not placed" column, never in a zone.

By default the scope is the objects placed in the pattern plus each direct relationship
endpoint (one hop) of a placed object whose type is a component, data, data store, runtime,
network, AI gateway or host object. ``--placed-only`` restricts the drawing to placed objects.
Derived ``runs on`` relationships never extend the scope.

Below the figure the page lists every relationship, the pattern's recorded
characteristics, open questions from Drafting Sessions that target the pattern,
and an inventory of every in-scope object with its catalog fields as recorded.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from generate_c4 import DEFAULT_WORKSPACE_ROOT, load_catalog  # noqa: E402

E = html.escape

CHIP_W = 190
CHIP_H = 46
GAP = 12
ZONE_HEAD = 34
ZONE_PAD = 12
ZONE_GAP = 18
BAND_GUTTER = 90
MARGIN = 24
MAX_COLS = 3
MAX_BAND_COLUMNS = 3  # deployment-target bands are packed into at most this many page columns
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


# D2: object types that may appear one hop away from a placed object.
ONE_HOP_TYPES = frozenset(
    {"product_component", "data_component", "data_store_service", "runtime_service", "network_service", "ai_gateway", "host"}
)

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
        self._read_groups()
        self._other_patterns = _other_pattern_names(catalog, sdp)
        self._build_nodes_and_edges()
        self._build_containers()
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
            # D29: a service group's drawn container is never also a box in the deployment view.
            return [node for node in self._nodes if node.uid not in self.container_uids]
        raise ValueError(f"unknown view: {view!r}")

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
                for near, far in ((source, target), (target, source)):
                    if near in placed and far and far not in placed and catalog.get(far, {}).get("type") in ONE_HOP_TYPES:
                        outside.add(far)
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
            dependency = is_dependency(rel)
            edge = DiagramEdge(
                source=source,
                target=end,
                label=clean(rel.get("label")),
                derived=dependency,
                uid=str(rel.get("uid", "")),
                origin="inline dependency" if dependency else "relationship object",
                direction=str(rel.get("direction") or ""),
                flow=str(rel.get("flow") or ""),
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
        # First pass (D29): every container uid is known before any group's boxes are filtered, so a
        # substrate placed in another group is never drawn as a box or lane member anywhere.
        planned = [group["substrate"] or self._derive_substrate(group["uids"]) for group in self.groups]
        self.container_uids = {uid for uid in planned if uid and uid in catalog}
        for group in self.groups:
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
            members = [uid for uid in group["uids"] if uid not in self.container_uids]
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


class Layout:
    def __init__(self, model: Model):
        self.model = model
        self.pos: dict[str, tuple[float, float]] = {}  # uid -> top-left
        self.zones: list[dict[str, Any]] = []
        self.width = 0.0
        self.height = 0.0
        self._build()

    def _band_cols(self, groups: list[dict[str, Any]]) -> int:
        biggest = max((len(g["uids"]) for g in groups), default=1)
        return 3 if biggest >= 7 else 2 if biggest >= 3 else 1

    def _build(self) -> None:
        bands: dict[str, list[dict[str, Any]]] = {}
        for group in self.model.groups:
            if group["uids"]:
                bands.setdefault(group["target"], []).append(group)
        band_list: list[tuple[str, list[dict[str, Any]]]] = list(bands.items())
        if self.model.unplaced_drawn:
            band_list.append(
                ("", [{"name": "Not placed in a service group", "target": "", "uids": self.model.unplaced_drawn, "unplaced": True}])
            )
        def rows_for(groups: list[dict[str, Any]], cols: int) -> int:
            return sum(math.ceil(len(g["uids"]) / cols) for g in groups)

        def est_height(groups: list[dict[str, Any]]) -> float:
            cols = self._band_cols(groups)
            return sum(
                ZONE_HEAD + math.ceil(len(g["uids"]) / cols) * (CHIP_H + GAP) + ZONE_PAD + ZONE_GAP for g in groups
            )

        n_columns = max(1, min(MAX_BAND_COLUMNS, len(band_list)))
        heights = [0.0] * n_columns
        assigned: list[list[tuple[int, list[dict[str, Any]]]]] = [[] for _ in range(n_columns)]
        for index, (_target, groups) in sorted(enumerate(band_list), key=lambda p: -est_height(p[1][1])):
            slot = heights.index(min(heights))
            assigned[slot].append((index, groups))
            heights[slot] += est_height(groups)
        columns = sorted((sorted(col) for col in assigned if col), key=lambda col: col[0][0])
        x = float(MARGIN)
        for column in columns:
            cols = max(self._band_cols(groups) for _i, groups in column)
            col_w = cols * CHIP_W + (cols - 1) * GAP + 2 * ZONE_PAD
            y = float(MARGIN)
            for _i, groups in column:
                for group in groups:
                    n = len(group["uids"])
                    rows = math.ceil(n / cols)
                    zone_h = ZONE_HEAD + rows * CHIP_H + (rows - 1) * GAP + ZONE_PAD
                    self.zones.append(
                        {"x": x, "y": y, "w": col_w, "h": zone_h, "name": group["name"], "target": group["target"],
                         "unplaced": bool(group.get("unplaced"))}
                    )
                    for i, uid in enumerate(group["uids"]):
                        r, c = divmod(i, cols)
                        self.pos[uid] = (x + ZONE_PAD + c * (CHIP_W + GAP), y + ZONE_HEAD + r * (CHIP_H + GAP))
                    y += zone_h + ZONE_GAP
            self.height = max(self.height, y - ZONE_GAP + MARGIN)
            x += col_w + BAND_GUTTER
        self.width = max(x - BAND_GUTTER + MARGIN, 2 * MARGIN + CHIP_W)

    def center(self, uid: str) -> tuple[float, float]:
        x, y = self.pos[uid]
        return x + CHIP_W / 2, y + CHIP_H / 2


def border_point(c: tuple[float, float], toward: tuple[float, float]) -> tuple[float, float]:
    dx, dy = toward[0] - c[0], toward[1] - c[1]
    if dx == 0 and dy == 0:
        return c
    t = min((CHIP_W / 2) / abs(dx) if dx else math.inf, (CHIP_H / 2) / abs(dy) if dy else math.inf)
    return c[0] + dx * t, c[1] + dy * t


# --------------------------------------------------------------------------- svg
def render_svg(model: Model, layout: Layout) -> str:
    zones, edges, chips, labels = [], [], [], []
    for z in layout.zones:
        cls = "zone un" if z["unplaced"] else "zone"
        zones.append(f'<rect class="{cls}" x="{z["x"]:.0f}" y="{z["y"]:.0f}" width="{z["w"]:.0f}" height="{z["h"]:.0f}" rx="8"/>')
        labels.append(f'<text class="zl" x="{z["x"] + 12:.0f}" y="{z["y"] + 16:.0f}">{E(z["name"])}</text>')
        if z["target"]:
            labels.append(f'<text class="zt" x="{z["x"] + 12:.0f}" y="{z["y"] + 29:.0f}">{E(z["target"])}</text>')
        elif not z["unplaced"]:
            labels.append(f'<text class="zt" x="{z["x"] + 12:.0f}" y="{z["y"] + 29:.0f}">deployment target not recorded</text>')
    show_labels = len(model.relationships) <= LABEL_LIMIT
    seen: dict[tuple[str, str], int] = {}
    for rel in model.relationships:
        s, t = rel["source"], rel["target"]
        if s not in layout.pos or t not in layout.pos:
            continue
        key = tuple(sorted((s, t)))
        index = seen.get(key, 0)
        seen[key] = index + 1
        if s == t:
            # A recorded self-relationship: a small loop off the top-right corner of the box.
            x, y = layout.pos[s]
            grow = 14.0 * index
            p1 = (x + CHIP_W * 0.62, y)
            p2 = (x + CHIP_W, y + CHIP_H * 0.3)
            c1 = (p1[0], y - 34 - grow)
            c2 = (x + CHIP_W + 36 + grow, p2[1])
            path = f"M{p1[0]:.1f} {p1[1]:.1f} C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
            loop_label = clean(rel.get("label"))
            tip = f"{model.name(s)} {loop_label or '(no label recorded)'} {model.name(t)} (self-relationship)"
            edges.append(
                f'<g class="edge" data-from="{E(s)}" data-to="{E(t)}"><title>{E(tip)}</title>'
                f'<path class="ln" d="{path}" marker-end="url(#ar)"/></g>'
            )
            if loop_label:
                hide = "" if show_labels else " hov"
                labels.append(
                    f'<text class="lb{hide}" data-from="{E(s)}" data-to="{E(t)}" x="{x + CHIP_W * 0.8:.1f}" '
                    f'y="{y - 28 - grow:.1f}" text-anchor="middle">{E(loop_label)}</text>'
                )
            continue
        cs, ct = layout.center(s), layout.center(t)
        bend = 0.0 if index == 0 else 26.0 * index * (1 if s < t else -1)
        mid = ((cs[0] + ct[0]) / 2, (cs[1] + ct[1]) / 2)
        dx, dy = ct[0] - cs[0], ct[1] - cs[1]
        length = math.hypot(dx, dy) or 1.0
        ctrl = (mid[0] - dy / length * bend, mid[1] + dx / length * bend)
        p1 = border_point(cs, ctrl if bend else ct)
        p2 = border_point(ct, ctrl if bend else cs)
        path = f"M{p1[0]:.1f} {p1[1]:.1f} Q{ctrl[0]:.1f} {ctrl[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}" if bend else f"M{p1[0]:.1f} {p1[1]:.1f} L{p2[0]:.1f} {p2[1]:.1f}"
        label = clean(rel.get("label"))
        tip = f"{model.name(s)} {label or '(no label recorded)'} {model.name(t)}"
        edges.append(
            f'<g class="edge" data-from="{E(s)}" data-to="{E(t)}"><title>{E(tip)}</title>'
            f'<path class="ln" d="{path}" marker-end="url(#ar)"/></g>'
        )
        if label:
            lx = (p1[0] + 2 * ctrl[0] + p2[0]) / 4 if bend else (p1[0] + p2[0]) / 2
            ly = (p1[1] + 2 * ctrl[1] + p2[1]) / 4 if bend else (p1[1] + p2[1]) / 2
            hide = "" if show_labels else " hov"
            labels.append(
                f'<text class="lb{hide}" data-from="{E(s)}" data-to="{E(t)}" x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">{E(label)}</text>'
            )
    for uid, (x, y) in layout.pos.items():
        obj = model.catalog[uid]
        life = lifecycle(obj)
        cls = "box"
        if life == "retired":
            cls += " ret"
        elif life == "deprecated":
            cls += " dep"
        if uid not in model.placement:
            cls += " un"
        lines = wrap(str(obj.get("name", uid)), int((CHIP_W - 16) / 6.0))[:2]
        count = len(lines) + 1
        y0 = y + CHIP_H / 2 - (count - 1) * 6.5 + 3.5
        text = "".join(
            f'<text class="ttl" x="{x + CHIP_W / 2:.1f}" y="{y0 + i * 13:.1f}" text-anchor="middle">{E(line)}</text>'
            for i, line in enumerate(lines)
        )
        text += f'<text class="sub" x="{x + CHIP_W / 2:.1f}" y="{y0 + len(lines) * 13:.1f}" text-anchor="middle">{E(model.sub(uid))}</text>'
        chips.append(
            f'<g class="node" data-id="{E(uid)}" tabindex="0"><title>{E(clean(obj.get("description"))[:300])}</title>'
            f'<rect class="{cls}" x="{x:.0f}" y="{y:.0f}" width="{CHIP_W}" height="{CHIP_H}" rx="6"/>{text}</g>'
        )
    defs = (
        '<defs><marker id="ar" viewBox="0 0 8 7" refX="8" refY="3.5" markerWidth="8" markerHeight="7" '
        'markerUnits="userSpaceOnUse" orient="auto"><polygon class="mk" points="0,0 8,3.5 0,7"/></marker></defs>'
    )
    aria = (
        f"{model.sdp.get('name', 'Deployment pattern')}: {len(layout.pos)} objects in "
        f"{len(layout.zones)} groups with {len(model.relationships)} recorded relationships."
    )
    return (
        f'<svg id="fig" viewBox="0 0 {layout.width:.0f} {layout.height:.0f}" role="img" aria-label="{E(aria)}">'
        + defs + "".join(zones) + "".join(edges) + "".join(chips) + "".join(labels) + "</svg>"
    )


# --------------------------------------------------------------------------- html parts
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
        tech = " · ".join(str(x) for x in (obj.get("language"), obj.get("runtimeRequirement")) if x)
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
            f'<td>{E(row["to"])}</td><td class="ds">{E(row["description"])}</td></tr>'
        )
    return "".join(out)


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
    for obj in model.catalog.values():
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


CSS = """
:root{--bg:#f5f7fa;--fg:#1a2230;--muted:#586374;--surface:#fff;--line:#aab4c2;--zone:#eaeff5;--zone-line:#9aa6b6;--accent:#0b62c4;--amber:#a85a00;--warn:#9a3412}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0e131a;--fg:#e4e9f0;--muted:#97a2b3;--surface:#18202b;--line:#4a586b;--zone:#121923;--zone-line:#3c485a;--accent:#5fadff;--amber:#f2a64e;--warn:#fb923c;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0e131a;--fg:#e4e9f0;--muted:#97a2b3;--surface:#18202b;--line:#4a586b;--zone:#121923;--zone-line:#3c485a;--accent:#5fadff;--amber:#f2a64e;--warn:#fb923c;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:28px max(16px,env(safe-area-inset-right,0px)) 56px max(16px,env(safe-area-inset-left,0px))}
.wrap{max-width:1280px;margin:0 auto;display:flex;flex-direction:column;gap:30px}
h1{font-size:26px;line-height:1.2;margin:0;font-weight:600}h2{font-size:17px;margin:0 0 4px;font-weight:600}
.lede,.sec>p,.cap{color:var(--muted);max-width:76ch;font-size:14px;margin:6px 0 12px}
.counts{display:flex;flex-wrap:wrap;gap:6px 22px;font-size:13.5px}.counts b{font-variant-numeric:tabular-nums}
.legend{display:flex;flex-wrap:wrap;gap:8px 20px;font-size:13px;color:var(--muted);margin-bottom:12px}.legend span{display:inline-flex;align-items:center;gap:8px}
.legend i{display:inline-block;width:26px;border-top:2px solid var(--line)}
.legend b{display:inline-block;width:22px;height:14px;border:1.5px solid var(--line);border-radius:3px;background:var(--surface)}
.legend b.r{border-style:dashed;opacity:.8}.legend b.d{border-style:dashed;border-color:var(--amber)}.legend b.u{border-color:var(--accent)}
.scroll,.tw{overflow-x:auto;border:1px solid var(--zone-line);border-radius:6px;background:var(--surface)}
svg{display:block;width:100%;min-width:760px;height:auto;color:var(--fg)}svg text{fill:currentColor;font-family:inherit}
.box{fill:var(--surface);stroke:var(--line);stroke-width:1.4}.box.ret{stroke-dasharray:5 3;opacity:.78}.box.dep{stroke-dasharray:5 3;stroke:var(--amber)}.box.un{stroke:var(--accent)}
.zone{fill:var(--zone);stroke:var(--zone-line);stroke-width:1.1;stroke-dasharray:6 4}.zone.un{stroke:var(--accent)}
.ttl{font-size:11.5px;font-weight:600}.sub,.zt{fill:var(--muted)!important;font-size:10px}.zl{fill:var(--muted)!important;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;font-weight:600}
.ln{stroke:var(--line);stroke-width:1.6;fill:none}.mk{fill:var(--line)}.edge{opacity:.7}
.lb{font-size:10.5px;fill:var(--muted)!important;paint-order:stroke;stroke:var(--zone);stroke-width:4px;stroke-linejoin:round}.lb.hov{display:none}
.node{cursor:pointer}.node:focus-visible rect{outline:2px solid var(--accent)}
svg.focus .edge,svg.focus .node,svg.focus .lb{opacity:.15}
svg.focus .edge.on,svg.focus .node.on,svg.focus .lb.on{opacity:1}
svg.focus .edge.on .ln{stroke:var(--accent);stroke-width:2.4}svg.focus .lb.on{display:block;fill:var(--accent)!important}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--zone-line)}
th{background:var(--zone);font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);white-space:nowrap}tr:last-child td{border-bottom:0}
td.nm{font-weight:600;white-space:nowrap}td.lbl{color:var(--accent);white-space:nowrap}td.ds{min-width:320px;color:var(--muted)}td.src{font:11px ui-monospace,Menlo,monospace;color:var(--muted);white-space:nowrap}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;border:1px solid var(--zone-line);font-size:11.5px;white-space:nowrap}
.pill.ret{color:var(--muted);border-style:dashed}.pill.dep{color:var(--amber);border-color:var(--amber)}.pill.open{color:var(--warn);border-color:var(--warn)}
.tools{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:10px}.tools input,.tools select{font:inherit;font-size:13.5px;padding:7px 10px;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--fg);min-width:0}.tools input{flex:1 1 240px;max-width:360px}
dl.facts{margin:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:10px}
.fact{border:1px solid var(--zone-line);border-radius:6px;padding:10px 12px;background:var(--surface);min-width:0}.fact dt{font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);font-weight:600;margin-bottom:3px}.fact dd{margin:0;font-size:13.5px;overflow-wrap:anywhere}
ul.q{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px;max-width:90ch}ul.q li{border:1px solid var(--zone-line);border-radius:6px;padding:10px 12px;background:var(--surface);font-size:13.5px}.ans{color:var(--muted);margin-top:6px;font-size:13px}
"""

JS = """
(function(){
 var svg=document.getElementById('fig');if(svg){
  var nodes=[].slice.call(svg.querySelectorAll('.node')),edges=[].slice.call(svg.querySelectorAll('.edge')),labs=[].slice.call(svg.querySelectorAll('.lb')),pinned=null;
  function show(id){
   if(!id){svg.classList.remove('focus');[].concat(nodes,edges,labs).forEach(function(n){n.classList.remove('on')});return}
   svg.classList.add('focus');var near={};near[id]=1;
   function on(el){var a=el.getAttribute('data-from'),b=el.getAttribute('data-to'),hit=a===id||b===id;if(hit){near[a]=1;near[b]=1}el.classList.toggle('on',hit)}
   edges.forEach(on);labs.forEach(on);nodes.forEach(function(n){n.classList.toggle('on',!!near[n.getAttribute('data-id')])});
  }
  nodes.forEach(function(n){var id=n.getAttribute('data-id');
   n.addEventListener('mouseenter',function(){if(!pinned)show(id)});n.addEventListener('mouseleave',function(){if(!pinned)show(null)});
   n.addEventListener('focus',function(){if(!pinned)show(id)});n.addEventListener('blur',function(){if(!pinned)show(null)});
   n.addEventListener('click',function(){pinned=pinned===id?null:id;show(pinned)});
   n.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();pinned=pinned===id?null:id;show(pinned)}});
  });
 }
 var q=document.getElementById('q'),lf=document.getElementById('lf'),pf=document.getElementById('pf'),cnt=document.getElementById('cnt');
 var rows=[].slice.call(document.querySelectorAll('#inv tbody tr'));
 function run(){var t=q.value.toLowerCase(),l=lf.value,p=pf.value,n=0;rows.forEach(function(r){var ok=(!t||r.textContent.toLowerCase().indexOf(t)>-1)&&(!l||r.dataset.life===l)&&(!p||r.dataset.placed===p);r.hidden=!ok;if(ok)n++});cnt.textContent=n+' of '+rows.length+' shown'}
 q.addEventListener('input',run);lf.addEventListener('change',run);pf.addEventListener('change',run);run();
})();
"""


def render_page(model: Model, layout: Layout) -> str:
    sdp = model.sdp
    placed = len(model.placement)
    unplaced = len([u for u in model.scope if u in model.catalog and u not in model.placement])
    retired = sum(1 for u in model.scope if u in model.catalog and lifecycle(model.catalog[u]) == "retired")
    facts = facts_html(model)
    questions = questions_html(model)
    parts = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
        f"<title>{E(str(sdp.get('name', 'Deployment pattern')))} Architecture</title><style>{CSS}</style></head><body><div class=\"wrap\">",
        f"<header><h1>{E(str(sdp.get('name', 'Deployment pattern')))} Architecture</h1>",
        '<p class="lede">Generated from the DRAFT catalog. Each box, arrow and row comes from a catalog object. '
        "An object with no recorded relationship has no arrow, and nothing is inferred.</p>",
        '<div class="counts">'
        f"<span><b>{len(layout.pos)}</b> objects drawn</span><span><b>{placed}</b> placed in a service group</span>"
        f"<span><b>{unplaced}</b> in scope but not placed</span><span><b>{retired}</b> retired</span>"
        f"<span><b>{len(model.relationship_rows)}</b> recorded relationships</span></div></header>",
        '<section class="sec"><h2>Deployment topology</h2>'
        "<p>Zones are the service groups of the deployment pattern, labelled with their recorded deployment target. "
        "Hover or focus a box to highlight its relationships; click to pin.</p>",
        '<div class="legend"><span><i></i>Recorded relationship</span><span><b></b>Placed in a service group</span>'
        '<span><b class="u"></b>Has a relationship but is not placed</span><span><b class="r"></b>Retired</span>'
        '<span><b class="d"></b>Deprecated</span></div>',
        (
            f'<div class="scroll">{render_svg(model, layout)}</div>'
            if layout.pos
            else "<p>No objects are placed in a service group and no recorded relationship connects an object, so there is nothing to draw.</p>"
        )
        + empty_groups_html(model)
        + "</section>",
    ]
    if model.relationship_rows:
        parts.append(
            '<section class="sec"><h2>Recorded relationships</h2><div class="tw"><table><thead><tr>'
            "<th>From</th><th>Relationship</th><th>To</th><th>Description</th></tr></thead><tbody>"
            f"{relationship_rows(model)}</tbody></table></div></section>"
        )
    else:
        parts.append('<section class="sec"><h2>Recorded relationships</h2><p>No relationship objects connect these objects.</p></section>')
    if facts:
        parts.append(f'<section class="sec"><h2>Recorded characteristics</h2><p>Quoted from the deployment pattern.</p><dl class="facts">{facts}</dl></section>')
    if questions:
        parts.append(f'<section class="sec"><h2>Open questions on record</h2><ul class="q">{questions}</ul></section>')
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
    parts.append(f"</div><script>{JS}</script></body></html>")
    return "".join(parts)


# --------------------------------------------------------------------------- stubs
def build_diagram_model(catalog: dict[str, dict[str, Any]], sdp: dict[str, Any], placed_only: bool) -> DiagramModel:
    """The two-view model for one pattern: logical nodes, edges, service group containers and warnings."""
    model = Model(catalog, sdp, placed_only)
    return DiagramModel(
        sdp_uid=str(sdp.get("uid", "")),
        nodes=model.nodes_for_view("logical"),
        edges=list(model.edges),
        containers=list(model.containers),
        warnings=list(model.warnings),
    )


def render_logical_svg(model: DiagramModel) -> str:
    raise NotImplementedError("enabled in S5")


def render_deployment_svg(model: DiagramModel) -> str:
    raise NotImplementedError("enabled in S6")


# --------------------------------------------------------------------------- cli
def build_from_catalog(catalog: dict[str, dict[str, Any]], selector: str | None, placed_only: bool = False) -> tuple[str, Model]:
    """Public seam (D16c): render one pattern from an already loaded catalog dict.

    Until S8 the page is the legacy page.
    """
    sdp = pick_sdp(catalog, selector)
    model = Model(catalog, sdp, placed_only)
    return render_page(model, Layout(model)), model


def build(workspace: Path, selector: str | None, placed_only: bool = False) -> tuple[str, Model]:
    return build_from_catalog(load_catalog(workspace), selector, placed_only)


def slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-") or "diagram"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a DRAFT deployment pattern as a visual diagram page.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE_ROOT, help="Workspace root containing catalog/.")
    parser.add_argument("--sdp", help="Deployment pattern name, alias or uid. Optional when only one exists.")
    parser.add_argument("--output", type=Path, help="Output HTML file. Default: <slug>-architecture.html in the current directory.")
    parser.add_argument("--placed-only", action="store_true", help="Limit scope to objects placed in a service group.")
    parser.add_argument("--list", action="store_true", help="List deployment patterns and exit.")
    args = parser.parse_args(argv)
    if not (args.workspace / "catalog").is_dir():
        print(f"error: no catalog/ directory under workspace {args.workspace}", file=sys.stderr)
        return 2
    if args.list:
        for pattern in sdps(load_catalog(args.workspace)):
            print(f"{pattern.get('uid')}\t{pattern.get('name')}")
        return 0
    try:
        page, model = build(args.workspace, args.sdp, args.placed_only)
    except ValueError as exc:  # D32: a malformed pattern is reported, not traced
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for warning in model.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    output = args.output or Path(f"{slug(str(model.sdp.get('name', 'diagram')))}-architecture.html")
    replaced = output.exists()
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(page, encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write {output}: {exc.strerror or exc}", file=sys.stderr)
        return 1
    note = "; replaced the existing file" if replaced else ""
    print(f"Wrote {output} ({len(model.relationships)} relationships, {len(model.scope)} objects in scope){note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
