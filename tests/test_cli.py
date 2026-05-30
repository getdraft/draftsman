from __future__ import annotations

import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest import mock

from draft_table.cli import build_parser, find_available_port, server_urls


class CliTests(unittest.TestCase):
    def test_cli_defines_required_commands(self) -> None:
        parser = build_parser()

        for command in ("onboard", "serve", "validate", "chat", "ai", "repo", "framework", "commit", "doctor"):
            with self.subTest(command=command):
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    with self.assertRaises(SystemExit) as context:
                        parser.parse_args([command, "--help"])
                self.assertEqual(context.exception.code, 0)

    def test_cli_rejects_one_shot_ask_command(self) -> None:
        parser = build_parser()

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as context:
                parser.parse_args(["ask", "What is a TechnologyComponent?"])

        self.assertNotEqual(context.exception.code, 0)

    def test_serve_defaults_to_lan_binding(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["serve"])

        self.assertEqual(args.host, "0.0.0.0")

    def test_server_urls_show_lan_and_local_urls_for_lan_binding(self) -> None:
        with mock.patch("draft_table.cli.local_lan_address", return_value="192.168.1.20"):
            urls = server_urls("0.0.0.0", 8765)

        self.assertEqual(
            urls,
            [
                ("LAN URL", "http://192.168.1.20:8765"),
                ("Local URL", "http://127.0.0.1:8765"),
            ],
        )

    def test_find_available_port_returns_port_number(self) -> None:
        fake_socket = mock.MagicMock()
        fake_socket.__enter__.return_value.getsockname.return_value = ("127.0.0.1", 5000)
        with mock.patch("socket.socket", return_value=fake_socket):
            port = find_available_port()

        self.assertEqual(port, 5000)


if __name__ == "__main__":
    unittest.main()
