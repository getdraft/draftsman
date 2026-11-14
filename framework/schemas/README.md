# Schema Notes

The catalog uses YAML documents rather than a compiled schema toolchain, so the executable schema lives in three places together: the object documentation, the seed examples, and `tools/validate.py`.

## Machine-Readable Decisions

Known `notes` keys must remain machine-readable. When `autoscaling`, `loadBalancer`, or `minNodes` are present, the validator enforces constrained values so the catalog can support future automation.
Dependency rationale keys such as `relationshipRationales`,
`internalComponentRationales`, and `dependencyRationales` are also
machine-readable: use stable relationship names, component refs, `enabledBy`
refs, roles, or capability IDs as map keys.

## Diagram Layout

`diagram_layout` (`diagram-layout.schema.yaml`) records the box order a person wants for one `software_deployment_pattern` in the page that `framework/tools/generate_diagram.py` renders. `pattern` must be the uid of a deployment pattern; the validator fails otherwise. `logical` and `deployment` list `{ref, position}` entries, where `ref` is a catalog uid or an `ext:` id and `position` is a positive integer; a `ref` that resolves to nothing is a warning. Keep the file beside the pattern file. `generate_diagram.py --sdp <pattern> --write-layout` creates or updates it from the computed order. An in-place update rewrites the file and drops hand-written comments.
