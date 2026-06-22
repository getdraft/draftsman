import unittest
from framework.tools.uid_utils import derive_inline_relationships, generate_relationship_uid

class TestInlineRelationships(unittest.TestCase):
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

if __name__ == "__main__":
    unittest.main()
