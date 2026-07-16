from __future__ import annotations

import unittest
from pathlib import Path

from draft_table.web import INDEX_HTML
from framework.tools.generate_browser import BROWSER_STATIC_ASSET_NAMES


BROWSER_JS = (Path(__file__).resolve().parents[1] / "framework" / "browser" / "draft-browser.js").read_text(encoding="utf-8")
MERMAID_CONFIG_JS = (Path(__file__).resolve().parents[1] / "framework" / "browser" / "mermaid-config.js").read_text(encoding="utf-8")
INDEX_TEMPLATE_HTML = (Path(__file__).resolve().parents[1] / "framework" / "browser" / "index.template.html").read_text(encoding="utf-8")


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
    def test_browser_resolves_relationship_and_alias_refs(self) -> None:
        self.assertIn("const objectAliasLookup", BROWSER_JS)
        self.assertIn("function relationshipResolutionForImplementation", BROWSER_JS)
        self.assertIn("rel.targetUid, rel.targetName, rel.name, rel.label", BROWSER_JS)
        self.assertIn("resolveImplementationReference(object, implementation)", BROWSER_JS)

    def test_sdp_internal_interactions_link_to_service_groups(self) -> None:
        self.assertIn("function findSdpServiceGroup", BROWSER_JS)
        self.assertIn("data-service-group-link", BROWSER_JS)
        self.assertIn("data-service-group-name", BROWSER_JS)
        self.assertIn("scrollIntoView({ behavior: 'smooth', block: 'start' })", BROWSER_JS)
    def test_browser_uses_generated_catalog_indexes(self) -> None:
        self.assertIn("const catalogIndexes = browserData.indexes || {}", BROWSER_JS)
        self.assertIn("catalogIndexes.domainCapability?.domains", BROWSER_JS)
        self.assertIn("catalogIndexes.requirementImplementations?.rows", BROWSER_JS)

    def test_browser_resolves_requirement_group_inheritance_lists(self) -> None:
        self.assertIn("function requirementGroupParentIds(group)", BROWSER_JS)
        self.assertIn("Array.isArray(inherits)", BROWSER_JS)
        self.assertIn("flatMap(parentId => resolvedRequirementsForGroup(parentId, stack))", BROWSER_JS)

    def test_sdp_detail_page_embeds_scoped_diagram(self) -> None:
        self.assertIn("function _sdpDiagramsMarkup(vm)", BROWSER_JS)
        self.assertIn("window.DraftDiagrams.buildSdpDiagram(object)", BROWSER_JS)
        self.assertIn("id: 'sdp-s-diagrams',    label: 'Diagrams', skip: !vm.diagram", BROWSER_JS)
        self.assertIn("window.DraftDiagrams.renderDiagramsIntoSlots([vm.diagram], vm.diagramRenderId)", BROWSER_JS)

    def test_sdp_diagram_initial_render_waits_for_dom_content_loaded(self) -> None:
        # Regression: draft-browser.js called applyRouteFromHash() (the initial
        # page render) synchronously at the bottom of the script. Both this
        # script and mermaid-config.js load with `defer`, so they execute in
        # document order before DOMContentLoaded fires — but a synchronous call
        # here ran before mermaid-config.js (next in the defer queue) had
        # installed window.DraftDiagrams, so a direct/bookmarked SDP detail URL
        # would render with the scoped diagram section silently skipped.
        # Gating the initial render on DOMContentLoaded guarantees every
        # deferred script has already run first.
        self.assertIn("function initialRender() {", BROWSER_JS)
        self.assertIn("document.addEventListener('DOMContentLoaded', initialRender)", BROWSER_JS)
        initial_render_pos = BROWSER_JS.index("function initialRender() {")
        dom_gate_pos = BROWSER_JS.index("document.addEventListener('DOMContentLoaded', initialRender)")
        self.assertGreater(
            dom_gate_pos, initial_render_pos,
            "the DOMContentLoaded gate must come after initialRender is defined",
        )
        # There must be no bare top-level applyRouteFromHash() call outside of
        # initialRender()/the hashchange listener that would reintroduce the race.
        top_level_calls = BROWSER_JS.count("\napplyRouteFromHash();")
        self.assertEqual(
            top_level_calls, 0,
            "applyRouteFromHash() must only run inside initialRender(), gated on "
            "DOMContentLoaded, not as a bare top-level statement",
        )

    def test_mermaid_config_patches_max_text_size_and_exposes_sdp_api(self) -> None:
        # Generated C4/flowchart diagrams for catalogs with many deployable
        # objects were exceeding Mermaid's 50 KB default text-size limit.
        self.assertIn("maxTextSize: safeConfig.maxTextSize ?? MERMAID_MAX_TEXT_SIZE", MERMAID_CONFIG_JS)
        self.assertIn("function buildSdpDiagram(sdp)", MERMAID_CONFIG_JS)
        self.assertIn("window.DraftDiagrams = {", MERMAID_CONFIG_JS)
        self.assertIn("renderDiagramsIntoSlots", MERMAID_CONFIG_JS)

    def test_index_template_loads_mermaid_config_after_browser_bundle(self) -> None:
        browser_pos = INDEX_TEMPLATE_HTML.index('<script defer src="assets/draft-browser.js"></script>')
        mermaid_config_pos = INDEX_TEMPLATE_HTML.index('<script defer src="assets/mermaid-config.js"></script>')
        self.assertGreater(
            mermaid_config_pos, browser_pos,
            "mermaid-config.js must load after draft-browser.js so its mermaid.initialize patch applies "
            "before any view calls mermaid.initialize.",
        )

    def test_generator_copies_mermaid_config_as_a_shell_asset(self) -> None:
        # Regression: mermaid-config.js was added directly under framework/browser/
        # without being added to the generator's static-asset list, so a fresh
        # install or --refresh-shell run would never copy it and the script tag
        # added in index.template.html would 404.
        self.assertIn("mermaid-config.js", BROWSER_STATIC_ASSET_NAMES)


if __name__ == "__main__":
    unittest.main()
