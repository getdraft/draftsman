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

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "diagram_workspace"


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
        self.assertEqual(page.count('class="edge"'), len(model.relationships))
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

    @unittest.skip("enabled in S5")
    def test_logical_golden(self) -> None:
        self.fail("not implemented until S5")

    @unittest.skip("enabled in S5")
    def test_logical_bands_and_dashed_derived(self) -> None:
        self.fail("not implemented until S5")

    @unittest.skip("enabled in S5")
    def test_barycentre_tie_break_by_uid(self) -> None:
        self.fail("not implemented until S5")

    @unittest.skip("enabled in S5")
    def test_grid_snapping(self) -> None:
        self.fail("not implemented until S5")

    @unittest.skip("enabled in S5")
    def test_external_node_in_outside_lane(self) -> None:
        self.fail("not implemented until S5")

    @unittest.skip("enabled in S5")
    def test_svg_escaping(self) -> None:
        self.fail("not implemented until S5")

    @unittest.skip("enabled in S5")
    def test_large_logical_svg_valid_fast_low_crossings(self) -> None:
        self.fail("not implemented until S5")

    @unittest.skip("enabled in S5")
    def test_logical_substrate_is_box(self) -> None:
        self.fail("not implemented until S5")

    @unittest.skip("enabled in S5")
    def test_svg_desc_has_no_version(self) -> None:
        self.fail("not implemented until S5")

    @unittest.skip("enabled in S6")
    def test_deployment_golden(self) -> None:
        self.fail("not implemented until S6")

    @unittest.skip("enabled in S6")
    def test_nesting_order(self) -> None:
        self.fail("not implemented until S6")

    @unittest.skip("enabled in S6")
    def test_zone_lanes_order_and_fallback(self) -> None:
        self.fail("not implemented until S6")

    @unittest.skip("enabled in S6")
    def test_substrate_container_not_node(self) -> None:
        self.fail("not implemented until S6")

    @unittest.skip("enabled in S6")
    def test_empty_group_caption(self) -> None:
        self.fail("not implemented until S6")

    @unittest.skip("enabled in S6")
    def test_container_edge_attachment(self) -> None:
        self.fail("not implemented until S6")

    @unittest.skip("enabled in S6")
    def test_large_deployment_svg_valid_fast(self) -> None:
        self.fail("not implemented until S6")

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
