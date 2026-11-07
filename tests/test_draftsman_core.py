"""Guards for framework/skills/draftsman-core/SKILL.md (E1-S2).

R6 is new text, not a move from agent/SOUL.md; it is checked structurally
only and has not been run against a live model.
"""

import re
import unittest
from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parents[1] / "framework" / "skills" / "draftsman-core" / "SKILL.md"

KEY_PHRASES = {
    "R1": "relationship the index does not characterise",
    "R2": "parse prose into structure",
    "R3": "the catalog does not record",
    "R4": "A count is a claim",
    "R5": "Refusing is a valid answer",
}

BANNED = [
    r"\bslack\b",
    r"\bdiscord\b",
    r"\bhermes\b",
    r"\bfargate\b",
    r"\barchie\b",
    r"\bcentral chat\b",
    r"switch-game-architect",
    r"ANTHROPIC_API_KEY",
]


class DraftsmanCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_line_count_under_150(self):
        self.assertLess(len(self.text.splitlines()), 150)

    def test_frontmatter(self):
        match = re.match(r"---\n(.*?)\n---\n", self.text, re.S)
        self.assertIsNotNone(match)
        meta = yaml.safe_load(match.group(1))
        self.assertEqual(meta["name"], "draftsman-core")
        self.assertTrue(meta["description"].startswith("Use when"))

    def test_rule_labels_and_key_phrases(self):
        for label, phrase in KEY_PHRASES.items():
            with self.subTest(rule=label):
                self.assertRegex(self.text, rf"\*\*{label}\*\*")
                self.assertIn(phrase, self.text)
        self.assertRegex(self.text, r"\*\*R6\*\*")

    def test_rule_rationale_sentences_kept(self):
        for sentence in (
            "indistinguishable from retrieved facts",
            "document what is already documented",
            "you have no standing to make",
            "Say how you counted",
            "spend that trust carefully",
            "read from relationship names rather than recorded endpoints",
        ):
            with self.subTest(sentence=sentence):
                self.assertIn(sentence, self.text)

    def test_direct_file_mapping(self):
        self.assertIn("reading catalog files directly applies it to the files it has actually opened", self.text)

    def test_r6_content(self):
        r6 = next(l for l in self.text.splitlines() if "**R6**" in l)
        for phrase in (
            "labeled as inferred",
            "asked to confirm",
            "never assert a relationship between two records",
            "list it as unknown",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r6)

    def test_evidence_table(self):
        for basis in ("Recorded", "Inferred", "Unknown"):
            self.assertRegex(self.text, rf"\| \*\*{basis}\*\* \|")

    def test_exactly_two_profiles(self):
        profiles = re.findall(r"^### (\w+) profile$", self.text, re.M)
        self.assertEqual(profiles, ["Query", "Author"])

    def test_no_channel_runtime_or_company_terms(self):
        for pattern in BANNED:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, self.text, re.I))


if __name__ == "__main__":
    unittest.main()
