---
name: draftsman-diagram
description: Use when someone wants to see a DRAFT architecture as a diagram, either a rendered shareable deployment-pattern page or Mermaid and C4 text for a catalog object. Needs the Author profile from draftsman-core.
---

# Draftsman Diagram

Load `draftsman-core` first. This skill needs the **Author profile**: read the catalog, run a local command and write an output file. If you only have the Query profile, say so and describe the architecture in words.

## Choose the output

- The user wants to *see* a deployment pattern, cannot follow text, or wants a page to open, refresh and share: render the **diagram page** with the generator (below). It carries two views: the **logical application diagram** and the **deployment pattern diagram**.
- The user wants text to embed in Markdown or a wiki, or asks for a sequence or component view of one object: write **Mermaid or C4** text from `references/mermaid.md`. That text is an option, not a diagram of record; it is outside the determinism guarantee.

## The generator is the only path for the two views

Both views come from `framework/tools/generate_diagram.py`. Run it; do not write the SVG or HTML yourself.

- **Hand-drawn SVG is forbidden** for the logical and deployment views, including "a quick sketch", edits to a generated SVG, and layouts drawn from memory. Hand layouts differ between runs and cannot be tested.
- If the generator cannot run (Query profile, no Python), say so and describe the architecture in words. Do not substitute a drawing.

```bash
python3 framework/tools/generate_diagram.py --list [--workspace PATH]
python3 framework/tools/generate_diagram.py --sdp "<name, alias or uid>" [--workspace PATH] [--output FILE] [--placed-only] [--svg-dir DIR]
python3 framework/tools/generate_diagram.py --all --output-dir DIR [--svg-dir DIR] [--workspace PATH]
```

When the framework is vendored into a workspace, run `.draft/framework/tools/generate_diagram.py` with the workspace root as `--workspace`.

- `--sdp` is optional when the workspace has one pattern. An ambiguous selector is an error: run `--list` and pass the uid.
- Without `--output` the page is `<pattern-name>-architecture.html` in the current directory; an existing file is overwritten and the command says so.
- `--svg-dir` writes `<slug>-logical.svg` and `<slug>-deployment.svg` for the two figures. Only use these as files for the user to open or publish.
- `--all --output-dir` renders every pattern. Exit code 0 means all rendered; 1 means at least one pattern failed or none exist; 2 means a usage error or no `catalog/` under the workspace.

Scope is the pattern's placed objects plus the objects they depend on (a placed object is the source of the relationship). A relationship sourced by a placed infrastructure object is kept only when its target is also placed in this pattern; one shared load balancer carries every product's relationships, and the others belong to those pages. Objects that only call into the pattern, and relationships between two unplaced objects, are not drawn. `--placed-only` keeps only placed objects; the counts line then reports how many recorded relationships lead outside the placed set and are not drawn.

## Reading the page

- **Logical application diagram.** Components and data components, in bands top to bottom: presentation, application, data, utility. Placed infrastructure (network, runtime, host, AI gateway and data store services) is not drawn here; it is in the deployment diagram, and its relationships stay in the table. Every edge is a recorded relationship object or a recorded `runtimeSpec.dependencies` entry.
- **Dashed derived-tier convention.** A placed object without a `diagramTier` is drawn in the band its `type` implies, with a **dashed border** and a `derived tier:` warning. Tell the user the tier is derived, not recorded. A dashed border on a derived container (a service group whose substrate was inferred) means the same thing.
- **External interactions lane.** The right-hand lane holds dependencies of the pattern not placed in it, captioned with the pattern that places them (or `placed in N other patterns`, `not placed in any pattern`, or `external` for `externalTarget` nodes). Solid borders there mean the object is recorded; nothing in the lane is a pattern member.
- **Deployment pattern diagram.** Deployment target, then service group container, then network-zone lane, then component box. Infrastructure appears here as boxes. A substrate appears as the container, not a box. Each data component sits inside a container named for the data store service in its `runsOn`; data components of one group on one store share a container, and that store has no box of its own. `data store not recorded` means `runsOn` is absent or names no data store service. A store with no data components stays a box. Its caption is the recorded `substrate`, or `derived` when every placed component's `runsOn` agrees; `substrate not recorded` means neither exists.
- **Recorded conflicts section.** Appears only when a placed component's `runsOn` names an object other than its group's substrate. The generator shows both and resolves nothing. Quote both values to the user and ask which is right; do not pick one.
- **Relationships table.** A `Source` column reads `relationship object` or `inline dependency`. Placement (`runsOn`, `host`) is never drawn as an edge and is not in this table.

## Rules

1. **Document, do not infer (R1, R3).** Boxes and arrows come from recorded catalog data only. An object with no recorded relationship has no arrow. Never add a box or arrow because it seems likely.
2. **Show gaps instead of hiding them.** Retired and deprecated objects stay on the page, styled as such. A missing label, technology or tier is shown as not recorded.
3. **Report conflicts, do not resolve them.** If two recorded fields disagree, say so in your reply, quote both values, and leave the choice to the user.
4. **Use the user's scope.** If several patterns exist and none is named, run `--list` and ask which one.
5. **Check the result.** Confirm the reported relationship count is what you expect and read every warning back to the user (below).

## Warnings to read back

The generator prints a `N warnings` count line, then each distinct warning once in sorted order. Repeat the ones that matter to the user:

- `derived tier: <name> (<uid>) -> <tier>`: a placed object has no `diagramTier`; ask whether it should record one.
- `conflict: <component> runsOn <X>; group substrate is <Y>`: a recorded disagreement (see Recorded conflicts).
- `substrate also listed as deployable object`, `unknown substrate uid`, `substrate ... has type ...`: the service group's substrate is recorded inconsistently.
- `duplicate placement: <name> (<uid>) first placed in <A>; also listed in <B>`: the object is placed in more than one group; the first placement is shown.
- `data store not recorded: <name> (<uid>) has no runsOn data store service`: the data component is drawn in a `data store not recorded` container; ask which store it runs on.
- `undeclared network zone: <id> in <group>`: the entry names a zone the pattern does not declare; the object is drawn in the `zone not recorded` lane. `unknown flow '<value>' on <uid>`: the edge is drawn as if `flow` were absent.

## Delivering the page

- If your harness can publish a page or file for the user, publish the generated HTML so they get a link, and republish to the same place after each regeneration.
- Otherwise give the user the output file path and tell them to open it in a browser.
- Click a box to pin its relationships; the same uid is highlighted in both figures. Edge labels show on hover or pin above eight edges.
- Offer Mermaid or C4 text only when the user wants something to embed.
