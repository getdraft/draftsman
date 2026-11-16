import unittest
from framework.tools.uid_utils import derive_inline_relationships, generate_relationship_uid

class TestInlineRelationships(unittest.TestCase):
    def test_derived_relationship_interface_carrier(self):
        catalog = {
            "comp-1": {
                "uid": "comp-1", "type": "product_component", "name": "C", "runsOn": "host-1",
                "runtimeSpec": {"dependencies": [
                    {"ref": "service-2", "interface": "PostgreSQL wire protocol"},
                    {"ref": "service-3", "purpose": "Reads"},
                ]},
            },
            "service-2": {"uid": "service-2", "type": "runtime_service", "name": "S2"},
            "service-3": {"uid": "service-3", "type": "runtime_service", "name": "S3"},
            "host-1": {"uid": "host-1", "type": "host", "name": "H"},
        }
        derived = derive_inline_relationships(catalog)
        with_iface = derived[generate_relationship_uid("comp-1", "service-2")]
        self.assertEqual(with_iface["_interface"], "PostgreSQL wire protocol")
        self.assertEqual(with_iface["label"], "PostgreSQL wire protocol")
        without = derived[generate_relationship_uid("comp-1", "service-3")]
        self.assertIsNone(without["_interface"])
        self.assertEqual(without["label"], "Reads")
        runs_on = derived[generate_relationship_uid("comp-1", "host-1", suffix="runsOn")]
        self.assertNotIn("_interface", runs_on)

    def test_derive_inline_relationships(self):
        catalog = {
            "comp-1": {
                "uid": "comp-1",
                "type": "product_component",
                "name": "My Component",
                "runtimeSpec": {
                    "dependencies": [
                        {
                            "ref": "service-2",
                            "purpose": "Reads user profiles",
                            "interface": "gRPC"
                        }
                    ]
                }
            },
            "service-2": {
                "uid": "service-2",
                "type": "runtime_service",
                "name": "Target Service"
            }
        }
        
        derived = derive_inline_relationships(catalog)
        
        # Verify deterministic UID is used
        expected_uid = generate_relationship_uid("comp-1", "service-2")
        self.assertIn(expected_uid, derived)
        
        rel = derived[expected_uid]
        self.assertEqual(rel["schemaVersion"], "1.0")
        self.assertEqual(rel["type"], "relationship")
        self.assertEqual(rel["source"], "comp-1")
        self.assertEqual(rel["target"], "service-2")
        self.assertEqual(rel["name"], "My Component → Target Service")
        self.assertEqual(rel["label"], "gRPC")
        self.assertEqual(rel["notes"], "Reads user profiles")
        self.assertEqual(rel["catalogStatus"], "complete")

    def test_derive_inline_relationships_deduplication(self):
        catalog = {
            "comp-1": {
                "uid": "comp-1",
                "type": "product_component",
                "name": "My Component",
                "runsOn": "service-2",
                "runtimeSpec": {
                    "dependencies": [
                        {
                            "ref": "service-2",
                            "purpose": "Reads user profiles",
                            "interface": "gRPC"
                        }
                    ]
                }
            },
            "service-2": {
                "uid": "service-2",
                "type": "runtime_service",
                "name": "Target Service"
            },
            # Hand-authored relationship already exists
            "hand-authored-rel": {
                "uid": "hand-authored-rel",
                "type": "relationship",
                "source": "comp-1",
                "target": "service-2",
                "label": "hand-authored"
            }
        }
        
        derived = derive_inline_relationships(catalog)
        
        # Since a hand-authored relationship already exists, no derived relationship should be created for comp-1 -> service-2
        self.assertEqual(len(derived), 0)

        # Remove hand-authored relationship to test that only one derived is generated instead of two
        catalog.pop("hand-authored-rel")
        derived = derive_inline_relationships(catalog)
        self.assertEqual(len(derived), 1)

if __name__ == "__main__":
    unittest.main()
