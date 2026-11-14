from __future__ import annotations

import contextlib
import hashlib
import inspect
import io
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.dom.minidom
from pathlib import Path

import yaml

from framework.tools import generate_diagram
from generate_c4 import load_catalog
from tests import diagram_harness as harness

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "diagram_workspace"
# Edge crossings allowed in the large logical figure (AC14). Set from the first committed golden; lower only on purpose.
# Raised from 869 to 873 by S12 (D35): the old router hid crossings in 96 collinear overlaps between 73 distinct pairs
# of co-visible edges drawn on top of each other (collinear runs count as no crossing); D35 forbids that, so those
# edges now cross on separate tracks.
LARGE_MAX_CROSSINGS = 873


def edge_polylines(svg: str) -> list:
    """(from uid, to uid, [(x, y), ...]) for every routed edge; self-loop curves are skipped."""
    found = []
    for match in re.finditer(r'<g class="edge" data-from="([^"]*)" data-to="([^"]*)"><title>[^<]*</title><path class="ln[^"]*" d="(M[-\d. L]+)"[^>]*/>', svg):
        numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", match.group(3))]
        found.append((match.group(1).replace("&amp;", "&"), match.group(2).replace("&amp;", "&"), list(zip(numbers[0::2], numbers[1::2]))))
    return found


def count_crossings(svg: str) -> int:
    """Proper crossings between segments of edges that do not share a node."""
    segments = []
    for source, target, pts in edge_polylines(svg):
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            segments.append(({source, target}, (ax, ay, bx, by)))

    def side(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

    total = 0
    for i, (ends_a, (ax, ay, bx, by)) in enumerate(segments):
        for ends_b, (cx, cy, dx, dy) in segments[i + 1 :]:
            if ends_a & ends_b:
                continue
            d1, d2 = side(ax, ay, bx, by, cx, cy), side(ax, ay, bx, by, dx, dy)
            d3, d4 = side(cx, cy, dx, dy, ax, ay), side(cx, cy, dx, dy, bx, by)
            if d1 * d2 < 0 and d3 * d4 < 0:
                total += 1
    return total


def edges_hitting_foreign_boxes(svg: str) -> list:
    """Edges with a segment that passes through the interior of a box that is not one of its endpoints."""
    rects = node_rects(svg)
    hits = []
    for source, target, pts in edge_polylines(svg):
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            lo_x, hi_x, lo_y, hi_y = min(ax, bx), max(ax, bx), min(ay, by), max(ay, by)
            for uid, (x, y, w, h) in rects.items():
                if uid in (source, target):
                    continue
                if lo_x < x + w and x < hi_x and lo_y < y + h and y < hi_y or (
                    lo_x == hi_x and x < lo_x < x + w and lo_y < y + h and y < hi_y
                ) or (lo_y == hi_y and y < lo_y < y + h and lo_x < x + w and x < hi_x):
                    hits.append((source, target, uid))
    return hits


def endpoint_rects(svg: str) -> dict:
    """uid -> (x, y, w, h) of every box, and of every drawn container (its first rectangle) in a deployment SVG."""
    rects = dict(node_rects(svg))
    for m in re.finditer(r'<g class="group[^"]*" data-id="([^"]*)"[^>]*>.*?<rect class="grp" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg, re.S):
        rects.setdefault(xml_unescape(m.group(1)), tuple(int(m.group(k)) for k in range(2, 6)))
    return rects


def _line_of(a: tuple, b: tuple):
    """(axis, coordinate, lo, hi) of an axis-parallel segment of positive length, else None."""
    if a[0] == b[0] and a[1] != b[1]:
        return ("v", a[0], min(a[1], b[1]), max(a[1], b[1]))
    if a[1] == b[1] and a[0] != b[0]:
        return ("h", a[1], min(a[0], b[0]), max(a[0], b[0]))
    return None


def _common_prefix(p: list, q: list) -> list:
    """The polyline two routes share from their first point until they part (D36: the shared run of a bundle)."""
    if not p or not q or p[0] != q[0]:
        return []
    out, cur, i, j = [p[0]], p[0], 0, 0
    while i + 1 < len(p) and j + 1 < len(q):
        lp, lq = abs(p[i + 1][0] - cur[0]) + abs(p[i + 1][1] - cur[1]), abs(q[j + 1][0] - cur[0]) + abs(q[j + 1][1] - cur[1])
        if lp == 0:
            i += 1
            continue
        if lq == 0:
            j += 1
            continue
        dp = ((p[i + 1][0] - cur[0]) / lp, (p[i + 1][1] - cur[1]) / lp)
        dq = ((q[j + 1][0] - cur[0]) / lq, (q[j + 1][1] - cur[1]) / lq)
        if dp != dq:
            break
        step = min(lp, lq)
        cur = (cur[0] + dp[0] * step, cur[1] + dp[1] * step)
        out.append(cur)
        i += lp == step
        j += lq == step
    return out


def _covered(line: tuple, path: list) -> bool:
    """Whether the overlap ``line`` lies on the polyline ``path``."""
    axis, coord, lo, hi = line
    spans = sorted(
        (seg[2], seg[3]) for seg in (_line_of(a, b) for a, b in zip(path, path[1:])) if seg and seg[0] == axis and seg[1] == coord
    )
    reach = None
    for a, b in spans:
        if reach is None or a > reach[1]:
            reach = [a, b]
        else:
            reach[1] = max(reach[1], b)
        if reach[0] <= lo and hi <= reach[1]:
            return True
    return False


def covisible_track_clashes(svg: str) -> list:
    """D35: pairs of co-visible edges (sharing an endpoint uid) with collinear runs that overlap, outside the part
    of their routes a fan bundle shares (D36: the common start of two edges of one source, the common end of two
    edges of one target). Horizontal runs that share a y over an overlapping x span, and vertical runs that share an
    x over an overlapping y span, both count."""
    edges = edge_polylines(svg)
    clashes = []
    for n, (s1, t1, p1) in enumerate(edges):
        for s2, t2, p2 in edges[n + 1 :]:
            if not {s1, t1} & {s2, t2}:
                continue
            prefix = _common_prefix(p1, p2) if s1 == s2 else []
            suffix = _common_prefix(p1[::-1], p2[::-1]) if t1 == t2 else []
            for a, b in zip(p1, p1[1:]):
                one = _line_of(a, b)
                for c, d in zip(p2, p2[1:]):
                    two = _line_of(c, d)
                    if not one or not two or one[:2] != two[:2]:
                        continue
                    lo, hi = max(one[2], two[2]), min(one[3], two[3])
                    if hi <= lo:
                        continue
                    shared = (one[0], one[1], lo, hi)
                    if not (_covered(shared, prefix) or _covered(shared, suffix)):
                        clashes.append((s1, t1, s2, t2, shared))
    return clashes


def covisible_stub_crossings(svg: str, free_x: list) -> list:
    """D35, D36: a horizontal run of one edge that crosses a vertical of a co-visible edge (sharing an endpoint uid),
    where the vertical is not inside one of the free x ranges ``free_x`` (gutters and channels, which runs cross by
    design): a box's stub or the drop of an edge into the next row."""
    edges = edge_polylines(svg)
    out = []
    for n1, (s1, t1, p1) in enumerate(edges):
        for (ax, ay), (bx, by) in zip(p1, p1[1:]):
            if ay != by:
                continue
            x0, x1 = min(ax, bx), max(ax, bx)
            for n2, (s2, t2, p2) in enumerate(edges):
                if n2 == n1 or not {s1, t1} & {s2, t2}:
                    continue
                for (cx, cy), (dx, dy) in zip(p2, p2[1:]):
                    if cx == dx and not any(lo < cx < hi for lo, hi in free_x) and x0 < cx < x1 and min(cy, dy) < ay < max(cy, dy):
                        out.append((s1, t1, s2, t2, (cx, ay)))
    return out


def logical_free_x(catalog: dict, uid: str) -> list:
    """The gutters of a logical figure, as x ranges."""
    layout = generate_diagram.layout_logical(generate_diagram.build_diagram_model(catalog, catalog[uid], False))
    return [(left, left + width) for left, width in layout.spaces]


def side_violations(svg: str) -> list:
    """D36: edges whose first point is not on the bottom side of the source, whose last point is not on the top side
    of the target, or whose first or last segment does not run downward."""
    rects = endpoint_rects(svg)
    bad = []
    for source, target, pts in edge_polylines(svg):
        sx, sy, sw, sh = rects[source]
        tx, ty, tw, _th = rects[target]
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        if not (abs(y0 - (sy + sh)) < 0.11 and sx <= x0 <= sx + sw and pts[1][1] > y0):
            bad.append((source, target, "start", pts[0]))
        if not (abs(y1 - ty) < 0.11 and tx <= x1 <= tx + tw and pts[-2][1] < y1):
            bad.append((source, target, "end", pts[-1]))
    return bad


def logical_svg(catalog: dict, uid: str, placed_only: bool = False) -> str:
    model = generate_diagram.build_diagram_model(catalog, catalog[uid], placed_only)
    return generate_diagram.render_logical_svg(model)


def deployment_svg(catalog: dict, uid: str, placed_only: bool = False) -> str:
    model = generate_diagram.build_diagram_model(catalog, catalog[uid], placed_only)
    return generate_diagram.render_deployment_svg(model)


def xml_escape(text: str) -> str:
    return generate_diagram.xml_text(text)


def xml_unescape(text: str) -> str:
    import html

    return html.unescape(text)


def node_rects(svg: str) -> dict:
    """uid -> (x, y, w, h) of each node box in a logical SVG."""
    found = {}
    for match in re.finditer(r'<g class="node[^"]*" data-id="([^"]*)">.*?<rect class="box" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg):
        found[match.group(1).replace("&amp;", "&")] = tuple(int(match.group(i)) for i in range(2, 6))
    return found


def write_workspace(root: Path, objects: list[dict]) -> Path:
    catalog = root / "catalog"
    catalog.mkdir(parents=True)
    for index, obj in enumerate(objects):
        (catalog / f"obj-{index}.yaml").write_text(yaml.safe_dump(obj), encoding="utf-8")
    return root


def component(uid: str, name: str, **extra: object) -> dict:
    return {
        "schemaVersion": "1.0",
        "uid": uid,
        "type": "product_component",
        "name": name,
        "description": f"{name} description",
        "owner": {"team": "team-a"},
        **extra,
    }


def pattern(refs_by_group: dict[str, list[str]]) -> dict:
    return {
        "schemaVersion": "1.0",
        "uid": "SDP-1",
        "type": "software_deployment_pattern",
        "name": "Demo Pattern",
        "description": "demo",
        "owner": {"team": "team-a"},
        "serviceGroups": [
            {"name": name, "deploymentTarget": "azure", "deployableObjects": [{"ref": r} for r in refs]}
            for name, refs in refs_by_group.items()
        ],
    }


def relationship(uid: str, source: str, target: str, label: str) -> dict:
    return {"schemaVersion": "1.0", "uid": uid, "type": "relationship", "name": uid, "source": source, "target": target, "label": label}


def svg_of(page: str) -> str:
    match = re.search(r"<svg.*?</svg>", page, re.S)
    assert match, "page has no svg"
    return match.group(0)


def figure_of(page: str, fig_id: str) -> str:
    """The inline SVG of one figure of the page, by its element id (D19)."""
    match = re.search(r'<svg id="' + fig_id + r'".*?</svg>', page, re.S)
    assert match, f"page has no figure {fig_id}"
    return match.group(0)


def logical_of(page: str) -> str:
    return figure_of(page, "fig-logical")


def node_count(svg: str) -> int:
    return len(re.findall(r'<g class="node[ "]', svg))


def svg_for(objects: list, view: str = "logical", uid: str = "SDP-1") -> str:
    with tempfile.TemporaryDirectory() as tmp:
        catalog = load_catalog(write_workspace(Path(tmp), objects))
        return logical_svg(catalog, uid) if view == "logical" else deployment_svg(catalog, uid)


def data_ids(svg: str) -> set:
    """Every data-id attribute of an element in the SVG, parsed as XML."""
    doc = xml.dom.minidom.parseString(svg)
    return {el.getAttribute("data-id") for el in doc.getElementsByTagName("g") if el.getAttribute("data-id")}


def class_of(svg: str, uid: str) -> str:
    """The class attribute of the node or group element whose data-id is uid."""
    match = re.search(r'<g class="((?:node|group)[^"]*)"[^>]*data-id="' + re.escape(uid) + '"', svg)
    assert match, f"no element with data-id {uid}"
    return match.group(1)


def edge_classes(svg: str) -> dict:
    """(from, to) -> class attribute of the edge path, for edges whose pair is unique in the figure."""
    return {
        (s, t): cls
        for s, t, cls in re.findall(r'<g class="edge" data-from="([^"]*)" data-to="([^"]*)"><title>[^<]*</title><path class="([^"]*)"', svg)
    }


def edge_paths(svg: str) -> dict:
    """(from, to) -> the path's attribute text after d, which holds the arrowhead markers."""
    return {
        (s, t): attrs
        for s, t, attrs in re.findall(
            r'<g class="edge" data-from="([^"]*)" data-to="([^"]*)"><title>[^<]*</title><path class="[^"]*" d="[^"]*"([^>]*)/>', svg
        )
    }


ALLOWED_ONE_HOP = [
    "product_component",
    "data_component",
    "data_store_service",
    "runtime_service",
    "network_service",
    "ai_gateway",
    "host",
]
FIXTURE_SDP = "FXSDP00001-0001"


def named_pattern(uid: str, name: str, refs: list[str]) -> dict:
    """A pattern with one service group holding refs, under the given uid and name."""
    sdp = pattern({"G": refs})
    sdp["uid"] = uid
    sdp["name"] = name
    return sdp


def run_cli(argv: list[str]) -> tuple:
    """Run the CLI in process: (exit code, stdout, stderr). Usage errors (SystemExit) become their code."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = generate_diagram.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def plain(uid: str, obj_type: str, name: str, **extra: object) -> dict:
    return {"schemaVersion": "1.0", "uid": uid, "type": obj_type, "name": name, **extra}


def model_of(objects: list, placed_only: bool = False, selector=None) -> generate_diagram.Model:
    with tempfile.TemporaryDirectory() as tmp:
        _, model = generate_diagram.build(write_workspace(Path(tmp), objects), selector, placed_only=placed_only)
    return model


def fixture_model(placed_only: bool = False) -> generate_diagram.Model:
    catalog = load_catalog(FIXTURE)
    return generate_diagram.Model(catalog, catalog[FIXTURE_SDP], placed_only)


class GenerateDiagramTests(unittest.TestCase):
    def test_example_workspace_renders_valid_self_contained_page(self) -> None:
        page, model = generate_diagram.build(EXAMPLES, "OpenStack IaaS Platform")
        xml.dom.minidom.parseString(svg_of(page))
        self.assertIn("OpenStack IaaS Platform Architecture", page)
        # D43: every placed object here is infrastructure, so the logical view has nothing to draw and the
        # deployment view carries every edge.
        self.assertIn("nothing to draw", page)
        self.assertEqual(figure_of(page, "fig-deployment").count('<g class="edge"'), len(model.edges))
        catalog = load_catalog(EXAMPLES)
        deployment = deployment_svg(catalog, model.sdp["uid"])
        xml.dom.minidom.parseString(deployment)
        self.assertGreater(deployment.count('<g class="edge"'), 0)
        self.assertGreater(len(model.relationships), 0)
        self.assertNotRegex(page, r'(?:src|href)="https?://')

    def test_output_is_deterministic(self) -> None:
        first, _ = generate_diagram.build(EXAMPLES, "OpenStack IaaS Platform")
        second, _ = generate_diagram.build(EXAMPLES, "OpenStack IaaS Platform")
        self.assertEqual(first, second)

    def test_component_without_relationship_gets_no_arrow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(
                Path(tmp),
                [component("A-1", "Alpha"), component("B-1", "Beta"), pattern({"Group": ["A-1", "B-1"]})],
            )
            page, model = generate_diagram.build(workspace, None)
        self.assertEqual(model.relationships, [])
        self.assertEqual(page.count('class="edge"'), 0)
        self.assertEqual(node_count(logical_of(page)), 2)
        self.assertIn("No relationship objects connect these objects.", page)

    def test_relationship_draws_exactly_one_arrow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(
                Path(tmp),
                [
                    component("A-1", "Alpha"),
                    component("B-1", "Beta"),
                    pattern({"Group": ["A-1", "B-1"]}),
                    relationship("R-1", "A-1", "B-1", "calls"),
                ],
            )
            page, _ = generate_diagram.build(workspace, "Demo Pattern")
        self.assertEqual(logical_of(page).count('<g class="edge"'), 1)
        self.assertIn('data-from="A-1" data-to="B-1"', page)

    def test_unplaced_component_is_drawn_only_when_it_has_a_relationship(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(
                Path(tmp),
                [
                    component("A-1", "Alpha"),
                    component("U-1", "Linked Unplaced"),
                    component("U-2", "Lonely Unplaced"),
                    pattern({"Group": ["A-1"]}),
                    relationship("R-1", "A-1", "U-1", "calls"),
                ],
            )
            page, model = generate_diagram.build(workspace, None)
        svg = svg_of(page)
        self.assertIn("Linked Unplaced", svg)
        self.assertNotIn("Lonely Unplaced", svg)
        self.assertIn("not placed in any pattern", svg)  # D5 caption of the outside lane
        # One-hop scope (D2): an object with no relationship to a placed object is out of scope.
        self.assertNotIn("Lonely Unplaced", page)
        self.assertIn("Linked Unplaced", page)
        self.assertEqual(model.unplaced_drawn, ["U-1"])

    def _lane_model(self, extra: list, placed_only: bool = False) -> tuple:
        objects = [component("A-1", "Alpha"), pattern({"Group": ["A-1"]})] + extra
        with tempfile.TemporaryDirectory() as tmp:
            return generate_diagram.build(write_workspace(Path(tmp), objects), None, placed_only=placed_only)

    def test_edge_between_two_unplaced_objects_is_not_drawn_or_tabled(self) -> None:
        # AC24 / D41: U-1 is a dependency of A-1; U-2 is too; the U-1 to U-2 relationship is nobody's business here.
        page, model = self._lane_model(
            [
                component("U-1", "Dep One"),
                component("U-2", "Dep Two"),
                relationship("R-1", "A-1", "U-1", "uses"),
                relationship("R-2", "A-1", "U-2", "uses too"),
                relationship("R-3", "U-1", "U-2", "talks to"),
            ]
        )
        self.assertEqual(sorted((e.source, e.target) for e in model.edges), [("A-1", "U-1"), ("A-1", "U-2")])
        self.assertEqual(sorted(r["uid"] for r in model.relationship_rows), ["R-1", "R-2"])
        self.assertNotIn("talks to", page)
        self.assertIn("Dep One", page)
        self.assertIn("Dep Two", page)
        self.assertNotIn('data-from="U-1" data-to="U-2"', page)

    def test_consumer_is_not_drawn_listed_or_tabled(self) -> None:
        # AC25 / D42: C-1 only sources a relationship into a placed object.
        page, model = self._lane_model([component("C-1", "Caller Only"), component("U-1", "Dep One"), relationship("R-1", "C-1", "A-1", "calls"), relationship("R-2", "A-1", "U-1", "uses")])
        self.assertNotIn("Caller Only", page)
        self.assertNotIn("C-1", model.scope)
        self.assertEqual(model.unplaced_drawn, ["U-1"])
        self.assertEqual([r["uid"] for r in model.relationship_rows], ["R-2"])
        self.assertEqual([(e.source, e.target) for e in model.edges], [("A-1", "U-1")])
        self.assertIn("Dep One", page)

    def test_dependency_and_consumer_is_drawn_with_only_its_dependency_edge(self) -> None:
        page, model = self._lane_model([component("U-1", "Both Ways"), relationship("R-1", "A-1", "U-1", "uses"), relationship("R-2", "U-1", "A-1", "calls back")])
        self.assertEqual([(e.source, e.target, e.label) for e in model.edges], [("A-1", "U-1", "uses")])
        self.assertEqual([r["uid"] for r in model.relationship_rows], ["R-1"])
        self.assertIn("Both Ways", page)
        self.assertNotIn("calls back", page)

    def test_derived_dependency_enters_scope_and_derived_consumer_does_not(self) -> None:
        deps = {"runtimeSpec": {"dependencies": [{"ref": "U-1", "purpose": "reads"}]}}
        consumer = {"runtimeSpec": {"dependencies": [{"ref": "A-1", "purpose": "calls"}]}}
        page, model = self._lane_model([component("U-1", "Derived Dep"), component("C-1", "Derived Caller", **consumer)])
        self.assertNotIn("Derived Caller", page)
        self.assertEqual(model.edges, [])
        objects = [component("A-2", "Alpha Two", **deps), component("U-1", "Derived Dep"), pattern({"Group": ["A-2"]})]
        with tempfile.TemporaryDirectory() as tmp:
            page, model = generate_diagram.build(write_workspace(Path(tmp), objects), None)
        self.assertIn("Derived Dep", page)
        self.assertEqual([(e.source, e.target, e.origin) for e in model.edges], [("A-2", "U-1", "inline dependency")])

    def test_lane_caption_is_external_interactions(self) -> None:
        page, model = self._lane_model([component("U-1", "Dep One"), relationship("R-1", "A-1", "U-1", "uses")])
        self.assertEqual(page.count(">External interactions</text>"), 2)
        self.assertNotIn("Outside this pattern", page)

    def test_placed_only_has_no_lane_and_renders_identically_twice(self) -> None:
        extra = [component("U-1", "Dep One"), component("C-1", "Caller Only"), relationship("R-1", "A-1", "U-1", "uses"), relationship("R-2", "C-1", "A-1", "calls")]
        page, model = self._lane_model(extra, placed_only=True)
        self.assertNotIn("External interactions", page)
        self.assertNotIn("Dep One", page)
        self.assertEqual(self._lane_model(extra)[0], self._lane_model(extra)[0])

    def test_placed_only_excludes_unplaced_components(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(
                Path(tmp),
                [
                    component("A-1", "Alpha"),
                    component("U-1", "Linked Unplaced"),
                    pattern({"Group": ["A-1"]}),
                    relationship("R-1", "U-1", "A-1", "calls"),
                ],
            )
            page, model = generate_diagram.build(workspace, None, placed_only=True)
        self.assertEqual(model.relationships, [])
        self.assertNotIn("Linked Unplaced", page)
        self.assertEqual(model.undrawn_relationship_count, 1)

    def test_unknown_reference_is_a_warning_not_a_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(Path(tmp), [component("A-1", "Alpha"), pattern({"Group": ["A-1", "MISSING-1"]})])
            _, model = generate_diagram.build(workspace, None)
        # The placed component also gets a derived tier warning (D4); only the unknown uid is checked here.
        unknown = [w for w in model.warnings if "unknown uid" in w]
        self.assertEqual(len(unknown), 1)
        self.assertIn("MISSING-1", unknown[0])

    def test_text_is_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(
                Path(tmp),
                [component("A-1", "<script>alert(1)</script>"), pattern({"Group": ["A-1"]})],
            )
            page, _ = generate_diagram.build(workspace, None)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_multiple_patterns_require_a_selector(self) -> None:
        second = pattern({"Group": []})
        second["uid"], second["name"] = "SDP-2", "Other Pattern"
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(Path(tmp), [component("A-1", "Alpha"), pattern({"Group": ["A-1"]}), second])
            with self.assertRaises(SystemExit):
                generate_diagram.build(workspace, None)
            _, model = generate_diagram.build(workspace, "other pattern")
        self.assertEqual(model.sdp["uid"], "SDP-2")

    def test_cli_writes_output_and_list_prints_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "diagram.html"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = generate_diagram.main(["--workspace", str(EXAMPLES), "--sdp", "OpenStack IaaS Platform", "--output", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue(out.read_text(encoding="utf-8").startswith("<!doctype html>"))
            listing = io.StringIO()
            with contextlib.redirect_stdout(listing):
                generate_diagram.main(["--workspace", str(EXAMPLES), "--list"])
            self.assertIn("OpenStack IaaS Platform", listing.getvalue())


    def _build(self, objects, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            return generate_diagram.build(write_workspace(Path(tmp), objects), None, **kw)

    def test_self_relationship_is_drawn_as_a_visible_loop(self) -> None:
        page, model = self._build(
            [component("A-1", "Alpha"), pattern({"G": ["A-1"]}), relationship("R-1", "A-1", "A-1", "retries")]
        )
        svg = svg_of(page)
        xml.dom.minidom.parseString(svg)
        self.assertEqual(logical_of(page).count('<g class="edge"'), 1)
        self.assertIn("M", re.search(r'<path class="ln" d="([^"]+)"', svg).group(1))
        self.assertIn("retries", svg)
        self.assertNotIn("nan", svg.lower())

    def test_uid_in_two_groups_warns_and_draws_once(self) -> None:
        page, model = self._build([component("A-1", "Alpha"), pattern({"G1": ["A-1"], "G2": ["A-1"]})])
        self.assertEqual(node_count(logical_of(page)), 1)
        self.assertTrue(any("G1" in w and "G2" in w for w in model.warnings))

    def test_malformed_service_group_entries_warn(self) -> None:
        sdp = pattern({"G": ["A-1"]})
        sdp["serviceGroups"].append("not a mapping")
        sdp["serviceGroups"][0]["deployableObjects"].append({"name": "no ref"})
        _, model = self._build([component("A-1", "Alpha"), sdp])
        joined = " ".join(model.warnings)
        self.assertIn("not a mapping", joined)
        self.assertIn("without a ref", joined)

    def test_empty_target_and_missing_label_are_said_plainly(self) -> None:
        sdp = pattern({"G": ["A-1", "B-1"]})
        sdp["serviceGroups"][0]["deploymentTarget"] = ""
        page, _ = self._build(
            [component("A-1", "Alpha"), component("B-1", "Beta"), sdp, relationship("R-1", "A-1", "B-1", "")]
        )
        self.assertIn("deployment target not recorded", page)
        self.assertIn("no label recorded", page)

    def test_lifecycle_filter_offers_every_schema_value(self) -> None:
        page, _ = self._build([component("A-1", "Alpha"), pattern({"G": ["A-1"]})])
        for value in ("candidate", "preferred", "existing-only", "retired", "deprecated"):
            self.assertIn(f'<option value="{value}">{value}</option>', page)

    def test_facts_render_bools_lists_and_flag_unrenderable_values(self) -> None:
        sdp = pattern({"G": ["A-1"]})
        sdp["architectureNotes"] = {"multiRegion": False, "regions": ["east", "west"], "nested": [{"a": 1}]}
        page, _ = self._build([component("A-1", "Alpha"), sdp])
        self.assertIn("false", page)
        self.assertIn("east; west", page)
        self.assertIn("not shown on this page", page)

    def test_empty_pattern_renders(self) -> None:
        page, model = self._build([pattern({})])
        self.assertEqual(node_count(page), 0)
        self.assertEqual(len(model.scope), 0)

    def test_attribute_and_label_escaping(self) -> None:
        page, _ = self._build(
            [
                component("A-1", 'Al"><script>x</script>'),
                component("B-1", "Beta"),
                pattern({"G": ["A-1", "B-1"]}),
                relationship("R-1", "A-1", "B-1", '<img src=x onerror=y>'),
            ]
        )
        self.assertNotIn("<script>x", page)
        self.assertNotIn("<img src=x", page)

    def test_placed_only_with_team_scope_drops_unplaced(self) -> None:
        page, model = self._build(
            [
                component("A-1", "Alpha"),
                component("B-1", "Beta"),
                pattern({"G": ["A-1"]}),
                relationship("R-1", "A-1", "B-1", "calls"),
            ],
            placed_only=True,
        )
        self.assertEqual(node_count(logical_of(page)), 1)
        self.assertEqual(model.edges, [])
        self.assertEqual(model.undrawn_relationship_count, 1)

    def test_cli_errors_and_output_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(generate_diagram.main(["--workspace", str(Path(tmp) / "nope")]), 2)
            self.assertIn("catalog/", err.getvalue())
            workspace = write_workspace(Path(tmp) / "ws", [component("A-1", "Alpha"), pattern({"G": ["A-1"]})])
            out = Path(tmp) / "deep" / "dir" / "d.html"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(generate_diagram.main(["--workspace", str(workspace), "--output", str(out)]), 0)
                self.assertEqual(generate_diagram.main(["--workspace", str(workspace), "--output", str(out)]), 0)
            self.assertTrue(out.is_file())
            self.assertIn("replaced the existing file", buffer.getvalue())
            blocker = Path(tmp) / "file"
            blocker.write_text("x")
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = generate_diagram.main(["--workspace", str(workspace), "--output", str(blocker / "d.html")])
            self.assertEqual(code, 1)
            self.assertIn("cannot write", err.getvalue())


    def test_empty_group_and_empty_pattern_are_stated(self) -> None:
        sdp = pattern({"Full": ["A-1"], "Empty": []})
        page, _ = self._build([component("A-1", "Alpha"), sdp])
        self.assertIn("recorded with no objects to draw: Empty (azure)", page)
        page, _ = self._build([pattern({})])
        self.assertIn("nothing to draw", page)
        logical_section = page.split('<section class="sec" id="logical">')[1].split('<section class="sec" id="deployment">')[0]
        self.assertNotIn("<svg", logical_section)

    def test_non_string_notes_key_does_not_crash(self) -> None:
        sdp = pattern({"G": ["A-1"]})
        sdp["architectureNotes"] = {1: "one"}
        page, _ = self._build([component("A-1", "Alpha"), sdp])
        self.assertIn("one", page)

    def test_ambiguous_selector_errors_and_uid_wins(self) -> None:
        a, b = pattern({"G": []}), pattern({"G": []})
        b["uid"], b["name"] = "SDP-2", "Demo Pattern"
        with tempfile.TemporaryDirectory() as tmp:
            ws = write_workspace(Path(tmp), [a, b])
            with self.assertRaises(SystemExit):
                generate_diagram.build(ws, "Demo Pattern")
            _, model = generate_diagram.build(ws, "SDP-2")
            self.assertEqual(model.sdp["uid"], "SDP-2")

REGISTRY_SDP = "FXSDP00002-0001"
INFRA_FIXTURE_UIDS = ("FXNET00002-0001", "FXDST00002-0001", "FXDST00003-0001", "FXHST00002-0001")


def store_containers(svg: str) -> dict:
    """data-group caption -> (data-id or "", (x, y, w, h)) of each data store container (D45)."""
    found = {}
    for m in re.finditer(
        r'<g class="group store[^"]*"(?: data-id="([^"]*)")? data-group="([^"]*)"><title>[^<]*</title>'
        r'<rect class="grp" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"',
        svg,
    ):
        found[m.group(2)] = (m.group(1) or "", tuple(int(m.group(i)) for i in range(3, 7)))
    return found


class InfrastructurePlacementTests(unittest.TestCase):
    """S17: infrastructure in the deployment view only (D43), no borrowed flows (D44), data components in their store (D45)."""

    def registry(self) -> tuple:
        catalog = load_catalog(FIXTURE)
        return catalog, generate_diagram.Model(catalog, catalog[REGISTRY_SDP], False)

    def test_logical_view_has_no_placed_infrastructure(self) -> None:  # AC26
        catalog, model = self.registry()
        logical, deployment = logical_svg(catalog, REGISTRY_SDP), deployment_svg(catalog, REGISTRY_SDP)
        ids = {n.uid for n in model.nodes_for_view("logical")}
        for uid in INFRA_FIXTURE_UIDS:
            self.assertNotIn(uid, ids)
            self.assertNotIn(f'data-id="{uid}"', logical)
        self.assertIn("FXNET00002-0001", node_rects(deployment))  # a placed network service is a deployment box
        self.assertIn("FXHST00002-0001", node_rects(deployment))  # and so is a placed host
        for uid in ("FXDST00002-0001", "FXDST00003-0001"):  # placed data store services are containers there
            self.assertIn(f'data-id="{uid}"', deployment)
        self.assertEqual(edges_hitting_foreign_boxes(logical), [])
        # No edge of the logical view touches the infrastructure; the deployment view draws it.
        self.assertNotIn("FXNET00002-0001", " ".join(f"{s} {t}" for s, t, _p in edge_polylines(logical)))
        self.assertIn("FXNET00002-0001", " ".join(f"{s} {t}" for s, t, _p in edge_polylines(deployment)))

    def test_all_five_infrastructure_types_leave_the_logical_view(self) -> None:  # AC26
        objects = [
            plain("N-1", "network_service", "Edge"),
            plain("R-1", "runtime_service", "Runner"),
            plain("H-1", "host", "Box"),
            plain("G-1", "ai_gateway", "Llm"),
            plain("S-1", "data_store_service", "Store"),
            component("C-1", "App"),
            plain("D-1", "data_component", "Rows", runsOn="S-1"),
            pattern({"G": ["N-1", "R-1", "H-1", "G-1", "S-1", "C-1", "D-1"]}),
            relationship("E-1", "C-1", "N-1", "uses"),
            relationship("E-2", "C-1", "D-1", "reads"),
        ]
        model = model_of(objects)
        self.assertEqual({n.uid for n in model.nodes_for_view("logical")}, {"C-1", "D-1"})
        deployment = {n.uid for n in model.nodes_for_view("deployment")}
        self.assertEqual(deployment, {"N-1", "R-1", "H-1", "G-1", "C-1", "D-1"})  # S-1 is D-1's container
        self.assertEqual(len(model.relationship_rows), 2)  # the edge to the network service keeps its table row
        logical = svg_for(objects)
        self.assertNotIn("N-1", data_ids(logical))
        self.assertEqual(len(edge_polylines(logical)), 1)
        self.assertEqual(len(edge_polylines(svg_for(objects, "deployment"))), 2)

    def test_unplaced_infrastructure_dependency_stays_in_the_lane(self) -> None:  # AC26
        catalog, model = self.registry()
        nodes = {n.uid: n for n in model.nodes_for_view("logical")}
        self.assertTrue(nodes["FXRTC00004-0001"].outside)
        self.assertIn("FXRTC00004-0001", node_rects(logical_svg(catalog, REGISTRY_SDP)))
        self.assertIn("FXRTC00004-0001", node_rects(deployment_svg(catalog, REGISTRY_SDP)))

    def test_infrastructure_relationships_to_other_patterns_are_not_borrowed(self) -> None:  # AC27
        catalog, model = self.registry()
        labels = {(row["from"], row["to"]) for row in model.relationship_rows}
        self.assertIn(("FX Ledger Gateway", "FX Shared Ledger"), labels)
        self.assertNotIn("FX Web Shop", {to for _from, to in labels})
        self.assertNotIn("FXEDG00014-0001", {e.uid for e in model.edges})
        self.assertNotIn("FXPRD00001-0001", model.scope)  # the elsewhere-placed target does not enter scope
        for svg in (logical_svg(catalog, REGISTRY_SDP), deployment_svg(catalog, REGISTRY_SDP)):
            self.assertNotIn("FXPRD00001-0001", data_ids(svg))
        self.assertNotIn("routes shop requests", generate_diagram.render_page(model, generate_diagram.diagram_of(model)))

    def test_infrastructure_sourced_relationships_need_a_placed_target(self) -> None:  # AC27
        objects = [
            plain("N-1", "network_service", "Edge"),
            component("C-1", "Placed"),
            component("X-1", "Elsewhere"),
            component("U-1", "Unplaced"),
            pattern({"G": ["N-1", "C-1"]}),
            relationship("E-1", "N-1", "C-1", "routes here"),
            relationship("E-2", "N-1", "X-1", "routes away"),
            relationship("E-3", "N-1", "U-1", "also away"),
            {"schemaVersion": "1.0", "uid": "E-4", "type": "relationship", "name": "E-4", "source": "N-1", "externalTarget": "Partner", "label": "out"},
            relationship("E-5", "C-1", "U-1", "calls"),  # a component's own dependency still enters scope
        ]
        model = model_of(objects)
        self.assertEqual([e.uid for e in model.edges], ["E-1", "E-5"])
        self.assertEqual({r["uid"] for r in model.relationship_rows}, {"E-1", "E-5"})
        self.assertEqual(model.scope, {"N-1", "C-1", "U-1"})
        self.assertFalse(any(n.external for n in model.nodes_for_view("logical")))

    def test_data_components_sit_in_their_data_store_container(self) -> None:  # AC28
        catalog, model = self.registry()
        svg = deployment_svg(catalog, REGISTRY_SDP)
        xml.dom.minidom.parseString(svg)
        boxes = store_containers(svg)
        self.assertEqual(sorted(boxes), ["FX Audit Store", "FX Ledger Store", "data store not recorded"])
        self.assertEqual(boxes["FX Ledger Store"][0], "FXDST00002-0001")
        self.assertEqual(boxes["data store not recorded"][0], "")
        rects = node_rects(svg)

        def inside(uid: str, caption: str) -> bool:
            bx, by, bw, bh = boxes[caption][1]
            x, y, w, h = rects[uid]
            return bx <= x and by <= y and x + w <= bx + bw and y + h <= by + bh

        self.assertTrue(inside("FXDCP00002-0001", "FX Ledger Store"))  # two data components share one container
        self.assertTrue(inside("FXDCP00003-0001", "FX Ledger Store"))
        self.assertTrue(inside("FXDCP00004-0001", "FX Audit Store"))  # a third has its own
        self.assertTrue(inside("FXDCP00005-0001", "data store not recorded"))  # no runsOn
        self.assertFalse(inside("FXDCP00004-0001", "FX Ledger Store"))
        self.assertNotRegex(svg, r'<g class="node[^"]*" data-id="FXDST0000[23]-0001"')  # the stores have no boxes
        warnings = [w for w in model.warnings if w.startswith("data store not recorded")]
        self.assertEqual(warnings, ["data store not recorded: FX Ledger Scratch (FXDCP00005-0001) has no runsOn data store service"])
        lane = re.search(r'<g class="zlane" data-zone="fx-data">.*?<g class="group store"', svg, re.S)
        self.assertIsNotNone(lane, "the container is drawn inside its data components' zone lane")

    def test_store_with_no_data_components_stays_a_box(self) -> None:  # AC28
        catalog = load_catalog(FIXTURE)
        svg = deployment_svg(catalog, FIXTURE_SDP)
        self.assertIn("FXDST00001-0001", node_rects(svg))
        self.assertIn("data store not recorded", store_containers(svg))  # FX Session Cache has no runsOn
        self.assertNotIn("FXDST00001-0001", {u for u, _r in store_containers(svg).values()})

    def test_store_container_is_per_group(self) -> None:  # AC28
        objects = [
            plain("S-1", "data_store_service", "Shared Store"),
            plain("D-1", "data_component", "One", runsOn="S-1"),
            plain("D-2", "data_component", "Two", runsOn="S-1"),
            plain("D-3", "data_component", "Three", runsOn="MISSING"),
            plain("S-2", "data_store_service", "Other Store"),
            plain("D-4", "data_component", "Four", runsOn="S-2"),  # keeps S-1 from being derived as group A's substrate
            pattern({"A": ["S-1", "D-1", "D-4"], "B": ["D-2", "D-3"]}),
        ]
        model = model_of(objects)
        stores = [[(st.uid, st.members) for lane in c.lanes for st in lane.stores] for c in model.containers]
        self.assertEqual(stores, [[("S-1", ["D-1"]), ("S-2", ["D-4"])], [("S-1", ["D-2"]), ("", ["D-3"])]])
        self.assertEqual(len([w for w in model.warnings if w.startswith("data store not recorded")]), 1)
        svg = svg_for(objects, "deployment")
        xml.dom.minidom.parseString(svg)
        self.assertEqual(svg.count('data-group="Shared Store"'), 2)  # one container per group, not one per store

    def test_edges_attach_to_the_data_component_box_and_the_store_border(self) -> None:
        catalog, _model = self.registry()
        svg = deployment_svg(catalog, REGISTRY_SDP)
        rects = node_rects(svg)
        boxes = store_containers(svg)
        seen = 0
        for source, target, pts in edge_polylines(svg):
            if source != "FXPRD00010-0001":
                continue
            if target.startswith("FXDCP"):
                x, y, w, _h = rects[target]
                ex, ey = pts[-1]
                self.assertEqual(ey, y, target)  # the last point lies on the top side of the box
                self.assertTrue(x <= ex <= x + w, target)
                seen += 1
            elif target == "FXDST00002-0001":
                x, y, w, h = boxes["FX Ledger Store"][1]
                ex, ey = pts[-1]
                on_border = (ey in (y, y + h) and x <= ex <= x + w) or (ex in (x, x + w) and y <= ey <= y + h)
                self.assertTrue(on_border, pts[-1])
                self.assertNotIn(target, rects)
                seen += 1
        self.assertEqual(seen, 5)

    def test_store_containers_are_deterministic_and_on_the_grid(self) -> None:
        catalog = load_catalog(FIXTURE)
        first = deployment_svg(catalog, REGISTRY_SDP)
        self.assertEqual(first, deployment_svg(load_catalog(FIXTURE), REGISTRY_SDP))
        self.assertEqual(side_violations(first), [])  # D36 holds for edges into store containers and their data components
        self.assertEqual(covisible_track_clashes(first), [])
        self.assertEqual(first, deployment_svg(dict(reversed(list(catalog.items()))), REGISTRY_SDP))
        for _uid, (x, y, _w, _h) in node_rects(first).items():
            self.assertEqual((x % generate_diagram.GRID, y % generate_diagram.GRID), (0, 0))
        for _uid, (_x, (x, y, _w, _h)) in store_containers(first).items():
            self.assertEqual((x % generate_diagram.GRID, y % generate_diagram.GRID), (0, 0))
        self.assertEqual(logical_svg(catalog, REGISTRY_SDP), logical_svg(load_catalog(FIXTURE), REGISTRY_SDP))

    def test_layout_writer_lists_data_components_and_store_containers(self) -> None:
        catalog = load_catalog(FIXTURE)
        model = generate_diagram.Model(catalog, catalog[REGISTRY_SDP], False)
        order = generate_diagram.drawn_order(model)["deployment"]
        drawn = [uid for container in order for uid in container]
        for uid in ("FXDCP00002-0001", "FXDCP00005-0001", "FXDST00002-0001", "FXDST00003-0001", "FXNET00002-0001"):
            self.assertIn(uid, drawn)
        self.assertEqual(len(drawn), len(set(drawn)))


if __name__ == "__main__":
    unittest.main()


class LaterStoryTests(unittest.TestCase):
    """Tests written ahead of the stories that implement them (D30). Each story removes its own markers."""

    def test_build_from_catalog_signature(self) -> None:
        params = list(inspect.signature(generate_diagram.build_from_catalog).parameters)
        self.assertEqual(params, ["catalog", "selector", "placed_only"])

    def test_build_from_catalog_returns_page_and_model(self) -> None:
        catalog = load_catalog(FIXTURE)
        page, model = generate_diagram.build_from_catalog(catalog, "FXSDP00001-0001", False)
        self.assertIsInstance(page, str)
        self.assertIsInstance(model, generate_diagram.Model)

    def test_one_hop_scope(self) -> None:
        # The fixture has no consumer, so add one: an unplaced object that only sources into a placed object.
        catalog = load_catalog(FIXTURE)
        first_placed = next(iter(fixture_model().placement))
        catalog["FXCON00001-0001"] = component("FXCON00001-0001", "Consumer Only")
        catalog["FXREL09999-0001"] = relationship("FXREL09999-0001", "FXCON00001-0001", first_placed, "calls")
        model = generate_diagram.Model(catalog, catalog[FIXTURE_SDP], False)
        nodes = model.nodes_for_view("logical")
        ids = {node.uid for node in nodes}
        self.assertNotIn("FXCON00001-0001", ids)
        placed = set(model.placement)
        infra = {u for u in placed if catalog[u]["type"] in generate_diagram.INFRA_TYPES}  # D43: deployment view only
        self.assertTrue(infra)
        self.assertTrue((placed - infra) <= ids)
        self.assertFalse(infra & ids)
        # One hop: unplaced objects a placed object sources a relationship to (D42) are nodes.
        self.assertIn("FXPRD00005-0001", ids)
        self.assertIn("FXPRD00010-0001", ids)
        # Two hops: reached only through the outside object FXPRD00010-0001, so not nodes.
        self.assertNotIn("FXDST00002-0001", ids)
        self.assertNotIn("FXHST00002-0001", ids)
        # Exact set: placed objects, allow-listed direct endpoints, and external nodes for placed sources.
        expected = set(placed) - infra
        for rel in catalog.values():
            if rel.get("type") != "relationship" or generate_diagram.is_runs_on(rel):
                continue
            source, target = rel.get("source") or "", rel.get("target") or ""
            if source in infra:  # D44: a placed infrastructure object's relationships never extend scope
                continue
            if source in placed and target:
                if catalog.get(target, {}).get("type") in ALLOWED_ONE_HOP:
                    expected.add(target)
            elif source in placed and rel.get("externalTarget"):
                expected.add("ext:" + hashlib.sha256(" ".join(str(rel["externalTarget"]).split()).encode("utf-8")).hexdigest()[:12])
            # D42: a source outside the placed set (a consumer) never enters scope.
        self.assertEqual(ids, expected - infra)
        self.assertTrue(all(e.source in placed for e in model.edges))
        for node in nodes:
            if node.outside and not node.external:
                self.assertTrue(
                    any(
                        e.source in placed and e.target == node.uid
                        for e in model.edges
                    ),
                    node.uid,
                )

    def test_one_hop_type_allow_list(self) -> None:
        objects = [plain("P-1", "product_component", "Placed")]
        for index, obj_type in enumerate(ALLOWED_ONE_HOP):
            objects.append(plain(f"T-{index}", obj_type, f"Allowed {index}"))
            objects.append(relationship(f"R-{index}", "P-1", f"T-{index}", "uses"))
        objects.append(plain("X-1", "api_contract", "Not Allowed"))
        objects.append(relationship("R-x", "P-1", "X-1", "documents"))
        objects.append(pattern({"G": ["P-1"]}))
        model = model_of(objects)
        ids = {node.uid for node in model.nodes_for_view("logical")}
        for index in range(len(ALLOWED_ONE_HOP)):
            self.assertIn(f"T-{index}", ids)
        self.assertNotIn("X-1", ids)
        self.assertNotIn("R-x", {edge.uid for edge in model.edges})
        self.assertEqual(len(model.edges), len(ALLOWED_ONE_HOP))

    def test_runs_on_does_not_extend_scope(self) -> None:
        model = fixture_model()
        ids = {node.uid for node in model.nodes_for_view("logical")}
        # FXHST00001-0001 hosts a placed data store only through a derived runs on relationship.
        self.assertNotIn("FXHST00001-0001", ids)
        runs_on = [obj for obj in load_catalog(FIXTURE).values() if generate_diagram.is_runs_on(obj)]
        self.assertTrue(runs_on)
        edge_uids = {edge.uid for edge in model.edges}
        row_uids = {row["uid"] for row in model.relationship_rows}
        for rel in runs_on:
            self.assertNotIn(rel["uid"], edge_uids)
            self.assertNotIn(rel["uid"], row_uids)
        inline = model_of(
            [plain("A-1", "product_component", "Alpha", runsOn="H-1"), plain("H-1", "host", "Host"), pattern({"G": ["A-1"]})]
        )
        self.assertEqual({node.uid for node in inline.nodes_for_view("logical")}, {"A-1"})
        self.assertEqual(inline.edges, [])

    def test_placed_only_restriction(self) -> None:
        model = fixture_model(placed_only=True)
        placed = set(model.placement)
        nodes = model.nodes_for_view("logical")
        self.assertTrue(all(node.placed for node in nodes))
        self.assertFalse(any(node.external for node in nodes))
        self.assertTrue(all(e.source in placed and e.target in placed for e in model.edges))
        self.assertGreater(len(model.edges), 0)

    def test_undrawn_relationship_count(self) -> None:
        catalog = load_catalog(FIXTURE)
        placed = set(fixture_model().placement)
        expected = 0
        for obj in catalog.values():
            if obj.get("type") != "relationship" or generate_diagram.is_runs_on(obj):
                continue
            source, target = obj.get("source") or "", obj.get("target") or ""
            if (source in placed or target in placed) and not (source in placed and target in placed):
                expected += 1
        placed_only = fixture_model(placed_only=True)
        self.assertEqual(placed_only.undrawn_relationship_count, expected)
        # FXEDG00008 (external), FXEDG00009 and FXEDG00010 leave the placed set; FXEDG00014 comes in from the
        # registry pattern's gateway.
        self.assertEqual(expected, 4)
        self.assertEqual(fixture_model().undrawn_relationship_count, 1)  # FXEDG00014: a consumer, not drawn (D42)

    def test_outside_lane_classification(self) -> None:
        model = fixture_model()
        nodes = {node.uid: node for node in model.nodes_for_view("logical")}
        self.assertFalse(nodes["FXPRD00001-0001"].outside)
        self.assertTrue(nodes["FXPRD00010-0001"].outside)
        self.assertEqual(nodes["FXPRD00010-0001"].caption, "FX Registry Pattern")
        self.assertEqual(nodes["FXPRD00005-0001"].caption, "not placed in any pattern")
        self.assertEqual([n.caption for n in nodes.values() if n.external], ["external"])
        objects = [
            plain("P-1", "product_component", "Placed"),
            plain("S-1", "product_component", "Shared"),
            relationship("R-1", "P-1", "S-1", "uses"),
            pattern({"G": ["P-1"]}),
        ]
        for uid, name in (("SDP-2", "Second Pattern"), ("SDP-3", "Third Pattern")):
            other = pattern({"G": ["S-1"]})
            other["uid"], other["name"] = uid, name
            objects.append(other)
        multi = model_of(objects, selector="Demo Pattern")
        shared = {node.uid: node for node in multi.nodes_for_view("logical")}["S-1"]
        self.assertEqual(shared.caption, "placed in 2 other patterns")
        # Two distinct other patterns that share a display name still count as two.
        same_name = [
            plain("P-1", "product_component", "Placed"),
            plain("S-1", "product_component", "Shared"),
            relationship("R-1", "P-1", "S-1", "uses"),
            pattern({"G": ["P-1"]}),
        ]
        for uid in ("SDP-2", "SDP-3"):
            other = pattern({"G": ["S-1"]})
            other["uid"], other["name"] = uid, "Same Name"
            same_name.append(other)
        twins = {n.uid: n for n in model_of(same_name, selector="Demo Pattern").nodes_for_view("logical")}
        self.assertEqual(twins["S-1"].caption, "placed in 2 other patterns")

    def test_derived_tier_warning(self) -> None:
        model = fixture_model()
        tier_warnings = [w for w in model.warnings if w.startswith("derived tier:")]
        self.assertEqual(tier_warnings, ["derived tier: FX Order Worker (FXPRD00003-0001) -> application"])
        nodes = {node.uid: node for node in model.nodes_for_view("logical")}
        self.assertTrue(nodes["FXPRD00003-0001"].derived)
        self.assertEqual(nodes["FXPRD00003-0001"].band, "application")
        self.assertEqual([n.uid for n in nodes.values() if n.derived], ["FXPRD00003-0001"])
        # FXPRD00005-0001 is an unplaced endpoint without a tier: no warning.
        self.assertFalse(any("FXPRD00005-0001" in w for w in model.warnings))

    def test_external_nodes(self) -> None:
        model = fixture_model()
        expected = "ext:" + hashlib.sha256("FX Payment Provider".encode("utf-8")).hexdigest()[:12]
        external = [node for node in model.nodes_for_view("logical") if node.external]
        self.assertEqual([node.uid for node in external], [expected])
        self.assertEqual(external[0].caption, "external")
        self.assertTrue(external[0].outside)
        self.assertTrue(any(e.source == "FXPRD00002-0001" and e.target == expected for e in model.edges))
        # Surrounding and repeated whitespace is trimmed and collapsed before hashing (D3).
        objects = [
            plain("A-1", "product_component", "Alpha"),
            plain("R-1", "relationship", "R-1", source="A-1", externalTarget="  Payments   API  ", label="calls"),
            plain("R-2", "relationship", "R-2", source="A-1", externalTarget="Payments API", label="calls"),
            pattern({"G": ["A-1"]}),
        ]
        ext = [node for node in model_of(objects).nodes_for_view("logical") if node.external]
        self.assertEqual(len(ext), 1)
        self.assertRegex(ext[0].uid, r"^ext:[0-9a-f]{12}$")
        self.assertEqual(ext[0].uid, "ext:" + hashlib.sha256(b"Payments API").hexdigest()[:12])
        self.assertEqual(ext[0].caption, "external")
        self.assertEqual(model_of(objects, placed_only=True).undrawn_relationship_count, 2)

    def test_duplicate_placement(self) -> None:
        model = fixture_model()
        duplicates = [w for w in model.warnings if w.startswith("duplicate placement:")]
        self.assertEqual(
            duplicates,
            ["duplicate placement: FX Order Worker (FXPRD00003-0001) first placed in Application; also listed in Batch"],
        )
        drawn = [node for node in model.nodes_for_view("logical") if node.uid == "FXPRD00003-0001"]
        self.assertEqual(len(drawn), 1)
        self.assertEqual(model.placement["FXPRD00003-0001"]["group"], "Application")
        same_group = model_of([plain("A-1", "product_component", "Alpha"), pattern({"G": ["A-1", "A-1"]})])
        self.assertIn("duplicate placement: Alpha (A-1) first placed in G; also listed in G", same_group.warnings)
        self.assertEqual(len(same_group.nodes_for_view("logical")), 1)

    def test_derived_relationships(self) -> None:
        model = fixture_model()
        rows = {row["label"]: row for row in model.relationship_rows}
        self.assertEqual(rows["reads cached sessions"]["source"], "inline dependency")
        self.assertEqual(rows["places orders"]["source"], "relationship object")
        self.assertNotIn("runs on", rows)
        dependencies = [edge for edge in model.edges if edge.origin == "inline dependency"]
        self.assertEqual([(e.source, e.target) for e in dependencies], [("FXPRD00002-0001", "FXDCP00001-0001")])
        self.assertTrue(dependencies[0].derived)
        self.assertIn("FXDCP00001-0001", model.scope)

    def test_malformed_service_groups_model(self) -> None:
        catalog = load_catalog(FIXTURE)
        malformed = dict(catalog[FIXTURE_SDP], serviceGroups="Edge")
        with self.assertRaises(ValueError) as raised:
            generate_diagram.Model(catalog, malformed, False)
        self.assertEqual(str(raised.exception), "serviceGroups must be a list")
        sdp = pattern({"G": []})
        sdp["serviceGroups"] = "not a list"
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(Path(tmp), [sdp])
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = generate_diagram.main(["--workspace", str(workspace)])
        self.assertEqual(code, 1)
        self.assertTrue(err.getvalue().startswith("error: serviceGroups must be a list"))

    def test_container_caption_variants(self) -> None:
        objects = [
            plain("RTC-1", "runtime_service", "Cluster"),
            plain("RTC-2", "runtime_service", "Cluster Two", host="HST-1"),
            plain("HST-1", "host", "Host One"),
            plain("DST-1", "data_store_service", "Store"),
            plain("P-1", "product_component", "Alpha"),
            plain("P-2", "product_component", "Beta", runsOn="RTC-1"),
            plain("P-3", "product_component", "Gamma", runsOn="RTC-1"),
            plain("P-4", "product_component", "Delta", runsOn="RTC-1"),
            plain("P-5", "product_component", "Epsilon", runsOn="RTC-2"),
            plain("P-6", "product_component", "Zeta"),
            plain("P-7", "product_component", "Eta"),
            plain("P-8", "product_component", "Theta"),
            pattern({"One": ["P-1"], "Two": ["P-2", "P-3"], "Three": ["P-4", "P-5"], "Four": ["P-6"], "Five": ["P-7"], "Six": ["P-8"]}),
        ]
        sdp = objects[-1]
        groups = sdp["serviceGroups"]
        groups[0]["substrate"] = "RTC-1"
        groups[3]["substrate"] = "FX-MISSING"
        groups[4]["substrate"] = "DST-1"
        groups[5]["substrate"] = "RTC-2"
        model = model_of(objects)
        captions = [container.caption for container in model.containers]
        self.assertEqual(
            captions,
            [
                "Cluster",
                "Cluster derived",
                "substrate not recorded",
                "substrate not found: FX-MISSING",
                "Store (data_store_service)",
                "Cluster Two on Host One",
            ],
        )
        self.assertEqual(model.containers[0].uid, "RTC-1")
        self.assertTrue(model.containers[1].derived)
        self.assertEqual(model.containers[2].uid, "")
        self.assertEqual(model.containers[3].uid, "")
        self.assertEqual(model.containers[5].members, ["P-8"])

    def test_substrate_type_mismatch_and_unknown_uid_warnings(self) -> None:
        objects = [
            plain("DST-1", "data_store_service", "Store"),
            plain("P-1", "product_component", "Alpha"),
            plain("P-2", "product_component", "Beta"),
            pattern({"Data": ["P-1"], "Other": ["P-2"]}),
        ]
        objects[-1]["serviceGroups"][0]["substrate"] = "DST-1"
        objects[-1]["serviceGroups"][1]["substrate"] = "FX-MISSING"
        model = model_of(objects)
        self.assertIn("substrate Store (DST-1) has type data_store_service; expected runtime_service or host", model.warnings)
        self.assertIn("unknown substrate uid 'FX-MISSING' in Other", model.warnings)
        self.assertEqual(model.containers[1].uid, "")
        # A recorded substrate is drawn as the container even when its type is not allowed.
        self.assertEqual(model.containers[0].uid, "DST-1")
        self.assertEqual(model.containers[0].caption, "Store (data_store_service)")

    def test_conflict_warning(self) -> None:
        objects = [
            plain("RTC-1", "runtime_service", "Cluster"),
            plain("RTC-2", "runtime_service", "Cluster Two"),
            plain("P-1", "product_component", "Alpha", runsOn="RTC-2"),
            plain("P-2", "product_component", "Beta", runsOn="RTC-1"),
            pattern({"G": ["P-1", "P-2"]}),
        ]
        objects[-1]["serviceGroups"][0]["substrate"] = "RTC-1"
        model = model_of(objects)
        self.assertEqual(len(model.conflicts), 1)
        self.assertEqual(model.conflicts[0].component, "P-1")
        self.assertIn("conflict: Alpha runsOn Cluster Two; group substrate is Cluster", model.warnings)
        self.assertEqual(model.containers[0].caption, "Cluster")
        # A derived substrate never conflicts: every runsOn agrees by construction.
        objects[-1]["serviceGroups"][0].pop("substrate")
        self.assertEqual(model_of(objects[:-1] + [pattern({"G": ["P-2"]})]).conflicts, [])

    def test_zone_assignment_and_warning(self) -> None:
        objects = [
            plain("A-1", "product_component", "Data Part"),
            plain("B-1", "product_component", "App Part"),
            plain("C-1", "product_component", "Unzoned"),
            plain("D-1", "product_component", "Stray"),
        ]
        sdp = pattern({"G": []})
        sdp["networkZones"] = [
            {"id": "z-app", "name": "App Zone", "tier": "application"},
            {"id": "z-data", "name": "Data Zone", "tier": "data"},
        ]
        sdp["serviceGroups"][0]["deployableObjects"] = [
            {"ref": "A-1", "networkZone": "z-data"},
            {"ref": "B-1", "networkZone": "z-app"},
            {"ref": "C-1"},
            {"ref": "D-1", "networkZone": "z-gone"},
        ]
        model = model_of(objects + [sdp])
        lanes = model.containers[0].lanes
        self.assertEqual([lane.name for lane in lanes], ["App Zone", "Data Zone", "zone not recorded"])
        self.assertEqual([lane.members for lane in lanes], [["B-1"], ["A-1"], ["C-1", "D-1"]])
        self.assertEqual(lanes[0].tier, "application")
        self.assertIn("undeclared network zone: z-gone in G", model.warnings)
        self.assertEqual([w for w in model.warnings if w.startswith("undeclared")], ["undeclared network zone: z-gone in G"])

    def test_node_sets_per_view(self) -> None:
        objects = [
            plain("RTC-1", "runtime_service", "Cluster"),
            plain("RTC-2", "runtime_service", "Cluster Two"),
            plain("P-1", "product_component", "Alpha"),
            plain("P-2", "product_component", "Beta"),
            pattern({"G": ["RTC-1", "P-1"], "H": ["P-2"]}),
        ]
        objects[-1]["serviceGroups"][0]["substrate"] = "RTC-1"
        objects[-1]["serviceGroups"][1]["substrate"] = "RTC-2"
        model = model_of(objects)
        logical = {node.uid for node in model.nodes_for_view("logical")}
        deployment = {node.uid for node in model.nodes_for_view("deployment")}
        self.assertNotIn("RTC-1", logical)  # D43: placed infrastructure is not in the logical view
        self.assertNotIn("RTC-1", deployment)
        self.assertEqual(model.containers[0].uid, "RTC-1")
        # A substrate that is neither placed nor a one-hop endpoint is a container only.
        self.assertNotIn("RTC-2", logical)
        self.assertNotIn("RTC-2", deployment)
        self.assertEqual(model.containers[1].uid, "RTC-2")
        self.assertEqual(logical, {"P-1", "P-2"})
        self.assertEqual(deployment, {"P-1", "P-2"})
        self.assertEqual(
            [w for w in model.warnings if w.startswith("substrate also listed")],
            ["substrate also listed as deployable object: Cluster (RTC-1) in G"],
        )
        self.assertEqual(model.containers[0].members, ["P-1"])
        with self.assertRaises(ValueError):
            model.nodes_for_view("unknown")

    def test_warning_dedup_sorted(self) -> None:
        objects = [
            plain("DST-1", "data_store_service", "Store"),
            plain("P-1", "product_component", "Alpha"),
            plain("P-2", "product_component", "Beta"),
        ]
        sdp = pattern({})
        sdp["serviceGroups"] = [
            {"name": "One", "deploymentTarget": "azure", "substrate": "DST-1",
             "deployableObjects": [{"ref": "P-1", "diagramTier": "application"}]},
            {"name": "Two", "deploymentTarget": "azure", "substrate": "DST-1",
             "deployableObjects": [{"ref": "P-2", "diagramTier": "application"}]},
            {"name": "Zeta", "deploymentTarget": "azure", "substrate": "FX-MISSING", "deployableObjects": []},
            {"name": "alpha", "deploymentTarget": "azure", "substrate": "FX-MISSING", "deployableObjects": []},
        ]
        model = model_of(objects + [sdp])
        # Code-point order: "Z" (U+005A) sorts before "a" (U+0061), so "Zeta" precedes "alpha".
        self.assertEqual(
            model.warnings,
            [
                "substrate Store (DST-1) has type data_store_service; expected runtime_service or host",
                "unknown substrate uid 'FX-MISSING' in Zeta",
                "unknown substrate uid 'FX-MISSING' in alpha",
            ],
        )
        self.assertEqual(model.warning_count_line, "3 warnings")

    def test_substrate_placed_in_other_group_is_not_a_lane_member(self) -> None:
        objects = [
            plain("RTC-1", "runtime_service", "Cluster"),
            plain("P-1", "product_component", "Alpha"),
            plain("P-2", "product_component", "Beta"),
        ]
        sdp = pattern({})
        sdp["networkZones"] = [{"id": "z-app", "name": "App Zone", "tier": "application"}]
        sdp["serviceGroups"] = [
            {"name": "A", "deploymentTarget": "azure", "substrate": "RTC-1",
             "deployableObjects": [{"ref": "P-1", "networkZone": "z-app", "diagramTier": "application"}]},
            {"name": "B", "deploymentTarget": "azure",
             "deployableObjects": [
                 {"ref": "RTC-1", "networkZone": "z-app", "diagramTier": "utility"},
                 {"ref": "P-2", "networkZone": "z-app", "diagramTier": "application"},
             ]},
        ]
        model = model_of(objects + [sdp])
        group_b = next(c for c in model.containers if c.group == "B")
        self.assertNotIn("RTC-1", group_b.members)
        self.assertEqual(group_b.members, ["P-2"])
        lane_members = [uid for container in model.containers for lane in container.lanes for uid in lane.members]
        self.assertNotIn("RTC-1", lane_members)
        deployment = {node.uid for node in model.nodes_for_view("deployment")}
        self.assertNotIn("RTC-1", deployment)
        for uid in lane_members:
            self.assertIn(uid, deployment)
        self.assertNotIn("RTC-1", {node.uid for node in model.nodes_for_view("logical")})  # D43

    def test_logical_golden(self) -> None:
        catalog = load_catalog(FIXTURE)
        patterns = generate_diagram.sdps(catalog)
        self.assertEqual(len(patterns), 3)
        for sdp in patterns:
            with self.subTest(sdp=sdp["uid"]):
                path = harness.golden_path(generate_diagram.slug(sdp["name"]), "logical")
                harness.check_golden(self, path, lambda: logical_svg(catalog, sdp["uid"]).encode("utf-8"))

    def test_logical_bands_and_dashed_derived(self) -> None:
        objects = [
            plain("N-1", "product_component", "Gateway"),
            plain("P-1", "product_component", "Alpha"),
            plain("D-1", "data_component", "Store"),
            plain("H-1", "product_component", "Machine"),
            plain("P-2", "product_component", "Tiered"),
            plain("X-1", "product_component", "Elsewhere"),
            pattern({"G": ["N-1", "P-1", "D-1", "H-1", "P-2"]}),
            relationship("R-1", "P-1", "X-1", "calls"),
        ]
        entries = next(o for o in objects if o["uid"] == "SDP-1")["serviceGroups"][0]["deployableObjects"]
        for index, tier in ((0, "presentation"), (2, "data"), (3, "utility"), (4, "utility")):
            entries[index]["diagramTier"] = tier
        catalog = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = logical_svg(catalog, "SDP-1")
        xml.dom.minidom.parseString(svg)
        rects = node_rects(svg)
        ys = {uid: rects[uid][1] for uid in rects}
        self.assertLess(ys["N-1"], ys["P-1"])
        self.assertLess(ys["P-1"], ys["D-1"])
        self.assertLess(ys["D-1"], ys["H-1"])
        self.assertEqual(ys["H-1"], ys["P-2"])  # recorded diagramTier utility puts P-2 beside the host
        self.assertIn('<g class="node dashed" data-id="P-1">', svg)
        self.assertNotIn('<g class="node dashed" data-id="P-2">', svg)
        # A one-hop endpoint placed nowhere is in the outside lane and drawn solid (D4).
        self.assertIn('<g class="node outside" data-id="X-1">', svg)
        self.assertNotRegex(svg, r'class="node[^"]*dashed[^"]*" data-id="X-1"')

    def test_barycentre_tie_break_by_uid(self) -> None:
        layers = [["T-1"], ["B-9", "A-1", "C-5"]]
        pairs = [("T-1", "B-9"), ("T-1", "A-1"), ("T-1", "C-5")]
        self.assertEqual(generate_diagram.barycentre_order(layers, pairs), [["T-1"], ["A-1", "B-9", "C-5"]])
        # Ties compare code points, not locale: "Z" sorts before "a".
        self.assertEqual(generate_diagram.barycentre_order([["a-1", "Z-1"]], []), [["Z-1", "a-1"]])

    def test_barycentre_orders_by_neighbour_position(self) -> None:
        layers = [["T-1", "T-2"], ["L-1", "L-2"]]
        pairs = [("T-1", "L-2"), ("T-2", "L-1")]
        self.assertEqual(generate_diagram.barycentre_order(layers, pairs), [["T-1", "T-2"], ["L-2", "L-1"]])

    def test_grid_snapping(self) -> None:
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            model = generate_diagram.build_diagram_model(catalog, sdp, False)
            layout = generate_diagram.layout_logical(model)
            self.assertEqual(set(layout.pos), {n.uid for n in model.nodes})
            for uid, (x, y) in layout.pos.items():
                self.assertEqual((x % generate_diagram.GRID, y % generate_diagram.GRID), (0, 0), uid)

    def test_external_node_in_outside_lane(self) -> None:
        catalog = load_catalog(FIXTURE)
        svg = logical_svg(catalog, FIXTURE_SDP)
        model = generate_diagram.build_diagram_model(catalog, catalog[FIXTURE_SDP], False)
        externals = [n for n in model.nodes if n.external]
        self.assertEqual(len(externals), 1)
        rects = node_rects(svg)
        inner = [rects[n.uid][0] for n in model.nodes if not n.outside]
        lane = [rects[n.uid][0] for n in model.nodes if n.outside]
        self.assertGreater(min(lane), max(inner))
        self.assertEqual(len(set(lane)), 1)
        self.assertEqual(max(rects[u][0] + rects[u][2] for u in rects), rects[externals[0].uid][0] + rects[externals[0].uid][2])
        self.assertEqual(svg.count(f'data-to="{externals[0].uid}"'), 1)
        # Lane captions (D5): other pattern's name, "not placed in any pattern", "external".
        for caption in ("external", "not placed in any pattern", "FX Registry Pattern"):
            self.assertIn(f">{caption}</text>", svg)
        self.assertNotIn("<desc>external", svg)

    def test_outside_lane_order_band_first(self) -> None:
        objects = [
            plain("A-1", "product_component", "Alpha"),
            plain("Z-N", "network_service", "Zed Net"),
            plain("B-D", "data_store_service", "Bee Store"),
            plain("C-A", "product_component", "Cee App"),
            pattern({"G": ["A-1"]}),
            relationship("R-1", "A-1", "B-D", "reads"),
            relationship("R-2", "A-1", "C-A", "calls"),
            relationship("R-3", "A-1", "Z-N", "uses"),
            {**relationship("R-4", "A-1", "", "talks"), "externalTarget": "Partner"},
        ]
        catalog = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        model = generate_diagram.build_diagram_model(catalog, catalog["SDP-1"], False)
        layout = generate_diagram.layout_logical(model)
        names = [next(n.name for n in model.nodes if n.uid == uid) for uid in layout.lane_order]
        self.assertEqual(names, ["Zed Net", "Cee App", "Bee Store", "Partner"])
        svg = generate_diagram.render_logical_svg(model)
        self.assertEqual(svg.count(">not placed in any pattern</text>"), 3)
        self.assertIn(">external</text>", svg)

    def test_svg_escaping(self) -> None:
        name = 'A<b> & "C"'
        catalog = load_catalog(
            write_workspace(Path(tempfile.mkdtemp()), [component("A-1", name), component("B-1", "Beta"), pattern({"G": ["A-1", "B-1"]}), relationship("R-1", "A-1", "B-1", "x <y> & z")])
        )
        svg = logical_svg(catalog, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertIn("A&lt;b&gt; &amp; &quot;C&quot;", svg)
        self.assertNotIn("<b>", svg)
        self.assertIn("x &lt;y&gt; &amp; z", svg)

    def test_large_logical_svg_valid_fast_low_crossings(self) -> None:
        import time

        catalog = load_catalog(FIXTURE)
        uid = "FXSDP00003-0001"
        started = time.monotonic()
        svg = logical_svg(catalog, uid)
        self.assertLess(time.monotonic() - started, 30)
        xml.dom.minidom.parseString(svg)
        crossings = count_crossings(svg)
        self.assertLessEqual(crossings, LARGE_MAX_CROSSINGS, f"{crossings} crossings")

    def test_edges_avoid_foreign_boxes(self) -> None:
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            svg = logical_svg(catalog, sdp["uid"])
            self.assertGreater(len(edge_polylines(svg)), 0)
            self.assertEqual(edges_hitting_foreign_boxes(svg), [], sdp["uid"])

    def test_wrapped_band_has_no_overlapping_boxes(self) -> None:
        uids = [f"P-{i:02d}" for i in range(9)]
        objects = [component(u, u) for u in uids] + [pattern({"G": uids})]
        for entry in objects[-1]["serviceGroups"][0]["deployableObjects"]:
            entry["diagramTier"] = "application"
        catalog = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        rects = list(node_rects(logical_svg(catalog, "SDP-1")).values())
        self.assertEqual(len(rects), 9)
        self.assertGreater(len({r[1] for r in rects}), 1)
        self.assertLessEqual(len({r[0] for r in rects}), generate_diagram.LOGICAL_COLUMNS)
        for i, (ax, ay, aw, ah) in enumerate(rects):
            for bx, by, bw, bh in rects[i + 1 :]:
                apart = ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay
                self.assertTrue(apart, ((ax, ay), (bx, by)))

    def test_logical_substrate_is_box(self) -> None:
        catalog = load_catalog(FIXTURE)
        svg = logical_svg(catalog, FIXTURE_SDP)
        self.assertNotIn('data-id="FXRTC00001-0001"', svg)  # D43: placed infrastructure is deployment-only

    def test_logical_order_independent_of_insertion_order(self) -> None:
        catalog = load_catalog(FIXTURE)
        for uid in ("FXSDP00001-0001", "FXSDP00003-0001"):
            reversed_catalog = dict(reversed(list(catalog.items())))
            self.assertEqual(logical_svg(catalog, uid), logical_svg(reversed_catalog, uid))

    def test_svg_desc_has_no_version(self) -> None:
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            for svg in (logical_svg(catalog, sdp["uid"]), deployment_svg(catalog, sdp["uid"])):
                desc = re.search(r"<desc>(.*?)</desc>", svg).group(1)
                self.assertEqual(desc, f"generate_diagram {sdp['uid']}")
                self.assertNotRegex(svg, r"\d+\.\d+\.\d+")
                self.assertNotRegex(svg, r"\d{4}-\d{2}-\d{2}T|/Users/|/home/|[A-Za-z]:\\")
                self.assertNotIn(str(REPO_ROOT), svg)

    def test_deployment_golden(self) -> None:
        catalog = load_catalog(FIXTURE)
        patterns = generate_diagram.sdps(catalog)
        self.assertEqual(len(patterns), 3)
        for sdp in patterns:
            with self.subTest(sdp=sdp["uid"]):
                path = harness.golden_path(generate_diagram.slug(sdp["name"]), "deployment")
                harness.check_golden(self, path, lambda: deployment_svg(catalog, sdp["uid"]).encode("utf-8"))

    def test_nesting_order(self) -> None:
        catalog = load_catalog(FIXTURE)
        svg = deployment_svg(catalog, FIXTURE_SDP)
        xml.dom.minidom.parseString(svg)
        model = generate_diagram.build_diagram_model(catalog, catalog[FIXTURE_SDP], False)
        expected_targets: list = []
        for container in model.containers:
            if container.drawn and container.target not in expected_targets:
                expected_targets.append(container.target)
        self.assertEqual(re.findall(r'<g class="target" data-target="([^"]*)"', svg), expected_targets)
        drawn = [c for c in model.containers if c.drawn]
        self.assertEqual(re.findall(r'<g class="(?!group store)group[^"]*"(?: data-id="[^"]*")? data-group="([^"]*)"', svg), [
            c.group for t in expected_targets for c in drawn if c.target == t
        ])
        dom = xml.dom.minidom.parseString(svg)
        for target in dom.getElementsByTagName("g"):
            if target.getAttribute("class") != "target":
                continue
            groups = [g for g in target.childNodes if getattr(g, "tagName", "") == "g"]
            self.assertTrue(groups)
            for group in groups:
                self.assertTrue(group.getAttribute("class").startswith("group"))
                for lane in [x for x in group.childNodes if getattr(x, "tagName", "") == "g"]:
                    self.assertEqual(lane.getAttribute("class"), "zlane")
                    for box in [x for x in lane.childNodes if getattr(x, "tagName", "") == "g"]:
                        self.assertTrue(box.getAttribute("class").startswith(("node", "group store")))  # D45
        ids = re.findall(r'<g class="node[^"]*" data-id="([^"]*)"', svg)
        in_lanes = [uid for c in drawn for lane in c.lanes for uid in lane.members]
        self.assertEqual([i for i in ids if i in in_lanes], [u for t in expected_targets for c in drawn if c.target == t for lane in c.lanes for u in generate_diagram.apply_positions(lane.members, model.deployment_positions)])

    def test_zone_lanes_order_and_fallback(self) -> None:
        catalog = load_catalog(FIXTURE)
        svg = deployment_svg(catalog, FIXTURE_SDP)
        self.assertEqual(svg.count('data-id="FXRTC00002-0001" data-group'), 1)
        group = re.search(r'<g class="group[^"]*" data-id="FXRTC00002-0001".*?(?=<g class="group|</g></g></svg>|</g>\n<g class="target")', svg, re.S).group(0)
        self.assertEqual(re.findall(r'<g class="zlane" data-zone="([^"]*)"', group), ["fx-app", "fx-data"])
        captions = re.findall(r'class="zc"[^>]*>([^<]*)<', svg)
        self.assertIn("FX Data Zone (data)", captions)
        self.assertIn("zone not recorded", captions)
        self.assertLess(captions.index("FX App Zone (application)"), captions.index("FX Data Zone (data)"))

    def test_substrate_container_not_node(self) -> None:
        catalog = load_catalog(FIXTURE)
        uid = "FXRTC00001-0001"
        deployment = deployment_svg(catalog, FIXTURE_SDP)
        self.assertRegex(deployment, rf'<g class="group[^"]*" data-id="{uid}"')
        self.assertNotRegex(deployment, rf'<g class="node[^"]*" data-id="{uid}"')
        self.assertNotIn(f'data-id="{uid}"', logical_svg(catalog, FIXTURE_SDP))  # D43

    def test_container_captions_and_conflict(self) -> None:
        catalog = load_catalog(FIXTURE)
        model = generate_diagram.build_diagram_model(catalog, catalog[FIXTURE_SDP], False)
        svg = deployment_svg(catalog, FIXTURE_SDP)
        captions = re.findall(r'class="gc"[^>]*>([^<]*)<', svg)
        self.assertEqual(captions, [xml_unescape(c.caption) for c in model.containers if c.drawn])
        self.assertIn("substrate not recorded", captions)
        objects = [
            plain("RTC-1", "runtime_service", "Cluster"),
            plain("RTC-2", "runtime_service", "Other"),
            plain("P-1", "product_component", "Alpha", runsOn="RTC-2"),
            pattern({"G": ["P-1"]}),
        ]
        objects[-1]["serviceGroups"][0]["substrate"] = "RTC-1"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        self.assertIn('class="gc" x="', svg)
        self.assertEqual(re.findall(r'class="gc"[^>]*>([^<]*)<', svg), ["Cluster"])
        self.assertEqual(len(model_of(objects).conflicts), 1)

    def test_empty_group_caption(self) -> None:
        catalog = load_catalog(FIXTURE)
        model = generate_diagram.build_diagram_model(catalog, catalog[FIXTURE_SDP], False)
        empty = [c for c in model.containers if not c.drawn]
        self.assertTrue(empty)
        svg = deployment_svg(catalog, FIXTURE_SDP)
        self.assertIn("Service groups recorded with no objects to draw", svg)
        for container in empty:
            self.assertIn(xml_escape(container.group), svg)
            self.assertNotIn(f'data-group="{xml_escape(container.group)}"', svg)

    def test_container_edge_attachment(self) -> None:
        objects = [
            plain("RTC-1", "runtime_service", "Cluster"),
            plain("P-1", "product_component", "Alpha"),
            plain("P-2", "product_component", "Beta"),
            pattern({"G": ["P-1", "RTC-1"], "H": ["P-2"]}),
            relationship("R-1", "RTC-1", "P-2", "serves"),
        ]
        objects[-2]["serviceGroups"][0]["substrate"] = "RTC-1"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertRegex(svg, r'<g class="group[^"]*" data-id="RTC-1"')
        self.assertIn("<title>Cluster serves Beta</title>", svg)  # the object's name, not the container caption
        (_, _, pts), = edge_polylines(svg)
        gx, gy, gw, gh = endpoint_rects(svg)["RTC-1"]
        box = node_rects(svg)["P-2"]
        # D29 as amended by D36: the container end is on its bottom border at centre + ATTACH_DX (the edge leaves
        # it), the box end on the box's top side at centre - ATTACH_DX (the edge enters it).
        self.assertEqual(pts[0], (gx + gw // 2 + generate_diagram.ATTACH_DX, gy + gh))
        self.assertEqual(pts[-1], (box[0] + box[2] // 2 - generate_diagram.ATTACH_DX, box[1]))
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            self.assertTrue(ax == bx or ay == by, "orthogonal route")
        self._assert_runs_clean(svg)

    def test_deployment_edges_avoid_foreign_boxes(self) -> None:
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            svg = deployment_svg(catalog, sdp["uid"])
            self.assertGreater(len(edge_polylines(svg)), 0)
            self.assertEqual(edges_hitting_foreign_boxes(svg), [], sdp["uid"])
            self.assertEqual(covisible_track_clashes(svg), [], sdp["uid"])  # D35: only co-visible edges must not share

    def _small_pair(self, extra: list) -> str:
        objects = [component("A-1", "Alpha"), component("B-1", "Beta"), pattern({"G": ["A-1", "B-1"]})] + extra
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        return deployment_svg(cat, "SDP-1")

    def test_deployment_repeated_self_loops_are_distinct(self) -> None:
        svg = self._small_pair([relationship("R-1", "A-1", "A-1", "one"), relationship("R-2", "A-1", "A-1", "two")])
        loops = re.findall(r'<g class="edge" data-from="A-1" data-to="A-1">.*?<path class="ln" d="([^"]*)"', svg)
        self.assertEqual(len(loops), 2)
        self.assertNotEqual(loops[0], loops[1])

    def test_deployment_parallel_edges_bend_apart(self) -> None:
        svg = self._small_pair([relationship("R-1", "A-1", "B-1", "x"), relationship("R-2", "B-1", "A-1", "y")])
        paths = re.findall(r'<path class="ln" d="(M[^"]*)"', svg)
        self.assertEqual(len(paths), 2)
        self.assertNotEqual(paths[0], paths[1])
        self.assertNotEqual(sorted(paths[0].split(" L")[1:-1]), [])

    def test_deployment_long_container_text_stays_inside(self) -> None:
        long_group = "A very long service group name " * 4
        objects = [component("A-1", "Alpha"), pattern({long_group.strip(): ["A-1"]})]
        objects[-1]["serviceGroups"][0]["substrate"] = "FX-MISSING-SUBSTRATE-WITH-A-LONG-IDENTIFIER-0001"
        objects[-1]["deploymentTarget"] = "t"
        objects[-1]["serviceGroups"][0]["deploymentTarget"] = "a deployment target with a rather long recorded name " * 2
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        grp = re.search(r'<rect class="grp" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg)
        gx, gy, gw, gh = (int(grp.group(i)) for i in range(1, 5))
        texts = re.findall(r'<text class="(?:gl|gc)" x="(\d+)" y="(\d+)">([^<]*)</text>', svg)
        self.assertGreater(len(texts), 3)
        for x, y, text in texts:
            self.assertLessEqual(int(x) + len(text) * generate_diagram.DEPLOY_CHAR_W, gx + gw)
            self.assertLess(int(y), gy + gh)
        joined = " ".join(t for _x, _y, t in texts)
        self.assertIn("substrate not found:", joined)
        self.assertIn("LONG-IDENTIFIER-0001", joined.replace(" ", ""))
        tgt = re.search(r'<rect class="tgt" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg)
        for x, _y, text in re.findall(r'<text class="tl" x="(\d+)" y="(\d+)">([^<]*)</text>', svg):
            self.assertLessEqual(int(x) + len(text) * generate_diagram.DEPLOY_CHAR_W, int(tgt.group(1)) + int(tgt.group(3)))

    def test_deployment_edge_tooltip_uses_names(self) -> None:
        svg = self._small_pair([relationship("R-1", "A-1", "B-1", "calls")])
        self.assertIn("<title>Alpha calls Beta</title>", svg)

    def test_declared_zone_lane_precedes_zone_not_recorded(self) -> None:
        objects = [component("A-1", "Alpha"), component("B-1", "Beta"), pattern({"G": ["A-1", "B-1"]})]
        sdp = objects[-1]
        sdp["networkZones"] = [{"id": "z1", "name": "Zone One", "tier": "frontend"}]
        sdp["serviceGroups"][0]["deployableObjects"][1]["networkZone"] = "z1"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        self.assertEqual(svg.count('<g class="group'), 1)
        self.assertEqual(re.findall(r'<g class="zlane" data-zone="([^"]*)"', svg), ["z1", ""])
        self.assertEqual(re.findall(r'class="zc"[^>]*>([^<]*)<', svg), ["Zone One (frontend)", "zone not recorded"])

    def test_deployment_horizontal_runs_do_not_overlap_or_touch_text_and_borders(self) -> None:
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            svg = deployment_svg(catalog, sdp["uid"])
            self._assert_runs_clean(svg)  # D35: co-visible runs keep apart; others may share a track
            horizontals = []
            for _s, _t, pts in edge_polylines(svg):
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    if ay == by and ax != bx:
                        horizontals.append((ay, min(ax, bx), max(ax, bx)))
            lanes = [tuple(int(v) for v in m) for m in re.findall(r'<rect class="zl" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg)]
            captions = [int(y) for y in re.findall(r'<text class="zc" x="\d+" y="(\d+)"', svg)]
            self.assertGreaterEqual(len(captions), len(lanes))
            for y, x0, x1 in horizontals:
                for lx, ly, lw, lh in lanes:
                    if not (x0 < lx + lw and lx < x1):
                        continue
                    self.assertGreaterEqual(abs(y - ly), 3, f"run on lane top border at y={y}")
                    self.assertGreaterEqual(abs(y - (ly + lh)), 3, f"run on lane bottom border at y={y}")
                    for cy in captions:
                        if ly <= cy <= ly + 40:
                            self.assertFalse(cy - 13 <= y <= cy + 8, f"run inside caption band at y={y}")

    def test_deployment_derived_host_and_mismatch_captions(self) -> None:
        objects = [
            plain("RTC-1", "runtime_service", "Cluster"),
            plain("RTC-2", "runtime_service", "Cluster Two", host="HST-1"),
            plain("HST-1", "host", "Host One"),
            plain("DST-1", "data_store_service", "Store"),
            plain("P-2", "product_component", "Beta", runsOn="RTC-1"),
            plain("P-5", "product_component", "Epsilon", runsOn="RTC-2"),
            plain("P-7", "product_component", "Eta"),
            pattern({"Derived": ["P-2"], "OnHost": ["P-5"], "Mismatch": ["P-7"]}),
        ]
        groups = objects[-1]["serviceGroups"]
        groups[1]["substrate"] = "RTC-2"
        groups[2]["substrate"] = "DST-1"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        model = generate_diagram.build_diagram_model(cat, cat["SDP-1"], False)
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        groups_svg = re.findall(r'<g class="(group[^"]*)"[^>]*>.*?(?=<g class="group|</g>\n</g>\n<g class="group|$)', svg, re.S)
        self.assertEqual(groups_svg, ["group dashed", "group", "group"])
        captions = []
        for block in re.split(r'(?=<g class="group)', svg)[1:]:
            captions.append(" ".join(xml_unescape(t) for t in re.findall(r'class="gc"[^>]*>([^<]*)<', block.split('<g class="zlane"')[0])))
        self.assertEqual(captions, [c.caption for c in model.containers])
        self.assertEqual(captions, ["Cluster derived", "Cluster Two on Host One", "Store (data_store_service)"])

    def test_deployment_self_loops_are_clear_of_other_edges(self) -> None:
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            svg = deployment_svg(catalog, sdp["uid"])
            routed = edge_polylines(svg)
            for match in re.finditer(r'<g class="edge" data-from="([^"]*)" data-to="\1"><title>[^<]*</title><path class="ln" d="(M[^"]*)"', svg):
                numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", match.group(2))]
                x0, x1, y0, y1 = min(numbers[0::2]), max(numbers[0::2]), min(numbers[1::2]), max(numbers[1::2])
                for _s, _t, pts in routed:
                    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                        crosses = min(ax, bx) <= x1 and max(ax, bx) >= x0 and min(ay, by) <= y1 and max(ay, by) >= y0
                        self.assertFalse(crosses, f"edge segment {(ax, ay, bx, by)} runs through the self-loop of {match.group(1)}")

    def test_deployment_rects_inside_viewbox(self) -> None:
        catalog = load_catalog(FIXTURE)
        objects = [component("A-1", "Alpha"), pattern({"G": ["A-1"]}), relationship("R-1", "A-1", "A-1", "loop")]
        small = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svgs = [deployment_svg(catalog, sdp["uid"]) for sdp in generate_diagram.sdps(catalog)] + [deployment_svg(small, "SDP-1")]
        own = [plain("RT-1", "runtime_service", "Runtime"), pattern({"Own": ["RT-1"]})] + [relationship(f"R-{k}", "RT-1", "RT-1", f"loop {k}") for k in range(7)]
        own[1]["serviceGroups"][0]["substrate"] = "RT-1"
        svgs.append(deployment_svg(load_catalog(write_workspace(Path(tempfile.mkdtemp()), own)), "SDP-1"))
        for svg in svgs:
            width, height = (int(v) for v in re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups())
            for x, y, w, h in re.findall(r'<rect class="[^"]*" x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"', svg):
                self.assertGreaterEqual(int(x), 0)
                self.assertLessEqual(int(x) + int(w), width, (x, w, width))
                self.assertLessEqual(int(y) + int(h), height)
            for d in re.findall(r'<path class="ln" d="([^"]*)"', svg):  # loops and routes too, control points included
                numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
                self.assertLessEqual(max(numbers[0::2]), width, d)
                self.assertGreaterEqual(min(numbers[1::2]), 0, d)

    def test_vertical_runs_keep_clear_of_container_borders(self) -> None:
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            svg = deployment_svg(catalog, sdp["uid"])
            borders = []
            for x, y, w, h in re.findall(r'<rect class="(?:tgt|grp|zl|lane stray|lane)" x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"', svg):
                borders += [(int(x), int(y), int(y) + int(h)), (int(x) + int(w), int(y), int(y) + int(h))]
            for _s, _t, pts in edge_polylines(svg):
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    if ax != bx:
                        continue
                    for bxx, by0, by1 in borders:
                        if min(ay, by) < by1 and max(ay, by) > by0:
                            self.assertGreaterEqual(abs(ax - bxx), generate_diagram.DEPLOY_BORDER_CLEAR, f"vertical run at x={ax} beside border x={bxx}")

    def test_stray_substrates_joined_by_an_edge_render(self) -> None:
        objects = [
            plain("RTC-1", "runtime_service", "One"),
            plain("RTC-2", "runtime_service", "Two"),
            pattern({"E1": [], "E2": []}),
            relationship("R-1", "RTC-1", "RTC-2", "talks"),
        ]
        objects[2]["serviceGroups"][0]["substrate"] = "RTC-1"
        objects[2]["serviceGroups"][1]["substrate"] = "RTC-2"
        for name in ("RTC-1", "RTC-2"):
            objects[2]["serviceGroups"][0 if name == "RTC-1" else 1]["deployableObjects"] = [{"ref": name}]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertEqual(len(edge_polylines(svg)), 1)
        self.assertEqual(edges_hitting_foreign_boxes(svg), [])

    def test_unplaced_substrate_of_empty_group_is_warned(self) -> None:
        objects = [component("P-1", "Alpha"), plain("RTC-9", "runtime_service", "Lonely"), pattern({"Full": ["P-1"], "Empty": []})]
        objects[2]["serviceGroups"][1]["substrate"] = "RTC-9"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        model = generate_diagram.build_diagram_model(cat, cat["SDP-1"], False)
        self.assertEqual(
            [w for w in model.warnings if w.startswith("substrate of a group")],
            ["substrate of a group with no drawable objects is not drawn: Lonely (RTC-9) in Empty"],
        )
        self.assertNotIn('data-id="RTC-9"', deployment_svg(cat, "SDP-1"))

    def _borders_of(self, svg: str) -> tuple:
        rect = r'<rect class="%s" x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"'
        return tuple([tuple(int(v) for v in m) for m in re.findall(rect % cls, svg)] for cls in ("tgt", "grp", "zl"))

    def test_deployment_geometry_stays_inside_borders(self) -> None:
        catalog = load_catalog(FIXTURE)
        objects = [component("A-1", "Alpha"), component("B-1", "Beta"), pattern({"G": ["A-1", "B-1"]})]
        objects += [relationship(f"R-{k}", "A-1", "A-1", f"loop {k}") for k in range(3)]
        small = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        cases = [deployment_svg(catalog, sdp["uid"]) for sdp in generate_diagram.sdps(catalog)] + [deployment_svg(small, "SDP-1")]
        for svg in cases:
            targets, groups, lanes = self._borders_of(svg)

            def inside(inner: tuple, outer: tuple, margin: int = 3) -> bool:
                return (
                    inner[0] >= outer[0] + margin and inner[1] >= outer[1] + margin
                    and inner[0] + inner[2] <= outer[0] + outer[2] - margin and inner[1] + inner[3] <= outer[1] + outer[3] - margin
                )

            for group in groups:
                self.assertTrue(any(inside(group, t) for t in targets), group)
            for lane in lanes:
                self.assertTrue(any(inside(lane, g) for g in groups), lane)
            strays = [tuple(int(v) for v in m) for m in re.findall(r'<rect class="lane stray" x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"', svg)]
            for box in node_rects(svg).values():
                if not targets or box[0] < max(t[0] + t[2] for t in targets):
                    self.assertTrue(any(inside(box, lane) for lane in lanes + strays), box)
            outside = re.search(r'<rect class="lane" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg)
            for match in re.finditer(r'<g class="edge" data-from="([^"]*)" data-to="\1"><title>[^<]*</title><path class="ln" d="(M[^"]*)"', svg):
                numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", match.group(2))]
                box = node_rects(svg).get(match.group(1).replace("&amp;", "&"))
                if box is None:
                    continue  # a container's loop sits on the container border, not inside a lane
                loop = (min(numbers[0::2]), min(numbers[1::2]), max(numbers[0::2]) - min(numbers[0::2]), max(numbers[1::2]) - min(numbers[1::2]))
                homes = lanes + strays
                if outside and box[0] >= int(outside.group(1)):
                    homes = [tuple(int(outside.group(i)) for i in range(1, 5))]
                self.assertTrue(any(inside(loop, lane) for lane in homes), f"loop {loop} leaves its lane")
        self.assertEqual(len(re.findall(r'class="ln[^"]*" d="M[\d.]+ [\d.]+ C', cases[-1])), 3)  # the line paths; the D34 overlay repeats each

    def test_loops_keep_the_logical_shape(self) -> None:
        objects = [component("A-1", "Alpha"), pattern({"G": ["A-1"]}), relationship("R-1", "A-1", "A-1", "one"), relationship("R-2", "A-1", "A-1", "two")]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        deploy = deployment_svg(cat, "SDP-1")
        logical = logical_svg(cat, "SDP-1")
        shape = lambda svg: [re.sub(r"-?\d+(?:\.\d+)?", "#", d) for d in re.findall(r'class="ln[^"]*" d="(M[^"]*C[^"]*)"', svg)]
        self.assertEqual(shape(deploy), shape(logical))
        self.assertEqual(len(shape(deploy)), 2)

    def test_group_listing_only_its_own_substrate_is_drawn_as_its_container(self) -> None:
        # D7 with D29: the substrate listed among the group's own objects is the container, never a box (R2 of the
        # third S6 review), and the group is drawn even though it has no box inside.
        objects = [
            plain("RTC-1", "runtime_service", "Cluster"),
            component("P-1", "Alpha"),
            pattern({"Full": ["P-1"], "Own": ["RTC-1"]}),
            relationship("R-1", "RTC-1", "P-1", "serves"),
        ]
        objects[2]["serviceGroups"][1]["substrate"] = "RTC-1"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        model = generate_diagram.build_diagram_model(cat, cat["SDP-1"], False)
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertRegex(svg, r'<g class="group" data-id="RTC-1" data-group="Own">')
        self.assertNotRegex(svg, r'<g class="node[^"]*" data-id="RTC-1"')
        self.assertNotIn('class="stray"', svg)
        self.assertIn('data-from="RTC-1" data-to="P-1"', svg)
        self.assertNotIn("Service groups recorded with no objects", svg)
        self.assertIn("substrate also listed as deployable object: Cluster (RTC-1) in Own", model.warnings)
        self.assertEqual([w for w in model.warnings if w.startswith("substrate of a group")], [])
        self.assertEqual([(c.group, c.drawn, c.members) for c in model.containers], [("Full", True, ["P-1"]), ("Own", True, [])])
        self.assertEqual(edges_hitting_foreign_boxes(svg), [])

    def test_group_listing_only_an_undrawn_groups_substrate_is_drawn(self) -> None:
        # D6 with D29: a group with no objects is not drawn, so its substrate is not a container; the group that
        # lists that object draws it as a box (R1 of the third S6 review).
        objects = [plain("RTC-1", "runtime_service", "Cluster"), pattern({"Lists": ["RTC-1"], "Empty": []})]
        objects[1]["serviceGroups"][1]["substrate"] = "RTC-1"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        model = generate_diagram.build_diagram_model(cat, cat["SDP-1"], False)
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertRegex(svg, r'<g class="group" data-group="Lists">')
        self.assertRegex(svg, r'<g class="node[^"]*" data-id="RTC-1"')
        self.assertNotIn('data-id="RTC-1" data-group', svg)
        self.assertIn("Empty (azure)", svg.split("Service groups recorded with no objects")[1])
        self.assertEqual([(c.group, c.drawn) for c in model.containers], [("Lists", True), ("Empty", False)])
        self.assertIn("substrate of a group with no drawable objects kept as a box: Cluster (RTC-1) in Empty", model.warnings)

    def test_targets_follow_document_order_of_every_group(self) -> None:
        # D6: a target named first by a group that is not drawn still comes first.
        objects = [component("P-1", "Alpha"), component("P-2", "Beta"), pattern({"E": [], "A": ["P-1"], "B": ["P-2"]})]
        groups = objects[2]["serviceGroups"]
        groups[0]["deploymentTarget"] = groups[2]["deploymentTarget"] = "later-in-the-alphabet"
        groups[1]["deploymentTarget"] = "azure"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        self.assertEqual(re.findall(r'<g class="target" data-target="([^"]*)"', svg), ["later-in-the-alphabet", "azure"])

    def test_container_and_its_own_boxes_attach_bottom_out_top_in(self) -> None:
        # D29 as amended by D36: edges between a container and boxes drawn inside it leave through the bottom side
        # and enter through the top side like every other edge, so no end sits on a side border.
        objects = [plain("RTC-1", "runtime_service", "Cluster")] + [component(f"P-{k}", f"Part {k}") for k in range(6)]
        objects.append(pattern({"G": [f"P-{k}" for k in range(6)] + ["RTC-1"]}))
        objects[-1]["serviceGroups"][0]["substrate"] = "RTC-1"
        objects += [relationship("R-1", "P-0", "RTC-1", "deploys to"), relationship("R-2", "RTC-1", "P-3", "hosts"), relationship("R-3", "P-3", "RTC-1", "reports to")]
        objects += [relationship("R-4", "P-0", "RTC-1", "also")]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        polys = edge_polylines(svg)
        self.assertEqual(len(polys), 4)
        gx, gy, gw, gh = endpoint_rects(svg)["RTC-1"]
        for _s, _t, pts in polys:
            self.assertFalse(any(px in (gx, gx + gw) and gy < py < gy + gh for px, py in pts), pts)
        into = [pts[-1] for _s, t_uid, pts in polys if t_uid == "RTC-1"]
        self.assertEqual(len(set(into)), 1, "the container's in-edges share one attachment point (D36)")
        self.assertEqual(into[0][1], gy)
        self._assert_runs_clean(svg)
        self.assertEqual(edges_hitting_foreign_boxes(svg), [])
        self.assertTrue(all(int(x) % generate_diagram.GRID == 0 and int(y) % generate_diagram.GRID == 0 for x, y, _w, _h in node_rects(svg).values()))

    def test_all_empty_groups_caption_fits_the_figure(self) -> None:
        # D6: when every group is empty the caption is the figure's only content; the viewBox must hold it.
        objects = [component("P-1", "Alpha"), pattern({"Alpha Group": [], "Beta Group": []})]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        width = int(re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).group(1))
        captions = re.findall(r'<text class="cap" x="(\d+)" y="\d+">([^<]*)</text>', svg)
        self.assertTrue(captions)
        for x, text in captions:
            self.assertLessEqual(int(x) + 6 * len(text), width, text)
        self.assertIn("Alpha Group (azure), Beta Group (azure)", " ".join(text for _x, text in captions))

    def test_hub_in_edges_share_one_top_attachment(self) -> None:
        # D36: 60 inbound edges on one box all enter through its top side at one attachment point and share its
        # in-run; D35: the band above the hub grows only by the tracks its runs need, not by the edge count.
        names = [f"P-{k:02d}" for k in range(60)]
        objects = [component(u, u) for u in names] + [component("HUB-1", "Hub"), pattern({"G": names + ["HUB-1"]})]
        objects += [relationship(f"R-{k:02d}", u, "HUB-1", "calls") for k, u in enumerate(names)]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        rects = node_rects(svg)
        hub = rects["HUB-1"]
        ends = {pts[-1] for _s, _t, pts in edge_polylines(svg)}
        self.assertEqual(ends, {(hub[0] + hub[2] // 2 - generate_diagram.ATTACH_DX, hub[1])})
        row_above = max(y + h for _x, y, _w, h in rects.values() if y + h <= hub[1])
        tracks = 1 + sum(1 for _x, y, _w, h in rects.values() if y + h == row_above)  # the hub's in-run and the out-runs above it
        self.assertLessEqual(hub[1] - row_above, -(-generate_diagram._band_height(tracks, 0) // 10) * 10)
        self._assert_runs_clean(svg)
        self.assertEqual(edges_hitting_foreign_boxes(svg), [])

    def test_box_centred_on_its_own_container_attaches_to_the_border(self) -> None:
        # The ray from the container centre toward a box centred exactly on it has no direction (review round 4, R1):
        # the end must still lie on the container border, never inside it.
        objects = [plain("RT-1", "runtime_service", "Runtime")] + [component(f"C-{k}", f"Comp {k}") for k in range(7)]
        sdp = pattern({"G": [f"C-{k}" for k in range(7)]})
        sdp["networkZones"] = [{"id": "z0", "name": "Zone Zero"}, {"id": "z1", "name": "Zone One"}]
        sdp["serviceGroups"][0]["substrate"] = "RT-1"
        for entry, zone in zip(sdp["serviceGroups"][0]["deployableObjects"], ("z1", "z1", "z0", "z1", "z1", None, "z0")):
            if zone:
                entry["networkZone"] = zone
        objects += [sdp, relationship("R-1", "C-1", "RT-1", "a"), relationship("R-2", "C-2", "RT-1", "b"), relationship("R-6", "C-6", "RT-1", "c")]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        self.assertEqual(len(edge_polylines(svg)), 3)
        self._assert_runs_clean(svg)
        self.assertEqual(edges_hitting_foreign_boxes(svg), [])
        objects2 = [plain("RT-1", "runtime_service", "Runtime"), component("A-1", "Alpha"), pattern({"G": ["A-1"]}), relationship("R-1", "A-1", "RT-1", "x")]
        objects2[2]["serviceGroups"][0]["substrate"] = "RT-1"  # one box: its centre x is left of the container centre
        cat2 = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects2))
        self._assert_runs_clean(deployment_svg(cat2, "SDP-1"))

    def test_self_relationship_on_a_container_is_a_loop_on_its_corner(self) -> None:
        # D13 with D29: a self-relationship whose endpoint is drawn as a container keeps the loop, off the
        # container's top-right corner, clear of the container's other edge ends and of the channels.
        objects = [plain("RT-1", "runtime_service", "Runtime"), component("A-1", "Alpha"), component("O-1", "Outside"), pattern({"G": ["A-1", "RT-1"], "Other": ["O-1"]})]
        objects[3]["serviceGroups"][0]["substrate"] = "RT-1"
        objects += [relationship("R-1", "RT-1", "RT-1", "self"), relationship("R-2", "RT-1", "A-1", "serves"), relationship("R-3", "RT-1", "O-1", "calls")]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        loop = re.search(r'<g class="edge" data-from="RT-1" data-to="RT-1"><title>[^<]*</title><path class="ln" d="(M[^"]*C[^"]*)"', svg)
        self.assertIsNotNone(loop, "the container's self-relationship is drawn")
        numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", loop.group(1))]
        gx, gy, gw, _gh = (int(v) for v in re.search(r'<rect class="grp" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg).groups())
        self.assertEqual((numbers[0], numbers[1]), (gx + gw - generate_diagram.LOGICAL_BOX_W + generate_diagram.LOGICAL_BOX_W * 0.62, gy))
        x0, x1, y0, y1 = min(numbers[0::2]), max(numbers[0::2]), min(numbers[1::2]), max(numbers[1::2])
        for _s, _t, pts in edge_polylines(svg):
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                self.assertFalse(min(ax, bx) <= x1 and max(ax, bx) >= x0 and min(ay, by) <= y1 and max(ay, by) >= y0, f"segment {(ax, ay, bx, by)} meets the container loop")
        self._assert_runs_clean(svg)
        self.assertNotIn('data-from="RT-1"', logical_svg(cat, "SDP-1"))  # D43: infrastructure edges are deployment-only

    def test_many_container_out_edges_share_one_bottom_attachment(self) -> None:
        # A group listing only its own substrate is a small container with twelve edges to two outside nodes: D36
        # sends all of them through one attachment point on its bottom border, whatever the border's length.
        objects = [plain("RT-1", "runtime_service", "Runtime"), component("O-1", "Outside One"), component("O-2", "Outside Two"), pattern({"Own": ["RT-1"], "Other": ["O-1", "O-2"]})]
        objects[3]["serviceGroups"][0]["substrate"] = "RT-1"
        objects += [relationship(f"R-{k:02d}", "RT-1", "O-1" if k % 2 else "O-2", f"rel {k}") for k in range(12)]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        polys = edge_polylines(svg)
        self.assertEqual(len(polys), 12)
        starts = [pts[0] for _s, _t, pts in polys]
        gx, gy, gw, gh = endpoint_rects(svg)["RT-1"]
        self.assertEqual(set(starts), {(gx + gw // 2 + generate_diagram.ATTACH_DX, gy + gh)}, "D36: one bottom attachment point")
        self._assert_runs_clean(svg)
        self.assertEqual(edges_hitting_foreign_boxes(svg), [])

    def test_groups_naming_each_others_substrate_are_both_drawn(self) -> None:
        # G lists RT-2 and names RT-1 as substrate; H lists RT-1 and names RT-2. Neither object may vanish: both
        # groups are drawn, each as the container of its own substrate (review round 6, R1).
        objects = [plain("RT-1", "runtime_service", "Runtime One"), plain("RT-2", "runtime_service", "Runtime Two"), component("P-1", "Alpha"), pattern({"G": ["RT-2"], "H": ["RT-1"], "J": ["P-1"]})]
        objects[3]["serviceGroups"][0]["substrate"] = "RT-1"
        objects[3]["serviceGroups"][1]["substrate"] = "RT-2"
        objects += [relationship("R-1", "RT-1", "P-1", "uses"), relationship("R-2", "RT-1", "RT-2", "peers")]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        model = generate_diagram.build_diagram_model(cat, cat["SDP-1"], False)
        self.assertEqual([(c.group, c.drawn, c.members) for c in model.containers], [("G", True, []), ("H", True, []), ("J", True, ["P-1"])])
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertRegex(svg, r'<g class="group" data-id="RT-1" data-group="G">')
        self.assertRegex(svg, r'<g class="group" data-id="RT-2" data-group="H">')
        self.assertEqual(len(edge_polylines(svg)), 2)
        self.assertNotIn("Service groups recorded with no objects", svg)
        self.assertEqual([w for w in model.warnings if w.startswith("substrate of a group")], [])
        self._assert_runs_clean(svg)

    def test_container_out_edges_share_one_attachment_clear_of_its_loop(self) -> None:
        # A container with a self-loop, eight edges to an outside node above and eleven to one below: D36 sends all
        # nineteen through one bottom attachment point, and the routes stay clean of the loop (D13).
        objects = [plain("RT-1", "runtime_service", "Runtime"), component("O-1", "Above"), component("O-2", "Below"), component("P-1", "Alpha"), pattern({"Up": ["O-1"], "Own": ["RT-1"], "Down": ["O-2"], "Rest": ["P-1"]})]
        objects[4]["serviceGroups"][1]["substrate"] = "RT-1"
        objects += [relationship("R-00", "RT-1", "RT-1", "self")]
        objects += [relationship(f"R-{k:02d}", "RT-1", "O-1", f"up {k}") for k in range(1, 9)]
        objects += [relationship(f"R-{k:02d}", "RT-1", "O-2", f"down {k}") for k in range(9, 20)]
        objects += [relationship("R-90", "P-1", "O-1", "x")] + [relationship(f"R-{k}", "P-1", "O-2", "y") for k in range(91, 97)]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        polys = edge_polylines(svg)
        starts = [pts[0] for s_uid, _t, pts in polys if s_uid == "RT-1"]
        self.assertEqual(len(starts), 19)
        self.assertEqual(len(set(starts)), 1, "D36: the container's out-edges share one attachment point")
        self._assert_runs_clean(svg)

    def test_deployment_boxes_sit_on_the_grid(self) -> None:
        # D14: positions snapped to a fixed grid, in the deployment view as well.
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            for uid, (x, y, _w, _h) in node_rects(deployment_svg(catalog, sdp["uid"])).items():
                self.assertEqual((x % generate_diagram.GRID, y % generate_diagram.GRID), (0, 0), (sdp["uid"], uid, x, y))

    def _seeded_objects(self, seed: int, zones: bool = False, outside: bool = False) -> list:
        """A random but reproducible pattern: shared runtime and host substrates over three targets, substrates
        listed in their own group, boxes in every column with edges to their own container, loops, parallel
        edges, outside nodes with many edges, external endpoints and, optionally, declared zones."""
        import random

        rnd = random.Random(seed)
        runtimes = [plain(f"RT-{k}", "runtime_service", f"Runtime {k}") for k in range(3)] + [plain("HST-1", "host", "Host One")]
        comps = [component(f"C-{k}", f"Comp {k}") for k in range(rnd.randint(4, 16))]
        groups: dict = {}
        pool = [c["uid"] for c in comps]
        rnd.shuffle(pool)
        for g in range(rnd.randint(2, 5)):
            take = pool[: rnd.randint(0, 5)]
            pool = pool[len(take) :]
            groups[f"G{g}"] = take
        sdp = pattern(groups)
        if zones:
            sdp["networkZones"] = [{"id": "z1", "name": "Zone One", "tier": "frontend"}, {"id": "z2", "name": "Zone Two", "tier": "data"}]
        for entry in sdp["serviceGroups"]:
            entry["deploymentTarget"] = rnd.choice(["target-a", "target-b", "target-c"])
            if rnd.random() < 0.8:
                entry["substrate"] = rnd.choice(["RT-0", "RT-1", "RT-2", "HST-1"])
                if rnd.random() < 0.3:
                    entry["deployableObjects"].append({"ref": entry["substrate"]})
            if zones:
                for obj in entry["deployableObjects"]:
                    r = rnd.random()
                    if r < 0.7:
                        obj["networkZone"] = "z1" if r < 0.4 else "z2"
        uids = [c["uid"] for c in comps] + [r["uid"] for r in runtimes]
        extra = []
        if outside:
            extra = [component(f"O-{k}", f"Outside {k}") for k in range(rnd.randint(1, 4))]
            uids += [o["uid"] for o in extra]
        rels = [relationship(f"R-{k:02d}", rnd.choice(uids), rnd.choice(uids), f"rel {k}") for k in range(rnd.randint(6, 30))]
        if rnd.random() < 0.5:
            rels.append({"schemaVersion": "1.0", "uid": "R-X", "type": "relationship", "name": "R-X", "source": uids[0], "externalTarget": "Outside Service", "label": "calls"})
        return runtimes + comps + extra + [sdp] + rels

    def test_outside_node_runs_dodge_dense_stack_runs(self) -> None:
        # One row of three boxes with six pairwise edges, plus an outside node whose six edges come first in uid
        # order so its channels lie left of the stack edges' channels: every outside-lane run must dodge a stack
        # run, which needs more levels than the lane's own edge count (review round 2, R1).
        objects = [component(u, u) for u in ("A-1", "B-1", "C-1")] + [component("O-1", "Outside")]
        objects.append(pattern({"G": ["A-1", "B-1", "C-1"]}))
        objects += [relationship(f"R-0{k}", u, "O-1", "o") for k, u in enumerate(("A-1", "B-1", "C-1", "A-1", "B-1", "C-1"))]
        pairs = [("A-1", "B-1"), ("B-1", "C-1"), ("A-1", "C-1"), ("B-1", "A-1"), ("C-1", "B-1"), ("C-1", "A-1")]
        objects += [relationship(f"R-1{k}", a, b, "s") for k, (a, b) in enumerate(pairs)]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        self.assertEqual(len(edge_polylines(svg)), 12)
        self._assert_runs_clean(svg)
        self.assertEqual(edges_hitting_foreign_boxes(svg), [])

    def test_in_edges_from_one_column_join_the_containers_in_run(self) -> None:
        # Two first-column boxes in different rows of one container both call it: D36 sends both through their own
        # bottom sides to the container's single top attachment point (D29 as amended by D36).
        parts = [component(f"P-{k:02d}", f"Part {k}") for k in range(12)]
        objects = [plain("RTC-1", "runtime_service", "Cluster")] + parts + [pattern({"G": [p["uid"] for p in parts]})]
        objects[-1]["serviceGroups"][0]["substrate"] = "RTC-1"
        objects += [relationship("R-1", "P-03", "RTC-1", "a"), relationship("R-2", "P-00", "RTC-1", "b")]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        polys = edge_polylines(svg)
        self.assertEqual(len(polys), 2)
        self.assertEqual(polys[0][2][-1], polys[1][2][-1])
        self._assert_runs_clean(svg)

    def test_seeded_patterns_route_cleanly(self) -> None:
        for seed in range(1, 16):
          for zones, outside in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(seed=seed, zones=zones, outside=outside):
                cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), self._seeded_objects(seed, zones, outside)))
                svg = deployment_svg(cat, "SDP-1")
                xml.dom.minidom.parseString(svg)
                self._assert_runs_clean(svg)
                self.assertEqual(edges_hitting_foreign_boxes(svg), [])
                for uid, (x, y, _w, _h) in node_rects(svg).items():
                    self.assertEqual((x % generate_diagram.GRID, y % generate_diagram.GRID), (0, 0), (uid, x, y))
                self.assertEqual(svg, deployment_svg(dict(reversed(list(cat.items()))), "SDP-1"))
                # AC21 in the logical figure too: D35 tracks, D36 sides, no foreign box, byte-identical.
                logical = logical_svg(cat, "SDP-1")
                xml.dom.minidom.parseString(logical)
                self.assertEqual(side_violations(logical), [])
                self.assertEqual(covisible_track_clashes(logical), [])
                self.assertEqual(edges_hitting_foreign_boxes(logical), [])
                self.assertEqual(covisible_stub_crossings(logical, logical_free_x(cat, "SDP-1")), [])
                self.assertEqual(logical, logical_svg(dict(reversed(list(cat.items()))), "SDP-1"))

    def test_fixture_routes_keep_covisible_tracks_apart_and_attach_bottom_out_top_in(self) -> None:
        # AC21 on every fixture pattern, both figures.
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            for render in (logical_svg, deployment_svg):
                with self.subTest(sdp=sdp["uid"], view=render.__name__):
                    svg = render(catalog, sdp["uid"])
                    self.assertGreater(len(edge_polylines(svg)), 0)
                    self.assertEqual(side_violations(svg), [])
                    self.assertEqual(covisible_track_clashes(svg), [])
                    self.assertEqual(edges_hitting_foreign_boxes(svg), [])
                    if render is logical_svg:  # the deployment figure checks stubs in _assert_runs_clean
                        self.assertEqual(covisible_stub_crossings(svg, logical_free_x(catalog, sdp["uid"])), [])

    def test_logical_stubs_are_not_crossed_whatever_the_document_order(self) -> None:
        # Review round 1, R1: four services in one row feeding one database in the next, and a hub with eight
        # in-edges from the row above, in forward, reversed and mixed relationship order. No run may cross a
        # co-visible stub or drop, and the figure must be the same in every order.
        def tiered(objects: list, tiers: dict) -> list:
            for entry in objects[-1]["serviceGroups"][0]["deployableObjects"]:
                entry["diagramTier"] = tiers[entry["ref"]]
            return objects

        services = [f"S-{k}" for k in range(4)]
        ups = [f"U-{k:02d}" for k in range(8)]
        cases = {
            "staircase": (services + ["DB-1"], {**{u: "application" for u in services}, "DB-1": "data"}, [(u, "DB-1") for u in services]),
            "hub": (ups + ["HUB-1"], {**{u: "presentation" for u in ups}, "HUB-1": "application"}, [(ups[(k * 5) % 8], "HUB-1") for k in range(8)]),
        }
        for name, (uids, tiers, pairs) in cases.items():
            renders = []
            for order in (pairs, pairs[::-1], pairs[1::2] + pairs[0::2]):
                objects = tiered([component(u, u) for u in uids] + [pattern({"G": uids})], tiers)
                objects += [relationship(f"R-{n}", a, b, "reads") for n, (a, b) in enumerate(order)]
                cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
                svg = logical_svg(cat, "SDP-1")
                with self.subTest(case=name, order=order[0]):
                    self.assertEqual(covisible_stub_crossings(svg, logical_free_x(cat, "SDP-1")), [])
                    self.assertEqual(covisible_track_clashes(svg), [])
                renders.append(re.sub(r"<title>[^<]*</title>|data-[a-z]+=\"R-\d+\"", "", "\n".join(sorted(re.findall(r'<path class="ln[^"]*" d="[^"]*"', svg)))))
            self.assertEqual(len(set(renders)), 1, f"{name}: routes depend on relationship order")

    def test_fan_out_into_one_gutter_shares_attachment_and_first_run(self) -> None:
        # D36 on the fixture: the out-edges of one box share their first point and their first run (the stub down
        # to the out-run and the out-run's y); out-edges that go on into the same gutter share the run to it too.
        catalog = load_catalog(FIXTURE)
        seen = 0
        for sdp in generate_diagram.sdps(catalog):
            for render in (logical_svg, deployment_svg):
                by_source: dict = {}
                for source, _t, pts in edge_polylines(render(catalog, sdp["uid"])):
                    by_source.setdefault(source, []).append(pts)
                for source, routes in sorted(by_source.items()):
                    if len(routes) < 2:
                        continue
                    self.assertEqual(len({pts[0] for pts in routes}), 1, (sdp["uid"], source))
                    self.assertEqual(len({pts[1] for pts in routes}), 1, (sdp["uid"], source))
                    gutters: dict = {}
                    for pts in routes:
                        if len(pts) >= 5:  # down, across to a gutter or channel, then along it
                            gutters.setdefault(pts[2][0], []).append(pts)
                    for x, group in sorted(gutters.items()):
                        if len(group) >= 2:
                            seen += 1
                            self.assertEqual(len({tuple(pts[:3]) for pts in group}), 1, (sdp["uid"], source, x))
        self.assertGreater(seen, 0, "the fixture must have a box with two out-edges into one gutter")

    def test_row_gaps_grow_only_with_covisible_density(self) -> None:
        # D35 growth bound: 16 boxes in one band, 160 edges i -> i + k (k = 1..10, mod 16), so every box has 20 edges
        # and the largest set of pairwise co-visible edges is 20. No row gap may exceed 20 * pitch + 2 * pad.
        uids = [f"P-{i:02d}" for i in range(16)]
        objects = [component(u, u) for u in uids] + [pattern({"G": uids})]
        for entry in objects[-1]["serviceGroups"][0]["deployableObjects"]:
            entry["diagramTier"] = "application"
        edges = [(uids[i], uids[(i + k) % 16]) for k in range(1, 11) for i in range(16)]
        objects += [relationship(f"R-{n:03d}", a, b, "x") for n, (a, b) in enumerate(edges)]
        degree: dict = {}
        for a, b in edges:
            degree[a] = degree.get(a, 0) + 1
            degree[b] = degree.get(b, 0) + 1
        self.assertEqual((len(edges), max(degree.values())), (160, 20))
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = logical_svg(cat, "SDP-1")
        self.assertEqual(len(edge_polylines(svg)), 160)
        bound = 20 * generate_diagram.TRACK_PITCH + 2 * generate_diagram.LOGICAL_TRACK_PAD
        rows = sorted({y for _x, y, _w, _h in node_rects(svg).values()})
        self.assertEqual(len(rows), 4)
        for upper, lower in zip(rows, rows[1:]):
            self.assertLessEqual(lower - upper - generate_diagram.LOGICAL_BOX_H, bound, (upper, lower))
        band_y, band_h = (int(v) for v in re.search(r'<rect class="band" x="\d+" y="(\d+)" width="\d+" height="(\d+)"', svg).groups())
        self.assertLessEqual(rows[0] - band_y, bound)  # the gap above the first row
        self.assertLessEqual(band_y + band_h - rows[-1] - generate_diagram.LOGICAL_BOX_H, bound)  # and below the last
        self.assertEqual(side_violations(svg), [])
        self.assertEqual(covisible_track_clashes(svg), [])
        self.assertEqual(edges_hitting_foreign_boxes(svg), [])

    def test_edge_runs_stay_in_free_bands_and_channels(self) -> None:
        """Comb routing: vertical runs are stubs inside a lane or channels right of every target and left of the
        outside lane; horizontal runs never cross a target label, group header or lane caption area."""
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            svg = deployment_svg(catalog, sdp["uid"])
            rect = r'<rect class="%s" x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"'
            targets, groups, lanes = ([tuple(int(v) for v in m) for m in re.findall(rect % cls, svg)] for cls in ("tgt", "grp", "zl"))
            outside = re.search(rect % "lane", svg)
            lane_left = int(outside.group(1)) if outside else math.inf
            stack_right = max(x + w for x, _y, w, _h in targets)
            heads = []  # caption areas: from the top of a target, group or lane to its first child
            for x, y, w, h in targets:  # the label; the band below it carries the first group's container ends
                heads.append((x, x + w, y, y + generate_diagram.DEPLOY_TARGET_HEAD))
            for x, y, w, h in groups:
                inner = [l for l in lanes if x < l[0] < x + w and y < l[1] < y + h]
                # a data store container (D45) has no lanes; its caption and type chip fill the top 44 px
                heads.append((x, x + w, y, min(l[1] for l in inner) if inner else min(y + h, y + 44)))
            for x, y, w, h in lanes:
                heads.append((x, x + w, y, y + generate_diagram.DEPLOY_LANE_HEAD))
            for _s, _t, pts in edge_polylines(svg):
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    if ax == bx:
                        in_lane = any(x < ax < x + w and y < min(ay, by) and max(ay, by) < y + h + generate_diagram.DEPLOY_PAD for x, y, w, h in lanes)
                        beside = any(x - generate_diagram.DEPLOY_PAD < ax < x for x, _y, _w, _h in groups)  # left-border container end
                        in_outside = bool(outside) and lane_left < ax < lane_left + int(outside.group(3))
                        self.assertTrue(in_lane or beside or in_outside or stack_right < ax < lane_left, f"vertical run at x={ax} is neither a stub nor a channel")
                    elif ay == by:
                        for x0, x1, y0, y1 in heads:
                            self.assertFalse(min(ax, bx) < x1 and x0 < max(ax, bx) and y0 <= ay <= y1, f"run at y={ay} crosses a caption area")

    def _assert_runs_clean(self, svg: str) -> None:
        """D35, D36: every edge leaves its source's bottom and enters its target's top; co-visible edges (sharing an
        endpoint) never share a track outside their fan bundle; co-visible horizontal runs closer than DEPLOY_LEVEL
        in y are DEPLOY_LEVEL apart in x; and no run crosses the stub of a co-visible edge (channels are the only
        verticals a run may cross). Edges that share no endpoint may share a track (D35)."""
        self.assertEqual(side_violations(svg), [])
        self.assertEqual(covisible_track_clashes(svg), [])
        targets = [tuple(int(v) for v in m) for m in re.findall(r'<rect class="tgt" x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"', svg)]
        outside = re.search(r'<rect class="lane" x="(-?\d+)"', svg)
        stack_right = max([x + w for x, _y, w, _h in targets], default=0)
        lane_left = int(outside.group(1)) if outside else math.inf
        edges = edge_polylines(svg)
        verticals, horizontals = [], []
        for number, (_s, _t, pts) in enumerate(edges):
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                if ax == bx and ay != by:
                    verticals.append((ax, min(ay, by), max(ay, by), number))
                elif ay == by and ax != bx:
                    horizontals.append((ay, min(ax, bx), max(ax, bx), number))

        def covisible(n1: int, n2: int) -> bool:
            return n1 != n2 and bool({edges[n1][0], edges[n1][1]} & {edges[n2][0], edges[n2][1]})

        for i, (y, x0, x1, n1) in enumerate(horizontals):
            for y2, a0, a1, n2 in horizontals[i + 1 :]:
                if covisible(n1, n2) and 0 < abs(y - y2) < generate_diagram.DEPLOY_LEVEL:
                    self.assertGreaterEqual(max(a0 - x1, x0 - a1), generate_diagram.DEPLOY_LEVEL, f"horizontal runs too close at y={y} and y={y2}")
        for y, x0, x1, n1 in horizontals:
            for x, y0, y1, n2 in verticals:
                if covisible(n1, n2) and not (stack_right < x < lane_left) and x0 < x < x1 and y0 < y < y1:
                    self.fail(f"run of edge {n1} at y={y} crosses the stub of edge {n2} at x={x}")

    def test_hub_with_many_inbound_edges_has_clean_runs(self) -> None:
        names = [f"P-{k:02d}" for k in range(20)]
        objects = [component(u, u) for u in names] + [component("HUB-1", "Hub"), pattern({"G": names + ["HUB-1"]})]
        objects += [relationship(f"R-{k:02d}", u, "HUB-1", "calls") for k, u in enumerate(names)]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertEqual(len(edge_polylines(svg)), 20)
        self._assert_runs_clean(svg)
        self.assertEqual(edges_hitting_foreign_boxes(svg), [])
        self.assertEqual(len({pts[-1] for _s, _t, pts in edge_polylines(svg)}), 1, "D36: the hub's in-edges share one point")
        for sdp in generate_diagram.sdps(load_catalog(FIXTURE)):
            self._assert_runs_clean(deployment_svg(load_catalog(FIXTURE), sdp["uid"]))

    def test_two_edges_leaving_one_container_share_attachment_and_out_run(self) -> None:
        objects = [
            plain("RTC-1", "runtime_service", "Cluster"),
            component("P-1", "Alpha"),
            component("X-1", "Xray"),
            component("Y-1", "Yankee"),
            pattern({"G": ["P-1", "RTC-1"], "H": ["X-1"], "I": ["Y-1"]}),
            relationship("R-1", "RTC-1", "X-1", "one"),
            relationship("R-2", "RTC-1", "Y-1", "two"),
        ]
        objects[4]["serviceGroups"][0]["substrate"] = "RTC-1"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        paths = edge_polylines(svg)
        self.assertEqual(len(paths), 2)
        self.assertEqual(paths[0][2][:2], paths[1][2][:2])  # D36: one attachment point and one out-run
        group = re.search(r'<g class="group[^"]*" data-id="RTC-1"[^>]*>.*?<rect class="grp" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg, re.S)
        gx, gy, gw, gh = (int(group.group(i)) for i in range(1, 5))
        for _s, _t, pts in paths:
            px, py = pts[0]
            self.assertTrue(gx <= px <= gx + gw and abs(py - (gy + gh)) < 0.11, "start lies on the container's bottom border")
        self._assert_runs_clean(svg)

    def test_placed_substrate_of_empty_group_stays_in_its_drawn_group(self) -> None:
        objects = [plain("RTC-1", "runtime_service", "Cluster"), component("P-1", "Alpha"), pattern({"A": ["P-1", "RTC-1"], "B": []})]
        objects[2]["serviceGroups"][1]["substrate"] = "RTC-1"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertNotIn('class="stray"', svg)
        lane = re.search(r'<g class="zlane".*?</g>\n</g>', svg, re.S).group(0)
        self.assertIn('data-id="P-1"', lane)
        self.assertIn('data-id="RTC-1"', lane)
        self.assertIn("Service groups recorded with no objects", svg)

    def test_outside_lane_in_deployment(self) -> None:
        catalog = load_catalog(FIXTURE)
        model = generate_diagram.build_diagram_model(catalog, catalog[FIXTURE_SDP], False)
        outer = [n for n in model.deployment_nodes if n.outside]
        self.assertTrue(outer)
        deployment = deployment_svg(catalog, FIXTURE_SDP)
        self.assertIn("External interactions", deployment)
        target_right = max(int(x) + int(w) for x, w in re.findall(r'<rect class="tgt" x="(\d+)" y="\d+" width="(\d+)"', deployment))
        rects = node_rects(deployment)
        logical = logical_svg(catalog, FIXTURE_SDP)
        for node in outer:
            self.assertGreater(rects[node.uid][0], target_right)
            if node.caption:
                self.assertIn(xml_escape(node.caption), deployment)
                self.assertIn(xml_escape(node.caption), logical)

    def test_deployment_order_independent_of_insertion_order(self) -> None:
        catalog = load_catalog(FIXTURE)
        for uid in (FIXTURE_SDP, "FXSDP00003-0001"):
            self.assertEqual(deployment_svg(catalog, uid), deployment_svg(dict(reversed(list(catalog.items()))), uid))

    def test_large_deployment_svg_valid_fast(self) -> None:
        import time

        catalog = load_catalog(FIXTURE)
        started = time.monotonic()
        svg = deployment_svg(catalog, "FXSDP00003-0001")
        self.assertLess(time.monotonic() - started, 30)
        xml.dom.minidom.parseString(svg)

    def test_edge_stroke_classes(self) -> None:
        objects = [component(f"C-{n}", n) for n in "ABCD"] + [pattern({"G": ["C-A", "C-B", "C-C", "C-D"]})]
        objects += [
            relationship("R-ASYNC", "C-A", "C-B", "a"),
            relationship("R-EVENT", "C-B", "C-C", "e"),
            relationship("R-SYNC", "C-C", "C-D", "s"),
            relationship("R-NONE", "C-D", "C-A", "n"),
        ]
        objects[5]["direction"] = "asynchronous"
        objects[6]["direction"] = "event"
        objects[7]["direction"] = "synchronous"
        classes = edge_classes(svg_for(objects))
        self.assertIn("dashed", classes[("C-A", "C-B")])
        self.assertIn("dotted", classes[("C-B", "C-C")])
        self.assertEqual(classes[("C-C", "C-D")], "ln")
        self.assertEqual(classes[("C-D", "C-A")], "ln")
        self.assertNotIn("dashed", classes[("C-C", "C-D")])
        self.assertNotIn("dotted", classes[("C-D", "C-A")])
        deployment = svg_for(objects, view="deployment")
        self.assertIn("dashed", edge_classes(deployment)[("C-A", "C-B")])

    def test_flow_arrowheads(self) -> None:
        names = "ABCDEFGH"
        objects = [component(f"C-{n}", n) for n in names] + [pattern({"G": [f"C-{n}" for n in names]})]
        flows = {("A", "B"): "inbound", ("C", "D"): "bidirectional", ("E", "F"): "outbound", ("G", "H"): None}
        for index, ((source, target), flow) in enumerate(flows.items()):
            rel = relationship(f"R-{index}", f"C-{source}", f"C-{target}", source)
            if flow:
                rel["flow"] = flow
            objects.append(rel)
        svg = svg_for(objects)
        paths = edge_paths(svg)
        start_marker, end_marker = 'marker-start="url(#lg-start)"', 'marker-end="url(#lg-end)"'
        self.assertIn(start_marker, paths[("C-A", "C-B")])
        self.assertNotIn(end_marker, paths[("C-A", "C-B")])
        self.assertIn(start_marker, paths[("C-C", "C-D")])
        self.assertIn(end_marker, paths[("C-C", "C-D")])
        self.assertIn(end_marker, paths[("C-E", "C-F")])
        self.assertNotIn(start_marker, paths[("C-E", "C-F")])
        self.assertIn(end_marker, paths[("C-G", "C-H")])
        self.assertNotIn(start_marker, paths[("C-G", "C-H")])
        self.assertIn('id="lg-start"', svg)
        self.assertIn('id="lg-end"', svg)

    def test_unknown_flow_warning(self) -> None:
        objects = [component("C-A", "A"), component("C-B", "B"), pattern({"G": ["C-A", "C-B"]})]
        rel = relationship("REL-X", "C-A", "C-B", "sideways")
        rel["flow"] = "sideways"
        objects.append(rel)
        model = model_of(objects)
        self.assertIn("unknown flow 'sideways' on REL-X", model.warnings)
        svg = svg_for(objects)
        self.assertIn('marker-end="url(#lg-end)"', edge_paths(svg)[("C-A", "C-B")])
        self.assertNotIn('marker-start="url(#lg-start)"', edge_paths(svg)[("C-A", "C-B")])

    def test_label_visibility_threshold(self) -> None:
        def chain(count: int) -> str:
            objects = [component(f"C-{n}", f"N{n}") for n in range(count + 1)]
            objects.append(pattern({"G": [f"C-{n}" for n in range(count + 1)]}))
            for n in range(count):
                rel = relationship(f"R-{n}", f"C-{n}", f"C-{n + 1}", f"rel {n}")
                if n == 0:
                    rel["technology"] = "HTTPS"
                objects.append(rel)
            return svg_for(objects)

        eight = chain(8)
        self.assertEqual(eight.count('class="lb"'), 8)
        self.assertNotIn('class="lb hov"', eight)
        nine = chain(9)
        self.assertEqual(nine.count('class="lb hov"'), 9)
        self.assertNotIn('class="lb"', nine)
        self.assertIn('<tspan class="tech"> / HTTPS</tspan>', eight)
        self.assertIn(".lb .tech{font-weight:400}", eight)

    def test_labels_clear_node_boxes(self) -> None:
        svg = logical_svg(load_catalog(FIXTURE), "FXSDP00002-0001")
        boxes = node_rects(svg)
        self.assertTrue(boxes)
        texts = []  # band labels and the outside lane caption: (left, top, width, height)
        for x, y, text in re.findall(r'<text class="(?:bl|ll)" x="([\d.]+)" y="([\d.]+)">([^<]*)</text>', svg):
            texts.append((float(x), float(y) - 11, len(xml_unescape(text)) * 7 + 4, 12))
        obstacles = [(bx, by, bw, bh) for bx, by, bw, bh in boxes.values()] + texts
        self.assertTrue(texts)
        for x, y, text in re.findall(r'<text class="lb" x="([\d.]+)" y="([\d.]+)" text-anchor="middle">([^<]*)</text>', svg):
            width = len(xml_unescape(text)) * 6.2 + 4
            left, top = float(x) - width / 2, float(y) - 13
            for bx, by, bw, bh in obstacles:
                clear = left + width <= bx or bx + bw <= left or top + 14 <= by or by + bh <= top
                self.assertTrue(clear, f"label '{text}' overlaps {bx, by}")

    def test_node_type_chip_and_tech_line(self) -> None:
        objects = [
            component("C-P", "Api", language="Python"),
            plain("D-1", "data_component", "Ledger", targetEngine="PostgreSQL"),
            plain("TC-1", "technology_component", "Engine X"),
            plain("S-1", "data_store_service", "Cache", productName="Aurora"),
            plain("S-2", "data_store_service", "Queue", primaryTechnologyComponent="TC-1"),
            plain("R-1", "runtime_service", "Runner", primaryTechnologyComponent="TC-MISSING"),
            plain("N-1", "network_service", "Edge", productName="Gateway Pro"),
            plain("G-1", "ai_gateway", "Llm"),
            plain("H-1", "host", "Box", computePlatformComponent="TC-1"),
            plain("H-2", "host", "Box two", operatingSystemComponent="TC-MISSING"),
        ]
        ids = [o["uid"] for o in objects if o["type"] != "technology_component"]
        objects.append(pattern({"G": ids}))
        external = relationship("R-EXT", "C-P", "", "calls out")
        external["externalTarget"] = "Partner API"
        objects.append(external)
        catalog = {o["uid"]: o for o in objects}
        tech = {uid: generate_diagram.technology_line(catalog, catalog[uid]) for uid in ids}
        self.assertEqual(tech["C-P"], "Python")
        self.assertEqual(tech["D-1"], "PostgreSQL")
        self.assertEqual(tech["S-1"], "Aurora")
        self.assertEqual(tech["S-2"], "Engine X")
        self.assertEqual(tech["R-1"], "TC-MISSING")
        self.assertEqual(tech["N-1"], "Gateway Pro")
        self.assertEqual(tech["G-1"], "")
        self.assertEqual(tech["H-1"], "Engine X")
        self.assertEqual(tech["H-2"], "TC-MISSING")
        svg = svg_for(objects, "deployment")  # D43: infrastructure boxes are drawn in the deployment view
        for chip in ("component", "data", "runtime", "network", "ai gateway", "host", "data store", "external"):
            self.assertRegex(svg, rf'class="chip-t" x="\d+" y="\d+">{chip}</text>', chip)
        self.assertIn('class="tech-line"', svg)
        self.assertRegex(svg, r'class="tech-line" x="\d+" y="\d+">TC-MISSING</text>')
        self.assertRegex(svg, r'class="tech-line" x="\d+" y="\d+">Python</text>')

    def test_lifecycle_and_theme_css(self) -> None:
        objects = [
            component("C-RET", "Old", lifecycleStatus="retired"),
            component("C-DEP", "Aging", lifecycleStatus="deprecated"),
            plain("SUB-1", "runtime_service", "Host Pool", lifecycleStatus="deprecated"),
            pattern({"G": ["C-RET", "C-DEP"]}),
        ]
        objects[3]["serviceGroups"][0]["substrate"] = "SUB-1"
        logical = svg_for(objects)
        self.assertIn("ret", class_of(logical, "C-RET").split())
        self.assertIn("dep", class_of(logical, "C-DEP").split())
        deployment = svg_for(objects, view="deployment")
        self.assertIn("dep", class_of(deployment, "SUB-1").split())
        for svg in (logical, deployment):
            self.assertIn("--chip-component:#dbeafe", svg)
            self.assertIn("@media (prefers-color-scheme:dark)", svg)
            self.assertIn('[data-theme="dark"]', svg)
            self.assertIn("--chip-component:#1e3a5f", svg)
            self.assertIn(".dep .box{stroke:var(--amber,#a85a00)}", svg)

    def test_svg_data_id_parity(self) -> None:
        catalog = load_catalog(FIXTURE)
        shared_seen = 0
        for sdp in generate_diagram.sdps(catalog):
            with self.subTest(sdp=sdp["uid"]):
                model = generate_diagram.build_diagram_model(catalog, sdp, False)
                logical = logical_svg(catalog, sdp["uid"])
                deployment = deployment_svg(catalog, sdp["uid"])
                logical_uids = {n.uid for n in model.nodes}
                deployment_uids = {n.uid for n in model.deployment_nodes}
                deployment_uids |= {c.uid for c in model.containers if c.uid and c.drawn}
                shared = logical_uids & deployment_uids
                shared_seen += len(shared)
                logical_ids, deployment_ids = data_ids(logical), data_ids(deployment)
                self.assertTrue(shared <= logical_ids, sorted(shared - logical_ids))
                self.assertTrue(shared <= deployment_ids, sorted(shared - deployment_ids))
        self.assertGreater(shared_seen, 0)

    def test_dependency_edges_drawn_like_relationships(self) -> None:
        catalog = load_catalog(FIXTURE)
        sdp = next(p for p in generate_diagram.sdps(catalog) if p["uid"] == "FXSDP00001-0001")
        model = generate_diagram.build_diagram_model(catalog, sdp, False)
        derived = [e for e in model.edges if e.derived]
        self.assertTrue(derived)
        svg = logical_svg(catalog, sdp["uid"])
        for edge in derived:
            self.assertIn(f'data-from="{xml_escape(edge.source)}" data-to="{xml_escape(edge.target)}"', svg)
        self.assertNotIn("runs on", svg)
        catalog_rels = [o for o in catalog.values() if generate_diagram.is_runs_on(o)]
        real = {
            (o.get("source"), o.get("target"))
            for o in catalog.values()
            if o.get("type") == "relationship" and not o.get("_derived")
        }
        checked = 0
        for rel in catalog_rels:
            pair = (rel["source"], rel["target"])
            if pair in real:
                continue
            checked += 1
            self.assertNotIn(f'data-from="{xml_escape(pair[0])}" data-to="{xml_escape(pair[1])}"', svg, pair)
        self.assertGreater(checked, 0)

    def test_page_section_order(self) -> None:
        for uid in [sdp["uid"] for sdp in generate_diagram.sdps(load_catalog(FIXTURE))]:
            page, model = generate_diagram.build(FIXTURE, uid)
            markers = [
                ("<header>", "header"),
                ('<div class="counts">', "counts"),
                ('id="logical"', "logical"),
                ('id="deployment"', "deployment"),
                ("<h2>Recorded relationships</h2>", "relationships"),
                ("<h2>Recorded characteristics</h2>", "characteristics"),
                ("<h2>Open questions on record</h2>", "questions"),
                ("<h2>Object inventory</h2>", "inventory"),
                ("<footer", "footer"),
            ]
            self.assertEqual(bool(model.conflicts), "<h2>Recorded conflicts</h2>" in page, uid)
            if model.conflicts:
                markers.insert(5, ("<h2>Recorded conflicts</h2>", "conflicts"))
            positions = [page.index(marker) for marker, _ in markers]
            self.assertEqual(positions, sorted(positions), f"sections out of D19 order for {uid}")

    def test_page_header_and_counts(self) -> None:
        sdp = pattern({"Web": ["A-1"]})
        sdp["lifecycleStatus"] = "candidate"
        sdp["followsReferenceArchitecture"] = "RA-1"
        objects = [component("A-1", "Alpha"), component("RA-1", "FX Reference Platform"), sdp]
        with tempfile.TemporaryDirectory() as tmp:
            page, _ = generate_diagram.build(write_workspace(Path(tmp), objects), None)
            self.assertIn("Demo Pattern Architecture", page)
            self.assertIn("Lifecycle: <b>candidate</b>", page)
            self.assertIn("Owner team: <b>team-a</b>", page)
            self.assertIn("Reference architecture: <b>FX Reference Platform</b>", page)
            sdp["followsReferenceArchitecture"] = "RA-MISSING"
            page, _ = generate_diagram.build(write_workspace(Path(tmp) / "unresolved", objects[:1] + [sdp]), None)
            self.assertNotIn("Reference architecture", page)
        catalog = load_catalog(FIXTURE)
        placed_only_page, model = generate_diagram.build(FIXTURE, FIXTURE_SDP, placed_only=True)
        self.assertGreater(model.undrawn_relationship_count, 0)
        self.assertIn(
            f"{model.undrawn_relationship_count} recorded relationships lead outside the placed set and are not drawn",
            placed_only_page,
        )
        full_page, _ = generate_diagram.build(FIXTURE, FIXTURE_SDP)
        self.assertNotIn("lead outside the placed set", full_page)
        self.assertIsNotNone(catalog)

    def test_footer_version_only_in_html(self) -> None:
        version = generate_diagram.framework_version()
        self.assertNotEqual(version, "version not recorded")
        catalog = load_catalog(FIXTURE)
        for uid in [sdp["uid"] for sdp in generate_diagram.sdps(catalog)]:
            page, _ = generate_diagram.build(FIXTURE, uid)
            footer = page.split('<footer class="foot">')[1].split("</footer>")[0]
            self.assertIn(version, footer)
            self.assertNotIn(version, logical_of(page))
            self.assertNotIn(version, figure_of(page, "fig-deployment"))
            self.assertNotIn(version, logical_svg(catalog, uid))
            self.assertNotIn(version, deployment_svg(catalog, uid))

    def test_footer_version_in_a_vendored_layout(self) -> None:
        # A vendored copy keeps tools/ beside draft-framework.yaml inside the framework directory (D15).
        with tempfile.TemporaryDirectory() as tmp:
            framework = Path(tmp) / "framework"
            tools = framework / "tools"
            tools.mkdir(parents=True)
            (framework / "draft-framework.yaml").write_text('version: "9.8.7"\n', encoding="utf-8")
            for name in ("generate_diagram.py", "generate_c4.py"):
                (tools / name).write_text((REPO_ROOT / "framework" / "tools" / name).read_text(encoding="utf-8"), encoding="utf-8")
            script = "import sys; sys.path.insert(0, sys.argv[1]); import generate_diagram as g; print(g.framework_version())"
            result = subprocess.run([sys.executable, "-I", "-c", script, str(tools)], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "9.8.7")

    def test_relationship_source_column(self) -> None:
        page, model = generate_diagram.build(FIXTURE, FIXTURE_SDP)
        sources = {row["source"] for row in model.relationship_rows}
        self.assertIn("inline dependency", sources)
        self.assertIn("relationship object", sources)
        self.assertIn("<th>Source</th>", page)
        self.assertNotIn("runs on", [row["label"] for row in model.relationship_rows])
        for row in model.relationship_rows:
            self.assertIn(f"<td>{row['source']}</td>", page)

    def test_conflicts_section(self) -> None:
        page, model = generate_diagram.build(FIXTURE, FIXTURE_SDP)
        self.assertTrue(model.conflicts)
        self.assertIn("<h2>Recorded conflicts</h2>", page)
        self.assertIn(f"<td>{model.name(model.conflicts[0].component)}</td>", page)
        sdp = pattern({"Web": ["A-1"]})
        sdp["serviceGroups"][0]["substrate"] = "RT-1"
        objects = [component("A-1", "Alpha", runsOn="RT-1"), component("RT-1", "Runtime", type="runtime_service"), sdp]
        with tempfile.TemporaryDirectory() as tmp:
            agreed, _ = generate_diagram.build(write_workspace(Path(tmp), objects), None)
        self.assertNotIn("Recorded conflicts", agreed)
        sdp["serviceGroups"][0]["substrate"] = "RT-2"
        objects = [component("A-1", "Alpha", runsOn="RT-1"), component("RT-1", "Runtime", type="runtime_service"), component("RT-2", "Other Runtime", type="runtime_service"), sdp]
        with tempfile.TemporaryDirectory() as tmp:
            disagreed, _ = generate_diagram.build(write_workspace(Path(tmp), objects), None)
        self.assertIn("<h2>Recorded conflicts</h2>", disagreed)

    def test_characteristics_and_inventory(self) -> None:
        sdp = pattern({"Web": ["A-1"]})
        sdp["scalingUnits"] = [{"name": "Web pool", "type": "instance", "instanceCount": 3}]
        sdp["tierVariants"] = [{"tier": "production", "deploymentTarget": "fx-east"}]
        objects = [component("A-1", "Alpha", language="Rust"), sdp]
        with tempfile.TemporaryDirectory() as tmp:
            page, _ = generate_diagram.build(write_workspace(Path(tmp), objects), None)
        characteristics = page.split("<h2>Recorded characteristics</h2>")[1].split("<h2>Open questions on record</h2>")[0]
        self.assertIn("Web pool", characteristics)
        self.assertIn("production", characteristics)
        self.assertNotIn("Web pool", logical_of(page))
        self.assertNotIn("Web pool", figure_of(page, "fig-deployment"))
        self.assertIn("<h2>Open questions on record</h2>", page)
        catalog = load_catalog(FIXTURE)
        page, model = generate_diagram.build(FIXTURE, FIXTURE_SDP)
        rows = generate_diagram.inventory_rows(model)
        self.assertIn("<th>Language / runtime</th>", page)
        checked = 0
        for uid in model.scope:
            if uid not in catalog:
                continue
            tech = generate_diagram.technology_line(catalog, catalog[uid])
            if tech:
                checked += 1
                self.assertIn(f"<td>{xml_escape(tech)}</td>", rows)
        self.assertGreater(checked, 0)

    def test_warnings_stderr_single_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "page.html"
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = generate_diagram.main(["--workspace", str(FIXTURE), "--sdp", FIXTURE_SDP, "--output", str(out)])
            _, model = generate_diagram.build(FIXTURE, FIXTURE_SDP)
        self.assertEqual(code, 0)
        lines = err.getvalue().splitlines()
        self.assertTrue(model.warnings)
        self.assertEqual(lines[0], f"{len(model.warnings)} warnings")
        self.assertEqual(lines[1:], sorted(set(model.warnings)))
        with tempfile.TemporaryDirectory() as tmp:
            placed = pattern({"Group": ["A-1"]})
            placed["serviceGroups"][0]["deployableObjects"][0]["diagramTier"] = "application"
            workspace = write_workspace(Path(tmp), [component("A-1", "Alpha"), placed])
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                generate_diagram.main(["--workspace", str(workspace), "--output", str(Path(tmp) / "p.html")])
        self.assertEqual(err.getvalue(), "0 warnings\n")

    def test_pin_script_cross_figure(self) -> None:
        page, _ = generate_diagram.build(FIXTURE, FIXTURE_SDP)
        self.assertEqual(page.count("<script>"), 1)
        self.assertIn('<svg id="fig-logical"', page)
        self.assertIn('<svg id="fig-deployment"', page)
        script = page.split("<script>")[1].split("</script>")[0]
        self.assertIn("'fig-logical'", script)
        self.assertIn("'fig-deployment'", script)
        css = page.split("<style>")[1].split("</style>")[0]
        for token in ("--hi-edge:#7c3a6b", "--hi-node:#006064", "svg .edge.on .ln{stroke:var(--hi-edge)", "svg .node.on .box{stroke:var(--hi-node)", "svg .group.on>.grp{stroke:var(--hi-node)"):
            self.assertIn(token, css)
        self.assertNotIn("opacity:.15", css, "highlighting colours the selection; it does not fade the rest")
        self.assertIn("appendChild(el)", script, "highlighted edges are raised above the others")
        # D34: connections hidden until a box is selected; direction colours; show-all toggle; legend
        self.assertIn("svg.quiet .edge:not(.on){display:none}", css)
        self.assertEqual(css.count("--hi-out:"), 3, "light, auto-dark and forced-dark values")
        self.assertEqual(css.count("--hi-in:"), 3)
        for token in ("svg .edge.on.out .ln{stroke:var(--hi-out)}", "svg .edge.on.in .ln{stroke:var(--hi-in)}", ".key .o i{border-color:var(--hi-out)}"):
            self.assertIn(token, css)
        self.assertIn("svg.classList.add('quiet')", script, "quiet mode is added by script so a page without script shows every line")
        self.assertIn("el.classList.toggle('out',on&&a===id)", script)
        self.assertIn("el.classList.toggle('in',on&&a!==id&&to===id)", script)
        self.assertEqual(page.count('data-all="fig-logical"'), 1)
        self.assertEqual(page.count('data-all="fig-deployment"'), 1)
        self.assertEqual(page.count("Show all connections"), 2)
        self.assertEqual(page.count('<span class="key">'), 2)
        self.assertEqual(page.count('<span class="o"><i></i>calls it makes</span>'), 2, "legend names the outbound colour under each figure")
        self.assertEqual(page.count('<span class="i"><i></i>calls it receives</span>'), 2, "legend names the inbound colour under each figure")
        for fid in ("fig-logical", "fig-deployment"):  # toggle and legend sit directly under the heading
            self.assertRegex(page, r'</h2><label class="tog"><input type="checkbox" data-all="' + fid + '">')

    def test_flow_overlay_per_edge(self) -> None:
        # D34: every drawn edge carries an animated overlay hidden until the edge is highlighted; its direction follows flow.
        objects = [component("A-1", "Alpha"), component("B-1", "Beta"), component("C-1", "Gamma"), component("D-1", "Delta"),
                   pattern({"G": ["A-1", "B-1", "C-1", "D-1"]}),
                   relationship("R-1", "A-1", "B-1", "calls"),
                   dict(relationship("R-2", "A-1", "C-1", "calls"), flow="inbound"),
                   dict(relationship("R-3", "A-1", "D-1", "calls"), flow="bidirectional")]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        for svg in (logical_svg(cat, "SDP-1"), deployment_svg(cat, "SDP-1")):
            groups = re.findall(r'<g class="edge" data-from="([^"]+)" data-to="([^"]+)">(.*?)</g>', svg, re.S)
            self.assertEqual(len(groups), 3)
            by_target = {t: body for _s, t, body in groups}
            self.assertEqual(by_target["B-1"].count('<path class="fl" d='), 1)
            self.assertEqual(by_target["B-1"].count('class="fl rev"'), 0)
            self.assertEqual(by_target["C-1"].count('<path class="fl rev" d='), 1)
            self.assertEqual(by_target["C-1"].count('<path class="fl" d='), 0)
            self.assertEqual(by_target["D-1"].count('<path class="fl" d='), 1)
            self.assertEqual(by_target["D-1"].count('<path class="fl rev" d='), 1)
            for _s, _t, body in groups:  # the overlay traces the line exactly
                ln = re.search(r'<path class="ln[^"]*" d="([^"]+)"', body).group(1)
                for fl in re.findall(r'<path class="fl(?: rev)?" d="([^"]+)"', body):
                    self.assertEqual(fl, ln)
            style = svg.split("<style>")[1].split("</style>")[0]
            self.assertIn(".fl{display:none;", style)
            self.assertIn("@keyframes flow{to{stroke-dashoffset:-10}}", style)
            self.assertIn("@media (prefers-reduced-motion:reduce){.fl{animation:none}}", style)
            self.assertIn(".fl.rev{animation-direction:reverse}", style)

    def test_property_render_twice(self) -> None:
        for uid in [sdp["uid"] for sdp in generate_diagram.sdps(load_catalog(FIXTURE))]:
            harness.assert_render_twice(self, lambda: generate_diagram.build(FIXTURE, uid)[0].encode("utf-8"))

    def test_property_reversed_discovery(self) -> None:
        for uid in [sdp["uid"] for sdp in generate_diagram.sdps(load_catalog(FIXTURE))]:
            harness.assert_reversed_discovery(self, lambda: generate_diagram.build(FIXTURE, uid)[0].encode("utf-8"))

    def test_property_shuffled_catalog(self) -> None:
        catalog = load_catalog(FIXTURE)
        for uid in [sdp["uid"] for sdp in generate_diagram.sdps(catalog)]:
            harness.assert_shuffled_catalog(
                self, lambda c: generate_diagram.build_from_catalog(c, uid)[0].encode("utf-8"), catalog
            )

    def test_cli_argument_matrix(self) -> None:
        cases = [
            ["--workspace", str(EXAMPLES), "--all"],
            ["--workspace", str(EXAMPLES), "--all", "--output-dir", "unused", "--sdp", "FX"],
            ["--workspace", str(EXAMPLES), "--all", "--output-dir", "unused", "--output", "unused.html"],
            ["--workspace", str(EXAMPLES), "--list", "--sdp", "FX"],
            ["--workspace", str(EXAMPLES), "--list", "--all"],
            ["--workspace", str(EXAMPLES), "--list", "--output", "unused.html"],
            ["--workspace", str(EXAMPLES), "--list", "--output-dir", "unused"],
            ["--workspace", str(EXAMPLES), "--list", "--svg-dir", "unused"],
            ["--workspace", str(EXAMPLES), "--output-dir", "unused"],
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                code, _, err = run_cli(argv)
                self.assertEqual(code, 2)
                self.assertIn("error:", err)

    def test_all_no_catalog_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            code, _, err = run_cli(["--workspace", str(Path(tmp) / "nope"), "--all", "--output-dir", str(out_dir)])
            self.assertEqual(code, 2)
            self.assertIn("catalog/", err)
            self.assertFalse(out_dir.exists(), "nothing may be rendered or created before the catalog check")

    def test_all_no_sdp_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(Path(tmp) / "ws", [component("A-1", "Alpha")])
            code, out, err = run_cli(["--workspace", str(workspace), "--all", "--output-dir", str(Path(tmp) / "out")])
        self.assertEqual(code, 1)
        self.assertIn("no software_deployment_pattern objects found", err)
        self.assertEqual(out, "")

    def test_all_continues_after_malformed_pattern(self) -> None:
        good = named_pattern("SDP-G", "Good Pattern", ["A-1"])
        bad = named_pattern("SDP-B", "Bad Pattern", [])
        bad["serviceGroups"] = "not a list"
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(Path(tmp) / "ws", [component("A-1", "Alpha"), good, bad])
            out_dir = Path(tmp) / "out"
            code, out, err = run_cli(["--workspace", str(workspace), "--all", "--output-dir", str(out_dir)])
            self.assertEqual(code, 1)
            self.assertTrue((out_dir / "good-pattern.html").is_file())
            self.assertFalse((out_dir / "bad-pattern.html").exists())
        self.assertIn("error: Bad Pattern (SDP-B): serviceGroups must be a list", err)
        self.assertEqual(out.count("\n"), 1)
        self.assertTrue(out.startswith("SDP-G\tGood Pattern\t"))

    def test_single_mode_malformed_exit_1(self) -> None:
        bad = named_pattern("SDP-B", "Bad Pattern", [])
        bad["serviceGroups"] = "not a list"
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(Path(tmp) / "ws", [bad])
            code, _, err = run_cli(["--workspace", str(workspace), "--output", str(Path(tmp) / "p.html")])
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("error:"), err)

    def test_slug_collision_suffix(self) -> None:
        objects = [
            component("A-1", "Alpha"),
            named_pattern("SDP-A", "Demo Pattern", ["A-1"]),
            named_pattern("SDP-B", "Demo Pattern", ["A-1"]),
            named_pattern("SDP-C", "Other Pattern", ["A-1"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(Path(tmp) / "ws", objects)
            out_dir, svg_dir = Path(tmp) / "html", Path(tmp) / "svg"
            code, _, err = run_cli(["--workspace", str(workspace), "--all", "--output-dir", str(out_dir), "--svg-dir", str(svg_dir)])
            self.assertEqual(code, 0)
            for stem in ("demo-pattern-sdp-a", "demo-pattern-sdp-b"):
                self.assertTrue((out_dir / f"{stem}.html").is_file())
                self.assertTrue((svg_dir / f"{stem}-logical.svg").is_file())
                self.assertTrue((svg_dir / f"{stem}-deployment.svg").is_file())
            self.assertTrue((out_dir / "other-pattern.html").is_file())
            self.assertFalse((out_dir / "demo-pattern.html").exists())
        self.assertEqual(err.count("slug collision: demo-pattern used by 2 patterns; uid suffix added"), 1)

    def test_svg_dir_matches_goldens(self) -> None:
        for sdp in generate_diagram.sdps(load_catalog(FIXTURE)):
            with self.subTest(sdp=sdp["uid"]), tempfile.TemporaryDirectory() as tmp:
                svg_dir = Path(tmp) / "svg"
                code, _, _ = run_cli(
                    ["--workspace", str(FIXTURE), "--sdp", sdp["uid"], "--output", str(Path(tmp) / "p.html"), "--svg-dir", str(svg_dir)]
                )
                self.assertEqual(code, 0)
                for view in ("logical", "deployment"):
                    produced = (svg_dir / f"{generate_diagram.slug(sdp['name'])}-{view}.svg").read_bytes()
                    harness.check_golden(self, harness.golden_path(generate_diagram.slug(sdp["name"]), view), lambda: produced)

    def test_subprocess_hashseed_identical(self) -> None:
        for sdp in generate_diagram.sdps(load_catalog(FIXTURE)):
            outputs = {}
            for seed in ("0", "4242"):
                with self.subTest(sdp=sdp["uid"], seed=seed), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "framework.tools.generate_diagram",
                            "--workspace",
                            str(FIXTURE),
                            "--sdp",
                            sdp["uid"],
                            "--output",
                            str(root / "page.html"),
                            "--svg-dir",
                            str(root / "svg"),
                        ],
                        cwd=str(REPO_ROOT),
                        env=dict(os.environ, PYTHONHASHSEED=seed),
                        check=True,
                        capture_output=True,
                    )
                    outputs[seed] = {
                        str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()
                    }
            self.assertEqual(sorted(outputs["0"]), sorted(outputs["4242"]))
            self.assertIn("page.html", outputs["0"])
            self.assertEqual(outputs["0"], outputs["4242"], f"hash seed changed the bytes of {sdp['uid']}")

    def test_all_on_examples_and_fixture_exit_0(self) -> None:
        for workspace in (EXAMPLES, FIXTURE):
            with self.subTest(workspace=workspace.name), tempfile.TemporaryDirectory() as tmp:
                html_dir, svg_dir = Path(tmp) / "html", Path(tmp) / "svg"
                code, out, err = run_cli(["--workspace", str(workspace), "--all", "--output-dir", str(html_dir), "--svg-dir", str(svg_dir)])
                count = len(generate_diagram.sdps(load_catalog(workspace)))
                self.assertEqual(code, 0, err)
                self.assertEqual(len(list(html_dir.glob("*.html"))), count)
                self.assertEqual(len(list(svg_dir.glob("*.svg"))), 2 * count)
                self.assertEqual(len([line for line in out.splitlines() if line.count("\t") == 3]), count)


class DiagramSkillTests(unittest.TestCase):
    """The draftsman-diagram skill sends both views to the generator (plan D23, AC11, AC12)."""

    SKILL = REPO_ROOT / "framework" / "skills" / "draftsman-diagram" / "SKILL.md"
    MERMAID = REPO_ROOT / "framework" / "skills" / "draftsman-diagram" / "references" / "mermaid.md"

    def test_skill_is_at_most_200_lines(self) -> None:
        self.assertLessEqual(len(self.SKILL.read_text(encoding="utf-8").splitlines()), 200)

    def test_skill_names_generator_as_only_path_and_forbids_hand_svg(self) -> None:
        text = self.SKILL.read_text(encoding="utf-8")
        self.assertIn("framework/tools/generate_diagram.py", text)
        self.assertIn("The generator is the only path for the two views", text)
        self.assertRegex(text, r"[Hh]and-drawn SVG is forbidden")

    def test_skill_explains_derived_tiers_outside_lane_conflicts_and_warnings(self) -> None:
        text = self.SKILL.read_text(encoding="utf-8")
        for phrase in ("dashed border", "External interactions lane", "Recorded conflicts section", "Warnings to read back"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_mermaid_reference_is_outside_determinism_guarantee(self) -> None:
        text = self.MERMAID.read_text(encoding="utf-8")
        self.assertIn("outside the determinism guarantee", text)
        self.assertIn("rendered page", text)


LAYOUT_UID = "FXDGM00001-0001"
LAYOUT_FILE = "diagram-layout-fx-storefront-pattern.yaml"
EXT_ID = "ext:f2e513630165"


def fixture_catalog_without_layout() -> dict:
    catalog = load_catalog(FIXTURE)
    del catalog[LAYOUT_UID]
    return catalog


def copy_fixture(root: Path, keep_layout: bool = True) -> Path:
    workspace = root / "ws"
    shutil.copytree(FIXTURE / "catalog", workspace / "catalog")
    if not keep_layout:
        (workspace / "catalog" / LAYOUT_FILE).unlink()
    return workspace


def run_tool(script: str, argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO_ROOT / "framework" / "tools" / script)] + argv, cwd=str(REPO_ROOT), capture_output=True, text=True)


class DiagramLayoutTests(unittest.TestCase):
    """S14: diagram_layout object (D38), position ordering (D39), --write-layout (D40)."""

    def test_logical_view_honours_positions(self) -> None:  # AC23
        catalog = load_catalog(FIXTURE)
        rects = node_rects(logical_svg(catalog, FIXTURE_SDP))
        base = node_rects(logical_svg(fixture_catalog_without_layout(), FIXTURE_SDP))
        self.assertNotIn("FXNET00001-0001", rects)  # D43: the placed gateway is deployment-only
        self.assertLess(rects["FXPRD00004-0001"][0], rects["FXPRD00002-0001"][0])
        self.assertLess(rects["FXPRD00002-0001"][0], rects["FXPRD00003-0001"][0])  # unpositioned follows positioned
        self.assertLess(rects[EXT_ID][1], rects["FXPRD00010-0001"][1])
        self.assertLess(rects["FXPRD00010-0001"][1], rects["FXPRD00005-0001"][1])
        self.assertLess(base["FXPRD00002-0001"][0], base["FXPRD00004-0001"][0])  # without the layout the order differs

    def test_deployment_view_honours_positions(self) -> None:  # AC23
        catalog = load_catalog(FIXTURE)
        rects = node_rects(deployment_svg(catalog, FIXTURE_SDP))
        base = node_rects(deployment_svg(fixture_catalog_without_layout(), FIXTURE_SDP))
        self.assertLess(rects["FXPRD00003-0001"][0], rects["FXPRD00002-0001"][0])
        self.assertEqual(rects["FXPRD00003-0001"][1], rects["FXPRD00002-0001"][1])
        self.assertGreater(rects["FXDCP00001-0001"][1], rects["FXDST00001-0001"][1])  # D45: a data container follows the boxes
        self.assertLess(rects["FXPRD00010-0001"][1], rects[EXT_ID][1])
        self.assertLess(rects[EXT_ID][1], rects["FXPRD00005-0001"][1])
        self.assertLess(base["FXPRD00002-0001"][0], base["FXPRD00003-0001"][0])

    def test_positioned_nodes_sort_by_position_then_uid(self) -> None:
        self.assertEqual(generate_diagram.apply_positions(["c", "a", "b", "d"], {"d": 1, "b": 1}), ["b", "d", "c", "a"])

    def test_validate_accepts_fixture_layout_and_rejects_non_sdp_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = copy_fixture(Path(tmp))
            good = run_tool("validate.py", ["--workspace", str(workspace)])
            self.assertIn(f"PASS {workspace.resolve() / 'catalog' / LAYOUT_FILE}", good.stdout)
            layout_path = workspace / "catalog" / LAYOUT_FILE
            doc = yaml.safe_load(layout_path.read_text(encoding="utf-8"))
            doc["pattern"] = "FXPRD00001-0001"
            layout_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            bad = run_tool("validate.py", ["--workspace", str(workspace)])
            self.assertNotEqual(bad.returncode, 0)
            lines = [line for line in bad.stdout.splitlines() if LAYOUT_FILE in line and "'pattern'" in line]
            self.assertTrue(lines, bad.stdout)
            self.assertIn("software_deployment_pattern", lines[0])

    def test_validate_warns_on_stale_ref_but_not_ext_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = copy_fixture(Path(tmp))
            layout_path = workspace / "catalog" / LAYOUT_FILE
            doc = yaml.safe_load(layout_path.read_text(encoding="utf-8"))
            doc["logical"].append({"ref": "FXGONE00001-0001", "position": 9})
            layout_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            out = run_tool("validate.py", ["--workspace", str(workspace)]).stdout
            stale = [line for line in out.splitlines() if LAYOUT_FILE in line and "no catalog object" in line]
            self.assertEqual(len(stale), 1, out)
            self.assertIn("FXGONE00001-0001", stale[0])
            self.assertNotIn(EXT_ID, stale[0])

    def test_validate_rejects_non_positive_position(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = copy_fixture(Path(tmp))
            layout_path = workspace / "catalog" / LAYOUT_FILE
            doc = yaml.safe_load(layout_path.read_text(encoding="utf-8"))
            doc["logical"][0]["position"] = 0
            layout_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            out = run_tool("validate.py", ["--workspace", str(workspace)]).stdout
            self.assertTrue([line for line in out.splitlines() if LAYOUT_FILE in line and "position" in line], out)

    def test_duplicate_layouts_use_lowest_uid_and_warn(self) -> None:
        catalog = load_catalog(FIXTURE)
        lower = {
            "schemaVersion": "1.0", "uid": "FXDGM00000-0001", "type": "diagram_layout", "name": "Lower", "pattern": FIXTURE_SDP,
            "catalogStatus": "complete", "logical": [{"ref": "FXPRD00002-0001", "position": 1}],
        }
        catalog[lower["uid"]] = lower
        model = generate_diagram.Model(catalog, catalog[FIXTURE_SDP], False)
        self.assertIn(f"multiple diagram layouts for {FIXTURE_SDP}; using FXDGM00000-0001", model.warnings)
        rects = node_rects(generate_diagram.render_logical_svg(generate_diagram.diagram_of(model)))
        self.assertLess(rects["FXPRD00002-0001"][0], rects["FXPRD00004-0001"][0])  # the lower layout, not the fixture one, ordered it

    def test_undrawn_ref_warns_once_and_render_succeeds(self) -> None:
        catalog = load_catalog(FIXTURE)
        for view in ("logical", "deployment"):
            catalog[LAYOUT_UID][view].append({"ref": "FXGONE00001-0001", "position": 7})
        model = generate_diagram.Model(catalog, catalog[FIXTURE_SDP], False)
        self.assertEqual(model.warnings.count("layout position for undrawn object FXGONE00001-0001"), 1)
        dm = generate_diagram.diagram_of(model)
        self.assertIn("<svg", generate_diagram.render_logical_svg(dm))
        self.assertIn("<svg", generate_diagram.render_deployment_svg(dm))
        self.assertEqual(generate_diagram.render_page(model, dm).count("layout position for undrawn object"), 0)

    def test_layout_never_changes_band_or_lane(self) -> None:
        catalog = load_catalog(FIXTURE)
        catalog[LAYOUT_UID]["logical"].append({"ref": "FXDCP00001-0001", "position": 1})  # a data box asking to be first
        model = generate_diagram.build_diagram_model(catalog, catalog[FIXTURE_SDP], False)
        layout = generate_diagram.layout_logical(model)
        bands = dict(zip(layout.band_names, layout.order))
        self.assertIn("FXDCP00001-0001", bands["data"])
        self.assertNotIn("FXDCP00001-0001", bands["presentation"])

    def test_write_layout_requires_sdp(self) -> None:
        code, _out, err = run_cli(["--workspace", str(FIXTURE), "--write-layout"])
        self.assertEqual(code, 2)
        self.assertIn("--write-layout requires --sdp", err)

    def test_write_layout_creates_file_and_second_run_is_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = copy_fixture(Path(tmp), keep_layout=False)
            before = sorted(str(p.relative_to(workspace)) for p in workspace.rglob("*") if p.is_file())
            page = Path(tmp) / "page.html"
            argv = ["--workspace", str(workspace), "--sdp", FIXTURE_SDP, "--output", str(page), "--write-layout"]
            first = run_tool("generate_diagram.py", argv)
            self.assertEqual(first.returncode, 0, first.stderr)
            target = workspace / "catalog" / LAYOUT_FILE
            self.assertTrue(target.is_file())
            after = sorted(str(p.relative_to(workspace)) for p in workspace.rglob("*") if p.is_file())
            self.assertEqual(after, sorted(before + [f"catalog/{LAYOUT_FILE}"]))  # only the layout file is new
            doc = yaml.safe_load(target.read_text(encoding="utf-8"))
            self.assertEqual(doc["type"], "diagram_layout")
            self.assertEqual(doc["pattern"], FIXTURE_SDP)
            self.assertEqual(doc["name"], "FX Storefront Pattern diagram layout")
            self.assertEqual(doc["catalogStatus"], "complete")
            self.assertRegex(doc["uid"], r"^[0-9A-HJKMNP-TV-Z]{10}-[0-9A-HJKMNP-TV-Z]{4}$")
            plain_catalog = fixture_catalog_without_layout()
            dm = generate_diagram.build_diagram_model(plain_catalog, plain_catalog[FIXTURE_SDP], False)
            self.assertEqual(sorted(e["ref"] for e in doc["logical"]), sorted(n.uid for n in dm.nodes))
            self.assertEqual(len(doc["deployment"]), len(dm.deployment_nodes))
            self.assertTrue(all(isinstance(e["position"], int) and e["position"] >= 1 for e in doc["logical"] + doc["deployment"]))
            self.assertEqual(min(e["position"] for e in doc["logical"]), 1)
            file_1, page_1 = target.read_bytes(), page.read_bytes()
            second = run_tool("generate_diagram.py", argv)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(target.read_bytes(), file_1)
            self.assertEqual(page.read_bytes(), page_1)
            plain_page = Path(tmp) / "plain.html"
            run_tool("generate_diagram.py", ["--workspace", str(workspace), "--sdp", FIXTURE_SDP, "--output", str(plain_page)])
            self.assertEqual(plain_page.read_bytes(), page_1)  # with and without the flag the page is the same
            checked = run_tool("validate.py", ["--workspace", str(workspace)])
            self.assertIn(f"PASS {target.resolve()}", checked.stdout)

    def test_write_layout_updates_in_place_keeping_uid_and_positions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = copy_fixture(Path(tmp))  # the fixture layout is already there
            target = workspace / "catalog" / LAYOUT_FILE
            doc = yaml.safe_load(target.read_text(encoding="utf-8"))
            doc["logical"] = [e for e in doc["logical"] if e["ref"] != "FXPRD00002-0001"]  # a node now missing from the layout
            doc["logical"].append({"ref": "FXGONE00001-0001", "position": 5})  # a node no longer drawn
            target.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            argv = ["--workspace", str(workspace), "--sdp", FIXTURE_SDP, "--output", str(Path(tmp) / "p.html"), "--write-layout"]
            self.assertEqual(run_tool("generate_diagram.py", argv).returncode, 0)
            updated = yaml.safe_load(target.read_text(encoding="utf-8"))
            self.assertEqual(updated["uid"], LAYOUT_UID)
            logical = {e["ref"]: e["position"] for e in updated["logical"]}
            self.assertNotIn("FXGONE00001-0001", logical)
            self.assertEqual(logical["FXPRD00004-0001"], 1)  # kept
            self.assertEqual(logical["FXPRD00001-0001"], 1)
            # FXPRD00002 and FXPRD00003 have no position in their band; each follows the highest one there
            self.assertEqual(sorted(logical[u] for u in ("FXPRD00002-0001", "FXPRD00003-0001")), [2, 3])
            self.assertEqual(len(updated["logical"]), 8)
            self.assertEqual(len(list((workspace / "catalog").glob("diagram-layout-*.yaml"))), 1)

    def test_write_layout_with_placed_only_is_a_usage_error(self) -> None:
        code, _out, err = run_cli(["--workspace", str(FIXTURE), "--sdp", FIXTURE_SDP, "--placed-only", "--write-layout"])
        self.assertEqual(code, 2)
        self.assertIn("--placed-only", err)

    def test_write_layout_refuses_to_overwrite_a_foreign_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = copy_fixture(Path(tmp), keep_layout=False)
            foreign = workspace / "catalog" / LAYOUT_FILE
            foreign.write_text("# someone else's file\nnote: keep me\n", encoding="utf-8")
            before = foreign.read_bytes()
            result = run_tool("generate_diagram.py", ["--workspace", str(workspace), "--sdp", FIXTURE_SDP, "--output", str(Path(tmp) / "p.html"), "--write-layout"])
            self.assertEqual(result.returncode, 1)
            self.assertIn("already exists", result.stderr)
            self.assertEqual(foreign.read_bytes(), before)
