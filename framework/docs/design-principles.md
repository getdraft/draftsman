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

## 5. Compliance is authoring, not auditing

RequirementGroups embed compliance questions into the normal architecture
interview. Evidence is captured as a byproduct of describing what was built,
not as a separate audit exercise run after the fact.

This means compliance posture is always current. There is no "compliance
snapshot" that goes stale — the catalog IS the evidence. Adding a new service
to the catalog adds it to the compliance posture automatically.

---

## 6. The AI owns the YAML, the human owns the facts

Engineers and architects describe their systems in plain language. The
Draftsman handles translation into valid YAML, schema compliance, UID
generation, and catalog structure. Humans should never be asked to invent UIDs,
choose object types by name, recall field names, or think about schema
structure directly.

The interview surfaces architecture facts. Everything else is the Draftsman's
job.

---

## 7. Uncertainty is first-class

Unresolved facts belong in DraftingSessions, not hidden in prose or forced to
premature closure. When the answer to an architecture question is genuinely
unknown, recording that uncertainty explicitly is more valuable than inventing
a plausible answer.

A catalog with visible, tracked gaps is more trustworthy than one with hidden
assumptions. DraftingSessions make uncertainty actionable — they preserve
context, identify who needs to answer what, and make it possible to resume work
without re-interviewing.
