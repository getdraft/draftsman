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
        self.assertIn("object.diagramPage ?", js)
        self.assertIn(">Diagrams</a>", js)
        self.assertIn(": ''}", js[js.index("object.diagramPage ?"):][:200])

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
        start = self.js.index(f"function {name}(")
        end = self.js.index("\nfunction ", start + 1)
        return self.js[start:end]

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


if __name__ == "__main__":
    unittest.main()
