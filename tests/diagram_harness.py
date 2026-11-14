"""Shared helpers for diagram tests: golden comparison and determinism properties (plan D16).

Importable from tests as ``from tests import diagram_harness``.
"""

from __future__ import annotations

import os
import random
import sys
import unittest
from pathlib import Path
from typing import Any, Callable

FIXTURE_WORKSPACE = Path(__file__).resolve().parent / "fixtures" / "diagram_workspace"
GOLDEN_DIR = FIXTURE_WORKSPACE / "golden"


def golden_path(slug: str, view: str) -> Path:
    """Path of the committed golden SVG: golden/<sdp-slug>-<view>.svg."""
    return GOLDEN_DIR / f"{slug}-{view}.svg"


def check_golden(case: unittest.TestCase, path: Path, render: Callable[[], bytes]) -> None:
    """Compare render() with the golden file byte for byte.

    With UPDATE_GOLDEN=1 the golden is (re)written and the check passes.
    """
    produced = render()
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(produced)
        return
    if not path.is_file():
        case.fail(f"golden missing: {path} (run with UPDATE_GOLDEN=1 to create it)")
    if path.read_bytes() != produced:
        case.fail(f"output differs from golden {path} (run with UPDATE_GOLDEN=1 if the change is intended)")


def assert_render_twice(case: unittest.TestCase, render: Callable[[], bytes]) -> bytes:
    """(a) Two renders in one process are byte-equal."""
    first = render()
    second = render()
    case.assertEqual(first, second, "two renders in one process differ")
    return first


def assert_reversed_discovery(case: unittest.TestCase, render: Callable[[], bytes]) -> bytes:
    """(b) Reversing file discovery does not change the output.

    discover_yaml_files is patched on sys.modules["generate_c4"], the module
    generate_diagram actually calls. render must trigger discovery; the call
    counter must be above zero so the test cannot pass vacuously.
    """
    module = sys.modules["generate_c4"]
    original = module.discover_yaml_files
    calls = {"count": 0}

    def reversed_discovery(root: Path) -> list[Path]:
        calls["count"] += 1
        return list(reversed(original(root)))

    baseline = render()
    module.discover_yaml_files = reversed_discovery
    try:
        patched = render()
    finally:
        module.discover_yaml_files = original
    case.assertGreater(calls["count"], 0, "patched discover_yaml_files was never called")
    case.assertEqual(baseline, patched, "reversed file discovery changed the output")
    return baseline


def shuffled_catalog(catalog: dict[str, Any], seed: int = 1234) -> dict[str, Any]:
    keys = list(catalog)
    random.Random(seed).shuffle(keys)
    return {key: catalog[key] for key in keys}


def assert_shuffled_catalog(case: unittest.TestCase, render: Callable[[dict[str, Any]], bytes], catalog: dict[str, Any]) -> bytes:
    """(c) Rebuilding the catalog dict in random.Random(1234)-shuffled order does not change the output."""
    baseline = render(catalog)
    shuffled = shuffled_catalog(catalog)
    case.assertEqual(baseline, render(shuffled), "shuffled catalog order changed the output")
    return baseline
