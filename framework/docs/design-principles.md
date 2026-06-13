---
type: documentation
title: "Design Principles"
description: "DRAFT is opinionated."
tags:
  - draft
  - documentation
  - design_principles
timestamp: 2026-06-12T21:06:02-07:00
---
# Design Principles

DRAFT is opinionated. These principles explain the reasoning behind the
opinions — why the framework works the way it does, and how to make good
judgment calls when the rules don't cover an edge case.

---

## 1. Reuse over invention

Infrastructure objects are defined once and referenced by many. A company with
fifty services on Kubernetes has one EKS Host standard and one Kubernetes
RuntimeService — not fifty. Creating duplicate Hosts, RuntimeServices,
DataStoreServices, or TechnologyComponents is always wrong.

The catalog scales through shared building blocks, not through repetition.
Before creating any infrastructure object, search the effective catalog. If a
matching object exists, reference it.

---

## 2. Stubs are progress, not debt

An incomplete catalog entry is better than no entry. The `stub → incomplete →
complete` progression is intentional — it lets teams capture what they know now
and deepen it over time through normal work, without blocking on perfection.

A stub that gets referenced is doing its job. A catalog that waits for
completeness before capturing anything captures nothing.

---

## 3. Governance is binary

Approvals are yes or no. A TechnologyComponent is either the company's
approved choice for a capability or it is not. Conditional approvals — approved
only for certain services, only until a certain date, only under certain
conditions — create governance overhead that is rarely maintained and usually
ignored.

When context or constraints matter, record them in a DecisionRecord. That is
where architectural rationale lives. The lifecycle status is the governance
signal — keep it clean.

---

## 4. The catalog serves automation, not documentation

The end state is deployable architecture facts that can drive pipelines,
infrastructure automation, and compliance tooling. Narrative description is a
byproduct, not the goal.

When there is a choice between a structured field and a prose note, prefer the
structured field. When there is a choice between a vague answer that closes a
question and an honest gap that stays open, prefer the honest gap. Automation
cannot act on prose; it can act on structured facts.

---

## 5. Object types are requirement scopes

DRAFT object types are not generic catalog buckets. They exist because the
Draftsman needs to know which intrinsic architecture obligations apply to the
thing being authored.

A Host must answer host questions. A RuntimeService must answer runtime and
substrate questions. A DataStoreService must answer persistence, backup,
recovery, and encryption-at-rest questions. A NetworkService must answer
network-function, topology, protocol, and traffic-control questions. The object
type gives RequirementGroups a stable scope so the Draftsman can ask the right
questions without guessing from product names.

Object type is not the only requirement scope. Placement, exposure, delivery
model, capability, data classification, and followed ReferenceArchitecture can
also create obligations. Requirements that arise because something is in a
perimeter zone, exposes public traffic, processes regulated data, or follows a
specific pattern should be scoped with RequirementGroup applicability and
SoftwareDeploymentPattern context, not by inventing another object type.

Use this rule when the model is unclear: create or keep a distinct object type
only when the artifact has intrinsic required questions that cannot be expressed
clearly through existing object type plus contextual RequirementGroup scope.

---

## 6. ReferenceArchitectures encode compliant composition

RequirementGroups define obligations. ReferenceArchitectures show approved
multi-object patterns for satisfying obligations that no single object can
answer alone.

For example, a RequirementGroup may say that web traffic in a perimeter zone
must be protected by an approved WAF capability. The compliant answer is not a
field on the web RuntimeService. A ReferenceArchitecture can show the required
composition: the web RuntimeService sits in the appropriate zone, traffic enters
through an approved WAF NetworkService, and the SoftwareDeploymentPattern records
the relationship or interaction path. If the system intentionally does not
follow that pattern, the deviation belongs in a DecisionRecord.

ReferenceArchitectures and RequirementGroups therefore work together:
RequirementGroups state what must be true; ReferenceArchitectures describe how a
valid architecture normally makes it true.

---

## 7. Compliance is authoring, not auditing

RequirementGroups embed compliance questions into the normal architecture
interview. Evidence is captured as a byproduct of describing what was built,
not as a separate audit exercise run after the fact.

This means compliance posture is always current. There is no "compliance
snapshot" that goes stale — the catalog IS the evidence. Adding a new service
to the catalog adds it to the compliance posture automatically.

---

## 8. The AI owns the YAML, the human owns the facts

Engineers and architects describe their systems in plain language. The
Draftsman handles translation into valid YAML, schema compliance, UID
generation, and catalog structure. Humans should never be asked to invent UIDs,
choose object types by name, recall field names, or think about schema
structure directly.

The interview surfaces architecture facts. Everything else is the Draftsman's
job.

---

## 9. Uncertainty is first-class

Unresolved facts belong in DraftingSessions, not hidden in prose or forced to
premature closure. When the answer to an architecture question is genuinely
unknown, recording that uncertainty explicitly is more valuable than inventing
a plausible answer.

A catalog with visible, tracked gaps is more trustworthy than one with hidden
assumptions. DraftingSessions make uncertainty actionable — they preserve
context, identify who needs to answer what, and make it possible to resume work
without re-interviewing.
