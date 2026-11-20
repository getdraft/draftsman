"""Lookup-before-create, stub creation, stub upgrade, ambiguity and the vendor-stub rule."""

import unittest

from draft_table.catalog import (
    VENDOR_STUB_REASON,
    link_or_stub_listener,
    record_authored_listener,
)


def base_objects():
    return {
        "PROD-0001": {"uid": "PROD-0001", "type": "product_component", "name": "Checkout"},
        "EXT-0002": {"uid": "EXT-0002", "type": "external_system", "name": "Vendor Gateway"},
    }


class LookupTests(unittest.TestCase):
    def test_missing_listener_creates_one_stub_and_second_lookup_links_it(self):
        objects = base_objects()
        first = link_or_stub_listener(objects, "product_component", "Checkout", "https", None, "/orders/{id}")
        self.assertEqual(first["action"], "created")
        self.assertEqual(first["stub"]["catalogStatus"], "stub")
        self.assertEqual(first["stub"]["owner"], {"kind": "product_component", "ref": "PROD-0001"})
        objects[first["uid"]] = first["stub"]

        second = link_or_stub_listener(objects, "product_component", "Checkout", "HTTPS", 443, "/orders/:id")
        self.assertEqual(second["action"], "linked")
        self.assertEqual(second["uid"], first["uid"])

    def test_ambiguous_owner_is_returned_for_choice_not_guessed(self):
        objects = base_objects()
        objects["PROD-0003"] = {"uid": "PROD-0003", "type": "product_component", "name": "Checkout"}

        result = link_or_stub_listener(objects, "product_component", "Checkout", "https", None, "/orders")

        self.assertEqual(result["action"], "ambiguous")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertNotIn("uid", result)


class UpgradeTests(unittest.TestCase):
    def test_authored_listener_upgrades_stub_without_a_new_uid(self):
        objects = base_objects()
        created = link_or_stub_listener(objects, "product_component", "Checkout", "https", None, "/orders/{id}")
        objects[created["uid"]] = created["stub"]

        result = record_authored_listener(objects, {
            "owner": {"kind": "product_component", "ref": "Checkout"},
            "name": "Orders API",
            "protocol": "https",
            "port": 443,
            "endpoint": "/orders/{id}",
            "authenticationModel": "iam",
        })

        self.assertEqual(result["action"], "upgraded")
        self.assertEqual(result["uid"], created["uid"])
        listener = result["listener"]
        self.assertEqual(listener["catalogStatus"], "incomplete")
        self.assertEqual(listener["name"], "Orders API")
        self.assertEqual(listener["authenticationModel"], "iam")

    def test_tbd_placeholder_is_dropped_when_authored_listener_does_not_set_it(self):
        objects = base_objects()
        created = link_or_stub_listener(objects, "product_component", "Checkout", "https", None, "/orders")
        objects[created["uid"]] = created["stub"]

        result = record_authored_listener(objects, {
            "owner": {"kind": "product_component", "ref": "Checkout"},
            "protocol": "https",
            "endpoint": "/orders",
        })

        self.assertEqual(result["action"], "upgraded")
        self.assertNotEqual(result["listener"]["catalogStatus"], "stub")
        self.assertNotIn("authenticationModel", result["listener"])


class VendorStubRuleTests(unittest.TestCase):
    def test_external_stub_without_internal_source_is_rejected(self):
        result = link_or_stub_listener(base_objects(), "external_system", "Vendor Gateway", "https", None, "/quote")

        self.assertEqual(result["action"], "rejected")
        self.assertEqual(result["reason"], VENDOR_STUB_REASON)

    def test_external_stub_with_internal_source_is_created(self):
        result = link_or_stub_listener(
            base_objects(), "external_system", "Vendor Gateway", "https", None, "/quote", source_uid="PROD-0001"
        )

        self.assertEqual(result["action"], "created")

    def test_authored_external_stub_is_rejected_without_internal_relationship(self):
        objects = base_objects()
        created = link_or_stub_listener(
            objects, "external_system", "Vendor Gateway", "https", None, "/quote", source_uid="PROD-0001"
        )
        objects[created["uid"]] = created["stub"]

        result = record_authored_listener(objects, {
            "owner": {"kind": "external_system", "ref": "Vendor Gateway"},
            "protocol": "https",
            "endpoint": "/quote",
            "catalogStatus": "stub",
        })

        self.assertEqual(result["action"], "rejected")
        self.assertEqual(result["reason"], VENDOR_STUB_REASON)

    def test_authored_external_stub_is_kept_when_internal_relationship_targets_it(self):
        objects = base_objects()
        created = link_or_stub_listener(
            objects, "external_system", "Vendor Gateway", "https", None, "/quote", source_uid="PROD-0001"
        )
        objects[created["uid"]] = created["stub"]
        objects["REL-1"] = {"uid": "REL-1", "type": "relationship", "source": "PROD-0001", "targetListener": created["uid"]}

        result = record_authored_listener(objects, {
            "owner": {"kind": "external_system", "ref": "Vendor Gateway"},
            "protocol": "https",
            "endpoint": "/quote",
            "catalogStatus": "stub",
        })

        self.assertEqual(result["action"], "upgraded")
        self.assertEqual(result["uid"], created["uid"])


if __name__ == "__main__":
    unittest.main()
