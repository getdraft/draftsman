# Schema Notes

The catalog uses YAML documents rather than a compiled schema toolchain, so the executable schema lives in three places together: the object documentation, the seed examples, and `tools/validate.py`.

## Machine-Readable Decisions

Known `notes` keys must remain machine-readable. When `autoscaling`, `loadBalancer`, or `minNodes` are present, the validator enforces constrained values so the catalog can support future automation.
Dependency rationale keys such as `relationshipRationales`,
`internalComponentRationales`, and `dependencyRationales` are also
machine-readable: use stable relationship names, component refs, `enabledBy`
refs, roles, or capability IDs as map keys.
