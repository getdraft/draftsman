#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from indexes import build_catalog_indexes
    from generate_browser import DEFAULT_WORKSPACE_ROOT, OUTPUT_PATH, display_path, load_objects
except ImportError:  # pragma: no cover - package import path for tests
    from framework.tools.indexes import build_catalog_indexes
    from framework.tools.generate_browser import DEFAULT_WORKSPACE_ROOT, OUTPUT_PATH, display_path, load_objects


INDEX_OUTPUT_NAME = "draft-indexes.json"


def default_output_path() -> Path:
    return OUTPUT_PATH.parent / "assets" / INDEX_OUTPUT_NAME


def write_indexes(indexes: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(indexes, default=str, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate canonical DRAFT catalog indexes.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE_ROOT, help="Workspace root to index")
    parser.add_argument("--output", type=Path, default=default_output_path(), help="JSON output path")
    args = parser.parse_args(argv)

    registry = load_objects(args.workspace.resolve())
    indexes = build_catalog_indexes(registry)
    write_indexes(indexes, args.output.resolve())
    print(
        f"Generated {display_path(args.output.resolve())} "
        f"with {len(indexes['domainCapability']['domains'])} domain entries "
        f"and {len(indexes['requirementImplementations']['rows'])} requirement implementation rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
