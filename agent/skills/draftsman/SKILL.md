---
name: draftsman
description: Deployable Reference Architecture Framework (DRAFT) catalog authoring, validation, maturity scoring, and GitHub PR workflows.
---

# Draftsman Skill

## When to Use
Use whenever performing architectural catalog tasks, including:
- Authoring or editing DRAFT catalog objects (`product_component`, `data_store_service`, `runtime_service`, `edge_gateway_service`, `software_deployment_pattern`)
- Validating DRAFT workspaces with `validate.py`
- Running architecture maturity rubric evaluations (`ARCHITECTURE_MATURITY.md`)
- Handling `/draft` and `/draftsman` slash commands
- Creating GitHub pull requests for architecture proposals

## Workflow Steps

### 1. Workspace Discovery & Context Setup
1. Check repository root for `.draft/workspace.yaml` and `.draft/framework/`.
2. If `.draft/framework/` exists, use `.draft/framework/schemas/` as authoritative contracts.
3. If working in the upstream framework repo, do NOT write company architecture objects into `framework/` or `examples/` — request or switch to the company workspace repo first.

### 2. Catalog Authoring & Editing
1. Search `catalog/` and `configurations/` to avoid creating duplicate objects or taxonomy entries.
2. Read the corresponding schema file under `.draft/framework/schemas/<object-type>.schema.yaml`.
3. Construct or modify YAML files using standard field naming and approved Technology Component identifiers.
4. If an unapproved technology or non-standard vocabulary value is used, flag it clearly as a proposed non-standard choice or write a `vocabulary_proposal` file in `configurations/vocabulary-proposals/`.

### 3. Workspace Validation
Run the DRAFT validator script:
```bash
python3 .draft/framework/tools/validate.py --workspace .
```
If errors are reported:
- Fix missing required fields, unresolvable references, or schema syntax errors.
- If UID repair is suggested, run `python3 .draft/framework/tools/repair_uids.py --workspace .`.

### 4. Documentation & Static Browser Generation
Regenerate static browser assets after catalog changes:
```bash
python3 .draft/framework/tools/generate_browser.py --workspace . --output docs/index.html
```

### 5. Maturity Scoring Procedure
When asked to score SDP maturity:
1. Read `ARCHITECTURE_MATURITY.md`.
2. Inspect the target `software_deployment_pattern` YAML file and its referenced components.
3. Score across vector criteria (Environments, Data, Gateway, Security, Observability, Deployment).
4. Output the standardized Phase 4 scorecard matrix.

### 6. GitHub Integration
Commit changes and submit PR:
```bash
git checkout -b draft/<feature-name>
git add catalog/ configurations/ docs/
git commit -m "feat(draft): add <component-name> architecture definition"
git push origin draft/<feature-name>
gh pr create --title "feat(draft): add <component-name> architecture definition" --body "Architectural catalog addition validated by Draftsman."
```
