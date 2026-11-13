from __future__ import annotations

import contextlib
import hashlib
import inspect
import io
import re
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
LARGE_MAX_CROSSINGS = 869


def edge_polylines(svg: str) -> list:
    """(from uid, to uid, [(x, y), ...]) for every routed edge; self-loop curves are skipped."""
    found = []
    for match in re.finditer(r'<g class="edge" data-from="([^"]*)" data-to="([^"]*)"><title>[^<]*</title><path class="ln" d="(M[-\d. L]+)"/>', svg):
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


def edge_polylines_straight(svg: str) -> list:
    """(from, to, [(x, y), (x, y)]) for each straight edge of a deployment SVG."""
    found = []
    for match in re.finditer(r'<g class="edge" data-from="([^"]*)" data-to="([^"]*)"><title>[^<]*</title><path class="ln" d="M([-\d.]+) ([-\d.]+) L([-\d.]+) ([-\d.]+)"/>', svg):
        a, b, x1, y1, x2, y2 = match.groups()
        found.append((a, b, [(float(x1), float(y1)), (float(x2), float(y2))]))
    return found


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
        # Edges are counted per figure: the page figure (until S8 assembles the two views) and the logical SVG.
        self.assertEqual(svg_of(page).count('class="edge"'), len(model.relationships))
        catalog = load_catalog(EXAMPLES)
        logical = logical_svg(catalog, model.sdp["uid"])
        xml.dom.minidom.parseString(logical)
        self.assertEqual(logical.count('<g class="edge"'), len(generate_diagram.build_diagram_model(catalog, model.sdp, False).edges))
        self.assertGreater(logical.count('<g class="edge"'), 0)
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
        self.assertEqual(page.count('class="node"'), 2)
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
        self.assertEqual(page.count('class="edge"'), 1)
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
                    relationship("R-1", "U-1", "A-1", "calls"),
                ],
            )
            page, model = generate_diagram.build(workspace, None)
        svg = svg_of(page)
        self.assertIn("Linked Unplaced", svg)
        self.assertNotIn("Lonely Unplaced", svg)
        self.assertIn("Not placed in a service group", svg)
        # One-hop scope (D2): an object with no relationship to a placed object is out of scope.
        self.assertNotIn("Lonely Unplaced", page)
        self.assertIn("Linked Unplaced", page)
        self.assertEqual(model.unplaced_drawn, ["U-1"])

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
        self.assertEqual(page.count('class="edge"'), 1)
        self.assertIn("M", re.search(r'<path class="ln" d="([^"]+)"', svg).group(1))
        self.assertIn("retries", svg)
        self.assertNotIn("nan", svg.lower())

    def test_uid_in_two_groups_warns_and_draws_once(self) -> None:
        page, model = self._build([component("A-1", "Alpha"), pattern({"G1": ["A-1"], "G2": ["A-1"]})])
        self.assertEqual(page.count('class="node"'), 1)
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
        self.assertEqual(page.count('class="node"'), 0)
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
        self.assertEqual(page.count('class="node"'), 1)
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
        self.assertNotIn("<svg", page.split("</header>")[1].split("Recorded relationships")[0])

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
        model = fixture_model()
        nodes = model.nodes_for_view("logical")
        ids = {node.uid for node in nodes}
        placed = set(model.placement)
        self.assertTrue(placed <= ids)
        # One hop: unplaced direct endpoints of placed objects are nodes.
        self.assertIn("FXPRD00005-0001", ids)
        self.assertIn("FXPRD00010-0001", ids)
        # Two hops: reached only through the outside object FXPRD00010-0001, so not nodes.
        self.assertNotIn("FXDST00002-0001", ids)
        self.assertNotIn("FXHST00002-0001", ids)
        # Exact set: placed objects, allow-listed direct endpoints, and external nodes for placed sources.
        catalog = load_catalog(FIXTURE)
        expected = set(placed)
        for rel in catalog.values():
            if rel.get("type") != "relationship" or generate_diagram.is_runs_on(rel):
                continue
            source, target = rel.get("source") or "", rel.get("target") or ""
            if source in placed and target:
                if catalog.get(target, {}).get("type") in ALLOWED_ONE_HOP:
                    expected.add(target)
            elif source in placed and rel.get("externalTarget"):
                expected.add("ext:" + hashlib.sha256(" ".join(str(rel["externalTarget"]).split()).encode("utf-8")).hexdigest()[:12])
            if target in placed and source and catalog.get(source, {}).get("type") in ALLOWED_ONE_HOP:
                expected.add(source)
        self.assertEqual(ids, expected)
        for node in nodes:
            if node.outside and not node.external:
                self.assertTrue(
                    any(
                        (e.source in placed and e.target == node.uid) or (e.target in placed and e.source == node.uid)
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
        # FXEDG00008 (external), FXEDG00009 and FXEDG00010 leave the placed set.
        self.assertEqual(expected, 3)
        self.assertEqual(fixture_model().undrawn_relationship_count, 0)

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
        self.assertIn("RTC-1", logical)
        self.assertNotIn("RTC-1", deployment)
        self.assertEqual(model.containers[0].uid, "RTC-1")
        # A substrate that is neither placed nor a one-hop endpoint is a container only.
        self.assertNotIn("RTC-2", logical)
        self.assertNotIn("RTC-2", deployment)
        self.assertEqual(model.containers[1].uid, "RTC-2")
        self.assertEqual(logical, {"RTC-1", "P-1", "P-2"})
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
        self.assertIn("RTC-1", {node.uid for node in model.nodes_for_view("logical")})

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
            plain("N-1", "network_service", "Gateway"),
            plain("P-1", "product_component", "Alpha"),
            plain("D-1", "data_store_service", "Store"),
            plain("H-1", "host", "Machine"),
            plain("P-2", "product_component", "Tiered"),
            plain("X-1", "product_component", "Elsewhere"),
            pattern({"G": ["N-1", "P-1", "D-1", "H-1", "P-2"]}),
            relationship("R-1", "P-1", "X-1", "calls"),
        ]
        next(o for o in objects if o["uid"] == "SDP-1")["serviceGroups"][0]["deployableObjects"][4]["diagramTier"] = "utility"
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
        self.assertIn('data-id="FXRTC00001-0001"', svg)
        self.assertRegex(svg, r'<g class="node[^"]*" data-id="FXRTC00001-0001">')

    def test_logical_order_independent_of_insertion_order(self) -> None:
        catalog = load_catalog(FIXTURE)
        for uid in ("FXSDP00001-0001", "FXSDP00003-0001"):
            reversed_catalog = dict(reversed(list(catalog.items())))
            self.assertEqual(logical_svg(catalog, uid), logical_svg(reversed_catalog, uid))

    def test_svg_desc_has_no_version(self) -> None:
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            svg = logical_svg(catalog, sdp["uid"])
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
            if container.members and container.target not in expected_targets:
                expected_targets.append(container.target)
        self.assertEqual(re.findall(r'<g class="target" data-target="([^"]*)"', svg), expected_targets)
        drawn = [c for c in model.containers if c.members]
        self.assertEqual(re.findall(r'<g class="group[^"]*"(?: data-id="[^"]*")? data-group="([^"]*)"', svg), [
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
                        self.assertTrue(box.getAttribute("class").startswith("node"))
        ids = re.findall(r'<g class="node[^"]*" data-id="([^"]*)"', svg)
        in_lanes = [uid for c in drawn for lane in c.lanes for uid in lane.members]
        self.assertEqual([i for i in ids if i in in_lanes], [u for t in expected_targets for c in drawn if c.target == t for lane in c.lanes for u in lane.members])

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
        self.assertRegex(logical_svg(catalog, FIXTURE_SDP), rf'<g class="node[^"]*" data-id="{uid}"')

    def test_container_captions_and_conflict(self) -> None:
        catalog = load_catalog(FIXTURE)
        model = generate_diagram.build_diagram_model(catalog, catalog[FIXTURE_SDP], False)
        svg = deployment_svg(catalog, FIXTURE_SDP)
        captions = re.findall(r'class="gc"[^>]*>([^<]*)<', svg)
        self.assertEqual(captions, [xml_unescape(c.caption) for c in model.containers if c.members])
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
        empty = [c for c in model.containers if not c.members]
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
            pattern({"G": ["P-1"], "H": ["P-2"]}),
            relationship("R-1", "RTC-1", "P-2", "serves"),
        ]
        objects[-2]["serviceGroups"][0]["substrate"] = "RTC-1"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertRegex(svg, r'<g class="group[^"]*" data-id="RTC-1"')
        (_, _, pts), = edge_polylines_straight(svg)
        group = re.search(r'<g class="group[^"]*" data-id="RTC-1"[^>]*>.*?<rect class="grp" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg, re.S)
        gx, gy, gw, gh = (int(group.group(i)) for i in range(1, 5))
        box = node_rects(svg)["P-2"]
        c_group = (gx + gw / 2, gy + gh / 2)
        c_box = (box[0] + box[2] / 2, box[1] + box[3] / 2)
        start = generate_diagram.border_point(c_group, c_box, gw, gh)
        end = generate_diagram.border_point(c_box, c_group, box[2], box[3])
        self.assertEqual(pts[0], (round(start[0], 1), round(start[1], 1)))
        self.assertEqual(pts[1], (round(end[0], 1), round(end[1], 1)))
        self.assertTrue(gx <= pts[0][0] <= gx + gw and gy <= pts[0][1] <= gy + gh)

    def test_outside_lane_in_deployment(self) -> None:
        catalog = load_catalog(FIXTURE)
        model = generate_diagram.build_diagram_model(catalog, catalog[FIXTURE_SDP], False)
        outer = [n for n in model.deployment_nodes if n.outside]
        self.assertTrue(outer)
        deployment = deployment_svg(catalog, FIXTURE_SDP)
        self.assertIn("Outside this pattern", deployment)
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

    @unittest.skip("enabled in S7")
    def test_edge_stroke_classes(self) -> None:
        self.fail("not implemented until S7")

    @unittest.skip("enabled in S7")
    def test_flow_arrowheads(self) -> None:
        self.fail("not implemented until S7")

    @unittest.skip("enabled in S7")
    def test_unknown_flow_warning(self) -> None:
        self.fail("not implemented until S7")

    @unittest.skip("enabled in S7")
    def test_label_visibility_threshold(self) -> None:
        self.fail("not implemented until S7")

    @unittest.skip("enabled in S7")
    def test_node_type_chip_and_tech_line(self) -> None:
        self.fail("not implemented until S7")

    @unittest.skip("enabled in S7")
    def test_lifecycle_and_theme_css(self) -> None:
        self.fail("not implemented until S7")

    @unittest.skip("enabled in S7")
    def test_svg_data_id_parity(self) -> None:
        self.fail("not implemented until S7")

    @unittest.skip("enabled in S8")
    def test_page_section_order(self) -> None:
        self.fail("not implemented until S8")

    @unittest.skip("enabled in S8")
    def test_page_header_and_counts(self) -> None:
        self.fail("not implemented until S8")

    @unittest.skip("enabled in S8")
    def test_footer_version_only_in_html(self) -> None:
        self.fail("not implemented until S8")

    @unittest.skip("enabled in S8")
    def test_relationship_source_column(self) -> None:
        self.fail("not implemented until S8")

    @unittest.skip("enabled in S8")
    def test_conflicts_section(self) -> None:
        self.fail("not implemented until S8")

    @unittest.skip("enabled in S8")
    def test_characteristics_and_inventory(self) -> None:
        self.fail("not implemented until S8")

    @unittest.skip("enabled in S8")
    def test_warnings_stderr_single_mode(self) -> None:
        self.fail("not implemented until S8")

    @unittest.skip("enabled in S8")
    def test_pin_script_cross_figure(self) -> None:
        self.fail("not implemented until S8")

    @unittest.skip("enabled in S9")
    def test_cli_argument_matrix(self) -> None:
        self.fail("not implemented until S9")

    @unittest.skip("enabled in S9")
    def test_all_no_catalog_exit_2(self) -> None:
        self.fail("not implemented until S9")

    @unittest.skip("enabled in S9")
    def test_all_no_sdp_exit_1(self) -> None:
        self.fail("not implemented until S9")

    @unittest.skip("enabled in S9")
    def test_all_continues_after_malformed_pattern(self) -> None:
        self.fail("not implemented until S9")

    @unittest.skip("enabled in S9")
    def test_single_mode_malformed_exit_1(self) -> None:
        self.fail("not implemented until S9")

    @unittest.skip("enabled in S9")
    def test_slug_collision_suffix(self) -> None:
        self.fail("not implemented until S9")

    @unittest.skip("enabled in S9")
    def test_svg_dir_matches_goldens(self) -> None:
        self.fail("not implemented until S9")

    @unittest.skip("enabled in S9")
    def test_subprocess_hashseed_identical(self) -> None:
        self.fail("not implemented until S9")

    @unittest.skip("enabled in S9")
    def test_all_on_examples_and_fixture_exit_0(self) -> None:
        self.fail("not implemented until S9")

    @unittest.skip("enabled in S10")
    def test_no_story_skip_markers(self) -> None:
        self.fail("not implemented until S10")
