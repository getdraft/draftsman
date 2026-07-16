## Unreleased

### Compatibility Impact

- None. Two browser-only fixes (diagram initial render race and business pillar grouping); no schema, validator, or CLI changes.

### Added

- Added a regression test asserting the SDP detail page's initial render is gated on `DOMContentLoaded` rather than called synchronously at the bottom of `draft-browser.js`.
- Added a regression test asserting `businessPillarForObject` in `framework/browser/draft-browser.js` checks `businessContext.pillar` before `businessContext.ownerNode`.

### Changed

- N/A

### Fixed

- Fixed a load-order race in the generated browser bundle where a direct or bookmarked Software Deployment Pattern detail URL could render without its scoped diagram section. `draft-browser.js` and `mermaid-config.js` both load with `defer` and execute in document order before `DOMContentLoaded` fires, but `draft-browser.js` called `applyRouteFromHash()` (the initial page render) synchronously at the bottom of the script — before `mermaid-config.js`, next in the defer queue, had installed `window.DraftDiagrams`. The initial render is now wrapped in `initialRender()` and gated on `DOMContentLoaded`. Closes #177.
- Fixed `businessPillarForObject` in `framework/browser/draft-browser.js` to prefer `businessContext.pillar` (the primary grouping key per `docs/workspaces.md`) over `businessContext.ownerNode`. Previously SDPs with both fields were grouped under the more specific owner node. `ownerNode` is now only used as a fallback when no pillar is declared. Closes #176.

### Migration Notes

- No manual migration required. Downstream company workspaces receive both fixes through a normal framework update.

## 0.63.2 - 2026-07-24

### Compatibility Impact

- None. Fixes a browser-only initial-render timing bug; no schema, validator, or CLI changes.

### Added

- Added a regression test asserting the SDP detail page's initial render is gated on `DOMContentLoaded` rather than called synchronously at the bottom of `draft-browser.js`.

### Fixed

- Fixed a load-order race in the generated browser bundle where a direct or bookmarked Software Deployment Pattern detail URL could render without its scoped diagram section. `draft-browser.js` and `mermaid-config.js` both load with `defer` and execute in document order before `DOMContentLoaded` fires, but `draft-browser.js` called `applyRouteFromHash()` (the initial page render) synchronously at the bottom of the script — before `mermaid-config.js`, next in the defer queue, had installed `window.DraftDiagrams`. The initial render (`initSidebarNav`, `initPalette`, `applyRouteFromHash`, and the background world-atlas warm-up) is now wrapped in `initialRender()` and gated on `DOMContentLoaded`, guaranteeing every deferred script has already run. Closes #177.

### Migration Notes

- No manual migration required. Downstream company workspaces receive the fix through a normal framework update.

## 0.63.1 - 2026-07-02

### Compatibility Impact

- None. Additive change to the generated browser bundle only.

