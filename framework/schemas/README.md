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

`.draft/validation-baseline.yaml` records the objects that already break a ratcheted validation rule, so a new rule binds an object only when that object changes. It holds `schemaVersion: '1.0'`, `frameworkVersion` (the framework version that wrote it) and `entries`, a list of `{rule, uid, hash}` sorted by rule then uid. `hash` is the sha256 of `yaml.safe_dump(object, sort_keys=True, allow_unicode=True)` for the object as loaded. A ratcheted violation whose `(rule, uid)` is listed with the same hash is a warning prefixed `baseline:`; any other ratcheted violation is an error. An entry whose object no longer exists or no longer violates prints a `stale baseline entry` warning. Only `python3 .draft/framework/tools/validate.py --workspace . --write-baseline` changes the file (it drops stale entries, then reports like a normal run: exit 0 unless other errors remain); `--no-baseline` ignores it. An empty or whitespace-only file counts as no entries; a duplicate `(rule, uid)` entry is an error. `--write-baseline` refuses to write (and exits 1) while YAML parse or object patch failures exist, so an unparseable object cannot silently drop out of the baseline. Run `--write-baseline` when vendoring a new framework version and commit the file with the update.

`serviceRole` is an optional `definition | instance` field on `runtime_service`, `data_store_service`, `network_service`, `host` and `ai_gateway`. A definition is the infrastructure team's standard solution: a pattern deploys it through `substrate` or `runsOn` and it is never a relationship endpoint. An instance is a concrete service, such as an external service, that relationships may name. When the field is absent, an object whose file is under the service definitions folder is a definition and any other object is an instance. The folder is `paths.serviceDefinitionsFolder` in `.draft/workspace.yaml` when set, else the catalog folder named `shared-services` in `paths.catalogFolders`, else none (every object without the field is then an instance). Set `serviceRole: instance` on an external service that lives in the definitions folder. The helper is `service_role(obj, path, workspace_config)` in `validate.py`.

Two ratcheted rules (see the baseline above) enforce ownership:

- `sdp-placement-types`: every `serviceGroups[].deployableObjects[].ref` on a `software_deployment_pattern` must resolve to a `product_component` or `data_component`. The message names the object, its type and the field that carries it: a runtime or host belongs in the service group's `substrate`, a data store in a data component's `runsOn`, an edge or external service in a relationship from the consuming component (or the reference architecture). An unresolvable ref is left to the reference check.
- `relationship-definition-endpoint`: a `relationship` whose `source` or `target` resolves to a definition violates. A definition carries no flows; record the relationship on the component or instance, and for an external service that lives in the definitions folder set `serviceRole: instance` on that object.
