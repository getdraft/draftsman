# Draftsman role: protocols the workflow skills share

These protocols apply to any harness. Where a step needs a capability, the profile in `../SKILL.md` says whether you have it.

## Product registration (Author profile)

- Scaffold `catalog/engineering/product-registrations/product-reg-<name>.yaml` against `product-registration.schema.yaml`.
- Set `repoUrl`, `sdpPath` (`.draft/sdp.yaml`) and `owner.team`.
- Search the catalog first. Do not create a second registration for a product that already has one.

## Local repository initialisation (Author profile)

- Inspect the code repository for build and infrastructure assets such as `Dockerfile`, `docker-compose.yml`, `main.tf`, `pom.xml`, `package.json` and `requirements.txt`.
- Scaffold `.draft/sdp.yaml` and `.github/workflows/draft-sync.yml`.
- Run `python3 .draft/framework/tools/validate.py --workspace .` before you say you are done.
- Anything you derive from a file name or a dependency list is inferred (rule R6), not recorded.

## Architecture questions (Query profile)

1. Answer from the pre-built index (`AI_INDEX.md`, `docs/assets/draft-indexes.json`) or, if you can read the catalog, from the files you actually open.
2. Give ports, protocols and network zones only when a field carries them.
3. Apply Evidence Discipline in `../SKILL.md`: Recorded, Inferred, Unknown.

For the full question patterns, load the `draftsman-query` skill. For onboarding a product, see `onboarding.md`.
