---
type: documentation
title: "Delivery Models"
description: "Delivery models explain how a deployable service is operated."
tags:
  - draft
  - documentation
  - delivery_models
timestamp: 2026-06-12T21:06:02-07:00
---
# Delivery Models

## Purpose

Delivery models explain how a deployable service is operated. They apply to
RuntimeService, DataStoreService, and NetworkService objects.

Delivery models are not object types.

## Values

| Delivery model | Meaning |
|---|---|
| `self-managed` | The company operates the service on a Host. The object must identify the Host and primary TechnologyComponent. |
| `paas` | A provider-managed platform delivers the service inside the company's cloud or infrastructure boundary. |
| `saas` | A vendor-managed service may operate outside the company's infrastructure boundary. |
| `appliance` | The service maps directly to a vendor appliance or appliance-like product and must answer service-like operating requirements because there is no Host wrapper. |

## Draftsman Guidance

Choose the service object type from the behavior first. Choose the delivery
model second.

Examples:

- Amazon ECS Service is a RuntimeService with `deliveryModel: paas`.
- Amazon RDS PostgreSQL is a DataStoreService with `deliveryModel: paas`.
- Snowflake is a DataStoreService with `deliveryModel: saas`.
- F5 BIG-IP WAF is a NetworkService with `deliveryModel: appliance`.
