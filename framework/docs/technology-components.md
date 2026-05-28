# Technology Components

## What A Technology Component Is

A Technology Component is a discrete vendor product object. It records one
vendor product at one product version so deployable objects can compose real
products instead of generic categories.

That definition matters. A Technology Component is not "Windows Server" in the
abstract. It is a named object such as "Microsoft Windows Server 2022". It is
not "SQL Server" as a general category. It is a named object such as "Microsoft
SQL Server 2019" or "Microsoft SQL Server 2022".

The framework uses that level of specificity because deployable architecture
becomes misleading very quickly if version and vendor lifecycle are left
implicit.

## YAML Shape

Technology Components follow
[technology-component.schema.yaml](../schemas/technology-component.schema.yaml).

At minimum, a Technology Component YAML should include:

- `schemaVersion`
- `uid`
- `type: technology_component`
- `name`
- `vendor`
- `productName`
- `productVersion`
- `classification`
- `catalogStatus`

## Classifications

Every Technology Component must declare exactly one classification.

| Classification | Meaning |
|---|---|
| Operating System | A vendor product that is the operating system. |
| Compute Platform | A vendor product that provides the physical or virtual compute substrate the operating system runs on. |
| Software | A vendor product that runs locally and does not require an external interaction. |
| Agent | A vendor product that runs locally and requires an external interaction. |

The validator uses these classifications when checking whether a deployable
object is built from the right kinds of Technology Components.

## Lifecycle

Vendor lifecycle facts remain on the Technology Component under
`vendorLifecycle`. Company adoption does not live as top-level lifecycle status
on the Technology Component. It lives on Capability implementation entries,
because a company may approve the same product differently for different
capabilities.

The capability owner is the authority that assigns lifecycle states such as
preferred, candidate, existing-only, deprecated, or retired.

## What A Technology Component Is Not

A Technology Component is not a deployment artifact. It does not say where or
how many times a product is deployed.

A Technology Component is not a Host, Runtime Service, Data-at-Rest Service,
Edge/Gateway Service, Product Service, or Software Deployment Pattern. Those
objects describe deployable behavior. Technology Components describe the vendor
products those deployable objects use.

## How Technology Components Are Used

Technology Components become useful when they are referenced by deployable
objects:

- A Host uses an Operating System Technology Component and a Compute Platform
  Technology Component.
- A Runtime Service or Data-at-Rest Service references one primary Technology
  Component that provides the service capability, such as IIS or SQL Server.
- An Edge/Gateway Service with `deliveryModel: appliance` may reference the
  appliance product Technology Component while carrying the service-like
  operating answers on the service object.

When an Agent Technology Component is used inside a deployable object, the
deployable object must also have a relationship object (with this object as
source) that represents the agent's platform dependency, unless an architectural
decision explains why the interaction is intentionally omitted via
`architectureNotes.agentInteractionExceptions`.

## Appliance Products

When a vendor appliance or appliance-like product delivers useful architecture
behavior, model the vendor product/version as a Technology Component and model
the deployable behavior as a Runtime Service, Data-at-Rest Service, or
Edge/Gateway Service with `deliveryModel: appliance`.

This preserves the Technology Component as the product lifecycle object and
keeps the service object responsible for authentication, logging, monitoring,
patch/update model, resilience, network placement, failure domain, and
compliance posture.

## How To Add A New Technology Component

1. Decide whether the object is an Operating System, Compute Platform, Software,
   or Agent Technology Component.
2. Create the YAML file in `catalog/technology-components/`.
3. Add or repair the generated `uid`.
4. Fill in vendor, product, product version, classification, owner, catalog
   status, and vendor lifecycle facts.
5. Add `capabilities` if the Technology Component itself satisfies reusable
   capabilities.
6. Add `configurations` if a named Technology Component configuration satisfies
   reusable capabilities.
7. Run `python3 framework/tools/validate.py`.

Do not place a deployable object in a capability implementation lifecycle list.
If a service is governed by technology lifecycle, model the specific vendor
product and version as a Technology Component and let the deployable object
compose that product into useful architecture.

## Configuration Network Bindings

Technology Component `configurations` can include `networkBindings` when a
specific configuration variant exposes or uses known network behavior. Put this
data on the configuration, not the top-level Technology Component, so different
variants can declare different ports, protocols, or traffic directions.

Example:

```yaml
configurations:
  - id: amqp-listener
    name: AMQP Listener
    description: Standard AMQP listener configuration.
    capabilities:
      - 01KQQ4Q026-D04B
    networkBindings:
      - port: 5672
        protocol: AMQP
        direction: inbound
        description: Client AMQP listener.
```

Deployable objects can reference that named variant from an
`internalComponents` entry:

```yaml
internalComponents:
  - ref: 01KQS0TF66-RBMQ
    role: broker-client
    configuration: amqp-listener
```

When `configuration` is present, validation requires the `ref` to resolve to a
Technology Component and the named configuration to exist on that component.
