from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


class ImportAsvsTests(unittest.TestCase):
    def test_import_asvs_generates_provider_pack_groups(self) -> None:
        fixture = {
            "requirements": [
                {
                    "chapterNr": 2,
                    "nr": "1",
                    "title": {"en": "Verify authentication is required."},
                    "levels": [1, 2, 3],
                },
                {
                    "chapterNr": 4,
                    "nr": "2",
                    "title": {"en": "Verify access control is enforced."},
                    "levels": [2, 3],
                },
                {
                    "chapterNr": 8,
                    "nr": "3",
                    "title": {"en": "Verify audit events are logged."},
                    "levels": [3],
                },
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "asvs.json"
            output_dir = tmp / "providers" / "owasp-asvs" / "configurations" / "requirement-groups"
            source.write_text(json.dumps(fixture), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "framework" / "tools" / "import_asvs.py"),
                    "--source",
                    str(source),
                    "--output-dir",
                    str(output_dir),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            l1 = yaml.safe_load((output_dir / "requirement-group-owasp-asvs-l1.yaml").read_text(encoding="utf-8"))
            l2 = yaml.safe_load((output_dir / "requirement-group-owasp-asvs-l2.yaml").read_text(encoding="utf-8"))
            l3 = yaml.safe_load((output_dir / "requirement-group-owasp-asvs-l3.yaml").read_text(encoding="utf-8"))

        self.assertEqual(l1["provider"]["id"], "provider.owasp-asvs")
        self.assertEqual(l1["provider"]["type"], "third-party")
        self.assertEqual(l2["inherits"], ["01KQQ4Q027-ASV1"])
        self.assertEqual(l3["inherits"], ["01KQQ4Q027-ASV2"])
        self.assertEqual(l1["requirements"][0]["relatedCapability"], "01KQQ4Q026-MHJM")
        self.assertEqual(l2["requirements"][0]["relatedCapability"], "01KQQ4Q026-4JR6")
        self.assertEqual(l3["requirements"][0]["relatedCapability"], "01KQQ4Q026-D04B")


if __name__ == "__main__":
    unittest.main()
