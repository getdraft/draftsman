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

    @unittest.skip("enabled in S4")
    def test_container_caption_variants(self) -> None:
        self.fail("not implemented until S4")

    @unittest.skip("enabled in S4")
    def test_substrate_type_mismatch_and_unknown_uid_warnings(self) -> None:
        self.fail("not implemented until S4")

    @unittest.skip("enabled in S4")
    def test_conflict_warning(self) -> None:
        self.fail("not implemented until S4")

    @unittest.skip("enabled in S4")
    def test_zone_assignment_and_warning(self) -> None:
        self.fail("not implemented until S4")

    @unittest.skip("enabled in S4")
    def test_node_sets_per_view(self) -> None:
        self.fail("not implemented until S4")

    @unittest.skip("enabled in S4")
    def test_warning_dedup_sorted(self) -> None:
        self.fail("not implemented until S4")

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
