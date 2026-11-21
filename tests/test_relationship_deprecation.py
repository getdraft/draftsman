"""#368 S1.1: flow inbound/bidirectional and free-text externalTarget are deprecated in the schema, template and docs,
and still accepted."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = REPO_ROOT / "framework" / "schemas" / "relationship.schema.yaml"
TEMPLATE = REPO_ROOT / "templates" / "relationship.yaml.tmpl"
DOCS = REPO_ROOT / "framework" / "docs"


def flat(text: str) -> str:
    return " ".join(text.split())


class SchemaDeprecationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))

    def test_values_are_still_accepted(self) -> None:
        self.assertEqual(self.schema["enumFields"]["flow"], ["outbound", "inbound", "bidirectional"])
        for field in ("flow", "externalTarget", "target", "targetListener"):
            self.assertIn(field, self.schema["optionalFields"])
        self.assertNotIn("flow", self.schema.get("requiredFields", []))
        self.assertEqual(self.schema["conditionalRequired"], [{"when": {"externalTarget": None}, "require": ["target"]}])
        # Deprecation is described, not enforced by a per-object warning here (the ratcheted rules come in S1.2).
        self.assertNotIn("deprecatedFields", self.schema)

    def test_descriptions_say_deprecated(self) -> None:
        notes = self.schema["fieldDescriptions"]
        self.assertTrue(notes["flow"].startswith("Deprecated except for outbound, the default."))
        self.assertIn("inbound (swap source and target so the caller is the source)", notes["flow"])
        self.assertIn("bidirectional (a request/response is direction synchronous)", notes["flow"])
        self.assertTrue(notes["externalTarget"].startswith("Deprecated."))
        self.assertIn("system object with listeners", notes["externalTarget"])
        hint = flat(self.schema["aiHint"])
        self.assertIn("externalTarget (free string) is deprecated", hint)
        self.assertIn("flow is deprecated except for its default, outbound", hint)
        self.assertIn("Removal is deferred to a later major version.", hint)


class TemplateTests(unittest.TestCase):
    def test_template_defaults_to_outbound_and_listener(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("\nflow: outbound\n", text)
        self.assertIn("targetListener: <listener-uid>", text)
        self.assertNotRegex(text, r"(?m)^externalTarget:")
        self.assertNotIn("inbound|bidirectional>", text)


class DocsDeprecationTests(unittest.TestCase):
    def test_draftsman_section(self) -> None:
        text = (DOCS / "draftsman.md").read_text(encoding="utf-8")
        match = re.search(r"(?ms)^### Deprecated Relationship Fields\n(.*?)(?=^#)", text)
        self.assertIsNotNone(match)
        body = flat(match.group(1))
        for phrase in (
            "`flow: inbound`, `flow: bidirectional` and free-text `externalTarget` are deprecated.",
            "existing relationships keep loading, validating and rendering",
            "nothing is removed until a later major version",
            "Never write them in new or edited relationships",
            "`direction: synchronous`",
            "X as `source` and the component as `target`",
            "`target: <system uid>` and `targetListener: <listener uid>`",
        ):
            self.assertIn(phrase, body)
        self.assertNotIn("Set `flow` to `outbound` (default), `inbound`, or `bidirectional`", text)

    def test_other_docs_and_skill(self) -> None:
        expectations = {
            DOCS / "object-types.md": "free-text `externalTarget` are deprecated but still accepted",
            DOCS / "how-to-add-objects.md": "are deprecated but still accepted",
            DOCS / "yaml-schema-reference.md": "are deprecated but still accepted",
            DOCS / "sdp-completion-interview.md": "free-text `externalTarget` is deprecated",
            DOCS / "software-deployment-patterns.md": "is deprecated but still accepted",
            REPO_ROOT / "framework" / "skills" / "draftsman-author" / "SKILL.md":
                "Never write `flow: inbound`, `flow: bidirectional` or free-text `externalTarget` in a new or edited relationship",
        }
        for path, phrase in expectations.items():
            with self.subTest(path=path.name):
                self.assertIn(phrase, flat(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
