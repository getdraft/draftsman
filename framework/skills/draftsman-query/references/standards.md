# Standards and governance questions

Use the same evidence rules as the main skill: quote what a field says, and say when your source does not carry the answer.

## Security and compliance requirements

- Look in `configurations/requirement-groups/` and `.draft/framework/configurations/requirement-groups/`.
- Check the `requirements` list, `description` and `complianceControls`.
- Quote the exact requirement ID, describe the policy, and name the requirement-group file.

## Approved technology

- Search `catalog/` and `configurations/` for `technology_component` entries in the target domain.
- List approved components, supported major versions and delivery models (managed service, self-hosted, high availability), each with its file.

## Version lifecycle

- Check the component's lifecycle status: `approved`, `deprecated`, `end-of-life` or `prohibited`.
- If a version is deprecated or end-of-life, say it is not approved for new deployments, give the reason from the record, and name the approved alternative if one exists.

## Unapproved technology and exceptions

- Search the catalog for the technology. If it is not present, say it is not in the approved catalog you can see, not that it is forbidden.
- Describe the exception route: a `vocabulary_proposal` file under `configurations/vocabulary-proposals/`, submitted for architecture review. Writing it needs the Author profile; offer to hand off to `draftsman-author`.

## Worked answers

**"Is a requirement set for host protection on containers?"** A good answer cites the requirement-group file and the requirement ID it read, states the policy in the record's words, and notes any condition (for example, a different control for serverless containers) only if the record states it.

**"What are the approved options for a given database engine?"** List each approved `technology_component` with its file and delivery model, and mark which one the record recommends only if a field says so.

**"Is a given tool allowed?"** If it is absent from the approved components, answer that it is not present in the approved catalog you can see, and offer the exception route above.
