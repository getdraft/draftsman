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

## Validation Baseline

`.draft/validation-baseline.yaml` records the objects that already break a ratcheted validation rule, so a new rule binds an object only when that object changes. It holds `schemaVersion: '1.0'`, `frameworkVersion` (the framework version that wrote it) and `entries`, a list of `{rule, uid, hash}` sorted by rule then uid. `hash` is the sha256 of `yaml.safe_dump(object, sort_keys=True, allow_unicode=True)` for the object as loaded. A ratcheted violation whose `(rule, uid)` is listed with the same hash is a warning prefixed `baseline:`; any other ratcheted violation is an error. An entry whose object no longer exists or no longer violates prints a `stale baseline entry` warning. Only `python3 .draft/framework/tools/validate.py --workspace . --write-baseline` changes the file (it drops stale entries and exits 0); `--no-baseline` ignores it. Run `--write-baseline` when vendoring a new framework version and commit the file with the update.
