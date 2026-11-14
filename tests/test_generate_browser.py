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

    def test_two_runs_identical(self) -> None:
        first, second = self.tmp / "a", self.tmp / "b"
        self.assertEqual(run_browser(FIXTURE, first).returncode, 0)
        self.assertEqual(run_browser(FIXTURE, second).returncode, 0)
        self.assertEqual(tree(first / "diagrams"), tree(second / "diagrams"))


if __name__ == "__main__":
    unittest.main()
