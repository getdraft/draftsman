---
name: draftsman-query
description: Use when someone asks a question about a company's architecture catalog (ports, APIs, datastores, dependencies, ownership) or about its technology standards, security requirements, version lifecycle or exceptions. Works in the Query or Author profile.
---

# Draftsman Query

Load `draftsman-core` first; its Evidence Discipline rules bind every answer here. This skill works in the **Query profile** and also in the Author profile. It never writes catalog files.

## Answering rules

1. **Read fields, not names.** A value is recorded only if you read it from a named field. A name that looks structured, such as `A → B` or `service-x-prod`, is prose. Using it is inference, and inference is labelled.
2. **Absent field, absent answer.** If `technology`, `port`, `protocol` or `label` is not present, say the source you can see does not carry it. Never fill the gap with a category you guessed from a name.
3. **Say what you cannot see.** Answer about your index or the files you opened, not about "the catalog".
4. **Qualify every count.** Say how you got the number, and never call a substring match complete.

## Question types

| Question | Where to look | Fields |
| :--- | :--- | :--- |
| Is an API exposed for X? | index entries for `product_component` and `software_deployment_pattern` matching X | linked `edge_gateway_service`; `interfaces` or `api_spec`; protocols and routing |
| What port does X listen on? | `runtime_service`, `product_component`, container profiles | listener ports, ingress ports, network zone |
| What does X write to? | `software_deployment_pattern` links between `product_component` and `data_store_service` | the link fields |
| Which services use Y? | reverse search across every `software_deployment_pattern` in the index | the dependency fields |
| How do I get my product into DRAFT? | `draftsman-core/references/onboarding.md` | not applicable |
| Is a requirement, technology or version approved? | see `references/standards.md` | requirement groups, technology components, lifecycle status |

When a request is to create or change a record, point the person to the Author profile and the `draftsman-author` skill.

## References

- `references/standards.md`: security requirements, approved technology, version lifecycle, exceptions, with worked answers.
