from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from framework.tools import generate_diagram  # noqa: F401  (puts generate_c4 on sys.modules)

from tests import diagram_harness as harness


class GoldenHarnessTests(unittest.TestCase):
    def test_update_golden_writes_and_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g" / "x-logical.svg"
            with mock.patch.dict(os.environ, {"UPDATE_GOLDEN": "1"}):
                harness.check_golden(self, path, lambda: b"<svg/>")
            self.assertEqual(path.read_bytes(), b"<svg/>")

    def test_matching_golden_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.svg"
            path.write_bytes(b"abc")
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("UPDATE_GOLDEN", None)
                harness.check_golden(self, path, lambda: b"abc")

    def test_one_byte_difference_fails_naming_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.svg"
            path.write_bytes(b"abc")
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("UPDATE_GOLDEN", None)
                with self.assertRaises(AssertionError) as ctx:
                    harness.check_golden(self, path, lambda: b"abd")
            self.assertIn(str(path), str(ctx.exception))

    def test_golden_path_shape(self) -> None:
        self.assertEqual(harness.golden_path("demo", "logical").name, "demo-logical.svg")
        self.assertEqual(harness.golden_path("demo", "deployment").parent.name, "golden")


class PropertyHelperTests(unittest.TestCase):
    def test_render_twice(self) -> None:
        calls = []

        def render() -> bytes:
            calls.append(1)
            return b"same"

        self.assertEqual(harness.assert_render_twice(self, render), b"same")
        self.assertEqual(len(calls), 2)

    def test_render_twice_detects_difference(self) -> None:
        counter = iter(range(10))
        with self.assertRaises(AssertionError):
            harness.assert_render_twice(self, lambda: str(next(counter)).encode())

    def test_reversed_discovery_patches_and_counts(self) -> None:
        original = sys.modules["generate_c4"].discover_yaml_files

        def render() -> bytes:
            files = sys.modules["generate_c4"].discover_yaml_files(harness.FIXTURE_WORKSPACE / "catalog")
            return ",".join(sorted(p.name for p in files)).encode()

        harness.assert_reversed_discovery(self, render)
        self.assertIs(sys.modules["generate_c4"].discover_yaml_files, original)

    def test_reversed_discovery_fails_when_discovery_unused(self) -> None:
        with self.assertRaises(AssertionError):
            harness.assert_reversed_discovery(self, lambda: b"x")

    def test_shuffled_catalog_is_rebuilt_in_seeded_order(self) -> None:
        catalog = {f"U{i}": {"uid": f"U{i}"} for i in range(20)}
        seen = []

        def render(cat: dict) -> bytes:
            seen.append(list(cat))
            return ",".join(sorted(cat)).encode()

        harness.assert_shuffled_catalog(self, render, catalog)
        self.assertEqual(seen[0], list(catalog))
        self.assertNotEqual(seen[1], seen[0])
        self.assertEqual(sorted(seen[1]), sorted(seen[0]))
        self.assertEqual(list(harness.shuffled_catalog(catalog)), seen[1])

    def test_shuffled_catalog_detects_order_dependence(self) -> None:
        catalog = {f"U{i}": {} for i in range(20)}
        with self.assertRaises(AssertionError):
            harness.assert_shuffled_catalog(self, lambda c: ",".join(c).encode(), catalog)


if __name__ == "__main__":
    unittest.main()
