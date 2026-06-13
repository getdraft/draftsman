---
type: documentation
title: "Naming Conventions"
description: "When a DRAFT object type is referred to by name in prose, headings, schema"
tags:
  - draft
  - documentation
  - naming_conventions
timestamp: 2026-06-12T21:06:02-07:00
---
# Naming Conventions

## Object Type Names

When a DRAFT object type is referred to by name in prose, headings, schema
hints, requirement-group names, validation messages, and the browser, write it
in PascalCase: `TechnologyComponent`, `Host`, `RuntimeService`,
`DataStoreService`, `NetworkService`, `ProductComponent`,
`DataComponent`, `ReferenceArchitecture`, `SoftwareDeploymentPattern`,
`Capability`, `RequirementGroup`, `Domain`, `DecisionRecord`, `DraftingSession`,
and `ObjectPatch`. Single-word types such as `Host`, `Capability`, and `Domain`
are unaffected. There are no spaces and no slash in `NetworkService`.

This is the display convention only. The machine identifier for each type stays
snake_case (`technology_component`, `data_store_service`, `network_service`,
`reference_architecture`), and schema filenames and catalog folder names keep
their existing kebab-case form (`data-store-service.schema.yaml`,
`catalog/network-services/`). When a type name appears as an ordinary
lowercase common noun inside a sentence ("the runtime service tier"), no
PascalCase is required.

## UID, Name, And Aliases

DRAFT first-class objects use an opaque generated `uid` for machine identity and
a human-readable `name` for conversation. Humans should not be asked to type or
remember UIDs.

The `uid` exists only so references remain stable when a team renames an object.
It uses this format:

```text
^[0-9A-HJKMNP-TV-Z]{10}-[0-9A-HJKMNP-TV-Z]{4}$
```

When an object is renamed, keep the `uid` unchanged and append the prior display
name to `aliases`. The Draftsman should resolve user references by exact name,
alias, file path, close name match, and only then UID.

## What Still Uses Local IDs

Some nested values still use local `id` fields because they are not first-class
objects. Examples include RequirementGroup requirement IDs, TechnologyComponent configuration IDs, DraftingSession question IDs, provider IDs, and
company business pillar IDs.

These local IDs are scoped to the object or workspace section that contains
them. They are not global object identity.

## File Naming

File names should remain descriptive and stable enough for review:

- `catalog/technology-components/technology-os-microsoft-windows-server-2022.yaml`
- `catalog/hosts/host-windows-server-2022-ec2.yaml`
- `catalog/software-deployment-patterns/software-deployment-student-health.yaml`

Changing a file name does not change object identity. The `uid` is the stable
reference.

## Repairing UID Problems

Validation reports missing, malformed, duplicate, or legacy object identity and
prints both a suggested UID and an explicit repair command.

To repair one file:

```bash
python3 framework/tools/repair_uids.py --workspace examples --file catalog/example.yaml --uid 01KQQ4Q027-ABCD
```

To repair a company workspace from inside the company repo:

```bash
python3 .draft/framework/tools/repair_uids.py --workspace .
```

The repair tool rewrites exact object references across the workspace. It does
not rewrite narrative prose.
