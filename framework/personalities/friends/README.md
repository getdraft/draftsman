---
type: documentation
title: "Friends Personality Pack"
description: "Draftsman cast personalities based on the Friends TV series cast."
tags:
  - draft
  - personalities
  - friends
timestamp: 2026-06-12T21:06:02-07:00
---
# Friends Personality Pack

Six friends from New York. One of them will help you draft architecture.

| Style | Cast Member | Character |
|---|---|---|
| Engineer | Monica | The perfectionist who already read your code before the meeting |
| PM | Rachel | The executive who learned to translate between worlds |
| Design Engineer | Phoebe | The one who questions how things are supposed to work |
| Security Engineer | Ross | The one with the receipts |
| Auditor | Chandler | Could this audit be any more complete? |
| People Leader | Joey | The one who actually listens |

## Installation

Copy or symlink `cast.yaml` to `.draft/personalities/friends/cast.yaml` in
your company DRAFT workspace. Then activate the pack in `.draft/workspace.yaml`:

```yaml
personalities:
  activePack: friends
```

If a style is not specified in the pack, the Draftsman falls back to the
corresponding Meridian Team member.

## Licensing

"Friends" and its character names are trademarks of Warner Bros. Entertainment
Inc. This pack uses character names and personalities for descriptive, functional
purposes within a developer tool. Organizations using this pack in commercial
products or client-facing deployments should verify their licensing position
with Warner Bros. independently before deployment.

This pack is provided as-is by the DRAFT framework for internal and
non-commercial use. It is not an official Warner Bros. product.
