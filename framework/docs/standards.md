# Deployable Objects

## Current Terminology

DRAFT previously used the word "Standard" for reusable deployable building
blocks. The current framework uses explicit object types instead:

- Host
- RuntimeService
- DataStoreService
- NetworkService
- ProductComponent

For the full object model, see [DRAFT Object Types](object-types.md).

## Authoring Rule

When drafting architecture, identify the behavior first, then select the object
type and delivery model:

- operating platform: Host
- application, web, cache, worker, or runtime behavior: RuntimeService
- database, file, object, search, analytics, or storage behavior:
  DataStoreService
- firewall, WAF, load balancer, API gateway, ingress, or proxy behavior:
  NetworkService
- first-party custom binary or black-box application behavior: ProductComponent

PaaS, SaaS, appliance, and self-managed describe how a service is delivered.
They do not create separate object types.
