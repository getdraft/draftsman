"""S18 (D46): diagram pages are published beside the browser and linked from the pattern detail view."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "diagram_workspace"
BROWSER_TOOL = REPO_ROOT / "framework" / "tools" / "generate_browser.py"
DIAGRAM_TOOL = REPO_ROOT / "framework" / "tools" / "generate_diagram.py"
BROWSER_JS = REPO_ROOT / "framework" / "browser" / "draft-browser.js"
BACK_LINK = ' <a href="../index.html">Back to catalog</a>'
FOOTER_END = "the same catalog always produces the same page."


def function_source(js: str, name: str) -> str:
    """Source of one top-level function in the shipped JS, up to the next top-level function."""
    start = js.index(f"function {name}(")
    end = js.index("\nfunction ", start + 1)
    return js[start:end]


def run_browser(workspace: Path, out_dir: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BROWSER_TOOL), "--workspace", str(workspace), "--output", str(out_dir / "index.html"),
         "--skip-validation", "--skip-user-manual", *extra],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )


def browser_data(out_dir: Path) -> dict:
    text = (out_dir / "assets" / "browser-data.js").read_text(encoding="utf-8")
    start = text.index("{")
    return json.loads(text[start:text.rindex("}") + 1])


def tree(path: Path) -> dict:
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


class DiagramPagesInBrowserTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_pages_match_standalone_all_output(self) -> None:
        out = self.tmp / "site"
        result = run_browser(FIXTURE, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        std = self.tmp / "std"
        subprocess.run([sys.executable, str(DIAGRAM_TOOL), "--workspace", str(FIXTURE), "--all",
                        "--output-dir", str(std), "--svg-dir", str(std)], check=True, capture_output=True, text=True)
        built = tree(out / "diagrams")
        expected = tree(std)
        self.assertTrue(built)
        self.assertEqual(sorted(built), sorted(expected))
        for name, data in built.items():
            if name.endswith(".html"):
                text = data.decode("utf-8")
                self.assertEqual(text.count("Back to catalog"), 1, name)
                self.assertEqual(text.replace(BACK_LINK, ""), expected[name].decode("utf-8"), name)
                self.assertIn(FOOTER_END + BACK_LINK + "</footer>", text)
            else:
                self.assertEqual(data, expected[name], name)

    def test_standalone_pages_have_no_back_link(self) -> None:
        std = self.tmp / "std"
        subprocess.run([sys.executable, str(DIAGRAM_TOOL), "--workspace", str(FIXTURE), "--all",
                        "--output-dir", str(std)], check=True, capture_output=True, text=True)
        for page in std.glob("*.html"):
            self.assertNotIn("Back to catalog", page.read_text(encoding="utf-8"))

    def test_diagram_page_in_data_and_link_in_js(self) -> None:
        out = self.tmp / "site"
        self.assertEqual(run_browser(FIXTURE, out).returncode, 0)
        data = browser_data(out)
        patterns = [o for o in data["objects"] if o["type"] == "software_deployment_pattern"]
        self.assertTrue(patterns)
        for entry in patterns:
            self.assertTrue(re.fullmatch(r"diagrams/[a-z0-9-]+\.html", entry["diagramPage"]), entry["diagramPage"])
            self.assertTrue((out / entry["diagramPage"]).is_file())
        for entry in data["objects"]:
            if entry["type"] != "software_deployment_pattern":
                self.assertNotIn("diagramPage", entry)
        js = BROWSER_JS.read_text(encoding="utf-8")
        self.assertIn("object.diagramPage", js)
        self.assertIn("Open full page", js)  # the hero Diagrams link became the section links (S2)

    def test_skip_diagrams(self) -> None:
        out = self.tmp / "site"
        self.assertEqual(run_browser(FIXTURE, out, "--skip-diagrams").returncode, 0)
        self.assertFalse((out / "diagrams").exists())
        self.assertTrue(all("diagramPage" not in o for o in browser_data(out)["objects"]))

    def test_failing_pattern_is_reported_and_skipped(self) -> None:
        ws = self.tmp / "ws"
        shutil.copytree(FIXTURE, ws)
        victim = None
        for path in sorted((ws / "catalog").rglob("*.yaml")):
            text = path.read_text(encoding="utf-8")
            if "type: software_deployment_pattern" in text and re.search(r"^serviceGroups:", text, re.M):
                victim = path
                break
        self.assertIsNotNone(victim)
        text = victim.read_text(encoding="utf-8")
        head, _, _ = text.partition("\nserviceGroups:")
        victim.write_text(head + '\nserviceGroups: "not a list"\n', encoding="utf-8")
        out = self.tmp / "site"
        result = run_browser(ws, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("error: diagram for", result.stderr)
        self.assertIn("serviceGroups must be a list", result.stderr)
        pages = sorted((out / "diagrams").glob("*.html"))
        self.assertGreaterEqual(len(pages), 1)
        data = browser_data(out)
        flagged = [o for o in data["objects"] if o["type"] == "software_deployment_pattern" and "diagramPage" in o]
        self.assertEqual(len(flagged), len(pages))

    def test_diagram_import_failure_does_not_fail_build(self) -> None:
        out = self.tmp / "site"
        code = (
            "import sys; sys.modules['generate_diagram'] = None; "
            f"sys.path.insert(0, {str(BROWSER_TOOL.parent)!r}); import generate_browser; "
            f"raise SystemExit(generate_browser.main(['--workspace', {str(FIXTURE)!r}, '--output', {str(out / 'index.html')!r}, "
            "'--skip-validation', '--skip-user-manual']))"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((out / "index.html").is_file())
        self.assertIn("error: diagram pages skipped", result.stderr)
        self.assertFalse((out / "diagrams").exists())

    def test_catalog_load_failure_does_not_fail_build(self) -> None:
        out = self.tmp / "site"
        code = (
            f"import sys; sys.path.insert(0, {str(BROWSER_TOOL.parent)!r}); import generate_diagram, generate_browser\n"
            "def boom(workspace):\n    raise ValueError('catalog unreadable')\n"
            "generate_diagram.load_catalog = boom\n"
            f"raise SystemExit(generate_browser.main(['--workspace', {str(FIXTURE)!r}, '--output', {str(out / 'index.html')!r}, "
            "'--skip-validation', '--skip-user-manual']))"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((out / "index.html").is_file())
        lines = [ln for ln in result.stderr.splitlines() if "diagram pages skipped" in ln]
        self.assertEqual(lines, ["error: diagram pages skipped: catalog unreadable"])
        self.assertFalse((out / "diagrams").exists())

    def test_stale_diagram_files_are_removed(self) -> None:
        out = self.tmp / "site"
        stale = out / "diagrams" / "stale.html"
        stale.parent.mkdir(parents=True)
        stale.write_text("old", encoding="utf-8")
        self.assertEqual(run_browser(FIXTURE, out).returncode, 0)
        self.assertFalse(stale.exists())
        self.assertTrue(list((out / "diagrams").glob("*.html")))
        stale.write_text("old", encoding="utf-8")
        self.assertEqual(run_browser(FIXTURE, out, "--skip-diagrams").returncode, 0)
        self.assertFalse((out / "diagrams").exists())

    def test_pattern_warnings_are_printed(self) -> None:
        result = run_browser(FIXTURE, self.tmp / "site")
        self.assertRegex(result.stderr, r"\d+ warnings")
        self.assertRegex(result.stdout, r"(?m)^\S+\t.+\t\d+ warnings\t.*diagrams.+\.html$")

    def test_two_runs_identical(self) -> None:
        first, second = self.tmp / "a", self.tmp / "b"
        self.assertEqual(run_browser(FIXTURE, first).returncode, 0)
        self.assertEqual(run_browser(FIXTURE, second).returncode, 0)
        self.assertEqual(tree(first / "diagrams"), tree(second / "diagrams"))


class IntentRemovedFromBrowserTests(unittest.TestCase):
    """Source-level proxies: the repo has no browser render test, so these assert on
    the shipped JS source and on generated browser-data.js, not on rendered DOM."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.js = BROWSER_JS.read_text(encoding="utf-8")

    def _function_source(self, name: str) -> str:
        return function_source(self.js, name)

    def test_no_intent_field_or_helper_in_browser_js(self) -> None:
        # Targets the field and helper identifiers; prose such as "intentionally" is not matched.
        self.assertIsNone(re.search(r"\bintent(?:Badge|Label|-tag|-dot|-ha|-sa)?\b", self.js, re.I), "intent identifier remains")
        self.assertNotIn(".intent", self.js)
        self.assertNotIn("intentBadge", self.js)

    def test_no_intent_in_any_browser_script(self) -> None:
        for path in (REPO_ROOT / "framework" / "browser").glob("*.js"):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\bintent\b|intentBadge|intent-(?:tag|dot|ha|sa)", text, re.I), path.name)

    def test_kpi_strip_has_no_ha_components_card(self) -> None:
        kpi = self._function_source("_sdpKpiMarkup")
        self.assertNotIn("HA Components", self.js)
        for label in ("Services", "Zones", "Connections", "Availability"):
            self.assertIn(f"label: '{label}'", kpi)
        self.assertEqual(kpi.count("{ label:"), 4)

    def test_legend_has_no_intent_group(self) -> None:
        self.assertNotIn(">Intent<", self.js)
        self.assertIn(">Tiers<", self.js)
        self.assertIn(">Protocols<", self.js)

    def test_topology_node_flags_have_no_intent_slot(self) -> None:
        node = self._function_source("topologyNodeMarkup")
        self.assertNotIn("intent", node.lower())
        flags = node[node.index('class="topology-node-flags"'):]
        flags = flags[:flags.index("</div>")]
        self.assertIn("ps-corner", flags)
        self.assertEqual(flags.count("<span"), 2)  # the two literal branches of one ternary: ps-corner span when badgeLabel is set, else the empty placeholder span (mutually exclusive)

    def test_risk_ref_still_rendered(self) -> None:
        self.assertIn("function topologyBadgeMarkup(", self.js)
        badge = self._function_source("topologyBadgeMarkup")
        self.assertIn("entry.riskRef", badge)
        self.assertIn("topology-risk", badge)
        self.assertIn("m.riskRef", self.js)
        self.assertIn("drawer-risk-ref", self.js)

    def test_standalone_without_risk_ref_has_no_decision_icon(self) -> None:
        self.assertNotIn("Explicit architecture decision", self.js)

    def test_fixture_derived_browser_data_has_no_intent_key(self) -> None:
        # The fixture has no intent, so this only covers fixture-derived data. The generator
        # passes unknown entry keys through, so legacy intent values in real catalogs still
        # reach browser-data.js as inert payload; this test does not prove stripping.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            result = run_browser(FIXTURE, out)
            self.assertEqual(result.returncode, 0, result.stderr)
            data_text = (out / "assets" / "browser-data.js").read_text(encoding="utf-8")
            self.assertNotIn('"intent"', data_text)
            self.assertNotIn("HA Components", data_text)


class IntentRemovedFromBrowserCssTests(unittest.TestCase):
    """Source-level proxies: the repo has no browser render test, so these assert on
    the shipped CSS text, not on a rendered layout."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.css_dir = REPO_ROOT / "framework" / "browser"
        cls.base = (cls.css_dir / "draft-browser.css").read_text(encoding="utf-8")
        cls.sdp = (cls.css_dir / "draft-browser-sdp.css").read_text(encoding="utf-8")
        cls.js = BROWSER_JS.read_text(encoding="utf-8")

    @staticmethod
    def _block(css: str, selector: str) -> str:
        start = css.index(selector + " {")
        return css[start:css.index("}", start)]

    def test_no_intent_in_any_browser_css(self) -> None:
        for path in (self.css_dir).glob("*.css"):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\bintent\b", text, re.I), path.name)

    def test_zone_tag_rules_retained(self) -> None:
        self.assertIn(".sdp-detail .group-row .zone-tag {", self.sdp)
        self.assertIn(".sdp-detail .group-row .zone-tag .dot {", self.sdp)
        self.assertIn('.zone-tag[data-zone="public"]', self.sdp)

    def test_group_row_columns_match_emitted_cells(self) -> None:
        block = self._block(self.sdp, ".sdp-detail .group-row")
        tracks = re.search(r"grid-template-columns:\s*([^;]+);", block).group(1).split()
        start = self.js.index('<div class="group-row">')
        end = self.js.index("</div>`;", start)
        row = self.js[start:end]
        body = row[len('<div class="group-row">'):]
        # Direct children: the svc div, the zone-tag span, the notes span.
        cells = len(re.findall(r'^\s{8}<(?:div|span) class="(?:svc|zone-tag|notes)\b', body, re.M))
        self.assertEqual(cells, 3)
        self.assertEqual(len(tracks), cells)
        self.assertEqual(tracks[-1], "1fr")
        self.assertTrue(body.strip().splitlines()[-1].lstrip().startswith('<span class="notes"'))

    def test_kpi_strip_four_columns_at_wide_width(self) -> None:
        block = self._block(self.sdp, ".sdp-detail .kpi-strip")
        self.assertIn("grid-template-columns: repeat(4, minmax(0, 1fr));", block)

    def test_kpi_strip_two_by_two_at_1180(self) -> None:
        start = self.sdp.index("@media (max-width: 1180px) {")
        media = self.sdp[start:self.sdp.index("\n}", start)]
        self.assertRegex(media, r"\.kpi-strip\s*\{ grid-template-columns: repeat\(2, minmax\(0, 1fr\)\); \}")

    def test_kpi_strip_four_cards_fit_at_760(self) -> None:
        start = self.sdp.index("@media (max-width: 760px) {")
        media = self.sdp[start:self.sdp.index("\n}", start)]
        self.assertRegex(media, r"\.kpi-strip\s*\{ grid-template-columns: repeat\(2, 1fr\); \}")


class DetailDiagramSectionsTests(unittest.TestCase):
    """Source-level proxies for the Application and Deployment sections, fit toggle and sticky nav.
    The old topology functions stay in the file until a later story, so these assert on the
    source of the new functions, not on whole-file text."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.js = BROWSER_JS.read_text(encoding="utf-8")
        cls.sdp = (REPO_ROOT / "framework" / "browser" / "draft-browser-sdp.css").read_text(encoding="utf-8")

    def fn(self, name: str) -> str:
        return function_source(self.js, name)

    def test_detail_sections_application_and_deployment(self) -> None:
        nav = self.fn("_sdpSectionNavMarkup")
        order = ["sdp-s-application", "sdp-s-deployment", "sdp-s-groups", "sdp-s-decisions",
                 "sdp-s-connections", "sdp-s-tiers", "sdp-s-metadata"]
        positions = [nav.find(f"'{i}'") for i in order]
        self.assertTrue(all(p >= 0 for p in positions), nav)
        self.assertEqual(positions, sorted(positions))
        for label in ("Application", "Deployment", "Service Groups", "Decisions", "Connections", "Tier Variants", "Metadata"):
            self.assertIn(f"label: '{label}'", nav)
        labels = re.findall(r"label: '([^']+)'", nav)
        self.assertEqual(labels, ["Application", "Deployment", "Service Groups", "Decisions", "Connections", "Tier Variants", "Metadata"])
        detail = self.fn("_sdpDetailMarkup")
        app = self.fn("_sdpApplicationMarkup")
        dep = self.fn("_sdpDeploymentMarkup")
        section = self.fn("_sdpDiagramSectionMarkup")
        self.assertIn("'sdp-s-application', '01 \u2014 Application', 'Logical application diagram'", app.replace("\u2014", "\u2014"))
        self.assertIn("'sdp-s-deployment', '02 \u2014 Deployment', 'Deployment pattern diagram'", dep)
        self.assertIn("Open full page", section)
        self.assertIn('aria-pressed="true"', section)
        self.assertIn("Fit width", section)
        self.assertIn("The diagram page is not generated for this pattern.", section)
        self.assertIn("object.diagramPage", section)
        self.assertLess(detail.index("_sdpApplicationMarkup"), detail.index("_sdpDeploymentMarkup"))
        self.assertLess(detail.index("_sdpDeploymentMarkup"), detail.index("_sdpGroupsMarkup"))
        for name in ("_sdpSectionNavMarkup", "_sdpDetailMarkup", "_sdpHeroMarkup", "_sdpDiagramSectionMarkup"):
            src = self.fn(name)
            for gone in ("sdp-s-topology", "sdp-s-diagrams", "data-tier-filter", "hero-diagrams", "_sdpTopologyMarkup", "_sdpDiagramsMarkup"):
                self.assertNotIn(gone, src, f"{gone} in {name}")

    def test_embed_static_contract(self) -> None:
        load = self.fn("_sdpLoadDiagramEmbeds")
        self.assertEqual(load.count("fetch("), 1)
        self.assertIn("_sdpExtractFigureParts", load)
        self.assertIn("_sdpScopeDiagramCss", load)
        self.assertIn("createElement('script')", load)
        self.assertLess(load.index("slot.appendChild(part)"), load.index("createElement('script')"))
        self.assertIn("_sdpEmbedFail(root, missing)", load)
        self.assertIn("The diagram page is not generated for this pattern.", load)
        self.assertEqual(self.js.count("_sdpLoadDiagramEmbeds("), 2)  # definition and the single call site
        scope = self.fn("_sdpScopeDiagramCss")
        self.assertIn("replaceSync", scope)
        self.assertRegex(scope, r"try \{[^}]*replaceSync")
        self.assertIn("_sdpScopeCssByText", scope)

    def test_embed_render_token_and_ids(self) -> None:
        load = self.fn("_sdpLoadDiagramEmbeds")
        self.assertIn("const token = ++_sdpEmbedToken", load)
        self.assertIn("token !== _sdpEmbedToken", load)
        self.assertLess(load.index("token !== _sdpEmbedToken"), load.index("document.head.appendChild(style)"))
        self.assertIn("getElementById(_SDP_EMBED_STYLE_ID)", load)
        self.assertIn("getElementById('sdp-diagram-embed-script')", load)
        self.assertIn("const _SDP_EMBED_STYLE_ID = 'sdp-diagram-embed-style'", self.js)
        self.assertLess(load.index("oldStyle.remove()"), load.index("document.head.appendChild(style)"))
        self.assertLess(load.index("old.remove()"), load.index("document.body.appendChild(script)"))
        self.assertIn("sdp-diagram-embed-script", self.fn("_sdpTeardown"))

    def test_browser_js_passes_node_check(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node is not on PATH; cannot run node --check")
        result = subprocess.run(["node", "--check", str(BROWSER_JS)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_scope_css_fallback_pure_function(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node is not on PATH; cannot run the CSS scoping fallback")
        src = "\n".join(self.fn(n) for n in ("_sdpSplitSelectors", "_sdpScopeSelector", "_sdpScopeCssByText"))
        css = (":root{--a:1}html,body{margin:0}.x,.y>b{color:red}.x:not(.a,.b){}.z{content:\"}\"}"
               "@keyframes spin{from{opacity:0}to{opacity:1}}"
               "@media (prefers-reduced-motion:reduce){.x{animation:none}}"
               "@media (prefers-color-scheme:dark){.x{color:white}}")
        script = ("const _SDP_EMBED_CLASS='sdp-diagram-embed';" + src
                  + f"\nprocess.stdout.write(_sdpScopeCssByText({json.dumps(css)}));")
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            ".sdp-diagram-embed{--a:1}"
            ".sdp-diagram-embed .x,.sdp-diagram-embed .y>b{color:red}"
            ".sdp-diagram-embed .x:not(.a,.b){}"
            ".sdp-diagram-embed .z{content:\"}\"}"
            "@keyframes spin{from{opacity:0}to{opacity:1}}"
            "@media (prefers-reduced-motion:reduce){.sdp-diagram-embed .x{animation:none}}",
        )

    def test_rendered_section_markup(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node is not on PATH; cannot render the section markup")
        src = "\n".join(self.fn(n) for n in ("_sdpDiagramSectionMarkup", "_sdpApplicationMarkup",
                                           "_sdpDeploymentMarkup", "_sdpSectionNavMarkup"))
        script = ("const document={addEventListener(){}};const escapeHtml=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;');"
                  + src + """
const vm={connections:[]};
const out={};
for (const [k,o] of [['with',{diagramPage:'diagrams/p.html',tierVariants:[]}],['without',{tierVariants:[]}]])
  out[k]=_sdpSectionNavMarkup(vm,o)+_sdpApplicationMarkup(o)+_sdpDeploymentMarkup(o);
process.stdout.write(JSON.stringify(out));""")
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        for key in ("with", "without"):
            html = out[key]
            self.assertIn('id="sdp-s-application"', html)
            self.assertIn('id="sdp-s-deployment"', html)
            self.assertNotIn("sdp-s-topology", html)
            self.assertNotIn("sdp-s-diagrams", html)
        self.assertEqual(out["with"].count('href="diagrams/p.html"'), 2)
        self.assertEqual(out["with"].count("Open full page"), 2)
        self.assertEqual(out["with"].count('aria-pressed="true"'), 2)
        self.assertEqual(out["without"].count("The diagram page is not generated for this pattern."), 2)
        self.assertNotIn("Open full page", out["without"])

    def test_fit_css_rules(self) -> None:
        fit = re.search(r"\.sdp-diagram-embed\.fit svg \{([^}]*)\}", self.sdp)
        self.assertIsNotNone(fit)
        for decl in ("width: 100%", "height: auto", "min-width: 0"):
            self.assertIn(decl, fit.group(1))
        self.assertRegex(self.sdp, r"\.sdp-diagram-embed\.fit \.scroll \{ overflow-x: hidden; \}")
        self.assertRegex(self.sdp, r"\.sdp-diagram-embed \.scroll \{[^}]*overflow-x: auto")
        self.assertRegex(self.sdp, r"\.detail-layout > \* \{ min-width: 0; \}")

    def test_sticky_nav_css(self) -> None:
        nav = re.search(r"\.sdp-detail \.section-nav \{([^}]*)\}", self.sdp).group(1)
        self.assertIn("position: sticky", nav)
        self.assertIn("top: var(--sdp-header-offset)", nav)
        self.assertIn("background: var(--page)", nav)
        self.assertIn("border-bottom: 1px solid", nav)
        self.assertIn("--sdp-header-offset: 0px", self.sdp)
        self.assertRegex(self.sdp, r"scroll-margin-top: calc\(var\(--sdp-header-offset\) \+ var\(--sdp-nav-height\) \+ 8px\)")
        detail = self.fn("_sdpDetailMarkup")
        self.assertIn('<div class="sdp-sections">', detail)
        self.assertLess(detail.index("_sdpKpiMarkup"), detail.index('class="sdp-sections"'))
        self.assertLess(detail.index('class="sdp-sections"'), detail.index("_sdpSectionNavMarkup"))


class LegacyIntentTests(unittest.TestCase):
    def test_browser_data_drops_legacy_intent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            shutil.copytree(FIXTURE, ws, ignore=shutil.ignore_patterns("golden"))
            sdp = ws / "catalog" / "storefront.yaml"
            text = sdp.read_text(encoding="utf-8")
            # Legacy intent at the top level, on a service group and on a deployable object.
            text = text.replace("serviceGroups:\n- name: Edge\n", "intent: ha\nserviceGroups:\n- name: Edge\n  intent: ha\n  notes: legacy group note\n", 1)
            text = text.replace("  - ref: FXNET00001-0001\n", "  - ref: FXNET00001-0001\n    intent: standalone\n    notes: legacy deployed note\n", 1)
            self.assertEqual(text.count("intent:"), 3)
            sdp.write_text(text, encoding="utf-8")
            out = Path(tmp) / "site"
            result = run_browser(ws, out)
            self.assertEqual(result.returncode, 0, result.stderr)
            raw = (out / "assets" / "browser-data.js").read_text(encoding="utf-8")
            self.assertNotIn('"intent"', raw)
            self.assertNotIn("intent:", raw)
            data = browser_data(out)
            by_uid = {o["uid"]: o for o in data["objects"]}
            self.assertIn("FXSDP00002-0001", by_uid)
            store = by_uid["FXSDP00001-0001"]
            self.assertEqual(store["name"], "FX Storefront Pattern")
            edge = store["serviceGroups"][0]
            self.assertEqual(edge["name"], "Edge")
            self.assertEqual(edge["notes"], "legacy group note")
            self.assertEqual(edge["deployableObjects"][0]["ref"], "FXNET00001-0001")
            self.assertEqual(edge["deployableObjects"][0]["notes"], "legacy deployed note")
            self.assertNotIn("intent", json.loads(store["detail"]))
            for obj in data["objects"]:
                self.assertNotIn("intent", obj)
                for group in obj.get("serviceGroups", []):
                    self.assertNotIn("intent", group)
                    for deployed in group.get("deployableObjects", []):
                        self.assertNotIn("intent", deployed)


if __name__ == "__main__":
    unittest.main()
