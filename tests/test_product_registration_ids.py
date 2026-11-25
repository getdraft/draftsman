"""ProductRegistration repository.id and repository.ownerId (#455)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "framework" / "tools"))

import validate  # noqa: E402

REG = {
    "schemaVersion": "1.0",
    "uid": "01M7SYNC03-PR01",
    "type": "product_registration",
    "name": "Absence Service",
    "catalogStatus": "complete",
    "owner": {"team": "absence", "contact": "absence@example.com"},
    "repository": {
        "provider": "github",
        "url": "https://github.com/example-org/absence-service",
        "defaultBranch": "main",
    },
}


class ProductRegistrationIdTests(unittest.TestCase):
    def schema(self) -> dict:
        found = [item for item in validate.load_schemas(validate.SCHEMA_ROOT) if item.get("type") == "product_registration"]
        self.assertEqual(len(found), 1)
        return found[0]

    def id_failures(self, repository: dict) -> list[str]:
        failures: list[str] = []
        validate.validate_product_registration({**REG, "repository": repository}, Path("reg.yaml"), {}, failures, [])
        return [item for item in failures if "repository.id" in item or "repository.ownerId" in item]

    def test_the_schema_names_the_optional_pins(self) -> None:
        repo = self.schema()["productRepository"]
        self.assertIn("id", repo["optionalFields"])
        self.assertIn("ownerId", repo["optionalFields"])
        self.assertIn("repository_id", repo["fieldDescriptions"]["id"])
        self.assertIn("repository_owner_id", repo["fieldDescriptions"]["ownerId"])

    def test_absent_and_numeric_ids_pass_schema_and_validation(self) -> None:
        base = dict(REG["repository"])
        self.assertEqual(self.id_failures(base), [])
        self.assertEqual(self.id_failures({**base, "id": 424242, "ownerId": 1001}), [])
        self.assertEqual(self.id_failures({**base, "id": "424242", "ownerId": "1001"}), [])
        failures: list[str] = []
        validate.validate_against_schema(
            {**REG, "repository": {**base, "id": 424242, "ownerId": "1001"}},
            Path("reg.yaml"),
            validate.load_schemas(validate.SCHEMA_ROOT),
            failures,
        )
        self.assertEqual(failures, [])

    def test_unusable_ids_fail_validation(self) -> None:
        base = dict(REG["repository"])
        for value in (0, -1, True, 1.5, "0", "042", "abc", "", [], {}):
            with self.subTest(value):
                id_failures = self.id_failures({**base, "id": value})
                owner_failures = self.id_failures({**base, "ownerId": value})
                self.assertTrue(id_failures and "repository.id" in id_failures[0], id_failures)
                self.assertTrue(owner_failures and "repository.ownerId" in owner_failures[0], owner_failures)

    def test_omitting_the_id_is_valid(self) -> None:
        failures: list[str] = []
        warnings: list[str] = []
        validate.validate_product_registration(REG, Path("reg.yaml"), {}, failures, warnings)
        self.assertEqual(failures, [])
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
