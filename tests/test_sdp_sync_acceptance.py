"""#195 S2.1: the receiver accepts content only from the registered repository, for the product's own objects."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "framework" / "tools"))

import sdp_sync  # noqa: E402
from tests import sdp_sync_identity as identity  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "sdp_sync"
REPOSITORY = "example-org/absence-service"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
SDP = (FIXTURES / "product_repo" / ".draft" / "sdp.yaml").read_text(encoding="utf-8")


def obj(**fields: object) -> str:
    return yaml.safe_dump({"schemaVersion": "1.0", **fields}, sort_keys=False)


class Central:
    def __init__(self, test: unittest.TestCase) -> None:
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "central"
        shutil.copytree(FIXTURES / "central_workspace", self.root)

    def write(self, rel_path: str, text: str) -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def receive(self, files: dict[str, str] | None = None, repository: str = REPOSITORY, action: str = "upsert") -> sdp_sync.Result:
        payload = {"format": sdp_sync.PAYLOAD_FORMAT, "repository": repository, "commit": COMMIT, "ref": "refs/heads/main",
                   "action": action, "correlationId": "run-1",
                   "files": ({".draft/sdp.yaml": SDP} if files is None else files) if action == "upsert" else {}}
        return identity.receive(self.root, payload)


class RegistrationTests(unittest.TestCase):
    def test_the_registered_repository_is_accepted(self) -> None:
        result = Central(self).receive()
        self.assertEqual((result.status, result.registration), ("accepted", "01M7SYNC03-PR01"), result.message)

    def test_repository_names_compare_case_insensitively(self) -> None:
        self.assertEqual(Central(self).receive(repository="Example-Org/Absence-Service").status, "accepted")

    def test_url_forms_normalize(self) -> None:
        for url in ("https://github.com/example-org/absence-service", "https://github.com/Example-Org/absence-service.git",
                    "https://www.github.com/example-org/absence-service/", "git@github.com:example-org/absence-service.git",
                    "ssh://git@github.com/example-org/absence-service"):
            with self.subTest(url):
                self.assertEqual(sdp_sync.normalize_github_url(url), REPOSITORY)
        for url in ("https://gitlab.com/example-org/absence-service", "https://github.com/example-org", "absence-service", None):
            with self.subTest(url):
                self.assertIsNone(sdp_sync.normalize_github_url(url))

    def test_an_unregistered_repository_is_rejected_and_nothing_is_written(self) -> None:
        central = Central(self)
        result = central.receive(repository="example-org/payroll-service")
        self.assertEqual(result.status, "rejected")
        self.assertIn("no ProductRegistration in catalog/ has repository.url https://github.com/example-org/payroll-service", result.message)
        self.assertFalse((central.root / ".draft" / "external_sdps").exists())

    def test_an_unregistered_repository_cannot_delete_another_products_cache(self) -> None:
        central = Central(self)
        self.assertEqual(central.receive().status, "accepted")
        self.assertEqual(central.receive(repository="example-org/absence-service-fork", action="delete").status, "rejected")
        self.assertTrue((central.root / ".draft" / "external_sdps" / "example-org__absence-service" / "sdp.yaml").exists())

    def test_two_registrations_for_one_repository_are_rejected(self) -> None:
        central = Central(self)
        reg = yaml.safe_load((FIXTURES / "central_workspace" / "catalog" / "engineering" / "product-registrations" /
                              "product-reg-absence-service.yaml").read_text(encoding="utf-8"))
        central.write("catalog/engineering/product-registrations/dup.yaml", yaml.safe_dump({**reg, "uid": "01M7SYNC03-PR02"}))
        result = central.receive()
        self.assertEqual(result.status, "rejected")
        self.assertIn("several ProductRegistrations", result.message)
        self.assertIn("01M7SYNC03-PR01, 01M7SYNC03-PR02", result.message)

    def test_a_registration_on_another_provider_does_not_match(self) -> None:
        central = Central(self)
        path = central.root / "catalog" / "engineering" / "product-registrations" / "product-reg-absence-service.yaml"
        reg = yaml.safe_load(path.read_text(encoding="utf-8"))
        reg["repository"]["provider"] = "gitlab"
        path.write_text(yaml.safe_dump(reg), encoding="utf-8")
        self.assertEqual(central.receive().status, "rejected")

    def test_registrations_in_a_product_cache_do_not_count(self) -> None:
        central = Central(self)
        central.write(".draft/external_sdps/x/reg.yaml", obj(uid="01M7SYNC03-PR09", type="product_registration", name="x",
                                                           repository={"provider": "github", "url": "https://github.com/example-org/sneaky"}))
        self.assertIn("no ProductRegistration", central.receive(repository="example-org/sneaky").message)


class OwnershipTests(unittest.TestCase):
    COMPONENT = obj(uid="01M7SYNC04-PC02", type="product_component", name="Absence Worker", repoUrl="https://github.com/example-org/absence-service",
                    owner={"team": "absence"}, classification="worker", catalogStatus="stub")

    def reject(self, files: dict[str, str], expected: str, central: Central | None = None) -> None:
        central = central or Central(self)
        result = central.receive({".draft/sdp.yaml": SDP, **files})
        self.assertEqual(result.status, "rejected", files)
        self.assertIn(expected, result.message)
        self.assertFalse((central.root / ".draft" / "external_sdps" / "example-org__absence-service").exists())

    def test_product_owned_types_are_accepted(self) -> None:
        files = {
            ".draft/catalog/worker.yaml": self.COMPONENT,
            ".draft/catalog/worker-listener.yaml": obj(uid="01M7SYNC05-LS02", type="listener", name="Worker queue",
                                                       owner={"kind": "product_component", "ref": "01M7SYNC04-PC02"},
                                                       protocol="AMQP", port=5672, endpoint="/", authenticationModel="iam", catalogStatus="stub"),
            ".draft/catalog/worker-calls-api.yaml": obj(uid="01M7SYNC06-RS01", type="relationship", name="Worker → API",
                                                        source="01M7SYNC04-PC02", target="01M7SYNC02-PC01", label="calls", catalogStatus="stub"),
        }
        result = Central(self).receive({".draft/sdp.yaml": SDP, **files})
        self.assertEqual(result.status, "accepted", result.message)
        self.assertEqual(len(result.written), 4)

    def test_central_types_are_refused(self) -> None:
        for kind in ("system", "runtime_service", "host", "product_registration", "requirement_group", "reference_architecture"):
            with self.subTest(kind):
                self.reject({".draft/catalog/x.yaml": obj(uid="01M7SYNC07-XX01", type=kind, name="x")},
                            f"cannot sync a '{kind}' object")

    def test_a_uid_owned_by_the_central_catalog_is_refused(self) -> None:
        # The fixture's central catalog owns the Absence API component.
        self.reject({".draft/catalog/api.yaml": obj(uid="01M7SYNC02-PC01", type="product_component", name="Absence API (hijack)")},
                    "uid 01M7SYNC02-PC01 is already owned by the central catalog")

    def test_a_uid_owned_by_another_product_is_refused(self) -> None:
        central = Central(self)
        central.write(".draft/external_sdps/example-org__payroll-service/catalog/pay.yaml",
                      obj(uid="01M7SYNC08-PC03", type="product_component", name="Payroll"))
        central.write(".draft/external_sdps/example-org_leave-service.yaml", obj(uid="01M7SYNC09-SDP2", type="software_deployment_pattern", name="Leave"))
        self.reject({".draft/catalog/pay.yaml": obj(uid="01M7SYNC08-PC03", type="product_component", name="Payroll")},
                    "already owned by another product (example-org__payroll-service)", central)
        leave_sdp = SDP.replace("01M7SYNC01-SDP1", "01M7SYNC09-SDP2")
        result = central.receive({".draft/sdp.yaml": leave_sdp})
        self.assertEqual(result.status, "rejected")
        self.assertIn("another product (example-org_leave-service)", result.message)

    def test_the_products_own_previous_snapshot_does_not_block_a_resync(self) -> None:
        central = Central(self)
        files = {".draft/sdp.yaml": SDP, ".draft/catalog/worker.yaml": self.COMPONENT}
        self.assertEqual(central.receive(files).status, "accepted")
        central.write(".draft/external_sdps/example-org_absence-service.yaml", SDP)  # its own legacy flat file
        self.assertEqual(central.receive(files).status, "accepted")

    def test_duplicate_and_missing_uids_are_refused(self) -> None:
        self.reject({".draft/catalog/a.yaml": self.COMPONENT, ".draft/catalog/b.yaml": self.COMPONENT}, "is also used by")
        self.reject({".draft/catalog/a.yaml": obj(type="product_component", name="no uid")}, "needs a uid")

    def test_objects_may_only_speak_for_the_products_own_objects(self) -> None:
        self.reject({".draft/catalog/r.yaml": obj(uid="01M7SYNC0A-RS02", type="relationship", name="x", source="01M7SYNC02-PC01",
                                                  target="01M7SYNC02-PC01", label="calls")},
                    "source 01M7SYNC02-PC01 is not an object this product syncs")
        self.reject({".draft/catalog/l.yaml": obj(uid="01M7SYNC0B-LS03", type="listener", name="x",
                                                  owner={"kind": "product_component", "ref": "01M7SYNC02-PC01"})},
                    "owner.ref 01M7SYNC02-PC01 is not an object this product syncs")
        self.reject({".draft/catalog/d.yaml": obj(uid="01M7SYNC0C-DR01", type="decision_record", name="x", linkedObject="01M7SYNC02-PC01")},
                    "linkedObject 01M7SYNC02-PC01 is not an object this product syncs")


if __name__ == "__main__":
    unittest.main()
