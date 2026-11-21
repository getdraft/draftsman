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
             "Otherwise create a stub and link it.", "Upgrade, do not duplicate."],
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
