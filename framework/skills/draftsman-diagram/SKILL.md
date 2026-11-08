---
name: draftsman-diagram
description: Use when someone wants to see a DRAFT architecture as a diagram, either a rendered shareable deployment-pattern page or Mermaid and C4 text for a catalog object. Needs the Author profile from draftsman-core.
---

# Draftsman Diagram

Load `draftsman-core` first. This skill needs the **Author profile**: read the catalog, run a local command and write an output file. If you only have the Query profile, say so and describe the architecture in words; do not hand-draw a diagram from memory.

## Choose the output

- The user wants to *see* the architecture, cannot follow text, or wants a page to open, refresh and share: render a **diagram page** (below).
- The user wants text to embed in Markdown or a wiki, or asks for a sequence or component view: write **Mermaid or C4** from `references/mermaid.md`.

## Rendered diagram page

Use the deterministic generator. Do not hand-draw the SVG: hand-drawn layouts differ from run to run and cannot be tested.

```bash
python3 framework/tools/generate_diagram.py --list [--workspace PATH]
python3 framework/tools/generate_diagram.py --sdp "<name, alias or uid>" [--workspace PATH] [--output FILE] [--placed-only]
```

When the framework is vendored into a workspace, run `.draft/framework/tools/generate_diagram.py` with the workspace root as `--workspace`.

Scope: by default the page covers every object owned by the same team as the pattern, plus anything the pattern places. `--placed-only` limits it to objects placed in a service group. Without `--output` the file is `<pattern-name>-architecture.html` in the current directory, and an existing file is overwritten (the command says so). `--sdp` is optional when the workspace has one pattern. Exit code 2 means there is no `catalog/` under the workspace; 1 means no pattern matched or the file could not be written.

The page is one self-contained HTML file with an inline SVG, light and dark themes and no external requests. It has: deployment topology, recorded relationships, recorded characteristics, open Drafting Session questions that target the pattern, and a filterable object inventory.

## Rules

1. **Document, do not infer (R1, R3).** Zones are `serviceGroups`, labelled with their recorded `deploymentTarget`. Boxes are the objects in scope (placed ones inside their zone). Arrows are `relationship` objects (including inline ones such as `runsOn`) and nothing else. An object with no recorded relationship has no arrow. Never add a box or arrow because it seems likely.
2. **Show gaps instead of hiding them.** Objects with a relationship but no service group are drawn in a "Not placed in a service group" zone. Retired and deprecated objects stay on the page, styled as such. A missing target or label is shown as not recorded.
3. **Report conflicts, do not resolve them.** If two recorded fields disagree (a description names one host, `runsOn` another), say so in your reply, quote both values and do not pick one.
4. **Use the user's scope.** If several deployment patterns exist, run `--list` and ask which one. An ambiguous `--sdp` selector is an error; pass the uid.
5. **Check the result.** Confirm the reported relationship count is what you expect and read every `warning:` line (unknown uids, duplicate or malformed service groups) back to the user.

## Delivering the page

- If your harness can publish a page or file for the user, publish the generated HTML so they get a link, and republish to the same place after each regeneration.
- Otherwise give the user the output file path and tell them to open it in a browser.
- Hovering or focusing a box highlights its relationships and clicking pins the highlight. Mention this when the diagram has more than a few arrows: edge labels stay hidden until a box is selected once there are more than eight.
- Offer the Mermaid or C4 text only when the user wants something to embed.
