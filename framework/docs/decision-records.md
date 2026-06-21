---
type: documentation
title: "DecisionRecords"
description: "DecisionRecords are first-class records for known risks,"
tags:
  - draft
  - documentation
  - decision_records
timestamp: 2026-06-12T21:06:02-07:00
---
# DecisionRecords

DecisionRecords are first-class records for known risks,
accepted decisions, mitigations, and follow-up paths tied to deployed
architecture.

The machine-readable object type is `decision_record`. The generated `uid` is
the stable machine reference; use `name` and `aliases` for human resolution.

## When To Use One

Create a DecisionRecord when architecture work needs to preserve one of these facts:

- a known runtime risk such as a single point of failure, unsupported platform,
  security gap, or migration dependency
- an accepted architectural decision with rationale
- a mitigation path that is not yet complete
- a product-specific exception attached to a SoftwareDeploymentPattern or service group

Do not use a DecisionRecord as a dumping ground for ordinary implementation notes.
If the detail is a stable reusable behavior, it likely belongs on a deployable
object, deployment configuration, TechnologyComponent configuration, or
SoftwareDeploymentPattern.

## YAML Shape

The authoritative schema is [decision-record.schema.yaml](../schemas/decision-record.schema.yaml).

At minimum, a DecisionRecord includes:
 
 - `uid`
 - `type: decision_record`
 - `name`
 - `category`
 - `status`
 - `description`
 - `affectedComponent`
 - `impact`
 
 Decision records also require `decisionRationale`. Optional fields `approver` and `approvalDate` are used to record approval metadata when a policy is enforced.
 
 ## Relationship To SoftwareDeploymentPatterns
 
 A SoftwareDeploymentPattern can reference DecisionRecords under `decisionRecords`. Use this
 when a product deployment needs visible risk or decision context without
 overloading the SoftwareDeploymentPattern prose.
 
 ## DecisionRecord Approval Policy
 
 Workspaces can declare a DecisionRecord approval policy in `.draft/workspace.yaml` under `decisionRecordApproval`. The validator enforces this policy when a DecisionRecord is moved to `status: accepted`.
 
 ### Declaration (`.draft/workspace.yaml`)
 
 ```yaml
 decisionRecordApproval:
   default:
     approver: team:architecture-review-board   # Fallback authority
   # optional decentralized rules (first match wins):
   rules:
     - match: { category: risk }                 # Matches category field value
       approver: team:architecture-review-board
     - match: { domain: security }               # Matches domain linked via capability
       approver: team:security-grc
     - match: { requirement: data-classification } # Matches specific requirement ID
       approver: team:data-governance
     - match: { affectedComponentOwner: true }   # Matches owner.team of the affected component
       approver: ownerTeam
   # or: enforcement: none   (default behavior if omitted)
 ```
 
 ### Schema Markings & Validation
 
 When a `decision_record` has `status: accepted` and a policy is active:
 1. **Scope Definition**: The record must declare either `affectedComponent` or `linkedObject`.
 2. **1:1 Scoping Enforced**: A DecisionRecord is intended to be a single unit of exception/approval. The validator will fail if a single DecisionRecord is referenced in multiple `requirementImplementations` across the catalog.
 3. **Approver & Date**: The record must declare `approver` (matching the policy-resolved expected approver) and `approvalDate` (ISO-8601 string or date) to verify proper transition markings.

