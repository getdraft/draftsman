---
type: documentation
title: "Big Bang Theory Personality Pack"
description: "Draftsman cast personalities based on The Big Bang Theory TV series cast."
tags:
  - draft
  - personalities
  - big-bang-theory
timestamp: 2026-06-12T21:06:02-07:00
---
# Big Bang Theory Personality Pack

A group of brilliant people who communicate very differently.
One of them is exactly right for your session.

| Style | Cast Member | Character |
|---|---|---|
| Engineer | Howard | The only one who actually builds things that leave the ground |
| PM | Penny | The one who learned that outcomes matter more than details |
| Design Engineer | Raj | Thinks in vast systems and fine aesthetic details simultaneously |
| Security Engineer | Sheldon | Does not accept "it's fine" as an architectural posture |
| Auditor | Amy | Applies neuroscience rigor to architecture evidence |
| People Leader | Bernadette | Small but the room adjusts to her |

## Installation

Copy or symlink `cast.yaml` to `.draft/personalities/big-bang-theory/cast.yaml`
in your company DRAFT workspace. Then activate the pack in `.draft/workspace.yaml`:

```yaml
personalities:
  activePack: big-bang-theory
```

If a style is not specified in the pack, the Draftsman falls back to the
corresponding Meridian Team member.

## Licensing

"The Big Bang Theory" and its character names are trademarks of Warner Bros.
Entertainment Inc. / Chuck Lorre Productions. This pack uses character names
and personalities for descriptive, functional purposes within a developer tool.
Organizations using this pack in commercial products or client-facing deployments
should verify their licensing position independently before deployment.

This pack is provided as-is by the DRAFT framework for internal and
non-commercial use. It is not an official Warner Bros. or Chuck Lorre product.
