from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REASON = re.compile(r"^enabled in S(3|4|5|6|7|8|9|10)$")


def skip_reasons(path: Path) -> list[tuple[int, object]]:
    found = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name == "skip" and (isinstance(func, ast.Name) or (isinstance(func, ast.Attribute) and getattr(func.value, "id", "") == "unittest")):
                arg = node.args[0] if node.args else None
                found.append((node.lineno, arg.value if isinstance(arg, ast.Constant) else None))
    return found


class SkipReasonTests(unittest.TestCase):
    def test_skip_reasons_name_a_story(self) -> None:
        for path in sorted(TESTS_DIR.rglob("*.py")):
            if path.name == Path(__file__).name:
                continue
            for line, reason in skip_reasons(path):
                with self.subTest(file=path.name, line=line):
                    self.assertIsInstance(reason, str)
                    self.assertRegex(reason, REASON)


if __name__ == "__main__":
    unittest.main()
