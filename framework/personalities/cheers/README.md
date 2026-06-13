---
type: documentation
title: "Cheers Personality Pack"
description: "Draftsman cast personalities based on the Cheers TV series cast."
tags:
  - draft
  - personalities
  - cheers
timestamp: 2026-06-12T21:06:02-07:00
---
# Cheers Personality Pack

Where everybody knows your name. Where nobody knows your YAML.

| Style | Cast Member | Character |
|---|---|---|
| Engineer | Carla | Blunt, efficient, already knows the answer |
| PM | Norm | Knows everyone, speaks in outcomes, always at his usual spot |
| Design Engineer | Woody | Asks the simple questions that turn out to matter |
| Security Engineer | Cliff | It's a little-known fact that he's never missed a requirement |
| Auditor | Frasier | Analytical, precise, and he is listening |
| People Leader | Sam | Owns the bar, knows every corner of it |

## Installation

Copy or symlink `cast.yaml` to `.draft/personalities/cheers/cast.yaml` in
your company DRAFT workspace. Then activate the pack in `.draft/workspace.yaml`:

```yaml
personalities:
  activePack: cheers
```

If a style is not specified in the pack, the Draftsman falls back to the
corresponding Meridian Team member.

## Licensing

"Cheers" and its character names are trademarks of Paramount Pictures / NBC.
This pack uses character names and personalities for descriptive, functional
purposes within a developer tool. Organizations using this pack in commercial
products or client-facing deployments should verify their licensing position
with Paramount independently before deployment.

This pack is provided as-is by the DRAFT framework for internal and
non-commercial use. It is not an official Paramount or NBC product.
