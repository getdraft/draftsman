"""Deterministic checks for the Evidence Discipline fixtures (E2-S3).

The fixtures are not run against a live model. This test only checks that
the fixtures are well formed and that draftsman-core contains each rule's
key phrase.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "framework" / "skills" / "draftsman-core" / "SKILL.md"
FIXTURES = ROOT / "tests" / "fixtures" / "evidence_discipline"

RULES = ("R1", "R2", "R3", "R4", "R5", "R6")

KEY_PHRASES = {
    "R1": "relationship the index does not characterise",
    "R2": "parse prose into structure",
    "R3": "the catalog does not record",
    "R4": "A count is a claim",
    "R5": "Refusing is a valid answer",
    "R6": "labeled as inferred",
}

KEYS = {"id", "rule", "question", "index_excerpt", "forbidden_phrases", "required_phrases"}


def _load(rule):
    return json.loads((FIXTURES / f"{rule}.json").read_text(encoding="utf-8"))


class EvidenceDisciplineFixtureTests(unittest.TestCase):
    def test_exactly_six_fixtures_one_per_rule(self):
        files = sorted(p.name for p in FIXTURES.glob("*.json"))
        self.assertEqual(files, [f"{r}.json" for r in RULES])

    def test_each_fixture_has_all_six_keys_and_matching_rule(self):
        for rule in RULES:
            with self.subTest(rule=rule):
                data = _load(rule)
                self.assertEqual(set(data.keys()), KEYS)
                self.assertEqual(data["rule"], rule)
                self.assertTrue(data["id"])
                self.assertTrue(data["question"])

    def test_phrase_lists_are_non_empty_string_lists(self):
        for rule in RULES:
            with self.subTest(rule=rule):
                data = _load(rule)
                for key in ("forbidden_phrases", "required_phrases"):
                    self.assertIsInstance(data[key], list)
                    self.assertTrue(data[key], f"{rule} {key} is empty")
                    self.assertTrue(all(isinstance(p, str) and p for p in data[key]))

    def test_skill_contains_each_rule_key_phrase(self):
        skill_text = SKILL.read_text(encoding="utf-8")
        for rule in RULES:
            with self.subTest(rule=rule):
                self.assertIn(KEY_PHRASES[rule], skill_text)


if __name__ == "__main__":
    unittest.main()
