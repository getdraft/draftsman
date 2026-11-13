from __future__ import annotations

import contextlib
import hashlib
import inspect
import io
import math
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
        self.assertEqual(logical_of(page).count('<g class="edge"'), len(model.edges))
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
                    relationship("R-1", "U-1", "A-1", "calls"),
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
            pattern({"G": ["P-1"], "H": ["P-2"]}),
            relationship("R-1", "RTC-1", "P-2", "serves"),
        ]
        objects[-2]["serviceGroups"][0]["substrate"] = "RTC-1"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertRegex(svg, r'<g class="group[^"]*" data-id="RTC-1"')
        self.assertIn("<title>Cluster serves Beta</title>", svg)  # the object's name, not the container caption
        (_, _, pts), = edge_polylines(svg)
        group = re.search(r'<g class="group[^"]*" data-id="RTC-1"[^>]*>.*?<rect class="grp" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg, re.S)
        gx, gy, gw, gh = (int(group.group(i)) for i in range(1, 5))
        box = node_rects(svg)["P-2"]
        c_group = (gx + gw / 2, gy + gh / 2)
        c_box = (box[0] + box[2] / 2, box[1] + box[3] / 2)
        start = generate_diagram.border_point(c_group, c_box, gw, gh)
        end = generate_diagram.border_point(c_box, c_group, box[2], box[3])
        self.assertEqual(pts[0], (round(start[0], 1), round(start[1], 1)))
        # The far end lies on the box border; the container end is the border_point checked above.
        self.assertIn(pts[-1][1], (box[1], box[1] + box[3]))
        self.assertTrue(box[0] <= pts[-1][0] <= box[0] + box[2])
        on_border = (
            abs(pts[0][0] - gx) < 0.1 or abs(pts[0][0] - (gx + gw)) < 0.1 or abs(pts[0][1] - gy) < 0.1 or abs(pts[0][1] - (gy + gh)) < 0.1
        )
        self.assertTrue(on_border, "container end lies on the container border")
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            self.assertTrue(ax == bx or ay == by, "orthogonal route")
        self.assertTrue(gx <= pts[0][0] <= gx + gw and gy <= pts[0][1] <= gy + gh)

    def test_deployment_edges_avoid_foreign_boxes(self) -> None:
        catalog = load_catalog(FIXTURE)
        for sdp in generate_diagram.sdps(catalog):
            svg = deployment_svg(catalog, sdp["uid"])
            self.assertGreater(len(edge_polylines(svg)), 0)
            self.assertEqual(edges_hitting_foreign_boxes(svg), [], sdp["uid"])
            segments = []
            for _s, _t, pts in edge_polylines(svg):
                segments.extend((min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1])) for a, b in zip(pts, pts[1:]))
            vertical = [(x0, y0, y1) for x0, x1, y0, y1 in segments if x0 == x1 and y0 < y1]
            for i, (x, y0, y1) in enumerate(vertical):
                for x2, a0, a1 in vertical[i + 1 :]:
                    self.assertFalse(x == x2 and y0 < a1 and a0 < y1, f"collinear overlap at x={x}")

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
            horizontals = []
            for number, (_s, _t, pts) in enumerate(edge_polylines(svg)):
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    if ay == by and ax != bx:
                        horizontals.append((ay, min(ax, bx), max(ax, bx), number))
            for i, (y, x0, x1, n1) in enumerate(horizontals):
                for y2, a0, a1, n2 in horizontals[i + 1 :]:
                    if abs(y - y2) < generate_diagram.DEPLOY_LEVEL and n1 != n2:
                        gap = max(a0 - x1, x0 - a1)
                        self.assertGreaterEqual(gap, generate_diagram.DEPLOY_LEVEL, f"runs of two edges {gap}px apart on y={y} and y={y2}")
            horizontals = [(y, x0, x1) for y, x0, x1, _n in horizontals]
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
        self.assertEqual(len(re.findall(r'd="M[\d.]+ [\d.]+ C', cases[-1])), 3)

    def test_loops_keep_the_logical_shape(self) -> None:
        objects = [component("A-1", "Alpha"), pattern({"G": ["A-1"]}), relationship("R-1", "A-1", "A-1", "one"), relationship("R-2", "A-1", "A-1", "two")]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        deploy = deployment_svg(cat, "SDP-1")
        logical = logical_svg(cat, "SDP-1")
        shape = lambda svg: [re.sub(r"-?\d+(?:\.\d+)?", "#", d) for d in re.findall(r'd="(M[^"]*C[^"]*)"', svg)]
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

    def test_two_left_border_ends_on_one_container_take_separate_verticals(self) -> None:
        # Edges between a container and boxes drawn inside it leave through its left border when the box sits
        # in the first column; each such end needs its own vertical outside the border.
        objects = [plain("RTC-1", "runtime_service", "Cluster")] + [component(f"P-{k}", f"Part {k}") for k in range(6)]
        objects.append(pattern({"G": [f"P-{k}" for k in range(6)]}))
        objects[-1]["serviceGroups"][0]["substrate"] = "RTC-1"
        objects += [relationship("R-1", "P-0", "RTC-1", "deploys to"), relationship("R-2", "RTC-1", "P-3", "hosts"), relationship("R-3", "P-3", "RTC-1", "reports to")]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertEqual(len(edge_polylines(svg)), 3)
        group = re.search(r'<rect class="grp" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg)
        gx, gy, gw, gh = (int(group.group(i)) for i in range(1, 5))
        tgt = re.search(r'<rect class="tgt" x="(\d+)"', svg)
        lefts = [pts for _s, _t, pts in edge_polylines(svg) if any(abs(px - gx) < 0.11 and gy < py < gy + gh for px, py in pts)]
        self.assertGreaterEqual(len(lefts), 2, "the fixture must exercise two left-border ends")
        for pts in lefts:
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                if ax == bx and ax < gx:
                    self.assertGreaterEqual(gx - ax, generate_diagram.DEPLOY_BORDER_CLEAR)
                    self.assertGreaterEqual(ax - int(tgt.group(1)), generate_diagram.DEPLOY_BORDER_CLEAR)
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

    def test_hub_with_too_many_ends_on_one_side_spills_to_the_other(self) -> None:
        # 60 inbound edges on one box from boxes above it: at most span / DEPLOY_MIN_STUB stubs fit on the top side,
        # so the rest leave through the bottom and stubs stay at least DEPLOY_MIN_STUB apart on both sides.
        names = [f"P-{k:02d}" for k in range(60)]
        objects = [component(u, u) for u in names] + [component("HUB-1", "Hub"), pattern({"G": names + ["HUB-1"]})]
        objects += [relationship(f"R-{k:02d}", u, "HUB-1", "calls") for k, u in enumerate(names)]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        hub = node_rects(svg)["HUB-1"]
        ends = [pts[-1] for _s, _t, pts in edge_polylines(svg)]
        self.assertEqual(len(ends), 60)
        tops = sorted(x for x, y in ends if y == hub[1])
        bottoms = sorted(x for x, y in ends if y == hub[1] + hub[3])
        self.assertTrue(tops and bottoms, "both sides in use")
        for side in (tops, bottoms):
            self.assertGreaterEqual(min(b - a for a, b in zip(side, side[1:])), generate_diagram.DEPLOY_MIN_STUB - 0.5)
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
        objects = [plain("RT-1", "runtime_service", "Runtime"), component("A-1", "Alpha"), component("O-1", "Outside"), pattern({"G": ["A-1"]})]
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
        self.assertIn('data-from="RT-1" data-to="RT-1"', logical_svg(cat, "SDP-1"))

    def test_container_border_over_capacity_spills_to_another_border(self) -> None:
        # A group listing only its own substrate is a 60 px container; twelve edges to two outside nodes do not fit
        # on its right border 8 px apart, so the surplus takes the top and bottom borders (review round 5, R1).
        objects = [plain("RT-1", "runtime_service", "Runtime"), component("O-1", "Outside One"), component("O-2", "Outside Two"), pattern({"Own": ["RT-1"]})]
        objects[3]["serviceGroups"][0]["substrate"] = "RT-1"
        objects += [relationship(f"R-{k:02d}", "RT-1", "O-1" if k % 2 else "O-2", f"rel {k}") for k in range(12)]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        polys = edge_polylines(svg)
        self.assertEqual(len(polys), 12)
        starts = [pts[0] for _s, _t, pts in polys]
        self.assertEqual(len(set(starts)), 12, "every container end has its own border point")
        self._assert_runs_clean(svg)
        self.assertEqual(edges_hitting_foreign_boxes(svg), [])

    def test_groups_naming_each_others_substrate_are_both_drawn(self) -> None:
        # G lists RT-2 and names RT-1 as substrate; H lists RT-1 and names RT-2. Neither object may vanish: both
        # groups are drawn, each as the container of its own substrate (review round 6, R1).
        objects = [plain("RT-1", "runtime_service", "Runtime One"), plain("RT-2", "runtime_service", "Runtime Two"), component("P-1", "Alpha"), pattern({"G": ["RT-2"], "H": ["RT-1"]})]
        objects[3]["serviceGroups"][0]["substrate"] = "RT-1"
        objects[3]["serviceGroups"][1]["substrate"] = "RT-2"
        objects += [relationship("R-1", "P-1", "RT-1", "uses"), relationship("R-2", "RT-1", "RT-2", "peers")]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        model = generate_diagram.build_diagram_model(cat, cat["SDP-1"], False)
        self.assertEqual([(c.group, c.drawn, c.members) for c in model.containers], [("G", True, []), ("H", True, [])])
        svg = deployment_svg(cat, "SDP-1")
        xml.dom.minidom.parseString(svg)
        self.assertRegex(svg, r'<g class="group" data-id="RT-1" data-group="G">')
        self.assertRegex(svg, r'<g class="group" data-id="RT-2" data-group="H">')
        self.assertEqual(len(edge_polylines(svg)), 2)
        self.assertNotIn("Service groups recorded with no objects", svg)
        self.assertEqual([w for w in model.warnings if w.startswith("substrate of a group")], [])
        self._assert_runs_clean(svg)

    def test_container_cluster_sliding_back_from_a_corner_stays_spread(self) -> None:
        # A container with a self-loop (which reserves the top of its right border), eight edges to an outside node
        # above and eleven to one below: the right-border cluster slides back from the bottom corner and must not
        # collapse onto the reserved top (review round 6, R2).
        objects = [plain("RT-1", "runtime_service", "Runtime"), component("O-1", "Above"), component("O-2", "Below"), component("P-1", "Alpha"), pattern({"Own": ["RT-1"], "Rest": ["P-1"]})]
        objects[4]["serviceGroups"][0]["substrate"] = "RT-1"
        objects += [relationship("R-00", "RT-1", "RT-1", "self")]
        objects += [relationship(f"R-{k:02d}", "RT-1", "O-1", f"up {k}") for k in range(1, 9)]
        objects += [relationship(f"R-{k:02d}", "RT-1", "O-2", f"down {k}") for k in range(9, 20)]
        objects += [relationship("R-90", "O-1", "P-1", "x")] + [relationship(f"R-{k}", "P-1", "O-2", "y") for k in range(91, 97)]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        polys = edge_polylines(svg)
        starts = [pts[0] for s_uid, _t, pts in polys if s_uid == "RT-1"]
        self.assertEqual(len(starts), 19)
        self.assertEqual(len(set(starts)), 19, "every container end has its own border point")
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
        objects += [relationship(f"R-0{k}", "O-1", u, "o") for k, u in enumerate(("A-1", "B-1", "C-1", "A-1", "B-1", "C-1"))]
        pairs = [("A-1", "B-1"), ("B-1", "C-1"), ("A-1", "C-1"), ("B-1", "A-1"), ("C-1", "B-1"), ("C-1", "A-1")]
        objects += [relationship(f"R-1{k}", a, b, "s") for k, (a, b) in enumerate(pairs)]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        self.assertEqual(len(edge_polylines(svg)), 12)
        self._assert_runs_clean(svg)
        self.assertEqual(edges_hitting_foreign_boxes(svg), [])

    def test_left_border_ends_level_in_vertical_order(self) -> None:
        # Four rows in one container; two first-column boxes above the centre both get left-border container ends.
        # The outer vertical must take the farther level so its run never crosses the inner vertical (round 2, R2).
        parts = [component(f"P-{k:02d}", f"Part {k}") for k in range(12)]
        objects = [plain("RTC-1", "runtime_service", "Cluster")] + parts + [pattern({"G": [p["uid"] for p in parts]})]
        objects[-1]["serviceGroups"][0]["substrate"] = "RTC-1"
        objects += [relationship("R-1", "P-03", "RTC-1", "a"), relationship("R-2", "P-00", "RTC-1", "b")]
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        gx = int(re.search(r'<rect class="grp" x="(\d+)"', svg).group(1))
        lefts = [pts for _s, _t, pts in edge_polylines(svg) if any(ax == bx and ax < gx for (ax, _ay), (bx, _by) in zip(pts, pts[1:]))]
        self.assertEqual(len(lefts), 2, "two left-border ends expected")
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
                heads.append((x, x + w, y, min(l[1] for l in inner) if inner else y + h))
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
        """No two vertical runs collinear with overlapping y; horizontal runs within DEPLOY_LEVEL in y are DEPLOY_LEVEL
        apart in x; no run crosses another edge's stub or left-border vertical (channels are the only verticals a run may cross)."""
        targets = [tuple(int(v) for v in m) for m in re.findall(r'<rect class="tgt" x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"', svg)]
        outside = re.search(r'<rect class="lane" x="(-?\d+)"', svg)
        stack_right = max([x + w for x, _y, w, _h in targets], default=0)
        lane_left = int(outside.group(1)) if outside else math.inf
        rects = dict(node_rects(svg))
        for m in re.finditer(r'<g class="group[^"]*" data-id="([^"]*)"[^>]*>.*?<rect class="grp" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg, re.S):
            rects.setdefault(xml_unescape(m.group(1)), tuple(int(m.group(k)) for k in range(2, 6)))
        for s_uid, t_uid, pts in edge_polylines(svg):  # every polyline end lies on its endpoint's border (D29)
            for uid, (px, py) in ((s_uid, pts[0]), (t_uid, pts[-1])):
                x, y, w, h = rects[uid]
                on_h = (abs(py - y) < 0.11 or abs(py - (y + h)) < 0.11) and x - 0.11 <= px <= x + w + 0.11
                on_v = (abs(px - x) < 0.11 or abs(px - (x + w)) < 0.11) and y - 0.11 <= py <= y + h + 0.11
                self.assertTrue(on_h or on_v, f"end {(px, py)} of {s_uid}->{t_uid} is not on the border of {uid} {rects[uid]}")
        verticals, horizontals = [], []
        for number, (_s, _t, pts) in enumerate(edge_polylines(svg)):
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                if ax == bx and ay != by:
                    verticals.append((ax, min(ay, by), max(ay, by), number))
                elif ay == by and ax != bx:
                    horizontals.append((ay, min(ax, bx), max(ax, bx), number))
        for i, (x, y0, y1, n1) in enumerate(verticals):
            for x2, a0, a1, n2 in verticals[i + 1 :]:
                if n1 != n2:
                    self.assertFalse(x == x2 and y0 < a1 and a0 < y1, f"collinear vertical runs at x={x}")
        for i, (y, x0, x1, n1) in enumerate(horizontals):
            for y2, a0, a1, n2 in horizontals[i + 1 :]:
                if n1 != n2 and abs(y - y2) < generate_diagram.DEPLOY_LEVEL:
                    self.assertGreaterEqual(max(a0 - x1, x0 - a1), generate_diagram.DEPLOY_LEVEL, f"horizontal runs too close at y={y} and y={y2}")
        for y, x0, x1, n1 in horizontals:
            for x, y0, y1, n2 in verticals:
                if n1 != n2 and not (stack_right < x < lane_left) and x0 < x < x1 and y0 < y < y1:
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
        stubs = sorted(pts[-1][0] for _s, _t, pts in edge_polylines(svg))  # the hub end of every edge
        self.assertGreaterEqual(min(b - a for a, b in zip(stubs, stubs[1:])), 2, "hub stubs at least 2 px apart")
        for sdp in generate_diagram.sdps(load_catalog(FIXTURE)):
            self._assert_runs_clean(deployment_svg(load_catalog(FIXTURE), sdp["uid"]))

    def test_two_edges_leaving_one_container_start_apart(self) -> None:
        objects = [
            plain("RTC-1", "runtime_service", "Cluster"),
            component("P-1", "Alpha"),
            component("X-1", "Xray"),
            component("Y-1", "Yankee"),
            pattern({"G": ["P-1"], "H": ["X-1"], "I": ["Y-1"]}),
            relationship("R-1", "RTC-1", "X-1", "one"),
            relationship("R-2", "RTC-1", "Y-1", "two"),
        ]
        objects[4]["serviceGroups"][0]["substrate"] = "RTC-1"
        cat = load_catalog(write_workspace(Path(tempfile.mkdtemp()), objects))
        svg = deployment_svg(cat, "SDP-1")
        paths = edge_polylines(svg)
        self.assertEqual(len(paths), 2)
        self.assertNotEqual(paths[0][2][0], paths[1][2][0])
        group = re.search(r'<g class="group[^"]*" data-id="RTC-1"[^>]*>.*?<rect class="grp" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg, re.S)
        gx, gy, gw, gh = (int(group.group(i)) for i in range(1, 5))
        for _s, _t, pts in paths:
            px, py = pts[0]
            self.assertTrue(gx <= px <= gx + gw and abs(py - (gy + gh)) < 0.11 or abs(py - gy) < 0.11, "start lies on the container border")
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
        svg = svg_for(objects)
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
