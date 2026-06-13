---
type: documentation
title: "Personality Packs"
description: "Third-party cast packs for the Draftsman. Each pack replaces the default Meridian Team with an alternative set of named personas."
tags:
  - draft
  - personalities
timestamp: 2026-06-12T21:06:02-07:00
---
# Personality Packs

The Draftsman ships with a default cast — the Meridian Team — defined in
`framework/docs/soul.md`. Personality packs replace that cast with alternative
named personas while keeping the same routing logic, interaction styles, and
catalog behavior underneath.

## Available Packs

| Pack | Cast |
|---|---|
| `friends` | Monica, Rachel, Phoebe, Ross, Chandler, Joey |
| `big-bang-theory` | Howard, Penny, Raj, Sheldon, Amy, Bernadette |
| `cheers` | Carla, Norm, Woody, Cliff, Frasier, Sam |

## How To Activate A Pack

Copy or symlink the pack's `cast.yaml` to `.draft/personalities/<pack-name>/cast.yaml`
in your company DRAFT workspace and activate it in `.draft/workspace.yaml`:

```yaml
personalities:
  activePack: cheers
```

Any interaction style not specified in the pack falls back to the corresponding
Meridian Team member automatically.

## How To Write Your Own Pack

See [framework/docs/soul.md](../docs/soul.md#personality-packs) for the
`cast.yaml` schema. A pack only needs to define the styles you want to replace;
the rest inherit from Meridian.

## Framework vs. Company Workspace Location

These packs ship with the upstream DRAFT framework under `framework/personalities/`.
When a company vendors the framework, they appear at `.draft/framework/personalities/`.

Company-specific or licensed packs that are not part of the upstream framework
should live at `.draft/personalities/<pack-name>/cast.yaml` in the company
workspace — outside the vendored framework tree so they are not overwritten
during framework updates.
