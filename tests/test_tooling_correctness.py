from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from framework.tools.generate_ai_index import markdown_summary
from framework.tools import generate_c4
from framework.tools.validate import scan_for_secrets


class SecretScanTests(unittest.TestCase):
    def test_plaintext_secret_beside_secret_reference_is_flagged(self) -> None:
        # A mapping that declares a secretReference must not become a hiding place
        # for a plaintext secret in a sibling key.
        failures: list[str] = []
        scan_for_secrets(
            {"config": {"secretReference": "vault://app/db", "db_password": "hunter2"}},
            Path("technology-component-x.yaml"),
            failures,
        )
        self.assertTrue(
            any("Plaintext secret leaked" in message for message in failures),
            failures,
        )

    def test_top_level_secret_reference_does_not_skip_whole_object(self) -> None:
        failures: list[str] = []
        scan_for_secrets(
            {"secretReference": "vault://app/token", "apiToken": "abc123"},
            Path("object.yaml"),
            failures,
        )
        self.assertTrue(any("Plaintext secret leaked" in message for message in failures), failures)

    def test_lone_secret_reference_is_not_flagged(self) -> None:
        # The approved indirection itself must remain valid.
        failures: list[str] = []
        scan_for_secrets(
            {"apiKey": {"secretReference": "vault://app/api-key"}},
            Path("object.yaml"),
            failures,
        )
        self.assertEqual(failures, [])


class MarkdownSummaryTests(unittest.TestCase):
    def _summary_for(self, text: str) -> str:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            path.write_text(text, encoding="utf-8")
            return markdown_summary(path)

    def test_uses_okf_frontmatter_description(self) -> None:
        summary = self._summary_for(
            "---\n"
            "type: documentation\n"
            'title: "Example"\n'
            'description: "Curated one-line description."\n'
            "tags:\n"
            "  - draft\n"
            "timestamp: 2026-01-01T00:00:00-00:00\n"
            "---\n"
            "# Example\n"
            "\n"
            "Body prose that should not win over the description.\n"
        )
        self.assertEqual(summary, "Curated one-line description.")

    def test_falls_back_to_body_prose_when_no_description(self) -> None:
        summary = self._summary_for(
            "---\n"
            "type: documentation\n"
            'title: "Example"\n'
            "---\n"
            "# Example\n"
            "\n"
            "First prose line.\n"
        )
        self.assertEqual(summary, "First prose line.")

    def test_plain_markdown_without_frontmatter(self) -> None:
        summary = self._summary_for("# Example\n\nFirst prose line.\n")
        self.assertEqual(summary, "First prose line.")


class GenerateC4Tests(unittest.TestCase):
    def test_handles_catalog_without_system_object(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            catalog = workspace / "catalog"
            catalog.mkdir(parents=True, exist_ok=True)
            (catalog / "a.yaml").write_text(
                'schemaVersion: "1.0"\n'
                "uid: 01TESTAAAA-0001\n"
                "type: product_component\n"
                "name: Component A\n"
                "description: A test component.\n",
                encoding="utf-8",
            )
            (catalog / "b.yaml").write_text(
                'schemaVersion: "1.0"\n'
                "uid: 01TESTAAAA-0002\n"
                "type: product_component\n"
                "name: Component B\n"
                "description: A test component.\n",
                encoding="utf-8",
            )
            (catalog / "rel.yaml").write_text(
                'schemaVersion: "1.0"\n'
                "uid: 01TESTAAAA-0003\n"
                "type: relationship\n"
                "name: A to B\n"
                "source: 01TESTAAAA-0001\n"
                "target: 01TESTAAAA-0002\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = generate_c4.main(
                    ["--workspace", str(workspace), "--format", "structurizr", "--dry-run"]
                )

            self.assertEqual(exit_code, 0)
            # The relationship between the two system-less containers is still rendered.
            self.assertIn("01TESTAAAA_0001", stdout.getvalue())
            self.assertIn("01TESTAAAA_0002", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
