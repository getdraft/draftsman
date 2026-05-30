# Delivery Models

## Purpose

Delivery models explain how a deployable service is operated. They apply to
Runtime Service, Data Store Service, and Edge/Gateway Service objects.

Delivery models are not object types.

## Values

| Delivery model | Meaning |
|---|---|
| `self-managed` | The company operates the service on a Host. The object must identify the Host and primary Technology Component. |
| `paas` | A provider-managed platform delivers the service inside the company's cloud or infrastructure boundary. |
| `saas` | A vendor-managed service may operate outside the company's infrastructure boundary. |
| `appliance` | The service maps directly to a vendor appliance or appliance-like product and must answer service-like operating requirements because there is no Host wrapper. |

## Draftsman Guidance

Choose the service object type from the behavior first. Choose the delivery
model second.

Examples:

- Amazon ECS Service is a Runtime Service with `deliveryModel: paas`.
- Amazon RDS PostgreSQL is a Data Store Service with `deliveryModel: paas`.
- Snowflake is a Data Store Service with `deliveryModel: saas`.
- F5 BIG-IP WAF is an Edge/Gateway Service with `deliveryModel: appliance`.
