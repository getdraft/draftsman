"""Hygiene for the diagram fixture (plan decision D28).

Fixture YAML and make_large.py must contain only invented data. Goldens (SVG)
are checked for hostnames, email addresses and banned terms only, because
coordinates are numeric by nature.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from framework.tools import validate_skills

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "diagram_workspace"

TWELVE_DIGITS = re.compile(r"\d{12}")
IPV4 = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
CLOUD_HOST = re.compile(r"\b[A-Za-z0-9.-]*\.(?:amazonaws\.com|azure\.com|googleapis\.com|cloudapp\.net)\b", re.IGNORECASE)
UID_VALUE = re.compile(r"^\s*-?\s*uid:\s*['\"]?([^'\"\s#]+)")


def fixture_yaml_and_script() -> list[Path]:
    files = sorted(FIXTURE_ROOT.rglob("*.yaml")) + [FIXTURE_ROOT / "make_large.py"]
    return [path for path in files if path.is_file()]


def golden_svgs() -> list[Path]:
    return sorted((FIXTURE_ROOT / "golden").glob("*.svg"))


def scope_failures(paths: list[Path], numeric: bool) -> list[str]:
    failures: list[str] = []
    for path in paths:
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            where = f"{rel}:{line_no}"
            if numeric:
                if TWELVE_DIGITS.search(line):
                    failures.append(f"12-digit number at {where}")
                if IPV4.search(line):
                    failures.append(f"IPv4 address at {where}")
                match = UID_VALUE.match(line)
                if match and not match.group(1).startswith("FX"):
                    failures.append(f"uid not starting with FX at {where}: {match.group(1)}")
            if EMAIL.search(line):
                failures.append(f"email address at {where}")
            if CLOUD_HOST.search(line):
                failures.append(f"cloud hostname at {where}")
        for label, rx in validate_skills.BANNED_TERM_RES:
            if rx.search(text):
                failures.append(f"banned term '{label}' in {rel}")
    return failures


class FixtureHygieneTests(unittest.TestCase):
    def test_fixture_yaml_and_make_large_are_clean(self) -> None:
        paths = fixture_yaml_and_script()
        self.assertGreaterEqual(len(paths), 4, "scan set unexpectedly small")
        self.assertEqual([], scope_failures(paths, numeric=True))

    def test_goldens_are_clean_when_present(self) -> None:
        # Goldens are optional until S2 commits them; scan whatever exists.
        self.assertEqual([], scope_failures(golden_svgs(), numeric=False))


if __name__ == "__main__":
    unittest.main()
