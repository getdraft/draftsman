"""Syntax floor: modules that ship under framework/tools must parse as Python 3.9.

This covers grammar only. Runtime-only constructs (isinstance with X | Y,
zip(strict=...), parenthesised multi-item context managers, newer stdlib APIs)
are forbidden by review rule instead (plan decision D27).
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Extend this list whenever a story adds a module under framework/tools/.
MODULES = [
    "framework/tools/generate_diagram.py",
]


class PythonFloorTests(unittest.TestCase):
    def test_modules_parse_as_python_3_9(self) -> None:
        for rel in MODULES:
            with self.subTest(module=rel):
                path = REPO_ROOT / rel
                self.assertTrue(path.is_file(), f"missing module {rel}")
                source = path.read_text(encoding="utf-8")
                ast.parse(source, filename=rel, feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
