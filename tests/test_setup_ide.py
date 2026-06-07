from __future__ import annotations

import importlib.util
import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

# Dynamically import setup_ide.py from framework/tools/setup_ide.py
spec = importlib.util.spec_from_file_location("setup_ide", "framework/tools/setup_ide.py")
setup_ide_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup_ide_mod)


class SetupIdeTests(unittest.TestCase):
    def test_copilot_setup_detection(self) -> None:
        with TemporaryDirectory() as directory:
            cwd_path = Path(directory)
            
            # Create a mock upstream framework repo structure so it detects it
            (cwd_path / "framework").mkdir(parents=True, exist_ok=True)
            (cwd_path / "draft-framework.yaml").write_text("version: 0.1.0", encoding="utf-8")
            (cwd_path / "framework" / "commands").mkdir(parents=True, exist_ok=True)
            (cwd_path / "framework" / "commands" / "draft.md").write_text("Claude instructions", encoding="utf-8")
            
            # Setup a pre-existing copilot file that merely mentions "Draftsman" but lacks "/draft"
            copilot_dir = cwd_path / ".github"
            copilot_dir.mkdir(parents=True, exist_ok=True)
            copilot_file = copilot_dir / "copilot-instructions.md"
            copilot_file.write_text("This repo uses Draftsman.\n", encoding="utf-8")
            
            # Mock Path.cwd() to point to our temp directory
            with mock.patch("pathlib.Path.cwd", return_value=cwd_path):
                # Redirect stdout to suppress print statements
                with mock.patch("sys.stdout", new_callable=StringIO):
                    setup_ide_mod.setup_ide()
            
            # Check that the copilot block was appended
            content = copilot_file.read_text(encoding="utf-8")
            self.assertIn("This repo uses Draftsman.", content)
            self.assertIn("/draft", content)
            
            # Running it again should be idempotent and not append it a second time
            with mock.patch("pathlib.Path.cwd", return_value=cwd_path):
                with mock.patch("sys.stdout", new_callable=StringIO):
                    setup_ide_mod.setup_ide()
            
            content_after = copilot_file.read_text(encoding="utf-8")
            # The file should remain identical (idempotence check)
            self.assertEqual(content_after, content)


if __name__ == "__main__":
    unittest.main()
