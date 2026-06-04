# OWASP ASVS Provider Pack

This provider pack contains reusable DRAFT RequirementGroups for the OWASP Application Security Verification Standard (ASVS) v4.0.3.

## Included RequirementGroups

- `01KQQ4Q027-ASV1` — OWASP ASVS Level 1 baseline controls.
- `01KQQ4Q027-ASV2` — OWASP ASVS Level 2 controls, inheriting Level 1.
- `01KQQ4Q027-ASV3` — OWASP ASVS Level 3 controls, inheriting Level 2.

The groups use `activation: workspace`, so workspace administrators opt in by copying or vendoring this pack under `.draft/providers/owasp-asvs/` and activating the desired level in `.draft/workspace.yaml`:

```yaml
requirements:
  activeRequirementGroups:
    - 01KQQ4Q027-ASV2
  requireActiveRequirementGroupDisposition: false
```

ASVS requirements map to framework capability UIDs through `relatedCapability` and relationship criteria, keeping compliance intent decoupled from company-specific TechnologyComponent/vendor choices.

## Regenerating From Source

Use the importer to regenerate the pack from structured ASVS JSON:

```bash
python3 framework/tools/import_asvs.py \
  --source path/to/asvs.json \
  --output-dir providers/owasp-asvs/configurations/requirement-groups
```
