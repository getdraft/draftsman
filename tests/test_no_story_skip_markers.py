"""No story-scoped skip markers may remain under tests/ once the final story lands (plan D30, AC17)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
OWN_FILE = Path(__file__).resolve().name
SKIP_REASON_FILE = "test_skip_reasons.py"
MARKER = re.compile(r"""^\s*@unittest\.skip\(["']enabled in S\d+""")


class NoStorySkipMarkersTests(unittest.TestCase):
    def test_no_enabled_in_skip_markers_remain(self) -> None:
        matches = []
        for path in sorted(TESTS_DIR.rglob("*.py")):
            if path.name in (OWN_FILE, SKIP_REASON_FILE):
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if MARKER.search(line):
                    matches.append(f"{path.relative_to(TESTS_DIR)}:{number}")
        self.assertEqual(matches, [], "story skip markers remain: " + ", ".join(matches))


if __name__ == "__main__":
    unittest.main()
