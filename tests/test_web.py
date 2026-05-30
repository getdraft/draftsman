from __future__ import annotations

import unittest

from draft_table.web import INDEX_HTML


class WebTests(unittest.TestCase):
    def test_chat_ui_replaces_thinking_on_errors(self) -> None:
        self.assertIn("replaceLastDraftsmanMessage", INDEX_HTML)
        self.assertIn("The Draftsman request failed", INDEX_HTML)
        self.assertIn("readJson(response)", INDEX_HTML)

    def test_ui_includes_draft_logo(self) -> None:
        self.assertIn('src="/assets/draftlogo.png"', INDEX_HTML)
        self.assertIn("brand-logo", INDEX_HTML)

    def test_chat_enter_sends_message(self) -> None:
        self.assertIn("event.key === 'Enter' && !event.shiftKey", INDEX_HTML)
        self.assertIn("event.preventDefault()", INDEX_HTML)
        self.assertIn("sendMessage()", INDEX_HTML)

    def test_ui_includes_configuration_commands(self) -> None:
        self.assertIn("draft-table onboard", INDEX_HTML)
        self.assertIn("draft-table ai doctor", INDEX_HTML)
        self.assertIn("draft-table framework refresh", INDEX_HTML)

    def test_ui_includes_new_user_guide(self) -> None:
        self.assertIn('data-side-tab="guide"', INDEX_HTML)
        self.assertIn("What DRAFT Is", INDEX_HTML)
        self.assertIn("How To Navigate", INDEX_HTML)
        self.assertIn("How Content Gets Updated", INDEX_HTML)
        self.assertIn("TechnologyComponent", INDEX_HTML)
        self.assertIn("SoftwareDeploymentPattern", INDEX_HTML)


if __name__ == "__main__":
    unittest.main()
