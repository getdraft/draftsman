---
type: documentation
title: "DRAFT Exporters"
description: "DRAFT catalogs are authoritative YAML — the source of truth for architecture"
tags:
  - draft
  - documentation
  - exporters
timestamp: 2026-06-12T21:06:02-07:00
---
# DRAFT Exporters

DRAFT catalogs are authoritative YAML — the source of truth for architecture
governance, lifecycle, and compliance. Exporters are separate tools that read
the catalog and emit derived output for external portals and diagram tools.
They are additive and non-destructive: no exporter modifies catalog objects.

## Available Exporters

| Tool | Output | Command |
|---|---|---|
| `generate_browser.py` | Static GitHub Pages browser | `python3 framework/tools/generate_browser.py` |
| `generate_backstage.py` | Backstage `catalog-info.yaml` files | `python3 framework/tools/generate_backstage.py` |
| `generate_c4.py` | C4 L2 Container diagrams (Structurizr DSL + Mermaid) | `python3 framework/tools/generate_c4.py` |

---

## Backstage Exporter

`framework/tools/generate_backstage.py` reads the DRAFT catalog and emits valid
Backstage entity files into `<workspace>/backstage/` (configurable with `--output`).

### Object mapping

| DRAFT type | Backstage kind | Notes |
|---|---|---|
| `domain` | `System` | Groups components by business domain |
| `system` | `System` | Groups components by explicit boundary |
| `runtime_service` | `Component` (type: service) | |
| `data_store_service` | `Component` (type: service) | |
| `network_service` | `Component` (type: service) | |
| `product_component` | `Component` (type: service) | |
| `technology_component` | `Resource` | |

### Lifecycle mapping

| DRAFT `lifecycleStatus` | Backstage `spec.lifecycle` |
|---|---|
| `preferred` | `production` |
| `existing-only` | `production` |
| `candidate` | `experimental` |
| `deprecated` | `deprecated` |
| `retired` | `deprecated` |

### Usage

```bash
# Write to backstage/ in the workspace root
python3 framework/tools/generate_backstage.py --workspace /path/to/company-draft-repo

# Preview without writing files
python3 framework/tools/generate_backstage.py --workspace /path/to/company-draft-repo --dry-run

# Write to a custom output directory
python3 framework/tools/generate_backstage.py --workspace /path/to/company-draft-repo --output /path/to/backstage-catalog
```

Each DRAFT object produces one `catalog-info.yaml` file named by its UID.
The generated files can be registered with Backstage using its catalog ingestion
mechanism — either by pointing the Backstage catalog at the output directory or
by committing the files to a repo that Backstage already watches.

DRAFT annotations (`draft/uid`, `draft/type`, `draft/lifecycleStatus`) are added
to every entity so Backstage can link back to the DRAFT catalog.

---

## C4 Exporter

`framework/tools/generate_c4.py` reads the DRAFT catalog and emits C4 L2
Container diagrams. It generates one diagram per `system` object; if no system
objects are defined, it generates one diagram containing all deployable objects.

### Relationship data

The C4 exporter uses `relationship` objects (added in framework 0.24.0) to
render inter-container edges. Without relationship objects the diagram shows
containers without edges, which is useful as an inventory but not a full C4
diagram. See [Relationship Authoring](draftsman.md#relationship-authoring) for
how to add relationships to the catalog via the Draftsman.

### Output formats

| Format | Extension | Use with |
|---|---|---|
| Structurizr DSL | `.dsl` | [structurizr.com](https://structurizr.com), `structurizr-cli` |
| Mermaid C4 | `.md` | GitHub markdown, Confluence, Notion |

### Usage

```bash
# Generate both formats to c4/ in the workspace root
python3 framework/tools/generate_c4.py --workspace /path/to/company-draft-repo

# Generate only Mermaid output
python3 framework/tools/generate_c4.py --workspace /path/to/company-draft-repo --format mermaid

# Preview without writing files
python3 framework/tools/generate_c4.py --workspace /path/to/company-draft-repo --dry-run

# Write to a custom output directory
python3 framework/tools/generate_c4.py --workspace /path/to/company-draft-repo --output /path/to/diagrams
```

---

## Writing a Custom Exporter

Exporters follow a simple convention: read catalog YAML, emit derived output.

The pattern used by all built-in exporters:

1. Discover YAML files by walking `catalog/` and `configurations/` in the workspace root.
2. Load each file and filter by `type` field.
3. Build a lookup by `uid` for cross-reference resolution.
4. Transform each object into the target format.
5. Write output files or print to stdout.

The shared catalog loading logic is in `generate_browser.py` (`load_objects`),
`generate_backstage.py` (`load_catalog`), and `generate_c4.py` (`load_catalog`).
Custom exporters can copy this pattern directly.

### Minimal exporter template

```python
#!/usr/bin/env python3
import sys
from pathlib import Path
import yaml

WORKSPACE_ROOT = Path("/path/to/company-draft-repo")
SKIP_DIRS = {"tools", "schemas", "docs", ".github", ".git", ".draft"}

def load_catalog(workspace_root):
    catalog = {}
    for path in sorted((workspace_root / "catalog").rglob("*.yaml")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            data = yaml.safe_load(path.read_text()) or {}
            if data.get("uid") and data.get("type"):
                catalog[data["uid"]] = data
        except Exception:
            pass
    return catalog

def main():
    catalog = load_catalog(WORKSPACE_ROOT)
    for uid, obj in catalog.items():
        if obj.get("type") == "runtime_service":
            print(f"{obj['name']} ({uid})")

if __name__ == "__main__":
    main()
```

### What to include in a company exporter

- A `--workspace` argument that defaults to the expected workspace root
- A `--dry-run` flag that prints to stdout instead of writing files
- `draft/uid` and `draft/type` annotations or comments in output so catalog
  objects stay traceable across the export boundary
- No writes to `catalog/`, `configurations/`, or `.draft/` — exporters are read-only
