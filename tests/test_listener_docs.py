"""#341 E3: the Draftsman docs describe listeners and lookup-before-create, and agree with the code."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "framework" / "docs"
for path in (REPO_ROOT, REPO_ROOT / "framework" / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import validate  # noqa: E402
from draft_table import catalog  # noqa: E402


def section(text: str, heading: str) -> str:
    match = re.search(rf"(?ms)^## {re.escape(heading)}\n(.*?)(?=^## )", text)
    assert match, heading
    return match.group(1)


class ListenerLookupDocTests(unittest.TestCase):
    def setUp(self) -> None:
        self.draftsman = (DOCS / "draftsman.md").read_text(encoding="utf-8")
        self.lookup = section(self.draftsman, "Listener Lookup Before Create")

    def test_procedure_steps_in_order(self) -> None:
        steps = re.findall(r"(?m)^\d+\. \*\*([^*]+)\*\*", self.lookup)
        self.assertEqual(
            steps,
            ["Resolve the owner.", "Normalize the identity key.", "Link an exact match.",
             "Ask about near matches.", "Otherwise create a stub and link it.", "Upgrade, do not duplicate."],
        )

    def test_key_statements(self) -> None:
        text = " ".join(self.lookup.split())
        for phrase in (
            "owner + protocol + port + endpoint",
            "never picked",
            "without asking",
            "`catalogStatus: stub`",
            "keeps its UID",
            "company-internal relationship owner",
            "`sdp-internal-stub-listener`",
            "`relationship-target-listener`",
            "the host is never stored",
            "`interface_unprotected`",
        ):
            self.assertIn(phrase, text)

    def test_owner_kinds_match_the_validator(self) -> None:
        for kind in validate.OWNER_KIND_TYPES:
            self.assertIn(f"`{kind}`", self.lookup)

    def test_default_ports_match_the_code(self) -> None:
        for protocol, port in catalog.LISTENER_DEFAULT_PORTS.items():
            self.assertIn(f"`{protocol}` {port}", self.lookup)
        self.assertEqual(catalog.LISTENER_DEFAULT_PORTS, validate.LISTENER_DEFAULT_PORTS)

    def test_named_helpers_exist(self) -> None:
        for name in re.findall(r"`(\w+_listener\w*|vendor_stub_problem)`", self.lookup):
            self.assertTrue(callable(getattr(catalog, name, None)), name)

    def test_normalization_described_matches_the_code(self) -> None:
        # path only, host dropped, templated parameters compared as one placeholder, trailing slash ignored
        a = catalog.normalize_listener_endpoint("https://api.example.com/orders/{id}/?x=1")
        b = catalog.normalize_listener_endpoint("/orders/:orderId")
        self.assertEqual(a, b)
        self.assertEqual(validate.normalize_listener_endpoint("https://api.example.com/orders/{id}/"), a)

    def test_relationship_authoring_names_target_listener(self) -> None:
        authoring = section(self.draftsman, "Relationship Authoring")
        self.assertRegex(authoring, r"(?m)^3\. Set `targetListener`")
        self.assertIn("Listener Lookup Before Create", authoring)
        self.assertEqual([int(n) for n in re.findall(r"(?m)^(\d+)\. Set ", authoring)], list(range(1, 8)))

    def test_object_types_and_how_to_add(self) -> None:
        object_types = (DOCS / "object-types.md").read_text(encoding="utf-8")
        self.assertRegex(object_types, r"(?m)^\| Listener \| `listener` \|")
        self.assertIn("Listener Lookup Before Create", object_types)
        how_to = (DOCS / "how-to-add-objects.md").read_text(encoding="utf-8")
        add = section(how_to, "Add A Listener")
        self.assertIn("Listener Lookup Before Create", add)
        self.assertIn("`targetListener`", add)
        self.assertIn("`targetListener`", section(how_to, "Record Interfaces, Listeners And Edge Slots"))


if __name__ == "__main__":
    unittest.main()


SKILLS = REPO_ROOT / "framework" / "skills"


class ListenerSkillTests(unittest.TestCase):
    """#341 E3 S4.2: the skills agents load carry the same procedure and never license a guess."""

    def read(self, rel: str) -> str:
        return " ".join((SKILLS / rel).read_text(encoding="utf-8").split())

    def test_every_listener_skill_points_to_the_procedure(self) -> None:
        for rel in ("draftsman-core/SKILL.md", "draftsman-author/SKILL.md", "draftsman-author/references/guide.md",
                    "draftsman-diagram/SKILL.md"):
            text = self.read(rel)
            self.assertIn("Listener Lookup Before Create", text, rel)
            self.assertIn(".draft/framework/docs/draftsman.md", text, rel)

    def test_procedure_doc_heading_exists(self) -> None:
        self.assertRegex((DOCS / "draftsman.md").read_text(encoding="utf-8"), r"(?m)^## Listener Lookup Before Create$")

    def test_author_skill_steps_match_the_docs(self) -> None:
        raw = (SKILLS / "draftsman-author" / "SKILL.md").read_text(encoding="utf-8")
        block = section(raw + "\n## end\n", "Calls land on listeners")
        steps = re.findall(r"(?m)^\d+\. \*\*([^*]+)\*\*", block)
        self.assertEqual(steps, ["Resolve the owner", "Normalize the key:", "Exact match:", "Near match:", "No match:", "Real listener authored later:"])
        text = " ".join(block.split())
        for phrase in ("`targetListener`", "Never pick one", "without asking", "`catalogStatus: stub`", "keep its UID",
                       "company-internal caller", "`sdp-internal-stub-listener`", "`interface_unprotected`",
                       "`relationship-target-listener`"):
            self.assertIn(phrase, text)

    def test_author_skill_helpers_exist(self) -> None:
        raw = (SKILLS / "draftsman-author" / "SKILL.md").read_text(encoding="utf-8")
        names = re.findall(r"`(\w+_listener)`", raw)
        self.assertTrue(names)
        for name in names:
            self.assertTrue(callable(getattr(catalog, name, None)), name)

    def test_no_skill_licenses_guessing(self) -> None:
        self.assertIn("never guess a listener's owner and never invent a port", self.read("draftsman-core/SKILL.md"))
        self.assertIn("never by inventing a port", self.read("draftsman-diagram/SKILL.md"))
        # every mention of guessing an owner or inventing a port is a prohibition
        for rel in ("draftsman-core/SKILL.md", "draftsman-author/SKILL.md", "draftsman-query/SKILL.md", "draftsman-diagram/SKILL.md"):
            text = self.read(rel)
            for match in re.finditer(r"(?i)\b(guess\w*|invent\w*) (the |a |an )?(listener's )?(owner|port)", text):
                before = text[max(0, match.start() - 12):match.start()].lower()
                self.assertRegex(before, r"(never|not|by) ?$", (rel, match.group(0)))

    def test_query_skill_reads_listener_objects(self) -> None:
        text = self.read("draftsman-query/SKILL.md")
        for phrase in ("`listener` objects whose `owner.ref` is X", "`targetListener`", "A stub is not a fact"):
            self.assertIn(phrase, text)

    def test_guide_scan_rows_use_schema_values(self) -> None:
        import yaml

        schema = yaml.safe_load((REPO_ROOT / "framework" / "schemas" / "listener.schema.yaml").read_text(encoding="utf-8"))
        for protocol in re.findall(r"`protocol: (\w+)`", self.read("draftsman-author/references/guide.md")):
            self.assertIn(protocol, schema["enumFields"]["protocol"])
