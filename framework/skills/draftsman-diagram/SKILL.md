---
name: draftsman-diagram
description: Use when someone wants to see or change a DRAFT deployment-pattern diagram, fix the catalog objects behind it, record a box order, or get Mermaid or C4 text. Needs the Author profile from draftsman-core.
---

# Draftsman Diagram

Load `draftsman-core` first. This skill needs the **Author profile** for anything that edits the catalog or runs a command. With only the Query profile, send the link to the published page and describe the architecture in words.

Nothing here requires an AI session to produce a diagram. The published site already carries them; this skill explains how to read them and how to change the objects behind them.

## Send people to the published page first

The browser generator (`generate_browser.py`) renders one diagram page per deployment pattern into `docs/diagrams/` beside the browser. Each pattern's entry in the browser has a `Diagrams` link, and each page links back to the browser. Give the user that page, not a fresh render and not a drawing. Run the standalone generator only for an unpublished draft or a pattern not yet in the published catalog.

The generator is the only path for the two views (`framework/tools/generate_diagram.py`, the same code the browser generator runs). Hand-drawn SVG is forbidden for the logical or deployment view, including quick sketches and edits to a generated file; hand layouts differ between runs and cannot be tested.

## How to read the page

- **Connections are hidden** until a box is hovered, focused or pinned (click a box; the same uid is highlighted in both figures). Then only that box's connections show.
- **Colours.** Purple lines are calls the box makes (outbound); orange lines are calls it receives (inbound). Small dots move along each line toward the arrowhead (off under reduced motion). Dashed lines are asynchronous, dotted are event flows.
- **Show all connections.** A checkbox under each figure restores the full drawing.
- **Labels** show with their line, at the end farthest from the selected box, inside that box's width. Each is two lines (the label, then its technology), each clipped to the box width. The full text is in the tooltip and in the callout shown when a single line is hovered.
- **Logical application diagram.** Components and data components in bands: presentation, application, data, utility. Infrastructure is not drawn here.
- **Deployment pattern diagram.** Deployment target, then service group container (captioned by its substrate), then network-zone lane, then component box. Placed infrastructure (network, runtime, host, AI gateway, data store services) appears only here. Each data component sits inside a container named for the data store service in its `runsOn`; that store has no box of its own unless it hosts no data component. `data store not recorded` means `runsOn` is absent or unresolved.
- **External interactions lane.** The right-hand lane holds dependencies of the pattern that it does not place, captioned with the pattern that places them, `external` for an `externalTarget` string, or `not placed in any pattern`. It shows dependencies only: consumers that merely call into the pattern are not drawn, and neither is any line between two outside objects.
- **Dashed border.** A box with a dashed border has a derived tier (no recorded `diagramTier`); a dashed container has an inferred substrate. Say so; it is not recorded.
- **Recorded conflicts section** appears only when a placed component's `runsOn` names something other than its group's substrate. Both values are shown and nothing is resolved. Quote both and ask which is right.
- **Relationships table.** `Source` reads `relationship object` or `inline dependency`. Placement (`runsOn`, `host`) is never an edge.

## Model rules behind the picture

A pattern owns application components and data components. Service definitions (data stores, runtimes, hosts, load balancers) are deployed through `substrate` on a service group and `runsOn` on a data component, and appear only in the deployment view. External services (Okta, Secrets Manager, SaaS) are External interactions reached by relationships.

1. **Document, do not infer (R1, R3).** Boxes and lines come from recorded catalog data. No relationship means no line. Never add one because it seems likely.
2. **Show gaps.** Retired and deprecated objects stay, styled as such; a missing label, technology or tier shows as not recorded.
3. **Report conflicts, do not resolve them.** Quote both recorded values and let the user choose.
4. **Use the user's scope.** With several patterns and none named, run `--list` and ask.

## Fixing the objects behind a picture

When a diagram looks wrong, the fix is a catalog change, then a pull request, never an edit to the page.

- **Wrong band:** set the right `diagramTier` on the deployable object entry in the pattern.
- **Missing data component:** add the `data_component` to the pattern's service group with `runsOn` naming its data store service.
- **A standard placed as a deployable object:** a service definition listed in `deployableObjects` belongs in `substrate` (service group) or `runsOn` (data component). Move it; do not draw it as a component.
- **A relationship recorded on a definition:** relationships sourced by a placed definition that point to objects in other patterns are not drawn here. Record the relationship on the application component that really makes the call.
- **Wrong placement:** `duplicate placement` and `undeclared network zone` warnings mean the pattern entry needs correcting.
- Validate with `python3 framework/tools/validate.py`, then open the pull request. A `baseline:` warning is a known violation on an unchanged object; one on an object you changed is an error to fix. Do not run `validate.py --write-baseline` to silence a violation in an object you are editing.

## Recording a box order

People can reorder boxes within their band or zone lane; the order is a `diagram_layout` object beside the pattern file (schema `framework/schemas/diagram-layout.schema.yaml`), and every render honours it. Tiers and zones stay catalog facts.

1. Render the editable local page (never published, never used by workflows):
   `python3 framework/tools/generate_diagram.py --sdp "<name, alias or uid>" --editable --output FILE`
2. Drag boxes, or focus one and press Alt with an arrow key, within its own band, zone lane or data store container; ordinals renumber per container. Reloading discards changes.
3. Choose `Export layout` and save the YAML it shows to a file. Its `uid` is `NEW` when no layout existed.
4. Write it: `python3 framework/tools/generate_diagram.py --sdp "<uid>" --write-layout --layout-from FILE`. `--layout-from` requires `--write-layout`. An existing uid is kept, a new layout gets a fresh uid, and every `ref` must be a drawn node.
5. Run `python3 framework/tools/validate.py`, then open the pull request. The published page picks the order up on the next browser build.

`--write-layout` without `--layout-from` writes the layout from the current drawn order. It cannot combine with `--placed-only`. More than one layout for a pattern warns, and the lowest uid wins.

## Standalone generator (unpublished drafts only)

```bash
python3 framework/tools/generate_diagram.py --list [--workspace PATH]
python3 framework/tools/generate_diagram.py --sdp "<name, alias or uid>" [--workspace PATH] [--output FILE] [--placed-only] [--svg-dir DIR]
python3 framework/tools/generate_diagram.py --all --output-dir DIR [--svg-dir DIR] [--workspace PATH]
```

In a vendored workspace use `.draft/framework/tools/generate_diagram.py` with `--workspace` set to the workspace root. `--sdp` is optional when there is one pattern; an ambiguous selector is an error, so use `--list`. Exit 0 means rendered, 1 means a pattern failed or none exist, 2 means a usage error or no `catalog/`. Without `--output` the page is `<pattern-name>-architecture.html`. Give the user the file path to open, or publish it if your harness can. Scope is placed objects plus what they depend on; `--placed-only` keeps only placed objects.

## Warnings to read back

The generator prints `N warnings`, then each distinct warning once. Repeat the ones that matter:

- `derived tier: <name> (<uid>) -> <tier>`: ask whether to record `diagramTier`.
- `conflict: <component> runsOn <X>; group substrate is <Y>`: see Recorded conflicts.
- `substrate also listed as deployable object`, `unknown substrate uid`, `substrate ... has type ...`: the substrate is recorded inconsistently.
- `data store not recorded: <name> (<uid>) ...`: ask which store the data component runs on.
- `duplicate placement`, `undeclared network zone`, `unknown flow`: correct the entry.
- `multiple diagram layouts for <sdp>`, `layout position for undrawn object <ref>`: remove the stale layout or entry.

## Mermaid and C4 text

For a conversational answer, embeddable text, or a sequence or component view of one object, write text from `references/mermaid.md`. It is outside the determinism guarantee and is never a diagram of record.
