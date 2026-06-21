# Upstream Maintainer Tools

This directory contains DRAFT framework maintainer tooling that is **not
vendored** into company workspaces.

Files here are only accessible in the upstream `getdraft/draftsman` repository.
They must never be copied into `.draft/framework/` or referenced in company
workspace documentation.

## Contents

| File | Purpose |
|---|---|
| `review-framework.md` | `/draft review-framework` action — expert consultant review of the DRAFT framework for simplification and adoption quality |

## Why a separate directory?

The `framework/` directory is vendored verbatim into company workspaces as
`.draft/framework/`. Any file placed there is reachable by an AI agent connected
to a company repo. Maintainer-only tools belong here instead, where the vendoring
pipeline cannot pick them up.
